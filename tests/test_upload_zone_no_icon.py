"""d1018-卡2 回归锁：上传拖拽区箭头图标组已移除（先红后绿）。

实测适配说明（卡面描述 → 现状核对）：
- 卡面锚点（行号约 932-934 / 三条 path d 值 / 文案「导入视频与字幕开始校对」
  / review 家族 CSS）全部指向右栏校对导入区 #reviewDropzone，
  本锁按该区块落断言；
- <p class="dropzone-text">导入视频与字幕开始校对</p> 在 index.html 不存在，
  该文案由 assets/review.js 的 review_drop_title 经 i18n 填充进 dz-title，
  文案存活锁改锁 review.js，另锁 index.html 中 dz-title/dz-actions 结构节点；
- style.css 仅存在 #tab-review .dz-icon（#reviewDropzone 删后即死代码），
  本锁断言其不再出现；#tab-translate .dz-icon 属主导入区，不在本卡范围。
"""

from pathlib import Path

ASSETS = (Path(__file__).resolve().parents[1]
          / "subtransjav" / "webview_gui" / "assets")
INDEX_HTML = ASSETS / "index.html"
STYLE_CSS = ASSETS / "style.css"
REVIEW_JS = ASSETS / "review.js"

# 卡面三条 path d 值锚点（向上箭头 + 底部下划线图标组）
DROP_PATHS = ("M12 16V4", "m6 10 6-6 6 6", "M4 20h16")


def _review_dropzone_block() -> str:
    """截取 index.html 中 id=reviewDropzone 起至下一节注释（播放器）止的区间。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    start = html.index('id="reviewDropzone"')
    end = html.index("<!-- 播放器", start)
    return html[start:end]


def test_review_dropzone_no_dz_icon():
    block = _review_dropzone_block()
    assert "dz-icon" not in block


def test_review_dropzone_no_arrow_paths():
    block = _review_dropzone_block()
    for d in DROP_PATHS:
        assert d not in block, d


def test_review_dropzone_text_nodes_kept():
    # 仅删图标组，其余结构（标题/提示/动作按钮容器）原样保留
    block = _review_dropzone_block()
    assert "dz-title" in block
    assert "dz-hint" in block
    assert "dz-actions" in block


def test_review_drop_title_text_alive():
    # 文案存活锁：i18n 词条保留，初始化后回填 dz-title
    js = REVIEW_JS.read_text(encoding="utf-8")
    assert "review_drop_title: '导入视频与字幕开始校对'" in js


def test_style_css_no_review_dz_icon_rule():
    css = STYLE_CSS.read_text(encoding="utf-8")
    assert "#tab-review .dz-icon" not in css
