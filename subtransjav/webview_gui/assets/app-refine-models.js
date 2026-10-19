  // ---- 已存模型名（批2 D2026-1002-12 拍板点2：删 custom-model-1/2 前端
  // 硬默认，模型下拉不再有"默认模型"语义——仅认用户显式保存过的值）----
  // 更新时机：applySavedStageSettings 回填 / saveStageEndpoints 保存成功；
  // 消费时机：refreshModels 成功后命中列表则恢复选中，未命中才提示更换
  //（default_model_missing 警告的唯一触发源）；无已存值不预选不出警告
  const savedStageModels = { 1: '', 3: '' };

  // 批3（D2026-1008-01）：分析模型独立配置的已存模型名（回填/保存成功后
  // 记忆；恢复语义对齐 savedStageModels 先例——刷新命中列表恢复选中，
  // 未命中注入标记 option 后选中）
  let savedAiModel = '';

  // 模型下拉空态占位 option（批2 D2026-1002-12）：value 空 + disabled +
  // selected，文案走 JS 态键 model_list_empty_hint；HTML 初始骨架 /
  // 切服务商重置 / 拉取失败恢复共用同一形态
  function modelEmptyOptionHTML() {
    return '<option value="" disabled selected>'
      + MSG.model_list_empty_hint + '</option>';
  }

  // ---- 模型列表刷新 ----
  async function refreshModels(n) {
    const prov = ($('refineS' + n + 'Provider') || {}).value;
    const btn = $('refineRefreshS' + n);
    const sel = $('refineS' + n + 'Model');
    if (!btn || !sel) return;
    if (!prov) { stageStatus(n, MSG.select_provider_first, 'err'); return; }
    btn.disabled = true;
    const old = btn.innerHTML; btn.textContent = '…';   // innerHTML 保存：按钮含内联 SVG，textContent 会丢图标（D2026-1001 批2）
    // 保留 HTML 空态占位 option，失败/异常时恢复，避免下拉被清空
    const originalHTML = sel.innerHTML;
    sel.innerHTML = '<option value="">' + MSG.loading_models + '</option>';
    stageStatus(n, MSG.fetching_models, '');
    try {
      const r = await pywebview.api.refine_list_models(
        prov, stageEndpoint(n), stageKeyOrNull(n));
      if (r.success && r.models.length) {
        sel.innerHTML = r.models.map(m =>
          '<option value="' + esc(m) + '">' + esc(m) + '</option>').join('');
        let warn = '';
        if (prov === 'zen') {
          const free = r.models.filter(x => x.endsWith('-free'));
          if (free.length) sel.value = free[0]; else sel.selectedIndex = 0;
        } else if (savedStageModels[n]
                   && r.models.includes(savedStageModels[n])) {
          // 已存模型命中刷新所得列表：恢复选中（老用户无感）
          sel.value = savedStageModels[n];
        } else if (savedStageModels[n]) {
          // 已存值与刷新所得列表不匹配：优先选第一个非嵌入模型，避免误选
          // text-embedding-*，并提示更换（default_model_missing 唯一触发源）
          const opts = Array.from(sel.options || []);
          const nonEmbed = opts.find(o =>
            !(o.value || '').toLowerCase().startsWith('text-embedding'));
          sel.value = nonEmbed ? nonEmbed.value : sel.options[0].value;
          warn = MSG.default_model_missing(savedStageModels[n], sel.value);
        }
        // 无已存值：不预选任何模型（列表首项自然显示）、不出警告
        stageStatus(n, warn || MSG.models_loaded(r.models.length),
                    warn ? '' : 'ok');
      } else {
        sel.innerHTML = originalHTML;
        stageStatus(n, '❌ ' + (r.error || MSG.fetch_failed) + (r.tip ? ' · ' + r.tip : ''), 'err');
      }
    } catch (e) {
      sel.innerHTML = originalHTML;
      stageStatus(n, '❌ ' + e, 'err');
    } finally {
      btn.disabled = false; btn.innerHTML = old;
    }
  }

  // ---- 接管模型列表刷新 ----
  async function refreshFallbackModels() {
    const sel = $('refineFallbackModel');
    const btn = $('refreshFallbackModels');
    if (!sel || !btn) return;

    // 获取 LM Studio endpoint（从阶段A的 lmstudio 配置中读取）
      const endpoint = stageEndpointFor('lmstudio') || 'http://localhost:1234/v1';

    btn.disabled = true;
    const old = btn.innerHTML; btn.textContent = '…';   // innerHTML 保存：按钮含内联 SVG，textContent 会丢图标（D2026-1001 批2）
    try {
      const r = await pywebview.api.list_local_models(endpoint);
      if (r.success && r.models.length) {
        const cur = sel.value;
        // A2 兜底重绑定：保留空值默认项（"不自动兜底"），用户未显式
        // 选择接管模型时不强塞本地模型
        sel.innerHTML = '<option value="">' + MSG.fallback_no_auto + '</option>'
          + r.models.map(m =>
            '<option value="' + esc(m) + '">' + esc(m) + (r.loaded.includes(m) ? ' ✓' : '') + '</option>').join('');
        // 尝试保持之前选中的值
        if (cur && r.models.includes(cur)) sel.value = cur;
      } else {
        // 保留默认选项
      }
    } catch (e) {
      // 静默失败，保留现有选项
    } finally {
      btn.disabled = false; btn.innerHTML = old;
    }
  }

  // 页面加载时自动刷新接管模型列表
  document.addEventListener('DOMContentLoaded', function() {
    setTimeout(refreshFallbackModels, 1000);
  });

  // ---- 单阶段测试 ----
  async function testStage(n) {
    const prov = ($('refineS' + n + 'Provider') || {}).value;
    const model = ($('refineS' + n + 'Model') || {}).value;
    const st = $('refineTestS' + n + 'Status');
    const btn = $('refineTestS' + n);
    if (!btn) return;
    btn.disabled = true;
    if (st) {
      st.style.color = 'var(--text-muted)';
      // P1-9 格8/9（D2026-1015-05）：失败锚补状态类（既有 .status-err，
      // 零新 CSS）——运行/成功清类，失败加类
      st.classList.toggle('status-err', false);
      st.textContent = MSG.testing;
    }
    try {
      const r = await pywebview.api.refine_test_stage(
        prov, model, stageEndpoint(n), stageKeyOrNull(n));
      if (st) {
        st.style.color = r.success ? 'var(--status-ok)' : 'var(--status-err)';
        st.classList.toggle('status-err', !r.success);
        st.textContent = (r.success ? '✅ ' : '❌ ') +
          (r.success ? r.message : (r.tip || r.error || MSG.failed));
      }
      if (!r.success && r.tip) console.warn('[refine]', r.tip);
    } catch (e) {
      if (st) {
        st.style.color = 'var(--status-err)';
        st.classList.toggle('status-err', true);
        st.textContent = '❌ ' + e;
      }
    } finally {
      btn.disabled = false;
    }
  }

  // ============================================================
  // 批3（D2026-1008-01）：分析/修复模型三件套（下拉+刷新+测试）
  // 下拉=select（阶段页 refineS*Model 先例）、刷新=在线拉模型、测试=
  // refine_test_stage 同桥。分析行锚 aiModelInput（id 保留）；修复行全
  // class+data-testid 零 id。状态反馈对齐 stageStatus（✅/❌+状态色）。
  // ============================================================

  // 刷新按钮内联 SVG（逐字对齐阶段页 refineRefreshS* 图标；innerHTML
  // 保存/恢复惯例见 D2026-1001 批2 注释——textContent 会丢图标）
  const MODEL_REFRESH_SVG = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/></svg>';

  // 行内状态 span（分析行/修复行共用；kind 对齐 stageStatus 口径）
  function trioStatus(el, text, kind) {
    if (!el) return;
    el.style.color = kind === 'err' ? 'var(--status-err)'
      : (kind === 'ok' ? 'var(--status-ok)' : 'var(--text-muted)');
    el.textContent = text;
  }

  // 三件套独立态刷新主体（分析行/修复行同款）：lmstudio 走
  // list_local_models（已加载 ✓ 置前 + 已下载合并——HRO-2 裁定：通用
  // /v1/models 只列已加载会复现"列表空"痛点）；其余 provider 走
  // refine_list_models（api_key 传 null=后端回退已存密钥）。端点用
  // REFINE_PROVIDER_URLS 默认端点（与后端 ai_provider 独立分支"CLI 各
  // provider 默认端点"消费口径一致）。失败恢复原 HTML（阶段页先例）。
  async function refreshTrioSelect(prov, sel, btn, savedModel, status) {
    if (!sel || !btn) return;
    if (!window.pywebview || !window.pywebview.api) {
      status(MSG.api_not_ready, 'err');
      return;
    }
    if (!prov || prov === 'follow') {
      status(MSG.select_provider_first, 'err');
      return;
    }
    btn.disabled = true;
    const old = btn.innerHTML; btn.textContent = '…';
    const originalHTML = sel.innerHTML;
    sel.innerHTML = '<option value="">' + MSG.loading_models + '</option>';
    status(MSG.fetching_models, '');
    try {
      const r = (prov === 'lmstudio')
        ? await window.pywebview.api.list_local_models(
            REFINE_PROVIDER_URLS.lmstudio || '')
        : await window.pywebview.api.refine_list_models(
            prov, REFINE_PROVIDER_URLS[prov] || '', null);
      if (r && r.success && r.models.length) {
        sel.innerHTML = r.models.map(m =>
          '<option value="' + esc(m) + '">' + esc(m)
          + (prov === 'lmstudio' && r.loaded && r.loaded.includes(m)
              ? ' ✓' : '')
          + '</option>').join('');
        // 已存值不在列表→注入标记 option（阶段页先例）；命中→恢复选中
        if (savedModel && !r.models.includes(savedModel)) {
          const marker = document.createElement('option');
          marker.value = savedModel;
          marker.textContent = savedModel;
          sel.appendChild(marker);
        }
        if (savedModel) sel.value = savedModel;
        status(MSG.models_loaded(r.models.length), 'ok');
      } else {
        sel.innerHTML = originalHTML;
        status('❌ ' + ((r && r.error) || MSG.fetch_failed)
          + (r && r.tip ? ' · ' + r.tip : ''), 'err');
      }
    } catch (e) {
      sel.innerHTML = originalHTML;
      status('❌ ' + e, 'err');
    } finally {
      btn.disabled = false; btn.innerHTML = old;
    }
  }

  // 三件套测试主体：桥=refine_test_stage（与阶段页测试按钮同桥同参），
  // 反馈样式对齐 stageStatus（✅/❌ + 状态色 span）
  async function testTrioModel(prov, model, endpoint, key, btn, status) {
    if (!btn) return;
    if (!window.pywebview || !window.pywebview.api) {
      status(MSG.api_not_ready, 'err');
      return;
    }
    btn.disabled = true;
    status(MSG.testing, '');
    try {
      const r = await window.pywebview.api.refine_test_stage(
        prov, model, endpoint, key);
      const ok = !!(r && r.success);
      status((ok ? '✅ ' : '❌ ') + (ok
        ? (r.message || MSG.testing)
        : ((r && (r.tip || r.error)) || MSG.failed)),
        ok ? 'ok' : 'err');
      if (!ok && r && r.tip) console.warn('[refine]', r.tip);
    } catch (e) {
      status('❌ ' + e, 'err');
    } finally {
      btn.disabled = false;
    }
  }

  // 分析行 follow 态统一口径：模型下拉禁用+占位（ai_model_follow_hint）、
  // 刷新/测试按钮随禁（follow=无独立配置可刷可测；provider 切换/回填
  // 共用此单源，避免状态漂移）
  function aiModelApplyFollowState() {
    const sel = $('aiModelInput');
    if (!sel) return;
    const follow = (($('aiProviderSel') || {}).value || 'follow') === 'follow';
    sel.innerHTML = '<option value="" disabled selected>'
      + (follow ? MSG.ai_model_follow_hint : MSG.model_list_empty_hint)
      + '</option>';
    sel.disabled = follow;
    const row = document.querySelector('.ai-config-row');
    ['.ai-model-refresh', '.ai-model-test'].forEach((cls) => {
      const b = row && row.querySelector(cls);
      if (b) b.disabled = follow;
    });
  }

  // 分析行刷新（独立态）
  async function refreshAnalysisModels() {
    const sel = $('aiModelInput');
    const btn = document.querySelector('.ai-config-row .ai-model-refresh');
    if (!sel || !btn) return;
    const st = document.querySelector('.ai-config-row .ai-model-status');
    await refreshTrioSelect(
      (($('aiProviderSel') || {}).value || 'follow'),
      sel, btn, savedAiModel, (t, k) => trioStatus(st, t, k));
  }

  // 分析行测试：follow=测阶段A 当前配置（生效模型语义一致）；
  // 独立态=测所选独立 provider/model（key=null=后端回退已存密钥）
  async function testAnalysisModel() {
    const btn = document.querySelector('.ai-config-row .ai-model-test');
    if (!btn) return;
    const st = document.querySelector('.ai-config-row .ai-model-status');
    const status = (t, k) => trioStatus(st, t, k);
    const prov = (($('aiProviderSel') || {}).value || 'follow');
    if (prov === 'follow') {
      await testTrioModel(
        (($('refineS1Provider') || {}).value || '').toLowerCase(),
        (($('refineS1Model') || {}).value || '').trim(),
        stageEndpoint(1), stageKeyOrNull(1), btn, status);
    } else {
      await testTrioModel(prov,
        (($('aiModelInput') || {}).value || '').trim(),
        REFINE_PROVIDER_URLS[prov] || '', null, btn, status);
    }
  }

