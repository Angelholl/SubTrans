#!/usr/bin/env python3
"""C22 听点式标注器（本地网页：一边听一边勾；d1012-C22-卡2）。

用法：
  python tools/c22_labeler.py --prepare --package <标注包目录>
  python tools/c22_labeler.py --serve    --package <标注包目录>
  python tools/c22_labeler.py --merge    --package <标注包目录>

- --prepare：读 <dir>/c22_manifest.json（实测格式：对象含
  _说明/generated_at/sample_count/labeled/samples[]，samples 每条 =
  {id, run, source, guide_path, media_path, timing, message, label:null}，
  逐间隙粒度如 id="run1-29"）。逐条在位校验 guide/media 存在（缺失汇总中文
  报错退出码 1）→ ffmpeg 切片（resolve_ffmpeg 定位；-ss 前置快 seek，
  起-3 clamp≥0、时长 min(止-起+6, 30)；CREATE_NO_WINDOW + capture_output
  + timeout）→ 原子写 state.json（records=[{id, run, wav, media, guide,
  timing, message, seek_in, label:null, relabel:null, sounds:null,
  relabel_sounds:null}]）→ 写 开始标注.bat → 打印中文摘要。
  **幂等保标注（卡4 硬约束）**：state.json 已存在时，新 records 按 id 继承旧
  记录的 label/sounds/relabel/relabel_sounds（id 匹配即继承，旧记录缺字段
  不崩，manifest 外旧条目不复活），已标注计数按合并后 records 重算并打印
  「已保留 N 条既有标注」；clips 重切覆盖（文件名=id 稳定）。message 为粗筛
  提示透传（缺省 null），serve 页 meta 第二行显示；seek_in=播放起点（timing
  起<3s 起点被 clamp→0.0 从头播，否则 3.0 跳过前缓冲直达间隙本体）。
- --serve：http.server 只绑 127.0.0.1，端口 8765 被占则 +1 重试至 8774，
  启动后自动开页。路由：GET /（内嵌单页 HTML，全中文零外链）、
  GET /api/state、GET /clips/<id>.wav、POST /api/answer（每次点击原子落盘，
  断电不丢；收 sounds 声源向量时按向量派生 label）、POST /api/relabel/start
  （首轮已决条目随机抽 ceil(20%) 进复标）、GET /api/agreement（复标轮只认
  派生 yes/no，无 skip）；
- --merge：首轮有 pending（null 或 skip）→ 中文报错退出码 1 并报计数；
  否则按 (guide, media) 分组保原序写 c22_manifest_labeled.json（harness
  数组格式，每组 {guide, media, timings[], labels[]}——走 C22-卡1 的
  timings+labels 显式对齐口径，labels=bool 且恒为**派生值**）+ 一键回放.bat
  （未达标时 harness 自拒写门控，fail-closed 安全），并打印声源组合分布
  （C22-卡3 观察数据，非校准指标）。

声源组合（C22-卡3：听感事实与派生真值分离）：网页点选 16 个声源组合按钮
（卡面标称 17，其枚举与「每按钮→唯一向量」均为 C(4,0)~C(4,4)=16 态），
records[].sounds={speech,moan,prop,bg} 四布尔向量；label 保留并由 sounds
派生（speech=true→"yes" 否则"no"），无 sounds 的旧记录退回存量 label
（读取零迁移，不崩不丢）；复标一致率与 merge 的 labels 一律按派生值计。

全程本地回环零外发零遥测；state.json 与 merge 产物一律原子写
（临时件 + os.replace）；仅 Python 标准库 + 复用 resolve_ffmpeg。
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from subtransjav.refine.asr_env import resolve_ffmpeg  # noqa: E402
from subtransjav.utils.subprocess_flags import CREATE_NO_WINDOW  # noqa: E402

_PORT_START = 8765
_PORT_END = 8774
_PAD_BEFORE_S = 3          # 切片前置留白（起-3，clamp≥0）
_PAD_TOTAL_S = 6           # 切片总留白（止-起+6）
_CLIP_CAP_S = 30           # 单片段时长上限（秒；卡4 20→30，30s≈940KB 16k 单声道）
_SEEK_IN_S = 3.0           # 播放起点=间隙本体：起点未 clamp 时跳过前 3s 缓冲
_FFMPEG_TIMEOUT_S = 120    # 单次切片超时兜底
_ATOMIC_RETRY = 5          # 原子写 Windows 瞬时占用重试次数
_ATOMIC_RETRY_DELAY_S = 0.05
_RELABEL_DIV = 5           # 复标抽样 = ceil(20%) = ceil(n/5)
_STATE_NAME = "state.json"
_FIRST = "first"
_RE = "re"
_DECIDED = ("yes", "no")
_ALL_VALUES = ("yes", "no", "skip")
# 幂等保标注（卡4）：重跑 --prepare 时按 id 从旧 state 继承的标注字段
_KEEP_FIELDS = ("label", "sounds", "relabel", "relabel_sounds")

# 声源向量四键（C22-卡3）：(单源全名, 组合短名)
_SOUNDS = ("speech", "moan", "prop", "bg")
_SOUND_CN = {
    "speech": ("台词", "台词"),
    "moan": ("呻吟喘息", "呻吟"),
    "prop": ("道具声", "道具"),
    "bg": ("背景声", "背景"),
}
_GROUP_NAMES = {0: "无声源", 1: "单声源 C(4,1)", 2: "双声源 C(4,2)",
                3: "三声源 C(4,3)", 4: "四声源 C(4,4)"}
_GLOSSARY = ("名词解释：台词（含小声/气声台词）/呻吟喘息（非言语人声）/"
             "道具声（衣物门脚步等）/背景声（音乐·环境音）")
_OVERLAY_CN = "「台词+道具/背景叠加」"   # 台词叠加道具声或背景声的组合小计
# 缓冲说明（卡4）：切片首尾各约 3s 是缓冲上下文，只判间隙本体（作答区提示行前一行）
_BUFFER_HINT = ("片段首尾各约 3 秒为缓冲上下文：只判间隙本体内是否有台词；"
                "边缘与既有字幕对齐的台词不算漏听")

_TIMING_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*"
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")


# ---------------------------------------------------------------- 基础工具

def _atomic_write_text(path: Path, text: str) -> None:
    """临时件 + os.replace 原子落盘（断电不留半截文件）。

    走 write_bytes：文本模式的换行翻译会把 bat 的 \\r\\n 变成 \\r\\r\\n
    （cmd 解析风险），此处由调用方显式控制行尾。

    Windows 下新建/替换瞬间可能被 Defender 等短暂占用（WinError 5），
    有界重试兜底（每次点击即落盘语义不变：重试间隔毫秒级，仍失败才
    如实抛出由调用方报错）。"""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    for attempt in range(_ATOMIC_RETRY):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt + 1 >= _ATOMIC_RETRY:
                raise
            time.sleep(_ATOMIC_RETRY_DELAY_S)


def _atomic_write_json(path: Path, data) -> None:
    _atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=1))


def _read_state(package: Path) -> dict | None:
    try:
        data = json.loads((package / _STATE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _merge_annotations(records: list[dict], prev: dict | None) -> int:
    """幂等保标注（卡4 硬约束）：新 records 按 id 继承旧 state 记录的标注字段
    （label/sounds/relabel/relabel_sounds——id 匹配即继承，旧记录缺字段不崩，
    manifest 外旧条目自然不复活）；返回已保留既有标注的条数（四字段任一非
    null 计 1，供摘要「已保留 N 条既有标注」与已标注重算使用）。"""
    prev_by_id = ({str(r.get("id")): r for r in (prev.get("records") or [])
                   if isinstance(r, dict)} if isinstance(prev, dict) else {})
    kept = 0
    for rec in records:
        old = prev_by_id.get(str(rec.get("id")))
        if isinstance(old, dict):
            for field in _KEEP_FIELDS:
                if field in old:
                    rec[field] = old[field]
        if any(rec.get(f) is not None for f in _KEEP_FIELDS):
            kept += 1
    return kept


# ------------------------------------------------ 声源组合与派生（卡3）

def _derive_label(sounds) -> str | None:
    """sounds 向量 → 派生 label：speech=true→"yes"，否则"no"；非对象→None。"""
    if not isinstance(sounds, dict):
        return None
    return "yes" if sounds.get("speech") else "no"


def _record_label(record: dict, *, re_round: bool = False) -> str | None:
    """记录的派生 label：有 sounds 按 sounds 派生（权威），无 sounds（旧口径）
    退回存量 label/relabel 列——state.json 读取零迁移，缺 sounds 视为 null。"""
    vector = record.get("relabel_sounds") if re_round else record.get("sounds")
    derived = _derive_label(vector)
    if derived is not None:
        return derived
    return record.get("relabel" if re_round else "label")


def _combo_table() -> list[dict]:
    """C(4,0)~C(4,4) 声源组合表：16 项（卡面标称 17 态，但其枚举
    1+4+6+4+1=16 且钉3 要求「每按钮→唯一 sounds 向量」，4 位向量空间恰 16 个），
    按声源数分组、组内按卡面枚举序（台词>呻吟>道具>背景 逐位命中优先）；
    每项 {n, text, sounds, derived}，sounds 向量与按钮一一双射。"""
    items: list[tuple[int, tuple[int, ...], dict]] = []
    for mask in range(16):
        sounds = {k: bool(mask >> i & 1) for i, k in enumerate(_SOUNDS)}
        picked = [k for k in _SOUNDS if sounds[k]]
        if not picked:
            text = "🔇 静音"
        elif len(picked) == 1:
            text = _SOUND_CN[picked[0]][0]
        else:
            text = "+".join(_SOUND_CN[k][1] for k in picked)
        order = tuple(0 if sounds[k] else 1 for k in _SOUNDS)
        entry = {"n": len(picked), "text": text, "sounds": sounds,
                 "derived": "yes" if sounds["speech"] else "no"}
        items.append((len(picked), order, entry))
    items.sort(key=lambda t: (t[0], t[1]))
    return [t[2] for t in items]


_COMBOS: list[dict] = _combo_table()   # 模块级定表：网页内嵌与 merge 分布同源


def _combo_name(sounds) -> str:
    """sounds 向量 → 组合文案（查定表；非法向量回退「未知组合」）。"""
    if isinstance(sounds, dict):
        for c in _COMBOS:
            if all(bool(sounds.get(k)) == c["sounds"][k] for k in _SOUNDS):
                return c["text"]
    return "未知组合"


def _validate_sounds(raw) -> tuple[dict | None, str | None]:
    """校验 /api/answer 的 sounds：必须是四键齐全且全为布尔的对象。
    返回 (归一化向量, None) 或 (None, 中文错误)。"""
    if not isinstance(raw, dict):
        return None, "sounds 须为 JSON 对象（speech/moan/prop/bg 四键布尔）"
    unknown = sorted(str(k) for k in raw if k not in _SOUNDS)
    if unknown:
        return None, f"sounds 含未知声源键：{'、'.join(unknown)}（只允许 speech/moan/prop/bg）"
    missing = [k for k in _SOUNDS if k not in raw]
    if missing:
        return None, f"sounds 缺声源键：{'、'.join(missing)}（四键须齐全）"
    bad = [k for k in _SOUNDS if not isinstance(raw[k], bool)]
    if bad:
        return None, f"sounds.{bad[0]} 须为布尔值 true/false"
    return {k: raw[k] for k in _SOUNDS}, None


def _sound_distribution(records: list[dict]) -> dict:
    """声源组合分布（卡3 观察数据，非校准指标）：16 组合各自计数 +
    「台词+道具/背景叠加」小计 + 旧口径未记声源计数。"""
    counts = {c["text"]: 0 for c in _COMBOS}
    overlay = 0
    legacy = 0
    for r in records:
        sounds = r.get("sounds")
        if not isinstance(sounds, dict):
            legacy += 1
            continue
        name = _combo_name(sounds)
        counts[name] = counts.get(name, 0) + 1
        if sounds.get("speech") and (sounds.get("prop") or sounds.get("bg")):
            overlay += 1
    return {"counts": counts, "overlay": overlay, "legacy": legacy}


def _pending(state: dict) -> list[dict]:
    """首轮待定条目：派生 label 为 null 或 skip（skip=稍后再听，不算已决）。"""
    return [r for r in (state.get("records") or [])
            if _record_label(r) not in _DECIDED]


def _ceil_20_percent(n: int) -> int:
    """ceil(n × 20%)，整数运算避开浮点误差。"""
    return -(-n // _RELABEL_DIV)


def _agreement(state: dict) -> dict:
    """复标一致率：按**派生 label** 计（两轮 sounds 派生相同=一致，sounds 优先、
    无向量退回存量列）；只认复标轮已决（无 skip），争议=派生判罚不一致。"""
    answered = [r for r in (state.get("records") or [])
                if _record_label(r, re_round=True) in _DECIDED]
    total = len(answered)
    agree = sum(1 for r in answered
                if _record_label(r) == _record_label(r, re_round=True))
    pct = round(agree * 100.0 / total, 2) if total else 0.0
    disputed = [str(r.get("id")) for r in answered
                if _record_label(r) != _record_label(r, re_round=True)]
    return {"total": total, "agree": agree, "pct": pct, "disputed": disputed}


def _parse_timing(timing: str) -> tuple[float, float] | None:
    """SRT 区间 → (起, 止) 秒；解析失败或止≤起 → None。"""
    m = _TIMING_RE.search(timing or "")
    if not m:
        return None

    def sec(h: str, mi: str, s: str, ms: str) -> float:
        return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0

    g = m.groups()
    start = sec(*g[:4])
    end = sec(*g[4:])
    return (start, end) if end > start else None


def _fmt_seconds(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.3f}"


def _seek_in(start: float) -> float:
    """播放起点（卡4）：timing 起≥前置留白 → 片段头部有完整 3s 缓冲，跳 3.0
    直达间隙本体；起<3s 时起点被 clamp（缓冲不完整）→ 0.0 从片段头播。"""
    return 0.0 if start < _PAD_BEFORE_S else _SEEK_IN_S


def _run_ffmpeg(cmd: list[str]) -> tuple[int, str]:
    """单次 ffmpeg 切片：CREATE_NO_WINDOW 防黑框 + 捕获输出 + 超时兜底。"""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, encoding="utf-8", errors="replace",
            timeout=_FFMPEG_TIMEOUT_S, creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)
    return proc.returncode, proc.stderr or ""


def _bat(header_lines: list[str], body: str) -> str:
    """bat 正文：@echo off + chcp 65001（中文路径/输出可读）+ body + pause。"""
    return "\r\n".join(["@echo off", "chcp 65001 >nul", *header_lines, body,
                        "pause", ""])


def _python_exe() -> str:
    return str(_PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")


# ------------------------------------------------------------------ 内嵌网页

_PAGE_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>C22 听点标注器</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; padding: 16px; background: #f4f5f7; color: #16181d;
         font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
         font-size: 20px; line-height: 1.6; }
  h1 { font-size: 22px; margin: 0 0 12px; }
  #progress { position: sticky; top: 0; z-index: 10; background: #1f2937;
              color: #fff; padding: 12px 16px; border-radius: 10px;
              font-size: 22px; font-weight: 700; margin-bottom: 16px; }
  .card { background: #fff; border: 1px solid #dfe3e8; border-radius: 12px;
          padding: 16px; margin-bottom: 16px; }
  .meta { color: #4b5563; font-size: 18px; word-break: break-all; margin-bottom: 8px; }
  audio { width: 100%; margin: 12px 0; display: block; }
  button { min-height: 44px; min-width: 44px; font-size: 20px; padding: 10px 20px;
           margin: 4px 6px 4px 0; border-radius: 10px; border: 1px solid #cbd5e1;
           background: #fff; color: #16181d; cursor: pointer; }
  button:disabled { opacity: .45; cursor: not-allowed; }
  .b-skip { background: #b45309; border-color: #b45309; color: #fff; }
  .b-main { background: #1d4ed8; border-color: #1d4ed8; color: #fff; }
  .glossary { background: #eef2ff; border: 1px solid #c7d2fe; color: #3730a3;
              padding: 8px 12px; border-radius: 10px; font-size: 17px;
              margin-bottom: 12px; }
  .combos { display: flex; flex-direction: column; gap: 10px; margin: 10px 0; }
  .grp { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px;
         padding: 8px 10px; }
  .grp-head { font-size: 17px; font-weight: 700; color: #334155; margin-bottom: 6px; }
  .grp-legend { margin-left: 10px; font-weight: 400; font-size: 15px;
                background: #dcfce7; border: 1px solid #16a34a; color: #14532d;
                border-radius: 999px; padding: 0 8px; }
  .grp-btns { display: flex; flex-wrap: wrap; gap: 6px; }
  .combo { margin: 0; padding: 8px 12px; font-size: 18px; border-radius: 10px; }
  .combo.c-yes { background: #15803d; border-color: #15803d; color: #fff; }
  .combo.c-no { background: #e5e7eb; border-color: #94a3b8; color: #16181d; }
  .corner { font-size: 14px; margin-left: 6px; border-radius: 6px; padding: 0 4px; }
  .combo.c-yes .corner { background: rgba(255, 255, 255, .22); }
  .combo.c-no .corner { background: #cbd5e1; color: #334155; }
  .ok { background: #dcfce7; border: 1px solid #16a34a; color: #14532d;
        padding: 14px; border-radius: 10px; margin-bottom: 12px; }
  .warn { background: #fef9c3; border: 1px solid #ca8a04; color: #713f12;
          padding: 14px; border-radius: 10px; margin-bottom: 12px; }
  .disputed { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px;
              padding: 12px; margin-bottom: 10px; }
  .hint { color: #6b7280; font-size: 17px; }
</style>
</head>
<body>
<h1>C22 听点标注器 · 一边听一边勾</h1>
<div class="glossary">__GLOSSARY__</div>
<div id="progress">第 <span id="pIdx">0</span> / <span id="pTotal">0</span> 条 ·
 已标 <span id="pDone">0</span> · 待定 <span id="pPend">0</span></div>
<div id="main" class="card">正在读取标注状态…</div>
<script>
"use strict";
let st = {records: [], relabel_queue: []};
let mode = "first";   // first=首轮 | re=复标轮 | done=已出一致率
let idx = 0;          // 首轮游标（可回退改判）
let qpos = 0;         // 复标游标
const COMBOS = __COMBOS__;   // 声源组合表（服务端同源注入：C(4,0)~C(4,4) 穷举）
const GROUP_NAMES = {0: "无声源", 1: "单声源 C(4,1)", 2: "双声源 C(4,2)",
                     3: "三声源 C(4,3)", 4: "四声源 C(4,4)"};
const SOUND_KEYS = ["speech", "moan", "prop", "bg"];

function el(id) { return document.getElementById(id); }
function esc(s) {
  return String(s === null || s === undefined ? "" : s).replace(
    /[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;",
              "'": "&#39;"}[c];
    });
}
// ---- 声源组合（卡3）：听感事实=四布尔向量，派生真值=speech 命中即有对话 ----
function deriveValue(sounds) {
  return sounds && sounds.speech ? "yes" : "no";
}
function sameSounds(a, b) {
  return SOUND_KEYS.every(function (k) { return !!a[k] === !!b[k]; });
}
function comboText(sounds) {
  const hit = COMBOS.find(function (c) { return sameSounds(c.sounds, sounds); });
  return hit ? hit.text : "未知组合";
}
function comboGroups() {
  const out = [];
  COMBOS.forEach(function (c, i) {
    const g = out[out.length - 1];
    if (g && g.n === c.n) { g.items.push({c: c, i: i}); }
    else { out.push({n: c.n, items: [{c: c, i: i}]}); }
  });
  return out;
}
function combosHtml() {
  let html = '<div class="combos">';
  comboGroups().forEach(function (g) {
    html += '<div class="grp"><div class="grp-head">' + GROUP_NAMES[g.n] +
            '<span class="grp-legend">含台词=有对话</span></div>' +
            '<div class="grp-btns">';
    g.items.forEach(function (it) {
      const yes = it.c.derived === "yes";
      html += '<button type="button" class="combo ' + (yes ? "c-yes" : "c-no") +
              '" data-i="' + it.i + '" title="' +
              (yes ? "组合含台词 → 派生「有对话」"
                   : "组合不含台词 → 派生「无对话」") + '">' +
              esc(it.c.text) +
              '<span class="corner">' + (yes ? "有对话" : "无对话") +
              '</span></button>';
    });
    html += '</div></div>';
  });
  return html + '</div>';
}
function wireCombos(root, cb) {
  if (!root) { return; }
  root.querySelectorAll("button.combo").forEach(function (b) {
    b.onclick = function () { cb(COMBOS[Number(b.dataset.i)].sounds); };
  });
}
function firstValue(r) { return r.sounds ? deriveValue(r.sounds) : r.label; }
function reValue(r) { return r.relabel_sounds ? deriveValue(r.relabel_sounds) : r.relabel; }
function decided(label) { return label === "yes" || label === "no"; }
function answeredRe(r) { return decided(reValue(r)); }
function pendingCount() {
  return st.records.filter(function (r) { return !decided(firstValue(r)); }).length;
}
function queueRecords() {
  return (st.relabel_queue || []).map(function (id) {
    return st.records.find(function (r) { return r.id === id; });
  }).filter(Boolean);
}
function badge(label) {
  if (label === "yes") { return "✅ 有对话"; }
  if (label === "no") { return "❌ 无对话"; }
  if (label === "skip") { return "⏭ 稍后再听（待定）"; }
  return "未作答";
}
function firstStateText(r) {
  if (r.sounds) { return comboText(r.sounds) + " → " + badge(deriveValue(r.sounds)); }
  if (r.label === "yes") { return "旧口径已标：有对话（可重答）"; }
  if (r.label === "no") { return "旧口径已标：无对话（可重答）"; }
  if (r.label === "skip") { return "旧口径已标：稍后再听（可重答）"; }
  return badge(r.label);
}
async function getJSON(url) {
  const r = await fetch(url, {cache: "no-store"});
  const data = await r.json();
  if (!r.ok) { throw new Error(data.error || ("请求失败：" + r.status)); }
  return data;
}
async function postJSON(url, payload) {
  const r = await fetch(url, {method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)});
  const data = await r.json();
  if (!r.ok) { throw new Error(data.error || ("请求失败：" + r.status)); }
  return data;
}
function refreshProgress() {
  const total = st.records.length;
  const done = st.records.filter(function (r) { return decided(firstValue(r)); }).length;
  el("pTotal").textContent = total;
  el("pDone").textContent = done;
  el("pPend").textContent = total - done;
  if (mode === "done") { el("pIdx").textContent = total; }
  else if (mode === "re") {
    el("pIdx").textContent = Math.min(qpos + 1, queueRecords().length);
  } else { el("pIdx").textContent = Math.min(idx + 1, total); }
}
function currentRecord() {
  if (mode === "re") {
    const q = queueRecords();
    if (!q.length) { return null; }
    return q[Math.min(qpos, q.length - 1)];
  }
  if (!st.records.length) { return null; }
  return st.records[Math.min(idx, st.records.length - 1)];
}
function advance() {
  if (mode === "re") {
    const q = queueRecords();
    qpos = qpos + 1;
    if (qpos >= q.length) { mode = "done"; qpos = Math.max(0, q.length - 1); }
    return;
  }
  const n = st.records.length;
  for (let k = idx + 1; k < n; k++) {
    if (!decided(firstValue(st.records[k]))) { idx = k; return; }
  }
  for (let k = 0; k < n; k++) {
    if (!decided(firstValue(st.records[k]))) { idx = k; return; }
  }
}
function goPrev() {
  if (mode === "re") { qpos = Math.max(0, qpos - 1); }
  else { idx = Math.max(0, idx - 1); }
  render();
}
async function answer(sounds) {
  const rec = currentRecord();
  if (!rec) { return; }
  const payload = {id: rec.id, round: mode === "re" ? "re" : "first"};
  if (sounds) {
    payload.sounds = sounds;          // 四布尔向量；服务端按向量派生 label
    payload.value = deriveValue(sounds);
  } else {
    payload.value = "skip";           // 次按钮「稍后再听」（仅首轮有）
  }
  try {
    const data = await postJSON("/api/answer", payload);
    st = data.state || st;
    advance();
    render();
  } catch (e) { alert("作答失败：" + e.message); }
}
async function startRelabel() {
  try {
    const data = await postJSON("/api/relabel/start", {});
    st.relabel_queue = data.queue || [];
    qpos = 0;
    mode = "re";
    render();
  } catch (e) { alert("进入复标失败：" + e.message); }
}
function resumeRelabel() {
  const q = queueRecords();
  const undone = q.findIndex(function (r) { return !answeredRe(r); });
  qpos = undone < 0 ? 0 : undone;
  mode = "re";
  render();
}
async function disputeAnswer(id, sounds) {
  // 争议改判：同款组合钮盲标，同步写回首轮标注（label 与向量一并覆盖）
  try {
    const data = await postJSON("/api/answer",
      {id: id, round: "re", value: deriveValue(sounds), sounds: sounds,
       sync_label: true});
    st = data.state || st;
    renderAgreement();
  } catch (e) { alert("改判失败：" + e.message); }
}
function renderFirstDone() {
  const hasQueue = queueRecords().length > 0;
  el("main").innerHTML =
    '<div class="ok">✅ 首轮标注已全部完成：共 ' + st.records.length +
    ' 条，已决 ' + st.records.length + ' 条。</div>' +
    '<p class="hint">复标建议隔 1-2 天再做，避免凭记忆作答。</p>' +
    (hasQueue ? '<button class="b-main" id="btnResume">继续复标</button>'
              : '<button class="b-main" id="btnRelabel">进入复标（建议隔 1-2 天）</button>');
  if (el("btnRelabel")) { el("btnRelabel").onclick = startRelabel; }
  if (el("btnResume")) { el("btnResume").onclick = resumeRelabel; }
}
function seekToGap(a, seekIn) {
  // 卡4 播放起点=间隙本体：片段时长 >6.5s 且未被起点 clamp（seek_in=3.0）时在
  // play 前跳过前 3s 缓冲；重听按钮不走本函数（保持从头）。片段元数据未加载时
  // 挂一次性 loadedmetadata 监听，避免 duration 为 NaN 时漏跳。
  if (!(seekIn > 0)) { return; }
  const apply = function () {
    if (a.duration > 6.5) { a.currentTime = seekIn; }
  };
  if (isFinite(a.duration) && a.duration > 0) { apply(); }
  else { a.addEventListener("loadedmetadata", apply, {once: true}); }
}
function render() {
  refreshProgress();
  if (mode === "done") { renderAgreement(); return; }
  if (mode === "first" && pendingCount() === 0) { renderFirstDone(); return; }
  const rec = currentRecord();
  if (!rec) {
    el("main").innerHTML = '<p class="hint">标注包内没有条目，请先执行 --prepare。</p>';
    return;
  }
  const isRe = mode === "re";
  let html = '<div class="meta">条目 <b>' + esc(rec.id) + '</b> · 轮次 ' +
             esc(rec.run) + ' · 判读区间：' + esc(rec.timing) +
             (isRe ? '' : ' · 首轮标注：<b>' + firstStateText(rec) + '</b>') +
             // 卡4：粗筛提示透传（manifest samples[].message，有则显、esc 转义）
             (rec.message ? '<br>粗筛提示：' + esc(rec.message) : '') + '</div>';
  html += '<audio id="au" preload="auto" loop src="/clips/' +
          encodeURIComponent(rec.id) + '.wav"></audio>';
  html += '<div><button class="b-main" id="btnPlay">▶ 播放（默认循环）</button>' +
          '<button id="btnRestart">重听</button>' +
          ((isRe ? qpos : idx) > 0
            ? '<button id="btnPrev">← 上一条（回退改判）</button>' : '') + '</div>';
  // 卡4：作答区提示行前追加缓冲说明（首尾各约 3s 为缓冲上下文，只判间隙本体）
  html += '<p class="hint">__BUFFER_HINT__。</p>';
  html += '<p class="hint">点选声源组合即提交：绿色+「有对话」角标=组合含台词（派生有对话）；' +
          '中性色+「无对话」角标=不含台词（静音同样为无对话）。</p>';
  html += '<div id="answerBtns">' + combosHtml() + '</div>';
  if (!isRe) {
    html += '<div><button class="b-skip" id="btnSkip">⏭ 稍后再听</button></div>';
  }
  html += '<p class="hint">' +
          (isRe ? '复标轮盲标：不回显首轮选择，请凭听感独立点选组合（只按派生 label 计，无「稍后再听」）。'
                : '单击任一组合即提交，自动跳下一条并自动播放；判错了可回退改判。') + '</p>';
  el("main").innerHTML = html;
  // 卡4：播放起点=间隙本体（seek_in 由服务端按 clamp 规则注入 records）；重听保持从头
  const seekIn = Number(rec.seek_in || 0);
  el("btnPlay").onclick = function () {
    const a = el("au"); seekToGap(a, seekIn); a.loop = true; a.play();
  };
  el("btnRestart").onclick = function () {
    const a = el("au"); a.currentTime = 0; a.play();
  };
  // 作答跳条后自动播放下一条（owner 2026-10-13 试听反馈）；页面刚打开尚无
  // 用户手势时浏览器自动播放策略会拒绝，静默降级为手动点播放
  const a0 = el("au"); a0.loop = true; seekToGap(a0, seekIn);
  const pp = a0.play();
  if (pp && pp.catch) { pp.catch(function () {}); }
  if (el("btnPrev")) { el("btnPrev").onclick = goPrev; }
  wireCombos(el("answerBtns"), answer);
  if (el("btnSkip")) { el("btnSkip").onclick = function () { answer(null); }; }
}
async function renderAgreement() {
  el("main").innerHTML = '<p class="hint">正在统计复标一致率…</p>';
  let a;
  try { a = await getJSON("/api/agreement"); }
  catch (e) {
    el("main").innerHTML = '<div class="warn">统计失败：' + esc(e.message) + '</div>';
    return;
  }
  let html = '';
  if (!a.total) {
    html += '<div class="warn">复标队列还没有作答记录（复标轮只按声源组合的派生 label 计）。</div>';
  } else {
    const ok = a.pct >= 90;
    html += '<div class="' + (ok ? 'ok' : 'warn') + '">复标一致率：' + a.agree +
            ' / ' + a.total + ' = <b>' + a.pct.toFixed(2) + '%</b>（门槛 90%）<br>' +
            (ok ? '✅ 已达标：可双击标注包内的「一键回放.bat」生成回放报告。'
                : '⚠️ 未达标：请逐条重听下面的争议条目并改判（改判同步写回首轮标注）。') +
            '</div>';
    if (!ok && a.disputed.length) {
      html += '<p class="hint">争议条目 ' + a.disputed.length +
              ' 条（盲标改判：点选你听到的声源组合，同步写回首轮标注）：</p>';
      a.disputed.forEach(function (id) {
        const rec = st.records.find(function (r) { return r.id === id; });
        html += '<div class="disputed" data-id="' + esc(id) + '"><b>' + esc(id) +
                '</b> · ' + esc(rec ? rec.timing : '') +
                '<div><audio controls loop src="/clips/' +
                encodeURIComponent(id) + '.wav"></audio></div>' +
                combosHtml() + '</div>';
      });
    }
  }
  html += '<div><button class="b-main" id="btnBack">返回首轮（回退改判）</button></div>';
  el("main").innerHTML = html;
  el("btnBack").onclick = function () { mode = "first"; idx = 0; render(); };
  el("main").querySelectorAll("div.disputed").forEach(function (d) {
    wireCombos(d.querySelector("div.combos"), function (sounds) {
      disputeAnswer(d.dataset.id, sounds);
    });
  });
}
async function init() {
  try {
    st = await getJSON("/api/state");
    st.records = st.records || [];
    if (!st.relabel_queue) { st.relabel_queue = []; }
    const q = queueRecords();
    const undone = q.findIndex(function (r) { return !answeredRe(r); });
    if (pendingCount() === 0 && q.length > 0) {
      if (undone < 0) { mode = "done"; }
      else { mode = "re"; qpos = undone; }
    } else { mode = "first"; idx = 0; }
    render();
  } catch (e) {
    el("main").innerHTML = '<div class="warn">读取标注状态失败：' +
                           esc(e.message) + '</div>';
  }
}
init();
</script>
</body>
</html>
"""

