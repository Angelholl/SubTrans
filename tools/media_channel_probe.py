"""媒体通道回归探针（2.7.5 件A / D2026-1007-02 常驻门工具）。

吸收原 spike 工件 tools/spike_review_video.py 升格而来（见
docs/decision-log.md D2026-1002-09 §七 与 D2026-1007-02）。

【用途】本地/真机验证 GUI 页面加载方式对 file:/// 媒体通道的影响：
- path 模式（``url=str(路径)``，旧行为）：pywebview 内置 Bottle 伺服，
  origin=http://127.0.0.1:随机端口，预期 WebView2 拒绝全部 file:/// 媒体；
- uri 模式（``url=Path.as_uri()``，2.7.5 件A 生产行为）：origin=file://，
  预期 4 个媒体变体全部 loadedmetadata。

两模式各起一个 pywebview 窗口（private_mode=True 与生产一致），同一次
webview.start 并发运行，页面经 js_api 桥回传采集结果，约 15 秒自毁。

【硬性契约】任一不满足 → 退出码非零：
- pywebview 版本（importlib.metadata 实测）满足 >=6.2,<7；
- uri 模式 location.protocol == "file:"；
- uri 模式 4 媒体（ASCII 路径 / 中文路径 / 含空格路径 / 盘符 %3A 编码变体）
  全部 loadedmetadata；
- js_api 桥回传成功（报告回调失败 = 失败退出）。
path 模式仅打印对照结果（预期 http origin + 全拒），不参与退出码判定。
页面另含无效 src 的 <audio> 与带 no-src guard 的 error 监听，验证
错误可见性模式（src 为空/被移除时的 error 不误报）。

【媒体来源】ffmpeg 在 PATH 时于探针目录合成 3 秒 h264+aac 小片；否则优雅
降级为复用本机任一已存在的真实小视频并打印注明。

【门属性】需要显示器（真窗口渲染），仅限本地/真机运行；文件名非 test_*
且不在 tests/ 下，pytest 不会收集。--keep 保留 %TEMP%/stj_media_probe/
现场供人工排查。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

PROBE_DIR = Path(tempfile.gettempdir()) / "stj_media_probe"
SELF_DESTRUCT_SECONDS = 15
REPORT_GRACE_SECONDS = 45
MEDIA_KEYS = ("ascii", "chinese", "space", "colon_encoded")

# 页面模板（__TOKEN__ 字符串替换，避免 format 与 JS 花括号打架）
_PAGE_TEMPLATE = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>media probe __MODE__</title></head>
<body>
<h3>mode=__MODE__</h3>
__VIDEOS__
<audio id="bad-audio" src="file:///nonexistent__no_such_file.mp3"></audio>
<pre id="out">collecting...</pre>
<script>
const results = {
  protocol: location.protocol,
  href: location.href,
  media: {},
  audioErrorSeen: false
};
document.querySelectorAll('video[data-key]').forEach(function (v) {
  v.addEventListener('loadedmetadata', function () {
    results.media[v.dataset.key] = true;
  });
  v.addEventListener('error', function () {
    if (!v.getAttribute('src')) return; // no-src guard：src 为空时的 error 不计
    results.media[v.dataset.key] = false;
  });
});
const bad = document.getElementById('bad-audio');
bad.addEventListener('error', function () {
  if (!bad.getAttribute('src')) return; // no-src guard
  results.audioErrorSeen = true;
});
function report() {
  try {
    window.pywebview.api.report(JSON.stringify(results));
  } catch (e) {
    document.getElementById('out').textContent = 'report failed: ' + e;
  }
}
if (window.pywebview) {
  setTimeout(report, 5000);
} else {
  window.addEventListener('pywebviewready', function () {
    setTimeout(report, 5000);
  });
}
</script>
</body>
</html>
"""


def _pywebview_version_raw() -> str:
    from importlib.metadata import version

    return version("pywebview")


def _version_tuple(raw: str) -> tuple[int, int] | None:
    parts = raw.split(".")
    try:
        return int(parts[0]), int(parts[1])
    except (IndexError, ValueError):
        return None


def _find_existing_video() -> Path | None:
    """ffmpeg 缺席时的降级来源：浅层找任一已有真实小视频（≤100MB）。"""
    roots = [
        Path.home() / "Videos",
        Path(tempfile.gettempdir()),
        Path(__file__).resolve().parent.parent,
    ]
    candidates: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for pattern in ("*.mp4", "*.mkv", "*.webm"):
            candidates.extend(p for p in root.glob(pattern) if p.is_file())
    usable = [
        p for p in candidates
        if 0 < p.stat().st_size <= 100 * 1024 * 1024
    ]
    usable.sort(key=lambda p: p.stat().st_size)
    return usable[0] if usable else None


