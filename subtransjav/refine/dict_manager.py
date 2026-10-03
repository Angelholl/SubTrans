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
import logging
import os
import urllib.request
import zipfile
from pathlib import Path

from subtransjav import paths

# 回退提示 logger（D2026-1003-06 条件①：auto 轮换由静默升级为可见）
_log = logging.getLogger("subtransjav.dict_manager")

_DICT_SOURCES_JSON = Path(__file__).resolve().parent / "defaults" / "dict_sources.json"

# 下载域名白名单：官方 PyPI 与既有国内镜像（新增镜像须随本白名单一并评审）
_URL_HOST_ALLOW = {
    "files.pythonhosted.org",
    "pypi.org",
    "pypi.tuna.tsinghua.edu.cn",
    "mirrors.aliyun.com",
    "mirrors.cloud.tencent.com",
    # sudachi_full 完整版 CDN 直链（2.5.0 修复A）：固定上游官方域名、仅 https、
    # 落位经 DictChecksumError 校验拒串改
    "d2ej7fkh96fzlu.cloudfront.net",
}


class DictDownloadError(RuntimeError):
    """词典下载失败（网络/源不可达/URL 不合规）。

    失败诊断字段（D2026-1004-01 C3）：``_http_get`` 失败时挂 ``diag``
    （结构见 ``_DIAG_FIELDS``），随 failed 快照透出供 GUI/日志定位。
    """

    diag: dict | None = None


class DictChecksumError(RuntimeError):
    """词典 SHA256 校验失败或清单字段非法（拒绝落位）。"""


# 下载进度状态（第四批 owner 验收反馈：下载无进度条/成败不醒目）：
# kind → 快照 {"kind","phase","downloaded","total","error"}，phase ∈
# download/verify/extract/done/failed。写侧整体赋值换引用（读侧拿到
# 一致性视图），无需复杂锁；GUI 经 api 层 1s 轮询消费。
_DOWNLOAD_PROGRESS: dict = {}


def download_progress(kind: str) -> dict:
    """某词典的下载进度快照副本（无记录返回 {}；只读零副作用）。

    D2026-1004-01 C3：diag 诊断字段亦做一层浅拷贝返回（读侧持有独立
    副本，不与写侧快照共享内层 dict）。"""
    snap = _DOWNLOAD_PROGRESS.get(kind)
    if not snap:
        return {}
    out = dict(snap)
    if "diag" in out:
        out["diag"] = dict(out["diag"])
    return out


def _set_download_progress(kind: str, phase: str, downloaded: int = 0,
                           total: int | None = None,
                           error: str | None = None,
                           note: str | None = None,
                           diag: dict | None = None) -> None:
    """整体赋值换引用写进度快照（2.6.3 批B 增可选 note：源回退可见提示；
    D2026-1004-01 C3 增可选 diag：失败诊断字段）。

    note 粘滞语义：显式传入时覆盖；未传（None）且 phase=="download" 时
    继承上一快照的 note——回退提示在后续源下载相位持续可见（1s 轮询必能
    采样），verify/extract/done/failed 相位自然清除。既有进度测试语义
    （phase 链/reset_per_source/failed 精确断言）不受扰：note 只增不扰。

    diag 仅在显式传入非 None 时写入快照（不无条件加键——既有测试对
    done 快照做全等断言，加空键即破坏）；随 download_progress() 浅拷贝
    透出。"""
    prev = _DOWNLOAD_PROGRESS.get(kind) or {}
    snap = {"kind": kind, "phase": phase, "downloaded": downloaded,
            "total": total, "error": error}
    if note is None:
        note = prev.get("note") if phase == "download" else None
    if note:
        snap["note"] = note
    if diag is not None:
        snap["diag"] = dict(diag)
    _DOWNLOAD_PROGRESS[kind] = snap


def _set_download_note(kind: str, note: str) -> None:
    """在当前快照上追加 note（不新增相位写入，整体赋值换引用）。

    专供跨源 fallback 可见提示（D2026-1003-06 条件①）：后续 download
    相位经 _set_download_progress 粘滞继承，verify/done 相位自然清除。
    """
    snap = _DOWNLOAD_PROGRESS.get(kind)
    if snap is not None:
        _DOWNLOAD_PROGRESS[kind] = {**snap, "note": note}


