# impl-card-audit-runtime.md — 审计运行时实现卡（治理轮 2026-10-22）

定性：**规则层验收通过；运行时层未交付。** 本卡是运行时层的唯一待办出处；本卡本身不构成验收，不得据本卡写"已止住循环"或"运行时生效"。

本轮（2026-10-22）收口定性：**文档层冻结；① 暴露面已按 owner 条件判（低敏感→接受现状，① 维持 closed）；运行时最小版已跑通一次真实扫描**——统计落盘与正式输出目录仍未交付。

以下命令均在项目根目录执行。

## 卡面（自足）

- 只改：运行时脚本、其输出目录、本地安全源。不改三份治理文件、不改 decision-log、不动归档卷。
- 执行者只 commit，不 push；第 6 项（脚本注释勘正）须走 owner 门，不得自行改。
- 卡面不含根路径字面量，不含旧品牌词字面量，不含敏感原值。

## 交付项

1. **脚本读 map**：读取 `docs/governance/closure-map.yaml` 的 `entries`（正式）与 `provisional`（临时）两个区，按 audit-filter-rules §2 `zones` 标记条目区属；provisional 条目只出占位行"临时条目，待归档，见 {canonical_id}"。
2. **按 disposition 输出**：实现 §2 disposition 表全部 9 键（含 `closed_and_optional_no_action` 复合分支，① 先例）＋ `similarity_action` / `unmapped_action` / `next_review_guard`；输出串与 §1、§3 逐字一致，不得只改文档不改可加载配置。
3. **统计字段落盘**：§2 `statistics_fields` 十字段按 §4 基线口径落盘（`statistics_scope: entries_only`，provisional 不进入任一字段）。落盘文件即"可复核"的唯一凭据；落盘前不得称可复核。
4. **输出目录新建**：输出目录当前不存在（脚本纯 stdout、无输出目录参数），须由本卡新建；路径与命名由 owner 定（建议与本地安全源同级，不入公开仓库）。规则配置不得假设输出目录存在。
5. **敏感关键词本地安全源**（本轮未建，规格定死如下）：
   - 位置：`%USERPROFILE%\.zcode\tools\governance-secret-keywords.json`（该目录独立 git 版本化，不属项目仓库；本卡不写用户名字面量）。
   - 维护人：owner（主审）；写入走 config-write 域，须 owner 门。
   - 不入仓库保证：项目仓库侧 `.gitignore` 排除任何本地源副本＋pre-commit 钩子对 `docs/governance/` 扫描敏感原值（命中即拒提交）。两者本轮均未建立，属本卡后续交付。
   - 匹配方式：运行时对命中文本做规范化（小写＋正斜杠）后比对 sha256 前 8 位。本轮已登记占位：`hash:92c47020`（用户名类）、`hash:9540b882`（本地绝对路径类）。威胁模型边界见 audit-filter-rules §0 第 5 条（防明文误 grep 与意外扩散，不抗字典反查，不含主动攻击者）。
6. **②-conflict 脚本注释勘正走 owner 门**：脚本 docstring/help 写"owner 2026-10-20 令：检索类计入判定面"，与 decision-log:141「待 owner」冲突（②-conflict 条目，硬冲突已登记不自动裁决）。勘正须走 owner 门＋单列卡（脚本属本地工具目录写入，走 config-write）；本卡不得自行改注释，也不得引脚本 docstring 作证据。

## 首次真实扫描基线，2026-10-22

