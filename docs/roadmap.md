# SubTransJAV 版本路线图

> 本文件是版本规划的唯一清单表。维护规则：每完成一项把 ⬜ 改 ✅ 并注明提交号；新版本立项后先在本表登记再开 decision-critic 评议。
> 建立：2026-09-29（D2026-0929-02）；**2026-09-29 重编为 2.0 系列（D2026-0929-05，owner 方向：视听对比+EXE 分发跨代，不再发布任何 1.X；默认不发，恶性缺陷可从 v1.4.0 分支出 1.4.1 紧急修补——仅收安全/致命修复、写明 EOL 窗口、不读新数据根，回退前先导出）；同日 owner 复核 11 条修订定案（D2026-0929-06：frozen 入口+resolver+内部 onedir 门禁前移 beta、TM 落点 pip 零感知、ffmpeg 选型为视听对比动工排期门）**。

## v2.0 —— 视听对比与分发 ⬜（重编立项 D2026-0929-05；原 v1.5 剩余+v1.6+前置视觉批并入）

### 2.0.0-beta（pip 形态 2.0.0b0 先行，PEP 440 预发布号；范围按 D2026-0929-06 修订）

- ✅ 打包地基：`app_root()`/data_root_resolver 路径收敛（优先级 `SUBTRANSJAV_DATA_ROOT` > `%LOCALAPPDATA%\SubTransJAV` > 旧仓库根/旧路径；env 两形态均生效，**默认值按 sys.frozen 判定不按版本号**——frozen 判定归口单一 canonical helper，现 3 处内联收拢；**pip 默认解析结果=旧位零感知**）+ pysubtrans 死依赖摘除（CI 门=import 级钉测试+pyproject dependencies/keywords 断言，不设全仓 grep 门，D2026-0929-07 点 5）+ TM 锚点挂 resolver（tm.py:26 + glossary_conflict.py:213 双文件、路径断言测试跟随；**迁出 Temp 实质清偿随 EXE 首发迁移承载**，D2026-0924-04 欠账结清口径按修订②）+ `subtransjav-refine --where` 诊断（全字段一次报全：运行形态/数据根及来源/配置/TM/conflict_watch/DPAPI 密钥位置/旧根检测+迁移状态）（D2026-0929-06 修订①⑧；执行 d4a4a35，基线 1377+4）
- ✅ frozen 入口改造：spawn 收敛 process_manager 单一 helper——活写入点=**api.py:173/1409、main.py:63 venv 引导 fail-loud**（pip=`-m` / frozen=`--subtrans-cli` 主入口分派，pywebview 初始化前完成；purpose=subprocess|venv_bootstrap 语义位）+ `freeze_support()` + CREATE_NO_WINDOW/UTF-8（子进程 env 注入，删除 relaunch 不取消保证）/显式 env 透传（含 SUBTRANSJAV_DATA_ROOT）/明确 cwd/杀进程树；**console.py relaunch_for_utf8=零调用死代码，同批删除**（静态确认三查全空）；钉测试（生产包 sys.executable spawn 仅准出现在 helper，AST 级）随收敛批落地（D2026-0929-07 点 1；执行 f1b1abe；frozen smoke 四项 rc=0：--subtrans-cli --help/--where 隔离数据根/--dry-run 全链；GUI 待 owner 真机）
- ⬜ 内部 onedir 构建验证（CI artifact 门禁，不对外发布）：子进程翻译/AI 分析 smoke + 双语言对拍 + 迁移 dry-run（验 EXE 迁移路径，非 pip 落点）；产出可下载 onedir zip+Inno 包+sha256，2.0.0 正式前**真人安装反馈一轮（≥2 环境：正常 Win10/11 + 无 WebView2/缺 .NET8 干净 VM）**（D2026-0929-07 点 6）——**本地首建已成功 267MB（sudachidict 208MB 为大头，裁切评估中；e85e001），待 frozen 入口改造后运行时 smoke+CI 首跑**
- ✅ 视听对比技术选型定案（**beta 动工排期门**：探测系统 ffmpeg/ffprobe（whisperjav 用户大概率已装）vs 捆绑 essentials（LGPL+体积评估）vs wave 级 VAD 降级/特性灰显；禁 torch 级默认）——未定案视听对比不动工（D2026-0929-09 定案：探测系统 ffmpeg+纯标准库 RMS 能量代理+HTML5 播放/mkv 抽片+威胁模型五条；C-5 收窄显式化；schema 冻结 suspected_missed_speech；排期门判开）
- ✅ 视觉批（D2026-0929-03 已拍板：A token 化+暗色自选 / B 导航双轨 / C 表单组件；试听 UI 硬前置）（执行 1813307：42 处 width 收编+361 死规则清理+style.dark.css+SVG 双轨导航+三列网格/pill/按钮三级/focus-visible/空态；web-gui-tester 黑盒 15 截图五页×亮暗双主题 PASS+1 暗色低对比当场修复；钉红线全绿）
- ⬜ 视听对比：~~疑似漏听检测~~ ✅ 检测层已落（2c02130：ffmpeg 探测+RMS 能量粗筛+gap 对照+报告节/导读类别 suspected_missed_speech 仅报告+4 参数 TUNABLE+未装灰显，D2026-0929-09 契约全遵循；试跑定阈 10~20 片真实媒体待 owner 侧语料）+ ⬜ 快速试听 UI（逐条字幕+音频播放+媒体路径选择，消费 v1.5 音频链路 media_path 契约与视觉批基线）

