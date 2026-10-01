"""词典管理（2.1 基建，D2026-0930-03 ②④）
================================================================================
数据根 ``dict/`` 布局 + sudachi 词典下载式加载 + jieba 可用性探测。

三源策略（源清单 defaults/dict_sources.json，sha256 官方核实）：
  1) PyPI 官方 wheel（主源）；
  2) 清华 PyPI 镜像（fallback——仅网络失败才降级，校验失败不轮换直接报错）；
  3) 本地文件导入（离线备选，``--dict-from-file``，wheel 同样过哈希校验）。

硬约束：
- SHA256 与源清单不符 = 拒绝落位（DictChecksumError），与网络失败
  （DictDownloadError）分开报错；
- 下载仅在显式动作（CLI ``--dict-download`` / 未来 GUI 按钮）触发，
  import/启动零网络；
- 下载 URL 仅允许 https + 固定域名白名单；清单路径字段必须为单一文件
  名分量；读侧拒绝含 ``..`` 分量的路径；一切落位路径必须包含于数据根
  ``dict/`` 之内（防清单被篡改后指内网/写任意路径）；
- 词典数据去捆绑（D2026-1001 D3）：sudachidict_core 不随包/不随主依赖
  分发，grammar_hint 在 ``dict/sudachi/`` 存在已下载词典时按路径加载
  （``Dictionary(dict=...)``，sudachipy>=0.6 支持绝对路径）；未下载时
  语法提示自动降级（不可用即跳过），经 CLI ``--dict-download`` / GUI
  引擎页按钮下载式补齐。
"""

import hashlib
import io
import os
import zipfile
from pathlib import Path

from subtransjav import paths

_DICT_SOURCES_JSON = Path(__file__).resolve().parent / "defaults" / "dict_sources.json"

# 下载域名白名单：官方 PyPI 与既有国内镜像（新增镜像须随本白名单一并评审）
_URL_HOST_ALLOW = {
    "files.pythonhosted.org",
    "pypi.org",
    "pypi.tuna.tsinghua.edu.cn",
    "mirrors.aliyun.com",
    "mirrors.cloud.tencent.com",
}


class DictDownloadError(RuntimeError):
    """词典下载失败（网络/源不可达/URL 不合规）。"""


class DictChecksumError(RuntimeError):
    """词典 SHA256 校验失败或清单字段非法（拒绝落位）。"""


# 下载进度状态（第四批 owner 验收反馈：下载无进度条/成败不醒目）：
# kind → 快照 {"kind","phase","downloaded","total","error"}，phase ∈
# download/verify/extract/done/failed。写侧整体赋值换引用（读侧拿到
# 一致性视图），无需复杂锁；GUI 经 api 层 1s 轮询消费。
_DOWNLOAD_PROGRESS: dict = {}


def download_progress(kind: str) -> dict:
    """某词典的下载进度快照副本（无记录返回 {}；只读零副作用）。"""
    snap = _DOWNLOAD_PROGRESS.get(kind)
    return dict(snap) if snap else {}


def _set_download_progress(kind: str, phase: str, downloaded: int = 0,
                           total: int | None = None,
                           error: str | None = None) -> None:
    """整体赋值换引用写进度快照。"""
    _DOWNLOAD_PROGRESS[kind] = {"kind": kind, "phase": phase,
                                "downloaded": downloaded, "total": total,
                                "error": error}


def _carry_download_progress(kind: str, phase: str) -> None:
    """阶段推进（verify/extract）：保留已下载计数，仅换 phase。"""
    prev = _DOWNLOAD_PROGRESS.get(kind) or {}
    _set_download_progress(kind, phase,
                           prev.get("downloaded") or 0, prev.get("total"))


def dict_dir() -> str:
    """数据根词典目录：``<数据根>/dict/``。"""
    return paths.data_subdir("dict")


def load_source_manifest() -> dict:
    """读包内源清单（schemaVersion 校验宽松：缺字段由调用方按缺省处理）。"""
    import json
    with open(_DICT_SOURCES_JSON, encoding="utf-8") as f:
        return json.load(f)


def _safe_component(name: str) -> str:
    """清单路径字段必须为单一文件名/目录名分量（防穿越）。"""
    if not name or name in (".", "..") or "/" in name or "\\" in name \
            or Path(name).name != name:
        raise DictChecksumError(f"清单字段含非法路径分量: {name!r}")
    return name


def _ensure_inside_dict_root(path: Path) -> Path:
    """落位路径必须包含于数据根 dict/ 之内（normcase 大小写不敏感）。"""
    root = os.path.normcase(str(Path(dict_dir()).resolve()))
    p = os.path.normcase(str(path.resolve()))
    if p != root and not p.startswith(root + os.sep):
        raise DictChecksumError(f"落位路径越出数据根词典目录: {path}")
    return path


