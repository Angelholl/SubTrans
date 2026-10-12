"""ASR 模型下载器（2.6.3 批B，D2026-1003-01 ② + D2026-1003-06 评议五条件）。
================================================================================
推荐清单（asr_env.ASR_RECOMMENDED_MODELS）驱动的大文件（3GB 档）下载引擎，
落位数据根 ``models/asr/<model>.pt``（清单 model 字段派生文件名，路径注入面
封死）。零 shell、零新依赖（urllib 标准库），下载仅在显式动作（GUI 按钮）
触发，import/启动零网络。

URL 信任三层（评议员条件④）：
  1) ``_validate_url``：强制 https + 非空（镜像 PENDING 空 URL 必硬拒）；
  2) 清单 URL 级精确匹配：传入 URL 规范化后必须与清单 sources[].url 规范化
     结果之一全等（比域名白名单更严；归一化仅用于等值判定，防御校验用原始值）；
  3) host 小名单 + 解析 IP 全量判定（护栏⑥）：hostname ∈
     {openaipublic.azureedge.net, hf-mirror.com}，且 socket.getaddrinfo 解析
     的全部 IP 逐个 ipaddress 判定，回环/私网/链路本地/保留/多播任一真即拒
     （DNS 解析失败同样拒绝——fail-closed）。
两硬化：重定向逐跳校验（自建 opener，HTTPRedirectHandler 子类对每一跳新 URL
重复合格性检查；重定向目标不可能再等于清单 URL，改用 host 小名单+IP 校验，
默认最多 5 跳）；镜像上架门=实下载字节级 sha256 与官方 pin 一致（格式转换
版一律不通过），PENDING 条目永不上候选（verified==True 才进源集）。

无取消语义（评议员条件①口径成文）：下载不支持暂停/取消——关闭应用即中断，
重新下载清 .part 从零开始。磁盘预检 fail-closed（与 dict_manager 的
fail-open 有意不同）：3GB 件量级下卷信息不可得即拒绝，防半截写满系统盘。

零出域声明：本模块仅出站下载模型文件，无任何用户数据上传面。
"""

import ipaddress
import logging
import os
import shutil
import socket
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from subtransjav import paths
from subtransjav.refine import asr_env
from subtransjav.refine.dict_manager import _sha256_file, _unlink_quiet

# 回退提示 logger（D2026-1003-06 条件①：回退必须可见——进度 note + 日志双通道）
logger = logging.getLogger("subtransjav.asr_downloader")

# host 小名单（层3；与清单 URL 精确匹配双层并行，重定向逐跳复用本名单）。
# cas-bridge.xethub.hf.co：hf-mirror.com 镜像 URL 会 308 跳该域（签名 URL），
# 与 dict 层 D2026-1005-05 白名单同款两域口径（hf-mirror.com + cas-bridge）
_ASR_HOST_ALLOW = {"openaipublic.azureedge.net", "hf-mirror.com",
                   "cas-bridge.xethub.hf.co"}
_MAX_REDIRECTS = 5               # 评议员条件④：默认最多 5 跳
_CONNECT_TIMEOUT_S = 10
_CHUNK = 1024 * 1024             # 1MB 分块（仿 dict_manager._http_get）
_FALLBACK_NOTE = "官方源不可达，已回退国内镜像"
_DISK_ERR = "磁盘空间不足或写入失败"


class AsrDownloadError(Exception):
    """ASR 模型下载失败（网络/源不可达/URL 不合规/磁盘/并发限制）。"""


class AsrChecksumError(AsrDownloadError):
    """ASR 模型 SHA256 校验失败（拒绝落位）。"""


class AsrDiskWriteError(AsrDownloadError):
    """下载写盘阶段 OSError（ENOSPC 等）——不得伪装成网络失败触发跨源轮换。"""


# ---------------------------------------------------------------------------
# 下载进度快照（结构与 dict_manager._DOWNLOAD_PROGRESS 同形：
# kind/phase/downloaded/total/error（+可选 note）；phase ∈ download/verify/
# done/failed。写侧整体赋值换引用；GUI 经 api 层 1s 轮询消费）
# ---------------------------------------------------------------------------
_ASR_DOWNLOAD_PROGRESS: dict = {}

# 单实例锁：model 名 → 在下载中（评议员条件⑥并发面收口；finally 释放）
_ACTIVE_DOWNLOADS: set = set()


def asr_download_progress(model: str) -> dict:
    """某模型的下载进度快照副本（无记录返回 {}；只读零副作用）。"""
    snap = _ASR_DOWNLOAD_PROGRESS.get(model)
    return dict(snap) if snap else {}


