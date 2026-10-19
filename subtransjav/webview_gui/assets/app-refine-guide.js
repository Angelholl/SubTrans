  // ---- 质量报告导读查看器（W1b：仅读 *_质量报告导读.json，不读 txt/全量 json）----
  const GUIDE_SUFFIX = '_质量报告导读.json';
  // 最近一次成功加载的导读路径（AI 分析按其 stem 推导质量报告 txt 路径）
  let lastLoadedGuidePath = '';
  // 最近一次成功加载的报告 txt 路径（双格式入口：AI 分析直接以其为入参）
  let lastLoadedReportTxtPath = '';
  // 最近一次加载的成品类型：'json' | 'txt'（决定 AI 分析取数来源）
  let lastLoadedIsTxt = false;
  // 最近一次 AI 分析的建议载荷（逐条落库时按下标取条目）
  let lastAiSuggestions = null;
  // P3（D2026-1008-02，C19）：TM 原始建议旁路存储（内存 Map idx→原始
  // target，不序列化、不写伴生 JSON）——「恢复原建议」数据源；随
  // lastAiSuggestions 重置/换渲染源而重置（修复复验重建属预期）
  let tmOriginalTargets = new Map();
  let tmOriginalSeed = null;   // 渲染源身份标记（同对象重渲染不覆盖已编辑值）
  // 最近一次成功加载的导读数据（媒体来源条渲染依据）
  let lastGuideData = null;
  // 卡A（D2026-1010-01 三轮）：加载时 mtime 基线（read_output_artifact
  // 返回），陈旧检测据此判变化
  let lastLoadedGuideMtime = 0;
  // 会话内媒体路径覆盖（等价 --media-path；仅显式输入，非空即优先生效）
  let mediaOverridePath = '';
  // 2.7.4 件2：试听媒体推断结果每 guide 前端缓存（override/持久化变更时
  // 失效）——导读加载后缺失态即可显示 tag-auto 横幅，不等首次试听
  let inferredMediaCache = {};

  // 状态行（2.7.4 件1 语义收敛）：#guideStatus 同槽复用（FROZEN 零改动），
  // 首用时动态补齐 .status-line 骨架——图标槽（成功✓/失败⚠）+.status-path
  // （mono 11px/nowrap/ellipsis）+媒体缺失琥珀提示槽+复制路径键；
  // 路径回显唯一走本行（guideCustomStatus 收敛为来源 chip，双写撤销）
  function ensureGuideStatusLine() {
    const st = $('guideStatus');
    if (!st || st.dataset.statusUpgraded) return st;
    st.dataset.statusUpgraded = '1';
    st.classList.add('status-path');
    const wrap = st.parentElement;
    if (!wrap) return st;
    wrap.classList.add('status-line');
    const ico = document.createElement('span');
    ico.className = 'status-ico';
    ico.textContent = '✓';
    wrap.insertBefore(ico, st);
    const hint = document.createElement('span');
    hint.className = 'guide-media-hint';
    hint.style.display = 'none';
    wrap.appendChild(hint);
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'btn btn-ghost btn-sm guide-copy-btn';
    copy.textContent = MSG.guide_copy_path;
    copy.addEventListener('click', () => guideCopyPath(copy));
    wrap.appendChild(copy);
    return st;
  }

  function guideStatus(text, isError) {
    const st = ensureGuideStatusLine();
    if (!st) return;
    st.textContent = text || '';
    st.title = text || '';          // 悬停全文（ellipsis 截断兜底）
    const line = st.parentElement;
    if (!line) return;
    line.classList.toggle('status-err', !!isError);
    const ico = line.querySelector('.status-ico');
    if (ico) ico.textContent = isError ? '⚠' : '✓';
  }

  // 复制路径：clipboard 失败/缺席静默降级（title 悬停可取全文，同
  // AppModal.download copyable 先例）；成功「已复制」1.5s 复位
  function guideCopyPath(btn) {
    const st = $('guideStatus');
    const text = st ? (st.title || st.textContent || '') : '';
    if (!btn || !text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        btn.textContent = MSG.guide_copy_path_done;
        setTimeout(() => { btn.textContent = MSG.guide_copy_path; }, 1500);
      }).catch(() => { btn.title = text; });
    } else {
      btn.title = text;
    }
  }

  // 媒体缺失琥珀提示槽（状态行内独立 span，随媒体来源三态联动）
  function mediaMissingHint(show) {
    ensureGuideStatusLine();
    const st = $('guideStatus');
    const hint = st && st.parentElement
      ? st.parentElement.querySelector('.guide-media-hint') : null;
    if (!hint) return;
    hint.textContent = show ? MSG.guide_media_missing_hint : '';
    hint.style.display = show ? '' : 'none';
  }

  function guidePath() {
    const opts = buildRefineOptions();
    const first = (opts.inputs || [])[0] || '';
    if (!first) return '';
    const norm = String(first).replace(/\\/g, '/');
    const outDirRaw = (opts.output_dir || '').trim();
    const outDir = (!outDirRaw || outDirRaw === 'source')
      ? norm.slice(0, norm.lastIndexOf('/')) || '.'
      : outDirRaw;
    const stem = norm.slice(norm.lastIndexOf('/') + 1)
      .replace(/\.[^./]+$/, '')
      .replace(/\.(japanese|chinese|translated)$/, '');
    return outDir.replace(/[\\/]+$/, '') + '/' + stem + GUIDE_SUFFIX;
  }

  // 卡B（D2026-1010-01 三轮，零 data-i18n）：行动条目明细弹窗文案与
  // 共享卡片构造——主页只留计数 chip + 入口按钮，全量条目在弹窗内阅读
  const GUIDE_ITEMS_OPEN_BTN_LABEL = (n) => '查看明细（' + n + ' 条）';
  const GUIDE_ITEMS_MODAL_TITLE = '行动条目明细';

  // 卡片 markup 共享构造（主页弹窗同一渲染源；试听契约红线
  // .btn-audio-preview + data-timing 原样保留——委托锚点分别在
  // #guideItems 与弹窗列表容器）。appliedSet 台账兜底/终态徽标逻辑
  // 与批6 钉口径一致（构造随载体变更移出 guideRender）
  function guideItemCardHtml(item, appliedSet) {
    const catCls = (c) => (c === 'cps_too_fast' ? 'bfp-cat-warn'
      : c === 'untranslated' ? 'bfp-cat-primary'
      : c === 'antonym_yamete' ? 'bfp-cat-danger' : 'bfp-cat-neutral');
    const o = item || {};
    const cur = (o.current_text == null)
      ? MSG.guide_item_unresolvable
      : esc(String(o.current_text).slice(0, 80));
    const isMissed = String(o.category || '') === 'suspected_missed_speech';
    const hasTiming = !!o.timing;
    const idxKey = Number(o.index);
    const applied = appliedSet != null && Number.isFinite(idxKey)
      && appliedSet.has(idxKey);
    return '<div class="guide-item'
      + (isMissed ? ' guide-item-missed' : '') + '">'
      + '<div class="item-head">'
      + '<span class="idx-chip">#' + esc(o.index) + '</span>'
      + '<span class="bfp-cat-chip ' + catCls(String(o.category || ''))
      + '">' + esc(o.category) + '</span>'
      + (o.status === 'nochange'
        ? '<span class="bfp-cat-chip bfp-cat-neutral">'
          + esc(MSG.guide_item_nochange) + '</span>'
        : (applied || o.status === 'retranslated')
          ? '<span class="media-source-tag tag-auto">'
            + esc(MSG.guide_item_applied) + '</span>'
          : '')
      + '<span class="item-timing">' + esc(o.timing) + '</span>'
      + (hasTiming
        ? '<button type="button" class="btn btn-ghost btn-sm'
          + ' btn-audio-preview" data-timing="' + esc(o.timing)
          + '">' + esc(MSG.preview_play_btn) + '</button>'
        : '')
      + '</div>'
      + '<div class="item-msg">' + esc(o.message) + '</div>'
      + '<div class="item-cur">' + MSG.guide_item_current_label + cur
      + ' · ' + esc(o.status) + '</div>'
      + '</div>';
  }

  function guideRender(data) {
    // json 模式：显示结构化导读块，隐藏只读文本块（双格式互斥）
    const txtView = $('guideTxtView');
    const jsonBlocks = $('guideJsonBlocks');
    if (txtView) txtView.style.display = 'none';
    if (jsonBlocks) jsonBlocks.style.display = '';
    // 区块重排（2.7.4 件1）：零 DOM 移动——容器挂 .json-blocks（flex
    // column + CSS order：条目1/结论2/章节3/伴生4/meta5），子节点 append
    // 顺序保持静态 DOM 原序
    if (jsonBlocks) jsonBlocks.classList.add('json-blocks');
    const ulC = $('guideConclusions');
    const dlS = $('guideSections');
    const ulP = $('guideCompanions');
    if (ulC) {
      ulC.innerHTML = (data.conclusions || [])
        .map(c => '<li>' + esc(c) + '</li>').join('')
        || '<li>' + MSG.no_conclusions + '</li>';
    }
    if (dlS) {
      // 章节导读分节卡（2.7.4 件1）：dt/dd 平铺改 .section-card——标题行
      // （chevron+title 600 字重）点击展开/收起，note 正文 muted 默认折叠。
      // 容器 dl#guideSections 与 id 零改动；dl 内分组 div 为 HTML5 合法子元素
      const sections = Array.isArray(data.sections) ? data.sections : [];
      dlS.innerHTML = '';
      if (!sections.length) {
        dlS.innerHTML = '<dt>' + MSG.no_sections + '</dt>';
      }
      sections.forEach((s) => {
        const o = s || {};
        const card = document.createElement('div');
        card.className = 'section-card';
        const head = document.createElement('div');
        head.className = 'section-card-head';
        const chev = document.createElement('span');
        chev.className = 'guide-chevd';
        chev.textContent = '▾';
        const title = document.createElement('span');
        title.className = 'section-card-title';
        title.textContent = String(o.title || '');
        head.appendChild(chev);
        head.appendChild(title);
        head.addEventListener('click', () => {
          card.classList.toggle('sect-open');
        });
        const note = document.createElement('div');
        note.className = 'section-card-note';
        note.textContent = String(o.note || '');
        card.appendChild(head);
        card.appendChild(note);
        dlS.appendChild(card);
      });
    }
    const divI = $('guideItems');
    if (divI) {
      const items = Array.isArray(data.items) ? data.items : [];
      // 行动条目标题提级 + 条数 chip（2.7.4 件1）：标题 h4 为静态节点，
      // JS 动态加 .block-title.main 与 .count-chip（applyI18n 首屏已跑完，
      // 动态子节点不会被 i18n 重写抹除；幂等——重渲染仅更新计数）
      // 批5（D2026-1008-02）：台账已修徽标——lastActionItems 存在且其
      // guide_path 与当前导读一致才生效（后端 _validate_user_directory
      // resolve 与前端拼接的分隔符/大小写形态可能不同，归一后比对）；
      // applied 集合按 Number 强转 index 匹配（null 先判防
      // Number(null)=0 误配）。无渲染源 seed 机制——每次渲染重算，
      // 幂等；未 applied 的 open 行保持现状不加徽标。
      // 批6：计算提级至条数 chip 之前——头部计数「已修」段在老文件
      // （无 status 终态）时复用本集合（C4 双源口径见下方 chip 注释）
      let appliedSet = null;
      if (lastActionItems && lastLoadedGuidePath) {
        const normPath = (s) =>
          String(s || '').replace(/\\/g, '/').toLowerCase();
        if (normPath(lastActionItems.guide_path)
            === normPath(lastLoadedGuidePath)) {
          appliedSet = new Set((lastActionItems.open_items || [])
            .filter(it => it && it.index != null
              && it.applied_in_ledger === true)
            .map(it => Number(it.index)));
        }
      }
      const itemsHead = divI.previousElementSibling;
      if (itemsHead && itemsHead.tagName === 'H4') {
        itemsHead.classList.add('block-title', 'main');
        let chip = itemsHead.querySelector('.count-chip');
        if (!chip) {
          chip = document.createElement('span');
          chip.className = 'count-chip';
          itemsHead.appendChild(chip);
        }
        // 批6（D2026-1008-02）头部计数五段式分解（决策 C-②）：待修/观察
        // 恒显。C4 统一去重公式（新/老/混合三文件形态全一致）：
        // applied = (status==='retranslated') ∪ appliedSet 台账 timing
        // 命中——同一 item 两源同真只计一次；已修=applied 计数；无需改动
        // =status==='nochange' 计数（>0 才显）；观察=status===
        // 'observation'；待修=total−已修−无需改动−观察（补集式恒 ≥0，
        // C2：open 与未知 status 天然落入待修）。老文件（无终态值）退化
        // 为纯台账轨
        const statusOf = (o) => String((o && o.status) || '');
        const nFixed = items.filter((o) => {
          const k = Number(o && o.index);
          return statusOf(o) === 'retranslated'
            || (appliedSet != null && Number.isFinite(k) && appliedSet.has(k));
        }).length;
        const nNochg = items.filter((o) => statusOf(o) === 'nochange').length;
        const nObs = items.filter((o) => statusOf(o) === 'observation').length;
        // 补集式待修：去重后的已修不与待修重复扣减（Math.max 防御性钳 0）
        const nFixable = Math.max(0,
          items.length - nFixed - nNochg - nObs);
        const segs = [String(items.length) + ' 条',
          MSG.guide_chip_fixable + ' ' + nFixable,
          MSG.guide_chip_observation + ' ' + nObs];
        if (nFixed > 0) {
          segs.push(MSG.guide_chip_applied + ' ' + nFixed);
        }
        if (nNochg > 0) {
          segs.push(MSG.guide_chip_nochange + ' ' + nNochg);
        }
        chip.textContent = segs.join(' · ');
      }
      if (!items.length) {
        divI.innerHTML = '<div>' + MSG.guide_items_none + '</div>';
      } else {
        // 卡B（D2026-1010-01 三轮）：主页只留计数 chip + 明细入口——
        // 全量条目移入弹窗（owner：主页浏览太多、不便阅读）；卡片
        // markup 由 guideItemCardHtml 共享构造（批6 全量渲染契约由
        // 弹窗承接，批6 钉随决策更新载体；试听委托锚在弹窗列表容器）
        divI.innerHTML = '';
        const openBtn = document.createElement('button');
        openBtn.type = 'button';
        openBtn.className = 'btn btn-secondary btn-compact guide-items-open-btn';
        openBtn.textContent = GUIDE_ITEMS_OPEN_BTN_LABEL(items.length);
        openBtn.addEventListener('click', () => openGuideItemsModal());
        divI.appendChild(openBtn);
      }
    }
    if (ulP) {
      const comp = data.companions || {};
      const keys = Object.keys(comp);
      ulP.innerHTML = keys.length
        ? keys.map(k => '<li>' + esc(k) + ' ' + (comp[k] ? '✓' : '✗') + '</li>').join('')
        : '<li>' + MSG.no_companions + '</li>';
    }
    const meta = $('guideMeta');
    if (meta) {
      meta.textContent = MSG.generated_at_label + (data.generated_at || MSG.unknown)
        + ' · ' + (data.basis || '');
    }
  }

  // customPath 传入时走「打开其他质量报告导读」：加载用户显式指定路径
  // （后端 read_output_artifact 白名单后缀 + 目录守卫，只读）；缺省走
  // guidePath 按输入/输出目录自动推导（只加载最近产出）
  async function guideLoad(silent, customPath) {
    if (!window.pywebview || !window.pywebview.api) {
      if (!silent) guideStatus(MSG.api_not_ready, true);
      return;
    }
    let p;
    const isCustom = customPath != null;
    if (isCustom) {
      // customPath 来自文件对话框选中结果（refine_pick_guide_json），
      // 后端 read_output_artifact 仍有白名单后缀 + 目录守卫兜底
      p = String(customPath).trim();
    } else {
      p = guidePath();
      if (!p) {
        if (!silent) guideStatus(MSG.guide_need_inputs);
        return;
      }
    }
    if (!silent || isCustom) guideStatus(MSG.guide_loading);
    // 2.7.4 件1 双写收敛：加载中隐藏来源 chip（成功后按来源重显），
    // 路径回显唯一走 #guideStatus 状态行
    guideCustomStatus('');
    try {
      const r = await window.pywebview.api.read_output_artifact(p);
      if (r && r.success) {
        // 修复C：载入新报告后清空旧 AI 分析结果——lastAiSuggestions=null
        // 防 aiApplyGlossary/aiApplyTm 把旧建议落进新报告对应的词库/TM
        // （错配消费），结果区 DOM 同步清零给用户可见反馈
        lastAiSuggestions = null;
        tmOriginalTargets = new Map();   // C19：原始建议随内存同批重置
        const air = $('refineAiResult');
        if (air) air.innerHTML = '';
        const dv = $('refineGuideViewer');
        if (dv) dv.open = true;
        const geh = $('guideEmptyHint');
        if (geh) geh.style.display = 'none';
        if (r.kind === 'txt') {
          // 报告 txt：只读文本块展示；AI 分析直接以该报告 stem 为入参
          lastLoadedReportTxtPath = r.path || p;
          lastLoadedIsTxt = true;
          guideRenderTxt(r);
          batchFixRefresh();
          guideStatus(MSG.guide_txt_loaded(r.path || p)
            + (r.truncated ? MSG.guide_txt_truncated_note : ''));
          // 来源 chip：仅自定义导读成功加载时显示（2.7.4 件1 收敛）
          guideCustomStatus(isCustom
            ? (MSG.guide_txt_loaded(r.path || p)
              + (r.truncated ? MSG.guide_txt_truncated_note : ''))
            : '');
          return;
        }
        lastLoadedGuidePath = r.path || p;
        lastLoadedIsTxt = false;
        lastLoadedGuideMtime = Number(r.mtime) || 0;
        lastGuideData = r.data || {};
        updateMediaSourceBar(lastGuideData);
        // 2.7.4 件2：推断缓存命中且当前为缺失态 → tag-auto 横幅显示
        // 推断路径（评议员条件②：持久化条目不在加载时阻塞校验，仅展示）
        const tagNow = $('mediaSourceTag');
        if (tagNow && tagNow.classList.contains('tag-none')
            && inferredMediaCache[lastLoadedGuidePath]) {
          renderMediaTag('tag-auto', MSG.preview_media_matched,
            inferredMediaCache[lastLoadedGuidePath]);
          mediaMissingHint(false);
        }
        guideRender(r.data || {});
        batchFixRefresh();
        guideStatus(MSG.guide_loaded(r.path || p));
        guideCustomStatus(isCustom ? MSG.guide_loaded(r.path || p) : '');
      } else {
        const err = MSG.guide_load_failed((r && r.error) || MSG.unknownError);
        guideStatus(err, true);
      }
    } catch (e) {
      const err = MSG.guide_load_failed(
        e && e.message ? e.message : String(e));
      guideStatus(err, true);
    }
  }

  // 卡A（D2026-1010-01 三轮）：导读陈旧自动重读——全链/批修复在后台
  // 更新导读文件后，本页已加载条目会停留修复前旧态（owner 真机实证：
  // 链修完 25+3 条页面仍显示待修 28）。批修复入口有自身静默重读，链
  // daemon 无前端完成钩子——切回本页时轻量探针比对 mtime，变化即静默
  // 重读+状态行提示。检测失败不阻断切页。
  async function guideStalenessCheck() {
    if (!lastLoadedGuidePath || lastLoadedIsTxt) return;
    if (!window.pywebview || !window.pywebview.api) return;
    if (!lastLoadedGuideMtime) return;   // 无基线（旧会话/读取失败）不误报
    try {
      const r = await window.pywebview.api.output_artifact_mtime(
        lastLoadedGuidePath);
      if (!r || !r.success || !r.exists) return;
      const m = Number(r.mtime) || 0;
      if (m && Math.abs(m - lastLoadedGuideMtime) > 0.5) {
        lastLoadedGuideMtime = m;        // 先更新基线防重复触发
        await guideLoad(true);
        guideStatus(MSG.guide_loaded(lastLoadedGuidePath)
          + '（已自动重读最新）');
      }
    } catch (e) { /* 陈旧检测失败不阻断切页 */ }
  }
  window.__guideStalenessHook = () => { guideStalenessCheck(); };

  // 卡B（D2026-1010-01 三轮）：明细弹窗打开——全量条目经共享卡片构造
  // 渲染进 AppModal.guideItems；appliedSet 与计数 chip 同源复算。
  // D2026-1010-03 件B：可选 index 过滤（仅数组实参生效——防御事件对象
  // 等非数组实参被当过滤条件；全量打开入口的监听已改显式无参包裹），
  // 过滤空集如实显示 0 条不做全量回退（HRO-B 裁决配套语义）。
  function openGuideItemsModal(indexes) {
    const all = Array.isArray(lastGuideData && lastGuideData.items)
      ? lastGuideData.items : [];
    let items = all;
    if (Array.isArray(indexes) && indexes.length) {
      const want = new Set(indexes.map(Number));
      items = all.filter((it) => it && want.has(Number(it.index)));
    }
    let appliedSet = null;
    if (lastActionItems && lastLoadedGuidePath) {
      const normPath = (s) =>
        String(s || '').replace(/\\/g, '/').toLowerCase();
      if (normPath(lastActionItems.guide_path)
          === normPath(lastLoadedGuidePath)) {
        appliedSet = new Set((lastActionItems.open_items || [])
          .filter(it => it && it.index != null
            && it.applied_in_ledger === true)
          .map(it => Number(it.index)));
      }
    }
    AppModal.guideItems({
      title: GUIDE_ITEMS_MODAL_TITLE + '（' + items.length + ' 条）',
      listHtml: items.map((it) => guideItemCardHtml(it, appliedSet)).join(''),
      onPreview: (timing) => openAudioPreview(timing),
    });
  }

  // 报告 txt 只读文本块：等宽/可滚动/保留换行（CSS 类 guide-txt-view）
  function guideRenderTxt(r) {
    const txtView = $('guideTxtView');
    const jsonBlocks = $('guideJsonBlocks');
    if (jsonBlocks) jsonBlocks.style.display = 'none';
    if (txtView) {
      txtView.style.display = '';
      // textContent 赋值天然保留换行且免注入
      txtView.textContent = String(r.text || '');
    }
  }

  // 「打开其他质量报告导读」来源徽标（2.7.4 件1 语义收敛）：仅自定义导读
  // 成功加载时显示 chip（primary-soft/strong 来源色，title 悬停本次加载
  // 路径）；加载中/失败/非自定义一律隐藏——路径与错误回显唯一走
  // #guideStatus 状态行
  function guideCustomStatus(text, isError) {
    const st = $('guideCustomStatus');
    if (!st) return;
    const show = !isError && !!text;
    st.style.display = show ? '' : 'none';
    if (show) {
      st.classList.add('guide-custom-chip');
      st.textContent = MSG.guide_custom_source;
      st.title = text;
    }
  }

  // 完成翻译后的静默自动探测：成功才展开面板，失败不打扰用户
  function guideAutoDetect() {
    guideLoad(true);
  }
  TranslatorManager.guideAutoDetect = guideAutoDetect;

  // ============================================================
  // 媒体来源条 + 快速试听（D2026-0929-09 视听对比第二阶段）
  // 媒体路径来源收窄（C-5 契约内选择）：导读 media_path（自动发现）
  // 或用户显式输入（等价 --media-path，会话内覆盖）；无文件对话框。
  // ============================================================

  // 媒体来源条标签/路径直写（2.7.4 件2）：推断命中（tag-auto）/重匹配
  // 成功后显示推断路径横幅；与 updateMediaSourceBar 的三态切换共用 DOM
  function renderMediaTag(cls, text, path) {
    const tagEl = $('mediaSourceTag');
    const pathEl = $('mediaSourcePath');
    if (!tagEl || !pathEl) return;
    tagEl.classList.remove('tag-none', 'tag-auto', 'tag-explicit');
    if (cls) tagEl.classList.add(cls);
    tagEl.textContent = text;
    pathEl.textContent = path || '';
    pathEl.title = path || '';
  }

  function updateMediaSourceBar(data) {
    const bar = $('mediaSourceBar');
    if (!bar) return;
    const pathEl = $('mediaSourcePath');
    const tagEl = $('mediaSourceTag');
    if (!pathEl || !tagEl) return;
    const autoPath = String((data && data.media_path) || '');
    const autoIsOverride = String((data && data.media_path_source) || '')
      === 'override';
    const path = mediaOverridePath || autoPath;
    // 三态修饰类（2.7.4 件1）：tag-none=warn 色系 / tag-auto=ok 色系 /
    // tag-explicit=主色（现蓝不变）。tag-auto 仅备类——「已自动匹配」的
    // 数据接线属件2，本件不触发（autoPath 命中仍按既有文案原蓝展示）
    const setTag = (cls, text) => {
      tagEl.classList.remove('tag-none', 'tag-auto', 'tag-explicit');
      if (cls) tagEl.classList.add(cls);
      tagEl.textContent = text;
    };
    if (mediaOverridePath) {
      setTag('tag-explicit', MSG.media_source_explicit);
      pathEl.textContent = mediaOverridePath;
      pathEl.title = mediaOverridePath;   // 悬停全路径
      mediaMissingHint(false);
    } else if (autoPath) {
      // 后端回包 media_path_source=override 时按原语义归显式态（tag-explicit）；
      // 纯自动命中暂用默认原蓝，「已自动匹配」接线属件2（tag-auto 备而不触发）
      setTag(autoIsOverride ? 'tag-explicit' : '',
        autoIsOverride ? MSG.media_source_explicit : MSG.media_source_auto);
      pathEl.textContent = autoPath;
      pathEl.title = autoPath;
      mediaMissingHint(false);
    } else {
      // 缺失态：tag-none 短句 + 状态行琥珀提示（条目可查看但不可试听）
      setTag('tag-none', MSG.media_source_none);
      pathEl.textContent = '';
      pathEl.title = '';
      mediaMissingHint(true);
    }
    bar.style.display = '';
  }

  // "HH:MM:SS,mmm --> HH:MM:SS,mmm" → [start_s, end_s]；解析失败 null
  function timingToSeconds(timing) {
    const m = String(timing || '').match(
      /(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})/);
    if (!m) return null;
    const s = (+m[1]) * 3600 + (+m[2]) * 60 + (+m[3]) + (+m[4]) / 1000;
    const e = (+m[5]) * 3600 + (+m[6]) * 60 + (+m[7]) + (+m[8]) / 1000;
    return [s, e];
  }

  // 本地媒体文件 → file:// URL（逐段 encodeURIComponent，兼容空格/中文）
  function fileUrlOf(p) {
    return 'file:///' + String(p).replace(/\\/g, '/').split('/')
      .map(encodeURIComponent).join('/');
  }

