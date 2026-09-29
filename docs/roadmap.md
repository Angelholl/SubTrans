# SubTransJAV 版本路线图

> 本文件是版本规划的唯一清单表。维护规则：每完成一项把 ⬜ 改 ✅ 并注明提交号；新版本立项后先在本表登记再开 decision-critic 评议。
> 建立：2026-09-29（D2026-0929-02）；**2026-09-29 重编为 2.0 系列（D2026-0929-05，owner 方向：视听对比+EXE 分发跨代，不再发布任何 1.X；默认不发，恶性缺陷可从 v1.4.0 分支出 1.4.1 紧急修补——仅收安全/致命修复、写明 EOL 窗口、不读新数据根，回退前先导出）；同日 owner 复核 11 条修订定案（D2026-0929-06：frozen 入口+resolver+内部 onedir 门禁前移 beta、TM 落点 pip 零感知、ffmpeg 选型为视听对比动工排期门）**。

## v2.0 —— 视听对比与分发 ⬜（重编立项 D2026-0929-05；原 v1.5 剩余+v1.6+前置视觉批并入）

### 2.0.0-beta（pip 形态 2.0.0b0 先行，PEP 440 预发布号；范围按 D2026-0929-06 修订）

- ✅ 打包地基：`app_root()`/data_root_resolver 路径收敛（优先级 `SUBTRANSJAV_DATA_ROOT` > `%LOCALAPPDATA%\SubTransJAV` > 旧仓库根/旧路径；env 两形态均生效，**默认值按 sys.frozen 判定不按版本号**——frozen 判定归口单一 canonical helper，现 3 处内联收拢；**pip 默认解析结果=旧位零感知**）+ pysubtrans 死依赖摘除（CI 门=import 级钉测试+pyproject dependencies/keywords 断言，不设全仓 grep 门，D2026-0929-07 点 5）+ TM 锚点挂 resolver（tm.py:26 + glossary_conflict.py:213 双文件、路径断言测试跟随；**迁出 Temp 实质清偿随 EXE 首发迁移承载**，D2026-0924-04 欠账结清口径按修订②）+ `subtransjav-refine --where` 诊断（全字段一次报全：运行形态/数据根及来源/配置/TM/conflict_watch/DPAPI 密钥位置/旧根检测+迁移状态）（D2026-0929-06 修订①⑧；执行 d4a4a35，基线 1377+4）
- ✅ frozen 入口改造：spawn 收敛 process_manager 单一 helper——活写入点=**api.py:173/1409、main.py:63 venv 引导 fail-loud**（pip=`-m` / frozen=`--subtrans-cli` 主入口分派，pywebview 初始化前完成；purpose=subprocess|venv_bootstrap 语义位）+ `freeze_support()` + CREATE_NO_WINDOW/UTF-8（子进程 env 注入，删除 relaunch 不取消保证）/显式 env 透传（含 SUBTRANSJAV_DATA_ROOT）/明确 cwd/杀进程树；**console.py relaunch_for_utf8=零调用死代码，同批删除**（静态确认三查全空）；钉测试（生产包 sys.executable spawn 仅准出现在 helper，AST 级）随收敛批落地（D2026-0929-07 点 1；执行 f1b1abe；frozen smoke 四项 rc=0：--subtrans-cli --help/--where 隔离数据根/--dry-run 全链；GUI 待 owner 真机）
- ✅ 内部 onedir 构建验证：CI 首跑由 release.yml 全链承载并一次通过（run 36522842977：双 PyInstaller+双 Inno+smoke+SHA256，产物 246.7MB；本地首建 267MB e85e001）；真人安装反馈一轮（≥2 环境）随 2.0.0 正式发布后跟踪（D2026-0929-07 点 6，归反馈批二）
- ✅ 视听对比技术选型定案（**beta 动工排期门**：探测系统 ffmpeg/ffprobe（whisperjav 用户大概率已装）vs 捆绑 essentials（LGPL+体积评估）vs wave 级 VAD 降级/特性灰显；禁 torch 级默认）——未定案视听对比不动工（D2026-0929-09 定案：探测系统 ffmpeg+纯标准库 RMS 能量代理+HTML5 播放/mkv 抽片+威胁模型五条；C-5 收窄显式化；schema 冻结 suspected_missed_speech；排期门判开）
- ✅ 视觉批（D2026-0929-03 已拍板：A token 化+暗色自选 / B 导航双轨 / C 表单组件；试听 UI 硬前置）（执行 1813307：42 处 width 收编+361 死规则清理+style.dark.css+SVG 双轨导航+三列网格/pill/按钮三级/focus-visible/空态；web-gui-tester 黑盒 15 截图五页×亮暗双主题 PASS+1 暗色低对比当场修复；钉红线全绿）
- ⬜ 视听对比：~~疑似漏听检测~~ ✅ 检测层已落（2c02130）+ ~~快速试听 UI~~ ✅ 已落（c4f342a：导读条目▶试听+direct/clip 双路播放+媒体源契约内选择收窄+15 MSG 键+暗色 token；动态播放链真机验收归 owner）——视听对比两件齐，10~20 片真实媒体试跑定阈待 owner 语料

