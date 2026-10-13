# d1013-卡4 · flake 甄别 B3：test_resume_rejects_changed_stage_prompts（顺序相关间歇红）

- **回链**：D2026-1012-01 ⑨ flake 家族台账；症状=单跑绿、全量/组合跑间歇红于 `tests/test_pipeline_v2.py::test_resume_rejects_changed_stage_prompts`（:2834：D1 指纹失配→--resume 拒绝复用阶段A）。
- **改动文件（只准这一个）**：
  1. `tests/test_pipeline_v2.py`
- **禁止改生产代码**：读 `run_v2` 的 resume/指纹路径（`subtransjav/refine/pipeline_v2.py`）属只读侦察；若根因坐实在生产侧（指纹含时变字段/缓存未失效/中断点时序），停在执行记录给证据待裁决。

## 主审候选假设（须实证或排除，不得照抄）

1. **中断点时序**：`_run_interrupted`（:1618）用 `InterruptingBClient` 抛 KeyboardInterrupt——若该假客户端的中断点受调用次序/缓冲影响，两轮运行间 manifest 状态可能不同（如阶段B 是否已留半截产物），导致 resume 判定路径漂移。
2. **指纹含时变字段**：manifest/配置指纹若掺入 `generated_at`/`ts`/`st_mtime` 秒级字段，同秒写入可产生偶发同/异值。
3. **capsys 竞速**：断言读 `capsys.readouterr().out`，若 run_v2 内有子进程/线程异步 print，捕获可能间歇缺行。
4. **共享 work 目录**：`_make_cfg(tmp_path)` 的 work 目录派生若含全局计数/固定名，他测残留可干扰。

## 复现手法（全部记录进执行记录）

1. 单测连跑 5 次：`python -m pytest "tests/test_pipeline_v2.py::test_resume_rejects_changed_stage_prompts" -q`
2. 整文件连跑 2 次：`python -m pytest tests/test_pipeline_v2.py -q`
3. 组合跑 3 次：`python -m pytest tests/test_pipeline_v2.py tests/test_gui_api.py -q`、`python -m pytest tests/test_pipeline_v2.py tests/test_action_retranslate.py -q`
4. 复现→二分到污染对/根因链→测试侧机制修复；全部绿→如实记"未复现"+防御性加固（对准上述假设逐条排除后的残余风险），不得弱化断言、不得删改既有用例语义。

## 先红后绿口径

同 B1：复现输出即红证据；修复前后对照或加固理由逐条给据。

## 验收标准

以下命令均在项目根目录执行：

1. `ruff check subtransjav tests` → All checks passed
2. `python -m pytest tests/test_pipeline_v2.py -q` 连续 2 次 → 全绿（逐一记录）
3. `python -m pytest tests/ -q` → 全量通过，基线只增不减（当前 2453+4）
4. `python -m subtransjav.refine.cli --help` 退出码 0（冒烟）

## 约束

- 只改 `tests/test_pipeline_v2.py` + 本卡追加执行记录。
- commit：`test(flake): resume 指纹拒绝用例顺序相关间歇红甄别与加固`，正文含 `verify:` 与 `Refs: D2026-1012-01`；只 commit 不 push；逐文件点名 add。

## 执行记录

### 改动文件

1. `tests/test_pipeline_v2.py`：仅 `test_resume_rejects_changed_stage_prompts`（:2834-2868）加机制级前置/自洽断言，既有断言一条未删未弱化。
2. 本卡（追加执行记录）。生产代码零改动（`subtransjav/refine/pipeline_v2.py`、`v2_manifest_fp.py`、`manifest.py` 全程只读侦察）。

### 复现矩阵（改动前 / 改动后，本沙箱 win32）

| 跑法 | 轮次 | 改动前 | 改动后 |
|------|------|--------|--------|
| 单测 `test_resume_rejects_changed_stage_prompts` | 5 | 全绿（1 passed ×5） | 全绿（1 passed ×5） |
| 整文件 `tests/test_pipeline_v2.py` | 2 | 全绿（109 passed ×2） | 全绿（109 passed ×2） |
| 组合 `test_pipeline_v2.py + test_gui_api.py` | 3 | 全绿（109 passed, 1 skipped ×3） | 全绿（109 passed, 1 skipped ×3） |
| 组合 `test_pipeline_v2.py + test_action_retranslate.py` | 3 | 全绿（146 passed ×3） | 全绿（146 passed ×3） |
| 定向污染对（`test_manifest_model` + `test_direction_batch1/2` + `test_rules_loader` + `test_context_sidecar` + `test_pipeline_v2`，即全部触碰提示词/方向/规则指纹的文件） | 2 | —— | 全绿（201 passed ×2） |
| 全量 `tests/` | 2 / 1 | 46 failed, 2072 passed, 18 skipped（×2） | 46 failed, 2072 passed, 18 skipped（×1） |

**结论：未复现。** 本沙箱 17 次跑（含 3 次全量）目标用例全绿。全量 46 例失败与本卡无交集：全部为 `tests/test_cli.py`(25) / `tests/test_subtitle_convert.py`(20) / `tests/test_h4b_adaptive.py`(1) 的 `ModuleNotFoundError: No module named 'pysubs2'`——本机缺该依赖的预存环境失败（改动前两次全量即已存在，逐项一致）。卡面"当前 2453+4"为全依赖环境口径；本沙箱 `--co` 实收 2134（缺 pysubs2 等可选依赖所致），故以"改动前后逐项一致"替代绝对数对照。

### 逐假设排除（证据）

