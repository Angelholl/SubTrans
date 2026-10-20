# 单件卡：C22 回放 harness 支持逐间隙 labels 数组

> 决策依据：D2026-1009-02 §三（decision-log 条目 D2026-1009-02）「label=该间隙确有台词的真值」逐间隙口径；owner 2026-10-12 要求将 C22 标注简化为听点式工具（见 d1012-C22-卡2），该工具的合并产物依赖本卡先行落库。C22 批。
> 执行者：OpenCode。只 commit 不 push；超卡即停待裁决。

## 根因

tools/c22_calibration.py `_replay_sample`（:75-96）把 manifest 条目的单一 `label` 复用到该导读的**全部**疑似漏听条目上（所有 rows 同一 label），规格要求的逐间隙真值无法表达。若用「每间隙一条 manifest 条目」绕过，会导致 detect_speech_windows / batch_transcribe_clips 对每条间隙各自全量抽音频+装载 whisper（140 次），回放耗时不可接受。故给 harness 加**可选**逐间隙 labels 数组，保持「7 文件级条目 × 每条 20 观测」的批量效率。

## 改动文件（一改一增）

1. `tools/c22_calibration.py`：`_replay_sample` 支持两个可选键（均缺省或 null 时保持旧行为）：
   - `"labels"`：bool 数组，逐 timing 取 `labels[i]` 作为该行 label（缺省时全条目用 `label`，旧行为）；
   - `"timings"`：SRT 区间字符串数组，显式给出本条目 timing 清单，**取代**导读 items 派生清单——标注包每文件只截取了「前 20 条」疑似漏听观测，导读全量条目可能多于 20，显式清单才能精确对齐（缺省时仍走导读派生）。
   - 校验：`len(timings 或 导读派生清单) == len(labels)`（labels 缺省时仅要求 timings 非空）；不匹配 → `_replay_sample` raise ValueError（中文消息），`main` 捕获打印 `❌` 中文提示并 return 1（fail-closed，不得静默截断/循环补齐）。`--selftest`、Wilson/聚合/报告格式/门控写盘逻辑零改动。
2. `tests/test_c22_calibration.py`（新增）：importlib 按路径加载 tools/c22_calibration.py，monkeypatch 模块级 `detect_speech_windows`（返回 `{}`）与 `batch_transcribe_clips`（返回合成转写）：
   - 钉1 逐间隙：单条目导读含 2 个 suspected_missed_speech 观测，sample 带 `labels=[True, False]` → 两行 label 分别为 True/False；
   - 钉2 旧行为回归：无 `labels` 键 → 两行 label 同为 sample 的 label；
   - 钉3 长度不匹配：`labels=[True]` 对 2 观测 → `_replay_sample` raise ValueError 且消息为中文；`main` 层退出码 1；
   - 钉4 门控语义不回归：合成 manifest 全 labels=true 走 `main`（不打 --enable）→ 退出码 0、门控文件不产生（防本卡改动外溢）；
   - 钉5 timings 显式清单：sample 带 `timings=[2 条]`+`labels=[True,False]`（导读实际条目数故意不同）→ 两行按显式 timing 输出且 label 逐条对齐；`timings` 与 `labels` 长度不等 → 退出码 1。

## 先红后绿

- 红：先写钉1-钉4 → 现版忽略 labels 键，钉1 红（两行同 label）。
- 绿：实现 labels 分发 → 定向全绿 + 全量基线不降 + `--selftest` 冒烟退出码 0 且报告仍为「未达标」（方向自证不变）。

## 验收命令

```
cd /d D:\SubTransJAV
.venv\Scripts\python -m pytest tests/test_c22_calibration.py -q --basetemp=.pytest_card
.venv\Scripts\python tools\c22_calibration.py --selftest --out %TEMP%\c22_selftest_card11.md
.venv\Scripts\python -m pytest -q --basetemp=.pytest_card
.venv\Scripts\python -m ruff check tools tests
```

## 约束

- 只动 tools/c22_calibration.py + 新增 tests/test_c22_calibration.py 两文件；不碰 subtransjav/ 产品代码与 C22-卡2 文件；
- `_PRECISION_LB_GATE`、Wilson 计算、聚合口径、报告格式、`config/fullchain_c22.json` 写盘条件（≥0.95 且 --enable）零变化；
- 兼容性：旧形态 manifest（无 labels 键）行为逐字节等值（钉2 保证）；
- 执行纪律：全部自测完成后 commit（Conventional Commits 中文描述，正文含 verify: 基线数与 selftest 结果）+ 本卡末尾追加执行记录 + 向主审报告「C22-卡1 完成」，禁止以「等待中」类文本收尾。

