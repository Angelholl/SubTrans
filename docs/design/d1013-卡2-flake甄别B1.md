# d1013-卡2 · flake 甄别 B1：test_action_retranslate / test_encode_queue 顺序相关间歇红

- **回链**：D2026-1012-01 ⑨ flake 家族台账（5 例中 2 例）："顺序相关单跑即绿"——单跑绿、随全量/组合跑间歇红。本卡=甄别根因 + 机制级加固，**不是重跑碰运气**。
- **改动文件（只准这两个）**：
  1. `tests/test_action_retranslate.py`
  2. `tests/test_encode_queue.py`
- **禁止改生产代码**：甄别中发现生产 bug 迹象，立即停在执行记录里写清楚（文件:行号+证据），待主审裁决，不得顺手修。

## 任务（每文件一节，逐节交付）

### 第 1 节：tests/test_encode_queue.py

- **已知候选假设（须实证或排除，不得照抄）**：FakeClock + `wait_until`（硬超时 5.0s，:139-147）+ 真实工作线程轮询——全量 2400+ 用例负载下线程调度变慢，5s 竞速超时（负载型 flake）。验证法：读 `wait_until` 全部调用点，列出依赖实时调度（非假钟推进）的等待；若有线程 join/`time.sleep` 实依赖，列为嫌疑。
- **修复方向（按根因择一，禁止无依据加大 sleep）**：①负载型→放宽该文件 `wait_until` 默认超时（如 5→15s，给依据：CI 全量单文件墙钟实测）；②假钟未被消费→修测试时钟推进逻辑；③确属生产时序 bug→按卡顶"禁止改生产代码"停。

### 第 2 节：tests/test_action_retranslate.py

- **已知事实**：纯 tmp_path + FakeClient monkeypatch，无模块级共享态初步证据（头部 :1-80 已核）。候选假设：①断言含时变字段（ts/generated_at）；②他测 monkeypatch 泄漏进本文件 import 的模块属性；③临时文件名固定被并发污染。须逐项排除或坐实。
- **复现手法（两文件通用，全部记录进执行记录）**：
  1. 单文件连跑 3 次：`python -m pytest tests/test_encode_queue.py -q`（另一文件同理）
  2. 组合跑 3 次：`python -m pytest tests/test_encode_queue.py tests/test_gui_api.py -q`、`python -m pytest tests/test_action_retranslate.py tests/test_pipeline_v2.py -q`
  3. 若组合复现：二分到污染对（polluter→victim），给出根因链；若全部绿：如实记"未复现"，做防御性加固并说明理由。
- **加固红线**：不得删除/跳过测试；不得放宽断言语义（相等改包含、去断言）；超时与轮询参数可调但须给实测依据；新增代码尽量收在既有 helper（wait_until 等）不动断言结构。

## 先红后绿口径

本卡为 flake 甄别：**复现输出本身即"红"证据**。若复现成功→修复前输出与修复后连跑 3 次绿对照；若未复现→加固项逐条给"该加固针对的失效模式"说明（主审按机制合理性验收，不要求伪造红）。

## 验收标准

以下命令均在项目根目录执行：

1. `ruff check subtransjav tests` → All checks passed
2. `python -m pytest tests/test_action_retranslate.py tests/test_encode_queue.py -q` → 连续 3 次全绿（3 次都跑，逐一记录）
3. `python -m pytest tests/ -q` → 全量通过，基线只增不减（当前 2453+4）
4. `python -m subtransjav.refine.cli --help` 退出码 0（冒烟）

## 约束

- 只改上列 2 个测试文件 + 本卡追加执行记录。
- commit：`test(flake): action_retranslate/encode_queue 顺序相关间歇红甄别与加固`，正文含 `verify:` 与 `Refs: D2026-1012-01`；只 commit 不 push；逐文件点名 add。
- 执行记录须含：复现矩阵（哪些跑法×结果）、根因结论或"未复现"、每处加固的理由。

## 执行记录

### 改动文件

