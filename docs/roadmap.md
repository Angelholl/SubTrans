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
- ⬜ 反馈批二（**owner 豁免推迟——D2026-1001-05 S7：实测发现问题再修，不删不改判定**）：数据保存目录改浏览选择（0b0e31b 已落）、质量报告 txt 整合+学习词库查看（5e36120 已落）、无黑框（37867dd 已落）——待 owner 新构建复验；+2.0.0 正式实测项：安装/卸载 ≥2 环境、真机 GUI 全链（无黑框/暗色/试听动态链）、zh→en 端到端 GUI 真跑（D2026-1001-02 补漏）、10~20 片真实媒体定阈（同 P4 口径）

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

## 2.3.0 —— 轻量安装包与词典自管理（D2026-1001 交接 D1-D4 拍板+D2026-1001-03 版本口径）✅ 已发布（2026-10-01，tag v2.3.0→5c3919b release/2.3.0 分支制+Release id 400807261：单 setup.exe 33,568,216B+SHA256SUMS 哈希核过，notes 只写本版；release.yml 双跑全绿 dispatch 36837536293+tag 36838069064；发版审读抓出并修复 setup.iss [Files] 空壳缺陷）

- ✅ 批 1 D1 dropzone A 案：#tab-translate 单屏锁定三分区+has-files 双级态（空态 134px/折叠 48px 实测）——黑盒四路径+暗色抽查 PASS（评议员条件①②③零新增 id/键；C1 render 入口单点切换）
- ✅ 批 2 D3 词典去捆绑：推翻 D2026-0930-01⑧+D2026-0930-03② 双决议——full 安装器去 sudachidict（81MB→≈33MB）双安装器合单（spec/iss/release.yml 三件+ci.yml [dev,ja-dict]）+pip 主依赖移除（ja-dict extra+防回流新钉 2 用例）+spec 反收集过滤无条件化（HRO①）+降级文案 C4 七处改写（HRO②）
- ✅ 批 3 D2 词典 B2 案：内嵌「空态引导+下拉+详情区」替代三行网格（解冻 id+9/静态键+4 走钉⑤快照程序，gate 旧基线 check 丢失 0 实证+新基线 174/190）；dictDownload 进度迁移=独立子项（HRO③，本批零改动）
- ✅ 批 4 docs：README ja-dict 安装指引+发布说明素材+批清单评议归档（黑盒发现 DICT_KINDS 两处旧口径文案已随批修正）
- ✅ 发版（D4，owner 放权全流程）：release/2.3.0 @ 5c3919b（bump 2.3.0+CHANGELOG 只写本版+setup.iss 空壳修复+安装器断言）→ dispatch 试构建先行（打包链批 2 大改后首实证）→ tag v2.3.0 REST 建引用（201，2.2.0 授权先例通道）→ tag 构建绿 → artifact 并行 Range 8 片 70,850,389B 精确+exe 33,568,216B sha256 与 SHA256SUMS 一致 → Release id 400807261（非草稿非预发布，notes 能力边界如实告知+禁词自查 CLEAN）→ main cherry-pick 回收发版修复+前进 2.3.1.dev0（release-checklist 第 8 步首次执行）；黑盒证据存 Temp/gui-23/，gate 新基线 %TEMP%\stj_gate\baseline.json（174/190）
- 批清单=docs/design/d1d4-批清单.md（二级评议：无 [HIGH_RISK_OBJECTION]，条件级 C1-C4+备注 R1-R6 全采纳；实现层闭环=批1 清空回归 134px 黑盒/批2 全量只增+ci.yml/批3 三态门控+空态 C2 条件黑盒）

## 2.3.1 —— UI 收尾轮（D2026-1001-04 立项+二级评议有条件放行+C2 复议）✅ 已落库并发布（2026-10-01，tag v2.3.1→3304f95 release/2.3.1 分支制+Release id 400979349：单 setup.exe 33,566,451B+SHA256SUMS 哈希核过 sha256 B079AFF6…59BD，notes 只写本版；构建 run 36864804050 绿；main 前进 2.3.2.dev0=第 8 步）

- ✅ 批 1 dictDownload 进度迁移（B2 案 HRO③ 独立子项回窗）：详情区独立进度条 #dictProgress（包裹容器+独立文本行，var(--text-3) 双主题 token），#dictStatus 降级终态/兜底；kind 归属校验防下载中切下拉串味；黑盒抓出并修复 #dictActionBtn 漏绑监听（批 3 重构静态化遗留）；解冻 id 174→175、静态键 +0
- ✅ 批 2 refineGlCount 悬空修复（decision-log:2000② 借同窗消账）：折叠卡头恢复计数 span（黑盒实证显示行数），app.js 零改动；解冻 175→176
- ✅ 批 3 五 TAB 世代死规则盘点清理（D2026-1001-03 ⑪ 兑现，候选池兑现）：双通道盘点（世代 diff：.translator-* 17 类已零残留；作用域扫描：167 class+18 id 全对照）——清理 .file-item .file-icon（:562 孤儿）+.pill-danger（C2 复议裁决随批删）；.console-line.command 豁免留档（JS 动态拼类不可证死）
- ✅ 批 4 docs：真机清单 F 节版本预期修正（2.3.0/2.3.1.dev0）+评议归档（D2026-1001-04 三级：立项/二级评议/C2 复议）
- 验证链：红线钉+静态钉 45 passed（钉⑤ 176 双向）/全量 1601+4 持平/gate 丢失 0+新基线 176/190/Mimosa 29 零新增（seal 2eafa499）/黑盒全用例 PASS（Temp/gui-231/）；GUI 已验证
- 发版：✅ **已发布**——D2026-1001-05 S0：R3 攒批前提（owner 未实测）被 owner 新指令显式豁免（"不考虑实测问题…实测发现问题再修"），攒批解除立发（原"暂不发"行作废）

## 2.4.0 —— 界面交互收口批（D2026-1001-05 S1+S2，国庆冲刺收口）✅ 已落库并发布（2026-10-01，tag v2.4.0→9f1829f release/2.4.0 分支制+Release id 401022313：单 setup.exe 33,571,466B+SHA256SUMS 哈希核过 sha256 A10C6711…8D72B，notes 只写本版；构建 run 36871376836 绿；main 前进 2.4.1.dev0=第 8 步）