---

## 执行记录（OpenCode，2026-10-12）

**改动文件（卡内两件，零越界）**

1. `tools/c22_calibration.py`
   - `_replay_sample` 支持两个可选键（均缺省或 null = 旧行为）：`labels`（bool 数组，逐 timing 取 `labels[i]` 作该行 label）、`timings`（SRT 区间字符串数组，显式清单**取代**导读 `_observation_timings` 派生；空数组视同缺省回落派生）。
   - 校验：`len(timings 或导读派生) != len(labels)` → raise 中文 `ValueError`（含双方长度）；另对两键类型非法（非 list）同走中文 `ValueError`（fail-closed 扩展，卡面只要求长度校验，类型校验为新键自身合法性检查，不涉旧行为）。
   - `main` 对 `_replay_sample` 包 `try/except ValueError` → 打印 `❌ manifest 第 N 项回放失败：<中文原因>` 并 `return 1`（不静默截断、不循环补齐）。
   - 模块 docstring 同步补两键说明；`--selftest`、Wilson 计算、`_aggregate`、`_write_report`、门控写盘条件（≥0.95 且 `--enable`）**零改动**（diff 仅落上述三处）。
2. `tests/test_c22_calibration.py`（新增，8 个测试 / 卡面 5 钉）
   - importlib 按路径加载 `tools/c22_calibration.py`；fixture monkeypatch 模块级 `detect_speech_windows`（返回 `{}`）与 `batch_transcribe_clips`（合成 good 转写）；另将 `cleanup_clips` 打桩为 no-op（best-effort 切片清理与本卡钉无关，避免测试碰真实数据根临时目录——卡面未列，属隔离手段，已披露）。
   - 钉1 逐间隙 labels（2 观测 → True/False）；钉2 旧行为回归（无 `labels` 键 + `labels: null` 两例，全行用 sample label）；钉3 长度不匹配（`ValueError` 消息含中文 + `main` 退出码 1 且 stdout 含 ❌/中文）；钉4 门控语义（全 `labels=true` 走 `main` 不打 `--enable` → 退出码 0、报告落盘、`config/fullchain_c22.json` 不产生，经 `SUBTRANSJAV_DATA_ROOT` 指向 tmp 隔离断言）；钉5 `timings` 显式清单（导读 3 条 > 显式 2 条 → 按显式出行且 label 逐条对齐）+ `timings`/`labels` 不等长 → `main` 退出码 1。

**先红后绿**

- 红（实现前，仅测试文件）：`5 failed, 3 passed` —— 钉1/钉3×2/钉5×2 红（现版忽略 `labels`/`timings` 键：两行同 label、无 ValueError、退出码 0），钉2/钉4 本就绿（旧行为/门控本就如此）。
- 绿（实现后）：定向 `8 passed`。

**自测结果（卡面验收命令逐条实测，全过）**

| 命令 | 结果 |
|------|------|
| `pytest tests/test_c22_calibration.py -q --basetemp=.pytest_card` | **8 passed** |
| `tools\c22_calibration.py --selftest --out %TEMP%\c22_selftest_card11.md` | **退出码 0**；报告「Wilson 95% 置信下界 0.5101（门槛 0.95：**未达标**）」、门控文件未写入（方向自证不变） |
| `pytest -q --basetemp=.pytest_card`（全量） | **2422 passed, 4 skipped**（基线 2414+4 → 2422+4，只增不减，+8=本卡新钉） |
| `ruff check tools tests` | **All checks passed** |

**遗留问题 / 待主审知悉**

- 标注包合并产物（C22-卡2 `--merge` 写 `c22_manifest_labeled.json` + 一键回放 bat）依赖本卡口径，但卡2 未实现，合并格式尚无端到端实测。
- `labels` 元素按原值入行（JSON `true/false` 形态即 bool），未对逐元素做 bool 类型强校验（卡面只要求长度校验）；若后续标注器产出非 bool，聚合按真值判读。
- 卡面要求的 `--selftest`/Wilson/聚合/报告/门控零改动已核（diff 复查），未跑 mypy 基线（不在本卡验收命令内）。
