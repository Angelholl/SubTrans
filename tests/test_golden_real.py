"""real 语料池守卫（案D′：树外载体外挂，D2026-1109-01 认账批准）。

real 池整体外挂树外载体，不进公开仓 tracked 面；本文件把载体契约钉死：

- 载体根解析三段序：env ``SUBTRANS_GOLDEN_REAL_ROOT`` → 仓根 ``.golden-root``
  指针（单行绝对路径）→ 两者皆无＝skip（reason 必携 ``source=absent``）；
- 载体＝``<golden_root>/greal_v1.json`` ＋ ``<golden_root>/labels.sha256``：
  根已配置而池文件缺席＝skip（reason 携 source＋路径＋missing）；
  载体在而封存件缺席＝红（fail-closed，禁只拷 greal 不拷封存件）；
- 树外 fail-closed：解析结果落在仓库内即红非 skip；
- 文件存在即 cases 非空（禁空骨架放行）；每条 real 须过 origin/采集来源/
  签署人/debt_scope/runner 输入契约；合并池 id 全局唯一、跨集文本零撞；
- 封存哈希＋可读计数快照（``REAL_POOL``）与载体三向对账，失配即红。

``REAL_POOL`` 是 tracked 常量：常量变更须同批 decision-log 条目＋commit 正文
``Refs:``。载体缺席态不在 CI 失败（skip），存在态由 neg 矩阵承载先红后绿。

合成夹具一律 ``demo@sample-NNN`` 口径（禁真实片名/站名格式）。
"""

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import gate0_golden_stats as gs  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "hallucination_golden"

ACTIONS = ("delete", "count", "keep")
DEBT_SCOPES = ("d0926", "3.3.0")

# tracked 常量：封存哈希＋可读计数快照（计数进 diff，漂移肉眼可辨）。
# labels_sha256=None／n=0 系「专用账未清偿」态：载体一旦落盘即 fail-closed 红，
# 须同批补常量（decision-log hash＋提交正文 Refs 回链）。
REAL_POOL = {
    "version": "1.0",
    "pool_id": "greal_v1",
    "labels_sha256": None,
    "n": 0,
    "debt_scope": {"d0926": 0, "3.3.0": 0},
}


# ---------------------------------------------------------------------------
# 合成载体（demo@sample-NNN 口径；负例矩阵全部在此构造）
# ---------------------------------------------------------------------------

def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _case(case_id="demo@sample-001", text="demo synthetic line",
          action="delete", category="pure_punctuation", debt="d0926"):
    return {
        "id": case_id,
        "text": text,
        "expected_action": action,
        "expected_category": category,
        "origin": "real",
        "source_file": "demo@sample-001.srt",
        "time_range": "00:00:01,000-00:00:03,000",
        "generated_by": "demo-pipeline batch1",
        "annotator": "demo-annotator-01",
        "debt_scope": debt,
    }


def _synthetic_carrier(cases=None):
    """返回 (pool, labels_text, expected_snapshot)，三者自洽可过全部契约。"""
    digest = _sha("demo@labels-v1")
    cases = [_case()] if cases is None else cases
    pool = {
        "version": "1.0",
        "pool_id": "greal_v1",
        "judgment_package_sha256": digest,
        "signers": ["demo-annotator-01"],
        "cases": cases,
    }
    debt = {"d0926": 0, "3.3.0": 0}
    for case in cases:
        if case.get("debt_scope") in debt:
            debt[case["debt_scope"]] += 1
    expected = {
        "version": "1.0",
        "pool_id": "greal_v1",
        "labels_sha256": digest,
        "n": len(cases),
        "debt_scope": debt,
    }
    return pool, digest + "\n", expected


def _write_carrier(root: Path, pool: dict, labels_text: str = None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / gs.GOLDEN_REAL_POOL).write_text(
        json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")
    if labels_text is not None:
        (root / gs.GOLDEN_REAL_LABELS).write_text(labels_text, encoding="utf-8")


def _normalized(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _tracked_cases(name: str) -> list:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))["cases"]


