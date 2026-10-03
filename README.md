# SubTrans

> 由 SubTransJAV 项目迭代而来：原 JAV 领域专用字幕翻译工具，现为通用字幕翻译与精修工具链。

自带角色卡与词典的双引擎字幕翻译与精修工具链：LLM 提示词工程 + 术语自学习（自动学习默认关闭）+ 幻觉检测 + 质量审校，日→中方向开箱即用，配套 Whisper 转写工具链使用；初始自带通用模板，动漫、GAL 等领域可自设模板与规则。

A dual-engine subtitle translation & refinement toolkit (evolved from the SubTransJAV project) with built-in persona templates and dictionaries: LLM prompt engineering, self-learning glossary/TM (opt-in), hallucination detection and quality review, Japanese→Chinese out of the box. Works with Whisper-based transcription toolchains; ships with a general-purpose template, and domain templates (anime, GAL, etc.) can be customized.

## 下载与安装

- **EXE 安装包**（推荐普通用户）：随正式版发布提供，请到 [Releases](../../releases) 页下载；系统要求与安装步骤见下方[安装](#安装)。
- **源码 / pip 方式**：见下方[安装](#安装)（`首次安装.bat` 一键脚本或 `pip install -e ".[gui]"`）。

本文档以中文为主体；英文用户可直接跳转 [English Quickstart](#english-quickstart)。

## 它解决什么问题

直译工具翻字幕的三大痛点：

1. 直白表述生硬尴尬 → refine 角色卡二次精修（净语翻译 / 审校抛光）
2. 术语/人名前后不一致 → TM 术语自学习（带准入门槛防污染）+ 强制术语表
3. 长句幻觉编造 → 幻觉模式检测 + 短语加固规则

## 核心特性

- 双引擎翻译 + 风格指令（tone）机制
- refine 精修管线：净语翻译 / 审校抛光两段角色卡（模板可编辑）
- TM 术语自学习（准入门槛：低质翻译不进词库）
- AI 质量分析（质量与建议页）：模型读取质量报告、导读条目与术语冲突汇总，输出术语/TM/一般观察三类建议，逐条人工确认后才写库，永不自动落库
- 文本层质量巡检：单行超长进质量报告导读行动条目、可条目级定点重翻；语速（CPS）与时间轴间隙为纯观测，不触发自动重翻
- 本地上下文窗口缺省 16384：可经 `config/user_settings.json`（`v2_ctx_local`）、环境变量或 `--v2-ctx` 分层覆盖
- 幻觉检测 + 加固短语规则（YAML，可自行维护）
- 双语字幕上下文预审（跨行上下文，防误翻）
- 质量报告 + 双引擎分歧分析
- Webview GUI + CLI 双入口
- 词库治理：全角/半角（NFKC）归一与拉丁词界匹配、单批注入上限 100 条、结构化 JSON 防注入包装、三级词库链冲突可见化
- 校对视图（校对页）：导入视频与字幕并排人工复核——字幕列表与播放双向联动、质量报告疑点段转跳/试听/确认标记、行内改译文、保存自动备份原文件并重编号（UTF-8 重写，兼容 GBK 读取）
- ASR 模型管理（引擎页）：自动探测本机已有模型（上游 WhisperJAV 环境与常见缓存）下拉即用，未装时提供推荐模型自备指引；媒体音频对照验证为可选开关（默认关闭，全程本地）

## 2.0 新特性（beta）

### 视听对比（疑似漏听检测）

- 以媒体文件音轨为参照，比对字幕覆盖率，输出疑似漏听条目清单进质量报告导读。
- 音频探测优先使用 ffmpeg；未安装 ffmpeg 时自动降级为 wave 级 VAD（RMS 能量粗筛），检测精度相应下降；GUI 中未装 ffmpeg 时相关入口灰显。
- **仅报告，不自动重翻**：疑似漏听条目需人工确认后经导读条目定点重翻处理。
- 配套**快速试听**：质量报告导读条目可直接试听对应片段；媒体来源遵循契约内选择（本期收窄为从已授权的媒体来源中选取，**非任意文件浏览**）；mkv 容器经 ffmpeg 抽取片段。
- CLI 侧经 `--media-path` 指定媒体文件，供试听/音频检测使用。

### EXE 分发（Windows 安装包）

- onedir 打包 + Inno Setup 安装器，数据根位于 `%LOCALAPPDATA%\SubTransJAV`；**卸载不删除用户数据**（词库/TM/配置/产物均保留）。
- 安装器内置 WebView2 检测与引导（GUI 运行时依赖）。
- 首发版本**未做代码签名**：首次运行可能触发 SmartScreen 提示（点「更多信息 → 仍要运行」），建议下载后核对发布页提供的 SHA256 校验值自行验证安装包完整性。

### 路径与数据根

- 环境变量 `SUBTRANSJAV_DATA_ROOT` 优先级最高，可整体重定位数据根（词库/TM/配置/产物锚点）。
- `subtransjav-refine --where` 一次性诊断当前全部路径锚点（只读零副作用），排障首选。
- **pip / 源码用户零感知**：数据位置不变（仍在仓库根），行为与 1.4 完全一致。
- EXE 首发迁移三段式：旧数据自动迁入新数据根 → 迁移前自动备份至数据根 `backups/` → 迁移失败自动回退旧路径，详见[从 1.4 升级到 2.0](#从-14-升级到-20)。

## 安装

三种方式并列，按你的身份选择其一：

### ① EXE 安装包（推荐普通用户）

到 [Releases](../../releases) 下载安装包（随 2.0.0 正式发布提供）。系统要求：Windows 10/11；WebView2 由安装器自动检测并引导安装。安装即用，无需 Python 环境。

### ② 首次安装.bat（源码用户）

克隆仓库后双击运行 `首次安装.bat`，需要 Python 3.10+。脚本完成依赖安装与入口注册。

### ③ pip 安装（开发者）

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

## LM Studio 配置指引（本地模型，普通用户视角）

EXE 安装包只解决**程序本体**的安装；翻译所用的本地模型需要**自备**。以 LM Studio 为例：

1. 下载并安装 [LM Studio](https://lmstudio.ai/)，在其内置模型搜索中下载模型（推荐搭配见「本地模型实测推荐」一节）。
2. 在 LM Studio 的 Local Server 页启动本地服务（默认端点 `http://localhost:1234/v1`）。
3. 在本程序 GUI 的**引擎与模型**页选择服务商（lmstudio）与模型名、确认端点；CLI 用户经 `--s1-model` / `--s3-model` 显式指定。

全本地方案（LM Studio / Ollama）不需要任何 API 密钥。

## 快速开始

配置 LLM 端点（DeepSeek / 兼容 OpenAI 协议的自定义端点，或 LM Studio 等本地服务）：

- 云端服务商密钥经环境变量提供：`DEEPSEEK_API_KEY` / `SILICONFLOW_API_KEY` / `CUSTOM_API_KEY`，也可在 GUI 中保存。

命令行示例：

```bat
:: GUI
subtransjav-gui

:: CLI 全流程（单文件）
subtransjav-refine -i 字幕.srt --profile local --s1-provider lmstudio --s1-model <模型名> --s3-provider lmstudio --s3-model <模型名>

:: CLI 批量（目录递归）
subtransjav-refine --input-dir "字幕目录" -r --filter-pattern "*.srt" --exclude "*_final_cn.srt" "*_refine_*" --profile local --lmstudio-endpoint http://localhost:1234/v1
```

GUI 左侧导航分两组——「工作区」：**字幕翻译**（主页保留选文件、输出目录、翻译服务快捷下拉、开始/停止与进度）、**校对**（视频+字幕并排人工复核）、**质量与建议**（含 AI 质量分析）；「设置」：**引擎与模型**、**词库与模板**、**高级参数**。初始安装即默认参数，全部高级定制在对应页内调整。

常用参数速查：`-i` / `--input-dir -r`（输入）、`--filter-pattern` / `--exclude`（文件过滤）、`-o`（输出目录）、`--glossary`（词库 CSV）、`--tm-db`（指定 TM 库）、`--force`（强制重跑）、`--dry-run`（执行计划预览，不实际调用）、`--v2-ctx`（本地上下文窗口）、`--ai-analyze`（质量报告 AI 分析）、`--action-retranslate --entries`（导读条目定点重翻）、`--media-path`（指定媒体文件，供后续试听/音频检测）、`--source-lang` / `--target-lang`（翻译方向，缺省 ja→zh；非缺省方向须为各启用阶段显式指定配套模板卡 `--s{n}-instructions`，包内仅随 ja→zh 卡）。

每部影片产出：`*_final_cn.srt`（终稿）、`*_质量报告.txt`（若存在 pass1/pass2 双引擎字幕则含「双引擎分歧」章节）、`*_分歧复核.csv`（pass1/pass2 分歧行级明细，无双引擎字幕时仅表头）、`*_质量报告导读.json`（可行动条目，供定点重翻）、`*_风险清单.md`/`*_风险清单.json`、`*_术语冲突观察.csv`（启用词库时）、`*_AI质量建议.json`（AI 分析后生成）；中间稿 `*_refine_A.srt` 与断点清单 `*_manifest.json` 在任务成功后自动清理，中断时保留供 `--resume` 续跑。

## 本地模型实测推荐（两轮矩阵测试）

> 以下结论来自 2026-09 的两轮全有序矩阵实测：第一轮 5 款本地模型 × A/B 席位全搭配 = 25 组合 × 2 部影片（TM 零学习）；其中 trans8b 因不读取输入（疑 GGUF 聊天模板损坏）确认不可用，被剔除后第二轮以其余 4 款继续 = 16 组合 × 1 部影片 1162 条台词（TM 启用并逐组合清零，模拟全新安装首用）。两轮共 66 个测试单元全部零失败。评测口径：终稿条目保全（逐条对源）＋ 未翻译占位成因分层 ＋ 考点锚定对照（51 锚点 × 16 组合共识聚类）＋ 主观盲评，多口径交叉验证。测试时点为 2026-09-21，早于 2026-09-23 发现并修复的引擎 GPU 部分卸载问题；本节耗时与速度读数均为该时点实测口径，修复后的生产速度见下文「速度提示」。以下 5 款模型为日译中方向的本地翻译模型，本节测试语料为 JAV 影片（2026-09 全有序矩阵实测），结论仅代表该领域的实测表现；通用场景请选择你自备的通用翻译模型（如 qwen/gemma 等通用 LLM），搭配方式与席位逻辑仍可参考本节。

### 参测模型（LM Studio 本地加载）

| 模型 | 规格 | 实测特点 |
|---|---|---|
| joyfox27b | 27B dense | 跨句语境推理强；解码慢 5~10 倍 |
| heretic35b | 35B-A3B MoE | 规则遵循好、最快；采样方差较大 |
| hauhau35b | 35B-A3B MoE | 审校修复力最强；做 A 时考点偏离较多 |
| sakura14b | 14B dense | 草稿协议缺陷，两轮垫底 |
| trans8b | 8B | 不读取输入（探针验证：任意输入返回无关内容），疑聊天模板损坏，首轮后剔除 |

### 关键发现

1. **阶段A 决定质量层级，阶段B 增益次要**——盲评中 25 组合呈清晰的 5 条 A 产线簇结构。
2. **「未翻译」总数 ≠ 质量损耗**：479 条占位逐条溯源，57% 为含汉字台词真丢失；另发现 B 席位“整行吞台词”（终稿条目数比源少 15~17%），只有终稿条目数比对才能探测，常规漏覆盖指标会漏检。
3. **语境推理是 A 席位的稀缺能力**：「僕たち、水泳部の部長で…」这类复数人称＋で中断句，仅 joyfox 做 A 时译出语境定语读法（4/4 组合），其余模型均为合法但字面的谓语读法。
4. **B 席位踩坑比 A 更隐蔽**：joyfox 做 B 在缺行重试耗尽后逐行降级，单部吞掉 7~20 条真台词；sakura 做 B 整行缺失约 15%。
5. **译文分歧主要由 A 席位决定**：按“偏离多数簇且命中模式”计席位，A 席位 52 次 vs B 席位 12 次。

### 推荐搭配（本项目已按此定版）

| 场景 | 搭配 | 依据 |
|---|---|---|
| **质量优先（默认）** | **joyfox27b → heretic35b** | 盲评并列第一；语境读法唯一；术语误译可被审校席位纠正；生产速度见下文「速度提示」 |
| 均衡 / 快速 | heretic35b → heretic35b 或 heretic35b → hauhau35b | 盲评 40/39；真台词零丢失；生产速度见下文「速度提示」 |
| 不推荐 | sakura14b 做 A；joyfox27b / sakura14b 做 B | 草稿缺陷 / 吞台词 / 整行缺失 |

> **速度提示**：表中耗时为矩阵测试口径（批间并发未启用）。质量档与快速档差距约 5.5 倍，主因是 27B 稠密模型解码速度；2026-09 性能定版（引擎 GPU 全载 + 批间并发 2）后，质量档生产实测约 16~21 分钟/部——该值为 2026-09-23/24 定版锁定配置的实测（引擎 64 层全载、ctx 22272、批间并发 2、批 1024、KV 双 Q8_0、无 draft；与现行缺省 ctx 16384/批间并发 1 不同，见「配置分层速查」），批间并发缺省自 v1.3.2 起为 1，可经 `--v2-concurrency` 调整。TM 精确命中可整句跳过（哈希匹配），但新内容命中率趋近于零，暖库不会明显提速。表中「默认」为生产定版推荐搭配，不是程序内置缺省：本地服务（lmstudio / ollama / siliconflow / custom）模型均需经 `--s1-model` / `--s3-model` 显式指定；云端 deepseek / zen 有内置默认模型，可被显式指定覆盖。`--profile` 与模型搭配无关（v2 兜底档位 local/cloud）。

## 上游转写配置实测推荐（WhisperJAV）

> 本节为 JAV 源的转写实测（可选上游）；其他类型片源可直接使用任意 Whisper 转写产物（SRT），无需套用本节配置。

本项目分工为「转写归上游、翻译＋精修归本仓库」。结论来自 2026-09/10 的两轮全片实测：第一轮 4 部 122~148 分钟影片 × 10 个候选配置；第二轮 7 部 113~180 分钟全新片池 × 6 配置（新增 Purfview Faster-Whisper-XXL、官方拍档复核、JA-Anime-Galgame 微调模型，及基于独立语音参考的时间轴误差分布与族加权伪真值一致率）。两轮共 11 部全片、70 个测试格全部零失败（唯一一次失败为瞬时 Temp 竞态，重跑即过）。

**默认推荐：两遍 ensemble，覆盖优先（两轮均全场第一，维持不变）**

```bat
whisperjav <视频> --ensemble ^
  --pass1-pipeline qwen --pass1-sensitivity aggressive --pass1-scene-detector semantic --pass1-speech-segmenter whisperseg ^
  --pass2-pipeline qwen --pass2-sensitivity aggressive --pass2-scene-detector semantic --pass2-speech-segmenter ten ^
  --merge-strategy pass1_primary
```

- **为什么覆盖优先**：漏掉的台词在下游不可恢复，而重复/碎行噪声会被本项目的闸门过滤＋预合并吸收——实测该配置产物喂入下游过滤，4800+ 行仅删除 4 行（净保留约 36 行真实内容）。两轮覆盖率均为全场第一：一轮 45.0%（均衡基线 24.8%），二轮 48.1%（balanced 基线 23.8%），连续重复为 0。
- **备选（上游官方拍档）**：anime-whisper ＋ TEN：两轮均略低于默认（-1.5pp / -3.3pp），串台/漂移标记同样为 0 且漂移行占比全池最低，求稳求净可用；两强均以 Qwen3-ASR-1.7B 做补漏席位。
- **按片开关①（提速）**：pass2 换 Purfview Faster-Whisper-XXL large-v2——`--pass2-pipeline xxl --xxl-exe <exe路径> --pass2-model large-v2`（**模型必须显式指定**，其内部默认是 large-v3）。实测整体提速 41%、补漏行最干净（串台/漂移标记全 0），代价覆盖率 -1.0~-12.3pp 且片越稀疏损失越大；仅推荐覆盖本就充裕的超密对白片（实测阈值：默认配置覆盖 ≥75% 时损失 ≤1.5pp）。**不要把 xxl 用作主行**：未做行切分后处理时 6/7 片出现 15 秒以上长行。
- **按片开关②（求净）**：v1.9.3 的 htdemucs ＋ enhance-for-vad 是"用覆盖换干净"开关（环境音短句 -80%、重复率下降，代价覆盖 -2.5pp、耗时 +23%），密集型片源求净可开，默认不开。
- **时间轴备注**：qwen/anime 系行边界继承段切器，对独立语音参考的边界误差 P50≈1.5s、>1s 行占比约 70%，是当前最弱轴；large-v2 词级时间戳可收紧至 P50≈0.4s，但需配合长行切分才可用作主行。对时间轴敏感的用法建议开启上游对齐器并人工抽查长行。
- **明确不推荐**：large-v2 / balanced 系——两轮均复现内容型串台句（凭空出现「犬」「母親」类台词，全部来自 balanced 行，单部 2~12 处），且覆盖率两轮垫底（24.8% / 23.8%）；large-v3 / v3-turbo 亦不采用（v3 为全球平均型，日语与时间轴均弱于 v2）。
- **JA-Anime-Galgame 微调模型**（`jaykwok/Qwen3-ASR-1.7B-JA-Anime-Galgame`，Qwen3-ASR 同架构，`--qwen-model-id` 换载）：单遍实测行控全池最稳（单行时长恒 ≤4.2s、重复率 2.0% 全场最低、内容标记全 0、伪真值一致率并列最高 65%），但覆盖率无优势（39.7%）且时间轴同样继承段切边界，暂不改变默认推荐，可作求净单遍候选。
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
:: 指纹（输入/配置/词库/TM）校验通过才复用：
subtransjav-refine -i 字幕.srt ... --resume

:: 指纹不匹配仍强制复用旧产物（自行承担错位风险）：
subtransjav-refine -i 字幕.srt ... --resume --force-resume
```

任务成功后断点产物（`*_manifest.json`、`*_refine_A.srt`）自动清理；`--force` 为忽略产物整任务重跑（覆盖前自动备份）。

## 事件协议与退出码（供集成/二次开发）

`--event-format ndjson` 后管线向 stdout 输出结构化事件（每行一个 JSON 对象），人类可读文本转往 stderr。事件类型 10 种：`task_started` / `phase_started` / `phase_progress` / `phase_finished` / `warning` / `degraded` / `error` / `heartbeat` / `task_finished` / `gate0_summary`（闸门0 处置摘要）。

退出码：`0` 成功、`1` 执行失败、`2` dry-run 配置错误、`3` 部分降级（需复核风险清单）、`130` 用户中断。完整字段与心跳机制见手册第 4 节。

## 从 1.4 升级到 2.0

按你的使用方式对号入座：

- **EXE 安装版**：迁移自动完成，无需手动操作。
- **pip 用户**：数据位置不变（仓库根），可选经 `SUBTRANSJAV_DATA_ROOT` 自定义数据根。
- **CLI / API / 自动化脚本**：见「路径与数据根」说明（`SUBTRANSJAV_DATA_ROOT` 优先级、`refine --where` 诊断）。

安全机制与建议：

- 旧数据自动备份至数据根 `backups/`；
- 迁移失败自动回退旧路径，不影响原有数据；
- 回退到 1.4.1 前建议先 `--tm-export` 导出翻译记忆库。

## FAQ（精选）

- **GBK 控制台乱码？** 程序内部已强制 UTF-8 输出；必要时 CMD 先执行 `chcp 65001`。
- **LM Studio 未启动/探测失败？** 确认服务已启动并加载模型，端口与端点一致（默认 `http://localhost:1234/v1`）。
- **提示模型未指定？** `lmstudio` / `ollama` / `siliconflow` / `custom` 需经 `--s1-model` / `--s3-model` 指定模型名。
- **云端密钥放哪？** 三级解析：CLI/GUI 传参 > 环境变量 > GUI 保存（DPAPI 加密存储）；本地服务无需密钥。
- **只想看执行计划、不实际调用？** 加 `--dry-run`。
- **我的数据（词库/TM/配置）在哪？** 运行 `subtransjav-refine --where` 一次报全当前全部路径锚点；EXE 版默认在 `%LOCALAPPDATA%\SubTransJAV`，pip 版在仓库根。
- **升级到 2.0 后配置还在吗？** EXE 版：首次启动自动迁移旧配置与词库/TM（迁移前自动备份，失败自动回退），无需手动操作；pip 版：数据位置不变，配置原样保留。
- **杀毒软件报毒怎么办？** 首发安装包未做代码签名，部分杀软可能误报。请从官方 Releases 下载并核对发布页提供的 SHA256 校验值；确认一致后可将安装包/安装目录加入杀软白名单。
- **想回退到旧版本要注意什么？** 先执行 `--tm-export` 导出翻译记忆库（2.0 的 TM/数据结构升级后，旧版本可能无法直接读取新库），再卸载/回装旧版。

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
2. Launch the GUI (`subtransjav-gui`) and pick the provider/model in the 引擎与模型 (Engine & Model) tab, or use the CLI:

```bat
subtransjav-refine -i subs.srt --profile local --s1-provider lmstudio --s1-model <model> --s3-provider lmstudio --s3-model <model>
```

The GUI is Chinese-oriented; the refine pipeline currently targets Japanese → Chinese; other target languages are not adapted yet.

### Data Location

- EXE install: `%LOCALAPPDATA%\SubTransJAV`; pip/source: repository root (unchanged since 1.4).
- Override everything with the `SUBTRANSJAV_DATA_ROOT` environment variable; run `subtransjav-refine --where` to print all resolved path anchors (read-only diagnostics).

### Migration (1.4 → 2.0)

- EXE install: migration runs automatically (old data backed up to `backups/` under the data root; automatic rollback on failure).
- pip users: data location unchanged, nothing to do.
- Before rolling back to 1.4.1, export your translation memory first with `--tm-export`.

See the Chinese sections above for full details.

## 更新日志

见 [CHANGELOG.md](CHANGELOG.md)。

## 声明

- 本项目为开源字幕翻译工具，使用者须遵守所在地区法律法规。因项目历史领域背景，随仓库保留的领域示例包（`docs/examples/jav-domain/`）与模型实测章节涉及成人领域内容，是否适用请自行判断。
- 上游转写工具：[WhisperJAV](https://github.com/meizhong986/WhisperJAV)——分工：转写归上游，翻译+精修归本仓库（旧名 SubTransJAV 由此而来）。仓库已更名 SubTrans，旧名保留历史沿革，定位为通用字幕翻译项目。上游 v1.9.2+ 的运行清单（`whisperjav_run.json`）可通过 `--asr-meta` 接入本仓库双幻觉防护（转写可信度信号驱动精修侧自适应过滤）；旧版上游产物同样支持。
- **设计参考**：GUI 信息架构参考了 [buxuku/SmartSub](https://github.com/buxuku/SmartSub)（MIT 许可）的分层收纳思路（引擎/模型集中管理 + 主界面任务流化），仅借鉴交互理念与信息架构，未复制其代码与图形资产。
- **非商业声明**：本项目基于个人使用设计，在 GitHub 公开仅为开源分享，未商业化、未收取任何费用。
- **联系与整改**：如权利人认为本项目中的商标、图形、文案等内容侵犯其权益，可通过 Issue 联系，我将及时核实并整改。

## 许可证

MIT