# 模板注入：页首名词解释、声源组合表与作答区缓冲说明与服务端同源
# （同一份 _GLOSSARY / _COMBOS / _BUFFER_HINT）
_PAGE = (_PAGE_TMPL.replace("__GLOSSARY__", _GLOSSARY)
         .replace("__COMBOS__", json.dumps(_COMBOS, ensure_ascii=False))
         .replace("__BUFFER_HINT__", _BUFFER_HINT))


# ------------------------------------------------------------- 子命令：prepare

def cmd_prepare(package: Path) -> int:
    manifest_path = package / "c22_manifest.json"
    if not manifest_path.is_file():
        print("❌ 标注包缺少 c22_manifest.json：请先生成 C22 校准标注包再执行 --prepare")
        return 1
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"❌ c22_manifest.json 读取失败：{e}")
        return 1
    samples = data.get("samples") if isinstance(data, dict) else None
    if not isinstance(samples, list) or not samples:
        print("❌ c22_manifest.json 格式不符：samples 数组缺失或为空")
        return 1

    # 在位校验：导读 / 媒体必须存在，缺失全部汇总后一次性报出（不逐条中断）
    missing: list[str] = []
    for i, s in enumerate(samples, 1):
        if not isinstance(s, dict):
            missing.append(f"第 {i} 条样本不是 JSON 对象")
            continue
        sid = str(s.get("id") or f"#{i}")
        for key, cn in (("guide_path", "导读"), ("media_path", "媒体")):
            p = str(s.get(key) or "")
            if not p:
                missing.append(f"{sid}：{cn}路径为空")
            elif not Path(p).is_file():
                missing.append(f"{sid}：{cn}不存在 → {p}")
    if missing:
        print("❌ 标注包在位校验失败（已中止，未写 state.json）：")
        for line in missing:
            print(f"   - {line}")
        print(f"共 {len(missing)} 处缺失，请补齐文件后重跑 --prepare")
        return 1

    ffmpeg = resolve_ffmpeg()
    if not ffmpeg:
        print("❌ 未找到可用的 ffmpeg（resolve_ffmpeg 返回空）：请安装 ffmpeg 或用内置上游目录后重试")
        return 1

    clips_dir = package / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    prev_state = _read_state(package)   # 幂等保标注（卡4）：重跑前先读旧 state
    records: list[dict] = []
    failures: list[str] = []
    for i, s in enumerate(samples, 1):
        sid = str(s.get("id") or f"#{i}")
        span = _parse_timing(str(s.get("timing") or ""))
        if span is None:
            failures.append(f"{sid}：timing 无法解析 → {s.get('timing')!r}")
            continue
        start, end = span
        seek = max(0.0, start - _PAD_BEFORE_S)
        dur = min(end - start + _PAD_TOTAL_S, float(_CLIP_CAP_S))
        wav = clips_dir / f"{sid}.wav"
        cmd = [ffmpeg, "-y", "-ss", _fmt_seconds(seek), "-t", _fmt_seconds(dur),
               "-i", str(s.get("media_path") or ""), "-vn", "-ac", "1",
               "-ar", "16000", str(wav)]
        rc, err = _run_ffmpeg(cmd)
        if rc != 0:
            tail = (err or "").strip()[-200:]
            failures.append(f"{sid}：ffmpeg 切片失败（退出码 {rc}）{('｜' + tail) if tail else ''}")
            continue
        msg = s.get("message")   # 粗筛提示透传（卡4）：缺省 null，serve 页 meta 显示
        records.append({"id": sid, "run": str(s.get("run") or ""),
                        "wav": str(wav), "media": str(s.get("media_path") or ""),
                        "guide": str(s.get("guide_path") or ""),
                        "timing": str(s.get("timing") or ""),
                        "message": None if msg is None else str(msg),
                        "seek_in": _seek_in(start),   # 播放起点（卡4）
                        "label": None, "relabel": None,
                        "sounds": None, "relabel_sounds": None})
    if failures:
        print("❌ 切片失败（已中止，未写 state.json）：")
        for line in failures:
            print(f"   - {line}")
        print(f"共 {len(failures)} 处失败，请检查媒体与 timing 后重跑 --prepare")
        return 1

    kept = _merge_annotations(records, prev_state)   # 幂等保标注（卡4 硬约束）
    labeled = sum(1 for r in records if _record_label(r) in _DECIDED)
    _atomic_write_json(package / _STATE_NAME,
                       {"records": records, "relabel_queue": []})

    script = str(Path(__file__).resolve())
    bat_body = f'"{_python_exe()}" "{script}" --serve --package "{package}"'
    _atomic_write_text(package / "开始标注.bat", _bat([], bat_body))

    runs = sorted({str(s.get("run") or "") for s in samples} - {""})
    medias = {str(s.get("media_path") or "") for s in samples}
    guides = {str(s.get("guide_path") or "") for s in samples}
    print(f"✅ 标注包准备完成：共 {len(records)} 段切片，"
          f"涉及轮次 {len(runs)} 个（{'、'.join(runs) or '未标轮次'}），"
          f"媒体 {len(medias)} 个 / 导读 {len(guides)} 个")
    print(f"📝 已标注 {labeled} 条 / 待定 {len(records) - labeled} 条"
          "（首轮已决口径，按合并后 records 重算）")
    if prev_state is not None:
        print(f"🔁 幂等合并：已保留 {kept} 条既有标注"
              "（按 id 继承 label/sounds/relabel/relabel_sounds，clips 已重切覆盖）")
    print(f"📄 标注状态：{package / _STATE_NAME}（每次作答原子落盘，断电不丢）")
    print("🎧 下一步：双击标注包内的「开始标注.bat」开标"
          "（网页只绑本机 127.0.0.1，零外发零遥测）")
    return 0