- 脚本：`%TEMP%\stj_governance_scan_min.py`（本轮在系统临时目录，未入仓库；第 4 项"输出目录新建"未执行）
- 输入：`audit_dispatch_compliance.py` 的真实输出，只读跑一次，落 `%TEMP%\audit_real_output_20261022.txt`（15 行，数据源为 hooks-log）
- 命令（以下命令均在项目根目录执行）：`python %TEMP%\stj_governance_scan_min.py %TEMP%\audit_real_output_20261022.txt`
- 十个统计字段：raw_hits 15 / dedup_hits 2 / closed_cited 1 / pending 1 / observation_due 0 / open 0 / conflicts 0 / evidence_gaps 0 / similarity_pending 0 / unclassified 1
- 对账：15 = 2 ＋ 1 ＋ 12（12 行为同 ID 重复命中，按去重不入统计字段）
- 命中条目：D2026-1020-07（closed → 只出引用行）、D2026-1022-02②（已拍板 → 不再重问）
- 与 §4 基线的差异：§4 是映射表的静态 status 分布（量纲＝条目数），本轮是单次扫描的动态结果（量纲＝命中行数），两者不可互推；本轮 10 字段中 7 项为 0，因为输入面（派卡审计输出）不含 closed/观察/冲突类命中，只出现 ② 与 1020-07 两个口径词——不得据此写"循环已止住"。
- 本轮实现选定的口径（须与 §1 一致）：raw_hits 按输入行计（每行最多一次判定）；相似匹配用 difflib 比率 ≥0.6 作最小实现；② 的"已拍板"由脚本侧 RULED 登记表实现（map 不扩字段）；provisional 去重仍适用（`seen.add` 在分区判定之前）。
- 敏感关键词未加载，本轮不计（map 内 `hash:` 占位 3 处）。
- 解析失败即报错退出已实测：构造畸形 map 与缺 map 两种情形均 `exit=1`，无静默降级。
- 残余指针分支（closed 且 optional_no_action）：基线输入面未命中，当时标"未验证分支"，不计入验收通过项。2026-10-22 补跑验证通过——输入面＝decision-log ① 段（tip 树 `git grep` 输出经 stdin），命中关键词 `fd87e1d`，输出行与 §1.4／§3 逐字一致："已收口，见 D2026-1022-02①；残余可选决策见 D2026-1022-02①-residual，默认不动"。补跑单列，不计入基线数字（补跑统计 raw_hits 1 / dedup_hits 1 / closed_cited 1 / 其余 0）。

## 验收

- 规则层：三份文件口径一致；closure-map 可被 YAML 解析（本轮实测 `yaml.safe_load` 通过）。附带勘正：原第 106 行 `notes` 值以 ASCII 双引号开头致整文件不可解析，已改为引号包裹＋内部全角引号——运行时实现须以可解析为前提。
- 运行时：最小版已跑通一次（上一节即凭据），但统计未落盘、正式输出目录未建、本地安全源未建——§4"统计数字可复核"仍标未满足，须待落盘后勾账。在此之前本轮交付定性保持"规则层验收通过；运行时层未交付"（最小版跑通 ≠ 运行时层交付完成）。

## 附录 A：可追溯性（首次基线须可复现）

- 脚本（本轮在系统临时目录，未入仓库）：`%TEMP%\stj_governance_scan_min.py`，sha256 `baf46980081d5b80775c74b5a4e6e853f0d0f0e184bf9760c012e5c51494f99c`（7256B／184 行）
- 输入样本：`%TEMP%\audit_real_output_20261022.txt`，sha256 `0df6b9a48d90ba8465970e49b1e963a515aa8ad01f7ec0f6fe6a9550ceabdf3b`（1636B／15 行）
- 可复现命令（以下命令均在项目根目录执行）：`python %TEMP%\stj_governance_scan_min.py %TEMP%\audit_real_output_20261022.txt`
- 附录 B 为脚本全文副本。若临时目录被清，按附录 B 重建后重算 sha256，须与上面记录值一致；不一致即"首次基线不可复现"，须如实报告，不得默认通过。
- 正式版迁移去向（未执行）：受控持久位置由 owner 定（建议与本地安全源同级，不入公开仓库）。迁移完成前，本卡附录 A＋B 是首次基线的唯一凭据。

## 执行记录（2026-10-22 收口轮，A1/A2/A3）

