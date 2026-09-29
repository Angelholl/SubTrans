"""
v2 共享工具（临时目录/TM 初始化/词库合并/路径解析）
====================================================
pipeline_v2（两阶段管线）复用的公共工具：
  - 临时目录登记与退出清理（CREATED_TMP_DIRS / cleanup_created_tmp_dirs）
  - 翻译记忆库初始化（_init_tm）
  - 词库合并加载（load_glossary_merged / learned_glossary_path）
  - 阶段路径解析（_resolve_stage_paths / refine_tmp_dir / strip_lang_suffix）
legacy 管线（已删除）的编排器（run 流程与单文件执行及其阶段辅助函数）不再保留。
"""

import hashlib
import threading
from pathlib import Path

from subtransjav import paths

# 本次进程创建过的临时目录（供退出时清理）
CREATED_TMP_DIRS: list[str] = []
_tmp_dirs_lock = threading.Lock()

from .config import TEMP_DIR, RefineConfig  # noqa: E402  # 延迟导入规避循环依赖
from .glossary import load_glossary_ex  # noqa: E402  # 延迟导入规避循环依赖


class RefineError(Exception):
    pass


def _init_tm(cfg: RefineConfig):
    """初始化翻译记忆库（如启用）。返回 TranslationMemory 或 None。"""
    if not cfg.tm_enabled:
        return None
    try:
        from .tm import TranslationMemory
        # 2.1 方向参数化（D2026-0930-05 批内缺陷修复）：实例缺省方向接
        # cfg——修复 zh→en 任务学出的 TM 行落 ('ja','zh') 缺省列
        # （与 _is_default_direction 同口径：字段缺席/空值回退 ja/zh）
        src = getattr(cfg, "source_lang", None) or "ja"
        tgt = getattr(cfg, "target_lang", None) or "zh"
        tm = (TranslationMemory(cfg.tm_db_path, source_lang=src,
                                target_lang=tgt) if cfg.tm_db_path
              else TranslationMemory(source_lang=src, target_lang=tgt))
        return tm
    except Exception as e:
        print(f"⚠️ [refine] 翻译记忆库初始化失败，已忽略: {e}")
        return None


def strip_lang_suffix(stem: str) -> str:
    """去掉文件名 stem 中的语言后缀（.japanese/.chinese/.translated）。

    单一实现：产物命名与 webview_gui/api.py 临时目录
    计算均复用本函数，避免两处实现漂移。
    """
    for suf in (".japanese", ".chinese", ".translated"):
        if stem.endswith(suf):
            return stem[: -len(suf)]
    return stem


def _resolve_stage_paths(cfg: RefineConfig, in_path: str):
    p = Path(in_path).resolve()
    out_dir = Path(cfg.output_dir).resolve() if cfg.output_dir else p.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = strip_lang_suffix(p.stem)    # 清理上游可能带来的语言后缀
    return str(p), str(out_dir), stem


def refine_tmp_dir(in_path: str, stem: str) -> str:
    """输入文件对应的流水线工作区，统一收束到 项目根/Temp/。

    目录名 = 输入文件名 + 输入完整路径哈希（跨目录同名文件互不冲突）。
    GUI 退出清理与 CLI 清理均基于此单一来源。
    """
    h = hashlib.sha1(Path(in_path).resolve().as_posix().lower().encode("utf-8")).hexdigest()[:10]
    d = Path(TEMP_DIR) / f"{stem}.{h}.refine_tmp"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def learned_glossary_path() -> str:
    """自动学习词库路径（数据根/config/glossary_learned.csv）。"""
    return paths.data_subdir("config", "glossary_learned.csv")


def load_glossary_override(cfg: RefineConfig) -> list:
    """加载最高优先覆盖词表（cfg.glossary_override_path）。

    v1.3.0 D2 终选（D2026-0925-01 补充裁决）：三级优先级链
    ``--glossary-override > 用户 glossary.csv > learned``；
    内置 rules 独立分域，不并入本链。路径为空/文件缺省时返回 []。
    """
    return load_glossary_ex(cfg.glossary_override_path) \
        if getattr(cfg, "glossary_override_path", "") else []