def _carry_download_progress(kind: str, phase: str) -> None:
    """阶段推进（verify/extract）：保留已下载计数，仅换 phase。"""
    prev = _DOWNLOAD_PROGRESS.get(kind) or {}
    _set_download_progress(kind, phase,
                           prev.get("downloaded") or 0, prev.get("total"))


def dict_dir() -> str:
    """数据根词典目录：``<数据根>/dict/``（2.6.1 批1b 起委托
    :func:`effective_dict_dir`，未设自定义目录时行为与历史逐字节一致）。"""
    return effective_dict_dir()


# ---------------------------------------------------------------------------
# 自定义词典目录（批1b D2026-1002-12 件1 + 规划员追补裁定）
# ---------------------------------------------------------------------------
# 进程内覆盖值（优先级①）：api 层启动时从 user_dirs.dict_dir 装载注入
# （依赖方向裁定：dict_manager 在 refine/ 包，user_dirs 在 webview_gui/，
# refine 不得反向 import webview_gui——选"注册器注入"而非"回调注册"：
# set_custom_dir 只传一个 str，dict_manager 保持可独立测试，现有测试
# 不依赖 webview_gui 即可覆盖覆盖/清除语义）。
_CUSTOM_DICT_DIR: str | None = None

# user_dirs.json 直读缓存（优先级②）：key=(文件路径, mtime)，命中即复用
# 上次解析值。mtime 缓存理由：grammar_hint 可能在 tokenize 路径高频触达
# dict_dir()，stat 未变即 O(stat)/次复用，避免每次 json 解析+磁盘读；
# key 含完整路径，测试换数据根（env）天然失效不串值。
_USER_DIRS_CACHE: dict = {"key": None, "value": None}


def set_custom_dir(path: str | None) -> None:
    """注入/清除进程内自定义词典目录（None=清除恢复数据根默认）。"""
    global _CUSTOM_DICT_DIR
    _CUSTOM_DICT_DIR = str(path) if path else None


def get_custom_dir() -> str | None:
    """当前注入的自定义词典目录（未设置返回 None；只读零副作用）。"""
    return _CUSTOM_DICT_DIR


# ---------------------------------------------------------------------------
# 系统目录黑名单（批1b 追补②，Mimosa finding:b50deb159fa0c0bdb4967000）：
# 用户自选任意盘目录是拍板产品语义（不收回），但"手改 user_dirs.json 指向
# 系统目录"须拦。口径锚点对齐 webview_gui/security.py
# ``_validate_user_directory`` 的 system_roots 段；因 refine 不得 import
# webview_gui（依赖方向），四根常量就地定义。
# ---------------------------------------------------------------------------
def _system_dir_roots() -> list[str]:
    """系统目录黑名单四根（env 可覆盖，与 security.py 同缺省）。"""
    return [
        os.environ.get("SystemRoot", r"C:\Windows"),  # noqa: SIM112  Windows 规范环境变量名，改大小写即行为变更
        os.environ.get("ProgramFiles", r"C:\Program Files"),  # noqa: SIM112
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),  # noqa: SIM112
        os.environ.get("ProgramData", r"C:\ProgramData"),  # noqa: SIM112
    ]


def _strip_extended_prefix(path: str) -> str:
    """还原 Windows 扩展路径前缀（``\\\\?\\`` / ``\\\\?\\UNC\\``）。

    口径对齐 security.py 同名助手：``Path.resolve()`` 对 ``\\\\?\\C:\\...``
    的折叠在部分 Python 版本会畸变为盘符相对路径致前缀判定漏判逃逸，
    统一先还原再 resolve。
    """
    if path.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path[8:]
    if path.startswith("\\\\?\\"):
        return path[4:]
    return path