- ✅ 批 1 S1 原生 alert/confirm/prompt 替换自制模态（#appModal 单例，AppModal 三形态 Promise 封装+重入守卫+alert 隐藏取消键+永不 reject；5 处调用点替换；preventDefault 同步序条款）——解冻 id 176→177
- ✅ 批 2 S2 首启初始化（first_run 一次性引导横幅+marker 键翻转句 refine_save_stage_settings(settings={first_run_seen:true})——HRO-1 修正路径，黑盒实证翻转调用参数精确）——解冻 177→178 恰达上限
- ✅ 批 3 ⑪收尾扫查固定小节：双通道扫查零新增死规则（6 候选全甄别为注释误报/沿袭豁免，本批新增规则全在用）
- ✅ 批 4 docs：S4/S5 评估文档（候选池大件评估-d1001-05.md）+三级评议归档（D2026-1001-05）
- 验证链：红线钉+静态钉 45 passed（钉⑤ 178 双向）/全量 1601+4 持平/gate 丢失 0+新基线 178/190/Mimosa 29 零新增（seal 92048012）/黑盒全用例 PASS（first_run 两分支+marker 断言/prompt 双段全链/重入守卫/遮罩+Esc/alert 无取消键/暗色+窄窗，截图存 Temp/gui-240 归档位置）；GUI 已验证
- 发版：✅ **已发布**（2.4.0 收口单发；国庆冲刺计划内容完结）

## 2.5.0 —— 2.4.0 实测反馈修复批（D2026-1001-06，owner 实测四条+词典链真 bug）✅ 已发布（2026-10-02，tag v2.5.0→eb0346c release/2.5.0 分支制+Release id 401160543：单 setup.exe 33,579,109B+SHA256SUMS 哈希核过 sha256 6382F28A…FAB7，notes 只写本版；构建 run 36892061454 绿；main 前进 2.5.1.dev0=第 8 步）

- ✅ 修复 A 词典链真 bug+完整版选版（owner 反馈 1+开工评议 HRO 实证升级）：**sudachipy 0.6.11 加载 20260723 core = Invalid header 静默失败实证（2.4.0 词典下载收益未生效）**→升级 `sudachipy>=0.7.0,<0.8`（0.7.0 LOAD_OK+全量零回归）；ja-dict extra 移除（显式复议：D3 支柱因新实证失效，统一下载式）+test_pyproject_meta 防捆绑钉重写+ci.yml 改 `.[dev]`（真 sudachi 覆盖接受退化落口径）；**sudachi_full 完整版变体**（CDN 直链 137MB+受控定 pin sha256 eb6d0220…871e+白名单扩 CloudFront+kind 三联+SystemSummary 分母 DICT_KINDS.length）+加载优先链 full→core+_extract_dic 流式+磁盘预检（zip+2×extracted）+_http_get 流式落盘
- ✅ 修复 B AI 分析路径守卫统一（owner 反馈 2）：refine_ai_analyze `_resolve_safe_path`→`_validate_user_directory`（E:\ 型字幕目录放行，与导读同口径）；差分回归四断言；guide_path_denied 文案改值；stderr_tail 摘要进错误信息（200 字符）；云 provider 发送前 AppModal.confirm
- ✅ 修复 C 质量报告加载链（owner 反馈 3）：载入新报告清旧 AI 结果（refineAiResult+lastAiSuggestions=null）；AI 分析 E:\ 路径点透随修复 B；子现象"无实际按钮"待复现（源码层按钮/绑定均在）
- ✅ 修复 D 角色卡两处联动（owner 反馈 4）：阶段A/B 角色卡旁"去编辑"跳转两分支（目录内精确打开含 canonical→tag 映射/目录外降级跳转+提示）；保存后动态回落提示——钉⑤ 178 零耗（class 承载）
- ✅ ⑪ 收尾扫查固定小节：零新增死规则（6 候选全甄别注释误报/沿袭豁免；新增 CSS 全量命中实证）
- 验证链：红线钉+静态钉 45 passed（钉⑤ 178 零耗）/全量 **1602+4**（+1 新行为钉）/gate 零漂移（178/190）/Mimosa seal 92048012 等待复核/secret 1 hex 甄别放行（full pin 数据摘要非凭据）/黑盒：词典 4 条目+摘要卡 2/4 新分母+full 变体详情+跳转按钮×2（截图 Temp/gui-250 归档位）；GUI 已验证（勘正注 D2026-1002-02：钉⑤数字系批 5 并入前口径，批 5 解冻 178→180=现基线，见 D2026-1001-07）
- 发版：✅ **已发布**（2026-10-02，见节首行；"提案待确认"行勾账=D2026-1002-02，release 记录见 D2026-1001-06 风险跟踪①追记）

## 2.6.0 —— 质量闭环（轨道 B 落地；D2026-1002-02 立项）✅ 已发布（2026-10-02，tag v2.6.0→ea7de25 release/2.6.0 分支制+Release id 401359943：setup.exe 33,636,399B sha256 b5a61673…7e4 与 SHA256SUMS 核过，notes 只写本版；构建 run 36925386474 绿；main 前进 2.6.1.dev0=第 8 步；含发版前 owner 反馈修订 D2026-1002-05——tag 撤销重打）

**需求信号（owner 2026-10-02，三点）**：①AI 分析完质量后应给出建议并可直接修复，不然分析没意义（**轨道 B 触发源到达**）②S4 改向——跨片质量趋势不做独立看板（无实际意义），应服务于 AI 质量分析后的建议与自动化调整 ③配音链路（TTS）没必要不做；改为"AI 质量分析加载音/视频进行重点分析"（与 AI 分析结合大幅提高复核清单的正确解决率）。