def validate_real_pool(pool, labels_text, *, expected=None,
                       constructed_cases=None, semantic_cases=None,
                       antonym_cases=None) -> list:
    """返回违规清单；空清单＝全契约通过。所有检查 fail-closed。"""
    expected = REAL_POOL if expected is None else expected
    constructed_cases = constructed_cases or []
    semantic_cases = semantic_cases or []
    antonym_cases = antonym_cases or []
    violations = []

    labels_hash = None
    if labels_text is None:
        violations.append("封存件 labels.sha256 缺席（fail-closed：禁只拷 greal 不拷封存件）")
    else:
        stripped = labels_text.strip()
        labels_hash = stripped.split()[0] if stripped else ""
        if not labels_hash:
            violations.append("封存件 labels.sha256 为空（fail-closed）")
            labels_hash = None

    cases = pool.get("cases") if isinstance(pool, dict) else None
    if not isinstance(cases, list) or not cases:
        violations.append("real 池空池：cases 缺失或为空（禁空骨架放行，守卫永久空转）")
        cases = []

    if pool.get("version") != expected.get("version"):
        violations.append(
            f"real 池 version 失配：载体 {pool.get('version')!r} ≠ 常量 {expected.get('version')!r}")
    if pool.get("pool_id") != expected.get("pool_id"):
        violations.append(
            f"real 池 pool_id 失配：载体 {pool.get('pool_id')!r} ≠ 常量 {expected.get('pool_id')!r}")

    signers = pool.get("signers")
    if not isinstance(signers, list) or not signers:
        violations.append("real 池缺 signers 签署人集合（annotator 对账无依据）")
        signers = []

    seal = pool.get("judgment_package_sha256")
    if labels_hash and seal != labels_hash:
        violations.append(
            f"自校验失配：judgment_package_sha256 {seal!r} ≠ labels.sha256 {labels_hash!r}")
    if expected.get("labels_sha256") is None:
        violations.append("tracked REAL_POOL.labels_sha256 未登记（封存哈希未入常量，fail-closed）")
    elif labels_hash and labels_hash != expected["labels_sha256"]:
        violations.append(
            f"封存哈希失配：labels.sha256 {labels_hash!r} ≠ 常量 {expected['labels_sha256']!r}")

    ids = [c.get("id") for c in constructed_cases]
    ids += [c.get("id") for c in cases]
    dup_ids = {i for i in ids if i and ids.count(i) > 1}
    if dup_ids:
        violations.append(f"合并池 id 撞车（runner by_id 静默塌缩防线）：{sorted(dup_ids)}")

    blocked = {_normalized(c.get("text")) for c in constructed_cases}
    blocked |= {_normalized(c.get("source")) for c in semantic_cases}
    blocked |= {_normalized(c.get("source")) for c in antonym_cases}
    blocked.discard("")

    for case in cases:
        cid = case.get("id") or "<无 id>"
        if not case.get("id"):
            violations.append(f"{cid}：id 缺失")
        if case.get("origin") != "real":
            violations.append(f"{cid}：origin={case.get('origin')!r} 非 \"real\"")
        for key in ("source_file", "time_range", "generated_by"):
            if not _normalized(case.get(key)):
                violations.append(f"{cid}：采集来源缺 {key}（源文件/时间段/管线批次必填）")
        if signers and case.get("annotator") not in signers:
            violations.append(
                f"{cid}：annotator={case.get('annotator')!r} 不在封存签署人集合")
        if case.get("debt_scope") not in DEBT_SCOPES:
            violations.append(f"{cid}：debt_scope={case.get('debt_scope')!r} 不在 {DEBT_SCOPES}")
        if case.get("expected_action") not in ACTIONS:
            violations.append(
                f"{cid}：expected_action={case.get('expected_action')!r} 不在 {ACTIONS}")
        cat = case.get("expected_category")
        if cat is not None and cat not in gs.ALL_CATS:
            violations.append(f"{cid}：expected_category={cat!r} 不在七类别")
        if not _normalized(case.get("text")):
            violations.append(f"{cid}：text 为空")
        text = _normalized(case.get("text"))
        if text and text in blocked:
            violations.append(f"{cid}：跨集文本撞车（与 tracked 集归一化后重复）")

    if expected.get("n") != len(cases):
        violations.append(f"计数快照失配：常量 n={expected.get('n')} ≠ 载体 {len(cases)} 条")
    actual_debt = {scope: 0 for scope in DEBT_SCOPES}
    for case in cases:
        if case.get("debt_scope") in actual_debt:
            actual_debt[case["debt_scope"]] += 1
    if expected.get("debt_scope") != actual_debt:
        violations.append(
            f"debt_scope 分列失配：常量 {expected.get('debt_scope')} ≠ 载体 {actual_debt}")
    return violations


