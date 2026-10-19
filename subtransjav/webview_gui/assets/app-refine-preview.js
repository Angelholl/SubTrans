  // ============================================================
  // 试听错误槽（2.7.4 件1 owner 终版裁定）：错误展示从浮层条内迁出为
  // 独立动态槽——旧浮层内静态错误元素废弃（DOM 保留不删不写，零
  // FROZEN 解冻）。槽注入 #tab-guide 页面级稳定容器（no_guide 态——导读
  // 未加载/折叠收起——也可见，不依赖导读加载后才存在的容器）；
  // position:fixed + z-index 1001：高于浮层条 z-900 与模态遮罩 z-1000，
  // 错误态永不被遮。幂等：首帧注入后复用。
  // ============================================================
  function ensurePreviewErrorSlot() {
    let slot = document.querySelector('.preview-error-slot');
    if (slot) return slot;
    slot = document.createElement('div');
    slot.className = 'preview-error-slot';
    const ico = document.createElement('span');
    ico.className = 'preview-error-ico';
    ico.textContent = '⚠';
    const txt = document.createElement('span');
    txt.className = 'preview-error-text';
    const rematch = document.createElement('button');
    rematch.type = 'button';
    rematch.className = 'btn btn-ghost btn-compact preview-error-rematch';
    rematch.textContent = MSG.preview_rematch;
    rematch.style.display = 'none';   // 仅 err_kind=path_invalid 时出现
    rematch.addEventListener('click', () => rematchPreviewMedia());
    const pick = document.createElement('button');
    pick.type = 'button';
    pick.className = 'btn btn-ghost btn-compact preview-error-pickmedia';
    pick.textContent = MSG.preview_pick_media;
    pick.style.display = 'none';   // 仅 err_kind=no_candidate（未找到媒体）时出现
    pick.addEventListener('click', () => pickPreviewMediaManually());
    slot.appendChild(ico);
    slot.appendChild(txt);
    slot.appendChild(rematch);
    slot.appendChild(pick);
    const page = document.getElementById('tab-guide');
    (page || document.body).appendChild(slot);
    return slot;
  }

  function clearPreviewError() {
    const slot = document.querySelector('.preview-error-slot');
    if (!slot) return;
    slot.classList.remove('show');
    const txt = slot.querySelector('.preview-error-text');
    if (txt) txt.textContent = '';
    const rematch = slot.querySelector('.preview-error-rematch');
    if (rematch) rematch.style.display = 'none';
    const pick = slot.querySelector('.preview-error-pickmedia');
    if (pick) pick.style.display = 'none';
  }

  // err_kind 结构化驱动（2.7.4 件2，评议员条件①）：前端按 error_key
  // 判定、禁靠中文文案匹配——仅 path_invalid（已有路径失效）时错误槽内
  // 出现「重新自动匹配」
  function showPreviewError(text, errKind) {
    // 停播保留（评议员条件）：错误即清 src，防上一次试听的声音持续播放
    detachPreviewSeekListeners();   // 同步拆 seek/停播监听（防幽灵暂停）
    const player = $('audioPreviewPlayer');
    if (player) { player.src = ''; }
    // 失败态=浮层条隐藏 + 独立错误槽红字（浮层不再承载错误展示）
    const bar = $('audioPreviewBar');
    if (bar) {
      bar.classList.remove('bar-loading', 'bar-ready');
      bar.style.display = 'none';
    }
    const slot = ensurePreviewErrorSlot();
    const txt = slot.querySelector('.preview-error-text');
    if (txt) txt.textContent = text;
    slot.classList.add('show');
    const rematch = slot.querySelector('.preview-error-rematch');
    if (rematch) rematch.style.display = errKind === 'path_invalid' ? '' : 'none';
    // F5 直通键：仅「未找到媒体」（结构化 err_kind=no_candidate）时出现
    const pick = slot.querySelector('.preview-error-pickmedia');
    if (pick) pick.style.display = errKind === 'no_candidate' ? '' : 'none';
  }

  // 「重新自动匹配」（2.7.4 件2）：复用后端推断引擎（refine_preview_infer_media
  // 与试听同源实现，零第二份）；成功后更新媒体条横幅并自动重试本次试听
  async function rematchPreviewMedia() {
    const slot = document.querySelector('.preview-error-slot');
    const btn = slot ? slot.querySelector('.preview-error-rematch') : null;
    if (btn) btn.disabled = true;
    try {
      if (!lastLoadedGuidePath || !window.pywebview
          || !window.pywebview.api
          || !window.pywebview.api.refine_preview_infer_media) {
        return;
      }
      const r = await window.pywebview.api.refine_preview_infer_media(
        lastLoadedGuidePath);
      if (r && r.ok && r.media_path) {
        inferredMediaCache[lastLoadedGuidePath] = String(r.media_path);
        renderMediaTag('tag-auto', MSG.preview_media_matched,
          String(r.media_path));
        mediaMissingHint(false);
        clearPreviewError();
        if (lastPreviewTiming) openAudioPreview(lastPreviewTiming);
      } else {
        showPreviewError(MSG.audio_preview_failed(
          (r && r.error) || MSG.unknownError), (r && r.error_key) || '');
      }
    } catch (e) {
      showPreviewError(MSG.audio_preview_failed(
        e && e.message ? e.message : String(e)), '');
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  // 「选择媒体文件…」（F5 直通，D2026-1007-02）：试听「未找到媒体」
  // （err_kind=no_candidate）时错误槽内出现——文件对话框直选 → 持久化
  // 覆盖（refine_save_media_override，media_overrides KV，失败不阻塞会话
  // 内重试）→ 清该 guide 推断缓存（防直通后仍走旧推断）→ 自动重试上次
  // 试听（rematch 先例：lastPreviewTiming）。用户取消对话框 → 静默返回。
  async function pickPreviewMediaManually() {
    const slot = document.querySelector('.preview-error-slot');
    const btn = slot ? slot.querySelector('.preview-error-pickmedia') : null;
    if (btn) btn.disabled = true;
    try {
      if (!window.pywebview || !window.pywebview.api
          || !window.pywebview.api.refine_review_pick_media) {
        return;
      }
      const r = await window.pywebview.api.refine_review_pick_media();
      // 取消（cancelled）/桥失败 → 静默返回（保留原错误态）
      if (!r || !r.success || !r.path || !lastLoadedGuidePath) return;
      if (window.pywebview.api.refine_save_media_override) {
        try {
          await window.pywebview.api.refine_save_media_override(
            lastLoadedGuidePath, String(r.path));
        } catch (e) { /* 持久化失败不阻塞会话内重试 */ }
      }
      delete inferredMediaCache[lastLoadedGuidePath];
      renderMediaTag('tag-explicit', MSG.media_source_explicit, String(r.path));
      mediaMissingHint(false);
      clearPreviewError();
      if (lastPreviewTiming) openAudioPreview(lastPreviewTiming);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  // loading 提示行（浮层条内动态注入，幂等）：timing 右侧「正在匹配媒体
  // 路径并定位片段…」，ready 态隐藏、audio 才显示
  function ensurePreviewLoadingNote() {
    const main = document.querySelector('#audioPreviewBar .audio-preview-main');
    if (!main) return null;
    let note = main.querySelector('.preview-loading-note');
    if (!note) {
      note = document.createElement('span');
      note.className = 'preview-loading-note';
      note.textContent = MSG.preview_matching;
      const audio = main.querySelector('audio');
      if (audio) main.insertBefore(note, audio); else main.appendChild(note);
    }
    return note;
  }

  function closeAudioPreview() {
    detachPreviewSeekListeners();   // 拆 seek/停播监听（防幽灵暂停）
    const bar = $('audioPreviewBar');
    const player = $('audioPreviewPlayer');
    if (player) { player.pause(); player.src = ''; }
    if (bar) {
      bar.classList.remove('bar-loading', 'bar-ready');
      bar.style.display = 'none';
    }
    clearPreviewError();   // 同步清理错误槽（关浮层不留残红）
    lastPreviewToken++;   // 在途请求返回后作废
  }

  // 请求序号：连续点击/关闭后旧响应不得覆盖新状态
  let lastPreviewToken = 0;
  // 2.7.4 件2：最近一次试听 timing（重匹配成功后自动重试用）
  let lastPreviewTiming = '';

  // ============================================================
  // direct 分支定位与段内自动停播（质量报告导读试听定位修复）：
  // direct 整文件此前一律从 0:00 起播；改为 metadata 就绪后 seek 至
  // 片段起点前置 0.5s（与 clip 抽取 pad 对齐），自然播到片段终点后
  // 0.5s 自动暂停。程序化 seek / 用户拖拽区分（pendingSeek 标志）：
  // seeking 时为真视为程序化（seeked 落定后清标志并武装自动停播）；
  // 为假即用户拖拽，解除武装（不打断续听）。代数计数器防过期：
  // openAudioPreview 每次重入 / close / error 均拆除监听并递增代数，
  // 新增回调先校验代数、过期即返回，防快速切换条目/重匹配重试时旧
  // 回调落错时间点。
  // ============================================================
  let previewSeekGen = 0;         // 代数：每次拆装递增作废在途回调
  let previewPendingSeek = false; // seeking 时区分程序化/用户拖拽
  let previewArmStop = false;     // 武装后 timeupdate 才可自动停播
  let previewSeekHandlers = null; // 当前监听句柄（拆除/防重复挂载）

  // 拆除 direct 分支 seek/停播监听并复位标志（close/error/重入共用）
  function detachPreviewSeekListeners() {
    previewSeekGen++;   // 作废全部在途 seek/停播回调
    previewPendingSeek = false;
    previewArmStop = false;
    if (!previewSeekHandlers) return;
    const h = previewSeekHandlers;
    previewSeekHandlers = null;
    h.el.removeEventListener('loadedmetadata', h.loadedmetadata);
    h.el.removeEventListener('seeking', h.seeking);
    h.el.removeEventListener('seeked', h.seeked);
    h.el.removeEventListener('timeupdate', h.timeupdate);
  }

  // direct 分支 src 赋值后挂载（play() 时机不变：即播，seek 在
  // metadata 就绪后落点；坏文件不触发 loadedmetadata 时仅不定位，
  // 既有 error 路径与 no-src guard 不受影响）
  function attachPreviewSeekListeners(player, span) {
    const gen = previewSeekGen;   // 入口 detach 已递增，此后过期即弃
    const onLoadedMetadata = () => {
      if (gen !== previewSeekGen) return;
      previewPendingSeek = true;   // 程序化 seek：seeking 不解除武装
      player.currentTime = Math.max(0, span[0] - 0.5);
    };
    const onSeeking = () => {
      if (gen !== previewSeekGen) return;
      if (!previewPendingSeek) previewArmStop = false;   // 拖拽解除武装
    };
    const onSeeked = () => {
      if (gen !== previewSeekGen) return;
      if (!previewPendingSeek) return;
      previewPendingSeek = false;   // 程序化 seek 落定
      previewArmStop = true;        // 落定后才武装段内自动停播
    };
    const onTimeUpdate = () => {
      if (gen !== previewSeekGen || !previewArmStop) return;
      if (player.currentTime >= span[1] + 0.5) player.pause();
    };
    previewSeekHandlers = {
      el: player,
      loadedmetadata: onLoadedMetadata,
      seeking: onSeeking,
      seeked: onSeeked,
      timeupdate: onTimeUpdate
    };
    player.addEventListener('loadedmetadata', onLoadedMetadata,
      { once: true });
    player.addEventListener('seeking', onSeeking);
    player.addEventListener('seeked', onSeeked);
    player.addEventListener('timeupdate', onTimeUpdate);
  }

  async function openAudioPreview(timing) {
    const bar = $('audioPreviewBar');
    const player = $('audioPreviewPlayer');
    const timingEl = $('audioPreviewTiming');
    if (!bar || !player || !timingEl) return;
    detachPreviewSeekListeners();   // 重入拆旧监听+递增代数（防过期回调落错点）
    clearPreviewError();   // 每分支入口先清旧红字（防残留），再判断分支
    if (!lastLoadedGuidePath) {
      // no_guide：失败态（浮层不展开，错误槽红字页面级可见）
      showPreviewError(MSG.audio_preview_no_guide);
      return;
    }
    const span = timingToSeconds(timing);
    if (!span) {
      showPreviewError(MSG.audio_preview_no_timing);
      return;
    }
    ensurePreviewLoadingNote();
    // 两态浮层：点击即 loading（timing + 匹配中文案，播放器隐藏）；
    // 拿到可播放 src 才 ready 显示 audio
    timingEl.textContent = String(timing || '');
    player.src = '';
    bar.classList.remove('bar-ready');
    bar.classList.add('bar-loading');
    bar.style.display = '';
    lastPreviewTiming = String(timing || '');   // 重匹配自动重试依据
    const token = ++lastPreviewToken;
    try {
      const r = await window.pywebview.api.refine_audio_preview(
        lastLoadedGuidePath, span[0], span[1], mediaOverridePath);
      if (token !== lastPreviewToken) return;   // 过期回调不写 UI
      if (r && r.ok && r.mode === 'direct' && r.media_path) {
        bar.classList.remove('bar-loading');
        bar.classList.add('bar-ready');
        markInferredMedia(r);
        player.src = fileUrlOf(r.media_path);
        attachPreviewSeekListeners(player, span);   // 定位+段内自动停播
        player.play().catch(() => {});
      } else if (r && r.ok && r.mode === 'clip' && r.data_url) {
        bar.classList.remove('bar-loading');
        bar.classList.add('bar-ready');
        markInferredMedia(r);
        player.src = r.data_url;
        player.play().catch(() => {});
      } else {
        showPreviewError(MSG.audio_preview_failed(
          (r && r.error) || MSG.unknownError),
          (r && r.error_key) || '');
      }
    } catch (e) {
      if (token === lastPreviewToken) {
        showPreviewError(MSG.audio_preview_failed(
          e && e.message ? e.message : String(e)), '');
      }
    }
  }

  // 推断命中回显（2.7.4 件2）：media_source=inferred → 媒体条 tag-auto
  // 横幅显示匹配路径 + 写入每 guide 缓存（导读加载后缺失态即可展示）
  function markInferredMedia(r) {
    if (!r || r.media_source !== 'inferred' || !r.media_path) return;
    inferredMediaCache[lastLoadedGuidePath] = String(r.media_path);
    renderMediaTag('tag-auto', MSG.preview_media_matched,
      String(r.media_path));
    mediaMissingHint(false);
  }