- ✅ 批 1 闭环主线（轨道 B 核心）✅ **已落库**（2026-10-02，D2026-1002-02-批1：开工门=owner 追认✓；二级评议两 HRO 采纳——HRO-A 幂等守卫改 GUI 层台账感知（执行器实证无跳过）、HRO-B dry-run 预览落弹窗（B10）；C1-C8 全落实；push 前双轴评审修订（进度契约矫正/兜底惯例/弹窗汇总补全，见批清单 §10）；全量 1612+4/gate 新基线 183/191/Mimosa 31 零新增/黑盒 B1-B8+B10 PASS、B9 部分；预算钉⑤ 183、静态键 191 余量 1；详见 decision-log 与 d260-批1-批清单.md §9-10）——原范围：AI 分析（本地/云端 provider 均可，云端独立设置+发送前确认已有基建）→ 结构化建议清单（对齐既有行动类别映射；**术语冲突类不纳入自动重翻目标=b2 红线**维持）→ 报告页**一键批次修复**（复用 1.3.1 重翻执行器 --action-retranslate/--entries 零件；人工点击发起=HRO-1 条件③"提案式放行而非全自动写盘"的落法，无人值守全自动须显式复议条件③）→ 修复复验（有限子集重检+结果回写）。**HRO-1 四条件落法**：①威胁模型=批 1 开工前落盘送评（云端发送内容范围/密钥面/留存边界；批 3 云端音频并入同一威胁模型）②云端不进缺省=现状已满足（缺省跟随阶段A=本地）③一键批次放行（见上）④行动台账记 provider/请求上下文（b3）+有限子集复验口径；b2 与立项评审 5 问清单入批 1 批清单二级评议固定议程。**批 1 硬化条件（立项评议 D2026-1002-02 采纳，开工评议逐项勾验、不得停留议程层面）**：复验口径成文（子集选取/规模上界/接受标准/回写语义/失败处置；起步=低置信子集重跑 AI 分析差异对比复用现役管线，不新造复验引擎）｜成本配额护栏成文（单批条目上限+预估成本进确认弹窗，无机制不开云端批量入口）｜TM·词库写入闸（三开关缺省不变批次流保持）｜GUI bridge 直调 action_retranslate 模块本体禁旁路重写+--action-source 来源解析成文｜台账 old_text 唯一回滚依据禁无台账直写+批次中断恢复语义｜批 2·3 扩展缝预留（建议 schema 版本化+prompt 组装钩子白名单）｜审计积压①②触发核查｜「一键」入口钉死报告页（黑盒：成功/部分勾选/取消/dry-run 预览+复验回显）。**四条件落法呈报 owner 追认=批 1 开工门。**
- ✅ 批 2 聚合数据层（S4 改向落地）✅ **已落库**（2026-10-02，D2026-1002-03：开工评议 C1-C7 全采纳；口径定案三件含两处降格声明（CPS 密度计数≤20/TM 入库量=命中率代理）+枚举序 generated_at 降序最近 20 片+聚合对象 N/A 纯建议；新模块 aggregate_stats.py 只读层（tm.py 零改动/mode=ro/降级）+quality_advisor 第四 DATA 块 additive 注入（默认开 aggregate_stats_inject 负向钉不进指纹）+系统提示列举句泛化；全量 1624+4/mypy 0/冒烟 OK/gate 零漂移/Mimosa 31 零新增；钉⑤静态键 0 耗；详见 d260-批2-批清单.md 与 decision-log）——原范围：跨片聚合读取层（TM 命中率走势/CPS 分布对比/风险密度统计，数据源=TM 库+各片质量报告 json）——注入批 1 AI 分析上下文（跨片基线对照进 prompt）+作为自动调整依据（阈值/白名单建议以聚合基线为据）；**无独立 GUI 页=钉⑤零耗**；聚合统计口径随批清单二级评议定案；自动调整边界=只出建议+确认、不改默认值（不得触碰 adaptive 默认开启硬化门 origin:real 0/30，decision-log:1315-1316），纠缠过深则降格「仅出建议」备选；聚合对象清单（哪些阈值/白名单）批 2 批清单定案时具名。
- ✅ 批 3 媒体重点分析（原 S5 位改向；**配音链路 owner 拍板不立项**）✅ **已落库**（2026-10-02，D2026-1002-04-批3：owner 四项决策落地——**云端不接受→路线 B 独走零出域**（A/C 阶段 2 不启动）、批次 E 不再启用（定阈退路=初值标"未定阈"）；开工评议 HRO 采纳方案 a（qwen 改候选挂账——不点火不排期，启动前置=HF 布局核实+加载 smoke+二级评议；推荐清单两件保留）；段 1 ASR 模型管理（探测三级候选/--selfcheck 真实契约/引擎页 ASR 卡/whisper-large-v2 推荐下载 sha256 pin 实测核算）+段 2 对照链（切片≤20→上游 env 子进程重转写→第五 DATA 块注入+知情行）；全量 1638+4/mypy 0/gate 新基线 190/192（静态键恰达 cap，扩 200 记下批首件）/Mimosa 31 零新增/黑盒 A1-A4 PASS；详见 d260-批3-批清单.md §7）——原范围：AI 质量分析支持加载音/视频，对疑似漏听段/低置信条目做媒体切片重点复核；复用 media_path 契约+疑似漏听检测层（suspected_missed_speech schema 冻结）+试听 UI 基建；选型材料（docs/design/批3-媒体重点分析-选型材料.md）定稿归档 D2026-1002-04；连带项=10~20 片真实媒体定阈（2.0 DoD 挂账）随批实测补（批次 E 不再启用，挂未来新片源）。
- 实施序：批 1 → 批 2 → 批 3（批 2/3 均以批 1 闭环为服务对象）；每批独立批清单+开工评议+验证链+黑盒；GUI 新增 id 走钉⑤解冻预算表（现 191，i18n 192 恰达 cap，扩 200 记下批首件）；批 1 动工时点=owner 追认四条件落法后。
- ✅ 2.6.1 修订：ASR 验证可选化+模型推荐制（2026-10-02，D2026-1002-06，owner 反馈收口）——**删除项目内下载链**（dict_manager/_ASR_DOWNLOADS/进度快照/流式校验、asr_env 薄委托、api refine_asr_download*、前端下载按钮+进度三件套+1s 轮询全删），改**推荐制**（ASR_RECOMMENDED_MODELS 只给 url/bytes/sha256 自备元信息；status 增 recommended（present/path/expected_path）+models_dir/cache_dir 落位指引）+**验证可选化**（media_crosscheck_enabled 默认 True→False，引擎页开关/user_settings/env/CLI --media-crosscheck-enabled 0|1 开启，GUI KV→CLI 透传）+**契约修正**（探测枚举两处/whisper 只认一处=假阳性，resolve_model_dir 使探测与加载同序：~/.cache/whisper 优先不传旗标、数据根 models/asr 经 runner --model-dir；qwen 改候选挂账不排期，启动前置=HF 布局核实+加载 smoke+二级评议；静态键零消耗，id 等量换血 -3/+3 仍 191）。
- ✅ **2.6.1 已发布（2026-10-02，tag v2.6.1→release/2.6.1 头 68f13e1，Release id 401896944：setup-2.6.1.exe 33,764,476B 哈希核过 3347b7d8+SHA256SUMS；notes 只写本版）**
- ⬜ **2.6.1 工作区重整+校对视图（2026-10-02 立项，D2026-1002-07；owner 四点反馈：质量与建议提到工作区/新增校对 TAB 视频字幕对照 SmartSub 式可选向/布局美观度对标 SmartSub 重整/校对组件规划已答=ffmpeg 既有依赖即可、ASR 仅批 3 可选联动）**——critic 有条件支持无 HRO 全采纳，批 1 开工门=决议归档。批 1 UI 基建：静态键 cap 192→200 解冻提案（首件，耗 2-4 个）+导航三分（工作区=字幕翻译/校对/质量与建议；设置=引擎与模型/词库与模板/高级参数，nav_group_quality 改字不加键）+间距 token 化（只增不改）+质量与建议页来源条折叠+布局变体统一+视觉三小件（✅ 已落库，见 d261 批清单）。批 2a 校对容器：播放器 spike 首件（file:// 直播+timeupdate/currentTime 精度+seek+10ms 补偿实证=验收口径）+右栏全隐迷你状态条（三 id 归属批 2a 评议定；✅ 归属+UI 规格已定案 D2026-1002-08=独立四 id reviewStatusBar/Dot/Label/Fill+makeStatusManager 工厂+翻译侧零改动，条件②已闭环，id 总额仍待批 2a 预算表逐段预演 ≤9）+SRT 编码嗅探（BOM→utf-8→gbk）+ffprobe 三态+手动转码临时预览+跳转入队接口空实现（{timestamp,label,source}+契约钉）+id 预算分段列名目标 ≤10。批 2b 校对编辑：双向联动五要点+行内编辑+保存（重编号确认+另存为/备份）；200-800 行不虚拟化。批 3 联动增强：对照链/AI 分析疑点段进校对视图+校对页 ASR 可选入口（承诺件）。设计红线：单一编辑器实现/状态单行/列表播放器同真源/新文案全 JS 态 MSG 键；程序分界=静态键 cap 走解冻提案、DOM id 走预算表+二级评议。

