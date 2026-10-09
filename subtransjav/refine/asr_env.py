"""ASR 环境探测与重转写（2.6.0 批 3 路线 B，D2026-1002-04-批3）。

探测（零写路径，C9 优先级成文）：env ``SUBTRANSJAV_ASR_PYTHON`` >
settings ``asr_python``（调用方传入）> 实测默认
``D:\\whisperJAV\\python.exe``（维护点：owner 机事实，他机经 env/settings
覆盖）> 不可用。探测＝上游 python 子进程 ``--selfcheck``（导入链+whisper
可导入+模型缓存定位，不实际加载模型，C2），超时即杀；模型缓存枚举
``~/.cache/whisper/*.pt``＋数据根 models/asr/*.pt（≥1GB 防半截）。

重转写＝上游 env 子进程（stdout JSON 契约），失败逐段降级。
2.7.1（D2026-1005-01 承接批）：运行器改 asr_runner.py 脚本路径直调
（_runner_script_path 随包定位 + spec datas 单文件；-m 形态仅 dev-only
回退）；ffmpeg 探测泛化（_candidate_ffmpeg_dirs 上游 env 自带目录，
抽片 subprocess 显式传绝对路径）；selfcheck 失败三分类 triage
（module-missing/whisper-import-failed/ffmpeg-missing/ok/
python-unavailable）+stderr tail 透出；探测枚举 2→3 落位（新增
HF hub cache，HF_HUB_CACHE→HF_HOME/hub→默认链，限深限时 fail-soft）；
探测总预算 90s；推荐清单扩 tier/desc/spec/backend/variants 元数据
（面板三态双门控数据源），tiny/base 下载元数据已实测下载字节级
sha256 核验通过（verified=True），small/medium 未核验（2.7.2 逐档转）。
对照块（C6）：≤2000 截断＋ASR 非真值信度声明；纯材料零自动改写。
模型管理（2.6.1 修订 D2026-1002-06→2.7.1 修订）：推荐清单
（ASR_RECOMMENDED_MODELS）给 url/bytes/sha256 等元信息，verified 档
可一键下载（复用 asr_downloader），未核验档自备落位；
resolve_model_dir 保证"探测枚举"与"运行加载"同序（缓存 ~/.cache/whisper
原生加载点优先，其次数据根 models/asr/ 经 --model-dir 传入）。
2.6.3 批B（D2026-1003-01 ②）：镜像上架门=实下载字节级 sha256 与官方 pin
一致（格式转换版一律不通过），经 D2026-1003-01 拍板②。

零出域声明：本模块无任何网络上传面；转写全程本地（探测/下载 URL 校验
除外）。
"""

import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from subtransjav import paths
from subtransjav.utils.subprocess_flags import CREATE_NO_WINDOW  # windowed 防黑框单一来源（批0）

# C9：探测优先级 env > settings（调用方传入）> 实测默认 > 不可用
_UPSTREAM_DEFAULT_PYTHON = r"D:\whisperJAV\python.exe"   # 维护点：owner 机事实
_ASR_PYTHON_ENV = "SUBTRANSJAV_ASR_PYTHON"
_SELFCHECK_TIMEOUT_S = 60
_MODEL_MIN_BYTES = 1024 * 1024 * 1024        # 1GB：防半截下载
_CLIPS_SUBDIR = "media_clips"
_MAX_CLIPS = 20
# 3.0 批3（D2026-1009-02 批3 C17）：批量转写调用侧。无 GPU（device=cpu）
# 保守上限：单次 spawn 最多转 _BATCH_CPU_CLIP_CAP 个 clip，超出分多次
# spawn（防 CPU 大模型长批占死进程）；cuda 单次全量。超时按 spawn 内
# clip 数线性放大（基值沿 run_transcription 缺省 300s，每 clip +60s）。
_BATCH_CPU_CLIP_CAP = 8
_BATCH_TIMEOUT_BASE_S = 300
_BATCH_TIMEOUT_PER_CLIP_S = 60
# 2.7.1（D2026-1005-01 承接批）：探测总预算（多候选慢启动叠加防护）、
# HF hub 枚举限深/限时、stderr tail 截断长度
_PROBE_TOTAL_BUDGET_S = 90.0
_HF_SCAN_BUDGET_S = 5.0
_HF_SCAN_MAX_DEPTH = 3
_STDERR_TAIL_CHARS = 200
# 数据根模型目录（原 dict_manager._ASR_MODELS_ROOT 迁入：2.6.1 修订
# D2026-1002-06 删下载链后，模型落位常量归探测/解析侧所有）
ASR_MODELS_ROOT = os.path.normpath(str(paths.data_subdir("models", "asr")))
# 推荐缓存目录（whisper 原生加载点；~/.cache/whisper）
ASR_CACHE_DIR = os.path.normpath(
    os.path.join(os.path.expanduser("~"), ".cache", "whisper"))

