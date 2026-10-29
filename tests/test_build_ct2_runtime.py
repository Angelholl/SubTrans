"""tests for tools/build_ct2_runtime.py（CT2 运行时 zip 构建，d1028-36）。

回归锚（d1028-35 重传勘误）：_pack_zip 返回的 sha256 必须=产物 zip 文件
本体哈希——即 asr_runtime._guarded_download 对下载件核验的口径。
d1028-36 曾把「源文件内容拼接哈希」当 pin 回填（a53da813…），生产下载
核验必失败；本钉保证 pin 口径与校验口径永远同源。
"""

from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import zipfile

_TOOL_PATH = pathlib.Path(__file__).resolve().parents[1] / "tools" / "build_ct2_runtime.py"

_spec = importlib.util.spec_from_file_location("build_ct2_runtime_under_test", _TOOL_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_pack_zip_returns_zip_file_sha256(tmp_path: pathlib.Path) -> None:
    stage = tmp_path / "stage"
    (stage / "sub").mkdir(parents=True)
    (stage / "a.txt").write_bytes(b"alpha")
    (stage / "sub" / "b.bin").write_bytes(bytes(range(256)) * 10)
    out = tmp_path / "out.zip"

    sha, size, count = mod._pack_zip(stage, str(out))

    assert out.is_file()
    assert sha == hashlib.sha256(out.read_bytes()).hexdigest()
    assert size == out.stat().st_size
    assert count == 2


def test_pack_zip_deterministic_and_layout(tmp_path: pathlib.Path) -> None:
    stage = tmp_path / "stage"
    (stage / "sub").mkdir(parents=True)
    (stage / "b.txt").write_bytes(b"beta")
    (stage / "a.txt").write_bytes(b"alpha")
    (stage / "sub" / "c.txt").write_bytes(b"gamma")
    out1 = tmp_path / "out1.zip"
    out2 = tmp_path / "out2.zip"

    sha1, _, _ = mod._pack_zip(stage, str(out1))
    sha2, _, _ = mod._pack_zip(stage, str(out2))

    assert sha1 == sha2  # 确定性打包：同输入同产物哈希
    with zipfile.ZipFile(out1) as z:
        assert z.namelist() == ["a.txt", "b.txt", "sub/c.txt"]
