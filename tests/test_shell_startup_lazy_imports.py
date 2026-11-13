"""壳层启动导入链回归钉（2026-11-13 启动优化）。

背景：GUI 冷启动链上 `subtrans.refine` 包级导出曾 eager 聚合
tm/glossary/batch，且 process_manager 顶层 import psutil——两者均在
`create_window` 之前白付装载税。本组钉子锁定「子模块导入不连带重模块」，
防止后续重构把惰性化改回去（都是独立子进程断言，避免 pytest 进程缓存污染）。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = REPO_ROOT / "packaging" / "SubTrans.spec"


def _run(code: str) -> str:
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_refine_package_import_stays_light():
    """仅 import 包不应拉起 tm(sqlite3)/glossary/batch/config。"""
    out = _run(
        "import sys\n"
        "import subtrans.refine  # noqa: F401\n"
        "heavy = [m for m in ('subtrans.refine.tm', 'subtrans.refine.batch',"
        " 'subtrans.refine.glossary', 'subtrans.refine.config', 'sqlite3')"
        " if m in sys.modules]\n"
        "print(','.join(heavy))\n"
    )
    assert out == ""


def test_refine_package_exports_still_resolve():
    """PEP 562 惰性导出保持既有 `from subtrans.refine import X` 语义。"""
    out = _run(
        "from subtrans.refine import (DEFAULT_BATCH_CLOUD, RefineConfig,"
        " StageConfig, TranslationMemory, find_srt_files, load_glossary)\n"
        "print(RefineConfig.__name__, StageConfig.__name__,"
        " TranslationMemory.__name__, callable(find_srt_files),"
        " callable(load_glossary), isinstance(DEFAULT_BATCH_CLOUD, int))\n"
    )
    assert out == "RefineConfig StageConfig TranslationMemory True True True"


def test_process_manager_does_not_import_psutil_at_module_level():
    """process_manager 顶层只探 spec 不装载；PSUTIL_AVAILABLE 标志语义不变。"""
    out = _run(
        "import sys\n"
        "import subtrans.utils.process_manager as pm\n"
        "print('psutil_loaded=%s' % ('psutil' in sys.modules))\n"
        "print('available=%s' % (pm.PSUTIL_AVAILABLE is True))\n"
        "mod = pm._ensure_psutil()\n"
        "print('ensure=%s' % (mod is not None and mod.__name__ == 'psutil'))\n"
    )
    assert "psutil_loaded=False" in out
    assert "available=True" in out
    assert "ensure=True" in out


def test_gui_api_import_chain_has_no_heavy_modules():
    """GUI api 导入链不得出现 sqlite3/refine.tm 与重型第三方库。"""
    out = _run(
        "import sys\n"
        "import subtrans.webview_gui.api  # noqa: F401\n"
        "banned = ('subtrans.refine.tm', 'subtrans.refine.batch',"
        " 'subtrans.refine.glossary', 'sqlite3', 'openai', 'httpx',"
        " 'pysubs2', 'sudachipy', 'jieba')\n"
        "print(','.join(m for m in banned if m in sys.modules))\n"
    )
    assert out == ""


def test_spec_pins_lazy_refine_submodules():
    """refine/__init__ 走 __getattr__ 动态 import，spec 必须显式钉子模块。"""
    src = SPEC_PATH.read_text(encoding="utf-8")
    for module in (
        "subtrans.refine.batch",
        "subtrans.refine.config",
        "subtrans.refine.glossary",
        "subtrans.refine.tm",
        "subtrans.refine.asr_meta",
        "subtrans.refine.fs_utils",
    ):
        assert f'"{module}"' in src, f"spec hiddenimports 缺惰性子模块钉: {module}"


def test_spec_no_jieba_hiddenimport_pin():
    """D2026-1113-01：jieba 改安装包可选——spec 不得再钉 jieba（卸离防复发钉）。

    反转 D2026-1004-01 段1①：安装包默认不含 jieba（可选组件，−30MB），
    缺失态由 token_hint/pipeline_v2/cli 三层降级链承接；重钉即回归
    「静默装载 30MB 词典」。打包链不装 [zh] extra（release.yml 同步）。
    """
    src = SPEC_PATH.read_text(encoding="utf-8")
    assert '"jieba"' not in src, "spec 重新钉入 jieba（违反安装包卸离口径）"
