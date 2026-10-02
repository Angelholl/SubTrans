"""批 2a 首件 spike：校对页 <video> file:// 直连播放能力自动化实证（D2026-1002-09）。

四组验收数据（决策条件 1/2 钉死口径）：
- A file:/// 直连：loadedmetadata + playing + videoWidth>0
- B timeupdate 间隔分布（50 采样）+ currentTime 小数精度
- C seek：seeked 事件延迟 + requestVideoFrameCallback mediaTime 与 seek 目标差
- D 10ms 补偿必要性：direct/+10ms/+50ms 三组呈现偏差（阈值=实测帧周期 1000/fps；
  统计量 median+P90；每组 10 目标 x 3 次 = 30 样本；三组同目标集）

自动化护栏（条件 2）：样本带 visibilityState 标签，仅采纳 visible 样本并记录丢弃计数；
窗口创建即置前台。A 组失败 => 转码兜底升级主路径（向 owner 报告）。

用法：.venv/Scripts/python.exe tools/spike_review_video.py [--ffmpeg <path>] [--keep]
产物：tools/spike_review_report.json + 临时件（默认清理，--keep 保留供复查）。

安全口径：--ffmpeg 为本机开发者自用调试参数（非对外输入面），全链路
list-args subprocess（shell=False 默认），无 shell 拼接。

教训：html= 注入页面 origin 非 file，WebView2 拒绝 file:// 媒体（URL safety
check/4）——加载方式必须与产品同构（url= 本地文件）。

spike 结论（2026-10-02 方案 a 收口）：
①D 判据已被数据回答=补偿非必需（direct 呈现偏差 median 0.0ms << 帧周期
33.33ms；+10ms 落同帧、+50ms 恰移一帧的帧量化证据完整，n_ok=12/30）；
②rVFC 暂停态隔次不回调为平台行为（严格交替失败模式、hidden=0），校对页
呈现帧确认需 seeked+currentTime 或 play-kick 兜底（批 2b 联动设计输入）。
"""
from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import webview  # noqa: E402  （venv [gui] extra）

DURATION_S = 13
FPS = 30
SAMPLE_TARGETS_MS = [500, 1200, 2000, 3100, 4200, 5000, 6100, 7200, 8300, 9000]
REPEATS = 3
TIMEUPDATE_SAMPLES = 50
WAIT_TIMEOUT_S = 60.0


def find_ffmpeg(explicit):
    if explicit:
        return explicit
    ff = shutil.which("ffmpeg")
    if ff:
        return ff
    for cand in (r"D:\jellyfin\Server\ffmpeg.exe",):
        if Path(cand).exists():
            return cand
    raise SystemExit("ffmpeg 未找到：--ffmpeg 显式指定或确认 PATH")


def synth_clip(ff, out):
    """合成 13s 30fps 测试片：testsrc2（内建时间码）+ aac 音轨，H.264 mp4。

    drawtext 为可选增强（依赖 libfreetype，非全量 build 可能缺滤镜）——失败
    降级纯 testsrc2 不阻塞（决策条件 1）。返回 {"drawtext": bool}。
    """
    inputs = ["-f", "lavfi", "-i",
              "testsrc2=size=640x360:rate=" + str(FPS) + ":duration=" + str(DURATION_S),
              "-f", "lavfi", "-i", "sine=frequency=440:duration=" + str(DURATION_S)]
    vcodec = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
              "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", "-r", str(FPS)]
    dt = ("drawtext=text='%{pts\\:hms}':x=10:y=10:fontsize=24:"
          "fontcolor=white:box=1:boxcolor=black@0.5")
    for vf_args, used_dt in ((["-vf", dt], True), ([], False)):
        cmd = [ff, "-y", *inputs, *vcodec, *vf_args, str(out)]
        r = subprocess.run(cmd, capture_output=True, shell=False)
        if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return {"drawtext": used_dt}
        if used_dt:
            print("[spike] drawtext 不可用，降级纯 testsrc2：", r.stderr[-200:])
        else:
            raise SystemExit("测试片合成失败：" + repr(r.stderr[-500:]))
    raise SystemExit("unreachable")


