# 2.7.1 批清单：ASR 探测修复+模型管理面板（D2026-1005-01 承接+owner 设计定稿 2026-10-05）

> owner 定稿原话：「就这版定稿，送二级评议」；四点拍板（面板形态 AppModal 720px/首启空闲探测+README 提示/点阵静态评定标注非实测/MVP 只核验 large-v2）+硬门槛（未核验档位禁止可点击一键下载）+红绿灯并入状态行规格。
> 设计来源：design-expert 方案（2026-10-05，关键决策 8 项+组件规格+约束自查 10 项全过）。
> 性质：UI 中+infra 中+数据层小-中；**不碰 runner 适配器、不改 asr_downloader 执行语义**。

## 一、范围（六件）

**件1 探测修复三件（D2026-1005-01 原立项；评议 C2 三坑钉）**
- asr_runner 随包按路径直调：**spec datas 补 asr_runner.py 单文件**（落点=onedir 内可定位处，定位代码与落点一致）；**新增定位函数集中解析**（frozen→exe 同目录/asr_runner.py；dev→仓库根）供 selfcheck/转写两处调用共用；探测/转写命令改 `[python, <runner 路径>, ...]` 脚本路径形态；**`-m` 回退显式注 dev-only**（frozen 数据根无包必失败），回退判定=runner 文件存在性优先；cwd 依赖随之消除（脚本直调不依赖 cwd；`--audio` 等参数保持 list 传参防中文路径拼接）；test_asr_env 导入图钉覆盖脚本直调形态（顶部仅标准库导入钉维持）。
- ffmpeg 探测泛化：候选=app 进程 PATH→上游 env 自带目录（<上游 python 目录>/Library/bin、Scripts、同级目录）→抽片 subprocess 显式传 ffmpeg 绝对路径（不再依赖 app PATH）。
- 探测失败三分类透出：模块缺失/whisper 导入失败/ffmpeg 缺失分列，stderr tail 进诊断网格。

**件2 红绿灯+提示归一（UI）**
- 状态行三色状态点：🟢就绪（四项全过）/🟡部分就绪（单项缺口，引导模型管理）/🔴不可用；复用词典卡状态点 class，零新增 DOM id（点挂现有 asrEnvStatus 元素内），探测结果单一来源驱动与文字同步翻转。
- 删 asr_entry_hint 独立行（说明并入开关 title 悬停）；删 asrRecList 折叠区（失配文案「项目不内置下载」随批消灭）；删下拉 qwen disabled 占位（操作面只列毕能用项）。
- 联动清洗：app.js asrRenderRecList/asrDownloadModal 调用链+.asr-rec-* 样式+相关 JS 态键，同批收口。

**件3 模型管理面板（AppModal kind='models'，720px modal-lg）**
- 布局：路径栏（whisper 缓存+应用数据目录，查看/打开/更改）→未适配 banner（全面板唯一长文案位）→三档分组（快速档·内存≤2GB/均衡档/高精档·≥8GB，内存门槛徽标）→每行=名称+一句话描述+速度/精度五格点阵（静态评定，标注「推荐参考非实测」）+大小+下载按钮；推荐★星标；变体行内展开（原版 .pt 可用✓/q5_0 量化·需适配）；下载行内进度（复用 .dl-progress）+MB/s（前端 1s 轮询增量计算）；失败诊断网格（复用 .dict-diag-grid，三分类字段并入）。
- 三态双门控：ready=绿 chip（可下载可选用）/adapter-needed=琥珀 chip（下载禁用+下拉不收录）/planned=灰 chip；backend_state 单一来源锁死「列出≠可用」。
- 下载语义：全量复用 asr_downloader（URL 三层校验/fail-closed 磁盘预检/sha256 落位/官方→镜像回退），无暂停/取消语义不变（D2026-1003-06 成文）；面板关闭下载后台继续、重开恢复进度。**评议 C3：models kind 不得复用 `_dlRunning` 布尔守卫（否则 `_settle` 命中 download 的 no-op 分支导致下载中关不掉）——`_settle` 扩 models 独立分支（关闭不阻塞）；进度恢复走 `_ASR_DOWNLOAD_PROGRESS` 进程内快照重开轮询**。
- 「分页」=三档分组+档间折叠+行内变体展开（owner 确认等效，真翻页不做）。

**件4 零配置三落位探测+缓存**
- 探测枚举 2→3 处：whisper 原生缓存（零配置主位）→应用数据目录 models/asr→**HF hub cache（评议 C4：枚举解析 HF_HUB_CACHE→HF_HOME/hub→默认 ~/.cache/huggingface/hub 三级 env 链，对接 owner 自定义盘符 G:\HuggingFace_Cache\hub\hub 事实；models--*/snapshots 按文件族识别格式：model.bin+tokenizer.json→CT2、.pt/safetensors→transformers；只读路径与大小；限目录深度+限时+fail-soft）**。
- 下拉合并去重+来源标注（校验序 whisper-cache>data-root>hf-hub 与加载序一致），只收 ready 项，完整路径 title 悬停。
- 首启空闲自动探测一次（不进安装器）+**结果快照缓存（评议 R5：磁盘级——落数据根 JSON 小文件，非进程内 dict；启动先显缓存再后台刷新；快照文件纳入 allowlist/禁区核对）**+**探测总预算上限约 90s**（多候选慢启动叠加防护）。
- README 提示句（见件6）。
- **状态判定同源（评议 R4）**：件2 红绿灯/件3 面板/下拉的 model_present 判定须共用同一探测结果对象（含第 3 落位枚举），禁双份维护。