# 推荐模型清单（2.6.1 修订 D2026-1002-06 模型推荐制；2.7.1 扩面板元数据
# D2026-1005-01 承接批）：tier（fast/balanced/precise 三档分组）+desc+
# spec{speed/precision 五格点阵·静态人工评定非实测, recommend, mem_min}+
# backend{type,state}（三态双门控单一来源：ready 可下载可选用/
# adapter-needed 展示数据/planned 规划中）+variants（行内变体展开）。
# verified 硬门槛：未核验档位禁止可点击下载（2.7.1 件5）——tiny/base/
# small/medium 已实测下载（2026-10-05，官方 openaipublic 资产）字节级
# sha256 核验通过（sha256=URL 段=whisper 上游 _MODELS pin，与 large-v2
# 同标准），五档 .pt（tiny/base/small/medium/large-v2）全核验；
# qwen3 仍 planned 不变。
# large-v2 字面量自 dict_manager._ASR_DOWNLOADS 迁移（url/bytes/sha256
# 实测核算值原样保留）；qwen3-asr-1.7b=规划中（HF 多文件目录布局，
# 启动前置=HF 布局核实+加载 smoke+二级评议）。
ASR_RECOMMENDED_MODELS: list[dict] = [
    {
        "name": "whisper-tiny",
        "model": "tiny",
        "title": "openai-whisper tiny（快速档）",
        "tier": "fast",
        "desc": "最小最快，精度有限；适合低配机先跑通对照链路",
        "spec": {"speed": 5, "precision": 1, "recommend": False,
                 "mem_min": 1},
        "backend": {"type": "openai-whisper-api", "state": "ready"},
        "verified": True,
        "bytes": 75572083,
        "sha256": ("65147644a518d12f04e32d6f3b26facc3f8dd46e5390956a9424"
                   "a650c0ce22b9"),
        "url": ("https://openaipublic.azureedge.net/main/whisper/models/"
                "65147644a518d12f04e32d6f3b26facc3f8dd46e5390956a9424a650"
                "c0ce22b9/tiny.pt"),
        "support": "available",
        "license": "MIT（openai/whisper 上游模型卡口径）",
        "sources": [
            {"source": "official", "label": "官方源",
             "url": ("https://openaipublic.azureedge.net/main/whisper/"
                     "models/65147644a518d12f04e32d6f3b26facc3f8dd46e5390"
                     "956a9424a650c0ce22b9/tiny.pt"),
             "sha256": ("65147644a518d12f04e32d6f3b26facc3f8dd46e5390956"
                        "a9424a650c0ce22b9"),
             "verified": True},
        ],
        "variants": [
            {"name": "原版 .pt", "state": "ready"},
            {"name": "q5_0 量化", "state": "adapter-needed",
             "note": "需 CT2/faster-whisper 适配（2.8.0）"},
        ],
    },
    {
        "name": "whisper-base",
        "model": "base",
        "title": "openai-whisper base（快速档）",
        "tier": "fast",
        "desc": "速度与精度的最低配平衡；内存占用极小",
        "spec": {"speed": 4, "precision": 2, "recommend": False,
                 "mem_min": 1},
        "backend": {"type": "openai-whisper-api", "state": "ready"},
        "verified": True,
        "bytes": 145262807,
        "sha256": ("ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b"
                   "0e6c6326e34e"),
        "url": ("https://openaipublic.azureedge.net/main/whisper/models/"
                "ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6"
                "c6326e34e/base.pt"),
        "support": "available",
        "license": "MIT（openai/whisper 上游模型卡口径）",
        "sources": [
            {"source": "official", "label": "官方源",
             "url": ("https://openaipublic.azureedge.net/main/whisper/"
                     "models/ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f8"
                     "91f668f8b0e6c6326e34e/base.pt"),
             "sha256": ("ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f6"
                        "68f8b0e6c6326e34e"),
             "verified": True},
        ],
        "variants": [
            {"name": "原版 .pt", "state": "ready"},
            {"name": "q5_0 量化", "state": "adapter-needed",
             "note": "需 CT2/faster-whisper 适配（2.8.0）"},
        ],
    },
    {
        "name": "whisper-small",
        "model": "small",
        "title": "openai-whisper small（均衡档）",
        "tier": "balanced",
        "desc": "均衡档入门；日语音频对照可用性一般",
        "spec": {"speed": 3, "precision": 3, "recommend": False,
                 "mem_min": 2},
        "backend": {"type": "openai-whisper-api", "state": "ready"},
        "verified": True,
        "bytes": 483617219,
        "sha256": ("9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42"
                   "bf17a411e794"),
        "url": ("https://openaipublic.azureedge.net/main/whisper/models/"
                "9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42bf1"
                "7a411e794/small.pt"),
        "support": "available",
        "license": "MIT（openai/whisper 上游模型卡口径）",
        "sources": [
            {"source": "official", "label": "官方源",
             "url": ("https://openaipublic.azureedge.net/main/whisper/"
                     "models/9ecf779972d90ba49c06d968637d720dd632c55bbf"
                     "19d441fb42bf17a411e794/small.pt"),
             "sha256": ("9ecf779972d90ba49c06d968637d720dd632c55bbf19d4"
                        "41fb42bf17a411e794"),
             "verified": True},
        ],
        "variants": [
            {"name": "原版 .pt", "state": "ready"},
            {"name": "q5_0 量化", "state": "adapter-needed",
             "note": "需 CT2/faster-whisper 适配（2.8.0）"},
        ],
    },
    {
        "name": "whisper-medium",
        "model": "medium",
        "title": "openai-whisper medium（均衡档）",
        "tier": "balanced",
        "desc": "均衡档高配；精度接近 large 而速度更快",
        "spec": {"speed": 2, "precision": 4, "recommend": False,
                 "mem_min": 5},
        "backend": {"type": "openai-whisper-api", "state": "ready"},
        "verified": True,
        "bytes": 1528008539,
        "sha256": ("345ae4da62f9b3d59415adc60127b97c714f32e89e936602e859"
                   "93674d08dcb1"),
        "url": ("https://openaipublic.azureedge.net/main/whisper/models/"
                "345ae4da62f9b3d59415adc60127b97c714f32e89e936602e859936"
                "74d08dcb1/medium.pt"),
        "support": "available",
        "license": "MIT（openai/whisper 上游模型卡口径）",
        "sources": [
            {"source": "official", "label": "官方源",
             "url": ("https://openaipublic.azureedge.net/main/whisper/"
                     "models/345ae4da62f9b3d59415adc60127b97c714f32e8"
                     "9e936602e85993674d08dcb1/medium.pt"),
             "sha256": ("345ae4da62f9b3d59415adc60127b97c714f32e89e93"
                        "6602e85993674d08dcb1"),
             "verified": True},
        ],
        "variants": [
            {"name": "原版 .pt", "state": "ready"},
            {"name": "q5_0 量化", "state": "adapter-needed",
             "note": "需 CT2/faster-whisper 适配（2.8.0）"},
        ],
    },
    {
        "name": "whisper-large-v2",
        "model": "large-v2",
        "title": "openai-whisper large-v2（上游同款）",
        "tier": "precise",
        "desc": "精度最高档；上游 WhisperJAV 同款，媒体对照首选",
        "spec": {"speed": 1, "precision": 5, "recommend": True,
                 "mem_min": 10},
        "backend": {"type": "openai-whisper-api", "state": "ready"},
        "verified": True,
        "bytes": 3086999982,
        "sha256": ("81f7c96c852ee8fc832187b0132e569d6c3065a3252ed18e56effd"
                   "0b6a73e524"),
        "url": ("https://openaipublic.azureedge.net/main/whisper/models/"
                "81f7c96c852ee8fc832187b0132e569d6c3065a3252ed18e56effd0b6a"
                "73e524/large-v2.pt"),
        "support": "available",
        # 2.6.3 批B（D2026-1003-01 ②）：多源元信息。mirror 条目已点亮
        # （D2026-1005-05，2026-10-10）：owner 上传原样字节副本至
        # Angelholl/openai-whisper-pt，hf-mirror 全量回读 sha256 与官方
        # pin 字节级一致，verified=True 入下载池。
        "license": "MIT（openai/whisper 上游模型卡口径）",
        "sources": [
            {"source": "official", "label": "官方源",
             "url": ("https://openaipublic.azureedge.net/main/whisper/models/"
                     "81f7c96c852ee8fc832187b0132e569d6c3065a3252ed18e56effd"
                     "0b6a73e524/large-v2.pt"),
             "sha256": ("81f7c96c852ee8fc832187b0132e569d6c3065a3252ed18e56e"
                        "ffd0b6a73e524"),
             "verified": True},
            {"source": "mirror", "label": "国内加速源",
             "url": ("https://hf-mirror.com/Angelholl/openai-whisper-pt/"
                     "resolve/7b3ad79575c53f369fbdb17060e6cf14c66cdc96/"
                     "large-v2.pt"),
             "sha256": ("81f7c96c852ee8fc832187b0132e569d6c3065a3252ed18e56e"
                        "ffd0b6a73e524"),
             "verified": True,
             "note": "已点亮 2026-10-10：owner 仓 Angelholl/openai-whisper-pt"
                     "（tip 7b3ad795）原样字节副本，hf-mirror 全量回读 "
                     "sha256 与官方 pin 一致"},
        ],
        "variants": [
            {"name": "原版 .pt", "state": "ready"},
            {"name": "q5_0 量化", "state": "adapter-needed",
             "note": "需 CT2/faster-whisper 适配（2.8.0）"},
        ],
    },
    {
        "name": "qwen3-asr-1.7b",
        "model": "qwen3-asr-1.7b",
        "title": "Qwen3-ASR-1.7B（HF 多文件目录，规划中）",
        "tier": "balanced",
        "desc": "Qwen3-ASR 轻量档；HF transformers 适配器规划中（2.9.0）",
        "spec": {"speed": 4, "precision": 3, "recommend": False,
                 "mem_min": 4},
        "backend": {"type": "qwen3-asr-hf", "state": "planned"},
        "support": "planned",       # 规划中：无下载字段，用户自备
    },
]


