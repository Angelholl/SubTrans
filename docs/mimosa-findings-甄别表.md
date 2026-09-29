# Mimosa 扫描发现三态甄别表（v1.3.1 D7a-3，D2026-0925-02）

- **数据源**：`C:\Users\57850\.mimosa\security-scans\project-84b400c5f32332301acf457f\scan-2026-09-24T17-54-12.317Z-a0276cc48beb\findings.json`
- **Seal digest（历史锚：2026-09-24 首扫基线，下表甄别结论即对该次快照作出）**：`sha256:53010c48d878099dfb2c3b91443593f3654baf79619c60063efbaa44bae080da`（seal.json，artifacts 含 findings.json sha256:51623f83…）
- **Seal digest（2026-09-26 复扫后新基线）**：`sha256:79eae27d882b5b250dc2bac8574dd2ed3accd42cc29adbf0fa19f485bedecd2e`，findingCount=**24**，零新增；净减 2 = `tools/tm_promote.py` SQL 字面量化与 `create_shortcut.py` 换 `subprocess` 两处修复在复扫中兑现消除；依赖扫描 completion=completed / packagesScanned=60 / matchedAdvisories=1。
- **Seal digest（2026-09-27 v1.3.2 七任务批后复扫）**：`sha256:c397561fa4ee3cf155b699aa8a7472e08f88f94e798046c89cd32835bddb645a`，findingCount=**24**，零新增（scan-2026-09-27T13-21-25.294Z-4be51437f721）；本批 17 文件（进程治理两原语/分歧复核修复/GUI 折叠与并发/README 修订）未引入新发现，taskkill 原语（process_manager.py）列表参数形态未被标记；依赖扫描 completion=completed / packagesScanned=60 / matchedAdvisories=1 同前。本批 push 时 git-gate L3 拦截的 26 高危+2 低危即本表已裁定各条（行号随代码演进漂移，以 identity.anchor 为准）。
- **Seal digest（2026-09-27 发布阻塞批复扫）**：`sha256:6b29e4581ac2de21c5fe7f4e57c46abbc6ce975322104f24530556fb4d0b9d2e`，findingCount=**24**，零新增（scan-2026-09-27T14-29-31.995Z-aa372695b084）；本批 5 文件（taskkill 测试平台护栏+POSIX 测试 psutil 闸/版本号 1.3.2 清算/cli help 漂移/classifiers 3.13/本甄别表增记）未引入新发现；依赖扫描 completion=completed / packagesScanned=60 / matchedAdvisories=1 同前。
- **Seal digest（2026-09-28 全面审计修复批复扫）**：`sha256:f7dc8d18200988680472dc82f8a8dc023285da9194847f0c91ce0570a0ac39d9`，findingCount=**24**，零新增（scan-2026-09-27T17-40-19.478Z-bcdf72a3f62e）；本批 16 文件（四路审计修复：管线核心 4/支撑层 6/GUI 6，含 resume 索引重对齐、导读路径拼接、TM db_path 锚点校验）未引入新发现；依赖扫描 completion=completed / packagesScanned=60 / matchedAdvisories=1 同前。
- **Seal digest（2026-09-28 v1.4 主体批复扫）**：`sha256:882e374b12f23a54d7d05ea9f5a83c09b42bea6738201e0745ba465921ece513`，findingCount=**24**，零新增（scan-2026-09-28T06-22-52.179Z-f3e39b59055f）；本批 24 文件（v1.4 主体：借鉴 4 点+L1 钉+文本层巡检+轨道 A 缺省重绑定+GUI 画像/主题，含 tools/cps_distribution.py 新增）未引入新发现；依赖扫描 completion=completed / packagesScanned=60 / matchedAdvisories=1 同前。
- **Seal digest（2026-09-29 GUI 外壳重构批复扫）**：`sha256:5e8713acc02fd1d82e20aeeaf20e9c298e08dea27b6b90f45a1608abadc63454`，findingCount=**24**，零新增（scan-2026-09-28T09-43-53.871Z-e3ff960c4121）；本批 4 文件（左侧 TAB 外壳：index.html 全量重排+app.js 用户模式/引导卡移除+两测试文件重构）未引入新发现；依赖扫描 completion=completed / packagesScanned=60 / matchedAdvisories=1 同前。
- **Seal digest（2026-09-29 AI 质量分析批复扫）**：`sha256:63f6552aa3402de56b385c7b0e41851d633cc2e7eb5de55534e3739b1d92211d`，findingCount=**24**，零新增（scan-2026-09-28T10-32-14.057Z-ed4b92e7f157）；本批 16 文件（AI 质量分析后端 quality_advisor.py+CLI 子命令+词库锁定追加+伴生件清理表收编+GUI 三端点与导读页接入）未引入新发现；依赖扫描 completion=completed / packagesScanned=60 / matchedAdvisories=1 同前。
- **Seal digest（2026-09-30 2.1 中英分词提示批复扫）**：`sha256:630632eed4af335c5bb8f227cba2700d6070302a8a4fd9b6c3b41b8cc97ca96a`，findingCount=**26 = 基线 24 零新增 + 树外签注 +2**（scan-2026-09-29T15-00-53.441Z-9d6d2c84f058）；本批 7 文件（token_hint.py 新增/pipeline_v2.py 源语言分派/test_token_hint.py 17 用例/决策日志/测试基线分类表/CHANGELOG/roadmap）未引入新发现。+2 均为 `Temp/pyinstaller_dist{,_lite}/SubTransJAV/_internal/webview/js/api.js` 的 high code-injection——**本地 onedir 构建产物中的 pywebview 自带资产拷贝**（verdictEffect=none，static-finding），按 ②树外签注 处置（Temp 瞬态构建目录不入库；留存期间深扫面不减，清理构建目录后自然消除）；基线 24 条（20 路径穿越+2 SSRF+2 弱随机）identity 逐一比对无变化；依赖扫描 completion=completed / matchedAdvisories=1（离线快照 context-only）同前。
- **Seal digest（2026-09-30 zh→en 冒烟三缺陷修复批复扫）**：`sha256:c9ec5c0a1347e236834721c9df0bf693f49c3fd0aeba6b535464b99be9f17e21`，findingCount=**26 = 基线 24 零新增 + 同上树外签注 +2**（scan-2026-09-29T16-10-31.452Z-8817050201b5）；本批 12 文件（回显修复：pipeline_v2/cleaner_rules/test_token_hint/test_direction_batch2；TM 方向接线：tm/cli/pipeline_support/test_tm_direction；generic B 协议：pipeline_v2/test_direction_batch2；docs 四件）未引入新发现，identity 清单与前扫完全一致（+2 仍为 pyinstaller_dist 构建产物签注项）；依赖扫描 completion=completed / matchedAdvisories=1 同前。
- **Seal digest（2026-09-30 词典下载进度反馈批复扫）**：`sha256:b0cabf9f6e1ad767b86f3d56965fa4c6674cf42c819ff0cf23c91ff5fffde56c`，findingCount=**26**，与前扫身份级比对**零新增零消除**（scan-2026-09-29T17-36-40.294Z-aa0a8c4e4811）；本批 6 文件（dict_manager 分块下载+phase 进度/api.py 进度端点/app.js 轮询渲染/strings.py 两 MSG 键/两测试文件）未引入新发现（+2 树外签注项同前）；依赖扫描 completion=completed / matchedAdvisories=1 同前。
- **行号声明**：下表 line 号为扫描时点快照，会随代码演进而漂移；以 `identity.anchor`（findings.json 内 sha256 锚）为准做身份比对，行号仅作定位便利。
- **口径修正声明（双基线并列）**：旧基线（2026-09-24 首扫，即上行历史锚 seal）——主控下发口径按 :786 分类相加为 25≠26；该次以 findings.json 实际数据为准：**20 路径穿越 + 2 SSRF + 1 SQL 注入 + 1 命令注入 + 2 弱随机 = 26 条（历史口径，仅指首扫快照）**。新基线（2026-09-26 复扫，即上新基线 seal）——findingCount=**24 条**，零新增，净减 2 = tm_promote.py SQL 注入 1 条与 create_shortcut.py 命令注入 1 条兑现消除。两引擎口径差异分列有先例：**D2026-0921-03 27/26 分列**。

