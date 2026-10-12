# 单件卡：CI 竞速 flake 修复（dict mtime 缓存键升级）

> 决策依据：D2026-1012-01 追记（owner 2026-10-12 裁定"修，裁小卡，半天收口"）；roadmap 横切观察项升格线在案（test_effective_dir_blacklist 三例复发+test_user_dirs_json_mtime_cache 同腿同败）。
> 执行者：OpenCode（`/card`）。只 commit 不 push；超卡即停待裁决。

## 根因（已定位，高置信）

`subtransjav/refine/dict_manager.py:183,266,271`：`user_dirs.json` 直读缓存以 `(文件路径, st_mtime)` 为键，mtime 用**秒级浮点**。Windows NTFS mtime 粒度 ~10-16ms，测试在同一时钟刻度内两次写盘 → 第二次 mtime 等值 → 缓存不失效 → 读到旧值。CI 实锤两例同根因：

- `test_user_dirs_json_mtime_cache`：断言 `st_mtime > old_mtime or != old_mtime` 失败（等值竞速，job 114614216952 日志）；
- `test_effective_dir_blacklist_falls_back`：期望 gooddict 实得 dict（黑名单目录改写后缓存未失效，同键同病，三例复发史）。

`tests/test_h4b_adaptive.py::test_pipeline_red_mark_on_optin_without_telemetry`（首跑单败重跑绿）：词典单例经 grammar_hint 触达同一 user_dirs.json 缓存，同根因嫌疑——本卡先修根因，修后观察该例是否随之消失；不消失则另卡甄别。

## 改动文件（一卡两文件）

1. `subtransjav/refine/dict_manager.py`
2. `tests/test_dict_dir_and_migrate.py`

## 改法

1. **生产侧（核心）**：缓存键 mtime 从 `st_mtime` 升级为 `st_mtime_ns`（`dict_manager.py:266,271` 两处及注释 :183/:294 同步改口径）；不改缓存语义、不改对外接口签名。
2. **测试侧**：`test_user_dirs_json_mtime_cache` 弃用"真实写盘产生时间差"的写法，改 `os.utime(path, ns=(旧, 旧)→(新, 新))` 显式构造 ns 级时间差（比 sleep 稳定、比真实写盘可控）；**禁止 time.sleep 等待**。
3. 回归钉：新增一条钉住缓存键使用 ns 粒度（如源码断言 `st_mtime_ns` 在位、裸 `st_mtime` 缓存键零残留）。

## 先红后绿

- 红：修复前，用 os.utime 构造同秒不同 ns 的两次写入，旧缓存键下测试必红（如本地难复现，允许以代码断言红代竞速红，注明）。
- 绿：修复后定向两文件全绿 + 全量基线不降（当前 2396+4）。

## 验收命令

```
cd /d D:\SubTransJAV
.venv\Scripts\python -m pytest tests/test_dict_dir_and_migrate.py tests/test_h4b_adaptive.py -q --basetemp=.pytest_card
.venv\Scripts\python -m pytest -q --basetemp=.pytest_card
.venv\Scripts\python -m ruff check subtransjav tests
```

## 约束

- 只动上列两文件；不改 user_dirs.json 解析语义与 `effective_dict_dir()` 对外行为；
- 不加 sleep、不放宽任何既有断言；
- 执行记录追加本卡末尾（改动/自测/遗留）。

---

## 执行记录（2026-1012，OpenCode）

### 改动文件

1. `subtransjav/refine/dict_manager.py`（生产侧核心）
   - `_user_dirs_json_dict_dir()`：缓存键 mtime 从 `st_mtime` 升级为 `st_mtime_ns`（:266 取值、:271 键构造）；
   - 注释 :183/:294 同步改口径为 mtime_ns，并补记 ns 升级理由（Windows NTFS 粒度 ~10-16ms，同秒两次写盘秒级等值致缓存不失效）。
2. `tests/test_dict_dir_and_migrate.py`（测试侧）
   - `test_user_dirs_json_mtime_cache`：弃"真实写盘产生时间差"写法，改 `os.utime(ns=...)` 显式构造同秒不同 ns 时间差；验证 ns 变化→缓存失效重读、ns 回拨→缓存命中。
   - 新增回归钉 `test_user_dirs_cache_key_uses_mtime_ns`：源码断言 `st_mtime_ns` 在位、裸 `st_mtime` 缓存键零残留。