def resolve_model_dir(model_name: str) -> str | None:
    """解析模型加载目录（探测与运行同序；2.6.1 修订 D2026-1002-06）。

    顺序：~/.cache/whisper/<name>.pt 命中→None（原生加载点优先，不传
    旗标）；数据根 models/asr/<name>.pt 命中→返回该目录字符串（运行器
    --model-dir）；都没有→None。"""
    fname = f"{model_name}.pt"
    if (Path(ASR_CACHE_DIR) / fname).is_file():
        return None
    if (Path(ASR_MODELS_ROOT) / fname).is_file():
        return ASR_MODELS_ROOT
    return None


def _enum_pt_models(root: str, source: str) -> list[dict]:
    """单目录 *.pt 枚举（≥1GB 防半截），条目带 source 落位标注。"""
    out: list[dict] = []
    base = Path(root)
    if not base.is_dir():
        return out
    for p in sorted(base.glob("*.pt")):
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size < _MODEL_MIN_BYTES:
            continue
        out.append({"name": p.stem, "path": str(p), "bytes": size,
                    "source": source})
    return out


def default_tm_cache_models() -> list[dict]:
    """枚举 ~/.cache/whisper/*.pt＋数据根 models/asr/*.pt（≥1GB 防半截）。

    2.7.1 起为 enumerate_models_three_sources 的 whisper 系两落位
    （去重合并不在此做，保持原样逐目录枚举——历史调用方兼容）。"""
    return _enum_pt_models(ASR_CACHE_DIR, "whisper-cache") \
        + _enum_pt_models(ASR_MODELS_ROOT, "data-root")