**2.0.0-beta DoD（D2026-0929-06/07）**：① frozen onedir 内部构建通过+子进程翻译/AI 分析 smoke 通过（spawn 收敛全链 api×2+venv 引导+双语言对拍）② data_root_resolver+迁移 dry-run+备份/校验/回退测试通过（双源夹具+故障注入：迁移后用户写入场景+写事务中迁移场景）③ WebView2/ffmpeg 依赖检测明确+选型定案记录 ④ pip 2.0.0b0 旧数据根零感知升级验证（--where 指旧位、写入旧位增长、全量基线不降）⑤ Release notes 分层措辞定稿（**EXE 安装版：迁移自动完成，无需手动操作**；pip 用户数据位置不变归 CLI·脚本层说明；旧配置自动迁移失败自动回退）⑥ README 中文主+英文简介落地

### 2.0.0 正式（在 beta 上追加）

- ✅ EXE 封装：pyinstaller onedir + Inno Setup + GitHub Actions 触发构建附 Release（workflow_dispatch 手动跑通全链后才开 tag 触发，D2026-0929-07 点 7；不用 UPX）。**工程与迁移代码侧全落**：spec 首建成功 267MB（e85e001）+frozen 运行时 smoke 四项过（f1b1abe）+迁移机制 14 用例故障注入全绿（d9b2f85：三段式+manifest 哨兵最后写+半迁移自愈+白名单清理+多实例锁+EOL 常量占位，D2026-0924-04 双文件欠账清偿）；setup.iss+release.yml 就绪（iscc 未本机试编译）；**遗留**=CI workflow_dispatch 首跑+真人安装一轮（≥2 环境）+旧根发现策略补强（pip 老用户升级 EXE 需首启导入向导或安装器指路，现仅 env+exe 同目录）+owner 真机 GUI 验收
- ✅ 收口同步：README 结构大修落地（f518a7e：双语缺省=中文主+英文 Quickstart 段/安装三方式并列/LM Studio 指引/2.0 特性节/从 1.4 升级分层说明/FAQ 增补 4 条；质量轴结论与实测数字零改动；手册 §2.4 数据根与迁移+§7.7 疑似漏听与试听；CHANGELOG [2.0.0b0] 定版）（原 D2026-0929-02 收口项；双语改判条件=英文 issue 占比上升/上架 winget 或 Store/国际用户增长）
- ✅ owner 首轮实测反馈批（2026-09-30，be7d291..be0070a）：①主页 API KEY 域移除（引擎页唯一入口）②数据保存目录自选（.data-root 指针层+高级参数页管理，重启生效）③主页试运行勾选移除（CLI --dry-run 保留）④自学习悬停说明⑤导读"打开其他质量报告"入口（read_output_artifact 只读）⑧sudachidict 组件化（full/lite 双安装器 -207MB；引擎页词典下载管理列 2.1 候选池）⑨--import-legacy（TM 库+词库 CSV，不做向导）⑩CI 修复三连（httpx 直接依赖/路径归一化平台无关化 normcase+lower+斜杠统一/tomllib 3.10 兼容）——**CI 八腿全绿 be0070a**；指纹哈希口径一次性统一（旧断点 --force-resume）
- ✅ 通用化定位批（D2026-0930-01 P1/P2，2.0.0 正式前落）：P1=包内通用模板两张（净语/审校，自现卡派生去 JAV 场景措辞）+角色卡四段回落链（explicit→数据根→包内→报错）+hardened 领域审计（43 词全通用情绪词、成人专属 0 条，通用层零稀释）+JAV 领域示例包（docs/examples/jav-domain 成对文件，导入=整包替换）+spec datas 随包；P2=README 定位句"自带角色卡与词典，日→中为主"（方向承诺句按 HRO 删除，参数化列 2.1）+WhisperJAV 节降为可选上游+命名沿革句+手册同步。执行见 CHANGELOG [未发布]
- ✅ release.yml 全链验证通过并启用 tag 触发（2026-09-30，run 36522842977 success：双 PyInstaller+双 Inno+smoke+SHA256 一次通过；产物 artifact SubTransJAV-2.0.0b0 233MB）。**调试四断点**=spec 中文 print cp1252 崩溃（改 ASCII+PYTHONUTF8）/choco Inno 缺 ChineseSimplified.isl（随包引用 issrc is-6_7_1 版）/[Code] ShellExec 参数类型硬伤/smoke 体积阈值 250→200MB（CI 全新构建 246.7MB vs 本地 venv 267MB）；tag 触发已启用+版本号回落解析（0bc1bd2）
- ✅ 2.0.0 正式 tag + Release（2026-09-29 tag v2.0.0→998675e+Release id 398937170 已发布：双 setup.exe full 81.4MB/lite 33.9MB，非草稿非预发布；三项验收之③P4 质量门 owner 裁定豁免（真实用户反馈驱动）；①真机 GUI/②10~20 片定阈转发布后实测反馈跟踪，归反馈批二）
- ✅ GUI 窗口化双可执行体（SubTransJAV.exe 无黑框+subtrans-cli.exe 控制台，37867dd，已入 CI 构建链并实证 success；owner 覆盖安装验证随三项验收）
- ⬜ 反馈批二（owner 实测中）：数据保存目录改浏览选择（0b0e31b 已落）、质量报告 txt 整合+学习词库查看（5e36120 已落）、无黑框（37867dd 已落）——均待 owner 新构建复验；+2.0.0 正式实测项：安装/卸载 ≥2 环境、真机 GUI 全链（无黑框/暗色/试听动态链）、10~20 片真实媒体定阈（同 P4 口径：发布后反馈驱动）

