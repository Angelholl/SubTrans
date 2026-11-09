"""
闸门0 黄金样本回归集基线统计工具
================================
读 tests/fixtures/hallucination_golden/golden_v1.json，逐条以 default 档
跑 apply_source_filter，机械核对 expected 与实际行为，输出：

1. 每样本判定结果（PASS/FAIL + 期望/实际行为）；
2. 七类别 precision/recall 混淆计数（delete 类以"删除"为预测正例，
   count 类以"检出"为预测正例，keep 样本作为各类别的负例来源）；
3. 末尾打印可复制进决策日志的基线摘要。

real 池（origin="real" 真实语料）走树外载体（案D′，D2026-1109-01）：载体根
解析三段序＝env ``SUBTRANS_GOLDEN_REAL_ROOT`` → 仓根 ``.golden-root`` 指针
（单行绝对路径）→ 两者皆无＝缺席。载体＝``<golden_root>/greal_v1.json`` ＋
``<golden_root>/labels.sha256``。载体缺席＝空池且不抛错（构造池 49 条口径
零漂移）；载体根落在仓库内＝fail-closed 拒绝装载。载体解析与产品数据根
（paths.data_root）刻意解耦：后者同时驱动 runtime/模型/Temp 解析链。

用法：
    python tools/gate0_golden_stats.py
    python tools/gate0_golden_stats.py --json 结果.json   # 另存机器可读结果
    python tools/gate0_golden_stats.py --require-real      # 专用账清偿门（不进 CI）

退出码：脚本正常完成恒为 0（样本 FAIL 不改变退出码，行为一致性由
tests/test_golden_set.py 作为硬守卫钉住）；``--require-real`` 下 real 池缺席
或空池即非零退出。

防循环验证契约：golden_v1.json 的 expected 字段独立于实现代码写就
（先按规则库文档化阈值手工判定，后跑本脚本核对），本脚本只做机械
核对，不反推样本预期。
"""

import json
import os
import shutil
import sys
import tempfile
import types
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from subtrans.refine.source_hallucination import apply_source_filter

# ---------------------------------------------------------------------------
# 口径常量（与 subtrans/refine/source_hallucination.py 的标签映射同源；
# 此处复制而非 import 私有符号，保持脚本对实现的只读独立性）
# ---------------------------------------------------------------------------

DELETE_CATS = ("pure_punctuation", "exclamation", "unpronounceable",
               "repeat_loop", "end_meta")
COUNT_CATS = ("isolated_response", "nonsense_syllables")
ALL_CATS = DELETE_CATS + COUNT_CATS

CATEGORY_LABELS = {
    "pure_punctuation": "纯标点行",
    "exclamation": "!串",
    "unpronounceable": "不可发音辅音串",
    "repeat_loop": "重复循环",
    "end_meta": "片尾元信息",
    "isolated_response": "孤立应答词",
    "nonsense_syllables": "无意义音节连缀",
}

ACTION_WORDS = {"delete": "删除", "count": "计数", "keep": "保留"}

REPO_ROOT = Path(__file__).resolve().parents[1]

GOLDEN_PATH = (Path(__file__).resolve().parents[1] / "tests" / "fixtures"
               / "hallucination_golden" / "golden_v1.json")

# real 池树外载体契约（案D′：载体指针与产品数据根解耦，禁复用 paths.data_root）
GOLDEN_REAL_ENV = "SUBTRANS_GOLDEN_REAL_ROOT"
GOLDEN_REAL_POINTER = ".golden-root"
GOLDEN_REAL_POOL = "greal_v1.json"
GOLDEN_REAL_LABELS = "labels.sha256"


class RealPoolLoadError(RuntimeError):
    """real 池载体配置/结构错误（fail-closed：配置态异常即红非静默空池）。"""


def is_within(path, parent) -> bool:
    """path 是否位于 parent 之下（均为 resolve 后比较）。"""
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def tree_out_violation(root, repo_root=None):
    """树外 fail-closed 判据：载体根落仓库内即返回违规文案，否则 None。"""
    repo_root = REPO_ROOT if repo_root is None else Path(repo_root)
    if root is not None and is_within(root, repo_root):
        return f"real 池载体根位于仓库内（树外 fail-closed）：{root}"
    return None


