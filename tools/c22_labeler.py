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
  起-3 clamp≥0、时长 min(止-起+6, 20)；CREATE_NO_WINDOW + capture_output
  + timeout）→ 原子写 state.json（records=[{id, run, wav, media, guide,
  timing, label:null, relabel:null}]）→ 写 开始标注.bat → 打印中文摘要；
- --serve：http.server 只绑 127.0.0.1，端口 8765 被占则 +1 重试至 8774，
  启动后自动开页。路由：GET /（内嵌单页 HTML，全中文零外链）、
  GET /api/state、GET /clips/<id>.wav、POST /api/answer（每次点击原子落盘，
  断电不丢）、POST /api/relabel/start（首轮已决条目随机抽 ceil(20%) 进复标）、
  GET /api/agreement（复标轮只认 yes/no，无 skip）；
- --merge：首轮有 pending（null 或 skip）→ 中文报错退出码 1 并报计数；
  否则按 (guide, media) 分组保原序写 c22_manifest_labeled.json（harness
  数组格式，每组 {guide, media, timings[], labels[]}——走 C22-卡1 的
  timings+labels 显式对齐口径）+ 一键回放.bat（未达标时 harness 自拒写门控，
  fail-closed 安全）。

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
_CLIP_CAP_S = 20           # 单片段时长上限（秒）
_FFMPEG_TIMEOUT_S = 120    # 单次切片超时兜底
_ATOMIC_RETRY = 5          # 原子写 Windows 瞬时占用重试次数
_ATOMIC_RETRY_DELAY_S = 0.05
_RELABEL_DIV = 5           # 复标抽样 = ceil(20%) = ceil(n/5)
_STATE_NAME = "state.json"
_FIRST = "first"
_RE = "re"
_DECIDED = ("yes", "no")
_ALL_VALUES = ("yes", "no", "skip")

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


def _pending(state: dict) -> list[dict]:
    """首轮待定条目：label 为 null 或 skip（skip=稍后再听，不算已决）。"""
    return [r for r in (state.get("records") or [])
            if r.get("label") not in _DECIDED]


