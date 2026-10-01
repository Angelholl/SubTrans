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
- ⬜ 反馈批二（owner 实测中）：数据保存目录改浏览选择（0b0e31b 已落）、质量报告 txt 整合+学习词库查看（5e36120 已落）、无黑框（37867dd 已落）——均待 owner 新构建复验；+2.0.0 正式实测项：安装/卸载 ≥2 环境、真机 GUI 全链（无黑框/暗色/试听动态链）、zh→en 端到端 GUI 真跑（D2026-1001-02 补漏：非缺省方向全流程+阶段A/B 指令卡启用+产物 _final_en+方向隔离）、10~20 片真实媒体定阈（同 P4 口径：发布后反馈驱动）

## 2.1 —— 三语词典与方向参数化（owner 钦点必落，D2026-0930-01 P3；细则 D2026-0930-03 ②③④；拍板 D2026-0930-04）✅ 已发布 v2.1.0（2026-09-30，tag v2.1.0→543fb3d release/2.1.0 分支制+Release id 399438370：双 setup.exe 80,993,108/33,538,736B+SHA256SUMS，本地哈希与 CI SHA256SUMS 全一致；含方向角色示例卡 docs/examples/direction-packs/；main CHANGELOG 已同步 [2.1.0]）

- ✅ 引擎页词典管理三区块（2026-09-30，846fae5：日/中/英 状态/下载/自定义路径+下载中态；api refine_dict_status/refine_dict_download；文案全 MSG 键 i18n 契约过；GUI 黑盒已验——bridge 黑盒三区块渲染+下载全链 PASS，截图证据在 Temp/gui-test-screenshots/）+ **下载进度反馈批（同日 owner 验收反馈，词典下载分块化+phase 状态+前端 1s 轮询：按钮百分比/已下载 MB/校验解压分阶段/完成回显路径与大小+行内"自定义词典已就位"徽标；真下载 73.4MB wheel→192.9MB .dic 全链黑盒 PASS）**
- ✅ 日语=sudachi 下载式（2026-09-30，7ca43ec：dict_manager 三源策略——上游已转 PyPI-only，"GitHub 主源"按现状映射为 PyPI 官方→清华镜像（仅网络失败降级）→本地导入；SHA256 官方 digest 核实+不符拒载；两类失败分开报错；sudachidict_core 主依赖保留；grammar_hint 自定义词典路径优先（sudachipy 0.6.11 实证 Dictionary(dict=路径)）；CLI --dict-status/--dict-download）
- ✅ 中文=jieba 走 `[zh]` extra（7ca43ec，缺失静默降级）；英文=规则级起步（en 签名/质量门随批 2 落）
- ✅ 中/英分词提示生成与注入（2026-09-30，D2026-0930-05 拍板+落地，**机制层完成**——zh→en 端到端含提示实效果验证归 owner 真跑冒烟项）：新模块 token_hint（zh=jieba 分词参考，token≥2 且行长≥6 门槛、每条 ≤1 条、缺失静默降级；en=全大写缩写规则零依赖）+_collect_grammar_hints 源语言分派（ja→sudachi 逐字节不动/zh→jieba/en→规则）+A/B 双缝零新缝+【语法提示】头复用残留清理零改动+缓存键 direction 透传缺口顺修；critic 1 HRO（审校绑定口径）采纳落澄清"A/B 均为真实消费点"+4 条件项全采纳；语言判定=字符集启发式逐条路由（en 签名已落 a18119c）
- ✅ 翻译方向参数化批 1+批 2（2026-09-30，be29cda/a18119c，拍板 D2026-0930-04：两 HRO 全采纳）：批 1=final_suffix 单点命名契约（缺省 _final_cn 一字符不变）+方向字段/validate 三查/CLI+TM 唯一约束升维表重建迁移（全 CRUD 语言过滤/CSV 语言列/指纹不变）+manifest direction+指纹条件键缺席归一（HRO-2 字节不变式钉）；批 2=提示词方向 builder（缺省逐字节复刻）+hardened_suffix/synopsis/词库/日文特调规则非缺省抑制+en 签名+is_fluent_target 分派+文法缓存键方向隔离（缓存键位含方向；调用点透传随 D2026-0930-05 补齐）+GUI 完成检测方向化+_v2_stage_prompts_sha1 cfg 感知；全量 1519→1522 基线只增，105 枚 pipeline_v2 缺省快照全绿=E2E 字节不变门
- ✅ 方向参数化残余（2026-09-30，zh→en 真跑冒烟三轮 PASS，LM Studio gemma-4-12b 实跑）：rc=0/`_final_en` 命名/en 签名过/文法提示注入 5/6（≥6 字符门槛生效，短行排除）/TM 方向列 zh-en；真跑抓出三缺陷批内修复（①模型回显提示辅助段→generic A/B 提示词防回显条款+cleaner target 门控 en 模式 ②generic B 无编号协议致 0 行解析→镜像缺省卡语言无关协议骨架 ③TM 方向接线缺口 zh→en 行落 ja/zh→TranslationMemory 实例缺省方向接 cli/pipeline_support 构造点）；基线 1538+5→1547+4 只增；~~测试基线语言假设人工分类复核~~ ✅ 已落（docs/测试基线语言假设分类-20260930.md：34 文件=默认方向钉 22/方向无关 8/方向专项 4，无错配）；README 已写回方向参数（846fae5 批，措辞守 HRO"需配套模板卡"）；**GUI 翻译方向控件补齐（同日 owner 验收发现缺口：定案① 控件批 1/2 未落地）**——高级参数页方向下拉（ja/zh/en）+非缺省方向阶段 A/B 指令卡入口+设置持久化（含 input 防抖兜底程序化赋值场景），缺省零旗标字节钉，桥黑盒渲染/回填/持久化全 PASS；zh→en 端到端 GUI 真跑归 owner 真机验收
- 实施序（D2026-0930-03 执行序 ⑤→①→④→②→③ 的 2.1 段）：词典 ④→② 先行、方向参数化 ③ 收尾——已按序完成，中英提示注入（D2026-0930-05）随收尾落；放行门=E2E 快照+新方向冒烟+方向字段钉+语言路由（快照/字段钉/语言路由已落，真跑冒烟待 owner）