def resolve_golden_real_root(repo_root=None, environ=None) -> dict:
    """载体根解析三段序：env → 仓根 .golden-root 指针 → 缺席。

    返回 {"root": Path|None, "source": "env"|"pointer"|"absent", "reason"}；
    reason 恒携 source 标签与解析路径（防指针误设/漏设静默看错库）。
    指针须为单行绝对路径；空指针或相对路径＝fail-closed（root=None）。
    """
    repo_root = REPO_ROOT if repo_root is None else Path(repo_root)
    environ = os.environ if environ is None else environ
    env_value = (environ.get(GOLDEN_REAL_ENV) or "").strip()
    pointer = repo_root / GOLDEN_REAL_POINTER
    if env_value:
        root = Path(env_value).expanduser().resolve()
        return {"root": root, "source": "env",
                "reason": f"source=env；路径={root}（{GOLDEN_REAL_ENV}）"}
    if pointer.is_file():
        raw = pointer.read_text(encoding="utf-8").strip()
        if not raw:
            return {"root": None, "source": "pointer",
                    "reason": f"source=pointer；路径={pointer}"
                              "（指针为空，fail-closed）"}
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            return {"root": None, "source": "pointer",
                    "reason": f"source=pointer；路径={pointer}"
                              f"（指向非绝对路径 {raw!r}，fail-closed）"}
        return {"root": candidate.resolve(), "source": "pointer",
                "reason": f"source=pointer；路径={candidate.resolve()}"
                          f"（指针文件 {pointer}）"}
    return {"root": None, "source": "absent",
            "reason": f"source=absent；解析路径=无（env {GOLDEN_REAL_ENV} 未设，"
                      f"仓根指针 {pointer} 不存在）"}


def load_real_pool(repo_root=None, environ=None, resolution=None) -> dict:
    """装载树外 real 池；缺席＝空池不抛错（stats 可继续跑构造池口径）。

    返回 dict：pool/cases/root/source/reason/missing/labels_text/labels_missing
    /pool_path/labels_path。根配置而池文件缺席＝missing=True（reason 携
    source＋路径＋missing）；根落在仓库内或载体非法＝抛 RealPoolLoadError。
    """
    repo_root = REPO_ROOT if repo_root is None else Path(repo_root)
    resolution = resolution or resolve_golden_real_root(repo_root, environ)
    root = resolution["root"]
    loaded = {
        "pool": None, "cases": [], "root": root,
        "source": resolution["source"], "reason": resolution["reason"],
        "missing": True, "labels_text": None, "labels_missing": True,
        "pool_path": None, "labels_path": None,
    }
    if root is None:
        return loaded
    violation = tree_out_violation(root, repo_root)
    if violation:
        raise RealPoolLoadError(violation)
    pool_path = root / GOLDEN_REAL_POOL
    labels_path = root / GOLDEN_REAL_LABELS
    loaded.update({"pool_path": pool_path, "labels_path": labels_path})
    if not pool_path.is_file():
        loaded["reason"] = (f"source={resolution['source']}；路径={root}；"
                            f"missing={GOLDEN_REAL_POOL}（根已配置而池文件缺席）")
        return loaded
    try:
        data = json.loads(pool_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RealPoolLoadError(
            f"real 池载体不可读或非法 JSON：{pool_path}（{exc}）") from exc
    if not isinstance(data, dict):
        raise RealPoolLoadError(f"real 池载体顶层须为对象：{pool_path}")
    cases = data.get("cases")
    if not isinstance(cases, list):
        raise RealPoolLoadError(f"real 池 cases 缺失或非列表：{pool_path}")
    loaded.update({
        "pool": data, "cases": cases, "missing": False,
        "reason": (f"source={resolution['source']}；路径={root}；"
                   f"n={len(cases)}"),
    })
    if labels_path.is_file():
        loaded["labels_text"] = labels_path.read_text(encoding="utf-8")
        loaded["labels_missing"] = False
    return loaded


def n_observations(entry: dict) -> int:
    """该类别实际观测条数（tp+fp+fn）：n=0 时 P/R 的 1.000 无意义。"""
    return entry["tp"] + entry["fp"] + entry["fn"]


def format_category_line(key: str, entry: dict) -> str:
    """类别行：n 展示列；n=0 显式「n=0（不适用）」，不展示分母 0 的假 1.000。"""
    n = n_observations(entry)
    if n == 0:
        return f"{CATEGORY_LABELS[key]:<10} n=0（不适用）"
    return (f"{CATEGORY_LABELS[key]:<10} n={n} TP={entry['tp']} FP={entry['fp']} "
            f"FN={entry['fn']}  precision={entry['precision']:.3f} "
            f"recall={entry['recall']:.3f}")



def load_golden(path=None) -> dict:
    """读黄金样本集（缺省走仓库内置路径）。"""
    p = Path(path) if path else GOLDEN_PATH
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data.get("cases"), list) or not data["cases"]:
        raise SystemExit(f"黄金样本集损坏（无 cases）: {p}")
    return data