def load_glossary_merged(cfg: RefineConfig) -> list:
    """三级显式合并：override 全量在前 > 用户词库 > learned 追加。

    v1.3.0 D2 终选（D2026-0925-01 补充裁决）三级优先级链：
    ``--glossary-override > 用户 glossary.csv > learned``；
    内置 rules 独立分域，不并入本链。

    v1.2.2 D：返回三元组 ``[(src, dst, aliases), ...]``——第三列为
    词表可选列 target_aliases（`|` 分隔，缺列/空 = 无别名；override
    词条同样支持别名列）；learned 自学习词库不生成别名（恒为空元组）。
    两列消费者（match_glossary / format_glossary_block）已兼容三列词条。

    低层（用户词库/learned）与更高层同 src 时被压制不重复追加
    （原 learned "同 src 不覆盖" 语义保持并扩展到 override 层），
    压制点统一收集，函数末打印 ⚠️ 覆盖冲突告警（同一 src 多层压制
    合并为一行列出）；返回结构不变，调用方零改动。
    """
    glossary = load_glossary_override(cfg)
    _src_layer = {s: "override" for s, _d, _a in glossary}
    _override_srcs = {s for s, _d, _a in glossary}
    _user = load_glossary_ex(cfg.glossary_path) if cfg.glossary_path else []
    # 压制点收集 (src, 保留层, 保留译法, 忽略层, 忽略译法)，末尾统一告警
    _suppressed: list = []
    # 仅当 override 启用时才压制用户同 src 词（override 为空时用户层
    # 保持旧链逐字节语义，含用户文件内部重复词条原样保留）
    if _override_srcs:
        _override_dst: dict = {}
        for s, d, _a in glossary:
            _override_dst.setdefault(s, d)
        for s, d, a in _user:
            if s not in _override_srcs:
                glossary.append((s, d, a))
                _src_layer.setdefault(s, "user")
            else:                       # 同 src 被 override 压制（D2 终选）
                _suppressed.append(
                    (s, "override", _override_dst[s], "user", d))
    else:
        glossary.extend(_user)
        for s, _d, _a in _user:
            _src_layer.setdefault(s, "user")
    _existing_srcs = {s for s, _d, _a in glossary}
    _learned = load_glossary_ex(learned_glossary_path())
    if _learned:
        for s, d, a in _learned:
            if s not in _existing_srcs:
                glossary.append((s, d, a))
                _existing_srcs.add(s)
                _src_layer[s] = "learned"
            else:                       # learned 同 src 只留首条（§11.5）
                _kept = next(e for e in glossary if e[0] == s)
                _suppressed.append(
                    (s, _src_layer[s], _kept[1], "learned", d))
    if glossary:
        print(f"📚 [refine] 词库已加载：{len(glossary)} 条")
    if _suppressed:
        _by_src: dict = {}
        for s, k_layer, k_val, d_layer, d_val in _suppressed:
            info = _by_src.setdefault(s, {"keep": (k_layer, k_val),
                                          "drops": []})
            info["drops"].append((d_layer, d_val))
        segs = []
        for s, info in _by_src.items():
            k_layer, k_val = info["keep"]
            drops = " ".join(f"忽略[{lay}]{val}" for lay, val in info["drops"])
            segs.append(f"src={s} 保留[{k_layer}]{k_val} {drops}")
        print(f"⚠️ 词库覆盖冲突 {len(_suppressed)} 处：" + "；".join(segs))
    return glossary


def cleanup_created_tmp_dirs():
    """删除本进程创建过的全部 .refine_tmp 临时目录（忽略错误）"""
    import shutil
    with _tmp_dirs_lock:
        snapshot = list(CREATED_TMP_DIRS)
        CREATED_TMP_DIRS.clear()
    cleaned = []
    for d in snapshot:
        if d and Path(d).is_dir():
            shutil.rmtree(d, ignore_errors=True)
            cleaned.append(d)
    return cleaned