三态定义：
1. **已修复**：本轮改动消除（入库）。
2. **树外签注**：目标文件 UNTRACKED/.gitignore，不入仓库基线；本机一次性处置/留存声明，不构成仓库基线修复面（UNTRACKED 2 文件 3 条统一用此表述；Temp 瞬态脚本不修，留存期间深扫面不减）。
3. **留痕维持**：本地单机工具，无不可信输入面，维持现状并留痕判据。

## 三态统计（双基线并列）：旧基线（2026-09-24 首扫，26 条，历史口径）：①已修复 1 ｜ ②树外签注 3 ｜ ③留痕维持 22 ｜ 新基线（2026-09-26 复扫，24 条）：上式净减 ①中 tm_promote.py SQL 1 条与 ②中 create_shortcut.py 1 条（兑现消除，①已从扫描面消除）→ ②剩 2（Temp/build_blind_pack.py 弱随机）｜ ③ 22 不变

---

## ① 已修复（1 条）

| # | file:line | publicClass | severity | findingId | 证据行与判据 |
|---|---|---|---|---|---|
| 1 | tools/tm_promote.py:51 | sql-injection | high | finding:f3e2befa37d0938f19301e67 | 原 `f"SELECT {cols} FROM {TABLE}…"` f-string SQL 三处（:51/:64/:96 附近）已改字面量 SQL（7a-1，先例 7f1c0c1 v2_manifest_fp），插值面清零，数据一律参数化 `?`。 |