# -------------------------------------------------------------- 子命令：serve

def _send(self: _Handler, code: int, body: bytes, ctype: str) -> None:
    self.send_response(code)
    self.send_header("Content-Type", ctype)
    self.send_header("Content-Length", str(len(body)))
    self.send_header("Cache-Control", "no-store")
    self.end_headers()
    self.wfile.write(body)


def _send_json(self: _Handler, obj, code: int = 200) -> None:
    _send(self, code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
          "application/json; charset=utf-8")


class _Handler(BaseHTTPRequestHandler):
    """内嵌单页标注网页 + 5 条 JSON 路由；只服务本机回环请求。"""

    server_version = "C22Labeler/1.0"

    def log_message(self, fmt: str, *args) -> None:  # 静默访问日志（避免污染终端）
        pass

    @property
    def _package(self) -> Path:
        return Path(self.server.package_dir)

    def _body_json(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length > 0 else b""
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def do_GET(self) -> None:  # http.server 约定的回调名（非 N 风格规则集）
        path = urlparse(self.path).path
        if path == "/":
            _send(self, 200, _PAGE.encode("utf-8"),
                  "text/html; charset=utf-8")
            return
        if path == "/api/state":
            try:
                raw = (self._package / _STATE_NAME).read_bytes()
            except OSError:
                _send_json(self, {"error": "state.json 不存在：请先执行 --prepare"}, 404)
                return
            _send(self, 200, raw, "application/json; charset=utf-8")
            return
        if path == "/api/agreement":
            state = _read_state(self._package)
            if state is None:
                _send_json(self, {"error": "state.json 缺失或损坏：请先执行 --prepare"}, 404)
                return
            _send_json(self, _agreement(state))
            return
        if path.startswith("/clips/"):
            name = unquote(path[len("/clips/"):])
            if Path(name).name != name or not name.endswith(".wav"):
                _send_json(self, {"error": "片段名不合法"}, 400)
                return
            wav = self._package / "clips" / name
            if not wav.is_file():
                _send_json(self, {"error": f"片段不存在：{name}"}, 404)
                return
            _send(self, 200, wav.read_bytes(), "audio/wav")
            return
        _send_json(self, {"error": f"未知路径：{path}"}, 404)

    def do_POST(self) -> None:  # http.server 约定的回调名（非 N 风格规则集）
        path = urlparse(self.path).path
        if path == "/api/answer":
            self._handle_answer()
            return
        if path == "/api/relabel/start":
            self._handle_relabel_start()
            return
        _send_json(self, {"error": f"未知路径：{path}"}, 404)

    def _handle_answer(self) -> None:
        payload = self._body_json()
        if payload is None:
            _send_json(self, {"error": "请求体须为 JSON 对象"}, 400)
            return
        rid = str(payload.get("id") or "")
        round_ = str(payload.get("round") or "")
        value = str(payload.get("value") or "")
        if round_ not in (_FIRST, _RE):
            _send_json(self, {"error": "round 须为 first（首轮）或 re（复标轮）"}, 400)
            return
        sounds: dict | None = None
        raw_sounds = payload.get("sounds")
        if raw_sounds is not None:
            # 卡3：带声源向量时以向量为权威，label 由服务端派生（客户端值只做一致性校验）
            sounds, err = _validate_sounds(raw_sounds)
            if err is not None:
                _send_json(self, {"error": err}, 400)
                return
            derived = _derive_label(sounds)
            if derived is None:  # 防御：_validate_sounds 已保证为四键布尔对象
                _send_json(self, {"error": "sounds 校验未通过（须为四键布尔对象）"}, 400)
                return
            if value == "skip":
                _send_json(self, {"error": "「稍后再听」不记录声源组合（请去掉 sounds）"}, 400)
                return
            if value and value not in _DECIDED:
                _send_json(self, {"error": "带 sounds 时 value 须为 yes / no（或省略）"}, 400)
                return
            if value and value != derived:
                _send_json(self, {"error": f"value={value} 与 sounds 派生结果 {derived} 不一致"
                                           "（含台词→yes，不含→no）"}, 400)
                return
            value = derived
        elif value not in _ALL_VALUES:
            _send_json(self, {"error": "value 须为 yes / no / skip"}, 400)
            return
        if round_ == _RE and value == "skip":
            _send_json(self, {"error": "复标轮只认 yes / no，没有「稍后再听」"}, 400)
            return
        with self.server.state_lock:
            state = _read_state(self._package)
            if state is None:
                _send_json(self, {"error": "state.json 缺失或损坏：请先执行 --prepare"}, 404)
                return
            record = next((r for r in (state.get("records") or [])
                           if str(r.get("id")) == rid), None)
            if record is None:
                _send_json(self, {"error": f"找不到条目：{rid}"}, 404)
                return
            if round_ == _RE and rid not in (state.get("relabel_queue") or []):
                _send_json(self, {"error": "该条目不在复标队列（请先「进入复标」）"}, 400)
                return
            if round_ == _FIRST:
                # 重答覆盖：不带 sounds 即清空向量（label 仍为权威，退回旧口径语义）
                record["label"] = value
                record["sounds"] = sounds
            else:
                record["relabel"] = value
                record["relabel_sounds"] = sounds
                if payload.get("sync_label"):
                    # 争议改判同步写回首轮标注（label 与向量一并覆盖，保持可派生）
                    record["label"] = value
                    record["sounds"] = sounds
            _atomic_write_json(self._package / _STATE_NAME, state)
        _send_json(self, {"ok": True, "state": state})

    def _handle_relabel_start(self) -> None:
        with self.server.state_lock:
            state = _read_state(self._package)
            if state is None:
                _send_json(self, {"error": "state.json 缺失或损坏：请先执行 --prepare"}, 404)
                return
            decided = [r for r in (state.get("records") or [])
                       if _record_label(r) in _DECIDED]
            if not decided:
                _send_json(self, {"error": "首轮尚无已决条目，无法进入复标"}, 400)
                return
            count = _ceil_20_percent(len(decided))
            # SystemRandom：Mimosa insecure-randomness 钉（D2026-1012-03 验收轮）；
            # 抽样虽非安全用途，加密级随机源零成本消除扫描噪声
            queue = [str(r.get("id"))
                     for r in random.SystemRandom().sample(decided, count)]
            for r in state.get("records") or []:
                r["relabel"] = None  # 重开复标即清旧复标答案（不混算一致率）
            state["relabel_queue"] = queue
            _atomic_write_json(self._package / _STATE_NAME, state)
        _send_json(self, {"ok": True, "queue": queue, "count": count})


def create_server(package: Path | str,
                  first_port: int = _PORT_START,
                  last_port: int = _PORT_END) -> ThreadingHTTPServer:
    """只绑 127.0.0.1：first_port 被占则 +1 重试至 last_port。"""
    package_dir = str(Path(package).resolve())
    for port in range(first_port, last_port + 1):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
        except OSError:
            continue
        httpd.package_dir = package_dir
        httpd.state_lock = threading.Lock()
        return httpd
    raise RuntimeError(f"端口 {first_port}-{last_port} 全部被占用："
                       "请关闭占用该端口的程序后重试")


def cmd_serve(package: Path) -> int:
    if not (package / _STATE_NAME).is_file():
        print(f"❌ 找不到 {package / _STATE_NAME}：请先执行 --prepare 生成标注状态")
        return 1
    try:
        httpd = create_server(package)
    except RuntimeError as e:
        print(f"❌ {e}")
        return 1
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"🎧 标注网页已启动：{url}")
    print("   只绑本机 127.0.0.1（零外发零遥测）；关掉本窗口即停止标注服务")
    threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 标注服务已停止（进度已原子落盘 state.json，可随时续标）")
    finally:
        httpd.server_close()
    return 0


