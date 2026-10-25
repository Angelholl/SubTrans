// ===== Refine UI：模型刷新/测试 + 词库表格编辑器 + 角色卡编辑器 =====
  window.__refineUI = true;

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    // 2.7.4 件1 三发修订（#189 双重转义根因）：& 必须最先转义——原序先
    // 把 " 转成 &quot; 再转 &，会把 &quot; 的 & 二次转义为 &amp;quot;，
    // 页面显示字面 &quot;（所有含引号文本全局受害，非模板双层包裹）
    return String(s == null ? '' : s).replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;').replace(/</g, '&lt;');
  }

  // 服务商默认接口地址（切换服务商时自动填充到该阶段的地址栏）
  const REFINE_PROVIDER_URLS = {
    lmstudio: 'http://localhost:1234/v1',
    ollama: 'http://localhost:11434/v1',
    zen: 'https://opencode.ai/zen/v1',
    deepseek: 'https://api.deepseek.com/v1',
    siliconflow: 'https://api.siliconflow.cn/v1',
    custom: ''
  };

  // ---- 字幕清洗参数弹窗会话态（D2026-1024-01 批2 件A）：当前会话已应用的
  // 清洗参数（null=全默认口径）；不落 localStorage，刷新自然复位 ----
  let _appliedPolishParams = null;

  // ---- TM 与断点合并弹窗会话态（D2026-1024-01 批3 件B）：原「TM 与学习闸」
  // 「断点与日志」两区块静态控件迁入 AppModal.tmBreak 弹窗；当前会话值
  // （初值=原静态控件初始值：TM 开/断点开，learned/冲突禁入/强制恢复/
  // 详细日志关，库路径/阈值空串）；不落 localStorage，刷新自然复位 ----
  let _tmBreakParams = {
    tm_enable: true,
    tm_db: '',
    tm_threshold: '',
    glossary_learn: false,
    glossary_conflict_block: false,
    resume: true,
    force_resume: false,
    verbose: false,
  };

  // 每阶段独立的接口地址输入框
  function stageEndpoint(n) {
    const v = ($('refineS' + n + 'Endpoint') || {}).value;
    return v && v.trim() ? v.trim() : '';
  }

  // 指定服务商当前使用的接口地址：优先取使用该服务商的阶段地址栏，否则用默认
  function stageEndpointFor(prov) {
    for (const n of [1, 3]) {
      if ((($('refineS' + n + 'Provider') || {}).value) === prov) {
        const ep = stageEndpoint(n);
        if (ep) return ep;
      }
    }
    return REFINE_PROVIDER_URLS[prov] || '';
  }

  // 服务商切换 → 该阶段地址栏自动填充对应默认地址
  function applyProviderEndpoint(n) {
    const prov = ($('refineS' + n + 'Provider') || {}).value;
    const ep = $('refineS' + n + 'Endpoint');
    if (!ep) return;
    ep.value = REFINE_PROVIDER_URLS[prov] || '';
    ep.disabled = (prov === 'deepseek');
    if (prov === 'deepseek') ep.value = '';
    ep.placeholder = prov === 'deepseek'
      ? MSG.ep_deepseek_placeholder : MSG.ep_placeholder;
    // ollama 地址同样可编辑（与 lmstudio 一致，placeholder 提示默认端口）
  }

  // 每阶段独立 API Key（LM Studio 无需；留空则后端回退到已保存密钥）
  function stageKeyOrNull(n) {
    const v = ($('refineS' + n + 'Key') || {}).value;
    return v && v.trim() ? v.trim() : null;
  }

  // 取指定服务商在阶段行里填写的第一个非空密钥（随启动参数传给子进程）
  function stageKeyFor(prov) {
    for (const n of [1, 3]) {
      if ((($('refineS' + n + 'Provider') || {}).value) === prov) {
        const k = stageKeyOrNull(n);
        if (k) return k;
      }
    }
    return '';
  }

  // 行内状态提示（每阶段自己的 span）
  function stageStatus(n, text, kind) {
    const st = $('refineTestS' + n + 'Status');
    if (!st) return;
    st.style.color = kind === 'err' ? 'var(--status-err)' : (kind === 'ok' ? 'var(--status-ok)' : 'var(--text-muted)');
    // P1-9 格8/9（D2026-1015-05）：保存/运行反馈补失败状态类（零新 CSS）
    st.classList.toggle('status-err', kind === 'err');
    st.textContent = text;
  }

  // ---- 并行度读取（1-5，非法/缺省回退1）----
  function readRefineConcurrency() {
    let n = parseInt(($('refineConcurrency') || {}).value, 10);
    if (!Number.isFinite(n)) n = 1;
    return Math.max(1, Math.min(5, n));
  }

  // ---- 上下文窗口读取（A1 缺省重绑定：显式合法值才传；空/非法/<4096
  // 返回 null=不传，走后端缺省 16384；管线会按生效值对齐引擎）----
  function readRefineCtx() {
    let n = parseInt(($('refineV2Ctx') || {}).value, 10);
    if (!Number.isFinite(n) || n < 4096) return null;
    return n;
  }

  // ---- 正整数读取（A5：空/非法/0/负数返回 null=不传，后端缺省接管；
  // 替代 parseInt(v)||30 形态——0 会被吞成缺省值）----
  function readPositiveInt(id) {
    let n = parseInt(($(id) || {}).value, 10);
    return (Number.isFinite(n) && n > 0) ? n : null;
  }

  // ---- 字幕清洗细参数折算（D2026-1024-01 批2 件A）：会话级已应用参数 →
  // buildRefineOptions 的 9 个 polish_* 键；未应用（null）=全默认=空对象
  // （零键，api 侧默认零旗标）；空串/0/default 值不给键 ----
  function appliedPolishOptionFields() {
    const out = {};
    const p = _appliedPolishParams;
    if (!p) return out;
    const posInt = (v) => {
      const n = parseInt(v, 10);
      return Number.isFinite(n) && n > 0 ? n : null;
    };
    const posNum = (v) => {
      const n = parseFloat(v);
      return Number.isFinite(n) && n > 0 ? n : null;
    };
    const mlc = posInt(p.max_line_chars);
    if (mlc) out.polish_max_line_chars = mlc;
    const ml = posInt(p.max_lines);
    if (ml) out.polish_max_lines = ml;
    const md = posInt(p.max_duration_ms);
    if (md) out.polish_max_duration_ms = md;
    const mg = posNum(p.min_gap_ms);
    if (mg) out.polish_min_gap_ms = mg;
    if (p.quote_style === 'keep' || p.quote_style === 'curly') {
      out.polish_quote_style = p.quote_style;
    }
    if (p.keep_final_period) out.polish_keep_final_period = true;
    if (p.remove_dialogue_gt) out.polish_remove_dialogue_gt = true;
    if (p.rewrap_enabled === false) out.polish_no_rewrap = true;
    if (p.clamp_long_enabled === false) out.polish_no_clamp_long = true;
    return out;
  }

  // ---- 启动选项收集器（v2 两阶段：阶段A→s1 槽位，阶段B→s3 槽位）----
  function buildRefineOptions() {
    return {
      inputs: AppState.selectedFiles,
      output_dir: $('outputDir') ? $('outputDir').value : '',
      extra_output_formats: [
        ($('outputFmtAss') || {}).checked ? 'ass' : null,
        ($('outputFmtVtt') || {}).checked ? 'vtt' : null,
      ].filter(Boolean),
      // 字幕清洗总开关（D2026-1023-03 批3）：默认不勾=不传/False；
      // 会话级无持久化（与附加格式复选框同语义，刷新复位）
      polish_enabled: !!($('polishEnabled') || {}).checked,
      // 字幕清洗细参数（D2026-1024-01 批2 件A）：自会话级 _appliedPolishParams
      // 折算 9 键（未应用=全默认，一律不给键）；白名单转发语义见
      // api.py _build_refine_args（空值/0/default 一律不产生旗标）
      ...appliedPolishOptionFields(),
      // 源文假名清洗两开关（D2026-1025-01 批3b）：会话级值存于
      // _appliedPolishParams（清洗弹窗分区三保存写回，与 9 个 polish_* 键
      // 同会话态）；未开过弹窗（null）=缺省反射管线默认 True/False；
      // api 侧白名单转发，默认态零旗标=字节不变
      source_kana_merge: _appliedPolishParams
        ? _appliedPolishParams.source_kana_merge !== false
        : true,
      source_kana_moan_delete: !!((_appliedPolishParams || {}).source_kana_moan_delete),
      profile: ($('refineProfile') || {}).value || 'local',
      v2_concurrency: readRefineConcurrency(),
      v2_ctx: readRefineCtx(),
      s1_provider: ($('refineS1Provider') || {}).value,
      s1_model: ($('refineS1Model') || {}).value || '',
      s3_provider: ($('refineS3Provider') || {}).value,
      s3_model: ($('refineS3Model') || {}).value || '',
      templates_dir: ($('refineTemplatesDir') || {}).value || '',
      glossary: ($('refineGlossary') || {}).value || '',
      custom_key: stageKeyFor('custom'),
      zen_key: stageKeyFor('zen'),
      siliconflow_key: stageKeyFor('siliconflow'),
      deepseek_key: stageKeyFor('deepseek'),
      apply_glossary_stage1: !($('refineGl1') && !$('refineGl1').checked),
      apply_glossary_stage2: !($('refineGl2') && !$('refineGl2').checked),
      batch_local: readPositiveInt('refineBatchLocal'),
      batch_cloud: readPositiveInt('refineBatchCloud'),
      lmstudio_endpoint: stageEndpointFor('lmstudio'),
      ollama_endpoint: stageEndpointFor('ollama'),
      zen_endpoint: stageEndpointFor('zen'),
      siliconflow_endpoint: stageEndpointFor('siliconflow'),
      custom_endpoint: stageEndpointFor('custom'),
      fallback_local: !!($('refineFallbackLocal') || {}).checked,
      fallback_model: (($('refineFallbackModel') || {}).value || '').trim(),
      cleaner_config_dir: (($('refineCleanerConfig') || {}).value || '').trim(),
      // 断点/日志/TM 8 键（D2026-1024-01 批3 件B）：键名与取值语义零变化，
      // 取值来源由静态控件 DOM $() 改为会话态 _tmBreakParams（控件迁入
      // AppModal.tmBreak 合并弹窗，保存结算写回会话态）
      resume: !!_tmBreakParams.resume,
      // 强制断点恢复：--force-resume 隐含 --resume 由 RefineConfig.__post_init__ 保证，前端只传一个键
      force_resume: !!_tmBreakParams.force_resume,
      // 学习闸开关：默认 false 不拼旗标（api.py 侧按需转 --glossary-learn / --glossary-conflict-block）
      glossary_learn: !!_tmBreakParams.glossary_learn,
      glossary_conflict_block: !!_tmBreakParams.glossary_conflict_block,
      verbose: !!_tmBreakParams.verbose,
      source_filter: (($('refineSourceFilter') || {}).value || 'default'),
      auto_synopsis: !($('refineAutoSynopsis') && !$('refineAutoSynopsis').checked),
      // H4b 条目级阈值自适应：默认不勾选不传旗标（api.py 侧按需转 --adaptive-thresholds）
      adaptive_thresholds: !!($('refineAdaptiveThresholds') || {}).checked,
      // 翻译记忆库：勾选取消时才传 no_tm（--no-tm）；路径/阈值非空才传
      no_tm: !_tmBreakParams.tm_enable,
      tm_db: (_tmBreakParams.tm_db || '').trim(),
      tm_threshold: (_tmBreakParams.tm_threshold || '').trim(),
      // 2.1 翻译方向（D2026-0930-04 定案①）：缺省 ja/zh 由 api 侧过滤
      // 不产生旗标；指令卡路径有值才传（缺卡由 CLI validate 报错）
      source_lang: ($('directionSource') || {}).value || '',
      target_lang: ($('directionTarget') || {}).value || '',
      s1_instructions: (($('directionCardS1') || {}).value || '').trim(),
      s3_instructions: (($('directionCardS3') || {}).value || '').trim()
    };
  }

  TranslatorManager.collectOptions = buildRefineOptions;

  // ---- 字幕清洗入口组（D2026-1024-01 批2 件A）：标题+徽章+说明+入口钮+
  // summary 行全 JS 态 MSG 填充（组内零 id/零静态 data-i18n）；入口钮开
  // AppModal.polish（回填会话已应用参数），保存结算后写回会话态并刷新
  // summary；summary 未应用=默认口径固定文案，应用后列实际值与偏离项
  // （零散拼接片段随值内联，同 encode 摘要行函数键先例） ----
  function renderPolishAdvSummary() {
    const row = document.querySelector('.polish-params-summary');
    if (!row) return;
    const p = _appliedPolishParams;
    if (!p) {
      row.textContent = MSG.polishAdvSummaryDefault;
      return;
    }
    const posInt = (v) => {
      const n = parseInt(v, 10);
      return Number.isFinite(n) && n > 0 ? n : null;
    };
    const posNum = (v) => {
      const n = parseFloat(v);
      return Number.isFinite(n) && n > 0 ? n : null;
    };
    const parts = [];
    const mlc = posInt(p.max_line_chars);
    if (mlc) parts.push('每行 ' + mlc + ' 全角字');
    const ml = posInt(p.max_lines);
    if (ml) parts.push('每条 ' + ml + ' 行');
    const md = posInt(p.max_duration_ms);
    if (md) parts.push('上限 ' + md + 'ms');
    const mg = posNum(p.min_gap_ms);
    if (mg) parts.push('间隔 ' + String(p.min_gap_ms).trim() + 'ms');
    if (p.quote_style === 'keep') parts.push('引号不动');
    else if (p.quote_style === 'curly') parts.push('弯引号“”');
    if (p.keep_final_period) parts.push('保留句号');
    if (p.remove_dialogue_gt) parts.push('删除>>标记');
    if (p.rewrap_enabled === false) parts.push('拆行重排关');
    if (p.clamp_long_enabled === false) parts.push('超长钳制关');
    row.textContent = MSG.polishAdvSummaryLine(parts);
  }

  (function initPolishAdvGroup() {
    const fill = () => {
      const title = document.querySelector('.polish-adv-title');
      if (title) {
        // 标题复用 polish_enabled_label（「字幕清洗（实验性）」文字相同）+ 徽章
        title.textContent = MSG.polish_enabled_label;
        title.appendChild(document.createTextNode(' '));
        const badge = document.createElement('span');
        badge.className = 'tag-provisional';
        badge.textContent = MSG.polishAdvBadge;
        title.appendChild(badge);
      }
      const desc = document.querySelector('.polish-adv-desc');
      if (desc) desc.textContent = MSG.polishAdvDesc;
      document.querySelectorAll('.polish-params-open-btn').forEach((btn) => {
        btn.textContent = MSG.polishAdvOpenBtn;
        btn.addEventListener('click', async () => {
          const r = await AppModal.polish({ last: _appliedPolishParams });
          if (r && r.ok) {
            _appliedPolishParams = r.params;
            renderPolishAdvSummary();
          }
        });
      });
      renderPolishAdvSummary();
    };
    // 本文件在 body 尾同步加载（DOM 已就绪）；readyState 兜底防早载
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fill);
    } else {
      fill();
    }
  })();

  // ---- TM 与断点入口组（D2026-1024-01 批3 件B）：原「TM 与学习闸」
  // 「断点与日志」两区块撤除迁入 AppModal.tmBreak 合并弹窗；入口组标题+
  // 说明+入口钮+summary 行全 JS 态 MSG 填充（组内零 id/零静态 data-i18n）；
  // 入口钮开弹窗（回填会话当前值），保存结算后写回会话态并刷新 summary；
  // summary 基线四项（TM 开关/TM 阈值/断点恢复/详细日志）+偏离项拼接
  // （状态词/偏离片段随值内联，同 encode 摘要行函数键先例） ----
  function renderTmBreakAdvSummary() {
    const row = document.querySelector('.tm-break-params-summary');
    if (!row) return;
    const p = _tmBreakParams;
    const parts = [
      '翻译记忆库：' + (p.tm_enable ? '开' : '关'),
      'TM 阈值：' + (String(p.tm_threshold).trim() || '默认'),
      '断点恢复：' + (p.resume ? '开' : '关'),
      '详细日志：' + (p.verbose ? '开' : '关'),
    ];
    if (String(p.tm_db || '').trim()) parts.push('TM 库路径：自定义');
    if (p.glossary_learn) parts.push('自学习：开');
    if (p.glossary_conflict_block) parts.push('冲突禁入：开');
    if (p.force_resume) parts.push('强制恢复：开');
    row.textContent = parts.join(' · ');
  }

  (function initTmBreakAdvGroup() {
    const fill = () => {
      const title = document.querySelector('.tm-break-adv-title');
      if (title) title.textContent = MSG.tmBreakAdvGroupTitle;
      const desc = document.querySelector('.tm-break-adv-desc');
      if (desc) desc.textContent = MSG.tmBreakAdvDesc;
      document.querySelectorAll('.tm-break-params-open-btn').forEach((btn) => {
        btn.textContent = MSG.tmBreakAdvOpenBtn;
        btn.addEventListener('click', async () => {
          const r = await AppModal.tmBreak({ last: _tmBreakParams });
          if (r && r.ok) {
            _tmBreakParams = r.params;
            renderTmBreakAdvSummary();
          }
        });
      });
      renderTmBreakAdvSummary();
    };
    // 本文件在 body 尾同步加载（DOM 已就绪）；readyState 兜底防早载
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fill);
    } else {
      fill();
    }
  })();