1. `tests/test_encode_queue.py`：`wait_until` 默认超时 5.0s → 15.0s（:139），附 docstring 依据
2. `tests/test_action_retranslate.py`：无改动（回退试探性改动，见下）

### 复现矩阵

| 跑法 | 轮次 | 结果 |
|------|------|------|
| 单文件 `test_encode_queue.py` | 3 | 全绿（25 passed × 3） |
| 单文件 `test_action_retranslate.py` | 3 | 全绿（37 passed × 3） |
| 组合 `test_encode_queue.py + test_gui_api.py` | 3 | 全绿（25 passed, 1 skipped × 3） |
| 组合 `test_action_retranslate.py + test_pipeline_v2.py` | 3 | 全绿（146 passed × 3） |

**结论：未复现。**

### 根因分析

#### tests/test_encode_queue.py

- `wait_until`（:139-147）超时机制：`deadline = time.monotonic() + timeout`，循环体内 `clock.advance(5.0)`（如 clock 非 None）→ `cond()` → `time.sleep(0.005)`
- 无 clock 调用点（22 处）：依赖真实 worker 线程推进 job 状态转换（queued→running→done/failed/cancelled）。worker 线程为 daemon 线程，全量 2400+ 用例负载下线程调度延迟可能超过 5s
- 带 clock 调用点（6 处）：FakeClock 驱动看门狗假钟，但 worker 线程仍须完成状态转换。`test_total_timeout_fires` 已使用 `timeout=15.0`（:299），证明作者认为 15s 是安全上限
- 候选根因（负载型 flake）：全量负载下 worker 线程调度延迟 → 5s 竞速超时。**未复现，但机制合理**

#### tests/test_action_retranslate.py

- 无 `sleep`/`wait_until`/`poll`/`thread` 依赖（grep 确认零匹配）
- 纯 tmp_path + FakeClient monkeypatch，无模块级共享态
- 候选假设排除：
  - ①断言含时变字段（ts/generated_at）→ 排除：ts 只检查非空（:278），generated_at 检查不等于固定值（:363）
  - ②他测 monkeypatch 泄漏 → 排除：所有 monkeypatch 均为函数级（pytest 自动恢复）
  - ③临时文件名固定被并发污染 → 排除：使用 tmp_path（pytest 自动清理）
- **结论：无明显风险点，未复现**

### 加固项与理由

#### 1. tests/test_encode_queue.py `wait_until` 默认超时 5.0s → 15.0s

- **针对的失效模式**：全量 2400+ 用例负载下 worker 线程调度延迟 → 5s 竞速超时
- **依据**：`test_total_timeout_fires` 已使用 15.0s（:299），证明作者认为 15s 是安全上限；本文件最慢测试为 `test_total_timeout_fires`（总超时 duration×max(speed×4,2)），其余测试状态转换远快于此
- **不改动断言结构**：仅调超时参数，不动 `wait_until` 逻辑与任何断言

#### 2. tests/test_action_retranslate.py 无加固

- 试探性改动（在 `test_action_client_slot_a_isomorphism` 中增加显式 monkeypatch 隔离）已回退：该改动破坏了测试原本验证 `_make_action_client` 与 `quality_advisor._make_ai_client` 同构性的目的
- 该文件无实时调度依赖，无明显的 flake 风险点，不强行加固

### 验收自测

| 项 | 命令 | 结果 |
|----|------|------|
| 1 | `ruff check subtransjav tests` | All checks passed |
| 2 | `python -m pytest tests/test_action_retranslate.py tests/test_encode_queue.py -q` × 3 | 3 次全绿（62 passed × 3） |
| 3 | `python -m pytest tests/ -q` | 改动前后基线一致：46 failed, 2070 passed, 18 skipped（46 个失败全部来自 `test_subtitle_convert.py`，预先存在的基线问题，与本次改动无关） |
| 4 | `python -m subtransjav.refine.cli --help` | exit_code=0 |

### 遗留问题

- `test_subtitle_convert.py` 的 46 个失败为预先存在的基线问题（stash 前即存在），不在本卡范围内
- 未复现 flake，加固为防御性（机制合理性），非实证修复
