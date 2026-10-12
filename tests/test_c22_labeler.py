"""tests for tools/c22_labeler.py（C22 听点式标注器，d1012-C22-卡2）。

六钉（卡面「测试钉」；本地回放零第三方依赖，server 用线程+urllib 真请求）：
  1. prepare 解析实测包格式（dict+samples[]，2 run×2 sample → 4 records，
     id/顺序/wav 命名正确；guide/media 缺失 → 中文汇总报错退出码 1）；
  2. 切片参数（-ss clamp≥0、时长 cap 20s、-ac 1 -ar 16000、-ss 前置、
     CREATE_NO_WINDOW/capture_output/timeout）与 ffmpeg 缺失报错路径；
  3. answer 原子落盘（os.replace 后无 .tmp 残留）与 skip→pending 语义；
  4. merge：全决 → 按 (guide,media) 分组出 timings+labels 对齐数组 + 路径绝对；
     有 pending → 退出码 1；
  5. 复标一致率（28 条构 25 同 3 异 → 89.29% <90；26 同 → 92.86% ≥90）
     与争议 id 清单正确；
  6. 服务端仅绑 127.0.0.1（断言 server_address）+ 端口被占 +1 重试。

钉外补测：首页内嵌 HTML 全中文/零外链/按钮 ≥44px/顶部进度常显。
全程离线：ffmpeg 走 subprocess 打桩，不起真实切片；server 只绑回环。

卡3 声源组合勾选（d1012-C22-卡3，听感事实与派生真值分离）六钉：
  c3钉1 派生规则：sounds.speech=true→label yes；仅 moan/prop/bg→no；
  c3钉2 旧记录兼容：label 有值无 sounds（缺键/null 两态）→ 读取不崩、
       UI 状态「旧口径…可重答」、重答新组合覆盖 label 并补 sounds；
  c3钉3 组合表穷举与向量映射：C(4,0)~C(4,4) 每按钮→唯一 sounds 向量，
       含台词组合派生 yes、其余 no（含静音），分组/文案/图例与卡面枚举一致；
  c3钉4 复标一致率按派生值（两轮向量不同但派生相同=一致）；
  c3钉5 merge 声源组合分布（含台词+道具/背景叠加单列小计）与 labels=派生值；
  c3钉6 /api/answer 接收 sounds 且原子落盘（含一致性/键位/skip 校验与复标轮）。
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import threading
import types
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "c22_labeler.py"
_spec = importlib.util.spec_from_file_location("c22_labeler_under_test", _TOOL_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

T_A = "00:00:01,000 --> 00:00:03,000"
T_B = "00:00:04,000 --> 00:00:06,000"
T_C = "00:00:07,000 --> 00:00:09,000"
T_D = "00:01:40,000 --> 00:02:10,000"  # 起=100s 止=130s：-ss 97、时长 cap 20


def _has_chinese(text: str) -> bool:
    return bool(re.search(r"[一-鿿]", text))


def _pkg(tmp_path: Path, name: str = "C22标注包") -> Path:
    pkg = tmp_path / name
    pkg.mkdir(parents=True, exist_ok=True)
    return pkg


def _touch(p: Path, text: str = "{}") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _sample(idx: int, run: int, guide: Path, media: Path, timing: str) -> dict:
    """实测包样本（逐间隙粒度，id 如 run1-29）。"""
    return {"id": f"run{run}-{idx}", "run": f"run{run}", "source": f"第{run}轮.mkv",
            "guide_path": str(guide), "media_path": str(media),
            "timing": timing, "message": f"疑似漏听 {timing}", "label": None}


def _measured_manifest(samples: list[dict]) -> dict:
    """实测 c22_manifest.json：对象 + _说明/generated_at/sample_count/labeled/samples。"""
    return {"_说明": "C22 校准标注包（逐间隙）", "generated_at": "2026-10-12 10:00:00",
            "sample_count": len(samples), "labeled": 0, "samples": samples}


def _stub_ffmpeg(monkeypatch, calls: list | None = None) -> None:
    """ffmpeg 定位给假路径；subprocess.run 打桩（收命令与窗口/捕获/超时实参）。"""

    def fake_run(cmd, **kwargs):
        if calls is not None:
            calls.append((list(cmd), dict(kwargs)))
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(mod, "resolve_ffmpeg", lambda *a, **k: "C:/fake/ffmpeg.exe")
    monkeypatch.setattr(mod.subprocess, "run", fake_run)


def _arg(cmd: list[str], flag: str) -> str:
    return cmd[cmd.index(flag) + 1]


def _write_state(pkg: Path, records: list[dict],
                 relabel_queue: list[str] | None = None) -> Path:
    state = {"records": records, "relabel_queue": relabel_queue or []}
    p = pkg / "state.json"
    p.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def _record(pkg: Path, idx: int, guide: Path, media: Path, timing: str,
            label=None, relabel=None, run: int = 1, sounds=None,
            relabel_sounds=None) -> dict:
    """state 记录。sounds/relabel_sounds 缺省不写键（=卡2 旧口径记录形态）。"""
    rid = f"run{run}-{idx}"
    rec = {"id": rid, "run": f"run{run}",
           "wav": str(pkg / "clips" / f"{rid}.wav"), "media": str(media),
           "guide": str(guide), "timing": timing, "label": label,
           "relabel": relabel}
    if sounds is not None:
        rec["sounds"] = sounds
    if relabel_sounds is not None:
        rec["relabel_sounds"] = relabel_sounds
    return rec


def _spy_replace(monkeypatch) -> list:
    calls: list = []
    real = os.replace

    def spy(src, dst):
        calls.append((str(src), str(dst)))
        return real(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    return calls


# ---------------------------------------------------------- 钉1 prepare 解析实测包

def test_pin1_prepare_parses_measured_package(tmp_path, monkeypatch, capsys):
    pkg = _pkg(tmp_path)
    guides = [_touch(tmp_path / "导读" / f"g{i}.json") for i in (1, 2)]
    medias = [_touch(tmp_path / "媒体" / f"m{i}.mkv") for i in (1, 2)]
    samples = [
        _sample(29, 1, guides[0], medias[0], T_A),
        _sample(30, 1, guides[0], medias[0], T_B),
        _sample(5, 2, guides[1], medias[1], T_C),
        _sample(6, 2, guides[1], medias[1], T_A),
    ]
    _touch(pkg / "c22_manifest.json",
           json.dumps(_measured_manifest(samples), ensure_ascii=False))
    _stub_ffmpeg(monkeypatch)

    rc = mod.main(["--prepare", "--package", str(pkg)])
    assert rc == 0
    out = capsys.readouterr().out
    assert _has_chinese(out) and "4" in out  # 中文摘要含段数

    state = json.loads((pkg / "state.json").read_text(encoding="utf-8"))
    records = state["records"]
    assert [r["id"] for r in records] == [s["id"] for s in samples]  # 保数组序
    assert len(records) == 4
    assert {r["run"] for r in records} == {"run1", "run2"}  # 2 run
    for r, s in zip(records, samples, strict=True):
        assert r["wav"] == str(pkg / "clips" / f"{s['id']}.wav")
        assert Path(r["wav"]).name == f"{s['id']}.wav"
        assert r["timing"] == s["timing"]
        assert r["label"] is None and r["relabel"] is None
    assert not list(pkg.glob("*.tmp"))  # 原子写无临时件残留

    bat = (pkg / "开始标注.bat").read_text(encoding="utf-8")
    assert "--serve" in bat and "--package" in bat and "pause" in bat
    assert ".venv" in bat and "python" in bat  # 绝对路径 venv 解释器
    assert str(pkg) in bat  # 绝对包路径
    # 行尾单一 CRLF（文本模式换行翻译会产出 \r\r\n，cmd 解析有风险）
    raw = (pkg / "开始标注.bat").read_bytes()
    assert b"\r\r\n" not in raw and b"\r\n" in raw


def test_pin1_prepare_missing_paths_aggregated_exit1(tmp_path, monkeypatch, capsys):
    pkg = _pkg(tmp_path)
    guide = _touch(tmp_path / "导读" / "g1.json")
    media = _touch(tmp_path / "媒体" / "m1.mkv")
    bad_guide = tmp_path / "导读" / "丢失导读.json"      # 不存在
    bad_media = tmp_path / "媒体" / "丢失媒体.mkv"        # 不存在
    samples = [
        _sample(1, 1, guide, media, T_A),
        _sample(2, 1, bad_guide, media, T_B),   # 缺 guide
        _sample(3, 1, guide, bad_media, T_C),   # 缺 media
    ]
    _touch(pkg / "c22_manifest.json",
           json.dumps(_measured_manifest(samples), ensure_ascii=False))
    _stub_ffmpeg(monkeypatch)

    rc = mod.main(["--prepare", "--package", str(pkg)])
    assert rc == 1
    out = capsys.readouterr().out
    assert _has_chinese(out) and "❌" in out
    # 汇总报错：两条缺失都要点名（不逐条中断）
    assert "run1-2" in out and "run1-3" in out
    assert "丢失导读" in out and "丢失媒体" in out
    assert not (pkg / "state.json").exists()  # 校验不过不落盘


# ------------------------------------------------------------- 钉2 切片参数

def test_pin2_slice_args_clamp_cap_and_flags(tmp_path, monkeypatch):
    pkg = _pkg(tmp_path)
    guide = _touch(tmp_path / "导读" / "g1.json")
    media = _touch(tmp_path / "媒体" / "m1.mkv")
    samples = [_sample(1, 1, guide, media, T_A),   # 起 1s → -ss clamp 0、-t 6
               _sample(2, 1, guide, media, T_D)]   # 起 100s → -ss 97、-t cap 20
    _touch(pkg / "c22_manifest.json",
           json.dumps(_measured_manifest(samples), ensure_ascii=False))
    calls: list = []
    _stub_ffmpeg(monkeypatch, calls)

    assert mod.main(["--prepare", "--package", str(pkg)]) == 0
    assert len(calls) == 2
    first, kwargs = calls[0]
    second, _ = calls[1]

    # -ss 前置快 seek（在 -i 之前），clamp ≥0
    assert first[0] == "C:/fake/ffmpeg.exe"  # resolve_ffmpeg 定位结果进 cmd[0]
    assert first[1] == "-y" and first[2] == "-ss"
    assert first[3] == "0"
    assert first.index("-ss") < first.index("-i")
    assert float(_arg(first, "-ss")) >= 0
    # 时长：早段 3-1+6 = 8s；长段 min(130-100+6, 20) = 20（cap 生效）
    assert _arg(first, "-t") == "8"
    assert second[second.index("-ss") + 1] == "97"
    dur = float(_arg(second, "-t"))
    assert dur == 20 and dur <= 20
    # 单声道 16k + 指定媒体入参 + 落点 clips/<id>.wav
    assert _arg(first, "-ac") == "1" and _arg(first, "-ar") == "16000"
    assert _arg(first, "-i") == str(media)
    assert first[-1] == str(pkg / "clips" / "run1-1.wav")
    assert first[first.index("-vn") + 1] == "-ac"  # -vn 后接声道/采样率
    # subprocess 实参：CREATE_NO_WINDOW / capture_output / timeout
    assert kwargs["capture_output"] is True
    assert kwargs["creationflags"] == mod.CREATE_NO_WINDOW
    assert isinstance(kwargs["timeout"], int) and kwargs["timeout"] > 0


def test_pin2_ffmpeg_missing_exit1(tmp_path, monkeypatch, capsys):
    pkg = _pkg(tmp_path)
    guide = _touch(tmp_path / "导读" / "g1.json")
    media = _touch(tmp_path / "媒体" / "m1.mkv")
    _touch(pkg / "c22_manifest.json",
           json.dumps(_measured_manifest([_sample(1, 1, guide, media, T_A)]),
                      ensure_ascii=False))
    monkeypatch.setattr(mod, "resolve_ffmpeg", lambda *a, **k: "")  # ffmpeg 缺失

    rc = mod.main(["--prepare", "--package", str(pkg)])
    assert rc == 1
    out = capsys.readouterr().out
    assert _has_chinese(out) and "❌" in out
    assert not (pkg / "state.json").exists()


# ------------------------------------------------------------- 钉3 answer 原子落盘

@pytest.fixture
def live(tmp_path):
    """起真服务（线程 + 真 HTTP 请求），返回 (pkg, base_url)。"""
    pkg = _pkg(tmp_path)
    guide = _touch(tmp_path / "导读" / "g1.json")
    media = _touch(tmp_path / "媒体" / "m1.mkv")
    _write_state(pkg, [_record(pkg, i + 1, guide, media, t)
                       for i, t in enumerate([T_A, T_B, T_C])])
    httpd = mod.create_server(pkg)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield pkg, base
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=10)


def _post(base: str, path: str, payload: dict) -> tuple[int, dict]:
    req = Request(base + path, data=json.dumps(payload).encode("utf-8"),
                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:  # 4xx/5xx 也要拿到中文错误体
        return e.code, json.loads(e.read().decode("utf-8"))


def _get(base: str, path: str):
    with urlopen(base + path, timeout=10) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, body


def test_pin3_answer_atomic_write_no_tmp(live, monkeypatch):
    pkg, base = live
    calls = _spy_replace(monkeypatch)

    status, body = _post(base, "/api/answer",
                         {"id": "run1-1", "round": "first", "value": "yes"})
    assert status == 200 and body.get("ok") is True
    state = json.loads((pkg / "state.json").read_text(encoding="utf-8"))
    assert state["records"][0]["label"] == "yes"
    # 每次点击即原子落盘：os.replace 由 state.json.tmp → state.json，且无残留
    assert (str(pkg / "state.json.tmp"), str(pkg / "state.json")) in calls
    assert not list(pkg.glob("*.tmp"))


def test_pin3_skip_counts_as_pending(live):
    pkg, base = live
    _post(base, "/api/answer", {"id": "run1-1", "round": "first", "value": "yes"})
    _post(base, "/api/answer", {"id": "run1-2", "round": "first", "value": "skip"})
    _post(base, "/api/answer", {"id": "run1-3", "round": "first", "value": "no"})

    state = json.loads((pkg / "state.json").read_text(encoding="utf-8"))
    assert [r["label"] for r in state["records"]] == ["yes", "skip", "no"]
    # skip=稍后再听 → 仍属 pending（待定），不算已决
    assert [r["id"] for r in mod._pending(state)] == ["run1-2"]
    assert mod._pending(state)[0]["label"] == "skip"


def test_pin3_re_round_rejects_skip(live):
    _pkg_dir, base = live
    status, body = _post(base, "/api/answer",
                         {"id": "run1-1", "round": "re", "value": "skip"})
    assert status == 400
    assert _has_chinese(body.get("error", ""))  # 复标轮只认 yes/no，无 skip


# ------------------------------------------------------------- 钉4 merge

def test_pin4_merge_groups_timings_labels_absolute(tmp_path, capsys):
    pkg = _pkg(tmp_path)
    g1 = _touch(tmp_path / "导读" / "g1.json")
    g2 = _touch(tmp_path / "导读" / "g2.json")
    m1 = _touch(tmp_path / "媒体" / "m1.mkv")
    m2 = _touch(tmp_path / "媒体" / "m2.mkv")
    _write_state(pkg, [
        _record(pkg, 1, g1, m1, T_A, label="yes"),
        _record(pkg, 2, g2, m2, T_B, label="no"),
        _record(pkg, 3, g1, m1, T_C, label="no"),
        _record(pkg, 4, g1, m1, T_A, label="yes"),
    ])

    rc = mod.main(["--merge", "--package", str(pkg)])
    assert rc == 0
    out = capsys.readouterr().out
    assert _has_chinese(out)

    manifest = json.loads(
        (pkg / "c22_manifest_labeled.json").read_text(encoding="utf-8"))
    assert isinstance(manifest, list) and len(manifest) == 2  # 按 (guide,media) 分组
    g = manifest[0]
    assert g["guide"] == str(g1) and g["media"] == str(m1)
    # 保 sample 原序：run1-1 / run1-3 / run1-4
    assert g["timings"] == [T_A, T_C, T_A]
    assert g["labels"] == [True, False, True]      # 对齐 bool 数组（卡1 口径）
    assert manifest[1]["guide"] == str(g2) and manifest[1]["media"] == str(m2)
    assert manifest[1]["timings"] == [T_B] and manifest[1]["labels"] == [False]
    for entry in manifest:                          # 路径绝对
        assert Path(entry["guide"]).is_absolute()
        assert Path(entry["media"]).is_absolute()

    bat = (pkg / "一键回放.bat").read_text(encoding="utf-8")
    assert "c22_calibration.py" in bat and "--enable" in bat
    assert "c22_manifest_labeled.json" in bat and "pause" in bat
    assert ".venv" in bat
    raw = (pkg / "一键回放.bat").read_bytes()
    assert b"\r\r\n" not in raw and b"\r\n" in raw  # 行尾单一 CRLF


def test_pin4_merge_pending_exit1(tmp_path, capsys):
    pkg = _pkg(tmp_path)
    g1 = _touch(tmp_path / "导读" / "g1.json")
    m1 = _touch(tmp_path / "媒体" / "m1.mkv")
    _write_state(pkg, [
        _record(pkg, 1, g1, m1, T_A, label="yes"),
        _record(pkg, 2, g1, m1, T_B, label=None),   # 未作答
        _record(pkg, 3, g1, m1, T_C, label="skip"),  # 稍后再听=pending
    ])

    rc = mod.main(["--merge", "--package", str(pkg)])
    assert rc == 1
    out = capsys.readouterr().out
    assert _has_chinese(out) and "❌" in out
    assert "2" in out  # pending 计数
    assert not (pkg / "c22_manifest_labeled.json").exists()


# ------------------------------------------------------------- 钉5 复标一致率

def _agreement_state(pkg: Path, n: int, disagree: int) -> dict:
    """28 条已决 + 复标答案：前 disagree 条判不一致。"""
    guide = _touch(pkg.parent / "导读" / "g1.json")
    media = _touch(pkg.parent / "媒体" / "m1.mkv")
    records = []
    for i in range(n):
        label = "yes" if i % 2 == 0 else "no"
        relabel = label if i >= disagree else ("no" if label == "yes" else "yes")
        records.append(_record(pkg, i + 1, guide, media, T_A,
                               label=label, relabel=relabel))
    return {"records": records, "relabel_queue": [r["id"] for r in records]}


def test_pin5_agreement_below_90_with_disputed_list(tmp_path):
    pkg = _pkg(tmp_path)
    _write_state(pkg, _agreement_state(pkg, 28, 3)["records"],
                 _agreement_state(pkg, 28, 3)["relabel_queue"])
    state = json.loads((pkg / "state.json").read_text(encoding="utf-8"))

    result = mod._agreement(state)
    assert result["total"] == 28 and result["agree"] == 25
    assert result["pct"] == 89.29 and result["pct"] < 90
    assert result["disputed"] == ["run1-1", "run1-2", "run1-3"]


def test_pin5_agreement_at_least_90(tmp_path):
    pkg = _pkg(tmp_path)
    data = _agreement_state(pkg, 28, 2)
    _write_state(pkg, data["records"], data["relabel_queue"])
    state = json.loads((pkg / "state.json").read_text(encoding="utf-8"))

    result = mod._agreement(state)
    assert result["total"] == 28 and result["agree"] == 26
    assert result["pct"] == 92.86 and result["pct"] >= 90
    assert result["disputed"] == ["run1-1", "run1-2"]


def test_pin5_agreement_route_over_http(tmp_path):
    """GET /api/agreement 真请求一轮：只认复标轮 yes/no。"""
    pkg = _pkg(tmp_path)
    data = _agreement_state(pkg, 28, 3)
    _write_state(pkg, data["records"], data["relabel_queue"])
    httpd = mod.create_server(pkg)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        status, body = _get(base, "/api/agreement")
        assert status == 200
        result = json.loads(body)
        assert result["total"] == 28 and result["agree"] == 25
        assert result["pct"] == 89.29
        assert len(result["disputed"]) == 3
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=10)


def test_pin5_relabel_start_samples_ceil_20_percent(live):
    pkg, base = live  # 3 条已决中的 0 条 → 先作答 2 条
    _post(base, "/api/answer", {"id": "run1-1", "round": "first", "value": "yes"})
    _post(base, "/api/answer", {"id": "run1-2", "round": "first", "value": "no"})

    status, body = _post(base, "/api/relabel/start", {})
    assert status == 200
    # ceil(2 × 20%) = 1 条，且只从首轮已决条目抽
    assert len(body["queue"]) == 1
    assert body["queue"][0] in ("run1-1", "run1-2")
    state = json.loads((pkg / "state.json").read_text(encoding="utf-8"))
    assert state["relabel_queue"] == body["queue"]


# ------------------------------------------------------------- 钉6 只绑回环

def test_pin6_server_binds_loopback_only(tmp_path):
    pkg = _pkg(tmp_path)
    httpd = mod.create_server(pkg)
    try:
        assert httpd.server_address[0] == "127.0.0.1"
        assert 8765 <= httpd.server_address[1] <= 8774  # 8765 被占 +1 至 8774
    finally:
        httpd.server_close()


def test_pin6_port_occupied_retries_next(tmp_path, monkeypatch):
    pkg = _pkg(tmp_path)
    tried: list[int] = []
    real = mod.ThreadingHTTPServer

    def fake(addr, handler):
        tried.append(addr[1])
        if len(tried) == 1:
            raise OSError("端口被占")
        return real(addr, handler)

    monkeypatch.setattr(mod, "ThreadingHTTPServer", fake)
    httpd = mod.create_server(pkg)
    try:
        assert tried[:2] == [8765, 8766]  # 被占 +1 重试
        assert httpd.server_address[1] >= 8766
        assert httpd.server_address[0] == "127.0.0.1"
    finally:
        httpd.server_close()


# ----------------------------------------------------- 钉外：首页内嵌 HTML

def test_serve_homepage_chinese_no_external(live):
    pkg, base = live  # 包目录本钉只用 base（pkg 由夹具持有）
    status, html = _get(base, "/")
    assert status == 200
    # 全中文、顶部常显进度、按钮高 ≥44px、大字号
    assert _has_chinese(html)
    assert "已标" in html and "待定" in html and "条" in html
    assert "min-height:44px" in html.replace(" ", "")
    assert "font-size" in html
    # 零外部资源（零外发零遥测）
    assert "http://" not in html and "https://" not in html
    assert "<script src" not in html and "<link " not in html


def test_serve_clips_route_serves_wav(live, tmp_path):
    pkg, base = live
    clip = pkg / "clips" / "run1-1.wav"
    clip.parent.mkdir(parents=True, exist_ok=True)
    clip.write_bytes(b"RIFF0000WAVE")
    with urlopen(base + "/clips/run1-1.wav", timeout=10) as resp:
        assert resp.status == 200
        assert resp.read() == b"RIFF0000WAVE"


# ==================== 卡3：声源组合勾选（C(4,0)~C(4,4) 穷举）六钉 ====================
# 卡面标题写「17 态」，但其枚举 = 无声源1 + C(4,1)4 + C(4,2)6 + C(4,3)4 + C(4,4)1 = 16，
# 且钉3 要求「每按钮→唯一 sounds 向量」（4 位向量空间恰 16 个，17 钮无法双射）——
# 按 16 组合钮执行（作答区按钮 17 = 16 组合 + 「稍后再听」次按钮），矛盾登记于卡面执行记录。

_SND = ("speech", "moan", "prop", "bg")


def _sounds(**flags: bool) -> dict:
    """4 布尔声源向量（未点名的声源取 False）：_sounds(speech=True, prop=True)。"""
    return {k: bool(flags.get(k, False)) for k in _SND}


# ------------------------------------------------------------- c3钉1 派生规则

def test_c3_pin1_derive_rule_from_sounds():
    """钉1 派生规则：sounds.speech=true→label yes；仅 moan/prop/bg→no。"""
    assert mod._derive_label(_sounds(speech=True)) == "yes"
    assert mod._derive_label(_sounds(speech=True, moan=True, prop=True, bg=True)) == "yes"
    for only in ("moan", "prop", "bg"):
        assert mod._derive_label(_sounds(**{only: True})) == "no"
    assert mod._derive_label(_sounds()) == "no"      # 静音=无对话
    assert mod._derive_label(None) is None           # 缺 sounds → 不派生
    assert mod._derive_label("非对象") is None
    # 记录级：有 sounds 以 sounds 为准（可覆盖矛盾的存量 label），无 sounds 退回存量
    assert mod._record_label({"sounds": _sounds(speech=True), "label": "no"}) == "yes"
    assert mod._record_label({"sounds": _sounds(prop=True), "label": "yes"}) == "no"
    assert mod._record_label({"label": "yes"}) == "yes"
    assert mod._record_label({"label": None}) is None
    # 复标轮同口径：relabel_sounds → relabel
    assert mod._record_label({"relabel_sounds": _sounds(moan=True),
                              "relabel": "yes"}, re_round=True) == "no"
    assert mod._record_label({"relabel": "no"}, re_round=True) == "no"
    assert mod._record_label({}, re_round=True) is None


# --------------------------------------------------- c3钉2 旧记录兼容（零迁移）

def test_c3_pin2_legacy_record_compat_zero_migration(tmp_path):
    """钉2 旧记录（有 label 无 sounds）→ 读取不崩、UI「旧口径」、重答覆盖。"""
    pkg = _pkg(tmp_path)
    guide = _touch(tmp_path / "导读" / "g1.json")
    media = _touch(tmp_path / "媒体" / "m1.mkv")
    no_key = _record(pkg, 1, guide, media, T_A, label="no")      # 卡2 旧态：整键缺失
    null_key = _record(pkg, 2, guide, media, T_B, label="yes")   # 卡3 新态：显式 null
    null_key["sounds"] = None
    undecided = _record(pkg, 3, guide, media, T_C, label=None)
    _write_state(pkg, [no_key, null_key, undecided])

    # ① 零迁移读取：缺键 / 为 null 都不崩不丢，已决语义保持
    state = mod._read_state(pkg)
    assert state is not None and len(state["records"]) == 3
    assert [mod._record_label(r) for r in state["records"]] == ["no", "yes", None]
    # 两条已决旧记录不算待定；未作答那条仍是 pending
    assert [r["id"] for r in mod._pending(state)] == ["run1-3"]

    httpd = mod.create_server(pkg)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        status, raw = _get(base, "/api/state")
        assert status == 200
        api_records = json.loads(raw)["records"]
        assert "sounds" not in api_records[0]          # 旧态整键缺失原样透出
        assert api_records[1]["sounds"] is None         # null 不被吞
        # ② UI 状态：「旧口径已标…（可重答）」文案在内嵌页面
        status, html = _get(base, "/")
        assert status == 200
        assert "旧口径已标：有对话（可重答）" in html
        assert "旧口径已标：无对话（可重答）" in html
        # ③ 重答新组合 → 覆盖 label 并补 sounds（原子落盘）
        status, body = _post(base, "/api/answer",
                             {"id": "run1-1", "round": "first", "value": "no",
                              "sounds": _sounds(prop=True, bg=True)})
        assert status == 200 and body.get("ok") is True
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=10)

    state = json.loads((pkg / "state.json").read_text(encoding="utf-8"))
    rec = state["records"][0]
    assert rec["label"] == "no" and rec["sounds"] == _sounds(prop=True, bg=True)
    assert not list(pkg.glob("*.tmp"))


# -------------------------------------------- c3钉3 组合表穷举与向量一一映射

def test_c3_pin3_combo_table_exhaustive_unique_mapping():
    """钉3 C(4,0)~C(4,4) 每按钮→唯一 sounds 向量；含台词派生 yes、其余 no。"""
    table = mod._combo_table()
    # 1+4+6+4+1 = 16 态，与 4 位向量空间一一双射（卡面「17」笔误见本节头注）
    assert len(table) == 16
    vecs = [tuple(c["sounds"][k] for k in _SND) for c in table]
    assert len(set(vecs)) == 16
    assert set(vecs) == {tuple(bool(mask >> i & 1) for i in range(4)) for mask in range(16)}
    # 分组序（按声源数）与卡面枚举文案逐条对齐
    assert [c["n"] for c in table] == [0] + [1] * 4 + [2] * 6 + [3] * 4 + [4]
    by_n = {n: [c["text"] for c in table if c["n"] == n] for n in range(5)}
    assert by_n[0] == ["🔇 静音"]
    assert by_n[1] == ["台词", "呻吟喘息", "道具声", "背景声"]
    assert by_n[2] == ["台词+呻吟", "台词+道具", "台词+背景",
                       "呻吟+道具", "呻吟+背景", "道具+背景"]
    assert by_n[3] == ["台词+呻吟+道具", "台词+呻吟+背景",
                       "台词+道具+背景", "呻吟+道具+背景"]
    assert by_n[4] == ["台词+呻吟+道具+背景"]
    # 含台词→yes、其余 no（含静音）；表内 derived 与派生函数、向量命名同源
    for c in table:
        expect = "yes" if c["sounds"]["speech"] else "no"
        assert c["derived"] == expect
        assert mod._derive_label(c["sounds"]) == expect
        assert mod._combo_name(c["sounds"]) == c["text"]
    # 内嵌页面吃同一张表（前端/服务端同源）+ 分组图例 + 页首名词解释 + 次按钮
    page = mod._PAGE
    assert page.count('"text":') == 16
    for c in table:
        assert c["text"] in page
    assert "含台词=有对话" in page
    assert all(f"C(4,{n})" in page for n in range(1, 5))
    for term in ("台词（含小声/气声台词）", "呻吟喘息（非言语人声）",
                 "道具声（衣物门脚步等）", "背景声（音乐·环境音）"):
        assert term in page
    assert "稍后再听" in page


# --------------------------------------------------- c3钉4 复标一致率按派生值

def test_c3_pin4_agreement_counts_derived_label(tmp_path):
    """钉4 两轮 sounds 不同但派生相同=一致；派生不同=争议（不依赖 label 缓存列）。"""
    pkg = _pkg(tmp_path)
    guide = _touch(tmp_path / "导读" / "g1.json")
    media = _touch(tmp_path / "媒体" / "m1.mkv")
    records = [
        # 向量不同（speech+prop vs speech+bg）但都含台词 → 派生同=一致；
        # label/relabel 缓存列为 null（只落向量）——一致率必须按派生值，不读缓存列
        _record(pkg, 1, guide, media, T_A, label=None,
                sounds=_sounds(speech=True, prop=True),
                relabel=None, relabel_sounds=_sounds(speech=True, bg=True)),
        # 首轮含台词、复标只有道具声 → 派生不同=争议
        _record(pkg, 2, guide, media, T_B, label="yes", sounds=_sounds(speech=True),
                relabel="no", relabel_sounds=_sounds(prop=True)),
        # 旧口径首轮（无 sounds，存量 label）+ 复标向量含台词 → 派生同=一致
        _record(pkg, 3, guide, media, T_C, label="yes",
                relabel="yes", relabel_sounds=_sounds(speech=True, moan=True)),
    ]
    _write_state(pkg, records, [r["id"] for r in records])
    state = json.loads((pkg / "state.json").read_text(encoding="utf-8"))

    result = mod._agreement(state)
    assert result["total"] == 3 and result["agree"] == 2
    assert result["pct"] == 66.67
    assert result["disputed"] == ["run1-2"]


# ------------------------------------------------ c3钉5 merge 分布统计与派生值

def test_c3_pin5_merge_distribution_and_derived_labels(tmp_path, capsys):
    """钉5 merge 输出声源组合分布（叠加小计单列），labels 数组=派生值。"""
    pkg = _pkg(tmp_path)
    guide = _touch(tmp_path / "导读" / "g1.json")
    media = _touch(tmp_path / "媒体" / "m1.mkv")
    _write_state(pkg, [
        _record(pkg, 1, guide, media, T_A, label="yes", sounds=_sounds(speech=True)),
        _record(pkg, 2, guide, media, T_B, label="yes",
                sounds=_sounds(speech=True, prop=True)),
        _record(pkg, 3, guide, media, T_C, label="yes", sounds=_sounds(speech=True, bg=True)),
        _record(pkg, 4, guide, media, T_A, label="yes",
                sounds=_sounds(speech=True, prop=True, bg=True)),
        # 存量 label 与 sounds 矛盾 → 以 sounds 派生为准（no）
        _record(pkg, 5, guide, media, T_B, label="yes", sounds=_sounds(prop=True)),
        _record(pkg, 6, guide, media, T_C, label="no"),   # 旧口径未记声源
    ])

    rc = mod.main(["--merge", "--package", str(pkg)])
    assert rc == 0
    out = capsys.readouterr().out
    assert _has_chinese(out)

    manifest = json.loads(
        (pkg / "c22_manifest_labeled.json").read_text(encoding="utf-8"))
    # labels 数组 = 派生值（bool，harness 零改动）
    assert manifest[0]["labels"] == [True, True, True, True, False, False]

    # 分布统计：16 组合各自计数 + 「台词+道具/背景叠加」小计单列 + 旧口径单列
    assert "声源组合分布" in out
    assert "静音=0" in out and "台词=1" in out and "道具声=1" in out
    assert "台词+道具=1" in out and "台词+背景=1" in out
    assert "台词+道具+背景=1" in out and "台词+呻吟+道具+背景=0" in out
    assert "「台词+道具/背景叠加」小计：3 条" in out
    assert "旧口径未记声源：1 条" in out
    assert "c22_manifest_labeled.json" in out


# -------------------------------------------- c3钉6 /api/answer 收 sounds 原子落盘

def test_c3_pin6_answer_accepts_sounds_atomic(live, monkeypatch):
    """钉6 sounds 随点击原子落盘；只给 sounds 时由服务端派生 label。"""
    pkg, base = live
    calls = _spy_replace(monkeypatch)

    status, body = _post(base, "/api/answer",
                         {"id": "run1-1", "round": "first", "value": "yes",
                          "sounds": _sounds(speech=True, prop=True)})
    assert status == 200 and body.get("ok") is True
    state = json.loads((pkg / "state.json").read_text(encoding="utf-8"))
    rec = state["records"][0]
    assert rec["label"] == "yes"
    assert rec["sounds"] == _sounds(speech=True, prop=True)
    assert (str(pkg / "state.json.tmp"), str(pkg / "state.json")) in calls
    assert not list(pkg.glob("*.tmp"))

    # 只给 sounds 不给 value → 按派生 label 落盘
    status, body = _post(base, "/api/answer",
                         {"id": "run1-2", "round": "first", "sounds": _sounds(moan=True)})
    assert status == 200 and body.get("ok") is True
    state = json.loads((pkg / "state.json").read_text(encoding="utf-8"))
    assert state["records"][1]["label"] == "no"
    assert state["records"][1]["sounds"] == _sounds(moan=True)


def test_c3_pin6_answer_sounds_validation(live):
    """sounds 校验：派生不一致/缺键/未知键/非布尔/skip 一律 400 中文且不落盘。"""
    _pkg_dir, base = live

    def ans(payload):
        return _post(base, "/api/answer", payload)

    status, body = ans({"id": "run1-1", "round": "first", "value": "yes",
                        "sounds": _sounds(prop=True)})
    assert status == 400 and _has_chinese(body.get("error", ""))
    status, body = ans({"id": "run1-1", "round": "first", "value": "no",
                        "sounds": {"speech": False}})          # 缺 3 键
    assert status == 400 and _has_chinese(body.get("error", ""))
    status, body = ans({"id": "run1-1", "round": "first", "value": "no",
                        "sounds": {**_sounds(), "voice": False}})  # 未知键
    assert status == 400 and "voice" in body.get("error", "")
    status, body = ans({"id": "run1-1", "round": "first", "value": "no",
                        "sounds": {**_sounds(), "bg": 1}})      # 非布尔
    assert status == 400 and _has_chinese(body.get("error", ""))
    status, body = ans({"id": "run1-1", "round": "first", "value": "skip",
                        "sounds": _sounds()})                   # skip 不记声源
    assert status == 400 and _has_chinese(body.get("error", ""))
    # 400 全程未落盘
    state = json.loads((_pkg_dir / "state.json").read_text(encoding="utf-8"))
    assert all(r.get("sounds") is None for r in state["records"])


def test_c3_pin6_re_round_sounds_and_sync_label(live):
    """钉6 复标轮写 relabel_sounds（派生 relabel），sync_label 一并覆盖首轮。"""
    pkg, base = live
    _post(base, "/api/answer", {"id": "run1-1", "round": "first", "value": "yes",
                                "sounds": _sounds(speech=True)})
    status, body = _post(base, "/api/relabel/start", {})
    assert status == 200
    rid = body["queue"][0]
    status, body = _post(base, "/api/answer",
                         {"id": rid, "round": "re", "value": "no",
                          "sounds": _sounds(bg=True), "sync_label": True})
    assert status == 200 and body.get("ok") is True

    state = json.loads((pkg / "state.json").read_text(encoding="utf-8"))
    rec = next(r for r in state["records"] if r["id"] == rid)
    assert rec["relabel"] == "no" and rec["relabel_sounds"] == _sounds(bg=True)
    assert rec["label"] == "no" and rec["sounds"] == _sounds(bg=True)  # 首轮同步覆盖
    assert mod._record_label(rec) == "no"
    assert mod._record_label(rec, re_round=True) == "no"
    assert mod._agreement(state)["disputed"] == []   # 派生一致 → 无争议