def _set_progress(model: str, phase: str, downloaded: int = 0,
                  total: int | None = None, error: str | None = None,
                  note: str | None = None) -> None:
    """整体赋值换引用写进度快照。

    note 粘滞语义（评议员条件①回退可见）：显式传入时覆盖；未传（None）且
    phase=="download" 时继承上一快照的 note——保证回退提示在后续源的下载
    相位持续可见（1s 轮询必能采样），verify/done/failed 相位自然清除。
    """
    prev = _ASR_DOWNLOAD_PROGRESS.get(model) or {}
    snap: dict[str, Any] = {"kind": model, "phase": phase,
                            "downloaded": downloaded, "total": total,
                            "error": error}
    if note is None:
        note = prev.get("note") if phase == "download" else None
    if note:
        snap["note"] = note
    _ASR_DOWNLOAD_PROGRESS[model] = snap


def _carry_progress(model: str, phase: str) -> None:
    """阶段推进（verify）：保留已下载计数，仅换 phase。"""
    prev = _ASR_DOWNLOAD_PROGRESS.get(model) or {}
    _set_progress(model, phase, int(prev.get("downloaded") or 0),
                  prev.get("total"))


# ---------------------------------------------------------------------------
# URL 信任三层（层1/层2 合一于 _validate_url；层3=_validate_host_ips）
# ---------------------------------------------------------------------------

def _normalize_url(url: str) -> str:
    """URL 规范化（仅用于「清单 URL 等值」判定）：scheme/hostname 小写、
    去 fragment、去默认端口；path+query 原样保留比对。空串原样返回（由
    调用方先拒）。"""
    parts = urllib.parse.urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower().rstrip(".")   # 尾点 FQDN 归一
    port = parts.port
    default = 443 if scheme == "https" else 80
    netloc = host if port in (None, default) else f"{host}:{port}"
    return urllib.parse.urlunsplit((scheme, netloc, parts.path,
                                    parts.query, ""))


def _known_manifest_urls() -> set:
    """清单内全部非空 sources[].url 的规范化集合（层2精确匹配基准）。"""
    known: set = set()
    for entry in asr_env.ASR_RECOMMENDED_MODELS:
        for s in entry.get("sources") or []:
            u = str(s.get("url") or "")
            if u:
                known.add(_normalize_url(u))
    return known


def _validate_url(url: str) -> None:
    """层1+层2（防御校验用原始值，归一化仅作等值判定）：
    空 URL/非 https/解析失败/不在清单内一律拒绝。"""
    if not url or not url.strip():
        # 镜像 PENDING 空 URL 必硬拒（不得旁路）
        raise AsrDownloadError("下载源 URL 为空（该源未上架或清单损坏）")
    raw = url.strip()
    try:
        parts = urllib.parse.urlsplit(raw)
    except ValueError as e:
        raise AsrDownloadError(f"URL 解析失败: {raw}") from e
    if parts.scheme.lower() != "https":
        raise AsrDownloadError(f"仅允许 https 下载源: {raw}")
    if not parts.hostname:
        raise AsrDownloadError(f"URL 缺少主机名: {raw}")
    if _normalize_url(raw) not in _known_manifest_urls():
        raise AsrDownloadError(f"URL 不在推荐清单内（精确匹配失败）: {raw}")


def _validate_host_ips(hostname: str) -> None:
    """层3（护栏⑥）：host 小名单 + 解析 IP 全量判定。

    回环/私网/链路本地/保留/多播任一真即拒；DNS 解析失败同样拒绝
    （fail-closed——不解析出公网 IP 就不给下载面）。"""
    if (hostname or "").lower() not in _ASR_HOST_ALLOW:
        raise AsrDownloadError(f"下载源域名不在白名单: {hostname}")
    try:
        infos = socket.getaddrinfo(hostname, 443,
                                   proto=socket.IPPROTO_TCP)
    except OSError as e:
        raise AsrDownloadError(f"下载源域名解析失败: {hostname}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_loopback or ip.is_private or ip.is_link_local
                or ip.is_reserved or ip.is_multicast):
            raise AsrDownloadError(
                f"下载源解析到受限 IP（SSRF 护栏⑥）: {hostname} -> {ip}")


def _validate_redirect_target(url: str) -> None:
    """重定向逐跳合格性（评议员条件④）：重定向目标不可能再等于清单 URL
    （清单 URL 已被层2精确匹配消费），故跳过层2、改用 https 强制 + host
    小名单 + IP 校验双层。"""
    parts = urllib.parse.urlsplit(str(url))
    if parts.scheme.lower() != "https" or not parts.hostname:
        raise AsrDownloadError(f"重定向目标非 https: {url}")
    _validate_host_ips(parts.hostname)