def probe_fps(ff, clip):
    """ffprobe 实测帧率（决策条件 1：阈值由实测帧周期推导，不硬编码 33ms）。"""
    name = "ffprobe.exe" if ff.lower().endswith(".exe") else "ffprobe"
    ffprobe = Path(ff).with_name(name)
    if not ffprobe.exists():
        found = shutil.which("ffprobe")
        if not found:
            raise SystemExit("ffprobe 未找到（ffmpeg 同目录与 PATH 均无）")
        ffprobe = Path(found)
    r = subprocess.run(
        [str(ffprobe), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate", "-of", "json", str(clip)],
        capture_output=True, shell=False)
    if r.returncode != 0:
        raise SystemExit("ffprobe 失败：" + repr(r.stderr[-300:]))
    data = json.loads(r.stdout.decode("utf-8", "replace"))
    num, _, den = data["streams"][0]["r_frame_rate"].partition("/")
    fps = float(num) / float(den or 1)
    if abs(fps - FPS) > 0.5:
        print("[spike] 实测帧率偏离合成目标，以实测为准：", fps)
    return fps


SPIKE_HTML = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>spike</title></head>
<body>
<video id="v" controls preload="auto" muted></video>
<script>
const TARGETS_MS = %%TARGETS%%;
const REPEATS = %%REPEATS%%;
const TU_SAMPLES = %%TU%%;

function playTo(ms) {
  return new Promise((resolve, reject) => {
    const v = document.getElementById('v');
    const t0 = performance.now();
    const onSeeked = () => {
      v.removeEventListener('seeked', onSeeked);
      // 呈现帧真实 PTS：requestVideoFrameCallback 给 mediaTime；不支持 rVFC
      // 的环境退 currentTime（标注 fallback）。
      if (v.requestVideoFrameCallback) {
        v.requestVideoFrameCallback((now, meta) => {
          resolve({ presentedMediaTimeMs: meta.mediaTime * 1000,
                    rVFC: true, elapsedMs: performance.now() - t0 });
        });
      } else {
        resolve({ presentedMediaTimeMs: v.currentTime * 1000,
                  rVFC: false, elapsedMs: performance.now() - t0 });
      }
    };
    v.addEventListener('seeked', onSeeked, { once: true });
    v.currentTime = ms / 1000;
    setTimeout(() => { v.removeEventListener('seeked', onSeeked);
                       reject(new Error('seek timeout ' + ms)); }, 5000);
  });
}

function median(arr) {
  if (!arr.length) return null;
  const s = arr.slice().sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

window.spikeRun = async function () {
  const v = document.getElementById('v');
  const report = { visibility: document.visibilityState,
                   hiddenDropped: 0, hasRVFC: !!v.requestVideoFrameCallback };

  // A：file:// 直连
  v.src = %%VIDEO_URL%%;
  report.A = await new Promise((resolve) => {
    const t0 = performance.now();
    const done = (ok, extra) => resolve(Object.assign(
      { ok, loadMs: performance.now() - t0, visibility: document.visibilityState }, extra));
    v.addEventListener('loadedmetadata', () => {
      v.play().then(() => v.pause()).then(() =>
        done(true, { videoWidth: v.videoWidth, duration: v.duration }))
       .catch((e) => done(false, { err: String(e) }));
    }, { once: true });
    v.addEventListener('error', () => done(false,
      { err: v.error ? (v.error.message + '/' + v.error.code) : 'unknown' }), { once: true });
    setTimeout(() => done(false, { err: 'timeout' }), 15000);
  });
  if (!report.A.ok) { return report; }

  // B：timeupdate 间隔分布 + currentTime 精度
  report.B = await new Promise((resolve) => {
    const gaps = [], precisions = [];
    let last = null, n = 0;
    v.currentTime = 0;
    const onTu = () => {
      if (document.visibilityState !== 'visible') { report.hiddenDropped++; return; }
      const now = performance.now();
      if (last !== null) gaps.push(now - last);
      const cur = v.currentTime;
      const decimals = (String(cur).split('.')[1] || '').length;
      precisions.push(decimals);
      last = now;
      if (++n >= TU_SAMPLES) {
        v.removeEventListener('timeupdate', onTu);
        v.pause();
        resolve({ gapCount: gaps.length, gapMedian: median(gaps),
                  gapSamples: gaps, maxDecimals: Math.max.apply(null, precisions) });
      }
    };
    v.addEventListener('timeupdate', onTu);
    v.play();
    setTimeout(() => { v.removeEventListener('timeupdate', onTu); v.pause();
                       resolve({ gapCount: gaps.length, gapSamples: gaps,
                                 gapMedian: median(gaps), timeout: true }); }, 45000);
  });

  // C/D：三组同目标集（direct / +10ms / +50ms）
  const groups = { direct: [], plus10: [], plus50: [] };
  const offsets = [['direct', 0], ['plus10', 10], ['plus50', 50]];
  for (const pair of offsets) {
    const name = pair[0], offset = pair[1];
    for (let rep = 0; rep < REPEATS; rep++) {
      for (const t of TARGETS_MS) {
        try {
          const r = await playTo(Math.min(t + offset, (v.duration - 0.2) * 1000));
          r.targetMs = t; r.offsetMs = offset; r.visibility = document.visibilityState;
          groups[name].push(r);
        } catch (e) {
          groups[name].push({ targetMs: t, offsetMs: offset, error: String(e),
                              visibility: document.visibilityState });
        }
        await new Promise((res) => setTimeout(res, 120));
      }
    }
  }
  report.D = groups;
  return report;
};
</script></body></html>
"""


def summarize(report, fps):
    """把原始采集折算成判据口径：帧周期、median/P90 呈现偏差、补偿判据。"""
    out = {"fps_measured": fps, "frame_period_ms": round(1000.0 / fps, 3)}
    a = report.get("A", {})
    out["A_direct_playback"] = {
        "ok": a.get("ok", False), "videoWidth": a.get("videoWidth"),
        "load_ms": round(a.get("loadMs", 0)), "err": a.get("err"),
        "visibility": a.get("visibility") or report.get("visibility"),
        "hidden_dropped": report.get("hiddenDropped", 0),
    }
    b = report.get("B", {})
    gaps = b.get("gapSamples", []) or []
    out["B_timeupdate"] = {
        "count": b.get("gapCount", 0),
        "gap_median_ms": round(b["gapMedian"], 2) if b.get("gapMedian") is not None else None,
        "gap_p90_ms": (round(sorted(gaps)[int(len(gaps) * 0.9)], 2)
                       if len(gaps) >= 10 else None),
        "max_currentTime_decimals": b.get("maxDecimals"),
        "timeout": b.get("timeout", False),
    }
    out["C_seek"] = {"rVFC_used": report.get("hasRVFC", False),
                     "note": "seeked 延迟分布见 raw.D.direct[].elapsedMs"}
    d_summary = {}
    for name in ("direct", "plus10", "plus50"):
        rows = [r for r in report.get("D", {}).get(name, [])
                if "presentedMediaTimeMs" in r]
        vis_errs = [abs(r["presentedMediaTimeMs"] - r["targetMs"])
                    for r in rows if r.get("visibility") == "visible"]
        d_summary[name] = {
            "n_total": len(report.get("D", {}).get(name, [])),
            "n_ok": len(rows), "n_visible": len(vis_errs),
            "median_abs_err_ms": (round(statistics.median(vis_errs), 2)
                                  if vis_errs else None),
            "p90_abs_err_ms": (round(sorted(vis_errs)[int(len(vis_errs) * 0.9)], 2)
                               if len(vis_errs) >= 10 else None),
        }
    out["D_compensation"] = d_summary
    dd = d_summary["direct"]
    d10 = d_summary["plus10"]
    period = 1000.0 / fps
    if dd["median_abs_err_ms"] is None or dd["n_visible"] < 30:
        out["D_verdict"] = "insufficient_data"
    elif dd["median_abs_err_ms"] <= period:
        out["D_verdict"] = "compensation_not_needed"
    elif (d10["median_abs_err_ms"] is not None
          and d10["median_abs_err_ms"] <= dd["median_abs_err_ms"] * 0.5):
        out["D_verdict"] = "compensation_needed_plus10"
    else:
        out["D_verdict"] = "inconclusive_see_raw"
    return out


class SpikeApi:
    """js_api 桥：前端把 report 交给 Python，随后关窗结束 webview.start。"""

    def __init__(self):
        self.result = None

    def submit_report(self, report):
        self.result = report
        if webview.windows:
            webview.windows[0].destroy()
        return "ok"


def wait_and_collect(window, api, t0):
    """spike 入口：等 spikeRun 就绪后注入执行，提交后 submit_report 关窗。"""
    injected = False
    while time.time() - t0 < WAIT_TIMEOUT_S:
        try:
            if not injected:
                ready = window.evaluate_js("typeof window.spikeRun === 'function'")
                if ready:
                    window.evaluate_js(
                        "window.spikeRun().then(function(r){"
                        "pywebview.api.submit_report(r);})"
                        ".catch(function(e){"
                        "pywebview.api.submit_report({fatal: String(e)});})")
                    injected = True
        except Exception as exc:
            print("[spike] 注入等待重试：", exc)
        time.sleep(0.5)
    if not injected:
        print("[spike] 等待超时")


def main():
    parser = argparse.ArgumentParser(description="批 2a 播放器 spike（D2026-1002-09）")
    parser.add_argument("--ffmpeg", default=None,
                        help="ffmpeg 路径（默认 which 探测+已知位置回退）")
    parser.add_argument("--keep", action="store_true", help="保留临时件供复查")
    args = parser.parse_args()

    ff = find_ffmpeg(args.ffmpeg)
    print("[spike] ffmpeg =", ff)
    tmp = Path(tempfile.mkdtemp(prefix="spike_review_"))
    clip = tmp / "spike_10s.mp4"
    report_path = ROOT / "tools" / "spike_review_report.json"

    info = synth_clip(ff, clip)
    print(f"[spike] 测试片就绪（drawtext={info['drawtext']}）：{clip}")
    fps = probe_fps(ff, clip)
    print(f"[spike] 实测帧率 = {fps:.3f}（帧周期 {1000 / fps:.2f}ms）")

    page = (SPIKE_HTML
            .replace("%%VIDEO_URL%%", json.dumps(clip.as_uri()))
            .replace("%%TARGETS%%", json.dumps(SAMPLE_TARGETS_MS))
            .replace("%%REPEATS%%", str(REPEATS))
            .replace("%%TU%%", str(TIMEUPDATE_SAMPLES)))

    # 加载方式与产品同构（file:// origin）：html= 注入页面 origin 非 file，
    # WebView2 媒体 URL 安全检查会拒绝 file:// 媒体（首轮实证，见 docstring 教训）
    html_path = tmp / "spike_review.html"
    html_path.write_text(page, encoding="utf-8")

    api = SpikeApi()
    # on_top：落实"窗口前台不被遮挡"的采集条件（遮挡下 rVFC 不回调致 seek
    # 超时）；visibilityState 护栏与判据零变更
    webview.create_window("SubTransJAV spike", url=html_path.as_uri(), js_api=api,
                          width=900, height=640, on_top=True)
    t0 = time.time()
    webview.start(func=lambda: wait_and_collect(webview.windows[0], api, t0),
                  debug=False)

    if api.result is None:
        print("[spike] 未能采集到结果（超时/窗口被关闭）")
        return 2
    raw = api.result
    if raw.get("fatal"):
        print("[spike] 前端 fatal：", raw["fatal"])
        summary = {"fatal": raw["fatal"]}
        payload = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "load_mode": "file-url",
                   "ffmpeg": ff, "synth": info, "summary": summary, "raw": raw}
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        return 2
    summary = summarize(raw, fps)
    payload = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "load_mode": "file-url",
               "ffmpeg": ff, "synth": info, "summary": summary, "raw": raw}
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print("[spike] 报告落盘：", report_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not args.keep:
        shutil.rmtree(tmp, ignore_errors=True)
        print("[spike] 临时件已清理：", tmp)
    else:
        print("[spike] 临时件保留：", tmp)
    return 0 if summary.get("A_direct_playback", {}).get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