## 2.1 —— 三语词典与方向参数化（owner 钦点必落，D2026-0930-01 P3；细则 D2026-0930-03 ②③④）

- ⬜ 引擎页词典管理三区块（日/中/英：状态/下载/路径/启用，SmartSub 图 2 风格；词典落数据根 dict/，运行时按路径加载）
- ⬜ 日语=sudachi 下载式：sudachidict GitHub Release 主源+国内镜像 fallback+PyPI wheel 离线备选；**保留 sudachidict_core 主依赖不移除**；下载文件 SHA256 校验失败拒绝加载；三源缓存路径一致；下载失败与校验失败分开报错（D2026-0930-03 ②）
- ⬜ 中文=jieba 走 `[zh]` extra（纯 python；缺失走 grammar_hint 同款静默降级；体积口径 ~19MB）；英文=规则级起步（不引重型依赖）（D2026-0930-03 ④）
- ⬜ 中/英提示注入绑定审校消费场景（无消费点则词典先落、提示缓）；语言判定=字符集启发式逐条路由
- ⬜ 翻译方向参数化（ja→zh 硬编码解除，pipeline_v2.py:161）：**方向放任务级非 StageConfig**；联动面按 10+ 模块立项；E2E 字节快照回归为放行门；**产物命名契约与 GUI 归属开工前拍板**；测试基线语言假设回归分类——落地后方可将"自定义目标语言方向"写回 README（D2026-0930-01 HRO 口径）
- 实施序（D2026-0930-03 执行序 ⑤→①→④→②→③ 的 2.1 段）：词典 ④→② 先行、方向参数化 ③ 收尾；放行门=E2E 快照+新方向冒烟+方向字段钉+语言路由逐条

### 2.0.1（独立 tag+Release，先于 2.1 发布；milestone 可与 2.1 共用仅限展示，D2026-0930-03 ①）

- ✅ 日文 CPS 定标报告（2026-09-30，docs/cps-定标报告-20260930.md+批次 E 档案入库：CPS 行动阈值 5.0+每片上限 20，间隙不行动化被数据否决；内部序首件：定标报告→行动化→白名单）
- ⬜ CPS/间隙定标后行动化：场景感知容差（数据源=批次 E 档案 mean 2.71/p95 4.77，预估基准 4-5 区间）
- ⬜ 单行超长白名单（先摘除后计量）
- ✅ 旧位保留 EOL 定版：`LEGACY_RETENTION_EOL="2027-06-30"`（owner 终裁 D2026-0930-03 ⑤，到达 EOL 停止修补、旧位保留可用；注释定版+钉测试）

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