@pytest.fixture(scope="module")
def carrier():
    """真实载体（缺席＝skip 且 reason 携 source/路径；根已配置而读取失败＝红）。"""
    loaded = gs.load_real_pool(REPO_ROOT)
    if loaded["missing"]:
        if loaded["source"] == "absent":
            pytest.skip(f"real 池载体缺席，按卡面 skip（{loaded['reason']}）")
        pytest.fail(f"real 池载体配置异常（{loaded['reason']}）")
    return loaded


def test_real_pool_is_tree_external(carrier):
    """树外 fail-closed：解析出的载体根不得位于仓库内。"""
    violation = gs.tree_out_violation(carrier["root"], REPO_ROOT)
    assert violation is None, violation


def test_real_pool_contract(carrier):
    """存在态全契约：origin/来源/签署人/debt_scope/去重/封存哈希/计数快照。"""
    violations = validate_real_pool(
        carrier["pool"], carrier["labels_text"],
        constructed_cases=_tracked_cases("golden_v1.json"),
        semantic_cases=_tracked_cases("semantic_v1.json"),
        antonym_cases=_tracked_cases("antonym_v1.json"))
    assert not violations, "；".join(violations)


def test_real_pool_resolution_absent_carries_source_and_path(tmp_path):
    """两者皆无＝skip 态：source=absent 且 reason 携解析路径（防漏设静默看错库）。"""
    loaded = gs.load_real_pool(repo_root=tmp_path, environ={})
    assert loaded["missing"] is True
    assert loaded["source"] == "absent"
    assert "source=absent" in loaded["reason"]
    assert "路径=" in loaded["reason"]