## ② 树外签注（3 条，UNTRACKED 2 文件）

| # | file:line | publicClass | severity | findingId | 证据行与判据 |
|---|---|---|---|---|---|
| 2 | create_shortcut.py:11 | command-injection | high | finding:e9281db5d22bac827e16b3c9 | 原 `os.system(f'"{sys.executable}" -m pip install pywin32')` 已改 `subprocess.call([sys.executable, "-m", "pip", "install", "pywin32"])`（7a-2）；文件 UNTRACKED/.gitignore，本机一次性处置，**不构成仓库基线（D2026-0925-02 D7a）**，故记树外签注。 |
| 3 | Temp/build_blind_pack.py:10 | insecure-randomness | low | finding:0bdd4fe29173e436783d1499 | `rng = random.Random(42)`：固定种子盲测打包器，弱随机反而是确定性重放需要；瞬态脚本不修，留存期间深扫面不减。 |
| 4 | Temp/build_blind_pack.py:57 | insecure-randomness | low | finding:0bdd4fe29173e436783d1499 | `random.Random(7).sample(rest, …)`：同上，抽样盲测集用固定种子可复现是特性不是缺陷。 |

## ③ 留痕维持（22 条）

### refine 面 10 条路径穿越（本地单机工具构造路径，无不可信输入面）

| # | file:line | severity | findingId | 证据行与判据 |
|---|---|---|---|---|
| 5 | subtransjav/refine/cli.py:329 | high | finding:bafa083aed72363167807da2 | `from .config import LOGS_DIR`：日志目录为程序内常量构造路径，非用户穿越面。 |
| 6 | subtransjav/refine/filters.py:91 | high | finding:7cc1ebfc7715bc5ca435880d | `open(srt_path, "w", …)`：输出路径由本地 CLI 参数链（操作者本人）构造，单机无跨信任边界调用方。 |
| 7 | subtransjav/refine/glossary_conflict.py:164 | high | finding:821a7f08ca21f75982bc1e1c | `open(p, "w", encoding="utf-8-sig", …)`：冲突报告路径同上，操作者 CLI 参数链。 |
| 8 | subtransjav/refine/glossary.py:60 | high | finding:aea75b4fd802834ad18b95ad | `open(path, "w", encoding="utf-8-sig", …)`：术语表导出路径由本地 config/参数构造，无不可信输入。 |
| 9 | subtransjav/refine/instructions.py:87 | high | finding:ec34fe6407d2dfef39e7ec56 | `open(path, "w", encoding="utf-8")`：提示词文件路径为程序内派生路径。 |
| 10 | subtransjav/refine/language_validator.py:274 | high | finding:e65e93ab1230f3b6ecbff2aa | `open(srt_path, "w", encoding="utf-8")`：校验器写回路径，操作者本人指定。 |
| 11 | subtransjav/refine/manifest.py:131 | high | finding:dc990779a13a808494c43465 | `open(tmp, "w", encoding="utf-8")`：manifest 临时文件路径程序内构造（tmp→rename 模式）。 |
| 12 | subtransjav/refine/quality_report.py:404 | high | finding:98f2b0aac98b7d33e7e57033 | 质量报告产物路径枚举（`[(r, "已过滤") for r in artifacts]` 一带）：报告目录本地派生，无外部输入。 |
| 13 | subtransjav/refine/runlog.py:148 | high | finding:1f68310dd90cadd7dbf5bafa | `open(target, 'w', encoding='utf-8')`：错误日志归档目标路径由 Logs/ 常量目录派生。 |
| 14 | subtransjav/refine/tm.py:331 | high | finding:a14e3c7d40ccc72049c86bb3 | `open(path, "w", encoding="utf-8-sig", …)`：TM 导出路径，操作者 CLI 参数链。 |

