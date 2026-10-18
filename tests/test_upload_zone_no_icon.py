"""d1018-卡2/卡3 回归锁：上传拖拽区箭头图标组已全站移除（先红后绿）。

卡2（#reviewDropzone 右栏校对导入区）实测适配说明：
- 卡面锚点（行号约 932-934 / 三条 path d 值 / 文案「导入视频与字幕开始校对」
  / review 家族 CSS）全部指向右栏校对导入区 #reviewDropzone，
  本锁按该区块落断言；
- <p class="dropzone-text">导入视频与字幕开始校对</p> 在 index.html 不存在，
  该文案由 assets/review.js 的 review_drop_title 经 i18n 填充进 dz-title，
  文案存活锁改锁 review.js，另锁 index.html 中 dz-title/dz-actions 结构节点。

卡3（owner 授权全站连根拔）扩展：#dropzone 主导入区同款图标一并移除，
dz-icon 升级为全站口径——index.html / style.css / 全部 js 资产均不得再出现；
功能性图标（addFilesBtn/addFolderBtn 按钮内 SVG、主题切换、chevron 等）不在口径。
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


# ---- 以下为 d1018-卡3 扩展：全站 dz-icon 连根拔 ----


def test_index_html_no_dz_icon_site_wide():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "dz-icon" not in html


def test_style_css_no_dz_icon_site_wide():
    css = STYLE_CSS.read_text(encoding="utf-8")
    assert "dz-icon" not in css


def test_js_assets_no_dz_icon():
    for js in ASSETS.glob("*.js"):
        assert "dz-icon" not in js.read_text(encoding="utf-8"), js.name


def test_index_html_no_arrow_paths_site_wide():
    # 三条 path d 值在 index.html 全文唯一属 dz-icon 图标（裁卡时实测），全站禁现
    html = INDEX_HTML.read_text(encoding="utf-8")
    for d in DROP_PATHS:
        assert d not in html, d


def test_dropzone_text_nodes_kept():
    # 主导入区只删图标：标题/提示/动作按钮结构与其 i18n 挂点保留
    html = INDEX_HTML.read_text(encoding="utf-8")
    segment = html[html.index('id="dropzone"'):][:2500]
    assert 'data-i18n="source_header"' in segment
    assert 'data-i18n="empty_hint"' in segment
    assert "addFilesBtn" in segment
    assert "addFolderBtn" in segment


def test_style_css_has_files_hint_rule_alive():
    # has-files 隐藏提示是活功能（app-main.js 切换 class）：
    # 组合选择器摘 .dz-icon 行后 .dz-hint 分支必须仍存活
    css = STYLE_CSS.read_text(encoding="utf-8")
    assert "#tab-translate.has-files .dz-hint" in css