def enumerate_models_three_sources() -> dict:
    """三落位枚举合并去重（2.7.1 件4）：whisper 原生缓存→数据根→HF hub。

    whisper 系 ready 条目按 name 去重（校验序=加载序：whisper-cache >
    data-root；hf-hub 无 ready .pt 形态，仅面板「需适配」展示）。
    返回 {"whisper": [...], "hf": [...]}。"""
    out: list[dict] = []
    seen: set[str] = set()
    for root, source in ((ASR_CACHE_DIR, "whisper-cache"),
                         (ASR_MODELS_ROOT, "data-root")):
        for m in _enum_pt_models(root, source):
            if m["name"] in seen:
                continue
            seen.add(m["name"])
            out.append(m)
    return {"whisper": out, "hf": enumerate_hf_hub_models()}


def hf_hub_cache_dir() -> Path:
    """HF hub cache 三级 env 链（评议 C4）：HF_HUB_CACHE→HF_HOME/hub→
    默认 ~/.cache/huggingface/hub（自定义盘符如 G:\\HuggingFace_Cache\\hub
    经 HF_HUB_CACHE/HF_HOME 覆盖即达）。"""
    env_hub = os.environ.get("HF_HUB_CACHE", "").strip()
    if env_hub:
        return Path(env_hub)
    env_home = os.environ.get("HF_HOME", "").strip()
    if env_home:
        return Path(env_home) / "hub"
    return Path(os.path.expanduser("~")) / ".cache" / "huggingface" / "hub"


def _classify_hf_snapshot(repo_name: str, snap: Path) -> dict | None:
    """按文件族识别单个 HF snapshot（models--*/snapshots/<sha>/）。

    model.bin+tokenizer.json→"ct2"；*.pt 或 model.safetensors→
    "transformers"；都不满足→None（不收录）。bytes=snapshot 内可识别
    文件族总大小。任何 OSError fail-soft 返回 None。"""
    try:
        files = [p for p in snap.iterdir() if p.is_file()]
    except OSError:
        return None
    names = {p.name for p in files}
    if "model.bin" in names and "tokenizer.json" in names:
        fmt = "ct2"
    elif any(n == "model.safetensors" or n.endswith(".pt")
             for n in names):
        fmt = "transformers"
    else:
        return None
    total = 0
    for p in files:
        try:
            total += p.stat().st_size
        except OSError:
            continue
    return {"name": repo_name.removeprefix("models--").replace("--", "/"),
            "source": "hf-hub", "path": str(snap), "bytes": total,
            "format": fmt, "backend_state": "adapter-needed"}


def enumerate_hf_hub_models(budget_s: float = _HF_SCAN_BUDGET_S,
                            max_depth: int = _HF_SCAN_MAX_DEPTH) -> list[dict]:
    """HF hub cache 枚举（2.7.1 件4 第 3 落位；只读零写路径）。

    扫 <hub>/models--*/snapshots/*/（目录深度 max_depth 语义：hub→
    repo→snapshots→snapshot；文件族识别见 _classify_hf_snapshot），
    总时限 budget_s（超时即返回已得部分），任何异常 fail-soft 返回
    已得部分/空列表。"""
    del max_depth    # 布局常量固定 4 级（hub/repo/snapshots/sha），深度上限由布局保证
    root = hf_hub_cache_dir()
    if not root.is_dir():
        return []
    deadline = time.monotonic() + budget_s
    out: list[dict] = []
    try:
        repos = sorted(root.glob("models--*"))
    except OSError:
        return out
    for repo in repos:
        if time.monotonic() >= deadline:
            break
        snaps = repo / "snapshots"
        try:
            snap_dirs = sorted(snaps.iterdir()) if snaps.is_dir() else []
        except OSError:
            continue
        for snap in snap_dirs:
            if time.monotonic() > deadline:
                break
            if not snap.is_dir():
                continue
            entry = _classify_hf_snapshot(repo.name, snap)
            if entry is not None:
                out.append(entry)
    return out


# ---------------------------------------------------------------------------
# 探测结果快照缓存（2.7.1 件4，评议 R5：磁盘级 JSON 落数据根，非进程内
# dict）——refine_asr_status 优先读缓存立即返回，刷新方写回
# ---------------------------------------------------------------------------

_ASR_PROBE_CACHE_RELPATH = ("config", "asr_probe_cache.json")
_ASR_PROBE_CACHE_TTL_S = 600      # 10 分钟：超龄由刷新方重新探测


def probe_cache_path() -> str:
    """探测快照落点：数据根 config/asr_probe_cache.json。"""
    return paths.data_subdir(*_ASR_PROBE_CACHE_RELPATH)


def load_probe_cache(path: str = "",
                     max_age_s: int = _ASR_PROBE_CACHE_TTL_S) -> dict | None:
    """读探测快照（timestamp+probe 结果+models 枚举）。

    超龄（time.time()-timestamp > max_age_s）/文件缺失/损坏 → None
    （fail-soft，调用方走重新探测）。path 空则用 probe_cache_path()。"""
    p = Path(path) if path else Path(probe_cache_path())
    try:
        if not p.is_file():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    ts = data.get("timestamp")
    if not isinstance(ts, (int, float)):
        return None
    if max_age_s and (time.time() - ts) > max_age_s:
        return None
    probe = data.get("probe")
    return probe if isinstance(probe, dict) else None