def _ensure_safe_dict_dir(path: str) -> str | None:
    """词典目录净化守卫（防御纵深；命中黑名单返回 None，调用方回落）。

    黑名单判定一律在 ``Path.resolve()``（strict=False）之后进行——
    junction/符号链接、8.3 短路径、大小写变体、``\\\\?\\`` 扩展前缀都先
    折叠/还原为真实落点，再做大小写不敏感的字符串前缀比较（normcase +
    casefold，任何平台一致），杜绝经由链接或大小写差异绕过。
    """
    p = Path(_strip_extended_prefix(str(path or ""))).resolve()
    p_key = os.path.normcase(str(p)).casefold()
    for root in _system_dir_roots():
        if not root:
            continue
        try:
            root_key = os.path.normcase(
                str(Path(root).resolve())).casefold()
        except OSError:
            continue
        prefix = root_key if root_key.endswith(os.sep) else root_key + os.sep
        if p_key == root_key or p_key.startswith(prefix):
            return None
    return str(p)


def _user_dirs_json_dict_dir() -> str | None:
    """直读 ``<数据根>/config/user_dirs.json`` 的 ``dict_dir`` 键（批1b
    规划员追补裁定：跨进程单源，GUI/CLI/refine/--dict-download 统一生效）。

    纯 json + paths 实现（不 import webview_gui）；文件缺失/损坏/键空/
    非 dict 形态一律跳过返回 None（回落数据根默认）。mtime 缓存见
    ``_USER_DIRS_CACHE`` 注释。
    """
    p = Path(paths.data_root()) / "config" / "user_dirs.json"
    try:
        mtime = p.stat().st_mtime
    except OSError:
        _USER_DIRS_CACHE["key"] = None
        _USER_DIRS_CACHE["value"] = None
        return None
    key = (str(p), mtime)
    if _USER_DIRS_CACHE["key"] == key:
        return _USER_DIRS_CACHE["value"]
    value: str | None = None
    try:
        import json
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            v = raw.get("dict_dir")
            if isinstance(v, str) and v.strip():
                value = v.strip()
    except (OSError, ValueError):
        value = None
    _USER_DIRS_CACHE["key"] = key
    _USER_DIRS_CACHE["value"] = value
    return value


def effective_dict_dir() -> str:
    """生效词典目录单源，三级优先级（批1b 追补裁定）：

    ① ``_CUSTOM_DICT_DIR``（进程内覆盖，GUI 注入/测试用，过净化守卫）；
    ② user_dirs.json ``dict_dir`` 键直读（跨进程单源，mtime 缓存，
       过净化守卫——手改 JSON 指向系统目录与损坏 JSON 同待遇，静默
       回退，返回值语义不变）；
    ③ 数据根 ``dict/`` 默认（程序内派生，不过守卫）。

    download/kind_dir/status 等一切落位与读取均经本函数（经 dict_dir
    委托自动跟随），保证自定义目录下"下载-加载-状态"三链路一致。
    """
    if _CUSTOM_DICT_DIR:
        guarded = _ensure_safe_dict_dir(_CUSTOM_DICT_DIR)
        if guarded:
            return guarded
        # ① 命中黑名单视为无效注入（防御纵深与②一致），继续向下解析
    persisted = _user_dirs_json_dict_dir()
    if persisted:
        guarded = _ensure_safe_dict_dir(persisted)
        if guarded:
            return guarded
        # ② 命中黑名单：静默回退（不 log 不抛，与损坏 JSON 同待遇）
    return paths.data_subdir("dict")


def count_dict_files(root: str) -> int:
    """统计目录下两层级（``<root>/<install>/<file>``）的常规文件数
    （迁移提示用；目录不存在返回 0，只读零副作用）。"""
    base = Path(root)
    if not base.is_dir():
        return 0
    n = 0
    for kdir in base.iterdir():
        if kdir.is_dir():
            n += sum(1 for p in kdir.iterdir() if p.is_file())
    return n


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


def _check_free_space(dest_dir: str, need_bytes: int) -> None:
    """磁盘空间预检：可用 < need_bytes 即拒（DictDownloadError）。

    量纲口径（2.5.0 修复A）：下载前=zip 体积+2×解压产物（.part/最终 zip
    与解压临时/落位并存的最坏情况）；解压前从 zipinfo 实时取 2×member
    体积。清单缺字段时仅解压前一道防线兜底。
    """
    import shutil
    try:
        free = shutil.disk_usage(dest_dir).free
    except OSError:
        return                      # 卷信息不可得时不阻塞下载
    if free < need_bytes:
        raise DictDownloadError(
            f"磁盘可用空间不足：本次约需 {need_bytes // (1024 * 1024)}MB，"
            f"当前仅剩 {free // (1024 * 1024)}MB（请清理后重试，或改用 "
            f"--dict-from-file 指向其他盘的离线包）")