- **A1 迁移已执行**：脚本与输入样本自 %TEMP% 逐字节迁入受控位置 `~/.zcode/governance/scan-min/`（脚本 sha256 迁移时与附录 A 记录值一致 `baf46980…`，输入样本 `0df6b9a4…`）；%TEMP% 副本已清空；清空后从受控位置复跑基线，十字段与首次基线逐字段一致（15/2/1/1/0/0/0/0/0/1，对账 15=2+1+12）。脚本不依赖 %TEMP%（输入经 argv）。
- **A2 三项已建**：①统计落盘——实跑输出写入受控位置 `output/stats-YYYYMMDD.json`，十字段与 §2 statistics_fields 逐字一致；②正式输出目录——受控位置下 `output/`（规则配置不假设 `~/.zcode/audit`）；③本地安全源——`~/.zcode/tools/governance-secret-keywords.json`（本卡第 5 项定死路径，与受控位置同处 `~/.zcode` 下），存两占位对应原值（`92c47020`／`9540b882`），运行时动态加载并对命中文本规范化后比对 sha256 前 8 位，逐条核验通过。维护方式：owner（主审），写入走 config-write 域须 owner 门；不入仓库——项目侧 `.gitignore` 防御条目已加（`governance/scan-min/`、`governance-secret-keywords.json`），`git check-ignore` 实测命中、治理文件本体不被忽略。
- **扩展版脚本**（受控位置，含安全源加载＋哈希前缀比对＋统计落盘＋未分类显式 emit）：sha256 `1e3fa9de1a782e04d094f8bdb2a2d87a377b3f65c49c13261875add33a38e04e`；基线输入复跑十字段不变（基线输入不含敏感原值，加载安全源不改变判定）。
- **A3 换输入面实跑**：输入面＝旧词（清史/在途/维护/观察/待 owner 令/等执行/等令/无回音/挂账）对归档卷＋decision-log＋design 文档的 grep（236 行，落受控位置 `inputs/a3_grep_20261022.txt`）。结果：closed_cited 11（只出引用行、无待办、无重复展开）、open 0、similarity_pending 0（单列）、pending 1（②每轮一次＋已拍板结论）、provisional 只出占位行（GOV-P-02/03）、closed_observation 未到期不出账（observation_due 0）、未分类 63 逐条处置见 `output/a3-unclassified-handling-20261022.md`（62 行触发词＝叙述词"观察"非任何条目关键词；1 行"待 owner 令"仅为 ① 关键词字面片段）。
- 遗留：B1（脚本注释勘正）与 B2（②状态转 closed＋provisional 三条移入＋entry_count 更新）属 owner 门，本轮仅呈请未执行。→ B2 执行轮已执行（见下节），本行保留作过程账。

## 执行记录（B2 执行轮，2026-10-22，承 D2026-1022-03）

- **B1 已执行（config-write owner 门＋单列卡）**：两行勘正（卡 d1022-B1-脚本注释勘正卡.md，含改前/改后两行＋哈希）；tools git 基线提交 67c572f＋勘正提交 6d05695，回滚路径＝单文件 `git revert 6d05695`；协议全流程留痕（TICKS C-20261022-2007、写前比对通过、写后重验通过）。
- **B2 已执行（硬序合规：先 decision-log 后 closure-map）**：② 与 GOV-P-01/02/03 落笔 decision-log D2026-1022-03（:208）；②→closed、三条移入 entries、seal 真身子项单列残余 GOV-P-2026-1022-03-residual（evidence_gap）；entry_count 实数 28（任务预期 27 未含单列残余条目，差 1 如实登记不强行勾账），provisional_count 0；yaml.safe_load 重验通过（28/0、status 分布自洽、无空 next_review）。
- **②-conflict 关闭动作**：按 B1 规则 4 在 decision-log 落笔后执行，closure-map ②-conflict→closed（冲突事实保留）。
- **§5 单列卡已执行**：见卡 d1022-§5-判定面单列卡.md 执行记录（tools git 707d5fa；回归测试实跑通过、全量 2521+4=2525 基线只增不减、冒烟真跑通过）。
- **RULED 退役**：受控位置脚本 RULED 表清空＋注释留痕（退役声明＋D2026-1022-03 锚点）；运行时验证：② 输入行只出引用行、pending 0、不再命中 RULED。
- **附录 A/B 漂移注记（如实登记）**：受控位置脚本退役前哈希 `b6ec2b43…` 与附录 A 记录值（`baf46980` 最小版）及实现卡扩展版记录值（`1e3fa9de`）均不一致——登记后漂移、归因未明，如实登记；退役后哈希 `2eee57e2…`。附录 B 为退役前副本，附录 A"重算 sha256 须与记录值一致"对退役后版本不再成立（首次基线可复现性指退役前快照）。

