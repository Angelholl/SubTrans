"""EXE 首发数据迁移机制（D2026-0929-05 P2 + D2026-0929-07 点 2 + 08 点 3 定案）
================================================================================

仅 frozen（EXE）形态、数据根为 frozen 默认（%LOCALAPPDATA%，env 显式指定
不迁移）、且旧根存在可迁数据时执行一次性迁移；pip/源码形态零感知（永不
触发、不写任何文件）。

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
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

from subtransjav import paths

__all__ = ["ensure_migrated"]

MIGRATION_VERSION = "2.0.0"
BACKUP_PREFIX = "pre-2.0.0-"
BACKUP_KEEP = 5                       # 备份 zip 保留最近份数
MANIFEST_NAME = "migration_manifest.json"
LEGACY_ROOT_ENV = "SUBTRANSJAV_LEGACY_ROOT"

# 旧根内相对路径白名单（存在才迁；全部缺失不算失败）
_BASE_FILES: tuple[str, ...] = (
    "Temp/translation_memory/tm.db",
    "Temp/translation_memory/glossary_conflict_watch.json",
    "config/api_keys.bin",
    "config/user_settings.json",
    "config/refine_stage_settings.json",
    "config/glossary.csv",
    "config/glossary_learned.csv",
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
    1. 环境变量 ``SUBTRANSJAV_LEGACY_ROOT``（诊断/测试显式指定）；
    2. frozen 形态下 EXE 所在目录（EXE 首发放/升到旧仓库根目录的场景，
       旧 pip/源码数据即在安装目录 = 旧仓库根）。
    """
    env = os.environ.get(LEGACY_ROOT_ENV, "").strip()
    if env:
        return Path(env)
    import sys as _sys
    if getattr(_sys, "frozen", False):
        return Path(_sys.executable).resolve().parent
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
    from subtransjav.refine import secrets as _secrets

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
    from subtransjav.refine.artifact_lock import (
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
    if paths.data_root_source() != "frozen-default":
        return "not-applicable:env-root"

    root = paths.data_root()
    legacy_root = _discover_legacy_root()
    if legacy_root is None:
        return "not-applicable:no-legacy-root"
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

    from subtransjav.refine.artifact_lock import ArtifactLockConflict

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
    """
    try:
        return _ensure_migrated_inner(verbose)
    except Exception as e:  # noqa: BLE001 - 全容错：失败永不阻塞首启
        _log(verbose, f"⚠️ [迁移] 数据迁移异常（程序以新根继续，"
                      f"旧数据可从数据根 backups/ 寻回）: {type(e).__name__}: {e}")
        return "failed:exception"