# 失败诊断字段契约（D2026-1004-01 C3，段2 #6 数据来源）：网络层失败时由
# _http_get 采集并挂 DictDownloadError.diag（download_dict 层随 failed
# 快照透出，供 GUI/日志定位：代理坏损 vs 响应截断 vs gzip 注入等）
_DIAG_FIELDS = ("expected_bytes", "actual_bytes", "content_encoding",
                "part_prefix_hex", "url", "proxy", "attempts")


class _DictGuardedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """逐跳校验的重定向处理器（dict 链本地版，D2026-1004-01 C6/候选B1）。

    不复用 asr_downloader 版（勿 import）：错误类型必须为 DictDownloadError
    （不是 AsrDownloadError），白名单必须用本模块 _URL_HOST_ALLOW——经
    ``_validate_url`` 同时落实 https 强制 + 固定域名白名单。
    ``max_redirections=5``；重定向目标非 https 或域名不在白名单即拒
    （fp.close() 后抛，防半开连接泄漏）。
    """

    max_redirections = 5

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            _validate_url(str(newurl))
        except DictDownloadError:
            fp.close()
            raise
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _http_get(url: str, dest: str, progress=None) -> None:
    """下载到 dest（流式分块落盘，.part 先写再原子改名；dest 由调用方
    约束在数据根词典目录内且父目录已建）。

    2.5.0 修复A：弃全量进内存（full 的 137MB zip + 内存缓冲双份不可接受），
    1MB 分块直接写盘。

    progress 为可选回调 ``progress(downloaded_bytes, total_bytes)``
    （total 取 Content-Length 响应头，缺席为 None；逐块上报）。

    D2026-1004-01 两跳状态机（候选B C8 + C6 重定向守卫，弃裸 urlopen
    改显式 opener）：
    - attempt#1：不显式装 ProxyHandler，经默认处理器自动挂 getproxies()
      系统代理（行为与裸 urlopen 一致——「默认沿用系统代理」语义仅指
      首发，记档口径）；
    - attempt#1 网络层失败（DictDownloadError）→ 同 URL attempt#2 经
      ``ProxyHandler({})`` 强制直连；两跳均失败抛末次异常（错误信息
      保留末次异常原文）；
    - 请求头带 ``Accept-Encoding: identity``（C1：防代理/gzip 注入，
      pin 校验按落盘字节）；
    - 重定向逐跳 https+白名单校验（_DictGuardedRedirectHandler）；
    - Content-Length 存在且实收不符=网络层失败（消息含「预期 X 字节/
      实收 Y 字节」），参与 attempt#2 直连重试，不与校验失败混淆。

    禁 shell、零新依赖（urllib 标准库）；URL 经 ``_validate_url`` 白名单
    校验（仅 https+固定域名，防清单被篡改后指内网）；socket 级超时 10s；
    网络层失败统一抛 DictDownloadError（跨源 fallback 由调用方决定），
    异常实例挂 ``.diag`` 诊断字段（C3，见 _DIAG_FIELDS）。
    """
    _validate_url(url)
    req = urllib.request.Request(url, headers={
        "User-Agent": "subtransjav-dict",
        "Accept-Encoding": "identity"})     # C1：pin 校验按落盘字节
    tmp = dest + ".part"

    def _collect_diag(expected: int | None, actual: int, enc: str,
                      proxy: str, attempts: int) -> dict:
        """失败诊断字段采集（C3 七键；.part 删除前调用，读不到为 ""）。"""
        part_hex = ""
        try:
            with open(tmp, "rb") as f:
                part_hex = f.read(64).hex()
        except OSError:
            pass
        return {"expected_bytes": expected, "actual_bytes": actual,
                "content_encoding": enc, "part_prefix_hex": part_hex,
                "url": url, "proxy": proxy, "attempts": attempts}

    last_err: DictDownloadError | None = None
    for attempt in (1, 2):
        expected: int | None = None
        done = 0
        enc = ""
        try:
            if attempt == 1:
                # 经默认处理器自动挂 getproxies() 系统代理（同裸 urlopen）
                opener = urllib.request.build_opener(
                    _DictGuardedRedirectHandler())
            else:
                # 空白 ProxyHandler = 强制直连（系统/环境代理坏损的兜底跳）
                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler({}),
                    _DictGuardedRedirectHandler())
            with opener.open(req, timeout=10) as resp:
                total = None
                try:
                    cl = resp.headers.get("Content-Length")
                    total = int(cl) if cl else None
                except (TypeError, ValueError):
                    total = None
                expected = total
                enc = resp.headers.get("Content-Encoding") or ""
                with open(tmp, "wb") as out:
                    while True:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            break
                        out.write(chunk)
                        done += len(chunk)
                        if progress is not None:
                            progress(done, total)
                if total is not None and done != total:
                    # 响应截断/注入=网络层失败（D2026-1004-01）：
                    # 参与 attempt#2 直连重试，绝不当作下载成功落位
                    raise DictDownloadError(
                        f"{url} 下载不完整：预期 {total} 字节/"
                        f"实收 {done} 字节")
            os.replace(tmp, dest)
            return
        except DictChecksumError:
            # 防洗白裁定边界（D2026-1003-06）：校验错误绝不吞成网络错误、
            # 绝不触发直连重试（当前不可达，防未来重构回归）
            raise
        except DictDownloadError as e:
            last_err = e
        except Exception as e:  # noqa: BLE001 - 网络层统一转义
            last_err = DictDownloadError(f"{url} -> {type(e).__name__}: {e}")
            last_err.__cause__ = e   # 保底链：等价原 raise ... from e
        # 失败：.part 删除前采集诊断字段挂异常实例（C3）
        last_err.diag = _collect_diag(expected, done, enc,
                                      "system" if attempt == 1 else "direct",
                                      attempt)
        _unlink_quiet(tmp)
    if last_err is None:    # pragma: no cover - 两跳必有一败，理论不可达
        last_err = DictDownloadError(f"{url} 下载失败")
    raise last_err