def _ceil_20_percent(n: int) -> int:
    """ceil(n × 20%)，整数运算避开浮点误差。"""
    return -(-n // _RELABEL_DIV)


def _agreement(state: dict) -> dict:
    """复标一致率：只认复标轮 yes/no（无 skip），争议=与首轮判罚不一致。"""
    answered = [r for r in (state.get("records") or [])
                if r.get("relabel") in _DECIDED]
    total = len(answered)
    agree = sum(1 for r in answered if r.get("label") == r.get("relabel"))
    pct = round(agree * 100.0 / total, 2) if total else 0.0
    disputed = [str(r.get("id")) for r in answered
                if r.get("label") != r.get("relabel")]
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

_PAGE = """<!DOCTYPE html>
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
  .b-yes { background: #15803d; border-color: #15803d; color: #fff; }
  .b-no { background: #b91c1c; border-color: #b91c1c; color: #fff; }
  .b-skip { background: #b45309; border-color: #b45309; color: #fff; }
  .b-main { background: #1d4ed8; border-color: #1d4ed8; color: #fff; }
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
<div id="progress">第 <span id="pIdx">0</span> / <span id="pTotal">0</span> 条 ·
 已标 <span id="pDone">0</span> · 待定 <span id="pPend">0</span></div>
<div id="main" class="card">正在读取标注状态…</div>
<script>
"use strict";
let st = {records: [], relabel_queue: []};
let mode = "first";   // first=首轮 | re=复标轮 | done=已出一致率
let idx = 0;          // 首轮游标（可回退改判）
let qpos = 0;         // 复标游标

function el(id) { return document.getElementById(id); }
function esc(s) {
  return String(s === null || s === undefined ? "" : s).replace(
    /[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;",
              "'": "&#39;"}[c];
    });
}
function decided(label) { return label === "yes" || label === "no"; }
function answeredRe(r) { return r.relabel === "yes" || r.relabel === "no"; }
function pendingCount() {
  return st.records.filter(function (r) { return !decided(r.label); }).length;
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
  const done = st.records.filter(function (r) { return decided(r.label); }).length;
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
    if (!decided(st.records[k].label)) { idx = k; return; }
  }
  for (let k = 0; k < n; k++) {
    if (!decided(st.records[k].label)) { idx = k; return; }
  }
}
function goPrev() {
  if (mode === "re") { qpos = Math.max(0, qpos - 1); }
  else { idx = Math.max(0, idx - 1); }
  render();
}
async function answer(value) {
  const rec = currentRecord();
  if (!rec) { return; }
  try {
    const data = await postJSON("/api/answer",
      {id: rec.id, round: mode === "re" ? "re" : "first", value: value});
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
async function disputeAnswer(id, value) {
  try {
    const data = await postJSON("/api/answer",
      {id: id, round: "re", value: value, sync_label: true});
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
             (isRe ? '' : ' · 首轮标注：<b>' + badge(rec.label) + '</b>') + '</div>';
  html += '<audio id="au" preload="auto" loop src="/clips/' +
          encodeURIComponent(rec.id) + '.wav"></audio>';
  html += '<div><button class="b-main" id="btnPlay">▶ 播放（默认循环）</button>' +
          '<button id="btnRestart">重听</button>' +
          ((isRe ? qpos : idx) > 0
            ? '<button id="btnPrev">← 上一条（回退改判）</button>' : '') + '</div>';
  html += '<div id="answerBtns">' +
          '<button class="b-yes" data-v="yes">✅ 有对话</button>' +
          '<button class="b-no" data-v="no">❌ 无对话</button>' +
          (isRe ? '' : '<button class="b-skip" data-v="skip">⏭ 稍后再听</button>') +
          '</div>';
  html += '<p class="hint">' +
          (isRe ? '复标轮不显示首轮答案，请凭听感独立判断（只认「有对话 / 无对话」）。'
                : '作答后自动跳下一条；判错了可回退改判。') + '</p>';
  el("main").innerHTML = html;
  el("btnPlay").onclick = function () {
    const a = el("au"); a.loop = true; a.play();
  };
  el("btnRestart").onclick = function () {
    const a = el("au"); a.currentTime = 0; a.play();
  };
  if (el("btnPrev")) { el("btnPrev").onclick = goPrev; }
  el("main").querySelectorAll("#answerBtns button").forEach(function (b) {
    b.onclick = function () { answer(b.dataset.v); };
  });
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
    html += '<div class="warn">复标队列还没有作答记录（复标轮只认「有对话 / 无对话」）。</div>';
  } else {
    const ok = a.pct >= 90;
    html += '<div class="' + (ok ? 'ok' : 'warn') + '">复标一致率：' + a.agree +
            ' / ' + a.total + ' = <b>' + a.pct.toFixed(2) + '%</b>（门槛 90%）<br>' +
            (ok ? '✅ 已达标：可双击标注包内的「一键回放.bat」生成回放报告。'
                : '⚠️ 未达标：请逐条重听下面的争议条目并改判（改判同步写回首轮标注）。') +
            '</div>';
    if (!ok && a.disputed.length) {
      html += '<p class="hint">争议条目 ' + a.disputed.length + ' 条：</p>';
      a.disputed.forEach(function (id) {
        const rec = st.records.find(function (r) { return r.id === id; });
        html += '<div class="disputed"><b>' + esc(id) + '</b> · ' +
                esc(rec ? rec.timing : '') +
                '<div><audio controls loop src="/clips/' +
                encodeURIComponent(id) + '.wav"></audio></div>' +
                '<button class="b-yes" data-id="' + esc(id) +
                '" data-v="yes">✅ 有对话</button>' +
                '<button class="b-no" data-id="' + esc(id) +
                '" data-v="no">❌ 无对话</button></div>';
      });
    }
  }
  html += '<div><button class="b-main" id="btnBack">返回首轮（回退改判）</button></div>';
  el("main").innerHTML = html;
  el("btnBack").onclick = function () { mode = "first"; idx = 0; render(); };
  el("main").querySelectorAll("button[data-id]").forEach(function (b) {
    b.onclick = function () { disputeAnswer(b.dataset.id, b.dataset.v); };
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
        records.append({"id": sid, "run": str(s.get("run") or ""),
                        "wav": str(wav), "media": str(s.get("media_path") or ""),
                        "guide": str(s.get("guide_path") or ""),
                        "timing": str(s.get("timing") or ""),
                        "label": None, "relabel": None})
    if failures:
        print("❌ 切片失败（已中止，未写 state.json）：")
        for line in failures:
            print(f"   - {line}")
        print(f"共 {len(failures)} 处失败，请检查媒体与 timing 后重跑 --prepare")
        return 1

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
        if value not in _ALL_VALUES:
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
                record["label"] = value
            else:
                record["relabel"] = value
                if payload.get("sync_label"):
                    # 争议改判同步写回首轮 label（合并产物取首轮真值）
                    record["label"] = value
            _atomic_write_json(self._package / _STATE_NAME, state)
        _send_json(self, {"ok": True, "state": state})

    def _handle_relabel_start(self) -> None:
        with self.server.state_lock:
            state = _read_state(self._package)
            if state is None:
                _send_json(self, {"error": "state.json 缺失或损坏：请先执行 --prepare"}, 404)
                return
            decided = [r for r in (state.get("records") or [])
                       if r.get("label") in _DECIDED]
            if not decided:
                _send_json(self, {"error": "首轮尚无已决条目，无法进入复标"}, 400)
                return
            count = _ceil_20_percent(len(decided))
            queue = [str(r.get("id")) for r in random.sample(decided, count)]
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
            "labels": [r.get("label") == "yes" for r in rows],
        })
    _atomic_write_json(package / "c22_manifest_labeled.json", manifest)

    manifest_path = package / "c22_manifest_labeled.json"
    report_path = package / "c22_report.md"
    bat_body = (f'"{_python_exe()}" '
                f'"{_PROJECT_ROOT / "tools" / "c22_calibration.py"}" '
                f'--manifest "{manifest_path}" --out "{report_path}" --enable')
    _atomic_write_text(package / "一键回放.bat", _bat([], bat_body))

    yes = sum(1 for r in records if r.get("label") == "yes")
    no = sum(1 for r in records if r.get("label") == "no")
    agreement = _agreement(state)
    print(f"✅ 合并完成：{len(manifest)} 组（按 guide+media 分组）/ "
          f"{len(records)} 条间隙 → {manifest_path}")
    print(f"   标注分布：true（有对话）= {yes}，false（无对话）= {no}")
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
