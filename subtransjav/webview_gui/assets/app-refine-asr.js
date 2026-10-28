  // ===== 2.6.0 批3（D2026-1002-04-批3）：ASR 模型管理 =====
  // 2.6.1 修订（D2026-1002-06，模型推荐制）：删内置下载链与 1s 进度轮询，
  // 改推荐清单渲染（present 徽标/大小/来源 URL/落位指引）+验证开关+上游
  // Python 路径回填（均 JS 态文案，零静态键消耗）。
  function asrStatus(text) {
    const st = $('asrStatus');
    if (st) st.textContent = text || '';
  }

  function fmtGB(bytes) {
    return Math.round(bytes / 1073741824 * 10) / 10 + 'GB';
  }

  // 2.7.1 红绿灯（D2026-1005-01 承接批件2）：三色状态点前置注入 asrEnvStatus
  // （span.status-dot.asr-dot，复用既有状态点 class，零新增 id）。
  // 🟢=available；🟡=上游通但缺模型/缺 ffmpeg（triage ok/ffmpeg-missing）；
  // 🔴=不可用（python 不可达/模块缺失/whisper 导入失败）。探测结果单一来源：
  // 红绿灯/面板/下拉共用同一 probe 对象（评议 R4，禁双份维护）。
  function asrApplyEnvStatus(r) {
    const el = $('asrEnvStatus');
    if (!el) return;
    el.textContent = '';
    const triage = (r && r.triage) || 'python-unavailable';
    let cls = 'dot-err';
    let text = MSG.asrProbeFail((r && r.reason) || '');
    if (r && r.available) {
      cls = 'dot-ok';
      text = MSG.asrProbeReady(r.whisper_version || '?',
        r.model_present ? (r.saved_model || MSG.asrModelUnselected)
          : MSG.asrProbeNoModel);
    } else if (triage === 'ok' || triage === 'ffmpeg-missing') {
      cls = 'dot-warn';
      text = MSG.asrProbeUpstreamOk;
    }
    const dot = document.createElement('span');
    dot.className = 'status-dot asr-dot ' + cls;
    el.appendChild(dot);
    el.appendChild(document.createTextNode(text));
  }

  // 2.7.1 件4：下拉来源标注（「<名>（<来源>）」，title=完整路径）
  const ASR_SOURCE_LABELS = {
    'whisper-cache': 'whisper 缓存',
    'data-root': '应用数据',
    'hf-hub': 'HF hub',
  };

  // 模型管理面板数据源（asrRefresh 回填；asrOpenModelsPanel 消费）
  let lastAsrProbe = null;

  // 2.7.1 件3：模型管理面板入口（AppModal kind='models'）。数据=最近一次
  // 探测结果（单一来源）；下载语义全量复用 asr_downloader 桥（面板行内
  // 进度，替代原 AppModal.download 源选择模态调用链）。
  function asrOpenModelsPanel() {
    if (!lastAsrProbe) {
      asrStatus(MSG.mpNeedProbe);
      return;
    }
    AppModal.models({
      probe: lastAsrProbe,
      onFinished: () => asrRefresh(true),   // 下载收尾后强制刷新（徽标/红绿灯翻转）
    });
  }

  function asrRefresh(force) {
    if (!window.pywebview || !window.pywebview.api) return;
    const env = $('asrEnvStatus');
    if (env) env.textContent = '…';
    // force=true（「重新探测」按钮/下载收尾）→ 绕过快照缓存同步重探；
    // 缺省（首开 ASR 页/后台预热）→ 优先读磁盘快照立即返回（TTL 10 分钟）。
    window.pywebview.api.refine_asr_status(force === true).then((r) => {
      if (!r || !r.success) {
        asrStatus((r && r.error) || MSG.unknown);
        return;
      }
      lastAsrProbe = r;
      asrApplyEnvStatus(r);
      const sel = $('asrModelSel');
      if (!sel) return;
      sel.innerHTML = '';
      const models = r.models || [];
      if (!models.length) {
        const o = document.createElement('option');
        o.value = '';
        o.textContent = MSG.asrSelectPlaceholder;
        sel.appendChild(o);
      }
      // 三落位合并去重结果（后端已按 whisper-cache>data-root 校验序去重，
      // 只收 whisper 系 ready 项；HF hub 条目不进下拉——需适配，走面板）
      models.forEach((m) => {
        const o = document.createElement('option');
        o.value = m.name;
        const src = ASR_SOURCE_LABELS[m.source] || '';
        o.textContent = m.name + (src ? '（' + src + '）' : '');
        o.title = m.path || '';
        sel.appendChild(o);
      });
      const saved = r.saved_model || '';
      if (saved && models.some(m => m.name === saved)) {
        sel.value = saved;
      } else {
        // 2.7.3 件③：saved 空或不在本机清单时，确保占位 option（JS 渲染）
        // 并显式归零选中——否则浏览器默认选中第一项=假选中（后端 CLI 不带
        // --asr-model 缺省 large-v2 是合法降级，UI 不得替用户显示已选）
        if (!sel.querySelector('option[value=""]')) {
          const ph = document.createElement('option');
          ph.value = '';
          ph.textContent = MSG.asrModelPlaceholder;
          sel.appendChild(ph);
        }
        sel.value = '';
      }
      const tgl = $('asrCrosscheckToggle');
      if (tgl) tgl.checked = !!r.crosscheck_enabled;
      const pyInp = $('asrPythonInput');
      if (pyInp) pyInp.value = r.saved_python || '';
    }).catch((e) => asrStatus(String(e)));
  }

  // ASR 卡懒探测钩子（switchTab 首开 tab-asrdict 触发一次；缓存秒回，
  // 强制刷新走「重新探测」按钮）
  window.__asrTabHook = () => {
    if (window.__asrTabHookDone) return;
    window.__asrTabHookDone = true;
    asrRefresh(false);
    ct2Refresh();
  };

  // ===== CT2 转写引擎面板（钉⑤解冻提案 d1028-38：api 桥三端点接线，
  // D2026-1028-03 脱钩轮待裁决项→「全部开工」令批准。状态/安装/模型行全
  // JS 态文案；安装与模型下载=后台异步操作面 1s 轮询 operation 至终态自动
  // 翻转；本批零后端改动，ct2 缺省仍默认关） =====

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