def _unlink_quiet(path: str) -> None:
    import contextlib
    with contextlib.suppress(OSError):
        Path(path).unlink()


def _extract_dic(archive_path: str, member_suffix: str,
                 dest_path: str) -> str:
    """从 zip/whl 提取词典文件到 dest（流式分块写+原子改名）。

    2.5.0 修复A 加固：①弃 read_bytes 全量双缓冲（full 的 .dic 解压后
    330MB 档位 OOM 风险），z.open+4MB 分块写；②member 匹配改 basename
    兼容（部分 zip 内部条目用 ``\\`` 分隔破 endswith，归一化后按完整
    后缀或 basename 后缀双通道匹配）；③解压前磁盘预检（2×member 体积，
    .extracting 临时+最终落位并存最坏情况）。
    """
    archive = _validated_path(archive_path)
    tmp = Path(dest_path + ".extracting")
    suffix_norm = member_suffix.replace("\\", "/")
    base_suffix = os.path.basename(suffix_norm) if suffix_norm else ""

    def _match(name: str) -> bool:
        n = name.replace("\\", "/")
        if suffix_norm and n.endswith(suffix_norm):
            return True
        if base_suffix and os.path.basename(n).endswith(base_suffix):
            return True
        return member_suffix == "" and os.path.basename(n).endswith(".dic")

    try:
        with zipfile.ZipFile(archive) as z:
            names = [n for n in z.namelist() if _match(n)]
            if not names:
                raise DictChecksumError(
                    f"压缩包内未找到词典文件（*{member_suffix or '.dic'}）: "
                    f"{archive}")
            zinfo = z.getinfo(names[0])
            _check_free_space(str(Path(dest_path).parent),
                              2 * zinfo.file_size)
            with z.open(names[0]) as src, open(tmp, "wb") as out:
                while True:
                    chunk = src.read(4 * 1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
    except DictChecksumError:
        _unlink_quiet(str(tmp))
        raise
    except Exception as e:  # noqa: BLE001
        _unlink_quiet(str(tmp))
        raise DictChecksumError(
            f"词典压缩包解析失败: {type(e).__name__}: {e}") from e
    os.replace(str(tmp), dest_path)
    return dest_path


def download_dict(kind: str, allow_unverified: bool = False,
                  local_file: str = "", source: str = "auto") -> str:
    """下载（或本地导入）词典到数据根 ``dict/<install_dir>/<target_name>``。

    local_file 非空=离线导入：wheel 按源清单哈希校验（不匹配即拒），
    已解压 .dic 直接落位（用户自行解压的产物，落位时提示无哈希可校）。
    返回落位路径；网络失败可跨源 fallback，校验失败直接抛
    DictChecksumError 不轮换（防串改文件被"换个源洗白"）。

    source（2.6.3 批B，D2026-1003-06 条件②①）：源选择 ∈ {auto, official,
    mirror}，非法值按 auto。mirror 集=清单 ``source=="tuna"``；official=
    排除镜像（保留 pypi 与 cloudfront-cdn——sudachi_full 官方源就是
    cloudfront，不得只留 pypi）；official/mirror 过滤后为空显式报错。
    auto 静默轮换升级为可见：官方源网络失败且有下一源时进度快照带
    note 提示（1s 轮询透出）。
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

    # 源选择过滤（D2026-1003-06 条件②）：mirror=tuna；official=排除镜像
    # （pypi+cloudfront-cdn 均属官方，不得只留 pypi）
    if source not in ("auto", "official", "mirror"):
        source = "auto"
    all_downloads = list(entry.get("downloads", []))
    if source == "mirror":
        pool = [d for d in all_downloads if d.get("source") == "tuna"]
        if not pool:
            raise DictDownloadError(f"词典 {kind} 无镜像源（官方 CDN 单源）")
    elif source == "official":
        pool = [d for d in all_downloads if d.get("source") != "tuna"]
        if not pool:
            raise DictDownloadError(f"词典 {kind} 无官方源")
    else:
        pool = all_downloads

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
        for i, d in enumerate(pool):
            if not d.get("sha256_verified") and not allow_unverified:
                continue
            url = d.get("url") or ""
            tmp = str(_ensure_inside_dict_root(
                out_dir / (target_name + ".downloading")))
            # 下载前磁盘预检（量纲=zip+2×解压产物；清单带 expected_* 字段时
            # 生效，缺字段由 _extract_dic 内 zipinfo 实时预检兜底）
            exp_d = int(entry.get("expected_download_bytes") or 0)
            exp_e = int(entry.get("expected_extracted_bytes") or 0)
            if exp_d and exp_e:
                _check_free_space(str(out_dir), exp_d + 2 * exp_e)
            # 跨源 fallback：每源重置计数（downloaded=0/total=None）
            _set_download_progress(kind, "download", 0, None)
            try:
                _http_get(url, tmp, progress=lambda n, t:
                          _set_download_progress(kind, "download", n, t))
            except DictDownloadError as e:
                last_err = e
                # D2026-1003-06 条件①：静默轮换升级为可见——快照带 note
                # （后续源 download 相位粘滞继承）+ logging 同文案
                has_next = any(x.get("sha256_verified") or allow_unverified
                               for x in pool[i + 1:])
                if has_next:
                    _set_download_note(kind, "官方源不可达，已回退镜像源")
                    _log.info("词典 %s 官方源不可达，已回退镜像源", kind)
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
        # D2026-1004-01 C3：_http_get 挂的 diag（若有）随 failed 快照
        # 透出（段2 #6 数据来源）；校验失败无 diag → 不加 diag 键
        _set_download_progress(kind, "failed", error=str(e),
                               diag=getattr(e, "diag", None))
        raise


# ---------------------------------------------------------------------------
# 一键迁移（批1b D2026-1002-12 件2）：旧词典目录 → 现生效目录
# ---------------------------------------------------------------------------
# 进度通道裁定：复用下载进度表 _DOWNLOAD_PROGRESS（伪 kind=``__migrate__``，
# api 层 refine_dict_download_progress 现成轮询桥零改动），phase ∈
# copy/verify/done/failed；downloaded/total=累计字节，另带 file_index/
# file_count/file_name 供前端"文件 x/y"文案。最小实现：字节粒度随拷贝
# 分块推进（与下载同粒度），不新增第二套轮询字段。
MIGRATE_PROGRESS_KIND = "__migrate__"


def _set_migrate_progress(phase: str, downloaded: int = 0,
                          total: int | None = None, error: str | None = None,
                          file_index: int = 0, file_count: int = 0,
                          file_name: str = "") -> None:
    """整体赋值换引用写迁移进度快照（与下载进度同口径）。"""
    _DOWNLOAD_PROGRESS[MIGRATE_PROGRESS_KIND] = {
        "kind": MIGRATE_PROGRESS_KIND, "phase": phase,
        "downloaded": downloaded, "total": total, "error": error,
        "file_index": file_index, "file_count": file_count,
        "file_name": file_name}


def _sha256_file(path: str) -> str:
    """流式分块 SHA256（迁移校验用：词典产物 300MB 档，不全量进内存）。"""
    h = hashlib.sha256()
    with open(_validated_path(path), "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def migrate_dicts(source_dir: str) -> dict:
    """把旧词典目录下各 kind 文件迁移到现生效目录（批1b 件2）。

    规则（与拍板点5 一致）：
    - 逐文件"临时名复制（1MB 分块）→ 大小+SHA256 校验 → 原子改名
      （os.replace）"；同名同 size 跳过（可续传）；校验失败删临时重试
      一次，再失败抛 RuntimeError 中止（不标记已迁移）；
    - 源文件一律不删；目标目录不存在自动创建；
    - 源目录与现生效目录相同（normcase）拒绝；源目录不存在拒绝。

    返回 ``{"migrated": [...], "skipped": [...], "total_bytes": n}``；
    任何异常经进度表 phase=failed 后照旧向上抛。
    """
    try:
        return _migrate_dicts_impl(source_dir)
    except Exception as e:  # noqa: BLE001 - 与下载链同口径：失败写进度再上抛
        _set_migrate_progress("failed", error=str(e))
        raise


def _migrate_dicts_impl(source_dir: str) -> dict:
    src_root = _validated_path(str(source_dir or ""))
    if not src_root.is_dir():
        raise ValueError(f"旧词典目录不存在: {src_root}")
    dst_root = Path(effective_dict_dir()).resolve()
    if os.path.normcase(str(src_root)) == os.path.normcase(str(dst_root)):
        raise ValueError("源目录与当前生效词典目录相同，无需迁移")

    # 迁移计划：清单各 kind 的安装子目录下全部常规文件（含 full/core
    # 双变体与用户自解压产物；非清单 kind 的杂散子目录一并覆盖更稳妥——
    # 仅在"目录名安全分量"约束下按 basename 拷贝，不越出目标根）；
    # 临时残件（.part/.downloading/.extracting/.migrating）不迁移
    _SKIP_SUFFIXES = (".part", ".downloading", ".extracting", ".migrating")
    plan: list[tuple[Path, Path]] = []
    for kdir in sorted(src_root.iterdir()):
        if not kdir.is_dir():
            continue
        install = _safe_component(kdir.name)
        for f in sorted(kdir.iterdir()):
            if f.is_file() and not f.name.endswith(_SKIP_SUFFIXES):
                plan.append((f, dst_root / install / f.name))
    total_bytes = sum(f.stat().st_size for f, _ in plan)
    _set_migrate_progress("copy", 0, total_bytes, file_count=len(plan))

    migrated: list[str] = []
    skipped: list[str] = []
    done_bytes = 0
    for idx, (src_file, dest) in enumerate(plan, start=1):
        dest.parent.mkdir(parents=True, exist_ok=True)
        src_size = src_file.stat().st_size
        if dest.is_file() and dest.stat().st_size == src_size:
            skipped.append(str(dest))       # 同名同 size：断点续传语义
            done_bytes += src_size
            _set_migrate_progress("copy", done_bytes, total_bytes,
                                  file_index=idx, file_count=len(plan),
                                  file_name=src_file.name)
            continue
        _copy_verified(src_file, dest, done_bytes, total_bytes, idx, len(plan))
        done_bytes += src_size
        migrated.append(str(dest))
        _set_migrate_progress("copy", done_bytes, total_bytes,
                              file_index=idx, file_count=len(plan),
                              file_name=src_file.name)
    _set_migrate_progress("done", done_bytes, total_bytes,
                          file_count=len(plan))
    return {"migrated": migrated, "skipped": skipped,
            "total_bytes": total_bytes}


def _copy_verified(src_file: Path, dest: Path, done_bytes: int,
                   total_bytes: int, file_index: int, file_count: int) -> None:
    """临时名复制 + 大小/SHA256 双校验 + 原子改名；失败删临时重试一次。

    字节进度按分块推进（downloaded=done_bytes+已拷字节）；校验失败
    （源与临时件哈希不符/大小不符）删临时件重试，二次失败抛
    RuntimeError（调用方中止整个迁移，目标不留半截产物）。
    """
    tmp = Path(str(dest) + ".migrating")
    src_sha = _sha256_file(str(src_file))
    last_err: Exception | None = None
    for _attempt in range(2):
        try:
            with open(src_file, "rb") as fin, open(tmp, "wb") as fout:
                copied = 0
                while True:
                    chunk = fin.read(1024 * 1024)
                    if not chunk:
                        break
                    fout.write(chunk)
                    copied += len(chunk)
                    _set_migrate_progress("copy", done_bytes + copied,
                                          total_bytes, file_index=file_index,
                                          file_count=file_count,
                                          file_name=src_file.name)
            if tmp.stat().st_size != src_file.stat().st_size \
                    or _sha256_file(str(tmp)) != src_sha:
                raise ValueError(f"复制后校验不符: {src_file.name}")
            os.replace(str(tmp), str(dest))     # 原子改名落位
            return
        except (OSError, ValueError) as e:
            last_err = e
            _unlink_quiet(str(tmp))
    raise RuntimeError(f"词典文件迁移失败（已重试一次）: {src_file} -> {dest}: "
                       f"{last_err}")


def _kind_dict_file(kind: str) -> Path:
    """某 kind 落位词典文件路径（清单缺 kind/字段非法抛异常，调用方捕获）。"""
    entry = load_source_manifest()["dicts"][kind]
    install = _safe_component(entry.get("install_dir") or kind)
    target = _safe_component(entry.get("target_name") or "")
    return Path(dict_dir()) / install / target


def sudachi_custom_dict_path() -> str:
    """用户下载的 Sudachi 词典路径（full 优先→core→空串）。

    2.5.0 修复A：kind 双变体（sudachi=core / sudachi_full，同目录二选一
    也可并存）——同目录两 dic 时取 full（词覆盖更全）；均不存在返回空串
    （grammar_hint 走降级链）。"""
    candidates = []
    import contextlib
    with contextlib.suppress(KeyError, DictChecksumError):
        candidates.append(_kind_dict_file("sudachi_full"))
    with contextlib.suppress(KeyError, DictChecksumError):
        candidates.append(_kind_dict_file("sudachi"))
    for p in candidates:
        if p.is_file():
            return str(p)
    return ""


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
        elif kind == "sudachi_full":
            # kind 兼容三联（2.5.0 修复A C4）：available=落位文件存在
            # （防误用恒 True 报"可用"实则未下载）
            try:
                available = _kind_dict_file(kind).is_file()
            except DictChecksumError:
                available = False
            custom = ""
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
    # 批1b 件1：dict_dir=现生效目录（自定义覆盖后即生效值），
    # custom_dir=设置值（未设 null），effective_dir 与 dict_dir 等价显式键
    # 2.6.3 批B（D2026-1003-06 条件②）：sources 摘要——前端「仅镜像」键
    # disabled 门控（从清单推导；仅 target_name 非空的可下载 kind）
    sources_summary: dict = {}
    for kind, entry in manifest["dicts"].items():
        if not (entry.get("target_name") or ""):
            continue
        dl = entry.get("downloads") or []
        sources_summary[kind] = {
            "has_official": any(d.get("source") != "tuna" for d in dl),
            "has_mirror": any(d.get("source") == "tuna" for d in dl),
        }
    return {"dict_dir": dict_dir(), "custom_dir": _CUSTOM_DICT_DIR,
            "effective_dir": dict_dir(), "dicts": dicts,
            "sources": sources_summary}
