"""品牌统一钉测试（D2026-1004-02 第 1 层：用户可见层 SubTransJAV→SubTrans）。

遍历 git tracked 文本文件，断言含品牌词 ``SubTransJAV`` 的文件集合
等于显式白名单 ALLOWLIST。未来任何新代码/新文案引入旧品牌词即本测试变红，
防止品牌漂移；白名单内每项均带保留理由。

另含上游项目名钉（G19，D2026-1106-01 慢清③）：whisperjav/wjtranslate
大小写不敏感入钉——品牌散文零容忍（已随慢清②中性化），字面量仅允许
格式兼容面与清理锚（_UPSTREAM_ALLOWLIST），tests/ 夹具域豁免（
.whisperjav 后缀族是兼容层被测语义本身，夹具命名纪律由合规终扫门②
合成名口径治理）。

白名单之外的新增出现 → 先判断是否禁区残留（数据根/spec 名/env 名等第 2 层口径），
确属新品牌污染则改为 SubTrans，确需保留则在本白名单补条目并注释理由。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# 扩展名兜底排除（二进制/资产；正文另有 NUL 字节 + 解码双重探测）
_BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".ico", ".gif", ".exe", ".zip", ".dll",
    ".ttf", ".woff", ".woff2", ".mp3", ".bin", ".srt",
}

# 旧品牌词 SubTransJAV 保留白名单（每项一行理由；路径以 / 分隔，跨平台比较）：
# D2026-1004-04 批1 后重算：spec 改名/dist 目录/产物 exe 名/安装目录/数据根
# 默认/AUMID/Documents 输出均已切 SubTrans，品牌串清空条目已删；剩余为
# 历史文档、注释级残留与旧品牌清理锚。
# D2026-1012-03：docs/design/** 整体豁免出判定面（_EXEMPT_PREFIXES，guard
# 断言锁死）——任务卡验收命令需引用真实仓库根路径、批清单/原型引旧品牌串
# 属引用非漂移；白名单只保留产品面与 docs 根级/历史档案（原 20 条
# docs/design 条目随之移除）。
ALLOWLIST = frozenset({
    # ---- CI/打包链（清理锚；历史注释行已随 D2026-1106-01 中性化）----
    "packaging/setup.iss",                 # [InstallDelete] 旧开始菜单组 {commonprograms}\SubTransJAV 清理锚（对不存在路径无害空操作）；AppId GUID/env 名禁区不动
    # ---- 用户/历史文档（不改史）----
    "CHANGELOG.md",                        # 历史变更记录（历史 commit 链接 Angelholl/SubTransJAV；不改史）
    # ---- 测试（本机路径，allowlist 明文保护）----
    "tests/test_media_path.py",            # 本机仓库绝对路径 D:/SubTransJAV 夹具（禁区）
    "tests/test_strings_and_shortcut.py",  # LEGACY_LNK_NAMES 旧桌面快捷方式名 SubTransJAV.lnk 清理锚（与 uninstall.bat LNK6 同源；d1102 桌面图标空白事故后补，防单侧清理漂移）
    # ---- bat 残留（旧品牌清理锚）----
    "uninstall.bat",                       # LNK6 旧桌面快捷方式 SubTransJAV.lnk 清理锚（D2026-1004-04 新增；任务栏钉扎 Quick Launch\User Pinned\TaskBar 红线永不清理）；小写 %LOCALAPPDATA%\subtrans 缓存目录清理行不匹配本钉
    # ---- 慢清①（D2026-1106-01）收尾：源码 docstring/前端文件头/bench print
    # 注释级残留 13 文件已全部中性化为 SubTrans，白名单条目同步移除（钉的
    # 精度恢复）；L9 清单见 docs/design/d1106-法律合规审计与清理报告.md。
})

# 本测试文件自身因白名单理由字符串引用旧品牌词而含品牌词，
# 显式自排除（tracked 前后行为一致），不入白名单集合。
_SELF = "tests/test_brand_allowlist.py"

# 豁免前缀（D2026-1012-03）：docs/design/** 为内部工作文档，整体移出判定面；
# 产品面（源码/前端资产/打包/发布资产/根级文档）仍 default-deny 全量钉死。
# guard 断言锁死豁免面：扩大豁免必须改断言、在 diff 里可见。
_EXEMPT_PREFIXES = ("docs/design/",)


def _tracked_text_files() -> list[str]:
    """git ls-files 全量 tracked 文件；排除二进制（NUL 字节探测 + 解码失败跳过）。"""
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, check=True,
        capture_output=True,
    )
    files = []
    for raw in out.stdout.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", "surrogateescape")
        if Path(rel).suffix.lower() in _BINARY_EXTS:
            continue
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        blob = path.read_bytes()
        if b"\x00" in blob:  # 二进制
            continue
        try:
            blob.decode("utf-8")
        except UnicodeDecodeError:
            try:
                blob.decode("gbk")
            except UnicodeDecodeError:
                continue  # 非 utf-8/gbk 文本（二进制兜底）
        files.append(rel.replace("\\", "/"))
    return files


def test_brand_subtrans_only_in_allowlist():
    """含旧品牌词 SubTransJAV 的 tracked 文本文件集合 == 白名单（防品牌漂移钉）。

    docs/design/** 豁免出判定面（D2026-1012-03），豁免面由断言锁死。"""
    assert _EXEMPT_PREFIXES == ("docs/design/",), (
        "豁免前缀只允许 docs/design/；扩大豁免须先评议并改本断言（diff 可见）")
    assert not any(rel.startswith(_EXEMPT_PREFIXES) for rel in ALLOWLIST), (
        "白名单不得含豁免前缀内条目（保持钉的精度，豁免即出清）")
    hits = {
        rel for rel in _tracked_text_files()
        if rel != _SELF
        and not rel.startswith(_EXEMPT_PREFIXES)
        and b"SubTransJAV" in (REPO_ROOT / rel).read_bytes()
    }
    unexpected = sorted(hits - ALLOWLIST)
    missing = sorted(ALLOWLIST - hits)
    assert not unexpected, (
        "发现白名单外的旧品牌词 SubTransJAV（品牌漂移），"
        "请改为 SubTrans 或补白名单并注释理由：\n" + "\n".join(unexpected)
    )
    assert not missing, (
        "白名单条目已不再含 SubTransJAV，请从白名单移除（保持钉的精度）：\n"
        + "\n".join(missing)
    )


# ---------------------------------------------------------------------------
# G19 上游项目名钉（D2026-1106-01 慢清③）：whisperjav / wjtranslate
# ---------------------------------------------------------------------------

# 判定面豁免前缀：docs/design/**（内部工作文档，沿用既有豁免）＋ tests/**
# （.whisperjav 后缀族夹具=兼容层被测语义；夹具命名纪律归合规终扫门②）。
# guard 断言锁死豁免面：扩大豁免必须改断言、在 diff 里可见。
_UPSTREAM_EXEMPT_PREFIXES = ("docs/design/", "tests/")

# 上游名字面量保留白名单（每项一行理由）。仅两类合法保留：
# ①上游格式兼容面——产物文件名/后缀族常量及其文档说明（D2026-1029-01
#   「asr_meta 输入兼容三面保留」：功能必须读旧名，字面量=格式事实）；
# ②清理锚——uninstall.bat LNK 族（拍板保留，与 SubTransJAV 锚同源）。
_UPSTREAM_ALLOWLIST = frozenset({
    "CHANGELOG.md",                        # 历史变更记录（不改史）
    "README.md",                           # 历史产物只读兼容说明（固定文件名/后缀族字面量）
    "docs/使用与维护手册.md",              # H4a/H4b/只读兼容说明（固定文件名/后缀族字面量）
    "subtrans/refine/asr_meta.py",         # 格式属主：RUN_META_NAME 与 .whisperjav 后缀剥链常量
    "subtrans/refine/cli.py",              # CLI 帮助文本须显示固定文件名（用户须知格式事实）
    "subtrans/refine/pass_disagreement.py",  # 格式属主：.merged 可选尾缀族 _MARKER_RE
    "subtrans/webview_gui/api.py",         # 剥后缀链注释（引用 asr_meta 常量族，格式事实）
    "uninstall.bat",                       # LNK2 旧快捷方式名 WhisperJAV Translate.lnk 清理锚（拍板保留）
})


def test_brand_no_upstream_project_names():
    """上游项目名 whisperjav/wjtranslate 入钉（G19，D2026-1106-01 慢清③）。

    大小写不敏感扫描 tracked 文本文件；豁免面由断言锁死；白名单双向
    断言（多出=品牌漂移即红，失效条目=钉精度衰减即红）。"""
    assert _UPSTREAM_EXEMPT_PREFIXES == ("docs/design/", "tests/"), (
        "上游名钉豁免前缀变更须先评议并改本断言（diff 可见）")
    hits: dict[str, set[str]] = {}
    for rel in _tracked_text_files():
        if rel == _SELF or rel.startswith(_UPSTREAM_EXEMPT_PREFIXES):
            continue
        blob = (REPO_ROOT / rel).read_bytes()
        low = blob.lower()
        found = {tok for tok in ("whisperjav", "wjtranslate") if tok.encode() in low}
        if found:
            hits[rel] = found
    unexpected = sorted(set(hits) - _UPSTREAM_ALLOWLIST)
    missing = sorted(rel for rel in _UPSTREAM_ALLOWLIST
                     if rel not in hits)
    assert not unexpected, (
        "发现白名单外的上游项目名 whisperjav/wjtranslate（品牌漂移），"
        "请改为「上游转写工作流」等中性表述，确属格式兼容面/清理锚则补白名单"
        "并注释理由：\n" + "\n".join(unexpected)
    )
    assert not missing, (
        "上游名白名单条目已不再含字面量，请从白名单移除（保持钉的精度）：\n"
        + "\n".join(missing)
    )
