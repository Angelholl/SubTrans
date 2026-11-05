"""EXE 首发数据迁移机制（D2026-0929-05 P2 + D2026-0929-07 点 2 + 08 点 3 定案）
================================================================================

仅 frozen（EXE）形态、数据根为 frozen 默认（安装目录旁路新默认，或旧
%LOCALAPPDATA% 默认位被收养；env/pointer 显式指定不迁移）、且旧根存在
可迁数据时执行一次性迁移；pip/源码形态零感知（永不触发、不写任何文件）。
收养旧根时旧根即数据根本身，迁移以 ``not-applicable:legacy-is-root`` 直返。

三段式（硬约束，顺序不可反）：
  1) 备份：磁盘空间预检（需 ≥ 源体积×2，不足即中止）→ 旧位数据 zip 备份到
     数据根 ``backups/pre-2.0.0-YYYYMMDD-HHMMSS.zip``，zip 内含
     ``migration_manifest.json``（文件清单+sha256+tm.db 迁移前行数）；
     保留最近 5 份。旧位文件原样保留 ≥ paths.LEGACY_RETENTION_EOL。
  2) 迁移：tm.db 先 ``PRAGMA wal_checkpoint(TRUNCATE)``（失败=本轮中止、
     下次启动重试，绝不在活写窗口三件齐拷）→ 复制到临时目录 → 校验
     （SQLite integrity_check + JSON 可解析 + DPAPI 密钥解密自检 +
     大小/哈希对 manifest）。
  3) 原子切换：全部校验通过 → 写入数据根（含数据根 manifest）→
     MIGRATION_SENTINEL 最后写（内容=manifest sha256+时间戳）。
     任何一步失败 → 删除数据根中仅 manifest 清单匹配的迁移残留
     （绝不触碰白名单外文件）→ 返回失败，旧位原样。

半迁移自愈：哨兵存在但数据根 manifest 缺失/校验失败 = 无效哨兵（哨兵晚于
manifest 写，其信息量依赖 manifest 可信）→ 按未迁移处理并给可见警告；
"备份 zip 存在 + 新根不完整 + 无有效哨兵" → 清理仅限 manifest 匹配残留
后按未迁移处理（新根白名单外用户文件绝不误删）。

多实例：迁移全程持 artifact_lock（锁键=migration），冲突=另一实例在迁，
本次跳过。幂等：有效哨兵存在即直接返回。任何异常不阻塞首启：返回失败
并由调用方打印警告，程序以（可能为空的）新根继续，数据可从 backups
zip 寻回。

C22 校准门 seeding（D2026-1101-01）：与迁移共用同一首启插桩点，但**独立**
于迁移三态——frozen 默认数据根下恒执行一次「缺行补行」：门控文件不存在
才写缺省行（enabled=true + rules_sha1/app_version 指纹），存量行（含显式
enabled:false、旧版五字段测量行）零扰动；写入走同目录临时文件 + os.replace
原子替换，失败零残留并记日志。dev 实测字段（measured_at/precision_lb/
coverage/n）只属于校准工具输出，绝不随 seeding 下发。读取侧按行型分治
（D2026-1105-06 裁决③）：测量行指纹不匹配（含缺失、版本失配）关门并要求
重新校准——旧测量依据不得静默复用；seeded 缺省行只绑定 rules_sha1，纯版本
升级不关门（仅记日志）。该判定是自束防误用（防旧测量依据静默复用/误配开门），
非对抗性安全边界——能改安装文件者不受其约束。
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

from subtrans import paths
from subtrans.utils.env_compat import env_get

__all__ = ["ensure_migrated", "import_legacy", "seed_c22_gate",
           "evaluate_c22_gate", "c22_gate_fingerprint", "C22_GATE_RELPATH"]

_logger = logging.getLogger(__name__)

MIGRATION_VERSION = "2.0.0"
BACKUP_PREFIX = "pre-2.0.0-"
BACKUP_KEEP = 5                       # 备份 zip 保留最近份数
MANIFEST_NAME = "migration_manifest.json"
LEGACY_ROOT_ENV = "SUBTRANSJAV_LEGACY_ROOT"   # 过渡别名（兜底，D2026-1106-02 ①）

# 属「frozen 默认」的来源标签集合（D2026-1103-05 项②）：新默认（安装目录
# 旁路）与旧默认收养两标签都要放行迁移与首启插桩门，env/pointer 自定义根
# 保持零感知。改此集合须同步 tests/test_c22_gate_seeding.py 与 paths.py 标签面。
_FROZEN_DEFAULT_SOURCES = ("frozen-default", "frozen-legacy-default")


def _same_path(a: Path, b: Path) -> bool:
    """大小写/斜杠归一后的同径判定（Windows 语义，复用 paths 口径）。"""
    return paths.normalize_path_case(str(a)) == paths.normalize_path_case(str(b))

# 旧根内相对路径白名单（存在才迁；全部缺失不算失败）
_BASE_FILES: tuple[str, ...] = (
    "Temp/translation_memory/tm.db",
    "Temp/translation_memory/glossary_conflict_watch.json",
    "config/api_keys.bin",
    "config/user_settings.json",
    "config/refine_stage_settings.json",
    "config/glossary.csv",
    "config/glossary_learned.csv",
    "config/fullchain_c22.json",
)
# tm.db 的 WAL/SHM 旁车（仅在主库存在时一并迁）与观察 json 的 .bak
_TM_SIDECARS: tuple[str, ...] = ("Temp/translation_memory/tm.db-wal",
                                 "Temp/translation_memory/tm.db-shm")
_WATCH_BAK = "Temp/translation_memory/glossary_conflict_watch.json.bak"


class MigrationError(RuntimeError):
    """迁移校验/落盘失败（触发残留清理与失败返回）。"""


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------
def _log(verbose: bool, message: str) -> None:
    if verbose:
        print(message)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _disk_free_bytes(path: Path) -> int:
    """目标盘剩余空间（独立函数便于故障注入测试）。"""
    return shutil.disk_usage(path).free


def _discover_legacy_root() -> Path | None:
    """旧根发现。

    优先级：
    1. 环境变量 ``SUBTRANS_LEGACY_ROOT``（优先；旧名 ``SUBTRANSJAV_LEGACY_ROOT``
       兜底，D2026-1106-02 ①兼容层）（诊断/测试显式指定）；
    2. frozen 形态下 EXE 所在目录（EXE 首发放/升到旧仓库根目录的场景，
       旧 pip/源码数据即在安装目录 = 旧仓库根）；
    3. 旧 frozen 默认位 ``%LOCALAPPDATA%\\SubTrans``（D2026-1103-05 项②：
       新默认改安装目录旁路后，3.1.1 及以前的存量数据落在此位，
       须被认作旧根；有锚点才认，无锚点维持 2 的既有回退语义）。
    """
    env = (env_get("LEGACY_ROOT") or "").strip()
    if env:
        return Path(env)
    import sys as _sys
    if getattr(_sys, "frozen", False):
        exe_dir = Path(_sys.executable).resolve().parent
        if not paths.has_data_anchors(exe_dir):
            old_default = paths.legacy_default_data_root()
            if old_default != exe_dir and paths.has_data_anchors(old_default):
                return old_default
        return exe_dir
    return None


def _collect_sources(legacy_root: Path) -> list[tuple[str, Path]]:
    """旧根内实际存在的可迁文件（保持白名单顺序）。"""
    srcs: list[tuple[str, Path]] = []
    for rel in _BASE_FILES:
        p = legacy_root.joinpath(*Path(rel).parts)
        if p.is_file():
            srcs.append((rel, p))
            if rel.endswith("tm.db"):
                for side in _TM_SIDECARS:
                    sp = legacy_root.joinpath(*Path(side).parts)
                    if sp.is_file():
                        srcs.append((side, sp))
            elif rel.endswith("glossary_conflict_watch.json"):
                bp = legacy_root.joinpath(*Path(_WATCH_BAK).parts)
                if bp.is_file():
                    srcs.append((_WATCH_BAK, bp))
    return srcs


def _tm_rows(db_path: Path) -> int:
    """tm.db 迁移前行数（best-effort：表缺失/库异常计 0）。"""
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.execute("SELECT COUNT(*) FROM tm_entries")
            return int(cur.fetchone()[0])
        finally:
            conn.close()
    except sqlite3.Error:
        return 0


def _checkpoint_wal(db_path: Path) -> None:
    """对源 tm.db 执行 wal_checkpoint(TRUNCATE)；失败上抛（本轮中止）。"""
    conn = sqlite3.connect(str(db_path), timeout=10)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _manifest_bytes(manifest: dict[str, Any]) -> bytes:
    return json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode("utf-8")


def _manifest_sha256(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(_manifest_bytes(manifest)).hexdigest()


# ---------------------------------------------------------------------------
# 半迁移自愈
# ---------------------------------------------------------------------------
def _valid_sentinel(root: Path) -> str | None:
    """有效哨兵校验：哨兵存在 + 数据根 manifest 存在可解析 + 哨兵内容含
    manifest sha256。通过返回 manifest sha256，否则 None（无效哨兵）。"""
    sentinel = root / paths.MIGRATION_SENTINEL
    if not sentinel.is_file():
        return None
    try:
        content = sentinel.read_text(encoding="utf-8")
        manifest = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
        sha = _manifest_sha256(manifest)
    except (OSError, ValueError):
        return None
    return sha if sha in content else None


def _latest_backup_manifest(root: Path) -> dict[str, Any] | None:
    """最新备份 zip 内的 manifest（自愈清理的唯一依据；读不到返回 None）。"""
    backups = root / "backups"
    if not backups.is_dir():
        return None
    zips = sorted(backups.glob(f"{BACKUP_PREFIX}*.zip"))
    for zp in reversed(zips):
        try:
            with zipfile.ZipFile(zp) as zf:
                raw = zf.read(MANIFEST_NAME)
            manifest = json.loads(raw.decode("utf-8"))
            if isinstance(manifest, dict) and isinstance(manifest.get("files"), list):
                return manifest
        except (OSError, ValueError, KeyError):
            continue
    return None


def _cleanup_residuals(root: Path, rels: list[str], verbose: bool) -> None:
    """删除数据根内仅 manifest 清单匹配的迁移残留（绝不触碰白名单外文件）。"""
    removed = []
    for rel in rels:
        p = root.joinpath(*Path(rel).parts)
        try:
            if p.is_file():
                p.unlink()
                removed.append(rel)
        except OSError as e:
            _log(verbose, f"⚠️ [迁移] 残留清理失败（忽略）: {rel} ({e})")
    with contextlib.suppress(OSError):
        (root / MANIFEST_NAME).unlink()
    if removed:
        _log(verbose, f"🧹 [迁移] 已清理迁移残留（仅限清单内 {len(removed)} 个文件）")


def _preheal(root: Path, verbose: bool) -> None:
    """半迁移自愈：无有效哨兵时按最新备份 manifest 清理新根残留。"""
    manifest = _latest_backup_manifest(root)
    if manifest is None:
        return
    rels = [str(f.get("path", "")) for f in manifest["files"] if f.get("path")]
    _log(verbose, "🔍 [迁移] 检测到半迁移残留（备份在、无有效哨兵），按清单清理")
    _cleanup_residuals(root, rels, verbose)


# ---------------------------------------------------------------------------
# 三段式
# ---------------------------------------------------------------------------
def _build_manifest(legacy_root: Path, srcs: list[tuple[str, Path]]) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for rel, src in srcs:
        entry: dict[str, Any] = {
            "path": rel,
            "sha256": _sha256_file(src),
            "size": src.stat().st_size,
        }
        if rel.endswith("tm.db"):
            entry["tm_rows"] = _tm_rows(src)
        files.append(entry)
    return {
        "migration_version": MIGRATION_VERSION,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "legacy_root": str(legacy_root),
        "files": files,
    }


def _write_backup(root: Path, manifest: dict[str, Any],
                  srcs: list[tuple[str, Path]]) -> Path:
    """备份 zip：数据根 backups/pre-2.0.0-TS.zip，含 manifest + 旧位文件；
    创建后裁剪只留最近 BACKUP_KEEP 份。"""
    backups = root / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    name = f"{BACKUP_PREFIX}{time.strftime('%Y%m%d-%H%M%S')}.zip"
    zpath = backups / name
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_NAME, _manifest_bytes(manifest))
        for rel, src in srcs:
            zf.write(src, rel)
    zips = sorted(backups.glob(f"{BACKUP_PREFIX}*.zip"))
    for old in zips[:-BACKUP_KEEP]:
        with contextlib.suppress(OSError):
            old.unlink()
    return zpath


def _validate_staged(staging: Path, manifest: dict[str, Any]) -> None:
    """对暂存副本逐文件校验：大小/哈希对 manifest；tm.db integrity_check；
    JSON 可解析；DPAPI 密钥解密自检（secrets 模块读一次）。"""
    from subtrans.refine import secrets as _secrets

    for entry in manifest["files"]:
        rel: str = entry["path"]
        p = staging.joinpath(*Path(rel).parts)
        if not p.is_file() or p.stat().st_size != entry["size"]:
            raise MigrationError(f"暂存副本大小校验失败: {rel}")
        if _sha256_file(p) != entry["sha256"]:
            raise MigrationError(f"暂存副本哈希校验失败: {rel}")
        if rel.endswith("tm.db"):
            try:
                conn = sqlite3.connect(str(p))
                try:
                    row = conn.execute("PRAGMA integrity_check").fetchone()
                finally:
                    conn.close()
            except sqlite3.Error as e:
                raise MigrationError(f"tm.db integrity_check 未通过: {rel} ({e})") from e
            if not row or row[0] != "ok":
                raise MigrationError(f"tm.db integrity_check 未通过: {rel}")
        elif rel.endswith(".json"):
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except ValueError as e:
                raise MigrationError(f"JSON 校验失败: {rel} ({e})") from e
        elif rel.endswith("api_keys.bin"):
            try:
                _secrets._read_raw(str(p))  # noqa: SLF001 - 解密自检需读原始库
            except Exception as e:
                raise MigrationError(f"DPAPI 密钥解密自检失败: {rel} ({e})") from e


def _install(staging: Path, root: Path, manifest: dict[str, Any]) -> None:
    """把暂存副本按清单写入数据根（逐文件 tmp+os.replace 原子化），
    数据根 manifest 随批写入（哨兵在其后另写，保持"哨兵最后"序）。"""
    for entry in manifest["files"]:
        rel = entry["path"]
        src = staging.joinpath(*Path(rel).parts)
        dst = root.joinpath(*Path(rel).parts)
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".migrating")
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
    tmp_m = root / (MANIFEST_NAME + ".migrating")
    tmp_m.write_bytes(_manifest_bytes(manifest))
    os.replace(tmp_m, root / MANIFEST_NAME)


def _verify_installed(root: Path, manifest: dict[str, Any]) -> None:
    """落位后按 manifest 复核（防同源双坏的兜底闸）。"""
    for entry in manifest["files"]:
        p = root.joinpath(*Path(str(entry["path"])).parts)
        if not p.is_file() or _sha256_file(p) != entry["sha256"]:
            raise MigrationError(f"落位复核失败: {entry['path']}")


def _write_sentinel(root: Path, manifest: dict[str, Any]) -> None:
    """哨兵最后写：内容=manifest sha256 + 时间戳。"""
    content = (f"migration-version={MIGRATION_VERSION}\n"
               f"manifest-sha256={_manifest_sha256(manifest)}\n"
               f"completed={time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
    (root / paths.MIGRATION_SENTINEL).write_text(content, encoding="utf-8")


def _run_migration(root: Path, legacy_root: Path,
                   srcs: list[tuple[str, Path]], verbose: bool) -> str:
    # 半迁移自愈（持锁后、任何写入前）
    _preheal(root, verbose)

    # 1) 磁盘空间预检：需 ≥ 源体积×2
    total = sum(p.stat().st_size for _, p in srcs)
    free = _disk_free_bytes(root)
    if free < total * 2:
        _log(verbose, f"❌ [迁移] 磁盘空间不足（需约 {total * 2} 字节，"
                      f"仅剩 {free}），迁移中止；请手动迁移或清理后重试")
        return "failed:disk-space"

    # 2) WAL checkpoint（失败=本轮中止，下次启动重试）。
    #    例外：库本体不可读（DatabaseError 且非锁忙类，如文件损坏）时
    #    checkpoint 无从执行，放行至校验阶段由 integrity_check 判死。
    tm_src = next((p for rel, p in srcs if rel.endswith("tm.db")), None)
    if tm_src is not None:
        try:
            _checkpoint_wal(tm_src)
        except sqlite3.OperationalError as e:
            _log(verbose, f"⚠️ [迁移] tm.db WAL checkpoint 失败（本轮中止，"
                          f"下次启动自动重试）: {e}")
            return "retry-wal"
        except Exception as e:  # noqa: BLE001 - 损坏库交由校验阶段判定
            _log(verbose, f"⚠️ [迁移] WAL checkpoint 无法执行"
                          f"（交由校验阶段判定）: {e}")

    # 3) 备份
    manifest = _build_manifest(legacy_root, srcs)
    try:
        zpath = _write_backup(root, manifest, srcs)
    except OSError as e:
        _log(verbose, f"❌ [迁移] 备份 zip 创建失败，迁移中止: {e}")
        return "failed:backup"
    _log(verbose, f"📦 [迁移] 备份完成: {zpath}")

    # 4) 复制到暂存目录 + 校验
    staging = Path(tempfile.mkdtemp(dir=root, prefix=".migration-staging-"))
    try:
        try:
            for rel, src in srcs:
                dst = staging.joinpath(*Path(rel).parts)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
            _validate_staged(staging, manifest)
        except MigrationError as e:
            _cleanup_residuals(root, [e2["path"] for e2 in manifest["files"]], verbose)
            _log(verbose, f"❌ [迁移] 迁移校验失败（旧位原样保留，"
                          f"备份见 {zpath}）: {e}")
            return "failed:validate"

        # 5) 原子切换：写入数据根 → 校验 → 哨兵最后写
        rels = [str(entry["path"]) for entry in manifest["files"]]
        try:
            _install(staging, root, manifest)
            _verify_installed(root, manifest)
        except (MigrationError, OSError) as e:
            _cleanup_residuals(root, rels, verbose)
            _log(verbose, f"❌ [迁移] 写入数据根失败（残留已按清单清理，"
                          f"旧位原样保留）: {e}")
            return "failed:install"
        _write_sentinel(root, manifest)
        _log(verbose, f"✅ [迁移] 数据迁移完成（{len(rels)} 个文件，"
                      f"tm.db {manifest['files'][0].get('tm_rows', 0)} 行）")
        return "migrated"
    finally:
        shutil.rmtree(staging, ignore_errors=True)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def _acquire_lock(root: Path):
    """迁移锁（artifact_lock 机制，锁键=migration）。

    返回 (handle, release)；冲突（另一实例在迁）抛 ArtifactLockConflict；
    机制不可用返回 (None, no-op)（降级无锁继续，沿既有三态契约）。
    """
    from subtrans.refine.artifact_lock import (
        acquire_artifact_lock,
        release_artifact_lock,
    )

    anchor = str(root / ".migration-lock-anchor")
    handle = acquire_artifact_lock(anchor, str(root))
    return handle, (lambda: release_artifact_lock(handle))


def _ensure_migrated_inner(verbose: bool) -> str:
    # 触发条件硬闸：pip/源码形态永不迁移（零感知）
    if not paths.is_frozen():
        return "not-applicable:pip"
    if paths.data_root_source() not in _FROZEN_DEFAULT_SOURCES:
        return "not-applicable:env-root"

    root = paths.data_root()
    legacy_root = _discover_legacy_root()
    if legacy_root is None:
        return "not-applicable:no-legacy-root"
    if _same_path(legacy_root, root):
        # 收养旧默认位当数据根本身（frozen-legacy-default）：数据已在位，
        # 不得把旧根往自己身上迁（D2026-1103-05 项②护栏 6）
        return "not-applicable:legacy-is-root"
    srcs = _collect_sources(legacy_root)
    if not srcs:
        return "not-applicable:no-legacy-data"

    # 首启时数据根尚不存在：先建根（frozen 形态常规初始化）
    root.mkdir(parents=True, exist_ok=True)

    # 哨兵有效性（读侧，无锁）：有效 → 幂等直返；无效 → 警告并按未迁移处理
    if _valid_sentinel(root) is not None:
        return "already-migrated"
    if (root / paths.MIGRATION_SENTINEL).exists():
        _log(verbose, "⚠️ [迁移] 检测到无效哨兵（manifest 缺失/校验失败），"
                      "按未迁移处理并重试迁移")

    from subtrans.refine.artifact_lock import ArtifactLockConflict

    try:
        handle, release = _acquire_lock(root)
    except ArtifactLockConflict:
        _log(verbose, "ℹ️ [迁移] 另一实例正在迁移，本次跳过")
        return "skipped-locked"
    if handle is None:
        _log(verbose, "⚠️ [迁移] 锁机制不可用（降级无锁继续）")
    try:
        return _run_migration(root, legacy_root, srcs, verbose)
    finally:
        release()


def ensure_migrated(verbose: bool = False) -> str:
    """EXE 首发数据迁移入口（幂等、全容错、失败永不阻塞首启）。

    返回状态串（供桩点日志/测试断言）：
    ``migrated`` / ``already-migrated`` / ``skipped-locked`` /
    ``retry-wal`` / ``failed:*`` / ``not-applicable:*``。

    同一插桩点顺带执行 C22 门控 seeding（frozen 默认数据根才动作，
    与迁移三态解耦；失败只记日志，返回串不变）。
    """
    try:
        status = _ensure_migrated_inner(verbose)
    except Exception as e:  # noqa: BLE001 - 全容错：失败永不阻塞首启
        _log(verbose, f"⚠️ [迁移] 数据迁移异常（程序以新根继续，"
                      f"旧数据可从数据根 backups/ 寻回）: {type(e).__name__}: {e}")
        status = "failed:exception"
    if status.split(":", 1)[0] in ("failed", "retry-wal") \
            or status == "skipped-locked":
        # 迁移未完成：旧根门控行尚未到达新根，此时补 enabled=true 缺省行，
        # 下轮迁移到达旧显式行后会因「存量零扰动」永久驻留——等于用缺省
        # 意志顶替用户显式意志（D2026-1101-01 §三①）。跳过本轮 seeding，
        # 门保持关闭（fail-closed 安全方向），待下轮首启迁移成功后自然补行。
        _log(verbose, f"ℹ️ [C22] 迁移未完成（{status}），本轮跳过门控补行"
                      f"（防顶替旧根显式意志，下轮首启重试）")
        return status
    try:
        _seed_c22_gate_on_startup(verbose)
    except Exception as e:  # noqa: BLE001 - seeding 失败不阻塞首启（门保持关闭）
        _log(verbose, f"⚠️ [C22] 门控 seeding 异常（忽略，门保持关闭）: "
                      f"{type(e).__name__}: {e}")
    return status


# ---------------------------------------------------------------------------
# C22 校准门 seeding（D2026-1101-01：把「配置行到达用户机」做幂等防呆）
# ---------------------------------------------------------------------------
C22_GATE_RELPATH = "config/fullchain_c22.json"
C22_GATE_FILENAME = "fullchain_c22.json"
# 仓库 dev 实测字段（校准工具输出专属），seeding 缺省行一律不带
_C22_DEV_METRIC_KEYS: tuple[str, ...] = ("measured_at", "precision_lb",
                                         "coverage", "n")


def _c22_gate_dir(config_dir: str | Path | None) -> Path:
    """门控落点目录：显式传入（测试/工具）优先，否则数据根 ``config/``。

    用 ``paths.data_root()`` 现算而非 import 期常量 ``config.CONFIG_DIR``：
    frozen 首启插桩点在 import 之后才确定数据根（测试亦需可重定向），
    两者在正常启动路径等价。
    """
    if config_dir is not None:
        return Path(config_dir)
    return Path(paths.data_root()) / "config"


def c22_gate_fingerprint(app_version: str | None = None) -> tuple[str | None, str]:
    """返回当前生效的 ``(rules_sha1, app_version)`` 指纹。

    rules_sha1＝source_hallucination 规则集语义哈希（用户覆盖优先，包内
    回退；与 manifest 的 gate0_rules_sha1 同源），解析不可得时返回 None
    （调用侧据此 fail-closed：无锁不补行、读取侧关门）。
    """
    rules_sha1: str | None = None
    try:
        from subtrans.refine.source_hallucination import gate0_rules_sha1
        rules_sha1 = gate0_rules_sha1()
    except Exception:  # noqa: BLE001 - 规则解析不可得=无指纹（fail-closed）
        rules_sha1 = None
    if app_version is None:
        try:
            from subtrans.__version__ import __version__
            app_version = str(__version__)
        except Exception:  # noqa: BLE001 - 版本不可得按空串（必然不匹配→关门）
            app_version = ""
    return rules_sha1, str(app_version)


def seed_c22_gate(config_dir: str | Path | None = None, *,
                  app_version: str | None = None,
                  verbose: bool = False) -> str:
    """C22 门控缺行补行（幂等反覆盖，D2026-1101-01 §三①）。

    只做「缺行才补」：门控文件不存在时写缺省行
    ``{"enabled": true, "rules_sha1", "app_version"}``（不带任何 dev 实测
    字段）；存量文件一律零扰动——显式 ``enabled:false`` 是用户意志，
    旧版五字段测量行交由读取侧指纹校验关门并要求重校准。

    损坏/半态（JSON 不可解析或非对象）不覆写、不崩，记日志后返回
    ``skipped-invalid``（读取侧同款 fail-closed）。写入走同目录临时文件
    + ``os.replace`` 原子替换，失败零残留。

    返回 ``seeded`` / ``kept-existing`` / ``skipped-invalid`` /
    ``failed:*``。
    """
    try:
        target = _c22_gate_dir(config_dir) / C22_GATE_FILENAME
        if target.exists():
            try:
                data = json.loads(target.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001 - 损坏=保留原文件并关门
                _logger.warning("C22 门控文件不可解析（%s），保留原文件并关门: %s",
                                type(e).__name__, target)
                _log(verbose, "⚠️ [C22] 门控文件损坏，保留原文件（需重新校准）")
                return "skipped-invalid"
            if not isinstance(data, dict):
                _logger.warning("C22 门控文件非 JSON 对象（%s），保留原文件并关门: %s",
                                type(data).__name__, target)
                _log(verbose, "⚠️ [C22] 门控文件形态非法，保留原文件（需重新校准）")
                return "skipped-invalid"
            return "kept-existing"

        rules_sha1, version = c22_gate_fingerprint(app_version)
        if not rules_sha1:
            _logger.warning("C22 门控 seeding 中止：规则集指纹不可得（无锁不补行）")
            _log(verbose, "⚠️ [C22] 规则集指纹不可得，跳过补行（门保持关闭）")
            return "failed:no-rules-fingerprint"

        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"enabled": True, "rules_sha1": rules_sha1,
                   "app_version": version}
        _c22_atomic_write_json(target, payload)
        _log(verbose, f"✅ [C22] 已补门控缺省行（enabled=true, "
                      f"app_version={version}）")
        return "seeded"
    except Exception as e:  # noqa: BLE001 - 失败零残留，门保持关闭
        _logger.warning("C22 门控 seeding 失败（fail-closed，不落半态）: %s: %s",
                        type(e).__name__, e)
        _log(verbose, f"⚠️ [C22] 门控 seeding 失败（忽略，门保持关闭）: {e}")
        return f"failed:{type(e).__name__}"


def _c22_atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """同目录临时文件 + fsync + os.replace（复用 fs_utils 既有原子写）。"""
    from subtrans.refine.fs_utils import _atomic_write_text
    text = json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    _atomic_write_text(path, text)


def evaluate_c22_gate(gate_path: str | Path, *,
                      rules_sha1: str | None = None,
                      app_version: str | None = None) -> tuple[bool, str]:
    """门控读取判定（纯读、零写）：返回 ``(是否开门, 原因码)``。

    原因码：``ok`` / ``missing`` / ``invalid`` / ``disabled`` /
    ``fingerprint-missing`` / ``fingerprint-mismatch`` /
    ``fingerprint-version-mismatch``。

    ``enabled is True`` 之外按**行型分治**（D2026-1105-06 裁决③）：

    - 测量行（含任一 dev 测量键，存在性判定、不看取值；混入/歧义按测量行
      fail-closed）：rules_sha1 失配→``fingerprint-mismatch``；版本失配→
      ``fingerprint-version-mismatch``（测量依据与版本绑定，升级即失效）。
    - seeded 行（无任何 dev 测量键）：只比 rules_sha1（失配→
      ``fingerprint-mismatch``）；版本失配→放行 ``(True, "ok")`` 并记一条
      warning（该行无校准证据可失效，纯版本升级不应关门）。
    - 两键存在性必填语义不变：缺失任一→``fingerprint-missing``。

    威胁模型：本判定是**自束防误用**（防止旧测量依据被静默复用、防止
    误配行开门），不是防对抗——能改本文件的攻击者可 outright 关闭门控。
    """
    try:
        data = json.loads(Path(gate_path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, "missing"
    except Exception:  # noqa: BLE001 - 损坏一律关门
        return False, "invalid"
    if not isinstance(data, dict):
        return False, "invalid"
    if data.get("enabled") is not True:
        return False, "disabled"
    expect_rules, expect_version = c22_gate_fingerprint(app_version)
    if rules_sha1 is not None:
        expect_rules = rules_sha1
    stored_rules = data.get("rules_sha1")
    stored_version = data.get("app_version")
    if not stored_rules or not stored_version:
        return False, "fingerprint-missing"
    # 行型判定：存在性判定（空串/None 仍算测量行），混入按测量行 fail-closed
    is_measured_row = any(k in data for k in _C22_DEV_METRIC_KEYS)
    if stored_rules != expect_rules:
        return False, "fingerprint-mismatch"
    if stored_version != expect_version:
        if is_measured_row:
            return False, "fingerprint-version-mismatch"
        _logger.warning("C22 门控版本指纹不符但为 seeded 行（无测量证据可"
                        "失效），按 rules_sha1 放行: 存储 %s / 当前 %s",
                        stored_version, expect_version)
    return True, "ok"


def _seed_c22_gate_on_startup(verbose: bool) -> str:
    """首启插桩调用点：仅 frozen + 默认数据根动作（pip/源码形态零感知）。

    默认标签含新默认与旧默认收养两态（D2026-1103-05 项②），否则升级用户
    收养旧根后 C22 门永不插桩（3.1.1 前既得行为不得回退）。
    """
    if not paths.is_frozen():
        return "not-applicable:not-frozen"
    if paths.data_root_source() not in _FROZEN_DEFAULT_SOURCES:
        return "not-applicable:custom-root"
    return seed_c22_gate(verbose=verbose)


# ---------------------------------------------------------------------------
# 手动导入旧资产（--import-legacy，owner 裁定：不做导入向导，只迁 TM 库+词库）
# ---------------------------------------------------------------------------
# 用户指定范围内的可迁文件（conflict_watch 不在范围，跳过）
_IMPORT_FILES: tuple[str, ...] = (
    "Temp/translation_memory/tm.db",
    "config/glossary.csv",
    "config/glossary_learned.csv",
)


def _import_target(rel: str) -> Path:
    """旧根相对路径 → 数据根目标路径（动态读模块属性，测试可重定向）。"""
    parts = Path(rel).parts
    if rel.startswith("Temp/"):
        from subtrans.refine import tm as _tm
        return Path(_tm._DEFAULT_TM_DIR).joinpath(*parts[2:])  # noqa: SLF001 - 模块级锚点常量
    from subtrans.refine import config as _cfg
    return Path(_cfg.CONFIG_DIR).joinpath(*parts[1:])


def import_legacy(legacy_dir: str, verbose: bool = True) -> dict[str, Any]:
    """从旧目录手动导入旧资产（仅 tm.db[-wal/-shm] 与 glossary*.csv）。

    纪律（复用既有迁移机制）：
    - 仅接受目录（成员逐个 isfile 校验，conflict_watch 不在范围）；
    - 目标已存在且内容不同 → 先按 manifest+zip 机制备份到数据根 backups/；
    - tm.db 迁入前暂存校验（integrity_check + ensure_source_name_column），
      坏库绝不写目标；
    - 幂等：同哈希文件跳过；
    - 全程 list-args/无 shell；任何异常降级为 errors 条目，绝不抛出。

    返回 ``{"ok": bool, "imported": [...], "skipped": [...], "errors": [...]}``。
    """
    result: dict[str, Any] = {"ok": True, "imported": [], "skipped": [], "errors": []}
    try:
        src_root = Path(legacy_dir)
        if not src_root.is_dir():
            result["ok"] = False
            result["errors"].append(f"目录不存在: {legacy_dir}")
            print(f"❌ [导入] 目录不存在: {legacy_dir}")
            return result

        # 收集实际存在的可迁文件
        srcs: list[tuple[str, Path]] = []
        for rel in _IMPORT_FILES:
            p = src_root.joinpath(*Path(rel).parts)
            if p.is_file():
                srcs.append((rel, p))
                if rel.endswith("tm.db"):
                    for side in _TM_SIDECARS:
                        sp = src_root.joinpath(*Path(side).parts)
                        if sp.is_file():
                            srcs.append((side, sp))
        if not srcs:
            print("ℹ️ [导入] 未发现可导入的旧资产"
                  "（tm.db / glossary.csv / glossary_learned.csv 均不存在）")
            return result

        root = paths.data_root()

        # 阶段一：暂存副本 + 处理（tm.db integrity_check + ensure_source_name_column
        # 可能在暂存上补列，故幂等/备份判定一律基于"处理后的暂存"哈希）
        staged: list[tuple[str, Path, Path]] = []   # (rel, src, tmp)
        for rel, src in srcs:
            dst = _import_target(rel)
            tmp = dst.with_name(dst.name + ".importing")
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, tmp)
                if rel.endswith("tm.db"):
                    try:
                        conn = sqlite3.connect(str(tmp))
                        try:
                            row = conn.execute("PRAGMA integrity_check").fetchone()
                        finally:
                            conn.close()
                        if not row or row[0] != "ok":
                            raise MigrationError("integrity_check 未通过")
                        from subtrans.refine.tm import ensure_source_name_column
                        ensure_source_name_column(str(tmp))
                    except Exception as e:  # noqa: BLE001 - 坏库降级，绝不写目标
                        raise MigrationError(f"tm.db 校验失败: {e}") from e
            except Exception as e:  # noqa: BLE001 - 单文件失败不阻断其余导入
                with contextlib.suppress(OSError):
                    tmp.unlink(missing_ok=True)
                result["ok"] = False
                result["errors"].append(f"{rel}: {e}")
                _log(verbose, f"❌ [导入] 失败（目标未写入）: {rel} ({e})")
                continue
            staged.append((rel, src, tmp))

        # 阶段二：幂等判定 + 备份（目标已存在且内容不同 → 先备份再覆盖）
        overwrite: list[tuple[str, Path]] = []      # (rel, 现存目标)
        installable: list[tuple[str, Path, Path]] = []
        for rel, src, tmp in staged:
            dst = _import_target(rel)
            if dst.is_file() and _sha256_file(dst) == _sha256_file(tmp):
                with contextlib.suppress(OSError):
                    tmp.unlink(missing_ok=True)
                result["skipped"].append(rel)
                _log(verbose, f"⏭️ [导入] 内容一致，跳过: {rel}")
                continue
            if dst.is_file():
                overwrite.append((rel, dst))
            installable.append((rel, src, tmp))

        if overwrite:
            manifest = _build_manifest(src_root, overwrite)
            try:
                zpath = _write_backup(root, manifest, overwrite)
            except OSError as e:
                result["ok"] = False
                result["errors"].append(f"备份失败: {e}")
                print(f"❌ [导入] 目标文件备份失败，导入中止: {e}")
                for _rel, _src, tmp in installable:
                    with contextlib.suppress(OSError):
                        tmp.unlink(missing_ok=True)
                return result
            _log(verbose, f"📦 [导入] 已备份现有文件到: {zpath}")

        # 阶段三：落位（tmp + os.replace 原子化）
        for rel, _src, tmp in installable:
            dst = _import_target(rel)
            try:
                os.replace(tmp, dst)
            except OSError as e:  # noqa: BLE001 - 单文件失败不阻断其余导入
                with contextlib.suppress(OSError):
                    tmp.unlink(missing_ok=True)
                result["ok"] = False
                result["errors"].append(f"{rel}: {e}")
                _log(verbose, f"❌ [导入] 落位失败: {rel} ({e})")
                continue
            result["imported"].append(rel)
            _log(verbose, f"✅ [导入] 已导入: {rel} -> {dst}")

        if result["errors"]:
            result["ok"] = False
        print(f"✅ [导入] 旧资产导入完成：导入 {len(result['imported'])} 个，"
              f"跳过 {len(result['skipped'])} 个，错误 {len(result['errors'])} 个"
              + (f"；详情: {result['errors']}" if result["errors"] else ""))
        return result
    except Exception as e:  # noqa: BLE001 - 全容错：手动导入失败不抛出
        result["ok"] = False
        result["errors"].append(f"{type(e).__name__}: {e}")
        print(f"❌ [导入] 旧资产导入异常: {type(e).__name__}: {e}")
        return result