def _prepare_media() -> tuple[dict[str, str], str]:
    """生成 3 个命名媒体文件；返回 {key: 路径} 与来源说明。"""
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    names = {"ascii": "ascii.mp4", "chinese": "中文媒体.mp4", "space": "带 空格.mp4"}
    target = PROBE_DIR / names["ascii"]
    ffmpeg = shutil.which("ffmpeg")
    source_note = ""
    if ffmpeg:
        proc = subprocess.run(  # noqa: S603  ffmpeg 取自 PATH，参数全字面量
            [
                ffmpeg, "-y", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=15",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest", str(target),
            ],
            capture_output=True, text=True, timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode == 0 and target.exists():
            source_note = "ffmpeg 合成 3 秒 h264+aac 小片"
        else:
            print(f"⚠️ ffmpeg 合成失败（rc={proc.returncode}），转降级复用: {proc.stderr[-200:]}")
            ffmpeg = None
    if not ffmpeg:
        reused = _find_existing_video()
        if reused is None:
            print("❌ ffmpeg 不可用且未找到可复用的已有视频，探针无法执行")
            sys.exit(2)
        shutil.copyfile(reused, target)
        source_note = f"降级：复用已有真实小视频 {reused}（ffmpeg 不在 PATH 或合成失败）"
    for key in ("chinese", "space"):
        shutil.copyfile(target, PROBE_DIR / names[key])
    return {k: str(PROBE_DIR / v) for k, v in names.items()}, source_note


def _build_page(mode: str, media_uris: dict[str, str]) -> str:
    videos = "\n".join(
        f"<video data-key='{k}' src='{u}' muted playsinline></video>"
        for k, u in media_uris.items()
    )
    return (_PAGE_TEMPLATE
            .replace("__MODE__", mode)
            .replace("__VIDEOS__", videos))


class _ProbeApi:
    """js_api 桥：页面 report() 回传采集结果（回调失败=超时判失败）。"""

    def __init__(self) -> None:
        self.result: dict[str, Any] | None = None
        self.reported = threading.Event()

    def report(self, payload_json: str) -> None:
        self.result = json.loads(payload_json)
        self.reported.set()


def run(keep: bool) -> int:
    # ---- 契约前置：pywebview 版本下限/上限钉 ----
    raw_version = _pywebview_version_raw()
    version = _version_tuple(raw_version)
    if version is None or not ((6, 2) <= version < (7, 0)):
        print(f"❌ pywebview 版本 {raw_version} 不满足契约 >=6.2,<7")
        return 1

    paths, source_note = _prepare_media()
    print(f"媒体来源: {source_note}")
    media_uris = {k: Path(v).as_uri() for k, v in paths.items()}
    # 盘符 %3A 编码变体：file:///D:/x → file:///D%3A/x。
    # 注意不能简单 replace(":/", ...)——"file:///" 自身就含 ":/"，会错改
    # scheme；须锚定 "file:///<盘符>:" 只编码盘符冒号。
    media_uris["colon_encoded"] = re.sub(
        r"^(file:///[^/:]+):", r"\1%3A", media_uris["ascii"])

    import webview  # 延迟导入：版本契约不过不进 GUI

    apis: dict[str, _ProbeApi] = {"path": _ProbeApi(), "uri": _ProbeApi()}
    windows: dict[str, Any] = {}
    for mode, api in apis.items():
        page = PROBE_DIR / f"probe_{mode}.html"
        page.write_text(_build_page(mode, media_uris), encoding="utf-8")
        url = str(page) if mode == "path" else page.as_uri()
        windows[mode] = webview.create_window(
            f"media probe [{mode}]", url=url, js_api=api,
            width=560, height=680,
        )
    for w in windows.values():
        timer = threading.Timer(SELF_DESTRUCT_SECONDS, w.destroy)
        timer.daemon = True
        timer.start()

    webview.start(private_mode=True)

    # start 返回（窗口自毁）后再给报告回传一个宽限期
    failures: list[str] = []
    for mode in ("path", "uri"):
        api = apis[mode]
        if not api.reported.wait(timeout=REPORT_GRACE_SECONDS):
            print(f"[{mode}] ❌ 未收到页面回传（报告回调失败/超时）")
            if mode == "uri":
                failures.append("uri 模式未收到 js_api 报告")
            continue
        result = api.result or {}
        print("=" * 64)
        print(f"[{mode}] protocol={result.get('protocol')} href={result.get('href')}")
        media = result.get("media") or {}
        for key in MEDIA_KEYS:
            state = {True: "loadedmetadata", False: "error/拒绝"}.get(
                media.get(key), "无事件(超时)")
            print(f"    {key:13s} -> {state}")
        print(f"    audio 无效src错误可见: {result.get('audioErrorSeen')}")
        if mode == "path":
            print("    （path 模式为对照，仅记录：预期 http origin + 全拒，不参与退出码）")
        if mode == "uri":
            if result.get("protocol") != "file:":
                failures.append(
                    f"uri 模式 protocol={result.get('protocol')!r} != 'file:'")
            bad_keys = [k for k in MEDIA_KEYS if media.get(k) is not True]
            if bad_keys:
                failures.append(f"uri 模式媒体未全部 loadedmetadata: {bad_keys}")

    if keep:
        print(f"--keep：现场保留于 {PROBE_DIR}")
    else:
        shutil.rmtree(PROBE_DIR, ignore_errors=True)

    print("=" * 64)
    if failures:
        print("❌ 契约失败：")
        for item in failures:
            print(f"  - {item}")
        return 1
    print(f"✅ 契约通过：pywebview {raw_version} 合规；"
          "uri 模式 file:// origin + 4 媒体全 loadedmetadata")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="媒体通道回归探针（需显示器的本地/真机门工具，pytest 不可收集）")
    parser.add_argument(
        "--keep", action="store_true",
        help="保留 %TEMP%/stj_media_probe/ 现场供人工排查")
    return run(keep=parser.parse_args().keep)


if __name__ == "__main__":
    sys.exit(main())
