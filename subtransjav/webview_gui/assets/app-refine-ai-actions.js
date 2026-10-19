  function aiBtnState(btn, statusText) {
    if (statusText) {
      btn.textContent = statusText;
      btn.disabled = true;
      btn.title = '';   // P3/G6：清掉失败重试残留的错误透因 title（终态不背旧错）
    } else {
      btn.disabled = false;
    }
  }

  // 落库失败反馈：按钮转「重试」态 + 行内（aiStatus）显示错误摘要，
  // 不再静默恢复；成功路径不受影响。
  // P3（D2026-1008-02，G6）：桥返回的真实原因同步拼进按钮 title
  //（悬停可读），杜绝只有笼统「重试」；重试能力保留（按钮未禁用）。
  function aiApplyFail(btn, err) {
    const m = (err && err.message) ? err.message : String(err || MSG.unknown);
    btn.textContent = MSG.aiApplyRetry;
    btn.title = m;
    btn.disabled = false;
    aiStatus(MSG.aiApplyFailed(m), true);
  }

  async function aiApplyGlossary(idx, btn) {
    const entry = (((lastAiSuggestions || {}).suggestions || {}).glossary
      || [])[idx];
    if (!entry || !window.pywebview || !window.pywebview.api) return;
    btn.disabled = true;
    try {
      const r = await window.pywebview.api.refine_ai_apply_glossary(
        JSON.stringify([{ src: entry.src, target: entry.target,
                          aliases: entry.aliases || [] }]));
      if (r && r.success === false) {
        aiApplyFail(btn, r.error || MSG.unknown);
        return;
      }
      const st = ((r && r.results && r.results[0]) || {}).status || '';
      aiBtnState(btn,
        st === 'added' ? MSG.aiApplied
          : st === 'exists' ? MSG.aiExists
            : st === 'exists_diff' ? MSG.aiExistsDiff
              : st === 'locked' ? MSG.aiLocked : '');
      if (st === 'added' && typeof glLoad === 'function') glLoad();
    } catch (e) {
      aiApplyFail(btn, e);
    }
  }

  async function aiApplyTm(idx, btn) {
    const entry = (((lastAiSuggestions || {}).suggestions || {}).tm
      || [])[idx];
    if (!entry || !window.pywebview || !window.pywebview.api) return;
    btn.disabled = true;
    try {
      const r = await window.pywebview.api.refine_ai_apply_tm(
        JSON.stringify([{ source: entry.source, target: entry.target }]));
      if (r && r.success === false) {
        aiApplyFail(btn, r.error || MSG.unknown);
        return;
      }
      const st = ((r && r.results && r.results[0]) || {}).status || '';
      // P3（D2026-1008-02，C20）：经编辑的条目存入成功反馈「编辑后译文」
      //（对原始值判定），杜绝「以为存的是 AI 原文」；exists 分支文案不变
      aiBtnState(btn,
        st === 'added'
          ? (tmOriginalTargets.has(idx)
             && entry.target !== tmOriginalTargets.get(idx)
            ? MSG.aiTmStoredEdited : MSG.aiTmStored)
          : st === 'exists' ? MSG.aiExists : '');
      // C14：已存入/已存在行行级同步禁用编辑与恢复（aiBtnState 只作用
      // 于传入单按钮，须 closest('tr') 定位）
      const row = btn.closest('tr');
      if (row) {
        row.querySelectorAll('button[data-ai-act]')
          .forEach(b => { b.disabled = true; });
      }
    } catch (e) {
      aiApplyFail(btn, e);
    }
  }

  // ---- P3（D2026-1008-02）：TM 建议编辑后存入 ----

  // 定向 DOM 更新（C13）：只替换该行拟型译文 span 的文本，禁止整表
  // 重渲染——其他行「已存入✓/已存在/重试」按钮态与原文格 ⚠️ 徽标原样
  // 保留（原文只读，徽标无被抹风险）
  function aiUpdateTmTarget(idx, text) {
    const box = $('refineAiResult');
    if (!box) return;
    const span = box.querySelector('span[data-ai-tgt="' + idx + '"]');
    if (span) span.textContent = text;
  }

  // 行内「编辑」入口：弹 AppModal.tmEdit（C15 另立方法）；保存回调
  // 同时改内存与 DOM（C16：仅改 DOM 会在修复复验重建重渲染时回退旧值）
  function aiEditTm(idx) {
    const entry = (((lastAiSuggestions || {}).suggestions || {}).tm
      || [])[idx];
    if (!entry) return;
    AppModal.tmEdit({
      entry: entry,
      onSaved: (next) => {
        entry.target = next;               // C16：内存先行
        aiUpdateTmTarget(idx, next);       // C13：定向更新该行 span
        const resBtn = document.querySelector(
          '#refineAiResult button[data-ai-act="restore"][data-ai-idx="'
          + idx + '"]');
        // 恢复入口只在当前≠原始时可用（改回原值即再禁用）
        if (resBtn) {
          resBtn.disabled = tmOriginalTargets.has(idx)
            && next === tmOriginalTargets.get(idx);
        }
      },
    });
  }

  // 行内「恢复原建议」（C19）：内存回原始值+定向 DOM 恢复+禁用自身；
  // 原始值随 lastAiSuggestions 重置/换渲染源而重置（旁路内存 Map，
  // 不写伴生 JSON、不序列化）
  function aiRestoreTm(idx, btn) {
    const entry = (((lastAiSuggestions || {}).suggestions || {}).tm
      || [])[idx];
    if (!entry || !tmOriginalTargets.has(idx)) return;
    entry.target = tmOriginalTargets.get(idx);
    aiUpdateTmTarget(idx, entry.target);
    btn.disabled = true;
  }

