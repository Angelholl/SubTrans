  // ===== 媒体重点对照（3.2 退役批 D2026-1029-01 收敛：whisper 半边删除，
  // 仅保 crosscheck 开关回显与状态行；引擎面=CT2 单面板，见下方 ct2 段） =====
  function asrStatus(text) {
    const st = $('asrStatus');
    if (st) st.textContent = text || '';
  }

  function asrRefresh(force) {
    if (!window.pywebview || !window.pywebview.api) return;
    // force 参数保留（调用兼容；refine_asr_status 探测快照语义已随退役批
    // 删除，ct2-only 状态面恒即时返回）
    window.pywebview.api.refine_asr_status(force === true).then((r) => {
      if (!r || !r.success) {
        asrStatus((r && r.error) || MSG.unknown);
        return;
      }
      const tgl = $('asrCrosscheckToggle');
      if (tgl) tgl.checked = !!r.crosscheck_enabled;
    }).catch((e) => asrStatus(String(e)));
  }

  // ASR 卡懒刷新钩子（switchTab 首开 tab-asrdict 触发一次）
  window.__asrTabHook = () => {
    if (window.__asrTabHookDone) return;
    window.__asrTabHookDone = true;
    asrRefresh(false);
    ct2Refresh();
  };

  // ===== CT2 转写引擎面板（钉⑤解冻提案 d1028-38：api 桥三端点接线。
  // 状态/安装/模型行全 JS 态文案；安装与模型下载=后台异步操作面 1s 轮询
  // operation 至终态自动翻转；3.2 退役批起唯一引擎主位面板） =====

  function ct2Set(elId, text) {
    const el = $(elId);
    if (el) el.textContent = text || '';
  }

  function ct2ModelLine(models) {
    const m = (models && models[0]) || null;
    if (!m) return MSG.ct2ModelPendingFmt('—');
    return MSG.ct2ModelPendingFmt((m.desc || m.model) + (m.verified
      ? '｜已核验' : '｜待镜像核验（下载门未开）'));
  }

  function ct2Render(r) {
    if (!r || !r.success) {
      ct2Set('refineCt2Status', MSG.ct2FailFmt((r && r.error) || ''));
      return;
    }
    ct2Set('refineCt2Status', r.installed
      ? MSG.ct2ReadyFmt(r.certified ? '通过' : '未过', r.detail || '')
      : MSG.ct2NotInstalledFmt(r.zip_published ? '' : '（件未发布）'));
    ct2Set('refineCt2ModelStatus', ct2ModelLine(r.models));
    const op = r.operation || {};
    const busy = op.phase === 'running';
    const ib = $('refineCt2InstallBtn');
    if (ib) {
      ib.disabled = busy;
      ib.querySelector('span').textContent =
        busy && op.kind === 'install' ? MSG.ct2InstallRunning : MSG.ct2InstallBtn;
    }
    const db = $('refineCt2ModelBtn');
    if (db) {
      db.disabled = busy;
      db.querySelector('span').textContent =
        busy && op.kind === 'model' ? MSG.ct2ModelDownloading : MSG.ct2ModelBtn;
    }
    if (busy) {
      setTimeout(ct2Poll, 1000);          // 后台操作面 1s 轮询至终态
    } else if (op.phase === 'failed') {
      ct2Set('refineCt2Status', MSG.ct2OpFailFmt(op.kind === 'model'
        ? '模型下载' : '安装', op.rc));
    }
  }

  function ct2Poll() {
    window.pywebview.api.refine_ct2_status().then(ct2Render)
      .catch((e) => ct2Set('refineCt2Status', MSG.ct2FailFmt(String(e))));
  }

  function ct2Refresh() {
    if (!window.pywebview || !window.pywebview.api) return;
    ct2Poll();
  }

  function ct2Install() {
    if (!window.pywebview || !window.pywebview.api) return;
    ct2Set('refineCt2Status', MSG.ct2InstallRunning);
    window.pywebview.api.refine_ct2_install('auto').then((r) => {
      if (r && r.started === false) ct2Set('refineCt2Status', r.reason || '');
      setTimeout(ct2Poll, 500);
    }).catch((e) => ct2Set('refineCt2Status', MSG.ct2FailFmt(String(e))));
  }

  function ct2ModelDownload() {
    if (!window.pywebview || !window.pywebview.api) return;
    ct2Set('refineCt2ModelStatus', MSG.ct2ModelDownloading);
    window.pywebview.api.refine_ct2_model_download('large-v2').then((r) => {
      if (r && r.started === false) ct2Set('refineCt2ModelStatus', r.reason || '');
      setTimeout(ct2Poll, 500);
    }).catch((e) => ct2Set('refineCt2Status', MSG.ct2FailFmt(String(e))));
  }

  (() => {
    const ib = $('refineCt2InstallBtn');
    if (ib) ib.addEventListener('click', ct2Install);
    const db = $('refineCt2ModelBtn');
    if (db) db.addEventListener('click', ct2ModelDownload);
  })();