### 2.0.1（独立 tag+Release，先于 2.1 发布；milestone 可与 2.1 共用仅限展示，D2026-0930-03 ①）

- ✅ 日文 CPS 定标报告（2026-09-30，docs/cps-定标报告-20260930.md+批次 E 档案入库：CPS 行动阈值 5.0+每片上限 20，间隙不行动化被数据否决；内部序首件：定标报告→行动化→白名单）
- ✅ CPS/间隙定标后行动化+单行超长白名单（2026-09-30，7059962：cps_too_fast 行动类别（阈值 5.0 CJK/上限 20/三参数分层可调，定点重翻处理要点登记）+白名单先摘除后计量（config/single_line_whitelist.txt，豁免透明计数，文件缺失行为不变）；间隙行动化被数据否决维持观测）
- ✅ 旧位保留 EOL 定版：`LEGACY_RETENTION_EOL="2027-06-30"`（owner 终裁 D2026-0930-03 ⑤，到达 EOL 停止修补、旧位保留可用；注释定版+钉测试）

## 2.1.1 —— UI 改版轮（D2026-0930-07 拍板，critic 有条件支持无 HRO，八修订全采纳）✅ 已落库（2026-09-30，b81e242）

- ✅ 批 1 信息架构与命名明晰化：方向与角色卡统一叙述（"阶段A/B 角色卡（可选，留空=自动查找）"+回落链说明+两套查找体系独立性明示+词库页优先级说明）；**净语配置目录真 bug 修复**（启动硬编码假填充去除+浏览值持久化，api 零改动）；provider 三处同步（快捷条补 zen+双向联动）；残留清理（单按钮标签/TAB4 双名）
- ✅ 批 2 视觉统一与降噪：四组目录行统一 .path-row；内联样式 144→64；app.js 硬编码色映射表逐条 token 化（--text-muted/--status-ok/--status-err/--status-warn 四主题覆盖）；外壳样式迁入 style.css（暗色完整覆盖侧栏/页头）；style.css 死段落 -948 行；btn-text 并入 btn-ghost；form-card 头部 token 统一；导读页"来源"归组；截图验收修复两处布局缺陷（方向卡标签竖排/净语浏览按钮超宽）
- ✅ 验收：全量 1561+4 基线只增；web-gui-tester 桥黑盒五页×亮暗双主题（含完整外壳）+provider 联动+净语目录断言全 PASS（截图 Temp/gui-ui-round-0930/）；联动回显加分观察项判定=说明句已消歧，暂不追加（追加须复议版本号）
- 出局项维持：引擎页左列表+右详情重构（D 项）仍挂候选池独立立项；全局排版节奏变更入候选池等 owner 痛点清单
- 待 owner：五 TAB 逐页痛点清单（下轮输入，D2026-0930-07 ⑥a 裁定）；真机 GUI 走查
- ✅ 已发布 v2.1.1（2026-09-30，tag v2.1.1→b3bc132 release/2.1.1 分支制+Release id 399855074：双 setup.exe 81,011,677/33,557,856B+SHA256SUMS，本地哈希与 CI SHA256SUMS 全一致，notes 只写本版；追加批 2 先例=角色卡目录动态化经版本复议维持 2.1.1）