## 哈希漂移登记（2026-10-22 收尾轮，owner 裁定显式登记，标 evidence_gap）

- **状态：evidence_gap**（显式登记，不静默带过；承上节漂移注记，本节为正式登记面）。
- 三哈希：退役前 `b6ec2b43…`（受控位置脚本，RULED 退役时点）／附录 A 记录值 `baf46980…`（最小版）／扩展版记录值 `1e3fa9de…`（本卡执行记录）。三值互不一致。
- **归因未明，待查**——不猜原因、不自行修复；查不出原因即维持本 evidence_gap 登记，不因此阻塞 push。
- 本登记满足判定链第 8 条；待查期间不得据附录 A 对退役后版本宣称"可复现性已恢复"。
- **评审轮核实补记（code-review 2026-10-22，实测事实，不归因）**：① 退役后记录值 `2eee57e2…` 与盘上实物逐位一致（现算 10374B，RULED 表已清空仅注释留痕）——缺口仅系退役前三值互不一致，退役后侧无缺口；② scan-min 不受 git 版本化（`~/.zcode/governance/` 无 .git、tools-baseline 无条目）→ 退役前哈希 `b6ec2b43…` 无版本化载体、不可从任何 commit 复算，附录 B 系最小版文本副本非退役前扩展版；③ tools git 三版（67c572f/6d05695/707d5fa）从未含 RULED（逐版 grep=0），"退役混入 §5 提交"假说被实测否定（707d5fa 哈希 `efd42e3f…` 属另一文件 audit_dispatch_compliance.py，非本脚本）。

## 执行记录（CI 红腿 rerun 轮，2026-10-22，owner 裁定：先 rerun 不改测试）

- **rerun 前检查**：工作树干净（`git status --porcelain` 空）；本地 HEAD＝远程 tip＝`6186e96`（ls-remote 一致）。run 39790957026 attempt 1：八腿中 7 绿 1 红，红腿＝test (windows-latest, 3.12)（job 119866528984），失败点 `tests/test_quality_report.py::test_guide_sink_absent_keeps_output_byte_identical`（`assert plain == with_sink`，tests\\test_quality_report.py:412），日志 diff 两时间戳 `13:57:14` vs `13:57:15`（报告头时间与【白话导读】时间跨秒边界），机制＝跨秒竞态，与本轮 docs-only 提交无因果。
- **rerun 方式＝rerun-failed-jobs（仅重跑红腿）**。理由：其余七腿已绿，整体 rerun 只会让已验证绿腿重新暴露 flake 风险并耗 runner 时间；单腿 rerun 基于同一 head SHA（6186e96），结果等价。rerun 期间零文件改动，工作树全程干净。
- **rerun 结果（attempt 2）**：run 级 completed/success。windows-3.12 新 job 119890345719 success（14:42:22→14:46:25Z），日志 `2180 passed, 21 skipped` 零失败（attempt 1 同腿为 `1 failed, 2179 passed, 21 skipped`；收集范围同为 2201，唯一变化即该红测试转绿）。其余七腿保持 attempt 1 绿（四腿 carry 入 attempt 2、三腿归属 attempt 1，均 success）。八腿全绿。
- **观察项单列登记（新 canonical_id，本卡 notes 面登记；不入 closure-map，entry_count 28 维持不动）**：`OBS-CI-FLAKE-20261022`——已知 flake，跨秒边界，rerun 自愈；是否加固待 owner 定。涉及测试＝`test_guide_sink_absent_keeps_output_byte_identical` 的时间处理（若加固，限定冻结 datetime 注入或容忍跨秒，不动被测逻辑）。
- **加固执行记录（2026-10-23，Q4-CI-02，owner 批准 A/B 项）**：测试时间处理已加固；OBS 继续观察，未关闭。
- **完结声明**：规则层＋运行时层＋② 归档均收口，循环验证通过，完全完结。附注：windows-3.12 首跑红系已知 flake 家族跨秒边界偶发，rerun 自愈，非本轮提交引入。
- **哈希漂移登记**：维持 evidence_gap（三哈希互不一致、归因待查），不因 rerun 绿而关闭或勾销。

