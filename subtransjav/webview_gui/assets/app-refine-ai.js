  // ============================================================
  // AI 质量分析（D2026-0929：--ai-analyze 前后端接入）
  // ============================================================

  // 与 refreshServiceQuickRow / saveStageEndpoints 同源的云服务商口径
  const AI_CLOUD_PROVIDERS = ['deepseek', 'siliconflow', 'custom', 'zen'];

  function isAiCloudProvider(prov) {
    return AI_CLOUD_PROVIDERS.includes(String(prov || '').toLowerCase());
  }

  // P1-9 格5（D2026-1015-05）：失败色锚——照 guideStatus 单点先例补
  // isError 分支（style.css 既有 .status-err 规则，零新样式）；失败加类，
  // 成功/中性清类。前置守卫类提示（需先加载导读）沿用 guideStatus 先例
  // 不标红，只有真实失败/异常（api 未就绪、aiFailed、落库失败）传 true。
  function aiStatus(text, isError) {
    const st = $('refineAiAnalyzeStatus');
    if (!st) return;
    st.textContent = text || '';
    st.classList.toggle('status-err', !!isError);
  }

  function aiReportPath() {
    // 双格式联动：用户显式加载的报告 txt 优先（stem 即用户自选报告），
    // 缺省仍按导读 json stem 推导（向后兼容）
    if (lastLoadedIsTxt) return lastLoadedReportTxtPath;
    const gp = lastLoadedGuidePath || guidePath();
    if (!gp) return '';
    return gp.replace(/_质量报告导读\.json$/, '_质量报告.txt');
  }

  function aiActionBtn(kind, idx, label) {
    return '<button type="button" class="btn btn-secondary btn-compact btn-sm"'
      + ' data-ai-kind="' + kind + '" data-ai-idx="' + idx + '">'
      + esc(label) + '</button>';
  }

  function aiConflictBadge() {
    return ' <span class="pill pill-warning" title="' + esc(MSG.aiConflictWarn)
      + '" style="cursor:help;">⚠️</span>';
  }

  // P3（D2026-1008-02）：TM 行编辑/恢复小按钮（C12：独立 data-ai-act
  // 标记，与 data-ai-kind 选择器不相交——点编辑绝不可误触 aiApplyTm
  // 存入链；恢复钮渲染时当前值恒等于原始值，初始禁用，编辑保存后启用）
  function aiEditBtn(idx, label) {
    return '<button type="button" class="btn btn-secondary btn-compact btn-sm"'
      + ' data-ai-act="edit" data-ai-idx="' + idx + '">'
      + esc(label) + '</button>';
  }

  function aiRestoreBtn(idx, label) {
    return '<button type="button" class="btn btn-secondary btn-compact btn-sm"'
      + ' data-ai-act="restore" data-ai-idx="' + idx + '" disabled'
      + ' title="' + esc(label) + '">↺</button>';
  }

  // D2026-1010-03 件B：TM 建议→导读条目定位解析。双路径（结构化 index
  // 优先；回捞 reason 文本中 #N 条目号），双校验（条目存在于已加载导读
  // + 原文词条与条目内容可互证，防模型张冠李戴的静默错误）；任一不过
  // 返回 null（前端降级无按钮）。导读未加载恒 null。
  function tmResolveEntry(t) {
    const items = (lastGuideData && Array.isArray(lastGuideData.items))
      ? lastGuideData.items : [];
    if (!items.length) return null;
    const idxCands = [];
    if (Number.isFinite(Number(t && t.index))) idxCands.push(Number(t.index));
    const re = /#(\d+)/g;
    const rs = String((t && t.reason) || '');
    let m;
    while ((m = re.exec(rs)) !== null) idxCands.push(Number(m[1]));
    const srcCore = String((t && t.source) || '').replace(/\s+/g, '');
    if (!srcCore) return null;
    for (const idx of idxCands) {
      if (!Number.isFinite(idx)) continue;
      const entry = items.find((it) => it && Number(it.index) === idx);
      if (!entry) continue;
      const hayCore = (String(entry.source_excerpt || '')
        + String(entry.current_text || '')).replace(/\s+/g, '');
      if (!hayCore) continue;
      if (hayCore.indexOf(srcCore) === -1
        && srcCore.indexOf(hayCore) === -1) continue;
      const timing = String(entry.timing || '');
      return { entry, timing: timing.includes('-->') ? timing : '' };
    }
    return null;
  }

  function aiRenderResult(r) {
    const box = $('refineAiResult');
    if (!box) return;
    const sug = (r && r.suggestions) || {};
    // parse_ok=False → 整体降级为纯文本观察，不渲染任何可执行按钮
    if (!r.parse_ok) {
      box.innerHTML = '<h4>' + esc(MSG.aiParseFailed) + '</h4><ul>'
        + (sug.observations || []).map(o => '<li>' + esc(o) + '</li>').join('')
        + '</ul>';
      return;
    }
    const parts = [];
    // 一段：术语建议
    parts.push('<h4>' + esc(MSG.aiSectionGlossary) + '</h4>');
    parts.push('<table class="gl-table">'
      + '<thead><tr><th>' + esc(MSG.th_source)
      + '</th><th>' + esc(MSG.th_target)
      + '</th><th>' + esc(MSG.aiThReason)
      + '</th><th></th></tr></thead><tbody>');
    (sug.glossary || []).forEach((g, i) => {
      parts.push('<tr><td>' + esc(g.src) + '</td><td>' + esc(g.target)
        + '</td><td>' + esc(g.reason || '') + '</td><td>'
        + aiActionBtn('glossary', i, MSG.aiApplyGlossary) + '</td></tr>');
    });
    parts.push('</tbody></table>');
    // 二段：TM 建议（conflict_warn 行加黄色 ⚠️ 徽标）
    // P3（D2026-1008-02，C19）：渲染源更换（新对象）时重置原始建议
    // Map——修复复验重建随内存重置属预期；同对象重渲染不覆盖已编辑值
    if (tmOriginalSeed !== r) {
      tmOriginalSeed = r;
      tmOriginalTargets = new Map();
      (sug.tm || []).forEach((t, i) => tmOriginalTargets.set(i, t.target));
    }
    parts.push('<h4>' + esc(MSG.aiSectionTm) + '</h4>');
    parts.push('<table class="gl-table">'
      + '<thead><tr><th>' + esc(MSG.th_source)
      + '</th><th>' + esc(MSG.th_target)
      + '</th><th>' + esc(MSG.aiThReason)
      + '</th><th></th></tr></thead><tbody>');
    (sug.tm || []).forEach((t, i) => {
      // 拟型译文包专用 span（C13）：定向更新只动该 span，原文格 ⚠️
      // 徽标与其他行按钮态不受牵连（保存后禁止整表重渲染）
      // D2026-1010-03 件B：定位解析通过才出「试听/查看条目」，否则无
      // 按钮（旧建议件/校验不过/导读未加载降级，不误导）
      const loc = tmResolveEntry(t);
      let locateBtns = '';
      if (loc) {
        if (loc.timing && lastLoadedGuidePath) {
          locateBtns += '<button type="button" class="btn btn-ghost btn-sm'
            + ' tm-preview-btn" data-timing="' + esc(loc.timing) + '">'
            + esc(MSG.preview_play_btn) + '</button>';
        } else {
          locateBtns += '<button type="button" class="btn btn-ghost btn-sm"'
            + ' disabled title="' + esc(MSG.previewNeedGuide) + '">'
            + esc(MSG.preview_play_btn) + '</button>';
        }
        locateBtns += '<button type="button" class="btn btn-ghost btn-sm'
          + ' tm-view-btn" data-idx="' + Number(loc.entry.index) + '">'
          + esc(MSG.tmViewEntry) + '</button>';
      }
      parts.push('<tr><td>' + esc(t.source) + (t.conflict_warn
        ? aiConflictBadge() : '') + '</td><td>'
        + '<span data-ai-tgt="' + i + '" data-testid="tm-sug-target">'
        + esc(t.target) + '</span>'
        + '</td><td>' + esc(t.reason || '') + '</td><td>'
        + locateBtns
        + aiActionBtn('tm', i, MSG.aiApplyTm)
        + aiEditBtn(i, MSG.aiTmEditBtn)
        + aiRestoreBtn(i, MSG.aiTmRestoreBtn) + '</td></tr>');
    });
    parts.push('</tbody></table>');
    // 三段：一般观察（纯文本，不可执行）
    parts.push('<h4>' + esc(MSG.aiSectionObs) + '</h4><ul>'
      + (sug.observations || []).map(o => '<li>' + esc(o) + '</li>').join('')
      + '</ul>');
    // 四段（D2026-1010-03 件A）：媒体对照区块——本地转写 vs 现译逐段
    // 并排 + 试听（复用现有试听链）；无段/开关关不渲染；未加载导读时
    // 试听按钮置灰提示（openAudioPreview 首行校验 lastLoadedGuidePath）
    const cc = Array.isArray(r.crosscheck_detail) ? r.crosscheck_detail : [];
    if (cc.length) {
      parts.push('<h4>' + esc(MSG.crosscheckTitle(cc.length)) + '</h4>');
      parts.push('<table class="gl-table"><thead><tr><th>'
        + esc(MSG.ccThTiming) + '</th><th>' + esc(MSG.ccThAsr)
        + '</th><th>' + esc(MSG.ccThCurrent) + '</th><th></th>'
        + '</tr></thead><tbody>');
      cc.forEach((seg) => {
        const canPreview = !!lastLoadedGuidePath;
        parts.push('<tr><td class="item-timing">' + esc(seg.timing || '')
          + '</td><td>' + esc(seg.asr_text || '') + '</td><td>'
          + esc(seg.current_text || '') + '</td><td>'
          + '<button type="button" class="btn btn-ghost btn-sm'
          + ' cc-preview-btn" data-timing="' + esc(seg.timing || '') + '"'
          + (canPreview ? '' : ' disabled title="'
            + esc(MSG.previewNeedGuide) + '"') + '>'
          + esc(MSG.preview_play_btn) + '</button></td></tr>');
      });
      parts.push('</tbody></table>');
    }
    box.innerHTML = parts.join('');
    box.querySelectorAll('button[data-ai-kind]').forEach(btn => {
      btn.addEventListener('click', () => {
        const i = Number(btn.dataset.aiIdx) || 0;
        if (btn.dataset.aiKind === 'glossary') aiApplyGlossary(i, btn);
        else aiApplyTm(i, btn);
      });
    });
    // P3（C12）：编辑/恢复分派循环独立成环（data-ai-act 与 data-ai-kind
    // 选择器不相交；该处为 per-render addEventListener 非文档级委托）
    box.querySelectorAll('button[data-ai-act]').forEach(btn => {
      btn.addEventListener('click', () => {
        const i = Number(btn.dataset.aiIdx) || 0;
        if (btn.dataset.aiAct === 'edit') aiEditTm(i);
        else aiRestoreTm(i, btn);
      });
    });
    // D2026-1010-03：媒体对照/TM 定位试听与查看条目（per-render 绑定，
    // 与上方 data-ai-* 选择器不相交）
    box.querySelectorAll('.cc-preview-btn, .tm-preview-btn').forEach(btn => {
      btn.addEventListener('click', () => openAudioPreview(btn.dataset.timing));
    });
    box.querySelectorAll('.tm-view-btn').forEach(btn => {
      btn.addEventListener('click', () =>
        openGuideItemsModal([Number(btn.dataset.idx)]));
    });
  }

  // P2（D2026-1008-02）：分析/修复模型解析单源（后端共用 helper
  // _resolve_ai_model_config 的前端镜像，C6/C7/G5-补）。语义：
  // - 独立配置全有（provider+model）→ 生效（provider=所选，model=所填）；
  // - 仅 provider（半配置）→ 视为未配置忽略（notes 记说明），回落阶段A；
  // - follow / 独立模型空 → provider=null（跟随阶段A），model=阶段A 输入
  //   （后端再落阶段A 模型/服务商默认兜底，C9）。
  // 返回 {provider, model, effProvider, notes}：provider=null=跟随阶段A
  // （桥参语义同 refine_ai_analyze）；effProvider=实际生效 provider（云端
  // 警示/展示判定用）；notes=人话注记（预览/确认框拼入）。
  function analyzeResolution() {
    const indep = (($('aiProviderSel') || {}).value || 'follow');
    const indepModel = (($('aiModelInput') || {}).value || '').trim();
    const s1p = (($('refineS1Provider') || {}).value || '').toLowerCase();
    const s1m = (($('refineS1Model') || {}).value || '').trim();
    if (indep !== 'follow' && indepModel) {
      return { provider: indep, model: indepModel,
               effProvider: indep, notes: [] };
    }
    const notes = [];
    if (indep !== 'follow') notes.push(MSG.aiIndepHalfIgnored);
    return { provider: null, model: s1m, effProvider: s1p, notes: notes };
  }

  // ============================================================
  // P1 分析模型预热（D2026-1008-02 批3，G1 落 (c) 阻断形态）
  // ============================================================
  // 触发守卫（顺序固定，静态钉）：全链开启短路（C-1，3.0 批1 a 段）→
  // 桥就绪 → 非翻译运行中 → 页面有报告（导读或报告全文）→ 模型解析非空
  // → 生效 provider 为本地 → 高频抑制。
  // 后端桥内另有单飞+C4 在载探活+G3 指纹三层去重（前端 5s 抑制仅兜高频）。
  // C21：预热结果只进 Console/状态文案与 warmup 桥状态——不碰分析按钮
  //（refineAiAnalyzeBtn）可用性、不跳过分析时真实 ensure。
  let __warmupInflight = false;

  function warmupMaybeStart() {
    try {
      // C-1（D2026-1009-02 C5 复议三条件）：全链开启时前端预热短路——
      // 预热由后端全链状态机链首环承接（后端同一 KV fullchain_auto_enabled
      // 门控，钩子整体改道状态机）；两触发点①②均经本函数，一处守卫全覆盖
      if (AppState.fullchainAutoEnabled) return;
      if (!window.pywebview || !window.pywebview.api) return;
      if (AppState.isRunning) return;                     // 翻译运行中跳过
      // 页面无报告不预热（触发点②前置条件；触发点①完成时报告已可加载）
      if (!lastLoadedGuidePath && !lastLoadedReportTxtPath) return;
      const res = analyzeResolution();
      if (!res || !res.model || !String(res.model).trim()) return;
      const eff = String(res.effProvider || '').toLowerCase();
      if (AI_CLOUD_PROVIDERS.includes(eff)) return;       // 云 provider 不预热
      if (__warmupInflight) return;                       // 5s 高频抑制
      __warmupInflight = true;
      setTimeout(() => { __warmupInflight = false; }, 5000);
      ConsoleManager.log(MSG.warmupStarted, 'info');
      Promise.resolve(window.pywebview.api.refine_warmup_analysis_model(
        res.model, res.provider))
        .then(r => {
          if (r && r.already_hot) {
            ConsoleManager.log(MSG.warmupHot, 'info');
          }
        })
        .catch(() => { /* 预热失败静默：C21 不推导分析可用性 */ });
    } catch (e) { console.warn('warmupMaybeStart failed:', e); }
  }
  // 触发点①（TranslatorManager completed 分支）经全局别名调用
  window.__warmupMaybeStart = warmupMaybeStart;
  // 触发点②（switchTab tab-guide）：姿势钩子（照 __asrTabHook；每次切入
  // 都触发，去重靠上方守卫+5s 抑制+后端桥三层）
  window.__warmupTabHook = () => { warmupMaybeStart(); };