## 2.2.0 —— UI 三栏工作台世代（D2026-0930-08/-09 + D2026-1001；版本裁定 D2026-1001-02）✅ 已发布（2026-10-01，tag v2.2.0→d62117e release/2.2.0 分支制+Release id 400355734：双 setup.exe 81,102,395/33,563,215B+SHA256SUMS 哈希核过，notes 只写本版；release.yml run 36762095627 绿）

- ✅ 阶段1 三栏骨架+双主题全量重写+主题 5 收敛 2（e4ad66e/ec8a903，D2026-0930-08；契约闸+四档截图+甄别表 d500d78）
- ✅ 阶段2 批1-3：Lucide 捒血+文案中文化+分组标题副标题/文件行四态 chip+只读镜像+进度点+dropzone 高亮/控制台行距+真机清单（4734ee0/fe9c262/3d8b6b3，D2026-0930-09）
- ✅ 真机反馈批五笔（D2026-1001，owner「1A 2不做 3同步 4配合」，明示免真机验收）：版本回填+3 钉（a5eb5b6）/布局断点纠偏（13bab3f）/innerHTML+词典行（ed9a1ed）/系统状态摘要卡（882cbbe）/清单 F 节（519c0bb）
- ✅ 版本裁定与发版纪律（D2026-1001-02）：UI 世代=用户可见新能力升 2.2.0（D2026-0930-07-追加1 的"未发版"前提失效，不静默沿用）；CHANGELOG 写全世代非 patch 观感；**main 回填即时检查点**（7e8a6a7，tag 后立即回填，幽灵版本根因防复发）——**〔D2026-1001-03 起该回填纪律被滚动 dev 号取代〕**：main 常驻 x.y.z.dev0 型滚动号（现=2.3.0.dev0）永不宣称发布版号（PEP 440 语义 2.3.0.dev0<2.3.0），发布走 release/2.x.y 分支，**发布后 main 前进到下一 dev 号=新即时检查点**（已实体化 docs/release-checklist.md 第 8 步，评议员★1 条件闭环）