## 附录 B：脚本全文（实跑副本）

```python
#!/usr/bin/env python3
"""最小运行时（治理轮 2026-10-22）：读 closure-map 两区，按 disposition 打标签输出，十字段统计到 stdout。

本轮范围（实现卡第 1-3 项的最小版）：
- 解析失败即报错退出，不静默降级；
- 统计只打 stdout，不落盘，不建正式输出目录（本轮用系统临时目录）；
- 敏感关键词（hash: 占位）不加载，显式标"敏感关键词未加载，本轮不计"；
- 只读 map 与扫描输出，不写归档卷、不写 decision-log、不改 map。
"""
import sys
import difflib
from collections import Counter
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[错误] 缺少 yaml，无法加载 map（不静默降级）", file=sys.stderr)
    sys.exit(1)

MAP_PATH = Path("docs/governance/closure-map.yaml")
TODAY = date(2026, 10, 22)

# RULED＝运行时侧临时登记表，不是第二真值源，只作提示；每条带 decision-log 锚点＋拍板日期；
# decision-log 归档后本表退役或改判。不写入 map（文档层已冻结、不扩字段）。
RULED = {
    "D2026-1022-02②": {
        "anchor": "decision-log.md:199",
        "date": "2026-10-22",
        "ruling": "仅 code-Executor 入判定面，检索类仅观察列；窗口延长至 2026-11-10",
    }
}

if not MAP_PATH.is_file():
    print("[错误] map 不存在，退出（不静默降级）", file=sys.stderr)
    sys.exit(1)
try:
    doc = yaml.safe_load(MAP_PATH.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"[错误] closure-map 解析失败，退出（不静默降级）：{exc}", file=sys.stderr)
    sys.exit(1)

index = []
for zone, rows in (("entries", doc.get("entries") or []), ("provisional", doc.get("provisional") or [])):
    for e in rows:
        index.append({
            "canonical_id": e["canonical_id"],
            "zone": zone,
            "status": e["status"],
            "default_action": e.get("default_action"),
            "titles": e.get("legacy_titles") or [],
            "keywords": e.get("legacy_keywords") or [],
            "evidence_refs": e.get("evidence_refs") or [],
            "next_review": e.get("next_review"),
            "ruling_question": e.get("ruling_question"),
            "default_option": e.get("default_option"),
            "consequence": e.get("consequence_if_no_decision"),
            "notes": e.get("notes"),
            "conflict": bool(e.get("conflict")),
        })

sensitive_skipped = sum(1 for e in index for kw in e["keywords"] if str(kw).startswith("hash:"))


def norm(s):
    return str(s).lower().replace("\\", "/")


def match(line):
    n = norm(line)
    for e in index:
        if norm(e["canonical_id"]) in n:
            return e, "exact"
        for kw in e["keywords"]:
            if str(kw).startswith("hash:"):
                continue
            if norm(kw) in n:
                return e, "exact"
    best, ratio = None, 0.0
    for e in index:
        for t in e["titles"]:
            r = difflib.SequenceMatcher(None, n, norm(t)).ratio()
            if r > ratio:
                best, ratio = e, r
    if best and ratio >= 0.6:
        return best, "similarity"
    return None, None


def due(next_review):
    if not next_review:
        return False
    if "触发条件" in str(next_review):
        return False  # 触发型不可自动判，只登记
    for tok in str(next_review).split():
        try:
            y, m, d = map(int, tok.split("-"))
            if date(y, m, d) <= TODAY:
                return True
        except ValueError:
            continue
    return False


def disposition(e, stats):
    if e["zone"] == "provisional":
        emit(f"临时条目，待归档，见 {e['canonical_id']}")
        return
    st = e["status"]
    if st in ("closed", "written_back", "meta_cleared"):
        stats["closed_cited"] += 1
        if st == "closed" and e["default_action"] == "optional_no_action":
            emit(f"已收口，见 {e['canonical_id']}；残余可选决策见 {e['canonical_id']}-residual，默认不动")
        else:
            emit(f"已收口，见 {e['canonical_id']}；证据 {e['evidence_refs']}")
    elif st == "optional_decision":
        emit(f"原账已关闭（{e['canonical_id']}），可选决策默认不动；除非 owner 明确覆盖红线")
    elif st == "owner_decision_pending":
        stats["pending"] += 1
        r = RULED.get(e["canonical_id"])
        if r:
            emit(f"{e['canonical_id']}｜已拍板，待落 decision-log（锚点 {r['anchor']}，拍板 {r['date']}）｜{r['ruling']}｜不再重问")
        else:
            emit(f"待拍板（每轮一次）：{e['ruling_question']}｜默认：{e['default_option']}｜不拍板后果：{e['consequence']}")
    elif st == "closed_observation":
        if due(e["next_review"]):
            stats["observation_due"] += 1
            emit(f"观察到期出账：{e['canonical_id']}（{e['next_review']}）")
    elif st == "open":
        stats["open"] += 1
        emit(f"出账：{e['canonical_id']}")
    elif st == "evidence_gap":
        stats["evidence_gaps"] += 1
        emit(f"补证清单（无执行动作）：{e['canonical_id']}｜{e['notes']}")
    if e["conflict"]:
        stats["conflicts"] += 1
        emit(f"冲突登记（不自动裁决）：{e['canonical_id']}｜{e['notes']}")


def emit(s):
    print(s)


def audit_round(text):
    stats = Counter()
    seen = set()
    for line in text.splitlines():
        if not line.strip():
            continue
        stats["raw_hits"] += 1
        e, kind = match(line)
        if e is None:
            stats["unclassified"] += 1
            continue
        if e["canonical_id"] in seen:
            stats["dedup_skipped"] += 1
            continue
        seen.add(e["canonical_id"])
        if e["zone"] == "provisional":
            emit(f"临时条目，待归档，见 {e['canonical_id']}")
            continue
        if kind == "similarity":
            stats["similarity_pending"] += 1
            emit(f"疑似匹配 {e['canonical_id']}（status={e['status']}），待人工确认，不自动关闭")
            continue
        stats["dedup_hits"] += 1
        disposition(e, stats)
    return stats


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "-"
    text = Path(src).read_text(encoding="utf-8") if src != "-" else sys.stdin.read()
    print(f"== 最小运行时扫描（map 两区：entries {len(doc.get('entries') or [])}／provisional {len(doc.get('provisional') or [])}；输入 {src}；日期 {TODAY}）==")
    print("敏感关键词未加载，本轮不计（map 内 hash: 占位 {} 处）".format(sensitive_skipped))
    stats = audit_round(text)
    print("== 统计（只计正式区）==")
    for f in ["raw_hits", "dedup_hits", "closed_cited", "pending", "observation_due",
              "open", "conflicts", "evidence_gaps", "similarity_pending", "unclassified"]:
        print(f"  {f} = {stats[f]}")
    print(f"  对账：raw_hits = dedup_hits + unclassified + dedup_skipped（同 ID 重复行，不入统计字段）"
          f" → {stats['raw_hits']} = {stats['dedup_hits']} + {stats['unclassified']} + {stats['dedup_skipped']}")
```
