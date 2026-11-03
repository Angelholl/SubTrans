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

  function ct2GpuLine(gp) {
    if (!gp) return MSG.ct2GpuUnknown;
    if (!gp.cuda_visible) return MSG.ct2GpuNoCuda;      // 无 GPU 零打扰
    if (gp.complete) return MSG.ct2GpuReadyFmt(gp.dll_dir || '');
    if (gp.installed) return MSG.ct2GpuIncompleteFmt(
      (gp.missing || []).length);
    if (!gp.online_pin_ready) return MSG.ct2GpuUnpublished;
    return MSG.ct2GpuOfferFmt;
  }

  // 落位来源标签映射（d1103 D2026-1103-04 起运行时/模型两行共用；经映射
  // 防暗合，未知值原样透出便于诊断）
  function ct2SourceLabel(source) {
    const labels = {
      default: MSG.ct2RuntimeSourceDefault,
      settings: MSG.ct2RuntimeSourceSettings,
      env: MSG.ct2RuntimeSourceEnv,
      legacy: MSG.ct2RuntimeSourceLegacy,
    };
    return labels[source] || source || '';
  }

  function ct2SizeGiB(bytes) {
    if (!bytes) return '—';
    return (bytes / 1073741824).toFixed(1) + ' GB';
  }

  // 转写引擎落位行（d1103 D2026-1103-03）：落位路径＋来源标签（默认/自定义/
  // 环境变量/旧位置）＋该位是否已有运行时
  function ct2RuntimeLine(rt) {
    if (!rt || !rt.dir) return MSG.ct2RuntimeUnknown;
    const tail = rt.has_runtime ? '' : '｜' + MSG.ct2RuntimeNoRuntime;
    return MSG.ct2RuntimeFmt(rt.dir, ct2SourceLabel(rt.source)) + tail;
  }

  // 模型落位行（d1103 D2026-1103-04）：路径＋来源＋该位有无模型与体量。
  // 体量必须显——模型约 2.9 GB，误切到空目录只看到路径判不出会重下大件
  function ct2ModelDirLine(mr, present, bytes) {
    if (!mr || !mr.dir) return MSG.ct2ModelDirUnknown;
    const tail = present ? '｜' + MSG.ct2ModelDirHasFmt(ct2SizeGiB(bytes))
      : '｜' + MSG.ct2ModelDirNoModel;
    return MSG.ct2ModelDirFmt(mr.dir, ct2SourceLabel(mr.source)) + tail;
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
    const gp = r.gpu_patch || null;
    ct2Set('refineCt2GpuStatus', ct2GpuLine(gp));
    const gb = $('refineCt2GpuBtn');
    if (gb) {
      const offer = !!gp && gp.cuda_visible && !gp.complete;
      gb.disabled = busy || !offer || !gp.online_pin_ready;
      gb.querySelector('span').textContent =
        busy && op.kind === 'gpu' ? MSG.ct2GpuInstalling : MSG.ct2GpuBtn;
    }
    // 落位行：在飞操作禁切换（线程按旧根写入而 UI 按新根显示）；
    // 「恢复默认」仅在有自定义值时可点
    const rt = r.runtime || {};
    ct2Set('refineCt2RuntimeStatus', ct2RuntimeLine(rt));
    const rpb = $('refineCt2RuntimePickBtn');
    if (rpb) {
      rpb.disabled = busy;
      rpb.querySelector('span').textContent = MSG.ct2RuntimePickBtn;
    }
    const rrb = $('refineCt2RuntimeResetBtn');
    if (rrb) {
      rrb.disabled = busy || rt.source !== 'settings';
      rrb.querySelector('span').textContent = MSG.ct2RuntimeResetBtn;
    }
    // 模型落位行（D2026-1103-04）：同守卫——在飞禁切、仅自定义态可恢复默认
    const mr = r.model_runtime || {};
    ct2Set('refineCt2ModelDirStatus',
      ct2ModelDirLine(mr, !!r.model_present, r.model_bytes || 0));
    const mpb = $('refineCt2ModelDirPickBtn');
    if (mpb) {
      mpb.disabled = busy;
      mpb.querySelector('span').textContent = MSG.ct2ModelDirPickBtn;
    }
    const mrb = $('refineCt2ModelDirResetBtn');
    if (mrb) {
      mrb.disabled = busy || mr.source !== 'settings';
      mrb.querySelector('span').textContent = MSG.ct2ModelDirResetBtn;
    }
    if (busy) {
      setTimeout(ct2Poll, 1000);          // 后台操作面 1s 轮询至终态
    } else if (op.phase === 'failed') {
      const kindName = op.kind === 'model' ? '模型下载'
        : op.kind === 'gpu' ? 'GPU 补丁包' : '安装';
      ct2Set('refineCt2Status', MSG.ct2OpFailFmt(kindName, op.rc));
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

  function ct2GpuInstall() {
    if (!window.pywebview || !window.pywebview.api) return;
    ct2Set('refineCt2GpuStatus', MSG.ct2GpuInstalling);
    window.pywebview.api.refine_ct2_gpu_install().then((r) => {
      if (r && r.started === false) ct2Set('refineCt2GpuStatus', r.reason || '');
      setTimeout(ct2Poll, 500);
    }).catch((e) => ct2Set('refineCt2GpuStatus', MSG.ct2FailFmt(String(e))));
  }

  // 落位自定义（d1103 D2026-1103-03）：目录选择复用既有 refine_pick_folder
  // （取消/失败静默），写侧走 refine_ct2_runtime_dir_set（空串=恢复默认）。
  // 落位即时生效不需重启，故不套数据根面板的 AppModal 重启提示。
  // B1（D2026-1104-01）：写侧带文件搬迁；弹「一并迁移/只迁当前」双向询问
  // （preview 失败降级直调，弹窗是增强不阻断基础功能）。
  async function ct2MigrateAsk(kind, path) {
    // kind="runtime"/"model"；返回 also 连带布尔。preview 不可得→false（降级）
    try {
      const pv = await window.pywebview.api.refine_ct2_migrate_preview(
        path, kind);
      if (!pv || !pv.success) { return false; }
      const kName = kind === 'runtime' ? MSG.ct2MigrateKindRuntime
        : MSG.ct2MigrateKindModel;
      const lines = [];
      if (pv.cur && pv.cur.has_files) {
        lines.push(MSG.ct2MigrateCurLineFmt(
          kName, pv.cur.size_gb, pv.cur.dst));
        if (!pv.cur.same_volume) {
          lines.push(MSG.ct2MigrateCrossNote);
        }
      } else {
        lines.push(MSG.ct2MigrateCurLineNoFilesFmt(kName, pv.cur.dst));
      }
      let link = false;
      if (pv.link) {
        const lName = pv.link.link_kind === 'runtime'
          ? MSG.ct2MigrateKindRuntime : MSG.ct2MigrateKindModel;
        if (pv.link.has_files) {
          lines.push(MSG.ct2MigrateLinkLineFmt(
            lName, pv.link.size_gb, pv.link.target));
          if (!pv.link.same_volume) {
            lines.push(MSG.ct2MigrateCrossNote);
          }
        } else {
          lines.push(MSG.ct2MigrateLinkLineNoFilesFmt(
            lName, pv.link.target));
        }
        link = await AppModal.confirm(
          MSG.ct2MigrateTitleFmt(kName), lines.join('\n'),
          { okText: MSG.ct2MigrateOkBoth, cancelText: MSG.ct2MigrateOkCur });
      }
      return link;
    } catch (e) {
      return false;   // 预览失败降级：不弹窗、只迁当前（基础功能不阻断）
    }
  }

  async function ct2RuntimePick() {
    if (!window.pywebview || !window.pywebview.api) return;
    try {
      const p = await window.pywebview.api.refine_pick_folder();
      if (!p || !p.success || !p.path) return;
      const also = await ct2MigrateAsk('runtime', p.path);
      const r = await window.pywebview.api.refine_ct2_runtime_dir_set(
        p.path, also);
      // 成功才回轮询刷新；被拒时不得轮询——否则拒绝文案 300ms 即被状态行
      // 重绘冲掉，用户看不见（黑盒 pick-rejected 态实证，D2026-1103-04）
      if (r && r.success) {
        ct2Set('refineCt2RuntimeStatus', MSG.ct2RuntimeSavedFmt(r.runtime_dir));
        if (r.link_error) {
          ct2Set('refineCt2RuntimeStatus',
                 MSG.ct2RuntimeSavedFmt(r.runtime_dir)
                 + ' ' + MSG.ct2MigrateLinkFailedFmt(r.link_error));
        }
        setTimeout(ct2Poll, 300);
      } else {
        ct2Set('refineCt2RuntimeStatus', (r && r.error) || '');
      }
    } catch (e) {
      ct2Set('refineCt2RuntimeStatus', MSG.ct2FailFmt(String(e)));
    }
  }

  async function ct2RuntimeReset() {
    if (!window.pywebview || !window.pywebview.api) return;
    try {
      const also = await ct2MigrateAsk('runtime', '');
      const r = await window.pywebview.api.refine_ct2_runtime_dir_set('', also);
      if (r && r.success) {
        let text = MSG.ct2RuntimeResetDone;
        if (r.link_error) { text += ' ' + MSG.ct2MigrateLinkFailedFmt(r.link_error); }
        ct2Set('refineCt2RuntimeStatus', text);
        setTimeout(ct2Poll, 300);
      } else {
        ct2Set('refineCt2RuntimeStatus', (r && r.error) || '');
      }
    } catch (e) {
      ct2Set('refineCt2RuntimeStatus', MSG.ct2FailFmt(String(e)));
    }
  }

  // 模型落位自定义（d1103 D2026-1103-04）：与引擎落位同形态但独立一键，
  // 桥面 refine_ct2_model_dir_set（空串=恢复默认），守卫在后端共用面；
  // B1：同带文件搬迁＋「一并迁移/只迁当前」双向询问（对称 which="model"）
  async function ct2ModelDirPick() {
    if (!window.pywebview || !window.pywebview.api) return;
    try {
      const p = await window.pywebview.api.refine_pick_folder();
      if (!p || !p.success || !p.path) return;
      const also = await ct2MigrateAsk('model', p.path);
      const r = await window.pywebview.api.refine_ct2_model_dir_set(
        p.path, also);
      if (r && r.success) {
        let text = MSG.ct2ModelDirSavedFmt(r.model_dir);
        if (r.link_error) {
          text += ' ' + MSG.ct2MigrateLinkFailedFmt(r.link_error);
        }
        ct2Set('refineCt2ModelDirStatus', text);
        setTimeout(ct2Poll, 300);
      } else {
        ct2Set('refineCt2ModelDirStatus', (r && r.error) || '');
      }
    } catch (e) {
      ct2Set('refineCt2ModelDirStatus', MSG.ct2FailFmt(String(e)));
    }
  }

  async function ct2ModelDirReset() {
    if (!window.pywebview || !window.pywebview.api) return;
    try {
      const also = await ct2MigrateAsk('model', '');
      const r = await window.pywebview.api.refine_ct2_model_dir_set('', also);
      if (r && r.success) {
        let text = MSG.ct2ModelDirResetDone;
        if (r.link_error) { text += ' ' + MSG.ct2MigrateLinkFailedFmt(r.link_error); }
        ct2Set('refineCt2ModelDirStatus', text);
        setTimeout(ct2Poll, 300);
      } else {
        ct2Set('refineCt2ModelDirStatus', (r && r.error) || '');
      }
    } catch (e) {
      ct2Set('refineCt2ModelDirStatus', MSG.ct2FailFmt(String(e)));
    }
  }

  (() => {
    const ib = $('refineCt2InstallBtn');
    if (ib) ib.addEventListener('click', ct2Install);
    const db = $('refineCt2ModelBtn');
    if (db) db.addEventListener('click', ct2ModelDownload);
    const gb = $('refineCt2GpuBtn');
    if (gb) gb.addEventListener('click', ct2GpuInstall);
    const rpb = $('refineCt2RuntimePickBtn');
    if (rpb) rpb.addEventListener('click', ct2RuntimePick);
    const rrb = $('refineCt2RuntimeResetBtn');
    if (rrb) rrb.addEventListener('click', ct2RuntimeReset);
    const mpb = $('refineCt2ModelDirPickBtn');
    if (mpb) mpb.addEventListener('click', ct2ModelDirPick);
    const mrb = $('refineCt2ModelDirResetBtn');
    if (mrb) mrb.addEventListener('click', ct2ModelDirReset);
  })();