def _timing(sec: int) -> str:
    """条目时间轴：起始 sec 秒、时长 1 秒（间隔 20s 避免跨条目干扰）。"""
    m1, s1 = divmod(sec, 60)
    m2, s2 = divmod(sec + 1, 60)
    return (f"00:{m1:02d}:{s1:02d},000 --> "
            f"00:{m2:02d}:{s2:02d},000")


def build_entries(case: dict) -> tuple:
    """按样本构造条目序列，返回 (entries, focus_index)。

    条目 = context（focus 前）+ focus + context_after（focus 后）；
    时间轴按每条 20s 间隔生成，样本带 timing 时覆盖 focus 的时间轴。
    """
    before = list(case.get("context") or [])
    after = list(case.get("context_after") or [])
    texts = before + [case["text"]] + after
    entries = [{"index": i + 1, "timing": _timing(20 * i), "text": t}
               for i, t in enumerate(texts)]
    if case.get("timing"):
        entries[len(before)]["timing"] = case["timing"]
    return entries, len(before) + 1     # 条目编号从 1 起，focus 恒存在


def run_case(case: dict, errors_dir: str = None) -> dict:
    """以 default 档跑单条样本，机械核对期望与实际。

    判定口径：
    - delete：focus 被删除，且期望类别的删除计数 ≥1；
    - count：focus 保留在主稿，且期望类别的检出计数 ≥1；
    - keep：focus 保留在主稿，且全文件零检出（负样本硬口径）。
    """
    if errors_dir is None:
        errors_dir = tempfile.mkdtemp(prefix="gate0_golden_")
    entries, focus_index = build_entries(case)
    cfg = types.SimpleNamespace(v2_source_filter="default",
                                v2_source_filter_valve_pct=50)
    # 静默运行：逐条结果以返回值呈现，避免检测器的过程输出刷屏
    with redirect_stdout(StringIO()):
        kept, stats = apply_source_filter(entries, cfg,
                                          errors_dir=errors_dir)
    kept_indexes = {e["index"] for e in kept}
    deleted = focus_index not in kept_indexes
    expected_cat = case.get("expected_category")
    expected_action = case.get("expected_action")
    label = CATEGORY_LABELS.get(expected_cat) if expected_cat else None

    ok = True
    detail = ""
    if expected_action == "delete":
        cat_deleted = stats["categories"][label]["deleted"] if label else 0
        if not deleted or cat_deleted < 1:
            ok = False
            detail = (f"期望删除（{label}），实际"
                      f"{'已删除' if deleted else '未删除'}"
                      f"/该类删除计数 {cat_deleted}")
    elif expected_action == "count":
        cat_detected = stats["categories"][label]["detected"] if label else 0
        if deleted or cat_detected < 1:
            ok = False
            detail = (f"期望计数保留（{label}，检出≥1），实际"
                      f"{'被删除' if deleted else '保留'}"
                      f"/该类检出 {cat_detected}")
    elif expected_action == "keep":
        if deleted or stats.get("detected_total", 0) != 0:
            ok = False
            detail = (f"期望零检出保留，实际"
                      f"{'被删除' if deleted else '保留'}"
                      f"/全文件检出 {stats.get('detected_total', 0)}")
    else:
        ok = False
        detail = f"未知期望行为: {expected_action!r}"

    # 检测器在本样本上的"类别活跃度"（供混淆计数）：delete 类看删除、
    # count 类看检出。样本构造保证 context 不引入无关检出。
    predicted = set()
    for key in DELETE_CATS:
        if stats["categories"][CATEGORY_LABELS[key]]["deleted"] > 0:
            predicted.add(key)
    for key in COUNT_CATS:
        if stats["categories"][CATEGORY_LABELS[key]]["detected"] > 0:
            predicted.add(key)

    return {
        "id": case["id"],
        "expected_category": expected_cat,
        "expected_action": expected_action,
        "deleted": deleted,
        "detected_total": stats.get("detected_total", 0),
        "predicted": sorted(predicted),
        "ok": ok,
        "detail": detail,
    }