# ------------------------------------------------------------- 子命令：merge

def cmd_merge(package: Path) -> int:
    state = _read_state(package)
    if state is None:
        print(f"❌ {package / _STATE_NAME} 缺失或损坏：请先执行 --prepare")
        return 1
    records = state.get("records") or []
    if not records:
        print("❌ state.json 内无标注记录：请先执行 --prepare 并完成标注")
        return 1
    pending = _pending(state)
    if pending:
        print(f"❌ 首轮仍有 {len(pending)} 条待定（未作答或「稍后再听」），"
              "不能合并出回放清单：")
        for r in pending[:10]:
            print(f"   - {r.get('id')}（{r.get('timing')}）")
        if len(pending) > 10:
            print(f"   … 其余 {len(pending) - 10} 条略")
        print(f"pending 计数：{len(pending)}；请回到标注网页补标后再 --merge")
        return 1

    groups: dict[tuple[str, str], list[dict]] = {}
    order: list[tuple[str, str]] = []
    for r in records:
        key = (os.path.abspath(str(r.get("guide") or "")),
               os.path.abspath(str(r.get("media") or "")))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)
    manifest = []
    for key in order:
        rows = groups[key]
        manifest.append({
            "guide": key[0], "media": key[1],
            "timings": [str(r.get("timing") or "") for r in rows],
            "labels": [_record_label(r) == "yes" for r in rows],   # 恒为派生值
        })
    _atomic_write_json(package / "c22_manifest_labeled.json", manifest)

    manifest_path = package / "c22_manifest_labeled.json"
    report_path = package / "c22_report.md"
    bat_body = (f'"{_python_exe()}" '
                f'"{_PROJECT_ROOT / "tools" / "c22_calibration.py"}" '
                f'--manifest "{manifest_path}" --out "{report_path}" --enable')
    _atomic_write_text(package / "一键回放.bat", _bat([], bat_body))

    yes = sum(1 for r in records if _record_label(r) == "yes")
    no = sum(1 for r in records if _record_label(r) == "no")
    agreement = _agreement(state)
    print(f"✅ 合并完成：{len(manifest)} 组（按 guide+media 分组）/ "
          f"{len(records)} 条间隙 → {manifest_path}")
    print(f"   标注分布：true（有对话）= {yes}，false（无对话）= {no}")
    dist = _sound_distribution(records)
    print("   声源组合分布（卡3 听感观察数据，非校准指标）：")
    for n in sorted(_GROUP_NAMES):
        parts = [f"{c['text']}={dist['counts'][c['text']]}"
                 for c in _COMBOS if c["n"] == n]
        print(f"     {_GROUP_NAMES[n]}：" + "、".join(parts))
    print(f"   {_OVERLAY_CN}小计：{dist['overlay']} 条"
          "（组合含台词且叠加道具声或背景声）")
    if dist["legacy"]:
        print(f"   旧口径未记声源：{dist['legacy']} 条"
              "（不入组合分布，可回网页重答补记）")
    if agreement["total"]:
        verdict = "达标（≥90%）" if agreement["pct"] >= 90 else "未达标（<90%，建议复标争议条目）"
        print(f"   复标一致率：{agreement['agree']}/{agreement['total']} = "
              f"{agreement['pct']:.2f}%（{verdict}）")
    else:
        print("   复标一致率：未做复标（建议先复标再回放）")
    print(f"📄 回放清单：{manifest_path}（timings 与 labels 显式对齐，卡1 口径）")
    print("👉 下一步：双击标注包内的「一键回放.bat」生成回放报告；"
          "未达标时 harness 自拒写门控（fail-closed，安全）")
    return 0


# ---------------------------------------------------------------- 入口

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="c22_labeler",
        description="C22 听点式标注器（本地网页：一边听一边勾，零第三方依赖）")
    parser.add_argument("--prepare", action="store_true",
                        help="切片并生成 state.json + 开始标注.bat")
    parser.add_argument("--serve", action="store_true",
                        help="启动本地标注网页（只绑 127.0.0.1:8765 起）")
    parser.add_argument("--merge", action="store_true",
                        help="合并首轮标注 → 回放清单 + 一键回放.bat")
    parser.add_argument("--package", default="",
                        help="标注包目录（含 c22_manifest.json / state.json）")
    args = parser.parse_args(argv)

    if not (args.prepare or args.serve or args.merge):
        parser.print_help()
        return 0
    if not args.package:
        print("❌ 缺少 --package <标注包目录>（--help 查看用法）")
        return 1
    package = Path(args.package)
    if not package.is_dir():
        print(f"❌ 标注包目录不存在：{package}")
        return 1
    if args.prepare:
        return cmd_prepare(package)
    if args.serve:
        return cmd_serve(package)
    return cmd_merge(package)


if __name__ == "__main__":
    sys.exit(main())