## 2.2.1 —— UI 阶段3 逐页套规范（D2026-1001-02 立项+批清单二级评议通过）✅ 已落库（2026-10-01，9bb398e+b414bd2，基线 1599+4）；**不单独发版——按 D4（D2026-1001 交接，owner 回"开工"=D1-D4 全按推荐）并入 2.3.0**。发版时点仍按 D2026-1001-03 第⑦项攒批口径：触发=反馈批二修复落库或下一功能批（现口径=D1-D4 落库）；死线=下次真机走查结束后 3 日内复盘是否发；禁把阶段3 回灌进 2.2.0 重新发布。main 版本号已改 **2.3.0.dev0** 滚动 dev 号=第⑧项（按交接文档"若 D4 拍 2.3.0 则直接改 2.3.0.dev0"分支），从 main 构建与发布版永久可区分；dev 号取代"main 回填"纪律——发布走 release/2.3.0 分支，发布后 main 前进下一 dev 号

- ✅ 引擎/模型页：阶段A/B/第三卡 11 处内联宽度收编 CSS+接口地址/兜底并发组卡片化（样式层，wrapper 零增删；C1 中和+C2 label:has 守卫）
- ✅ 词库/模板页：两表挂 .gl-table+表级/列宽规则（C4）+glRender/glLearnedLoad 行模板内联清到类（.gl-alias/.gl-sel-cell）
- ✅ 质量页/高级参数页：adv-group 卡头分层（双标题 :first-child 双选择器，C7）+来源组挂 form-card+AI 结果两表挂 gl-table（C8）
- ✅ 开工门闭环：批清单 docs/design/ui-phase3-批清单.md 二级评议通过（1 HRO 采纳=钉⑤ id 165/i18n 键 186 全集冻结，补 gate 只拦丢失的机器闸；C1-C9 并入第六节）；红线钉 tests/test_ui_phase3_redlines.py 六用例；web-gui-tester 黑盒六组 PASS+四档截图（Temp/gui-phase3/）；Mimosa 复扫 29 零新增（seal 485f0ce9）
- 待 owner：真机走查时顺带目检阶段3 面（引擎三卡/高级卡头/词库表/暗色）；候选池未动：状态 tag 列、checkbox→toggle、接口地址区深化（三项 2026-10-01 复核维持挂起，D2026-1001-03 第⑤项）

## 轨道 B —— 云端闭环（与 2.0 开发并行候选，未启动）

- ⬜ 放行评审（HRO-1 四条件）→ 提案式自动（自动分析+自动提议+批次人工放行）（2026-10-01 复核维持挂起：触发=自动质量闭环真实需求信号，四条件未闭环不进实施，D2026-1001-03 第①项）
- ⬜ A′ UX 复审清单随 B 落地逐条重审（2026-10-01 确认随 B，防过期条款，D2026-1001-03 第②项。计数勘误（评议员 [MATERIAL_CONFLICT] 采纳）：菜单"13 项"与在案 decision-log:1387"未改的 11 项入复审"不一致，以 :1387 口径为准（A′ 已改写=横幅 1 键+6 项 tooltip 两级句式）；若 13=11+2，2=glossary_learn/conflict_block 两无 title 属性控件；逐项枚举随 B 启动时落盘）

## v2.1+ —— 未规划（需 owner 立项；候选池 2026-10-01 全量复核维持挂起（D2026-1001-03）：跨片聚合分析独立页 / 配音链路 / 上游 v1.9.3+ 对齐（被动跟进；触发=owner 发起 whisperjav 升级或上游 release 通知到达，升级后必跑 6 例真实命名端到端测试防命名漂移复发，不设主动轮询，第⑥项）/ 引擎页左列表+右详情重构（D2026-0929-03 D 项，复核维持出局；重启条件=真机走查暴露引擎页布局痛点，第③项）/ 代码签名 Trusted Signing（不立项；触发=非中文 issue 累计 ≥5 或 winget/Store 上架被接受——与双语改判条件同组信号防多头挂信号；计数口径见 D2026-1001-03；零成本前置=SmartScreen+哈希校验指引已补 README 与手册；自签证书不消除 SmartScreen 不作替代，第⑩项）/ ~~UI 改版轮（owner 2026-09-30 挂账）~~ ✅ 已立项落地为 2.1.1（D2026-0930-07，见上节）/ frameless 自绘标题栏（D2026-1001 拍板不做，2026-10-01 复核维持后置；重议条件=owner 对窗口外观再有诉求，第④项）；候选池新增：全局字号/行高/间距节奏 token 化与密度重排（等 owner 痛点清单=第⑫项走查 G 节输入）、GUI 原生 alert/prompt 替换自制弹窗、首启初始化（第⑨项唯一真残余：api.py:1305 first_run 信号已在、前端零消费；承接画像预设取消后的"小白型首启极简"诉求）、Translator Panel 等残余死规则清理（降格=并入下一 UI 批批清单固定小节收尾扫查，独立勾选+提交信息注明"候选池兑现"；落地时按"五 TAB 世代泛名类"重新盘点防空头，第⑪项）；旧轨道 A 残余账（第⑨项）：统一持久化层=已吸收（主题双通道 ThemeManager/控件级即时保存先例，不立项）、画像预设=已取消（a9c4ec1+test_gui_js_static 回流钉，decision-log :1404 追记指针）、ctx 档案值+gemma 兜底与 L1 回归钉=已闭环（代码实证不补登））