**2.0.0-beta DoD（D2026-0929-06/07）**：① frozen onedir 内部构建通过+子进程翻译/AI 分析 smoke 通过（spawn 收敛全链 api×2+venv 引导+双语言对拍）② data_root_resolver+迁移 dry-run+备份/校验/回退测试通过（双源夹具+故障注入：迁移后用户写入场景+写事务中迁移场景）③ WebView2/ffmpeg 依赖检测明确+选型定案记录 ④ pip 2.0.0b0 旧数据根零感知升级验证（--where 指旧位、写入旧位增长、全量基线不降）⑤ Release notes 分层措辞定稿（**EXE 安装版：迁移自动完成，无需手动操作**；pip 用户数据位置不变归 CLI·脚本层说明；旧配置自动迁移失败自动回退）⑥ README 中文主+英文简介落地

### 2.0.0 正式（在 beta 上追加）

- ⬜ EXE 封装：pyinstaller onedir + Inno Setup + GitHub Actions 触发构建附 Release（**workflow_dispatch 手动跑通全链「构建→Inno→安装→smoke→卸载」后才开 tag 触发**，D2026-0929-07 点 7；frozen CLI 冒烟必过：--version / --subtrans-cli --help / 数据根创建+TM SQLite 读写+DPAPI 往返 / GUI 启动连子进程；产物 SHA256+依赖锁必做、SBOM 可选，SHA256 清单随 Release 发布；不用 UPX）；用户数据根=`%LOCALAPPDATA%\SubTransJAV`（**数据根迁移只随 EXE 首发**：三段式迁移落成可测试条件——磁盘预检+backups/pre-2.0.0-YYYYMMDD.zip 保留 N 份且**旧位保留 ≥ 1.4.1 EOL 声明时点**（R4）+**迁移 manifest（清单+sha256+迁移前计数）、哨兵最后写、恢复校验对 manifest**+SQLite integrity_check/JSON/DPAPI 自检+原子切换失败清理**仅限 manifest 匹配迁移残留**续旧根+半迁移自愈（启动检测备份存在+新根不完整→清残留回退）+WAL checkpoint 失败=本轮中止下次重试+幂等多实例锁；tm.db+glossary_conflict_watch.json 双文件携带即 D2026-0924-04 欠账实质清偿；双形态共存防写竞争+卸载器永不删用户数据）；Inno 检测 WebView2 引导 Evergreen Bootstrapper（与 main.py 运行时探测共用 winreg GUID）；首发不签名+SmartScreen/杀软 FAQ（含 SHA256 自证核对指引），Trusted Signing 后续评估
- ⬜ 收口同步：README 结构大修贴合当前项目（双语策略已定缺省=中文主+英文简介段，改判条件=英文 issue 占比上升/上架 winget 或 Store/国际用户增长；README 顶部中英一句话+下载入口、英文 Quickstart 段；CHANGELOG/使用与维护手册同批对齐）（原 D2026-0929-02 收口项）
- ⬜ 2.0.0 tag + Release（附 setup.exe；**Release notes 分层措辞**：EXE 安装版迁移自动完成无需手动操作 / pip 用户数据位置不变、CLI·API·自动化脚本见「路径与数据根迁移」/ 旧配置自动迁移失败自动回退+回退前先导出指引——2.0 定位为功能里程碑；可选 2.0.0rc0 预发布；发布前 owner 真机 GUI 人工验收一次（含无 .NET 8 的 Win10 场景，与 beta 真装一轮合并执行）；更新链路=Inno 覆盖安装+版本检测写入发布文档）

### 2.0.1（独立项，无前置依赖）

- ⬜ CPS/间隙定标后行动化：JAV 场景感知容差（数据源=批次 E 档案 mean 2.71/p95 4.77，预估基准 4-5 区间）
- ⬜ 单行超长白名单（先摘除后计量）
- ⬜ 日文 CPS 定标报告（批次 E 档案 + 增量语料）

## 轨道 B —— 云端闭环（与 2.0 开发并行候选，未启动）

- ⬜ 放行评审（HRO-1 四条件）→ 提案式自动（自动分析+自动提议+批次人工放行）
- ⬜ A′ 等 13 项 UX 复审清单随 B 落地逐条重审

## v2.1+ —— 未规划（需 owner 立项；候选池：跨片聚合分析独立页 / 配音链路 / 上游 v1.9.3+ 对齐 / 引擎页左列表+右详情重构（D2026-0929-03 D 项，立项须重启评议）/ 代码签名 Trusted Signing）

## 已完成版本存档

- ✅ v1.4 —— 质量闭环与通用化（2026-09-29，22efd22 收口；1.4.0 发布 2842693）—— 模型缺省重绑定 / SmartSub 借鉴 4 点 / 文本层巡检 / AI 质量分析 / 五 TAB 外壳 / 前置小件批
- ✅ v1.5 开工批 ——（2026-09-29，2824ea2/14653b6/92ca022/2058d29，D2026-0929-04）README 前置硬伤批（12 项闭集）+ 任务 0 验证（32 份真实 manifest 黄金配对 100%）+ 音频链路（media_path 契约，`--media-path` 进指纹口径）；**原 v1.5 剩余 4 项重编并入 2.0（2.0.0-beta/正式/2.0.1）**
- ✅ v1.3 及更早 —— 见 CHANGELOG 与决策日志

## 横切观察项（不占版本）

- ctx 16384：长文截断 / 术语链断裂 / 重翻触发率 / OOM
- gui-probe 月跳核对；B2 语料相关截止 2026-10-16