def save_probe_cache(probe: dict, path: str = "") -> bool:
    """写探测快照（含时间戳；OSError/序列化失败 fail-soft 返回 False）。"""
    p = Path(path) if path else Path(probe_cache_path())
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {"timestamp": time.time(), "probe": probe}
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                     encoding="utf-8")
        return True
    except (OSError, TypeError, ValueError):
        return False


def _candidate_pythons(asr_python_setting: str = "") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    env_p = os.environ.get(_ASR_PYTHON_ENV, "").strip()
    if env_p:
        out.append(("env", env_p))
    setting = (asr_python_setting or "").strip()
    if setting:
        out.append(("settings", setting))
    out.append(("default", _UPSTREAM_DEFAULT_PYTHON))
    return out


def _runner_script_path() -> str:
    """asr_runner.py 随包定位（2.7.1 件1：脚本直调形态单一来源）。

    frozen→<exe 目录>/_internal/subtransjav/refine/asr_runner.py
    （spec datas 单文件落点；存在性检查，回退 exe 同目录）；
    dev→包内同目录 asr_runner.py（仓库/安装源码形态）。找不到返回
    ""（调用方回退 -m 形态，dev-only）。"""
    if getattr(sys, "frozen", False):
        cand = (Path(sys.executable).parent / "_internal" / "subtransjav"
                / "refine" / "asr_runner.py")
        if cand.is_file():
            return str(cand)
        fb = Path(sys.executable).parent / "asr_runner.py"
        return str(fb) if fb.is_file() else ""
    dev = Path(__file__).resolve().parent / "asr_runner.py"
    return str(dev) if dev.is_file() else ""


def _runner_command(python: str, *args: str) -> list[str]:
    """上游 python + 运行器命令组装（2.7.1 件1：脚本路径直调优先）。

    runner 文件存在→[python, <runner 路径>, *args]（无 cwd 依赖，
    --audio 等参数 list 传参防中文路径拼接）；不存在→回退
    -m subtransjav.refine.asr_runner 形态（**dev-only**：frozen 数据根
    无 subtransjav 包，-m 必失败——此分支仅源码形态可达）。"""
    runner = _runner_script_path()
    if runner:
        return [python, runner, *args]
    return [python, "-m", "subtransjav.refine.asr_runner", *args]


def _candidate_ffmpeg_dirs(python_path: str = "") -> list[str]:
    """上游 env 自带 ffmpeg 候选目录（2.7.1 件1：探测泛化）。

    app 进程 PATH 由 shutil.which 覆盖；此处补上游 python 发行版惯例
    落位：<python 目录>/Library/bin、Scripts、python 目录本身、其父
    目录（conda/win embeddable 常见布局）。"""
    dirs: list[str] = []
    if not python_path:
        return dirs
    py = Path(python_path)
    base = py.parent if py.is_file() else py
    for d in (base / "Library" / "bin", base / "Scripts", base, base.parent):
        s = str(d)
        if s not in dirs and d.is_dir():
            dirs.append(s)
    return dirs


def resolve_ffmpeg(python_path: str = "") -> str:
    """ffmpeg 绝对路径解析（2.7.1 件1）：PATH 优先，缺则逐候选目录探测。

    返回可执行文件绝对路径或 ""（不可用）；抽片 subprocess 显式传该
    路径，不再依赖 app 进程 PATH。"""
    hit = shutil.which("ffmpeg")
    if hit:
        return hit
    for d in _candidate_ffmpeg_dirs(python_path):
        for name in ("ffmpeg.exe", "ffmpeg"):
            cand = os.path.join(d, name)
            if os.path.isfile(cand):
                return cand
    return ""


def _first_available_python(asr_python_setting: str = "") -> str:
    """候选链上第一个真实存在的上游 python（抽片 ffmpeg 定位用）。"""
    for _src, py in _candidate_pythons(asr_python_setting):
        if os.path.isfile(py):
            return py
    return ""


def _run_selfcheck(python: str, model: str, model_dir: str = "",
                   timeout: int = _SELFCHECK_TIMEOUT_S
                   ) -> tuple[bool, dict, str, str]:
    """上游 python 子进程 --selfcheck（C2 真实契约探测）。

    返回 (ok, info, stderr_tail, err)：stderr_tail=stderr 末 200 字符
    （诊断网格透出），err=selfcheck JSON error 字段（whisper 导入失败
    等机器可读失败原因，供三分类 triage）。spawn 失败/超时返回
    (False, {}, "", "")——triage 由 probe 侧定 python-unavailable。"""
    cmd = _runner_command(python, "--selfcheck", "--model", model)
    if model_dir:
        cmd.extend(["--model-dir", model_dir])
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(paths.app_root()),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            creationflags=CREATE_NO_WINDOW)  # GUI windowed 防黑框（批0；POSIX=0 无操作）
    except (OSError, subprocess.TimeoutExpired):
        return False, {}, "", ""
    tail = (proc.stderr or "")[-_STDERR_TAIL_CHARS:]
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if payload.get("ok"):
            return True, payload.get("info") or {}, tail, ""
        return False, {}, tail, str(payload.get("error") or "")
    return False, {}, tail, ""


def _triage_selfcheck(err: str, stderr_tail: str) -> str:
    """selfcheck 失败三分类（2.7.1 件1）：whisper 导入失败 / 模块缺失 /
    其他（归 python-unavailable 口径）。"""
    blob = f"{err}\n{stderr_tail}"
    if "whisper 导入失败" in blob:
        return "whisper-import-failed"
    if "ModuleNotFoundError" in blob or "No module named" in blob:
        return "module-missing"
    return "python-unavailable"


