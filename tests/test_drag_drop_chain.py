"""d1021-卡1：拖拽加载链路回归钉（必修①字幕后缀口径 ＋ 诊断埋点存在性）。

背景：main.py on_drop_event 的 allowed_exts 已在 2.7.2 件1 放开到
.ass/.ssa/.vtt，但校对页 JS 侧 REVIEW_SRT_EXTS 仍只写 ['.srt']，
导致校对页拖入 .ass/.ssa/.vtt 被 isSrt 过滤静默丢弃。本文件按
test_gui_js_static.py 的静态断言形态（源码文本提取）钉死两侧一致。
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI_DIR = ROOT / "subtransjav" / "webview_gui"

SUBTITLE_EXTS = {".srt", ".ass", ".ssa", ".vtt"}


def _read(rel: str) -> str:
    return (GUI_DIR / rel).read_text(encoding="utf-8")


def _review_js() -> str:
    return _read("assets/review.js")


def _main_src() -> str:
    return _read("main.py")


def _review_srt_exts(src: str) -> set:
    m = re.search(r"REVIEW_SRT_EXTS:\s*\[([^\]]*)\]", src)
    assert m, "review.js 未找到 REVIEW_SRT_EXTS"
    exts = set(re.findall(r"'(\.[a-z0-9]+)'", m.group(1)))
    assert exts, "review.js REVIEW_SRT_EXTS 解析为空"
    return exts


def _main_allowed_exts(src: str) -> set:
    m = re.search(r"allowed_exts\s*=\s*\(([^)]*)\)", src)
    assert m, "main.py 未找到 allowed_exts 元组"
    exts = set(re.findall(r"'(\.[a-z0-9]+)'", m.group(1)))
    assert exts, "main.py allowed_exts 解析为空"
    return exts


def _extract_body(src: str, marker: str, stop: str) -> str:
    start = src.find(marker)
    assert start > -1, f"未找到 {marker}"
    end = src.find(stop, start)
    assert end > start, f"未找到 {marker} 的结束锚点 {stop}"
    return src[start:end]


def test_review_srt_exts_cover_four_subtitle_exts():
    """必修①：校对页字幕后缀集合 = .srt/.ass/.ssa/.vtt（与 dialog/main 同口径）。"""
    exts = _review_srt_exts(_review_js())
    assert exts == SUBTITLE_EXTS, \
        f"校对页拖入字幕后缀集合漂移: {sorted(exts)}"


def test_review_srt_exts_synced_with_main_drop_whitelist():
    """防漂移钉：REVIEW_SRT_EXTS 与 main.py 放行集的字幕子集逐项相等。"""
    js_exts = _review_srt_exts(_review_js())
    main_exts = _main_allowed_exts(_main_src())
    assert main_exts & SUBTITLE_EXTS == js_exts, (
        "main.py 放行集字幕子集与 review.js REVIEW_SRT_EXTS 不同步: "
        f"main={sorted(main_exts & SUBTITLE_EXTS)} js={sorted(js_exts)}"
    )


def test_review_ondroppedfiles_consumes_all_subtitle_exts():
    """onDroppedFiles 的 isSrt 走 REVIEW_SRT_EXTS，且无单后缀硬编码残留。"""
    src = _review_js()
    body = _extract_body(src, "onDroppedFiles(paths)", "\n    setVideoPath(path)")
    assert "REVIEW_SRT_EXTS.some" in body, \
        "onDroppedFiles 的 isSrt 未走 REVIEW_SRT_EXTS"
    assert "filter(isSrt)" in body and "setSrtPath" in body, \
        "onDroppedFiles 未把字幕后缀文件交给 setSrtPath"
    assert "endsWith('.srt')" not in body, \
        "onDroppedFiles 仍残留 .srt 单后缀硬编码（会丢弃 .ass/.ssa/.vtt）"


def test_on_drop_event_emits_chain_diagnostics(capsys, monkeypatch):
    """阶段2：drop 链诊断埋点每步一行（触发/文件数/过滤前后/evaluate_js 前后），
    且埋点为纯增量——放行文件仍汇聚为一次 ReviewUI 转发。"""
    import webview

    from subtransjav.webview_gui.main import on_drop_event

    scripts = []

    class FakeWin:
        @staticmethod
        def evaluate_js(script):
            scripts.append(script)

    monkeypatch.setattr(webview, "windows", [FakeWin()])
    event = {"dataTransfer": {"files": [
        {"pywebviewFullPath": "D:/x/a.ass"},
        {"name": "b.txt"},  # 无 pywebviewFullPath = 注入失效形态
    ]}}
    on_drop_event(event)
    out = capsys.readouterr().out
    assert "[drop] event received files=2" in out
    assert "[drop] filter pathless=1 allowed=1 of 2" in out
    assert "[drop] evaluate_js begin n=1" in out
    assert "[drop] evaluate_js ok" in out
    assert len(scripts) == 1 and "a.ass" in scripts[0]


def test_filelist_drop_listener_must_not_stop_propagation():
    """d1021-卡1 缺陷B 静态钉：#fileList 的 drop 监听禁 stopPropagation——
    pywebview 桥的 document 级 drop 监听（main.py bind_dom_events）靠冒泡接收，
    目标层拦断 = document 收不到 = 拖拽文件永不加载（v2.6.0 起回归）。"""
    from pathlib import Path
    body = Path("subtransjav/webview_gui/assets/app-file-list.js").read_text(encoding="utf-8")
    drop_block = body[body.index("fileList.addEventListener('drop'"):]
    drop_block = drop_block[:drop_block.index("});")]
    code_only = "\n".join(line for line in drop_block.splitlines()
                          if not line.strip().startswith("//"))
    assert "stopPropagation" not in code_only, \
        "#fileList drop 监听不得 stopPropagation，否则 document 级 pywebview 桥接收不到 drop"
    assert "preventDefault" in drop_block, "preventDefault 必须保留（防 WebView2 默认打开文件）"