## 2.8.0 —— 压制成品输出（D2026-1007-03，当版本全部完成含 NVENC）+ CT2 引擎顺延下版本 ⬜ 立项（2026-10-07，待开工令）

- **三批（压制输出=硬字幕成品；MVP 定稿/条件 C1''-C7''+owner 追加拍板八条/P0-P3/R1-R10 全文见 decision-log D2026-1007-03）**：批1 CPU 编码链+队列+护栏（受控生成者注册制/外部入队接口/会话结束钩子骨架，可独立验收）→ 批2 NVENC 硬件后端（当版本必做，双检探测+显因）+参数面板（AppModal 三分区）+预设体系 → 批3 自动化管线集成（用户勾选开关：批量翻译→批后自动压制/单个→单个后自动压制；lms unload 清场+双向互斥）+音量增益。
- 关键定案（owner 追加拍板修订）：**10bit 删除，8bit 固定**；**AV1 预设参数+滤镜链=缺省默认**（lanczos+hqdn3d+deblock+unsharp 实串复刻，**链参数可调随预设存取**——owner 重申自定义参数用户可设）；三挡=调码控/速度档参数实现，滤镜链固定；格式 H.264/H.265/AV1 × 后端 自动/GPU(NVENC)/CPU；分辨率 保持原样/720p/1080p/1440p/2160p；码控=画质档 ‖ 目标码率 VBR（2-pass 挂候选）；预设三层；黑名单 25 件；ffmpeg 来源=PATH→按需下载兜底（full 变体含 libsvtav1）→随装后置；UI=B+（校对页入口+模态面板+全局队列底条）；自动化工作链参考 [VideoCaptioner](https://github.com/WEIFENG2333/VideoCaptioner)（ASR→断句→LLM 优化→翻译→合成范式）。
- **VideoCaptioner UI 借鉴（研究已出，进批清单素材）**：参数面板按输出档位条件显隐组织（批2）；流水线镜像升级阶段链 stepper+「翻译完成后自动压制」开关状态行（批3）；交付闭环三件套=活动流完成行+进度 error 变体+失败行内重试（批1·3）。明确不抄 qfluentwidgets 视觉/InfoBar/右键菜单/自动弹窗；**字幕样式实时预览 owner 裁定不做**（2026-10-07）；**字幕缺省位置=底端居中（对齐 owner Shana 预设）**。预算：静态键 +6 内、id +5~8、CSS 2~3 组件族。
- **版本策略（owner 定）**：当版本提出的全部当版本完成（NVENC 不顺延、无降级砍范围），下版本=修复+新功能集成；**CT2 引擎顺延下版本立项**；2.7.5 C10 复测门→发版不受影响；2.7.6 关闭。

## 2.7.5 —— 真机三反馈修复批（媒体通道 origin+试听推断剥链+批量修复模型解析；D2026-1007-02）🔶 六件已收口（2026-10-07，五笔 c5fa8b7/0ba9982/faee1d5/16b02c7/9da9d40，main=9da9d40；基线 2049+4 只增；Mimosa 36 零新增 seal d8da7692；黑盒五点过）；**待 owner C10 实景复测门（真机：修复发起 model_used 非空+校对页视频直连+试听 direct 有声+无红横幅）→发版**

- **批序 P0**：F1 校对页/试听媒体通道 origin 修复（`asset_page_url()`=as_uri+UNC 回退+启动 protocol 自检；pywebview 钉 `>=6.2,<7`；tools/spike_review_video.py 吸收升格为单一媒体链路回归脚本：版本断言+protocol 断言+4 媒体 file:// 矩阵+audio error 可见性+非零码契约）+F4 试听推断 leveled 逐层剥链（扩 .merged）+边界感知前缀兜底（唯一精确命中即停，多候选 fail-closed）+F7a 批量修复模型解析补链（`resolve_fix_model_config()` 单一函数：阶段B KV 空→整组回退阶段A 三元组一致；两处皆空拒绝发起；修复卡补「修复将使用」明示行）。
- **批序 P1**：F2 播放错误文案分型（`codec_probe===true` 且 code 4 才示通道异常，audio 监听补 no-src guard 入错误槽）+F3 校对列表时间列溢出修复（11em 钉死→max-content）+F5 试听失败槽直通「选择媒体文件」（含 inferredMediaCache 按 guide 清理）+F7b spawn 前本地端点连通预检（resolve 之后跑，/v1/models 超时 5s 常量，不验模型加载）+F7c 可观测性（stdout_tail 落 gui.log+失败文案附台账 top1 reason ≤200 字符，复用 `_read_ledger` 零新增 open 写读点）。
- **批序 P2**：F6 上次手动媒体目录持久化为推断附加搜索目录（跨目录候选集不合并，同目录优先）。
- 条件 C1-C10+两微项随批闭环（全文见 decision-log D2026-1007-02）；**C10 实景复测门=owner 真机**（修复发起后重翻记录 model_used 非空+校对页视频直连可播+试听 direct 有声+启动自检 protocol 输出留档）。硬约束：F1+F4+F7a 同批先行。

## 2.7.4 —— 质量报告导读可读性+批量修复确认框完整化+试听媒体路径推断+TM 入库埋点版 ✅ 已发布（2026-10-07，Release id 405140722：SubTrans-setup-2.7.4.exe 50,909,098B sha256 9EEB453F…382A2 与 SHA256SUMS 一致+公开 URL 回读 MATCH；tag v2.7.4→799d20e release/2.7.4 分支制；构建 run 37529914240 success；main 前进 2.7.5.dev0=8816131；全程详见 decision-log D2026-1007-01 与 CHANGELOG；黑盒连带修复 esc() 全局转义序+Chrome146 line-clamp 失效两笔老 bug）

## 2.7.3 —— 词典链自锁修复+下载镜像提速+ASR 状态口径对齐+收编过滤+词典停止版+Console 可视化+启动缺陷修复版 🔶（件1-5 已收口 2026-10-05（D2026-1005-05 开工门）；件6-8 已收口 2026-10-06、件9 已收口 2026-10-06（D2026-1006-01 执行追记，main=a471408）；基线 2000+4；待 owner 真机走查+件②点亮后发版）

- ✅ **件1 词典下载 WinError 5 自锁修复**：grammar_hint 分词器单例 reset（尽力释放语义：_init_lock 内清实例+cache_clear→重试 os.replace 一次→仍 PermissionError 人话化含「重启生效」提示）+PermissionError 窄域捕获人话化（不并入网络/校验异常类防误触跨源轮换）+失败路径清理 .extracting/.downloading 残件+回归钉。
- 🔶 **件2 下载镜像提速（代码接线完成；点亮=owner HF 上传后生产路径核验转 verified）**：HF 镜像通道（owner 上传 137MB zip+large-v2 3GB，Apache-2.0/MIT 许可声明留档，原样字节副本）；dict_sources.json mirror 源 sha256 沿用既有 pin 零放宽+URL 钉 /resolve/<commit-sha>/；`_URL_HOST_ALLOW` 域名集=实测 hf-mirror 重定向链后定（HRO 收窄：禁预设写死，白名单外域名回评议）；**点亮门=生产代码路径（_http_get+逐跳守卫）实下载 sha256 比对一致**；auto 链镜像优先（仅 sudachi_full，失败轮换回 cloudfront；core 维持 pypi→tuna 不动）；未点亮前 GUI 口径不虚亮。
- ✅ **件3 ASR 状态三口径对齐+下载缓解引导**：下拉空保存值占位项「未选择（点选即保存）」（消灭单选项假选中）+红绿灯去硬编码 'large-v2' 兜底+摘要卡口径统一（同键族 5 消费点全查：三 UI+asr_runner/quality_advisor 降级缺省）；新增 i18n 键 app.js MSG 与 strings.py 双表同步；系统代理两跳自动+--dict-from-file 离线导入引导文案；GUI 黑盒空/存两态钉。
- ✅ **件4 文件夹收编智能过滤（D2026-1005-04，owner 真机反馈：.merged.whisperjav 才是产成品）**：select_srt_folder 黑名单排除三类（`.pass1/.pass2` 复用 pass_disagreement `_MARKER_RE` 单一事实源不排 merged、`_refine_[A-Za-z]` 中间稿、`_final_[A-Za-z0-9_-]+` 终稿多语言码——评议修订放宽）+返回 skipped 明细+console 两行可见化（主行 addedFilesFromFolder 改值+明细行新键）+空态第四分支=后端 strings.py 新键（全滤光人话+「添加文件」指引，零前端键零 id）+单文件/拖拽不过滤+CLI find_srt_files 默认口径不变（脚本契约）+scan_srt_folder summary 透传 skipped。
- ✅ **件5 词典下载停止按钮（D2026-1005-04，owner 真机反馈：直连慢需主动停换代理）**：协作式停止（threading.Event+分块检查点含解压相位+**会话 ID 绑定 stop 端点防误杀新下载**（替代评议 HRO 采纳）+残件清理并件① try/finally+快照 phase="stopped" 独立字段）；UI=主键原位变停止（btn-danger+stop_btn 复用，**id 预算 0**）+四态状态机+停止后源 pill 立即解锁+过渡兜底（超「单分块超时+2 拍」本地按失败收口防无限停止中）；语义=放弃重下不做暂停续传；**ASR 3GB 档维持无取消（D2026-1003-06 边界修订+判据=尺寸与重下成本不对称入档防回翻）**；新 MSG 键 dict_stopping/dict_stop_pending/dict_stop_note+后端键 2 个。批序：件①→件⑤（残件清理复用硬依赖）→件③→件②；件④独立可并行。
- ✅ **件6 P1 启动缺陷修复（D2026-1006-01，bd291da）**：refreshPipelineMirror 两处 `$()` 换 document.getElementById+作用域审计等价强判据钉（全文件 `$(` 总数==IIFE 区间总数，265 处全在区间内）+回归钉四断言（函数体无 `$(` 引用/IIFE 外零污染/gui_initialized 可达序/链B 语法徽章+ASR 预热完整）。执行纠正：词法作用域按定义位置解析，IIFE 内调用（loadRemote→链B）同样炸——两链同根因确证。
- ✅ **件7 流断诊断+修复（D2026-1006-01，e540060）**：诊断证据链（decision-log 执行追记六）：排除 CLI 管道/pump 解码/DOM/MSG 键/spawn 参数/console 标志；实锤①PyInstaller 无视 PYTHONUTF8/PYTHONIOENCODING（frozen stderr=GBK 乱码实验实证）→`_harden_stdio()` isatty 分叉（管道强制 utf-8/tty 本地码页零变化）；实锤②fetchLogs 嵌套 status try+打点前置单点结构→轮询先行+打点防弹+双通道解耦；promise 链嫌疑以防御重排失效化+件⑧结构化层第二通道兜底（留 owner 真机终验）。
- ✅ **件8 Console 结构化活动流（D2026-1006-01，9c1d3b7+1af0b26）**：pump 闸门 P0（裸 JSON 零泄漏+gate0 人话行 ev_gate0 信息保全）+翻译日志全量落盘 gui.log+ActivityStream 六类差分打点（阶段/文件✓✗/风险带 file 归属/错误/心跳超时/完成摘要 task_summary 透出；phase_progress 不进）+原始日志折叠默认收起+localStorage 持久化+500 行裁剪仅 DOM（_lines 会话全量）+导出/复制+伴生 bug 全修（files_completed/files_total 语义+files_total_expected/error→failed 终态保护/chip 四态/risks 文件归属）+FROZEN 213→217 记档（风险跟踪②流程）。黑盒六点全过（IAB 物理输入失效以程序化 click 代理完成，已声明）。
- ✅ **件9 阶段B 预检 TTL 卸载缓解（owner 真机 mufr-006 现场拍板 2026-10-06，a471408）**：双模型常驻+LM Studio TTL 空闲卸载，末位文件阶段A 恰好把审校模型空闲顶过 TTL 线→阶段B 预检不在载+无 lms CLI+JIT 未开→文件失败跳过（伴生 bug 修复仅使失败可见，引擎侧行为可复现）。缓解=ensure_lmstudio_model 无 CLI 分支前插入有限等待复查（3×15s，纯 HTTP 查 state 零 GPU 占用）：命中手动加载自动续跑（ctx 失配告警放行）；超时落回现行失败+已等待时长；CLI 存在/未下载/不可达路径零变化；等待窗口内 state 查询抖动按续查。4 用例钉。

## 2.7.2 —— 字幕入口修复（ASS/SSA/VTT 导入点亮）+ASR 模型元数据核验版 ✅ 已发布（2026-10-05，tag v2.7.2→b8abcfa release/2.7.2 分支制，Release id 403549433：SubTrans-setup-2.7.2.exe 50,839,755B sha256 69264DF8…E9C1 与 SHA256SUMS 核对一致+公开 URL 回读下载复验一致；构建 run 37285101270 绿（smoke 全链）；notes 只写本版；main 前进 2.7.3.dev0；发版期 windows-3.13 腿 flake 一次（test_effective_dir_blacklist_falls_back，同 commit 重跑自愈，横切观察项第 2 例））

- ✅ **件1 字幕入口点亮（D2026-1005-02，fix 非 feat）✅ 已落库（2026-10-05，381cf5c+a1c1952 推送 main；黑盒 T1-T3 PASS+补修复验；基线 1930+4→1937+4；Mimosa 36 零新增 seal 9e835baf；code-review 两轴过）**：2.6.4 承诺兑现+对话框回归修复（2.6.4 起「添加文件」被非法 filter 串整体封死连 .srt 也不可用，2.7.1 真机走查暴露）——strings.py filter 改合法写法 `ASS SSA VTT 字幕 (*.ass;*.ssa;*.vtt)`（pywebview 描述段不容斜杠）+拖拽白名单与前端二层过滤放开 .ass/.ssa/.vtt+拖拽文案去 .srt 硬编码（addedViaDrop/skippedNonSrt）+source_header 标题改值（追认项可单项回退）+目录收编保持 *.srt 增「有 ASS 无 SRT」分支提示（no_srt_in_folder 改值）；测试三层钉（精确值钉改合法串/parse_file_type 直测钉断言返回值——daily CI 无 gui extra 恒 skip 由 gui-probe 与本地实跑/全腿静态钉描述段无斜杠）；**输出口径维持 SRT**（保 ASS 格式另立项）；发行说明按「2.6.4 承诺兑现+回归修复」口径。详见 decision-log D2026-1005-02。
- ✅ **件2 ASR 下载元数据逐档核验（d271-asr-批清单 版本梯队表）✅ 已落库（2026-10-05，31c30d3；openaipublic 实下载 sha256 字节级核验：small 483,617,219B/9ecf7799…e794、medium 1,528,008,539B/345ae4da…dcb1——medium 首下 404 教训=URL 段必须取自上游 whisper/_MODELS 表记忆哈希不可信；五档 .pt 全核验转可下载，qwen3 仍 planned；配套 test_gui_api 两处设置存储隔离防本机态污染，owner config 只读未动）**：tiny/base/small/medium 下载元数据逐档核验+sha256 补全，核验一档转一档（tiny/base 已于 2.7.1 顺手核验通过转可下载）。

## 2.7.1 —— 安装版 ASR 探测修复+模型管理面板 ✅ 已发布（2026-10-05，tag v2.7.1→87f0002 release/2.7.1 分支制，Release id 403198677：SubTrans-setup-2.7.1.exe 50,828,884B sha256 01769C01…77B56 与 SHA256SUMS 核对一致；构建 run 37232463479 绿（含 UTF-8 热修重建）；notes 只写本版；main=2.7.2.dev0=f41e836+1126df4；owner 从 GitHub 下载真机测试中）

- **件1 探测修复三件（D2026-1005-01）**：asr_runner 随包（spec datas 单文件+定位函数 frozen/dev 双形态+脚本直调优先 -m dev-only 回退）+**secrets.py 劫持修复**（脚本直调 sys.path[0]=refine 目录劫持标准库 secrets 致 whisper 导入链炸——sys.path 自清+双回归钉）/ffmpeg 泛化（PATH→上游 env Library\bin 等候选→抽片显式绝对路径）/失败三分类 triage+stderr tail。
- **件2 红绿灯+提示归一**：状态行三色点（复用词典 dot 范式零新增 id）/删 asr_entry_hint 行+asrRecList 折叠区（失配文案「项目不内置下载」消灭）/删 qwen disabled 占位。
- **件3 模型管理面板**：AppModal kind='models' 720px（路径栏/未适配 banner/三档分组折叠/速度精度五格点阵·静态评定/推荐★/变体展开/行内进度+增量 MB/s/诊断网格/三态双门控/_settle models 独立分支关面板不阻塞下载）。
- **件4 三落位探测+缓存**：whisper 缓存→数据目录→**HF hub cache（HF_HUB_CACHE→HF_HOME/hub→默认三级 env 链；文件族识别 ct2/transformers；限深限时 fail-soft）**；下拉合并去重来源标注；磁盘级快照缓存（config/asr_probe_cache.json，TTL 10 分钟，.gitignore 兜底）+首启空闲探测+总预算 90s。
- **件5 数据层+硬门槛**：ASR_RECOMMENDED_MODELS 2→6 条扩 tier/desc/spec/backend/variants/verified；**tiny/base 顺手核验通过（openaipublic 实下载 sha256 比对，verified=True 可一键下载）；small/medium verified=False 禁下载仅「自备」说明（owner 硬门槛）；large-v2 sha64 位顺修**。
- **件6 文档**：README 首启后台探测提示句；手册 2.5 章重写。
- **实现期抓出并修复**：runner secrets 劫持（黑盒前本机实测）+fmtGB 闭包不可见（RefineUI IIFE 内定义、AppModal 顶层不可见致面板渲染中断——models 闭包本地版修复）。黑盒 PASS（真实探测数据注入 stub：红绿灯/面板三档/三态 chip 双门控/路径栏/banner）。
- 待 owner 真机：全新安装包验证（runner 随包+红绿灯+面板+large-v2/tiny/base 下载+G 盘 HF 路径 title+下载中关面板后台继续）。

## 2.7.0 —— 品牌统一第 2 层+数据根统一+复审收尾+行为清零版 ✅ 已发布（2026-10-05，tag v2.7.0→cb46341 release/2.7.0 分支制，Release id 403129217：SubTrans-setup-2.7.0.exe 50,813,596B sha256 826BE5C0…D1DFE5 与 SHA256SUMS 核对一致；构建 run 37218792098 绿；notes 只写本版+钉扎重固定行动提示；发版链 Mimosa 36 零新增 seal 5c3ec2d6；main 前进 2.7.1.dev0=第 8 步）

- **批1 品牌统一第 2 层+数据根统一（全新安装口径，D2026-1004-04 拍板）**：GUI exe→SubTrans.exe+spec 改名 SubTrans.spec（docstring 全清）+DefaultDirName {autopf}\SubTrans+**数据根/Documents 输出统一 SubTrans（直接改默认值无迁移代码，owner 0 start 豁免原文入档）**+AUMID→Angelholl.SubTrans.GUI（常量+值级钉，永不变更纪律）+[InstallDelete]+uninstall.bat LNK6+Documents 提示串；批清单=docs/design/d270-批1-批清单.md（二级评议通过，C1-C5 已回写）；禁区表（AppId GUID/env 名/CLI 名/dev 运行时行为/numba 小写缓存目录等）；批1 首提交后 release workflow_dispatch 先行验证。
- **批2 A′ UX 复审清单逐项重审** ✅ 已落库（D2026-1004-04 批序第二批；批清单=docs/design/d270-批2-批清单.md 二级评议通过 C1-C3）：枚举收口=A′ 6 项+横幅事实核对全一致维持+非 A′ 带 title 9 项（历史"11 项"名单未留存、以全仓双源勘探为唯一基准，映射留痕 C1）；改写 4 项=fallback_local（事实修正=失败行级接管）+profile 两级化+dict_jieba_desc（EXE 捆绑语义）+direction_title 双源漂移（strings.py"指令卡"→"角色卡"）；全复用既有键零新键零 id，基线 1902+4→1905+4（+3 钉：双键结构钉+direction 三源同值钉）；**挂起上报两行为缺陷**（①auto_glossary 外层闸缺 GUI 拼装通道=学习写入配置层全局不触发；②--verbose 旗标 refine 包无消费点——均 CLI/GUI 通吃，文案随行为修，owner 拍板后另批）；候选池=direction 两级化/conflict_block+gl1+gl2 补 title（解冻提案）。黑盒：jieba 描述新文案渲染+高级参数 tooltip 运行态全过（stub 桥环境；主题切换依赖后端链未验=零主题改动不适用）。
- **批3 docs 勾账+文档级收敛（B 方案，D2026-1004-04）** ✅ 已落库（229bf8b）：roadmap 2.6.4 节状态勘误（限状态行）+.pytest-* 残留清理+.gitignore `/.pytest-*/` 兜底；**README/手册主推 EXE 单一安装方式+保留三形态说明+开发者 fork 指引（代码零删改）**；用户导向命令引用切安装目录 subtrans-cli.exe 语境（pip 语境保留）；README/手册 %LOCALAPPDATA%\SubTransJAV 口径随数据根更名同步；手册 1.1/1.2 标题纠正旧世代定位。
- **批4 行为修复（本版问题清零，owner 拍板「这版本发现了就是版本修」）** ✅ 已落库：①学习闸接线——GUI 勾选学习词库同拼 --glossary-learn+--auto-glossary（api.py，双闸 AND 语义；auto_glossary 刻意不入指纹注释固化 manifest.py）；②--verbose 接通三诊断消费点（TM 模糊注入逐条命中/闸门0 判定明细/A·B·final·复用四处阶段耗时，[VERBOSE] 前缀+cfg.verbose 门控+stderr 既有通道，缺省输出逐字节不变，phase payload/事件协议/产物字节三面零触碰）；批清单=docs/design/d270-批4-批清单.md（二级评议 C1-C4 回写）；基线 1905+4→**1909+4**（+4 钉）；verbose 真跑冒烟+学习闸端到端（glossary_learned.csv 增量）归 owner 真机走查。
- 挂起：CI 腿收敛（8→4）=deferred 候选未拍板不进 2.7（D2026-1004-04 ⑥）。
- 发版 ✅ **已发布**（见节首行）；owner 真机走查清单：全新下载安装→--where 显示 %LOCALAPPDATA%\SubTrans+无迁移提示→任务栏分组正常→勾选学习词库跑一轮看 config/glossary_learned.csv 增量→勾选调试日志看控制台 [VERBOSE] 行。

## 2.6.5 —— 词典链与 UX 修复版 ✅ 已发布（2026-10-04，tag v2.6.5→830ac23 release/2.6.5，Release id 402920447：SubTrans-setup-2.6.5.exe 50,816,598B sha256 AD5F9A77…87A02 核对一致+SHA256SUMS；notes 只写本版；CI 全绿+Mimosa 36 零新增 seal 9cc727ed；真机门② owner 真机 PASS"直连和代理下载没问题"）

- 段1 词典链+安装器六件（jieba 渠道四件套/下载链两跳直连重试+完整性校验+守卫+诊断/setup.iss 图标/候选A 坏行行号明细/候选B flake 闭账）+段2 UI 三项+#6（状态卡两行式/引擎页去外壳/词典入口收敛+失败诊断网格）+真机反馈轮（ASR 按钮溢出+品牌统一第 1 层 D2026-1004-02）——D2026-1004-01/02 全程记录。
- 发版后 main 前进 2.6.6.dev0（即时检查点）。

## 2.6.4 —— 输入侧扩展版（D2026-1003-05 立项）✅ 已发布（2026-10-03，Release id 402610079）

- **批1 TM 浏览/搜索 UI**（FTS5 标准库零依赖；词库与模板页新增区块，只读浏览；开工门=冻结包 FTS5 探测+同步策略 spike 对拍；验收门 C1 热路径/C2 迁移链）
- **批2 ASS/VTT→SRT 多格式导入**（统一"转 SRT 再进管线"，TM 指纹零影响；开工门=语义映射规格 owner 画押（C3 八项）+pysubs2 钉 <1.9 真实样本 spike，不合格自研解析器）
- **批3 收尾+发版 v2.6.4**（release 分支制；顺延出口=痛感优先，TM 搜索先发，ASS/VTT 可顺延 2.6.5）
- 预研：worktree feature 分支闲时进行（D2026-1003-05 C4 隔离纪律）——已随批1/批2 落库

## 轨道 B —— 云端闭环 ✅ 已立项为 2.6.0（D2026-1002-02：2026-10-02 owner 需求信号到达；批骨架与 HRO-1 四条件落法见 2.6.0 节）

- ~~⬜ 放行评审（HRO-1 四条件）→ 提案式自动（自动分析+自动提议+批次人工放行）~~ ✅ 触发=自动质量闭环真实需求信号已到达（owner 2026-10-02），并入 2.6.0 批 1；四条件落法呈报 owner 追认=批 1 开工门（D2026-1001-03 第①项闭账）
- ⬜ A′ UX 复审清单随 B 落地逐条重审（2026-10-01 确认随 B，防过期条款，D2026-1001-03 第②项。计数勘误（评议员 [MATERIAL_CONFLICT] 采纳）：菜单"13 项"与在案 decision-log:1387"未改的 11 项入复审"不一致，以 :1387 口径为准（A′ 已改写=横幅 1 键+6 项 tooltip 两级句式）；若 13=11+2，2=glossary_learn/conflict_block 两无 title 属性控件；逐项枚举随 B 启动时落盘）

## v2.1+ —— 未规划（需 owner 立项；候选池 2026-10-01 全量复核维持挂起（D2026-1001-03）：~~跨片聚合分析独立页~~、~~配音链路~~（两件大件经 D2026-1001-05 S4/S5 降档为评估文档 docs/design/候选池大件评估-d1001-05.md 存照；**2026-10-02 owner 裁定：聚合改向并入 2.6.0 批 2（不做独立看板）、配音链路正式不立项、媒体重点分析新立并入 2.6.0 批 3**）/ 上游 v1.9.3+ 对齐（被动跟进；触发=owner 发起 whisperjav 升级或上游 release 通知到达，升级后必跑 6 例真实命名端到端测试防命名漂移复发，不设主动轮询，第⑥项）/ 引擎页左列表+右详情重构（D2026-0929-03 D 项，复核维持出局；重启条件=真机走查暴露引擎页布局痛点——触发源因 owner 豁免实测暂不可达，维持挂起不判出局）/ 代码签名 Trusted Signing（不立项；触发=非中文 issue 累计 ≥5 或 winget/Store 上架被接受——与双语改判条件同组信号防多头挂信号；计数口径见 D2026-1001-03；零成本前置=SmartScreen+哈希校验指引已补 README 与手册；自签证书不消除 SmartScreen 不作替代，第⑩项）/ ~~UI 改版轮（owner 2026-09-30 挂账）~~ ✅ 已立项落地为 2.1.1（D2026-0930-07，见上节）/ frameless 自绘标题栏（D2026-1001 拍板不做，D2026-1001-05 S3 HRO 采纳再次确认维持后置——重议条件=owner 对窗口外观再有诉求）/ ~~GUI 原生 alert/prompt 替换自制弹窗~~ ✅ 已激活落地 2.4.0 批 1（D2026-1001-05 S1）/ ~~首启初始化~~ ✅ 已激活落地 2.4.0 批 2（D2026-1001-05 S2）；全局字号/行高/间距节奏 token 化与密度重排（维持挂起——钉④禁区无诉求不得复议，触发=owner 痛点清单 G 节输入，触发源因豁免实测暂不可达；D2026-1001-05 S6 裁定不做自主审美轮）；~~Translator Panel 等残余死规则清理~~ ✅ 已兑现 2.3.1 批 3）

**新增候选（D2026-1003-02 登记，2026-10-03）**：**多格式导入（ASS/VTT→SRT）**（特性候选；开工门=语义映射规格化（帧精度/样式/多语轨降级）+ 库选型评估（pysubs2 为届时评估对象，其 1.9+ 要求 py≥3.12，本项目 requires-python≥3.10 须钉 <1.9）；核心 SRT 链不动——TM 指纹字节不变式 D2026-0930-04）/ **TM 浏览/搜索 UI**（特性候选；零依赖选项=标准库 SQLite FTS5（stdlib 实测 CREATE VIRTUAL TABLE 可用，无新依赖）；开工门=冻结包内 FTS5 探测随该批收尾验证同通道，不设独立 spike）/ **uv 开发侧契约**（不立项迁移：uv 环境仅 owner 个人实验用，不得宣判 CI 口径结论，canonical 验证归 .venv+CI；lockfile 再评估触发=依赖解析漂移事故再现或外部贡献者出现）/ **产品内品牌统一（SubTransJAV→SubTrans）**（~~远期候选 D2026-1003-04~~ → **已点火、分层执行中（D2026-1004-02，2026-10-04 owner 真机测试测试包后点火）**：第 1 层用户可见面（安装器产物名/AppName/弹窗/GUI 显示名/bat 快捷方式）随 2.6.5 落地；第 2 层（spec/dist 目录名+DefaultDirName+AUMID+历史遗留 lnk 清理）✅ 已立项 2.7.0（D2026-1004-03，见 2.7.0 节，全新安装口径）；第 3 层"本批不统一清单"（包名 subtransjav/数据根/Documents 输出目录/entry points/prog 名/AppId GUID，理由与远期路径见 D2026-1004-02））。

## 已完成版本存档

- ✅ v1.4 —— 质量闭环与通用化（2026-09-29，22efd22 收口；1.4.0 发布 2842693）—— 模型缺省重绑定 / SmartSub 借鉴 4 点 / 文本层巡检 / AI 质量分析 / 五 TAB 外壳 / 前置小件批
- ✅ v1.5 开工批 ——（2026-09-29，2824ea2/14653b6/92ca022/2058d29，D2026-0929-04）README 前置硬伤批（12 项闭集）+ 任务 0 验证（32 份真实 manifest 黄金配对 100%）+ 音频链路（media_path 契约，`--media-path` 进指纹口径）；**原 v1.5 剩余 4 项重编并入 2.0（2.0.0-beta/正式/2.0.1）**
- ✅ v1.3 及更早 —— 见 CHANGELOG 与决策日志

## 横切观察项（不占版本）

- ctx 16384：长文截断 / 术语链断裂 / 重翻触发率 / OOM
- gui-probe 月跳核对（2026-10-01：workflow active，手动探针先行全绿 run 36757171642＝collected 112/112 passed；**定时首跳核对=未发生**——03:00 UTC 后 3h+ 该 workflow API total_count 仍=2、event=schedule run 数=0；"未触发"为实证、"整点高负载丢弃"为推断（GitHub 已知特性），cron 已错峰 03:00→03:17 UTC（D2026-1001-03）；下次复核=2026-11-01 首跳，若仍未触发须升格处置（评估弃定时或转真机承载），不得仅再调时间）；~~B2 语料相关截止 2026-10-16~~ ✅ 门②已提前结案（2026-10-01，decision-log [B2 门②基线-20260926]）
- adaptive thresholds 默认开启前置债务：须先补 ≥30 条 origin:"real" 语料，未达标不得改默认开启（decision-log:1316 硬化条件；D2026-1001-03 统一登记）
- ~~refineGlCount 悬空（app.js:1965/2061 有引用无元素）~~ ✅ 已随 2.3.1 批2 修复（折叠卡头恢复 `<span id="refineGlCount">`，app.js 零改动；解冻钉⑤ 175→176，decision-log:2105；本行 2026-10-02 勾账 D2026-1002-01）
- 容器查询治本方案：不主动引入；触发=真机清单 F 节 DPI 探针实测异常再评估（decision-log:1939）
- 审计积压 4 项挂起（2026-10-01 复核维持挂起，decision-log:1395；D2026-1001-03 收编）：v2_outputs "done" payload 消费端核查（触发=新增/改动消费端或结构时先核查）/ premerge_max_gap_s 移出指纹（触发=任一指纹/断点/恢复路径改动立项时先出兼容分析，无方案不得动指纹哈希面）/ tools 一次性脚本债务（笼统挂起）/ _pid_alive AccessDenied（psutil 硬依赖不可达，笼统挂起）
- 首文件抽检历史观测（v1.3.0 时代，decision-log:1082）：考点=别停/クリ/部長で 误切；后续多轮实测无复发记录，触发=同类误切再现时复核
- test_effective_dir_blacklist_falls_back windows 腿 flake 观测（2026-10-05，批4 CI 首现）：windows-3.13 单腿 AssertionError（tmp 路径竞速类），同 commit attempt 2 自愈全绿；本地 3.12 五连绿；与 2.6.5 候选B flake 同模式；**2026-10-07 复发第 2 次（windows-3.12 腿，7177c18 首跑单败 rerun 自愈，D2026-1007-01 执行追记）——升格线已达成，登记钉测试竞速修复专项候选，如需动工另令**
- TM 入库层多句/异常长词条埋点观察（D2026-1007-01 件4）：refine_ai_apply_tm 仅记特征计数（长度/句末标点数）不记 TM 原文、debug 级、不阻断不改行为；触发=真机死键/误配再现或埋点数据显著，届时再决定入库打标方案