def test_real_pool_resolution_env_precedes_pointer(tmp_path):
    """解析序 env > 指针：两者同设时 env 生效。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    env_root = tmp_path / "env-golden"
    (repo / gs.GOLDEN_REAL_POINTER).write_text(
        str(tmp_path / "pointer-golden"), encoding="utf-8")
    resolved = gs.resolve_golden_real_root(
        repo_root=repo, environ={gs.GOLDEN_REAL_ENV: str(env_root)})
    assert resolved["source"] == "env"
    assert resolved["root"] == env_root.resolve()


# ---------------------------------------------------------------------------
# 存在态红/绿负例矩阵（合成载体，CI 可跑；每负例一条测试）
# ---------------------------------------------------------------------------

def test_negative_origin_not_real_red():
    pool, labels, expected = _synthetic_carrier()
    pool["cases"][0]["origin"] = "constructed"
    violations = validate_real_pool(pool, labels, expected=expected)
    assert any("origin" in v for v in violations), violations


def test_negative_empty_pool_red():
    pool, labels, expected = _synthetic_carrier(cases=[])
    violations = validate_real_pool(pool, labels, expected=expected)
    assert any("空池" in v for v in violations), violations


def test_negative_missing_provenance_red():
    for key in ("source_file", "time_range", "generated_by"):
        pool, labels, expected = _synthetic_carrier()
        pool["cases"][0].pop(key)
        violations = validate_real_pool(pool, labels, expected=expected)
        assert any(key in v for v in violations), (key, violations)


def test_negative_annotator_not_in_signers_red():
    pool, labels, expected = _synthetic_carrier()
    pool["cases"][0]["annotator"] = "demo-annotator-99"
    violations = validate_real_pool(pool, labels, expected=expected)
    assert any("annotator" in v for v in violations), violations


def test_negative_carrier_without_labels_red(tmp_path):
    """载体在而封存件缺席＝红（同时验证 loader 的 labels_missing 标记）。"""
    pool, _, expected = _synthetic_carrier()
    root = tmp_path / "golden-root"
    _write_carrier(root, pool, labels_text=None)
    loaded = gs.load_real_pool(
        repo_root=tmp_path / "repo",
        environ={gs.GOLDEN_REAL_ENV: str(root)})
    assert loaded["missing"] is False
    assert loaded["labels_missing"] is True
    violations = validate_real_pool(loaded["pool"], loaded["labels_text"],
                                    expected=expected)
    assert any("labels.sha256" in v for v in violations), violations


def test_negative_cross_set_text_collision_red():
    pool, labels, expected = _synthetic_carrier()
    text = pool["cases"][0]["text"]
    violations = validate_real_pool(
        pool, labels, expected=expected,
        constructed_cases=[{"id": "demo@constructed-001", "text": f"  {text}  "}],
        semantic_cases=[{"id": "demo@semantic-001", "source": text}])
    assert any("跨集文本撞车" in v for v in violations), violations


def test_negative_id_collision_red():
    pool, labels, expected = _synthetic_carrier()
    case_id = pool["cases"][0]["id"]
    violations = validate_real_pool(
        pool, labels, expected=expected,
        constructed_cases=[{"id": case_id, "text": "demo other line"}])
    assert any("id 撞车" in v for v in violations), violations


def test_negative_n_zero_prints_not_applicable():
    """n=0 类显式打印「n=0（不适用）」，禁分母 0 → 1.000 假数据。"""
    empty = {"tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0}
    for key in gs.ALL_CATS:
        line = gs.format_category_line(key, empty)
        assert "n=0（不适用）" in line, line
        assert "1.000" not in line, line
    one = {"tp": 1, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0}
    assert "n=1" in gs.format_category_line(gs.ALL_CATS[0], one)


def test_negative_golden_root_inside_repo_red(tmp_path):
    """树外判据违例（resolve 落 REPO_ROOT 下）＝红，loader 拒绝装载。"""
    repo = tmp_path / "repo"
    inside = repo / "golden"
    pool, labels, _ = _synthetic_carrier()
    _write_carrier(inside, pool, labels)
    resolved = gs.resolve_golden_real_root(
        repo_root=repo, environ={gs.GOLDEN_REAL_ENV: str(inside)})
    assert gs.tree_out_violation(resolved["root"], repo) is not None
    with pytest.raises(gs.RealPoolLoadError):
        gs.load_real_pool(repo_root=repo,
                          environ={gs.GOLDEN_REAL_ENV: str(inside)})


def test_negative_resolution_reason_missing_source_or_path_red(tmp_path):
    """三种解析态 reason 必携 source 标签与路径（含指针空/非绝对路径 fail-closed）。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    absent = gs.resolve_golden_real_root(repo_root=repo, environ={})
    env = gs.resolve_golden_real_root(
        repo_root=repo, environ={gs.GOLDEN_REAL_ENV: str(tmp_path / "env-golden")})
    (repo / gs.GOLDEN_REAL_POINTER).write_text(str(tmp_path / "ptr-golden"),
                                                encoding="utf-8")
    pointer = gs.resolve_golden_real_root(repo_root=repo, environ={})
    for resolved, tag in ((absent, "absent"), (env, "env"), (pointer, "pointer")):
        assert resolved["source"] == tag
        assert f"source={tag}" in resolved["reason"]
        assert "路径=" in resolved["reason"]

    (repo / gs.GOLDEN_REAL_POINTER).write_text("relative/path", encoding="utf-8")
    broken = gs.resolve_golden_real_root(repo_root=repo, environ={})
    assert broken["root"] is None and broken["source"] == "pointer"
    assert "路径=" in broken["reason"]


def test_negative_runner_input_contract_red():
    """runner 输入契约：expected_action/expected_category/text 缺失即红。"""
    probes = (
        ("expected_action", "demo-action"),
        ("expected_category", "demo-category"),
        ("text", ""),
    )
    for key, bad in probes:
        pool, labels, expected = _synthetic_carrier()
        pool["cases"][0][key] = bad
        violations = validate_real_pool(pool, labels, expected=expected)
        assert any(key in v for v in violations), (key, violations)
