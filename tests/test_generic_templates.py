"""通用化 P1（D2026-0930-01）：包内自带通用模板 + 角色卡四级回落。

覆盖：
1. 包内通用模板存在且两张齐全（subtransjav/refine/defaults/templates/）；
2. 通用模板无 JAV/成人专属残留措辞（grep 级断言）；
3. 四级回落：显式文件优先 / 数据根 config/templates 优先于包内 /
   仅包内时成功读取 / 全缺时明确报错；
4. 数据根旧卡优先语义（存量用户自定义模板不受影响——钉住）；
5. hardened 领域分布审计表存在且覆盖全部词条（keywords + patterns）。
"""

from pathlib import Path

import pytest
import yaml

from subtransjav.refine import pipeline_v2
from subtransjav.refine.cleaner_rules import resolve_data_file
from subtransjav.refine.pipeline_v2 import V2_TEMPLATE_FILES, _read_v2_card

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------

PKG_TEMPLATES = Path(pipeline_v2.__file__).parent / "defaults" / "templates"
REPO_ROOT = Path(pipeline_v2.__file__).parents[2]
AUDIT_DOC = REPO_ROOT / "docs" / "领域包-hardened-审计-20260930.md"

# 通用卡内不得残留的 JAV/成人专属措辞（grep 级断言用）
FORBIDDEN_TOKENS = [
    "JAV", "jav", "成人", "性爱", "高潮", "中出", "内射", "精液",
    "小穴", "阴部", "骚", "淫", "插入", "抽插", "敏感词", "挑逗",
    "エロ", "イク", "イく",
]


# ---------------------------------------------------------------------------
# 1. 包内通用模板存在且两张齐全
# ---------------------------------------------------------------------------

def test_pkg_generic_templates_exist_and_complete():
    for tag, fname in V2_TEMPLATE_FILES.items():
        p = PKG_TEMPLATES / fname
        assert p.is_file(), f"包内通用模板缺失：{p}"
        text = p.read_text(encoding="utf-8")
        # 两段式流程语义与硬约束必须在
        assert "Translation>" in text
        assert "[未翻译]" in text
        assert "只输出" in text
        assert "120个中文字符" in text
        if tag == "A":
            assert "净语" in text and "翻译" in text
        else:
            assert "审校" in text and "补译" in text


def test_pkg_templates_readme_exists():
    readme = PKG_TEMPLATES / "README-模板说明.txt"
    assert readme.is_file()
    text = readme.read_text(encoding="utf-8")
    assert "通用" in text
    assert "四级回落" in text or "优先级" in text
    assert "jav-domain" in text  # 指向领域示例包


# ---------------------------------------------------------------------------
# 2. 通用模板无 JAV/成人专属残留措辞
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fname", list(V2_TEMPLATE_FILES.values()))
def test_generic_cards_no_domain_residue(fname):
    text = (PKG_TEMPLATES / fname).read_text(encoding="utf-8")
    for token in FORBIDDEN_TOKENS:
        assert token not in text, f"通用卡残留领域措辞 '{token}'（{fname}）"


# ---------------------------------------------------------------------------
# 3+4. 四级回落链
# ---------------------------------------------------------------------------

def test_fallback_explicit_file_wins(tmp_path, monkeypatch):
    card = tmp_path / "explicit.txt"
    card.write_text("EXPLICIT_CARD", encoding="utf-8")
    # templates_dir 指向存在同名卡的目录，显式文件仍最高优先
    td = tmp_path / "td"
    td.mkdir()
    (td / V2_TEMPLATE_FILES["A"]).write_text("DATAROOT_CARD", encoding="utf-8")
    got = _read_v2_card("A", str(card), str(td))
    assert got == "EXPLICIT_CARD"


def test_fallback_dataroot_beats_package(tmp_path):
    """数据根旧卡优先语义（存量用户不受影响钉）。"""
    td = tmp_path / "td"
    td.mkdir()
    (td / V2_TEMPLATE_FILES["B"]).write_text("DATAROOT_CUSTOM", encoding="utf-8")
    got = _read_v2_card("B", "", str(td))
    assert got == "DATAROOT_CUSTOM"


def test_fallback_package_when_dataroot_missing(tmp_path):
    td = tmp_path / "nonexistent-td"
    got = _read_v2_card("A", "", str(td))
    assert "Translation>" in got
    # 读到的应是包内通用卡（无领域残留的净语卡）
    pkg_text = (PKG_TEMPLATES / V2_TEMPLATE_FILES["A"]).read_text(encoding="utf-8")
    assert got == pkg_text


def test_fallback_all_missing_raises(tmp_path, monkeypatch):
    # monkeypatch 包内目录为空目录，模拟全缺
    empty = tmp_path / "empty-pkg-templates"
    empty.mkdir()
    monkeypatch.setattr(pipeline_v2, "_PKG_TEMPLATES_DIR", str(empty))
    with pytest.raises(Exception) as ei:
        _read_v2_card("A", "", str(tmp_path / "no-td"))
    assert "v2 角色卡缺失" in str(ei.value)


# ---------------------------------------------------------------------------
# 5. hardened 审计表覆盖全部词条
# ---------------------------------------------------------------------------

def _hardened_yaml() -> dict:
    p = resolve_data_file("hardened_phrases.yaml")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def test_hardened_audit_doc_exists():
    assert AUDIT_DOC.is_file(), f"审计表缺失：{AUDIT_DOC}"


def test_hardened_audit_covers_all_keywords_and_patterns():
    data = _hardened_yaml()
    # 文档为 markdown 表格：`\|` 是转义管道，比对前两侧统一去反斜杠
    doc = AUDIT_DOC.read_text(encoding="utf-8").replace("\\", "")
    missing = [w for w in data.get("keywords", []) if w not in doc]
    assert not missing, f"审计表遗漏 keywords：{missing}"
    for pat in data.get("patterns", []):
        plain = pat.replace("\\", "")
        assert plain in doc, f"审计表遗漏 pattern：{pat}"