### api 面 2 条路径穿越（本地 GUI 回环，路径来自本地配置/会话内自产数据）

| # | file:line | severity | findingId | 证据行与判据 |
|---|---|---|---|---|
| 15 | subtransjav/webview_gui/api.py:1057 | high | finding:ccbcb5d0b3d2c98620b1b856 | `by_stage = {s.get("stage"): s for s in data["stages"]…}`：本地 webview GUI 只回环服务本机会话，路径/阶段数据自产自用，无远程不可信客户端。 |
| 16 | subtransjav/webview_gui/api.py:1193 | high | finding:ccbcb5d0b3d2c98620b1b856 | `if not os.path.isfile(p):`：同 finding 同源，`p` 为本地会话内工作目录派生路径。 |

### tools 面 8 条路径穿越（操作者 CLI 参数链）

| # | file:line | severity | findingId | 证据行与判据 |
|---|---|---|---|---|
| 17 | tools/ab_compare_srt.py:318 | high | finding:a5484d1c0947dfeb4d24d39b | `open(OUT_TXT, "w", encoding="utf-8")`：A/B 对比输出为脚本内常量路径。 |
| 18 | tools/bench_refine.py:122 | high | finding:f78a5359eef3855f194e9521 | `open(in_path, "w", encoding="utf-8")`：基准输入构造，操作者本人指定路径。 |
| 19 | tools/context_review.py:906 | high | finding:af160b62079add92c8d6b247 | `open(out_path, "w", encoding="utf-8-sig", …)`：复核报告输出，操作者 CLI 参数链。 |
| 20 | tools/glossary_learned_reset.py:71 | high | finding:4f8c0efde120d7f5a26517c3 | `open(p, "w", encoding="utf-8-sig", …)`：学习术语表重置目标路径，config 常量派生。 |
| 21 | tools/model_matrix_run.py:121 | high | finding:9e4a8467fa88a394ea68d158 | `open(tmp, "w", encoding="utf-8")`：矩阵评测临时文件，程序内构造。 |
| 22 | tools/model_matrix_run.py:403 | high | finding:9e4a8467fa88a394ea68d158 | `logf = open(log_path, "w", …)`：评测日志路径，操作者 CLI 参数链。 |
| 23 | tools/model_matrix_run.py:1069 | high | finding:9e4a8467fa88a394ea68d158 | 同上（第二处日志句柄），同源同判据。 |
| 24 | tools/tm_purge.py:348 | high | finding:ce19f1834895030d6d709990 | `open(path, "w", encoding="utf-8-sig", …)`：清理工具导出路径，操作者本人指定。 |

### SSRF 2 条（本地回环探测，无远程攻击者可控 URL）

| # | file:line | severity | findingId | 证据行与判据 |
|---|---|---|---|---|
| 25 | subtransjav/refine/glossary_learn.py:91 | high | finding:f47d894d666709fe19ea5304 | `r = requests.get(probe_url, timeout=timeout_probe)`：probe URL 为本地词典服务健康探测（本机回环），目标由本地配置给出。 |
| 26 | tools/model_matrix_run.py:221 | high | finding:0f0d5e2b912d2f7d0cc88f80 | `with _urlreq.urlopen(req, timeout=60) as resp:`：请求本地 LM Studio/模型服务端点（127.0.0.1 回环），端点来自本地配置。 |

---

**留痕维持总判据**：本项目为本地单机工具链（CLI + 本地 webview 回环），上述路径/URL 全部来自操作者本人 CLI 参数、程序内常量或本地配置文件派生，不存在跨信任边界的不可信输入方；边界加固以守卫脚本（tools/guard_banned_paths.py，D10）+ 敏感路径名单制承接（decision-log :139 契约）。