## 已完成版本存档

- ✅ v1.4 —— 质量闭环与通用化（2026-09-29，22efd22 收口；1.4.0 发布 2842693）—— 模型缺省重绑定 / SmartSub 借鉴 4 点 / 文本层巡检 / AI 质量分析 / 五 TAB 外壳 / 前置小件批
- ✅ v1.5 开工批 ——（2026-09-29，2824ea2/14653b6/92ca022/2058d29，D2026-0929-04）README 前置硬伤批（12 项闭集）+ 任务 0 验证（32 份真实 manifest 黄金配对 100%）+ 音频链路（media_path 契约，`--media-path` 进指纹口径）；**原 v1.5 剩余 4 项重编并入 2.0（2.0.0-beta/正式/2.0.1）**
- ✅ v1.3 及更早 —— 见 CHANGELOG 与决策日志

## 横切观察项（不占版本）

- ctx 16384：长文截断 / 术语链断裂 / 重翻触发率 / OOM
- gui-probe 月跳核对（2026-10-01：workflow active，手动探针先行全绿 run 36757171642＝collected 112/112 passed；**定时首跳核对=未发生**——03:00 UTC 后 3h+ 该 workflow API total_count 仍=2、event=schedule run 数=0；"未触发"为实证、"整点高负载丢弃"为推断（GitHub 已知特性），cron 已错峰 03:00→03:17 UTC（D2026-1001-03）；下次复核=2026-11-01 首跳，若仍未触发须升格处置（评估弃定时或转真机承载），不得仅再调时间）；~~B2 语料相关截止 2026-10-16~~ ✅ 门②已提前结案（2026-10-01，decision-log [B2 门②基线-20260926]）
- adaptive thresholds 默认开启前置债务：须先补 ≥30 条 origin:"real" 语料，未达标不得改默认开启（decision-log:1316 硬化条件；D2026-1001-03 统一登记）
- refineGlCount 悬空（app.js:1965/2061 有引用无元素）：修复须新增 id 即触钉⑤全集冻结，随下次 UI DOM 批一并处理（decision-log:2000②）
- 容器查询治本方案：不主动引入；触发=真机清单 F 节 DPI 探针实测异常再评估（decision-log:1939）
- 审计积压 4 项挂起（2026-10-01 复核维持挂起，decision-log:1395；D2026-1001-03 收编）：v2_outputs "done" payload 消费端核查（触发=新增/改动消费端或结构时先核查）/ premerge_max_gap_s 移出指纹（触发=任一指纹/断点/恢复路径改动立项时先出兼容分析，无方案不得动指纹哈希面）/ tools 一次性脚本债务（笼统挂起）/ _pid_alive AccessDenied（psutil 硬依赖不可达，笼统挂起）
- 首文件抽检历史观测（v1.3.0 时代，decision-log:1082）：考点=别停/クリ/部長で 误切；后续多轮实测无复发记录，触发=同类误切再现时复核