def probe_asr_env(asr_python_setting: str = "",
                  model: str = "large-v2") -> dict:
    """零写路径探测（available/reason 形态，audio_detect 先例）。

    2.7.1 扩展：返回新增 triage（三分类：module-missing/
    whisper-import-failed/ffmpeg-missing/ok/python-unavailable）、
    ffmpeg_path（实际所用绝对路径，可为空）、stderr_tail（末 200 字符）、
    models_hf（HF hub cache 第 3 落位枚举）；探测总预算 90s
    （time.monotonic 检查，超时按已得结果返回）。"""
    models_catalog = enumerate_models_three_sources()
    models = models_catalog["whisper"]
    models_hf = models_catalog["hf"]
    model_present = any(m["name"] == model for m in models)
    # 探测与加载同序（2.6.1 修订 D2026-1002-06）：selfcheck 也带
    # --model-dir，防"枚举两处/加载一处"假阳性。
    model_dir = resolve_model_dir(model) or ""
    last_err = "无候选上游 Python"
    last_triage = "python-unavailable"
    last_tail = ""
    ff_path = ""
    deadline = time.monotonic() + _PROBE_TOTAL_BUDGET_S
    for source, py in _candidate_pythons(asr_python_setting):
        if not os.path.isfile(py):
            last_err = f"{source}:{py} 不存在"
            continue
        if time.monotonic() > deadline:
            last_err = "探测总预算（90s）超时，按已得结果返回"
            break
        ok, info, tail, err = _run_selfcheck(py, model, model_dir)
        ff_path = resolve_ffmpeg(py)
        if ok:
            ffmpeg = bool(ff_path)
            reason = ("whisper " + str(info.get("whisper_version") or "?")
                      + "｜模型缓存"
                      + ("在位" if info.get("model_present") else "缺失")
                      + "｜ffmpeg " + ("可用" if ffmpeg else "缺失"))
            return {"available": bool(ffmpeg and model_present),
                    "reason": reason,
                    "python": py,
                    "python_source": source,
                    "whisper_version": str(info.get("whisper_version") or ""),
                    "model_present": bool(info.get("model_present")),
                    "models": models,
                    "models_hf": models_hf,
                    "ffmpeg": ffmpeg,
                    "ffmpeg_path": ff_path,
                    "triage": "ok" if ffmpeg else "ffmpeg-missing",
                    "stderr_tail": tail}
        last_err = f"{source}:{py} selfcheck 未通过"
        last_triage = _triage_selfcheck(err, tail)
        last_tail = tail
    return {"available": False, "reason": last_err, "python": "",
            "python_source": "", "whisper_version": "",
            "model_present": model_present, "models": models,
            "models_hf": models_hf,
            "ffmpeg": bool(ff_path), "ffmpeg_path": ff_path,
            "triage": last_triage, "stderr_tail": last_tail}


# ---------------------------------------------------------------------------
# 重转写与对照块
# ---------------------------------------------------------------------------

def run_transcription(clip_path: str, asr_python: str = "",
                      model: str = "large-v2", language: str = "ja",
                      timeout: int = 300) -> dict:
    """单片段重转写（上游 env 子进程；JSON 契约解析；失败降级 dict）。

    返回 {"ok": bool, "text": str, "error": str}。"""
    python = ""
    for _src, cand in _candidate_pythons(asr_python):
        if os.path.isfile(cand):
            python = cand
            break
    if not python:
        return {"ok": False, "text": "",
                "error": "上游 ASR Python 不可用（探测降级）"}
    cmd = _runner_command(python, "--audio", str(clip_path),
                          "--model", model, "--language", language)
    # 探测与加载同序（2.6.1 修订 D2026-1002-06）：数据根落位时显式传
    # --model-dir；缓存命中/都无 → 不传（原生 ~/.cache/whisper 行为）。
    model_dir = resolve_model_dir(model)
    if model_dir:
        cmd.extend(["--model-dir", model_dir])
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(paths.app_root()),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            creationflags=CREATE_NO_WINDOW)  # GUI windowed 防黑框（批0；POSIX=0 无操作）
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "text": "", "error": f"ASR 子进程失败: {e}"}
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if payload.get("ok"):
            return {"ok": True, "text": str(payload.get("text") or ""),
                    "error": ""}
        return {"ok": False, "text": "",
                "error": str(payload.get("error") or "ASR 失败")}
    return {"ok": False, "text": "",
            "error": f"ASR 运行器无有效输出（rc={proc.returncode}）"}


def _resolve_asr_python(asr_python: str) -> str:
    """候选链解析第一个真实存在的上游 python（run_transcription 同序，
    抽出复用；找不到返回 ""）。"""
    for _src, cand in _candidate_pythons(asr_python):
        if os.path.isfile(cand):
            return cand
    return ""


def _spawn_runner(python: str, args: list[str], timeout: int) -> dict:
    """spawn 上游 python 跑运行器并解析 stdout 单行 JSON（契约同
    run_transcription：首个以 { 开头的可解析行）。spawn 失败/超时/
    无有效输出返回 {"ok": False, "payload": None, "error": ...}。"""
    cmd = _runner_command(python, *args)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(paths.app_root()),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            creationflags=CREATE_NO_WINDOW)  # GUI windowed 防黑框（批0；POSIX=0 无操作）
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "payload": None,
                "error": f"ASR 子进程失败: {e}"}
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        return {"ok": bool(payload.get("ok")), "payload": payload,
                "error": "" if payload.get("ok")
                else str(payload.get("error") or "ASR 失败")}
    return {"ok": False, "payload": None,
            "error": f"ASR 运行器无有效输出（rc={proc.returncode}）"}