- **假设1 中断点时序 → 排除**。阶段B 输入条目在 `pipeline_v2.py:862-874` 恒以 `f"{ja} ||| {zh}"` 组装（ja 为空串也保留分隔符），`InterruptingBClient.translate_entries`（:1583-1587）只在**首个**含 `|||` 的批次抛 KeyboardInterrupt；清单在 `mark_running("A")`/`mark_running("B")` 处即落盘（:1519-1520、:1555-1556），早于客户端调用。异常吞噬面已查：`_run_with_fallback`（:563-599）无 try/except；`_process_file` 只 `except Exception`（:1100），KeyboardInterrupt 属 BaseException 不被吞；全仓 `except BaseException` 仅 llm_client:331（重新 raise）、glossary/secrets 各处（不在本路径）。→ run1 现场恒为 A=done / B=running，无"半截阶段B产物"漂移。
- **假设2 指纹含时变字段 → 排除**。config_hash 各成分均为内容/语义哈希：`compute_file_sha1`/`compute_dir_hash`/`compute_glossary_sha1` 只吃字节内容（manifest.py:187-218）；`instruction_files_sha1` 只哈希角色卡+translation_rules.yaml 内容（manifest.py:451-455）；`gate0_rules_sha1` 为规则对象语义 json（source_hallucination.py:840-849）；`asr_meta_sha1` 只由 status/mileage_pct 语义字段构成，且本用例未设 `cfg.asr_meta`、指纹场景 srt_path 为空直接返回无信号 → None（asr_meta.py:189-191、220-235）；`cleaner_config_dir` 缺省 ""→None（config.py:324 + manifest.py:196-199）；`v2_stage_prompts_sha1` 为内存 dict 的 json sha1。manifest 的 `started_at/updated_at`（`timespec="seconds"`）**不进** payload。→ 无秒级字段可产生同/异值抖动。
- **假设3 capsys 竞速 → 排除**。`⚠️ 不复用(...)` 由 `_prepare_manifest` 在主线程同步 print（v2_manifest_fp.py:156，经 pipeline_v2.py:1486 调用），run2 路径无子进程/线程打印：`v2_file_parallel` 缺省 False 且两阶段均为 lmstudio 时直接禁用（:994-1006），`v2_concurrency` 缺省 1（config.py:330），词库学习线程因 `glossary_learn_enabled` 缺省 False 不启动；capsys 捕获 sys.stdout（线程 print 同样入捕）。残余仅"结论只靠 stdout 字符串"这一可诊断性风险。
- **假设4 共享 work 目录 → 排除**。`_setup_e2e`（:1608-1611）把 `refine_tmp_dir` 钉到 `tmp_path/"work"`（每测独享），`_make_cfg(tmp_path)` 的 inputs/输出全在 tmp_path；无全局计数或固定名。`tm_enabled=False` → tm 指纹 None；`glossary_learn_enabled` 缺省 False（config.py:318）→ 不写会话级 learned glossary。会话级只读路径（数据根角色卡/用户覆盖 rules）在 run1→run2 之间不存在写者。

### 加固项与理由（针对排除后的残余风险）

均在 `test_resume_rejects_changed_stage_prompts` 内新增，不改既有断言语义：

1. **中断现场前置钉**（:2839-2844）：断言 manifest 存在且 A=done / B=running。残余风险=假设1 排除所依赖的现场前提一旦被生产侧改动破坏，红点应落在中断侧而非"不复用"断言上。
2. **指纹无时变字段钉**（:2846-2849）：中断轮落盘的 `m.config_hash` 必须等于 `compute_config_hash(cfg)` 独立复算值。残余风险=未来往 `_CONFIG_FIELDS`/指令源指纹掺入 ts/mtime 时，秒级漂移即在此暴露（否则会以"偶发不复用"形态回归）。
3. **D1 机制钉**（:2855-2858）：改 `V2_STAGE_PROMPTS["A"]` 后 config_hash 必须变化。残余风险=方向分派走错（cfg 方向被污染成非 ja→zh 时改用 `_generic_stage_prompt`，其内容不含 V2_STAGE_PROMPTS）或 `_v2_stage_prompts_sha1` 延迟导入异常返回 None——两者都会让 D1 静默失守并表现为"复用阶段A"间歇红，此断言把失败提前到机制点并给出明确理由。
4. **拒绝原因钉 + capsys 无关证据**（:2864、:2866-2868）：`"配置已变化" in out`（只认 D1 原因，防术语表/TM 等其它指纹成分"代打"出的假绿）、首调条目不含 `|||`（证明阶段A 确已重跑，不单靠 stdout 判定）。残余风险=假设3 排除后仅存的"结论只依赖捕获字符串"。

### 验收自测

| 项 | 命令 | 结果 |
|----|------|------|
| 1 | `ruff check subtransjav tests` | All checks passed! |
| 2 | `python -m pytest tests/test_pipeline_v2.py -q` × 2 | 全绿（109 passed；28.31s / 17.02s，逐一记录） |
| 3 | `python -m pytest tests/ -q` | 46 failed, 2072 passed, 18 skipped——与改动前基线逐项一致（46 例全部为缺 `pysubs2` 的预存环境失败，见复现矩阵注）；目标用例通过 |
| 4 | `python -m subtransjav.refine.cli --help` | exit_code=0 |

### 遗留问题

- 本沙箱缺 `pysubs2`，`tests/test_cli.py` + `tests/test_subtitle_convert.py` + `tests/test_h4b_adaptive.py` 共 46 例预存失败，改动前后一致，不在本卡范围（与 B1 卡执行记录同源）。
- flake 未在本环境复现，加固为机制级防御（非实证修复）。若主审在全依赖/CI 环境复现，红点应精确落在加固①-④之一（中断现场 / 指纹时变 / D1 失守 / 拒绝原因），可据此直接二分到根因链。
