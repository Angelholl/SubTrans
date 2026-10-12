# SubTrans

> 由 SubTransJAV 项目迭代而来：原 JAV 领域专用字幕翻译工具，现为通用字幕翻译与精修工具链。

自带角色卡与词典的双引擎字幕翻译与精修工具链：LLM 提示词工程 + 术语自学习（自动学习默认关闭）+ 幻觉检测 + 质量审校，日→中方向开箱即用，配套 Whisper 转写工具链使用；初始自带通用模板，动漫、GAL 等领域可自设模板与规则。

A dual-engine subtitle translation & refinement toolkit (evolved from the SubTransJAV project) with built-in persona templates and dictionaries: LLM prompt engineering, self-learning glossary/TM (opt-in), hallucination detection and quality review, Japanese→Chinese out of the box. Works with Whisper-based transcription toolchains; ships with a general-purpose template, and domain templates (anime, GAL, etc.) can be customized.

## 下载与安装

- **EXE 安装包（主推）**：普通用户只需读本节——到 [Releases](../../releases) 页下载安装包（`SubTrans-setup-*.exe`）双击安装即可；系统要求与安装步骤见下方[安装](#安装) ①。
- 进阶 / 开发者：源码（`首次安装.bat`）或 pip 方式安装，见下方[安装](#安装) ②③。
- 首次启动后应用会在后台自动检测上游 ASR 环境（短暂启动一次 Python 子进程，通常数秒）；检测期间不影响正常翻译操作，结果稍后显示在引擎页。

本文档以中文为主体；英文用户可直接跳转 [English Quickstart](#english-quickstart)。

## 它解决什么问题

直译工具翻字幕的三大痛点：

1. 直白表述生硬尴尬 → refine 角色卡二次精修（净语翻译 / 审校抛光）
2. 术语/人名前后不一致 → TM 术语自学习（带准入门槛防污染）+ 强制术语表
3. 长句幻觉编造 → 幻觉模式检测 + 短语加固规则

## 核心特性

- 双引擎翻译 + 风格指令（tone）机制：阶段A 净语+翻译、阶段B 审校+抛光（角色卡模板可编辑）
- TM 术语自学习（准入门槛：低质翻译不进词库）+ 强制术语表
- **全链路自动化**（开关控制，缺省关）：一次翻译完成后自动串联 AI 分析→批量修复→全片复验→（可选）自动压制；链级状态行与摘要一键可读；云端服务商下整链不启动（零外发）
- **一键回滚**：自动修复可整体恢复为修复前文本（含删除自动插入行），全程台账可追溯
- **压制成品输出**：翻译完成后可自动压制（GPU 编码），成品已存在但字幕更新时自动重压
- AI 质量分析（质量与建议页）：模型读取质量报告、导读条目与术语冲突汇总，输出术语/TM/一般观察三类建议，逐条人工确认后才写库，永不自动落库
- 文本层质量巡检：单行超长进质量报告导读行动条目、可条目级定点重翻；语速（CPS）与时间轴间隙为纯观测，不触发自动重翻
- **视听对比（疑似漏听检测）**：以媒体音轨为参照比对字幕覆盖率，疑似漏听条目进质量报告导读并可快速试听（mkv 经 ffmpeg 抽取）；检测路径为 ffmpeg 抽取音频 → 能量粗筛（「粗筛」即指此能量级初筛，精核由全链自动化的漏听二级 whisper 转写承担）；未装 ffmpeg 时该检测不产出，不影响翻译主流程。全链自动化的漏听二级核对经三维置信门分档，高置信自动补行缺省关闭（校准门达标才启用）。CLI 经 `--media-path` 指定媒体文件
- 幻觉检测 + 加固短语规则（YAML，可自行维护）
- 双语字幕上下文预审（跨行上下文，防误翻）
- 质量报告 + 双引擎分歧分析
- 校对视图（校对页）：导入视频与字幕并排人工复核——字幕列表与播放双向联动、质量报告疑点段转跳/试听/确认标记、行内改译文、保存自动备份原文件并重编号（UTF-8 重写，兼容 GBK 读取）
- ASR 模型管理（引擎页）：自动探测本机已有模型（上游 WhisperJAV 环境与常见缓存）下拉即用，未装时提供推荐模型自备指引；词典一键下载；媒体音频对照验证为可选开关（默认关闭，全程本地）
- 本地上下文窗口缺省 16384：可经 `config/user_settings.json`（`v2_ctx_local`）、环境变量或 `--v2-ctx` 分层覆盖
- 词库治理：全角/半角（NFKC）归一与拉丁词界匹配、单批注入上限 100 条、结构化 JSON 防注入包装、三级词库链冲突可见化
- Webview GUI + CLI 双入口

## 安装包与数据根

- onedir 打包 + Inno Setup 安装器，数据根位于 `%LOCALAPPDATA%\SubTrans`；**卸载不删除用户数据**（词库/TM/配置/产物均保留）。
- 安装器内置 WebView2 检测与引导（GUI 运行时依赖）。
- 安装包**未做代码签名**：首次运行可能触发 SmartScreen 提示（点「更多信息 → 仍要运行」）。发布页提供的 `SHA256SUMS.txt` 是**安装包完整性校验值（哈希），不是数字签名**——下载后可用它核对文件未被篡改，但不改变 SmartScreen 行为。
- 环境变量 `SUBTRANSJAV_DATA_ROOT` 优先级最高，可整体重定位数据根（词库/TM/配置/产物锚点）。
- `subtrans-cli.exe --where`（EXE 版位于安装目录；pip/源码版为 `subtransjav-refine --where`）一次性诊断当前全部路径锚点（只读零副作用），排障首选。
- EXE 版数据根默认 `%LOCALAPPDATA%\SubTrans`；pip / 源码版数据位置在仓库根（同样可用 `SUBTRANSJAV_DATA_ROOT` 重定位）。

## 安装

普通用户只需读 ①（主推方式）；②③ 面向进阶与开发者（想修改代码/自定义构建请 fork 本仓库自行构建，见本章末「进阶与开发」）。

### ① EXE 安装包（主推·普通用户）

到 [Releases](../../releases) 下载安装包（`SubTrans-setup-*.exe`，随各正式版发布提供）。系统要求：Windows 10/11；WebView2 由安装器自动检测并引导安装。安装即用，无需 Python 环境。

### ② 进阶｜首次安装.bat（源码方式）

克隆仓库后双击运行 `首次安装.bat`，需要 Python 3.10+。脚本完成依赖安装与入口注册。

### ③ 开发者｜pip 安装

要求 Python 3.10–3.13。

```bat
:: 安装（核心翻译引擎 + CLI）
pip install -e .

:: 安装（含桌面 GUI）
pip install -e ".[gui]"

:: 可选：日语语法提示词典数据（core 版/完整版二选一；不装则语法提示自动降级）
:: 词典数据一律下载式——EXE 版在引擎页「词典管理」一键下载；pip/CLI 版：
python -m subtransjav.refine.cli --dict-download sudachi          :: core 版
python -m subtransjav.refine.cli --dict-download sudachi_full     :: 完整版（约 137MB zip，CDN 单源）
```

> **进阶与开发**：想修改代码或自定义构建的进阶用户，请 fork 本仓库（[Angelholl/SubTrans](https://github.com/Angelholl/SubTrans)）后按上文 ②③ 自行构建；EXE 安装包用户无需使用源码与 pip 方式。

## LM Studio 配置指引（本地模型需自备）

安装包只含**程序本体**；翻译所用模型需自备。以 LM Studio 为例，三步即用：

1. 安装 [LM Studio](https://lmstudio.ai/)，在其内置模型搜索中下载模型（推荐搭配见下节速查）。
2. 在 Local Server 页启动本地服务（默认端点 `http://localhost:1234/v1`）。
3. 在本程序「引擎与模型」页选择服务商（lmstudio）与模型名、确认端点；CLI 用户经 `--s1-model` / `--s3-model` 显式指定。

全本地方案（LM Studio / Ollama）不需要任何 API 密钥。

## 快速开始

配置 LLM 端点（DeepSeek / 兼容 OpenAI 协议的自定义端点，或 LM Studio 等本地服务）：

- 云端服务商密钥经环境变量提供：`DEEPSEEK_API_KEY` / `SILICONFLOW_API_KEY` / `CUSTOM_API_KEY`，也可在 GUI 中保存。

命令行示例：

```bat
:: GUI
subtransjav-gui

:: CLI 全流程（单文件）——EXE 用户运行安装目录内的 subtrans-cli.exe（下例以默认安装路径为例）；pip/源码用户将命令替换为 subtransjav-refine
& "C:\Program Files\SubTrans\subtrans-cli.exe" -i 字幕.srt --profile local --s1-provider lmstudio --s1-model <模型名> --s3-provider lmstudio --s3-model <模型名>

:: CLI 批量（目录递归）
& "C:\Program Files\SubTrans\subtrans-cli.exe" --input-dir "字幕目录" -r --filter-pattern "*.srt" --exclude "*_final_cn.srt" "*_refine_*" --profile local --lmstudio-endpoint http://localhost:1234/v1
```

GUI 左侧导航分两组——「工作区」：**字幕翻译**（主页保留选文件、输出目录、翻译服务快捷下拉、开始/停止与进度）、**校对**（视频+字幕并排人工复核）、**质量与建议**（含 AI 质量分析）；「设置」：**引擎与模型**、**词库与模板**、**高级参数**。初始安装即默认参数，全部高级定制在对应页内调整。

常用参数速查：`-i` / `--input-dir -r`（输入）、`--filter-pattern` / `--exclude`（文件过滤）、`-o`（输出目录）、`--glossary`（词库 CSV）、`--tm-db`（指定 TM 库）、`--force`（强制重跑）、`--dry-run`（执行计划预览，不实际调用）、`--v2-ctx`（本地上下文窗口）、`--ai-analyze`（质量报告 AI 分析）、`--action-retranslate --entries`（导读条目定点重翻）、`--media-path`（指定媒体文件，供后续试听/音频检测）、`--source-lang` / `--target-lang`（翻译方向，缺省 ja→zh；非缺省方向须为各启用阶段显式指定配套模板卡 `--s{n}-instructions`，包内仅随 ja→zh 卡）。

每部影片产出：`*_final_cn.srt`（终稿）、`*_质量报告.txt`（若存在 pass1/pass2 双引擎字幕则含「双引擎分歧」章节）、`*_分歧复核.csv`（pass1/pass2 分歧行级明细，无双引擎字幕时仅表头）、`*_质量报告导读.json`（可行动条目，供定点重翻）、`*_风险清单.md`/`*_风险清单.json`、`*_术语冲突观察.csv`（启用词库时）、`*_AI质量建议.json`（AI 分析后生成）；启用自动压制时另产压制成品视频（管线卡开关，缺省关）；中间稿 `*_refine_A.srt` 与断点清单 `*_manifest.json` 在任务成功后自动清理，中断时保留供 `--resume` 续跑。

## 本地模型推荐速查

> 定版结论来自两轮全有序矩阵实测（66 个测试单元零失败）；参测模型、关键发现与速度口径等完整内容见 [docs/模型与转写实测推荐.md](docs/模型与转写实测推荐.md)。

| 场景 | 搭配（阶段A → 阶段B） | 说明 |
|---|---|---|
| **质量优先（定版推荐）** | **joyfox27b → heretic35b** | 盲评并列第一；GPU 全载后约 16~21 分钟/部 |
| 均衡 / 快速 | heretic35b → heretic35b（或 → hauhau35b） | 真台词零丢失，速度约快 5.5 倍 |
| 不推荐 | sakura14b 做 A；joyfox27b / sakura14b 做 B | 草稿缺陷 / 吞台词 / 整行缺失 |

- 本地服务（lmstudio / ollama / siliconflow / custom）模型均需 `--s1-model` / `--s3-model` 显式指定（GUI 在引擎页选择）；云端 deepseek / zen 有内置默认模型。`--profile` 与模型搭配无关。
- 测试语料为 JAV 影片（日译中方向），结论仅代表该领域实测表现；通用场景请选择你自备的通用翻译模型（如 qwen / gemma 等），席位搭配逻辑仍可参考。

## 上游转写配置推荐（WhisperJAV，可选上游）

> 本节为 JAV 源转写实测精简版；其他类型片源直接使用任意 Whisper 转写产物（SRT）即可，无需套用本节配置。完整两轮 11 部全片实测（备选拍档、提速/求净按片开关、时间轴备注、不推荐清单、微调模型）见 [docs/模型与转写实测推荐.md](docs/模型与转写实测推荐.md)。

默认推荐：两遍 ensemble，覆盖优先（两轮实测均全场第一，维持不变）：

```bat
whisperjav <视频> --ensemble ^
  --pass1-pipeline qwen --pass1-sensitivity aggressive --pass1-scene-detector semantic --pass1-speech-segmenter whisperseg ^
  --pass2-pipeline qwen --pass2-sensitivity aggressive --pass2-scene-detector semantic --pass2-speech-segmenter ten ^
  --merge-strategy pass1_primary
```

- **为什么覆盖优先**：漏掉的台词在下游不可恢复，而重复/碎行噪声会被本项目的闸门过滤＋预合并吸收——实测该配置产物喂入下游过滤，4800+ 行仅删除 4 行。
- **升级注意**：不要 `pip install -U whisperjav`（会连带更换 CPU 版 torch），用官方 release wheel 加 `--no-deps` 安装。

## 架构一览

```
SRT 输入
   │  预合并（短句按时间间隙合并，减少批次数）
   ▼
阶段A：净语+翻译（角色卡①，词库/TM 上下文注入）
   │  产出中间稿 *_refine_A.srt（断点产物）
   ▼
阶段B：审校+抛光（角色卡②，幻觉检测/加固短语/质量审校）
   │  兜底规则（解析失败/超时降级：保留原文并记录风险事件）
   ▼
产物：*_final_cn.srt 终稿 + 质量报告 / 分歧复核 / 风险清单
   └── 学习沉淀：TM 句子级翻译记忆（带准入门槛）+ 术语词库
```

两阶段各自独立配置服务商与模型（`--s1-*` / `--s3-*`）；云端阶段故障可选本地接管（`--fallback-local`）。

## 受众定位

本项目面向中文用户：默认翻译方向为 日文 → 中文，角色卡模板、质量审校规则与 GUI 均为中文语境设计。

精修管线当前方向为 日→中；其他目标语言的完整适配列入后续版本。如需适配，修改角色卡模板与规则文件中的语言相关条目：

- 编辑词库与模板页中的角色卡（2.0 自带通用模板，保存写入可编辑层）
- 调整 refine 规则（`config/rules/translation_rules.yaml` 等）中的语言相关条目

## 配置分层速查

优先级从低到高：内置默认 < `config/user_settings.json` < `SUBTRANSJAV_*` 环境变量 < CLI/GUI 显式赋值。

| 字段 | 默认值 | 说明 |
|---|---|---|
| `temperature_cloud` | 0.5 | 云端采样温度 |
| `temperature_local` | 0.1 | 本地采样温度 |
| `premerge_max_gap_s` | 8.0 | 预合并 gap 阈值占位（已不参与合并判定，时长上限见 `premerge_max_span_ms`） |
| `premerge_max_items` | 3 | 预合并条数上限 |
| `v2_concurrency_max` | 5 | 批间并发钳制上限 |
| `timeout_llm` | 900 | LLM 单批超时（秒） |
| `timeout_http` | 60 | HTTP 客户端超时（秒） |
| `timeout_probe` | 5 | 本地服务探测超时（秒） |
| `v2_ctx_local` | 16384 | 本地上下文窗口（22272 为作者档案参考值） |
| `v2_concurrency` | 1 | 批间并发数（钳制上限见 `v2_concurrency_max`） |

环境变量命名：`SUBTRANSJAV_` + 大写字段名（如 `SUBTRANSJAV_TIMEOUT_LLM=600`）。完整语义见 `docs/使用与维护手册.md` 第 2 节。

## 断点恢复

长任务中断后可续跑，复用已完成的阶段A 产物，不重复计算：

```bat
:: 指纹（输入/配置/词库/TM）校验通过才复用（EXE 用户运行安装目录内的 subtrans-cli.exe；pip/源码用户替换为 subtransjav-refine）：
& "C:\Program Files\SubTrans\subtrans-cli.exe" -i 字幕.srt ... --resume

:: 指纹不匹配仍强制复用旧产物（自行承担错位风险）：
& "C:\Program Files\SubTrans\subtrans-cli.exe" -i 字幕.srt ... --resume --force-resume
```

任务成功后断点产物（`*_manifest.json`、`*_refine_A.srt`）自动清理；`--force` 为忽略产物整任务重跑（覆盖前自动备份）。

## 事件协议与退出码（供集成/二次开发）

`--event-format ndjson` 后管线向 stdout 输出结构化事件（每行一个 JSON 对象），人类可读文本转往 stderr。事件类型 10 种：`task_started` / `phase_started` / `phase_progress` / `phase_finished` / `warning` / `degraded` / `error` / `heartbeat` / `task_finished` / `gate0_summary`（闸门0 处置摘要）。

退出码：`0` 成功、`1` 执行失败、`2` dry-run 配置错误、`3` 部分降级（需复核风险清单）、`130` 用户中断。完整字段与心跳机制见手册第 4 节。

## FAQ（精选）

- **GBK 控制台乱码？** 程序内部已强制 UTF-8 输出；必要时 CMD 先执行 `chcp 65001`。
- **LM Studio 未启动/探测失败？** 确认服务已启动并加载模型，端口与端点一致（默认 `http://localhost:1234/v1`）。
- **提示模型未指定？** `lmstudio` / `ollama` / `siliconflow` / `custom` 需经 `--s1-model` / `--s3-model` 指定模型名。
- **云端密钥放哪？** 三级解析：CLI/GUI 传参 > 环境变量 > GUI 保存（DPAPI 加密存储）；本地服务无需密钥。
- **只想看执行计划、不实际调用？** 加 `--dry-run`。
- **我的数据（词库/TM/配置）在哪？** 运行安装目录内的 `subtrans-cli.exe --where`（pip/源码版为 `subtransjav-refine --where`）一次报全当前全部路径锚点；EXE 版默认在 `%LOCALAPPDATA%\SubTrans`，pip 版在仓库根。
- **杀毒软件报毒怎么办？** 安装包未做代码签名，部分杀软（含 Windows Defender）可能对这类 Python 打包文件误报，不代表文件有问题。处理步骤：① 从官方 Releases 下载并核对发布页提供的 SHA256 校验值；② 核对一致后将被隔离的文件「恢复」，并把安装包/安装目录加入杀软白名单；③ 仍持续误报可向杀软厂商提交误报申诉（如微软 Defender 的[文件提交页](https://www.microsoft.com/en-us/wdsi/filesubmission)），厂商核实后会更新病毒库放行。

更多问题见 [docs/使用与维护手册.md](docs/使用与维护手册.md)。

## 词库与模板（自配）

`config/templates/`（角色卡/幻觉模式/加固短语）与 `subtransjav/refine/defaults/`（默认规则）为通用默认；词库 CSV（`--glossary`，两列 source,target，可选第三列 target_aliases 别名，`|` 分隔）与 TM 库不入版本库，克隆后按需自建。

初始自带通用模板角色卡与默认规则（`config/templates/` 与 `subtransjav/refine/defaults/`，可编辑/可覆盖）；词库 CSV（`--glossary`）与 TM 库不入版本库，克隆后按需自建。领域扩展包（如 JAV）见 `docs/examples/`。TM 翻译记忆库的自动学习产物（`glossary_learned.csv`、`tm.db`）由你自己的翻译流程生成，管理命令见 `--tm-stats` / `--tm-export` / `--tm-import` / `--tm-clear`。

## English Quickstart

### Install

- **EXE installer** (recommended for most users): download from [Releases](../../releases) (provided with the 2.0.0 stable release). Requires Windows 10/11; WebView2 is detected and guided by the installer. See the Chinese 安装 section for details.
- **Source install**: run `首次安装.bat` (needs Python 3.10+), or for developers:

```bat
pip install -e ".[gui]"
```

### Quick Start

1. Install [LM Studio](https://lmstudio.ai/), download a model, and start its local server (default `http://localhost:1234/v1`). Local models are **not** bundled — you must provide your own.
2. Launch the GUI (`subtransjav-gui`) and pick the provider/model in the 引擎与模型 (Engine & Model) tab, or use the CLI (`subtrans-cli.exe` inside the EXE install directory; pip/source users: `subtransjav-refine`):

```bat
& "C:\Program Files\SubTrans\subtrans-cli.exe" -i subs.srt --profile local --s1-provider lmstudio --s1-model <model> --s3-provider lmstudio --s3-model <model>
```

The GUI is Chinese-oriented; the refine pipeline currently targets Japanese → Chinese; other target languages are not adapted yet.

### Data Location

- EXE install: `%LOCALAPPDATA%\SubTrans`; pip/source: repository root.
- Override everything with the `SUBTRANSJAV_DATA_ROOT` environment variable; run `subtrans-cli.exe --where` from the EXE install directory (pip/source: `subtransjav-refine --where`) to print all resolved path anchors (read-only diagnostics).

See the Chinese sections above for full details.

## 更新日志

见 [CHANGELOG.md](CHANGELOG.md)。

## 声明

- 本项目为开源字幕翻译工具，使用者须遵守所在地区法律法规。因项目历史领域背景，随仓库保留的领域示例包（`docs/examples/jav-domain/`）与模型/转写实测文档（[docs/模型与转写实测推荐.md](docs/模型与转写实测推荐.md)）涉及成人领域内容，是否适用请自行判断。
- 上游转写工具：[WhisperJAV](https://github.com/meizhong986/WhisperJAV)——分工：转写归上游，翻译+精修归本仓库（旧名 SubTransJAV 由此而来）。仓库已更名 SubTrans，旧名保留历史沿革，定位为通用字幕翻译项目。上游 v1.9.2+ 的运行清单（`whisperjav_run.json`）可通过 `--asr-meta` 接入本仓库双幻觉防护（转写可信度信号驱动精修侧自适应过滤）；旧版上游产物同样支持。
- **设计参考**：GUI 信息架构参考了 [buxuku/SmartSub](https://github.com/buxuku/SmartSub)（MIT 许可）的分层收纳思路（引擎/模型集中管理 + 主界面任务流化），仅借鉴交互理念与信息架构，未复制其代码与图形资产。
- **非商业声明**：本项目基于个人使用设计，在 GitHub 公开仅为开源分享，未商业化、未收取任何费用。
- **联系与整改**：如权利人认为本项目中的商标、图形、文案等内容侵犯其权益，可通过 Issue 联系，我将及时核实并整改。

## 许可证

MIT