def batch_transcribe_clips(media_path: str, timings: list[str], *,
                           model: str | None = None,
                           model_dir: str | None = None,
                           max_clips: int = _MAX_CLIPS,
                           progress=None) -> list[dict]:
    """批量转写（3.0 批3 C17 调用侧）：slice_clips 切片→组 clips-json→
    spawn 上游 python（单次进程 load_model 一次转 N 段）→按 timing 对齐
    返回 per-timing 转写。

    - model/model_dir 缺省沿用 run_transcription 惯例（large-v2 /
      resolve_model_dir 解析）；
    - 无 GPU 保守上限：先以空 clips-json 探测 device（运行器空列表不
      加载模型，零成本）；device=cpu 时每 spawn 最多 _BATCH_CPU_CLIP_CAP
      个 clip（超出分多次 spawn）；device 探测失败保守按 cpu 处理；
    - 超时＝_BATCH_TIMEOUT_BASE_S + per-clip 线性放大（spawn 内 clip 数
      ×_BATCH_TIMEOUT_PER_CLIP_S）；失败/超时该批如实标记 ok=False
      （不静默）；
    - progress：可选回调 progress(done, total)（切片后可用数口径）；
    - 切片失败/被 max_clips 截断的 timing 如实标记 ok=False；
    - cleanup_clips 交调用方（保持现惯例）。

    返回：与 timings 等长的 list[dict]，每项 {"timing", "ok", "text",
    "segments", "error"}（segments 为含置信字段的段级数组，C13）。"""
    model_name = model or "large-v2"
    failed = lambda timing, err: {"timing": timing, "ok": False,  # noqa: E731
                                  "text": "", "segments": [], "error": err}
    sliced = slice_clips(media_path, timings, max_clips=max_clips)
    clips = sliced.get("clips") or []
    by_timing: dict[str, dict] = {}
    for t in timings:
        by_timing[t] = failed(t, "")      # 占位，成功后被覆盖
    if not clips:
        err = sliced.get("error") or "无可用切片"
        for t in timings:
            by_timing[t] = failed(t, f"切片失败: {err}")
        return [by_timing[t] for t in timings]
    # 切片成功但部分跳过（超 max_clips 截断/ffmpeg 单段失败）→ 如实标记
    done_timings = {c["timing"] for c in clips}
    skipped_note = (f"切片跳过 {sliced.get('skipped', 0)} 段"
                    f"（超上限 {_MAX_CLIPS} 或 ffmpeg 失败）"
                    if sliced.get("skipped") else "切片失败")
    python = _resolve_asr_python("")
    if not python:
        for t in timings:
            by_timing[t] = failed(t, "上游 ASR Python 不可用（探测降级）")
        return [by_timing[t] for t in timings]

    def _write_clips_json(chunk: list[dict]) -> str:
        """组 clips-json 临时文件（与切片同目录 sha256 指纹名）。"""
        import hashlib
        d = Path(paths.data_subdir("Temp", _CLIPS_SUBDIR))
        d.mkdir(parents=True, exist_ok=True)
        fp = hashlib.sha256(    # 非加密用途：批清单临时名（sha256 同切片惯例）
            json.dumps([c["path"] for c in chunk],
                       ensure_ascii=False).encode()).hexdigest()[:12]
        p = d / f"batch_{fp}.json"
        p.write_text(json.dumps(
            [{"clip": c["path"], "timing": c["timing"]} for c in chunk],
            ensure_ascii=False), encoding="utf-8")
        return str(p)

    # 设备探测：空 clips-json（运行器空列表不加载模型）。探测失败保守
    # 按 cpu 处理（分批上限方向安全，不激进）。
    model_dir_resolved = (model_dir if model_dir is not None
                          else resolve_model_dir(model_name))
    probe_json = _write_clips_json([])
    probe_args = ["--clips-json", probe_json, "--model", model_name]
    if model_dir_resolved:
        probe_args.extend(["--model-dir", model_dir_resolved])
    probe = _spawn_runner(python, probe_args, _SELFCHECK_TIMEOUT_S)
    device = "cpu"
    if probe["ok"] and isinstance(probe["payload"], dict):
        device = str(probe["payload"].get("device") or "cpu")
    cap = len(clips) if device == "cuda" else _BATCH_CPU_CLIP_CAP
    # cuda 单次全量（cap=len(clips)）＝单次 load_model 转 N 段（C17 主旨）
    chunks = [clips[i:i + cap] for i in range(0, len(clips), cap)]
    total = len(clips)
    done = 0
    for chunk in chunks:
        cj = _write_clips_json(chunk)
        args = ["--clips-json", cj, "--model", model_name]
        if model_dir_resolved:
            args.extend(["--model-dir", model_dir_resolved])
        timeout = (_BATCH_TIMEOUT_BASE_S
                   + _BATCH_TIMEOUT_PER_CLIP_S * len(chunk))
        r = _spawn_runner(python, args, timeout)
        got = (r["payload"] or {}).get("clips") if r["ok"] else None
        if not isinstance(got, list):
            # 整批失败如实标记（不静默）；同 timing 后续不覆盖
            for c in chunk:
                if c["timing"] in done_timings:
                    by_timing[c["timing"]] = failed(
                        c["timing"], f"批量转写失败: {r['error']}")
        else:
            for item in got:
                t = str((item or {}).get("timing") or "")
                if t not in done_timings:
                    continue
                segs = item.get("segments")
                by_timing[t] = {
                    "timing": t,
                    "ok": not item.get("error"),
                    "text": str(item.get("text_all") or ""),
                "segments": segs if isinstance(segs, list) else [],
                "error": str(item.get("error") or "")}
        with contextlib.suppress(OSError):
            os.unlink(cj)
        done += len(chunk)
        if progress is not None:
            with contextlib.suppress(Exception):
                progress(done, total)   # 进度回调故障不阻断
    with contextlib.suppress(OSError):
        os.unlink(probe_json)
    for t in timings:
        if t not in done_timings and not by_timing[t]["error"]:
            by_timing[t] = failed(t, skipped_note)
    return [by_timing[t] for t in timings]