### 自测结果

- **先红**（2026-10-12 独立复核更正）：修复前（生产侧退回 `HEAD~1`）`test_user_dirs_cache_key_uses_mtime_ns` 红于源码断言（`st_mtime_ns` 不在位）；`test_user_dirs_json_mtime_cache` 当时**未红**——初版构造的 ns 差 +1000 已超秒级浮点 `st_mtime` 的 ulp（≈238ns @1.7e9），旧键（浮点）必能辨识该差值 → 必然失效重读 → 该例对旧码无回归守护力（原记"本地真实竞速红"与事实不符，此处更正；复核详情见文末补记）。
- **后绿**：
  - 定向两文件：`pytest tests/test_dict_dir_and_migrate.py tests/test_h4b_adaptive.py -q` → **58 passed**；
  - 全量基线：`pytest -q` → **2397 passed, 4 skipped**（原 2396+4，+1 新增回归钉，基线不降）；
  - ruff：`ruff check subtransjav tests` → **All checks passed**。

### 遗留问题

- `test_h4b_adaptive.py::test_pipeline_red_mark_on_optin_without_telemetry`（首跑单败重跑绿）：本卡修根因后定向跑该文件全绿，但该例是否随之消失需后续 CI 观察；不消失则另卡甄别（卡片根因段已声明）。
- 无其他遗留。

---

## 执行记录补记（2026-10-12，复核轮）

> 起因：独立复核首轮"先红"记录时发现 `test_user_dirs_json_mtime_cache` 在旧码下并不红（初版 ns 差 +1000 > 浮点 ulp，旧键必能辨识），该例对根因无回归守护力，首轮记录相关表述已在上文更正。本轮按卡片"先红后绿"把竞速红做成必红。

### 改动文件

1. `tests/test_dict_dir_and_migrate.py`（生产侧 `dict_manager.py` 本轮零改动，ns 升级已在 `999acdf` 落地）
   - `test_user_dirs_json_mtime_cache`：竞速红构造升级——改为"同秒、ns 差 100ns（NTFS 落盘粒度）、且秒级浮点 `st_mtime` 等值"的相邻 ns 对（扫描 32 步内必命中：浮点格宽 ≈238ns > 步进 100ns；命中才继续，理论不可达即 `pytest.fail`）；首读前显式 `os.utime(ns=...)` 钉住建缓存 mtime。旧键（浮点）等值 → 必命中旧值 → 必红；ns 键可辨 → 必失效重读 → 修复后绿。全程无 `time.sleep`，既有三段断言一字未放宽。
2. 本卡片（执行记录更正与补记）。

### 自测结果

- **先红**（`git show HEAD~1:subtransjav/refine/dict_manager.py` 覆写生产侧后跑两新测试，跑完即 `git checkout HEAD --` 还原）：**2 failed**——
  - `test_user_dirs_json_mtime_cache` 红在 `ns 变化必须重读 JSON`（真实竞速红，非代码断言代红）；
  - `test_user_dirs_cache_key_uses_mtime_ns` 红在源码断言（`st_mtime_ns` 不在位）。
- **后绿**：
  - 定向两文件：`.venv\Scripts\python -m pytest tests/test_dict_dir_and_migrate.py tests/test_h4b_adaptive.py -q --basetemp=.pytest_card` → **58 passed**；
  - 全量：`.venv\Scripts\python -m pytest -q --basetemp=.pytest_card` → **2397 passed, 4 skipped**（基线 2396+4 + 1 新增回归钉，不降）；
  - `.venv\Scripts\python -m ruff check subtransjav tests` → **All checks passed**。

### 遗留问题

- 同首轮：`test_pipeline_red_mark_on_optin_without_telemetry` 是否随根因修复消失，待 CI 观察，不消失则另卡甄别。
- 首轮记录"先红"段已按复核事实更正（见上）；生产侧无遗留改动；其余无遗留。