def _validated_path(path: str) -> Path:
    """读侧校验：拒绝带 ``..`` 分量的路径并 resolve 规范化（穿越面收口；
    本地工具语义=用户明示路径可读，此处仅禁越界分量）。"""
    p = Path(path)
    if ".." in p.parts:
        raise DictChecksumError(f"路径含越界分量: {path}")
    return p.resolve()


def kind_dir(kind: str) -> str:
    """某词典的落位目录：``<数据根>/dict/<install_dir>/``。"""
    entry = load_source_manifest()["dicts"].get(kind)
    if entry is None:
        raise ValueError(f"未知词典类型: {kind}")
    install = _safe_component(entry.get("install_dir") or kind)
    return str(_ensure_inside_dict_root(Path(dict_dir()) / install))


def _sha256_of(path: str) -> str:
    p = _validated_path(path)
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def _validate_url(url: str) -> str:
    """仅允许 https + 域名白名单（防清单被篡改后指内网/云元数据）。"""
    import urllib.parse
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise DictDownloadError(f"仅允许 https 下载源: {url}")
    if parts.hostname.lower() not in _URL_HOST_ALLOW:
        raise DictDownloadError(f"下载源域名不在白名单: {parts.hostname}")
    return url


def _http_get(url: str, dest: str, progress=None) -> None:
    """下载到 dest（先写 .part 再原子改名；dest 由调用方约束在数据根
    词典目录内且父目录已建）。

    progress 为可选回调 ``progress(downloaded_bytes, total_bytes)``
    （total 取 Content-Length 响应头，缺席为 None；分块 1MB 读取逐块
    上报，第四批词典下载进度）——缺省 None 时一次性 read，行为与历史
    版本一致。

    禁 shell、零新依赖（urllib 标准库）；URL 经 ``_validate_url`` 白名单
    校验（仅 https+固定域名，防清单被篡改后指内网）；socket 级超时 10s；
    网络层失败统一抛 DictDownloadError（跨源 fallback 由调用方决定）。
    """
    import urllib.request
    _validate_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": "subtransjav-dict"})
    tmp = dest + ".part"
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if progress is None:
                data = resp.read()          # 旧行为：一次性读
            else:
                total = None
                try:
                    cl = resp.headers.get("Content-Length")
                    total = int(cl) if cl else None
                except (TypeError, ValueError):
                    total = None
                buf = bytearray()
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    buf.extend(chunk)
                    progress(len(buf), total)
                data = bytes(buf)
    except Exception as e:  # noqa: BLE001 - 网络层统一转义
        _unlink_quiet(tmp)
        raise DictDownloadError(f"{url} -> {type(e).__name__}: {e}") from e
    Path(tmp).write_bytes(data)
    os.replace(tmp, dest)


def _unlink_quiet(path: str) -> None:
    import contextlib
    with contextlib.suppress(OSError):
        Path(path).unlink()


def _extract_dic(archive_path: str, member_suffix: str,
                 dest_path: str) -> str:
    """从 zip/whl 提取词典文件（按 member 后缀匹配）到 dest（原子改名）。"""
    data = _validated_path(archive_path).read_bytes()
    tmp = Path(dest_path + ".extracting")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = [n for n in z.namelist()
                     if n.endswith(member_suffix) or
                     (member_suffix == "" and n.endswith(".dic"))]
            if not names:
                raise DictChecksumError(
                    f"压缩包内未找到词典文件（*{member_suffix or '.dic'}）: "
                    f"{archive_path}")
            member_data = z.read(names[0])
    except DictChecksumError:
        _unlink_quiet(str(tmp))
        raise
    except Exception as e:  # noqa: BLE001
        _unlink_quiet(str(tmp))
        raise DictChecksumError(
            f"词典压缩包解析失败: {type(e).__name__}: {e}") from e
    tmp.write_bytes(member_data)
    os.replace(str(tmp), dest_path)
    return dest_path