def build_crosscheck_block(clips: list[dict], asr_python: str = "",
                           model: str = "large-v2",
                           char_limit: int = 2000) -> dict:
    """切片批量重转写并聚合对照块（C6：≤2000 截断+非真值声明）。

    clips 元素＝{path, timing, current}。返回 {"block": str, "segments": n,
    "failed": n}；无可用片段 block=""。"""
    lines: list[str] = [
        "信度声明：以下 ASR 转写文本为本机语音识别输出，非真值（转写可能"
        "自带错误），仅作漏听/误听对照参考；不改变任何默认阈值。"]
    segments = 0
    failed = 0
    for clip in clips:
        r = run_transcription(clip.get("path") or "", asr_python, model)
        if not r["ok"] or not r["text"].strip():
            failed += 1
            lines.append(f"- 段 {clip.get('timing') or clip.get('start')}"
                         f"：ASR 失败（{r['error'][:60]}）")
            continue
        segments += 1
        lines.append(f"- 段 {clip.get('timing') or clip.get('start')}："
                     f"ASR 转写：{r['text'].strip()[:200]}"
                     + (f"（现译：{str(clip.get('current'))[:100]}）"
                        if clip.get("current") else ""))
    if not segments:
        return {"block": "", "segments": 0, "failed": failed}
    block = "\n".join(lines)
    if len(block) > char_limit:
        block = block[:char_limit] + "\n（对照块超长已截断）"
    return {"block": block, "segments": segments, "failed": failed}


def slice_clips(media_path: str, timings: list[str],
                max_clips: int = _MAX_CLIPS) -> dict:
    """按 SRT timing 列表抽 16k 单声道 wav 片段（ffmpeg list-args，无 shell）。

    timings：["HH:MM:SS,mmm --> HH:MM:SS,mmm", ...]（疑似漏听段等），超
    max_clips 截断。落数据根 Temp/media_clips/（sha1 指纹命名，复用
    audio_detect 临时面语义）。返回 {"ok", "clips": [{path, timing}],
    "error", "skipped"}；ffmpeg 缺失/失败逐段降级。2.7.1 件1：ffmpeg
    路径经 resolve_ffmpeg 解析（PATH→上游 env 自带目录），subprocess
    显式传绝对路径，不再依赖 app 进程 PATH。"""
    ffmpeg = resolve_ffmpeg(_first_available_python())
    if not ffmpeg:
        return {"ok": False, "clips": [], "error": "ffmpeg 不可用",
                "skipped": len(timings)}
    if not os.path.isfile(media_path):
        return {"ok": False, "clips": [], "error": "媒体文件不存在",
                "skipped": len(timings)}
    d = Path(paths.data_subdir("Temp", _CLIPS_SUBDIR))
    d.mkdir(parents=True, exist_ok=True)
    import hashlib
    fingerprint = hashlib.sha256(        # 非加密用途：切片缓存名（Mimosa 建议 sha256）
        f"{media_path}|{sorted(timings)[:max_clips]}".encode()
    ).hexdigest()[:12]

    def _sec(ts: str) -> float:
        hh, mm, rest = ts.split(":")
        ss, ms = rest.split(",")
        return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000

    clips: list[dict] = []
    skipped = 0
    for timing in timings[:max_clips]:
        try:
            start_s, end_s = timing.split("-->")
            start = _sec(start_s.strip())
            dur = max(0.5, _sec(end_s.strip()) - start)
        except (ValueError, AttributeError):
            skipped += 1
            continue
        out = d / f"clip_{fingerprint}_{len(clips)}.wav"
        try:
            proc = subprocess.run(
                [ffmpeg, "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
                 "-i", media_path, "-vn", "-ac", "1", "-ar", "16000",
                 str(out)],
                capture_output=True, encoding="utf-8", errors="replace",
                timeout=120,
                creationflags=CREATE_NO_WINDOW)  # GUI windowed 防黑框（批0；POSIX=0 无操作）
        except (OSError, subprocess.TimeoutExpired):
            skipped += 1
            continue
        if proc.returncode == 0 and out.is_file() \
                and out.stat().st_size > 0:
            clips.append({"path": str(out), "timing": timing})
        else:
            skipped += 1
    return {"ok": bool(clips), "clips": clips,
            "error": "" if clips else "无可用切片", "skipped": skipped}


def cleanup_clips(max_age_s: int = 0) -> int:
    """切片临时目录清理（C8 best-effort，不抛）。"""
    d = Path(paths.data_subdir("Temp", _CLIPS_SUBDIR))
    removed = 0
    if not d.is_dir():
        return 0
    now = time.time()
    for p in d.iterdir():
        try:
            if max_age_s and now - p.stat().st_mtime < max_age_s:
                continue
            p.unlink()
            removed += 1
        except OSError:
            continue
    return removed