class _GuardedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """逐跳校验的重定向处理器（默认最多 5 跳，不合格即抛 AsrDownloadError）。"""

    max_repeats = 4
    max_redirections = _MAX_REDIRECTS

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            _validate_redirect_target(newurl)
        except AsrDownloadError:
            fp.close()
            raise
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _build_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_GuardedRedirectHandler())


# ---------------------------------------------------------------------------
# 下载本体
# ---------------------------------------------------------------------------

def _open_part(tmp: str):
    """打开 .part 写句柄；OSError（ENOSPC 等）→ AsrDiskWriteError + 清残件。

    独立封装原因：① 写盘失败必须与网络失败分层上抛（评议员条件⑥，
    不得伪装成网络错误触发跨源轮换）；② SIM115 收口点。"""
    try:
        return open(tmp, "wb")  # noqa: SIM115 - 句柄交由调用方 with 托管
    except OSError as e:
        _unlink_quiet(tmp)
        raise AsrDiskWriteError(f"{_DISK_ERR}: {e}") from e


def _http_get_asr(url: str, dest: str, progress: Callable | None = None) -> None:
    """下载到 dest（仿 dict_manager._http_get：UA、10s 连接超时、1MB 分块
    写 ``dest + ".part"``、progress(downloaded, total) 逐块回调、os.replace
    原子改名）+ 三层 URL 校验 + 逐跳守卫 opener。

    异常分层：网络层失败（含重定向拒）统一包装 AsrDownloadError；写盘阶段
    OSError（ENOSPC 等）原样以 AsrDiskWriteError 上抛——不得伪装成网络失败
    触发跨源轮换（评议员条件⑥）。"""
    _validate_url(url)                      # 层1+2（原始值防御校验）
    hostname = urllib.parse.urlsplit(url.strip()).hostname or ""
    _validate_host_ips(hostname)            # 层3
    req = urllib.request.Request(url.strip(),
                                 headers={"User-Agent": "subtransjav-asr"})
    tmp = dest + ".part"
    try:
        with _build_opener().open(req, timeout=_CONNECT_TIMEOUT_S) as resp:
            total = None
            try:
                cl = resp.headers.get("Content-Length")
                total = int(cl) if cl else None
            except (TypeError, ValueError):
                total = None
            done = 0
            out = _open_part(tmp)           # OSError→AsrDiskWriteError（含 .part 清理）
            with out:
                while True:
                    chunk = resp.read(_CHUNK)   # 网络 OSError → 外层包装
                    if not chunk:
                        break
                    try:
                        out.write(chunk)
                    except OSError as e:
                        _unlink_quiet(tmp)
                        raise AsrDiskWriteError(f"{_DISK_ERR}: {e}") from e
                    done += len(chunk)
                    if progress is not None:
                        progress(done, total)
    except AsrDiskWriteError:
        raise
    except Exception as e:  # noqa: BLE001 - 网络层统一转义
        _unlink_quiet(tmp)
        raise AsrDownloadError(f"{url} -> {type(e).__name__}: {e}") from e
    os.replace(tmp, dest)


def _disk_preflight(out_dir: str, expected_bytes: int) -> None:
    """磁盘预检（评议员条件⑥，fail-closed）：需空间=expected×1.1+100MB 余量；
    shutil.disk_usage 不可得（OSError）→ 拒绝下载。

    与 dict_manager._check_free_space 的 fail-open 有意不同：3GB 件量级下
    卷信息不可得即写，一旦中途 ENOSPC 用户要付出整块盘清理代价，宁可先拒。"""
    need = int(expected_bytes * 1.1) + 100 * 1024 * 1024
    try:
        free = shutil.disk_usage(out_dir).free
    except OSError as e:
        raise AsrDownloadError(
            f"磁盘空间预检不可得，已拒绝下载（3GB 件量级 fail-closed）: {e}"
        ) from e
    if free < need:
        raise AsrDownloadError(
            f"磁盘可用空间不足：本次约需 {need // (1024 * 1024)}MB，"
            f"当前仅剩 {free // (1024 * 1024)}MB（请清理后重试）")


def _symlink_guard(*targets: str) -> None:
    """符号链接守卫（评议员条件⑥）：任一目标/临时件是 link 即拒。"""
    for t in targets:
        if os.path.islink(t):
            raise AsrDownloadError(f"落位路径为符号链接，已拒绝写入: {t}")