def download_dict(kind: str, allow_unverified: bool = False,
                  local_file: str = "") -> str:
    """下载（或本地导入）词典到数据根 ``dict/<install_dir>/<target_name>``。

    local_file 非空=离线导入：wheel 按源清单哈希校验（不匹配即拒），
    已解压 .dic 直接落位（用户自行解压的产物，落位时提示无哈希可校）。
    返回落位路径；网络失败可跨源 fallback，校验失败直接抛
    DictChecksumError 不轮换（防串改文件被"换个源洗白"）。
    """
    entry = load_source_manifest()["dicts"].get(kind)
    if entry is None:
        raise ValueError(f"未知词典类型: {kind}")
    target_name = _safe_component(entry.get("target_name") or "")
    if not target_name:
        raise ValueError(f"词典 {kind} 无下载文件（内置/pip 提供）")
    install = _safe_component(entry.get("install_dir") or kind)
    out_dir = _ensure_inside_dict_root(Path(dict_dir()) / install)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = str(_ensure_inside_dict_root(out_dir / target_name))
    member = entry.get("archive_member") or ""

    # 2.1 第四批（owner 验收反馈）：全程写进度状态供 GUI 轮询——
    # 任何异常 phase=failed+error 后照旧向上抛（api 层语义不变）
    try:
        if local_file:
            src = _validated_path(local_file)
            if not src.is_file():
                raise DictDownloadError(f"本地文件不存在: {src}")
            if src.suffix.lower() in (".whl", ".zip"):
                _set_download_progress(kind, "verify", 0, None)
                shas = [d.get("sha256") for d in entry.get("downloads", [])
                        if d.get("sha256")]
                if shas and _sha256_of(str(src)) not in shas:
                    raise DictChecksumError(
                        f"本地 wheel SHA256 与源清单不符: {src}")
                _set_download_progress(kind, "extract", 0, None)
                _extract_dic(str(src), member, dest)
            else:
                print(f"⚠️ 本地 .dic 导入无源清单哈希可校，按用户自解压产物落位: "
                      f"{src}")
                import shutil
                shutil.copyfile(str(src), dest)
            size = os.path.getsize(dest)
            _set_download_progress(kind, "done", size, size)
            return dest

        last_err: Exception | None = None
        for d in entry.get("downloads", []):
            if not d.get("sha256_verified") and not allow_unverified:
                continue
            url = d.get("url") or ""
            tmp = str(_ensure_inside_dict_root(
                out_dir / (target_name + ".downloading")))
            # 跨源 fallback：每源重置计数（downloaded=0/total=None）
            _set_download_progress(kind, "download", 0, None)
            try:
                _http_get(url, tmp, progress=lambda n, t:
                          _set_download_progress(kind, "download", n, t))
            except DictDownloadError as e:
                last_err = e
                continue            # 网络失败 → 试下一源
            _carry_download_progress(kind, "verify")
            if _sha256_of(tmp) != d.get("sha256"):
                _unlink_quiet(tmp)
                # 校验失败不轮换直接报（防串改文件被"换个源洗白"）
                raise DictChecksumError(
                    f"SHA256 校验失败，已拒绝落位: {url}")
            _carry_download_progress(kind, "extract")
            _extract_dic(tmp, member, dest)
            _unlink_quiet(tmp)
            size = os.path.getsize(dest)
            _set_download_progress(kind, "done", size, size)
            return dest
        if last_err is not None:
            raise last_err
        raise DictDownloadError(
            f"词典 {kind} 无可用下载源（全部未核实且未开 --dict-allow-unverified）")
    except Exception as e:
        _set_download_progress(kind, "failed", error=str(e))
        raise


def sudachi_custom_dict_path() -> str:
    """用户下载的 Sudachi 词典路径；不存在返回空串（grammar_hint 回退内置）。"""
    try:
        entry = load_source_manifest()["dicts"]["sudachi"]
        install = _safe_component(entry.get("install_dir") or "sudachi")
        target = _safe_component(entry.get("target_name") or "system_core.dic")
    except (KeyError, DictChecksumError):
        return ""
    p = Path(dict_dir()) / install / target
    return str(p) if p.is_file() else ""


def dict_status() -> dict:
    """三词典状态（只读、零网络）：可用性/自定义路径/已落位文件。"""
    from importlib.util import find_spec

    from . import grammar_hint

    root = Path(dict_dir())
    manifest = load_source_manifest()
    dicts: dict = {}
    for kind, entry in manifest["dicts"].items():
        install = entry.get("install_dir") or kind
        kdir = root / install
        files = sorted(p.name for p in kdir.iterdir() if p.is_file()) \
            if kdir.is_dir() else []
        if kind == "sudachi":
            available = grammar_hint.is_grammar_hint_available()
            custom = sudachi_custom_dict_path()
        elif kind == "jieba":
            available = find_spec("jieba") is not None
            custom = ""
        else:   # english_rules：规则级内置
            available = True
            custom = ""
        dicts[kind] = {
            "available": bool(available),
            "description": entry.get("description") or "",
            "custom_path": custom,
            "files": files,
        }
    return {"dict_dir": dict_dir(), "dicts": dicts}