def confusion_matrix(golden: dict, results: list) -> dict:
    """七类别混淆计数（以样本为观测单位）：

    TP=预测为该类且期望为该类；FP=预测为该类但期望非该类（含负样本）；
    FN=期望为该类但未预测到。precision=TP/(TP+FP)、recall=TP/(TP+FN)，
    分母为 0 时记 1.000（该类无任何观测，视为无退化）。
    """
    by_id = {r["id"]: r for r in results}
    matrix = {}
    for key in ALL_CATS:
        tp = fp = fn = 0
        for case in golden["cases"]:
            r = by_id.get(case["id"])
            if r is None:      # 分池装载（real 独立跑）时按 by_id 取数，防 KeyError
                continue
            hit = key in r["predicted"]
            expected = (case.get("expected_category") == key)
            if hit and expected:
                tp += 1
            elif hit and not expected:
                fp += 1
            elif expected and not hit:
                fn += 1
        precision = tp / (tp + fp) if (tp + fp) else 1.0
        recall = tp / (tp + fn) if (tp + fn) else 1.0
        matrix[key] = {"tp": tp, "fp": fp, "fn": fn,
                       "precision": round(precision, 3),
                       "recall": round(recall, 3)}
    return matrix


def main() -> int:
    # Windows 控制台默认非 UTF-8 编码，摘要含中文/emoji，稳妥起见重配置
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    golden = load_golden()
    tmp = tempfile.mkdtemp(prefix="gate0_golden_")
    try:
        results = [run_case(case, errors_dir=tmp)
                   for case in golden["cases"]]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    n_pass = sum(1 for r in results if r["ok"])
    print("=" * 64)
    print(f"闸门0 黄金样本回归集 v{golden.get('version')}："
          f"共 {len(results)} 条，PASS {n_pass} / FAIL {len(results) - n_pass}")
    print("=" * 64)
    print("-- 逐条判定 --")
    for r in results:
        mark = "PASS" if r["ok"] else "FAIL"
        word = ACTION_WORDS.get(r["expected_action"],
                                r["expected_action"])
        cat = r["expected_category"] or "-"
        line = f"[{mark}] {r['id']}  期望={word}/{cat}"
        if not r["ok"]:
            line += f"  {r['detail']}"
        print(line)

    matrix = confusion_matrix(golden, results)
    print("-- 类别 precision/recall（delete=删除为正例，count=检出为正例）--")
    for key in ALL_CATS:
        m = matrix[key]
        print(f"{CATEGORY_LABELS[key]:<10} TP={m['tp']} FP={m['fp']} "
              f"FN={m['fn']}  precision={m['precision']:.3f} "
              f"recall={m['recall']:.3f}")

    # real 池走树外载体（案D′）：与构造池双 dict 分离，不合并后直调共享函数。
    # 载体缺席态（source=absent）打印旧行以守住「与 HEAD 现值逐字节一致」验收
    # 等价钉；载体配置态输出构造池/real 分池摘要与 n 展示列。
    try:
        real = load_real_pool()
    except RealPoolLoadError as exc:
        print(f"[real 池] 载体配置异常（fail-closed）：{exc}", file=sys.stderr)
        return 2
    if real["source"] == "absent":
        print("-- origin=real 真实子集分项 --")
        print("origin=real 真实子集：0 条（工具面就绪，待真实语料标注）")
    else:
        print("-- 分池摘要（构造池 / real 池）--")
        print(f"构造池（origin=constructed）：共 {len(golden['cases'])} 条"
              f"（PASS {n_pass} / FAIL {len(results) - n_pass}）")
        if real["missing"] or not real["cases"]:
            print(f"real 池：缺席（{real['reason']}）")
        else:
            real_cases = real["cases"]
            tmp_real = tempfile.mkdtemp(prefix="gate0_golden_real_")
            try:
                real_results = [run_case(case, errors_dir=tmp_real)
                                for case in real_cases]
            finally:
                shutil.rmtree(tmp_real, ignore_errors=True)
            matrix_real = confusion_matrix({"cases": real_cases}, real_results)
            n_real_pass = sum(1 for r in real_results if r["ok"])
            n_real = {"delete": 0, "count": 0, "keep": 0}
            debt = {"d0926": 0, "3.3.0": 0}
            for case in real_cases:
                action = case.get("expected_action")
                if action in n_real:
                    n_real[action] += 1
                if case.get("debt_scope") in debt:
                    debt[case["debt_scope"]] += 1
            print(f"real 池（origin=real，树外载体）：共 {len(real_cases)} 条"
                  f"（delete {n_real['delete']} / count {n_real['count']}"
                  f" / keep {n_real['keep']}），"
                  f"行为一致 {n_real_pass}/{len(real_cases)}")
            print(f"real 池载体：source={real['source']}；路径={real['root']}")
            print(f"real 池 debt_scope 分列：d0926={debt['d0926']}；"
                  f"3.3.0={debt['3.3.0']}（两债分别记账、分别验收，"
                  "本账不替代、不折抵 D2026-0926-01）")
            print("real 池口径：用于债计量读数，不自动充当门值标定件"
                  "（门值标定须另取独立于债的标注件；单管线偏置防同源循环）")
            if len(real_cases) < 30:
                print(f"real 池计数门：{len(real_cases)} < 30，"
                      "专用账未清偿（保持挂账，不以备材充数）")
            for key in ALL_CATS:
                print(format_category_line(key, matrix_real[key]))

    macro_p = sum(m["precision"] for m in matrix.values()) / len(matrix)
    macro_r = sum(m["recall"] for m in matrix.values()) / len(matrix)
    n_delete = sum(1 for c in golden["cases"]
                   if c["expected_action"] == "delete")
    n_count = sum(1 for c in golden["cases"]
                  if c["expected_action"] == "count")
    n_keep = sum(1 for c in golden["cases"]
                 if c["expected_action"] == "keep")
    print("-- 基线摘要（可复制进决策日志）--")
    print(f"golden_v{golden.get('version')} 样本 {len(results)} 条"
          f"（delete {n_delete} / count {n_count} / keep {n_keep}），"
          f"行为一致 {n_pass}/{len(results)}；"
          f"七类别宏平均 precision={macro_p:.3f} recall={macro_r:.3f}")
    print("类别明细："
          + "；".join(f"{CATEGORY_LABELS[k]}"
                      f"P={matrix[k]['precision']:.3f}"
                      f"/R={matrix[k]['recall']:.3f}" for k in ALL_CATS))

    args = sys.argv[1:]
    require_real = "--require-real" in args
    json_out = None
    if "--json" in args:
        idx = args.index("--json")
        if idx + 1 < len(args):
            json_out = args[idx + 1]
    if json_out:
        out = {"version": golden.get("version"),
               "pass": n_pass, "fail": len(results) - n_pass,
               "cases": results, "confusion": matrix}
        Path(json_out).write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"结果已落盘: {json_out}")

    # 专用账清偿门（只进债清偿验收命令，不进 CI）：real 池缺席/空池即非零退出。
    if require_real:
        if real["source"] == "absent" or real["missing"] or not real["cases"]:
            print(f"[清偿门] real 池不可用：{real['reason']}", file=sys.stderr)
            return 2
        print(f"[清偿门] real 池可用：{len(real['cases'])} 条"
              f"（source={real['source']}；路径={real['root']}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