**件5 large-v2 下载核验+硬门槛**
- ASR_RECOMMENDED_MODELS 条目扩字段：tier/desc/spec{speed,precision,recommend,mem_min}/backend{type,state}/variants[]（静态人工评定元数据）。
- large-v2 下载元数据实测核验（url/bytes/sha256）→一键下载可用；**硬门槛：未核验档位（tiny/base/small/medium）禁止可点击下载，只给「自备落位」说明；核验通过逐档转可用（2.7.2）**；顺手可提前核验 tiny/base（不阻塞、不承诺）。
- 下载进度快照复用 _ASR_DOWNLOAD_PROGRESS（后台续显）。

**件6 文档**
- README：首启后台探测提示句（「首次启动后应用会在后台自动检测上游 ASR 环境（短暂启动一次 Python 子进程，通常数秒）；检测期间不影响正常翻译操作，结果稍后显示在引擎页」）。
- 手册 ASR 章同步（模型管理面板/落位说明/后端兼容边界）。

## 二、版本梯队（owner 定，依赖顺序不乱；评议 R1 口径：**「可用」=可下载且当前后端可加载**，2.7.2 逐档转可用仅证明前者，状态迁移与适配器能力绑定防「能下不能用」）

| 版本 | 内容 |
|---|---|
| **2.7.1** | 本清单六件（UI 层+复用下载器，不碰 runner） |
| 2.7.2 | tiny/base/small/medium 下载元数据逐档核验+sha256 补全，核验一档转一档 |
| 2.8.0 | CT2/faster-whisper 适配器（runner 大项）+HF cache CT2 量化版可用化+面板转「可用」 |
| 2.8.x | 点阵静态值→实测数据（需基准测试矩阵，UI 不重做只换数据源） |
| 2.9.0 | qwen3 适配器（HF transformers 系；启动前置=D2026-1002-04：HF 布局核实+加载 smoke+二级评议） |
| 2.10/3.0 | 下载暂停/续传（须重新评议推翻 D2026-1003-06「无取消语义」） |
| 不做 | 真分页；安装器内探测；红绿灯新增 DOM id；模型删除功能 |

## 三、禁区/边界

- runner 适配器（CT2/qwen3）不进 2.7.1；面板对 adapter-needed 条目零可执行动作（展示数据）。
- asr_downloader 执行语义零改动（UI 仅镜像进度）；AppModal download kind 既有语义不变。
- 零新增 DOM id（FROZEN_IDS 214 不动）；静态 data-i18n 键零新增（cap 200）；**新增 JS 态 MSG 键 15-20 个——评议 C1 勘正：JS 态键不受静态 cap 200 约束（FROZEN_I18N_KEYS 只扫 HTML data-i18n 属性），由 test_gui_js_static.py 定向断言守护+死键清理承接；新增键必须有定向断言引用，删除旧键（asrEntryHint/asrRecList 相关）同步清理死键检查清单**。
- 深色主题全引用既有 token 零新增色值；图标全内联 Lucide（download/folder-open/chevron/star/info），无删除类图标；模型删除功能不设计。
- 既有元素 id 全保留（asrRefreshBtn/asrEnvStatus/asrModelSel/asrStatus/asrCrosscheckToggle/asrPythonInput）；表单控件底层类型不变。

## 四、验收门

1. 定向：ASR 相关测试+test_ui_phase3_redlines（FROZEN_IDS/FROZEN_I18N_KEYS 快照更新后双向）+allowlist+test_event_stream。
2. 全量 1909+4 只增（+解冻键快照+capsys 探测三分类钉）。
3. ruff 0+mypy 0+node --check。
4. **黑盒（stub 桥 web-gui-tester）——评议 C5 分层：黑盒只断言「重开恢复渲染」（mock refine_asr_download_progress 两段快照序列：下载中/完成）**；「下载后台继续」真实性归验收门 6 owner 真机。面板打开/三档分组渲染/三态 chip 与下载禁用态/红绿灯三态/路径栏/暗色主题抽查/诊断网格展开/下载中可关面板。
5. Mimosa 36 零新增；secret 0；提交五步；CI 绿。
6. owner 真机：重启后重新探测（红绿灯+状态行三分类）+面板打开+large-v2 下载走通+**下载中关面板→等完成→重开面板进度 done（后台继续实证）**+HF hub cache 落位（owner G 盘路径 title 悬停可见，评议 C4 验收）。

## 五、风险与回退

- UI 大改集中在 app.js ASR 区块+AppModal 新 kind；单批单提交可 revert。
- HF 枚举 fail-soft 设计防真机 hub 目录拖慢；探测总预算防多候选叠加。
- asrRecList 删除涉及调用链清洗漏项=钉红自证；新增键漏解冻=快照钉红自证。
- **release.yml smoke 增加一条 asr_runner 随包存在断言（评议 R6，与 jieba 双断言同款，防打包漂移）**。