def download_asr_model(model: str, source: str = "auto") -> str:
    """显式下载推荐 ASR 模型到数据根 ``models/asr/<model>.pt``。

    model 白名单=清单中 support=="available" 的 name（落位文件名一律由清单
    model 字段派生，路径注入面封死）；source ∈ {auto, official, mirror}。
    候选源=条目 sources 中 verified==True 者（PENDING 永不上候选）：
    auto/official 顺序全取（官方在前），mirror 只取 source=="mirror"。
    返回落位路径；官方源网络失败且存在下一源时进度 note 可见回退提示
    （评议员条件①）；校验失败删 .part 直接抛不轮换（对齐 dict 语义）。"""
    entry = next((e for e in asr_env.ASR_RECOMMENDED_MODELS
                  if e.get("name") == model
                  and e.get("support") == "available"), None)
    if entry is None:
        raise AsrDownloadError(f"未知或不可下载的 ASR 模型: {model}")
    if source not in ("auto", "official", "mirror"):
        raise AsrDownloadError(f"非法下载源: {source}")

    verified = [s for s in (entry.get("sources") or []) if s.get("verified")]
    if source == "mirror":
        candidates = [s for s in verified if s.get("source") == "mirror"]
        if not candidates:
            raise AsrDownloadError("该模型暂无可用镜像源")
    else:
        candidates = list(verified)          # 官方在前（清单顺序）
    if not candidates:
        raise AsrDownloadError("该模型无可用下载源")

    if model in _ACTIVE_DOWNLOADS:
        raise AsrDownloadError("该模型已有下载进行中")
    _ACTIVE_DOWNLOADS.add(model)
    try:
        return _download_impl(entry, candidates, source)
    finally:
        _ACTIVE_DOWNLOADS.discard(model)


def _download_impl(entry: dict, candidates: list, source: str) -> str:
    model = str(entry["name"])
    fname = f"{entry['model']}.pt"           # 文件名一律由清单 model 字段派生
    out_dir = os.path.normpath(str(paths.data_subdir("models", "asr")))
    os.makedirs(out_dir, exist_ok=True)
    if os.path.islink(out_dir) or not os.path.isdir(out_dir):
        raise AsrDownloadError(f"落位目录非法（须为真实目录）: {out_dir}")
    dest = os.path.join(out_dir, fname)
    part = dest + ".part"
    extracting = dest + ".extracting"
    # 启动侧清理：旧残留（无取消语义：重下清 .part 从零开始）
    _unlink_quiet(part)
    _unlink_quiet(extracting)
    _disk_preflight(out_dir, int(entry.get("bytes") or 0))
    _symlink_guard(dest, part)

    last_err: Exception | None = None
    for idx, s in enumerate(candidates):
        url = str(s.get("url") or "")
        _set_progress(model, "download", 0, None)
        _symlink_guard(dest, part)           # 写 .part 前守卫（逐源复查）
        try:
            _http_get_asr(url, part,
                          progress=lambda n, t: _set_progress(
                              model, "download", n, t))
        except (AsrDiskWriteError, OSError) as e:
            # 评议员条件⑥：磁盘空间不足/写入失败——不轮换，failed 相位后抛
            _unlink_quiet(part)
            _set_progress(model, "failed", error=_DISK_ERR, note=_DISK_ERR)
            raise AsrDownloadError(_DISK_ERR) from e
        except AsrDownloadError as e:
            last_err = e
            has_next = any(c.get("verified") for c in candidates[idx + 1:])
            if source in ("auto", "official") and has_next:
                # 评议员条件①：回退必须可见（进度 note + 日志双通道）
                prev = _ASR_DOWNLOAD_PROGRESS.get(model) or {}
                _set_progress(model, str(prev.get("phase") or "download"),
                              int(prev.get("downloaded") or 0),
                              prev.get("total"), note=_FALLBACK_NOTE)
                logger.info("%s（model=%s）", _FALLBACK_NOTE, model)
            continue
        _carry_progress(model, "verify")
        if _sha256_file(part) != entry.get("sha256"):
            _unlink_quiet(part)
            # 校验失败不轮换直接报（防串改文件被"换个源洗白"）
            raise AsrChecksumError(
                f"SHA256 校验失败，已拒绝落位: {url}")
        _symlink_guard(dest, part)           # 改名前守卫
        try:
            os.replace(part, dest)
        except OSError as e:
            _unlink_quiet(part)
            _set_progress(model, "failed", error=_DISK_ERR, note=_DISK_ERR)
            raise AsrDownloadError(_DISK_ERR) from e
        size = os.path.getsize(dest)
        _set_progress(model, "done", size, size)
        return dest
    if last_err is not None:
        prev = _ASR_DOWNLOAD_PROGRESS.get(model) or {}
        _set_progress(model, "failed", int(prev.get("downloaded") or 0),
                      prev.get("total"), error=str(last_err))
        raise last_err
    raise AsrDownloadError("该模型无可用下载源")
