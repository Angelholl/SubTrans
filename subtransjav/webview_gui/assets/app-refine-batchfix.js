  async function refineAiAnalyze() {
    if (!lastLoadedGuidePath && !lastLoadedIsTxt) {
      aiStatus(MSG.aiNeedGuide);
      return;
    }
    if (!window.pywebview || !window.pywebview.api) {
      aiStatus(MSG.api_not_ready, true);
      return;
    }
    const rp = aiReportPath();
    if (!rp || !rp.endsWith('_质量报告.txt')) {
      aiStatus(MSG.aiNeedGuide);
      return;
    }
    // 修复B+2.5.0 批5（D2026-1001-07）：生效 provider/model 读数改单源
    // analyzeResolution（P2/D2026-1008-02：G5-补 半配置忽略+回落阶段A，
    // 弃「独立 provider×阶段A 模型」跨服务商拼装）；云 provider 发送前
    // 确认读实际生效值（C1/C7）
    const res = analyzeResolution();
    if (AI_CLOUD_PROVIDERS.includes(res.effProvider)) {
      const go = await AppModal.confirm(MSG.aiCloudConfirm(res.effProvider));
      if (!go) return;
    }
    const btn = $('refineAiAnalyzeBtn');
    if (btn) btn.disabled = true;
    // 批4（D2026-1008-01）：分析中旁挂「停止分析」（class 锚零 id，
    // 文案 JS 态 MSG；点击置 pending 态并发取消桥，最终结果由主调用
    // 回包收口——回包 cancelled=True 时状态行显 C12 文案）
    const stopBtn = document.querySelector('.ai-analyze-stop-btn');
    if (stopBtn) {
      stopBtn.textContent = MSG.aiStopBtn;
      if (!stopBtn.dataset.stopBound) {
        stopBtn.dataset.stopBound = '1';
        stopBtn.addEventListener('click', () => {
          if (!window.pywebview || !window.pywebview.api) return;
          stopBtn.disabled = true;
          aiStatus(MSG.aiStopPending);
          Promise.resolve(window.pywebview.api.refine_cancel_ai_analyze())
            .catch(() => {})
            .finally(() => { stopBtn.disabled = false; });
        });
      }
      stopBtn.style.display = '';
    }
    aiStatus(MSG.aiAnalyzing);
    try {
      const r = await window.pywebview.api.refine_ai_analyze(
        rp, res.model, res.provider);
      if (r && r.success) {
        lastAiSuggestions = r;
        aiRenderResult(r);
        aiStatus(MSG.aiDone + (r.crosscheck_segments
          ? MSG.asrCrosscheckNote(r.crosscheck_segments) : ''));
      } else if (r && r.cancelled) {
        aiStatus(MSG.aiCancelled);
      } else {
        // 修复B：分析失败时 stderr_tail 首行摘要进错误信息（截断 200 字符）
        let detail = (r && r.error) || MSG.unknown;
        const tail = (r && r.stderr_tail) || '';
        const firstLine = tail.split('\n').map(s => s.trim()).find(Boolean) || '';
        if (firstLine) detail += '｜' + firstLine.slice(0, 200);
        aiStatus(MSG.aiFailed(detail), true);
      }
    } catch (e) {
      aiStatus(MSG.aiFailed(e && e.message ? e.message : String(e)), true);
    } finally {
      if (btn) btn.disabled = false;
      // 批4：停止按钮隐藏复位——取消/完成后均可重新发起
      if (stopBtn) stopBtn.style.display = 'none';
    }
  }

  // ===== 2.6.0 批1（D2026-1002-02-批1）：质量闭环一键批次修复 =====
  // 幂等守卫在后端（台账 applied 拒入批）；前端只做范围选择+逐条预览+
  // 确认放行（无无人值守自动写盘）。stderr_tail/stdout_tail 一律走
  // textContent 渲染（R2），禁 innerHTML 拼接。
  let lastActionItems = null;

  // P1-9 格5（D2026-1015-05）：失败色锚——同 aiStatus/guideStatus 先例补
  // isError 分支（既有 .status-err 类，零新样式）；仅真实失败分支传 true
  // （api 未就绪/回滚失败/修复失败），成功与中性提示（需导读/无可修条目/
  // 运行中/取消）清类。
  function bfStatus(text, isError) {
    const st = $('refineBatchFixStatus');
    if (!st) return;
    st.textContent = text || '';
    st.classList.toggle('status-err', !!isError);
  }

  // 2.7.4 件C（D2026-1007-02）：修复生效配置常驻明示行（对齐
  // 生效行直拼先例）：生效 provider/model 由后端
  // refine_preview_fix_config 统一解析，拒绝时明示行红色直显原因；
  // 未加载导读时隐藏。P2（D2026-1008-02）：入参=analyzeResolution()
  // 产物（预览与修复执行同源 by construction，C7）；notes（半配置
  // 忽略说明）前端直拼；返回桥结果（供 batchFixRun 确认框副行复用），
  // 桥异常回 null。
  function bfRefreshEffective() {
    const el = $('batchFixEffectiveLine');
    if (!el) return Promise.resolve(null);
    if (!lastLoadedGuidePath || lastLoadedIsTxt) {
      el.style.display = 'none';
      return Promise.resolve(null);
    }
    if (!window.pywebview || !window.pywebview.api) {
      return Promise.resolve(null);
    }
    const res = analyzeResolution();
    const note = (res.notes || []).join('；');
    return window.pywebview.api.refine_preview_fix_config(
        res.provider, res.model)
      .then((r) => {
        if (!r) return null;
        el.style.display = '';
        if (r.ok) {
          el.classList.remove('status-err');
          // 生效源人话标识（分析模型/跟随阶段A）由后端 source_label
          // 直出，前端零解析直拼（拒绝分支仍走 reason）
          el.textContent = MSG.batchFixUsing(
            r.provider || MSG.batchFixModelUnset,
            r.model || MSG.batchFixModelUnset)
            + (r.source_label ? MSG.batchFixSourceTag(r.source_label) : '')
            + (note ? '｜' + note : '');
        } else {
          el.classList.add('status-err');
          el.textContent = (note ? note + '；' : '')
            + (r.reason || MSG.batchFixModelUnset);
        }
        return r;
      })
      .catch(() => null);
  }

  function batchFixRefresh() {
    // 使能钩子：导读 json 加载成功后拉取行动条目（含台账已修标记）。
    // 批5（D2026-1008-02）：返回拉取 promise（既有调用方均忽略返回值，
    // 行为不变）——batchFixRun 成功分支 await 它后再算剩余明细
    const btn = $('refineBatchFixBtn');
    const scope = $('refineBatchFixScope');
    if (!btn || !window.pywebview || !window.pywebview.api) return;
    // 2.7.4 件C（D2026-1007-02）：明示行随刷新链同步（载入导读/修复结束共用）
    bfRefreshEffective();
    // 3.0 批2：一键回滚按钮随导读加载态显隐（json 导读就绪才可用）
    const rbBtn = document.querySelector('.fullchain-rollback-btn');
    if (rbBtn) {
      rbBtn.style.display =
        (!lastLoadedGuidePath || lastLoadedIsTxt) ? 'none' : '';
    }
    if (!lastLoadedGuidePath || lastLoadedIsTxt) {
      lastActionItems = null;
      btn.disabled = true;
      if (scope) { scope.style.display = 'none'; scope.innerHTML = ''; }
      return;
    }
    return window.pywebview.api.refine_guide_action_items(lastLoadedGuidePath)
      .then((r) => {
        if (!r || !r.success) {
          lastActionItems = null;
          btn.disabled = true;
          return;
        }
        lastActionItems = r;
        const fixable = (r.open_items || []).filter(it => !it.applied_in_ledger);
        btn.disabled = fixable.length === 0;
        if (scope) {
          scope.innerHTML = '';
          scope.title = MSG.batchFixScopeLabel;
          const optAll = document.createElement('option');
          optAll.value = 'all';
          optAll.textContent = MSG.batchFixScopeAll + '（' + fixable.length + '）';
          scope.appendChild(optAll);
          Object.keys(r.cat_counts || {}).sort().forEach((c) => {
            const o = document.createElement('option');
            o.value = c;
            o.textContent = MSG.batchFixScopeCat(c, r.cat_counts[c]);
            scope.appendChild(o);
          });
          scope.style.display = fixable.length ? '' : 'none';
        }
      })
      .catch(() => {
        lastActionItems = null;
        if (btn) btn.disabled = true;
      });
  }

  // ===== 3.0 批2（D2026-1009-02 批2）：全链链级状态行+digest+一键回滚 =====
  // {name} 占位符格式化 helper（MSG 模板串 + 参数对象 → 文案；未知名保留原样）
  const fcFmt = (tpl, kw) => String(tpl).replace(/\{(\w+)\}/g, (m, k) =>
    (Object.prototype.hasOwnProperty.call(kw, k) ? String(kw[k]) : m));

  // 卡2（D2026-1010-01）：口径说明行（零 data-i18n，不入 i18n 冻结集）——
  // 链白名单 fail-closed 口径可修数 < 导读页「待修」补集口径，属正常
  const FULLCHAIN_SCOPE_NOTE =
    '说明：全链仅自动修复白名单类目（且须有现译），'
    + '可修数小于导读页「待修」数属正常';

  // 链级状态行刷新（silent=true 静默失败）：fullchain_automation_status →
  // running=进行中文案；否则按 last_run 分形态（skipped=服务商原因 /
  // ended_at 空=未完成 / 其余=上次结果一行+漏听放弃段）。展开区（details）
  // 呈现最近一次链 digest：9 键汇总 + 漏听放弃（k=0 隐藏）+ 复验三键计数
  // 差值（last_run 无 per-file/verify 明细，如实显示「—」）+ 台账指引。
  async function fullchainStatusRefresh(silent) {
    const line = document.querySelector('.fullchain-status-line');
    if (!line || !window.pywebview || !window.pywebview.api) return;
    let r = null;
    try {
      r = await window.pywebview.api.fullchain_automation_status();
    } catch (e) { /* 桥异常按读取失败处理 */ }
    if (!r || !r.success) {
      if (!silent) {
        line.hidden = false;
        line.textContent = MSG.fcStatusFail;
      }
      return;
    }
    const run = r.last_run || {};
    const hasRun = Object.keys(run).length > 0;
    const k = Number(run.missed_skipped) || 0;
    let text;
    if (r.running) {
      text = fcFmt(MSG.fcStatusRunning, {
        d: run.files_done || 0, t: run.files_total || 0,
        f: run.entries_fixed || 0 });
    } else if (!hasRun) {
      text = MSG.fcStatusNever;
    } else if (String(run.phase || '') === 'skipped') {
      // 卡2（D2026-1010-01）：透出 skip_reason 真因（原固定文案只说
      // 「服务商原因」不透值，done-0 与 skipped 两侧原因可见性同补）
      const why = String(run.skip_reason || '').trim();
      text = why ? `未启动全链：${why}` : MSG.fcStatusSkipped;
    } else if (!String(run.ended_at || '').trim()) {
      text = fcFmt(MSG.fcStatusUnfinished, { p: run.entries_pending || 0 });
    } else {
      // ended_at 形如 2026-10-10T12:34:56（本地秒级 ISO）→ hh:mm
      text = fcFmt(MSG.fcStatusLast, {
        time: String(run.ended_at).slice(11, 16),
        f: run.entries_fixed || 0, m: run.entries_failed || 0,
        p: run.entries_pending || 0, phase: String(run.phase || '') });
      if (k > 0) text += ' · ' + fcFmt(MSG.fcMissedSkipped, { k });
    }
    line.hidden = false;
    line.textContent = '';
    const main = document.createElement('span');
    main.className = 'fc-status-main';
    main.textContent = text;
    line.appendChild(main);
    // digest 展开区（createElement 注入，零 innerHTML；重刷新整体重建幂等）
    const det = document.createElement('details');
    det.className = 'fc-status-digest';
    const sum = document.createElement('summary');
    sum.textContent = MSG.fcDigestTitle;
    det.appendChild(sum);
    const box = document.createElement('div');
    box.className = 'fc-digest-body';
    const rows = [];
    if (hasRun) {
      rows.push(fcFmt(MSG.fcDigestSummary, {
        d: run.files_done || 0, t: run.files_total || 0,
        f: run.entries_fixed || 0, m: run.entries_failed || 0,
        p: run.entries_pending || 0 }));
      if (k > 0) rows.push(fcFmt(MSG.fcMissedSkipped, { k }));
      // 卡2（D2026-1010-01）：全链原因只以 last_run 为载体（HRO：翻译
      // 完成即停轮询，Console 对链 notice 是前端死信）——notices 逐条
      // 渲染；done 且 0 修时取首条实质原因置顶（跳过「自动化开始」
      // 泛化行），防「看起来 done 但 0 修」无声
      const notices = Array.isArray(run.notices)
        ? run.notices.map(String) : [];
      if (String(run.phase || '') === 'done'
          && (Number(run.entries_fixed) || 0) === 0 && notices.length) {
        const reason = notices.find(
          n => !n.includes('[全链] 自动化开始')) || notices[0];
        rows.push(`原因：${reason}`);
      }
      notices.forEach((n) => rows.push(n));
      if ((Number(run.notices_truncated) || 0) > 0) {
        rows.push(`（另有 ${Number(run.notices_truncated)} 条通知未显示）`);
      }
    }
    rows.push(MSG.fcDigestVerifyNone);
    rows.push(fcFmt(MSG.fcDigestLedgerNote,
      { stem: String(run.guide_stem || lastGuideData
        && lastGuideData.stem || '') }));
    rows.push(FULLCHAIN_SCOPE_NOTE);
    rows.forEach((t) => {
      const d = document.createElement('div');
      d.textContent = t;
      box.appendChild(d);
    });
    det.appendChild(box);
    line.appendChild(det);
  }
  // 切页钩子（switchTab tab-guide 分支消费；失败不阻断切页）
  window.__fullchainStatusHook = () => { fullchainStatusRefresh(true); };

  // 一键回滚（改写恢复）：确认框（applied 条数+auto_insert 条件化提示，
  // 文案不带内部批号）→ fullchain_rollback → 结果如实回显 → 静默重读导读
  // （仿批5 batchFixRun finally 静默重读）+按钮/状态行刷新。
  async function fullchainRollbackRun() {
    if (!lastLoadedGuidePath || lastLoadedIsTxt) return;
    if (!window.pywebview || !window.pywebview.api) {
      bfStatus(MSG.api_not_ready, true);
      return;
    }
    const rbBtn = document.querySelector('.fullchain-rollback-btn');
    let pv = null;
    try {
      pv = await window.pywebview.api
        .fullchain_rollback_preview(lastLoadedGuidePath);
    } catch (e) { /* 预览失败按失败文案处理 */ }
    if (!pv || !pv.success) {
      bfStatus(MSG.fcRollbackFail + '：' + ((pv && pv.error) || ''), true);
      return;
    }
    if (!pv.applied && !pv.auto_insert) {
      bfStatus(MSG.fcRollbackNone); return;
    }
    let body = fcFmt(MSG.fcRollbackConfirmBody, { n: pv.applied });
    if (pv.auto_insert > 0) {
      body += '\n' + fcFmt(MSG.fcRollbackAutoInsertDelete,
        { n: pv.auto_insert });
    }
    const ok = await AppModal.confirm(MSG.fcRollbackConfirmTitle, body);
    if (!ok) return;
    if (rbBtn) rbBtn.disabled = true;
    try {
      const r = await window.pywebview.api
        .fullchain_rollback(lastLoadedGuidePath);
      if (r && r.success) {
        let done = fcFmt(MSG.fcRollbackDone, { n: r.restored || 0 });
        if (r.unmatched && r.unmatched.length) {
          done += fcFmt(MSG.fcRollbackUnmatched,
            { n: r.unmatched.length });
        }
        if (r.auto_insert_skipped > 0) {
          done += fcFmt(MSG.fcRollbackSkipped,
            { k: r.auto_insert_skipped });
        }
        bfStatus(done);
        // 静默重读导读快照（只更新 lastGuideData+局部重渲染，禁走
        // loadGuide 全量链——不抹 AI 结果区，同批5 口径）；静默失败不提示
        window.pywebview.api.read_output_artifact(lastLoadedGuidePath)
          .then((rr) => {
            if (!rr || !rr.success || rr.kind !== 'json' || !rr.data) return;
            lastGuideData = rr.data;
            guideRender(rr.data);
          })
          .catch(() => { /* 静默：下次打开导读自然刷新 */ });
        batchFixRefresh();
        fullchainStatusRefresh(true);
      } else {
        bfStatus(MSG.fcRollbackFail + '：' + ((r && r.error) || ''), true);
      }
    } catch (e) {
      bfStatus(MSG.fcRollbackFail + '：'
        + (e && e.message ? e.message : String(e)), true);
    } finally {
      if (rbBtn) rbBtn.disabled = false;
    }
  }

  async function batchFixRun() {
    if (!lastActionItems) { bfStatus(MSG.batchFixNeedGuide); return; }
    if (!window.pywebview || !window.pywebview.api) {
      bfStatus(MSG.api_not_ready, true);
      return;
    }
    const all = (lastActionItems.open_items || [])
      .filter(it => !it.applied_in_ledger);
    if (!all.length) { bfStatus(MSG.batchFixNoItems); return; }
    const scope = $('refineBatchFixScope');
    const v = (scope && scope.style.display !== 'none') ? scope.value : 'all';
    const chosen = (v && v !== 'all')
      ? all.filter(it => it.category === v)
      : all.slice();
    if (!chosen.length) { bfStatus(MSG.batchFixNoItems); return; }
    let batch = chosen;
    let capNote = '';
    if (batch.length > 50) {
      capNote = MSG.batchFixCapHit(50, batch.length);
      batch = batch.slice(0, 50);
    }
    // P2（D2026-1008-02）：云端警示/服务商展示按生效分析 provider 判定
    // （C7——修复与分析已完全同一模型源，弃阶段B 服务商旧口径）
    const fixRes = analyzeResolution();
    const cloud = isAiCloudProvider(fixRes.effProvider);
    const provLabel = fixRes.effProvider
      ? (MSG['ai_prov_' + fixRes.effProvider] || fixRes.effProvider)
      : MSG.batchFixModelUnset;
    const catCount = {};
    batch.forEach(it => {
      catCount[it.category] = (catCount[it.category] || 0) + 1;
    });
    // 分类明细按数量降序（设计取舍：主要问题类前置，原字母序弱化主次
    // ——2.7.4 件3 D2026-1007-01）
    const cats = Object.keys(catCount)
      .sort((a, b) => catCount[b] - catCount[a])
      .map(c => ({ cat: c, count: catCount[c] }));
    // 现译全文取自已加载导读（lastGuideData 经 read_output_artifact 持有；
    // 后端 action_items 摘录限长仅约束回包形状）——Number 强转匹配，
    // index 非 int 的条目查无全文自动回退摘录并带标记（弹窗内处理）
    const textMap = {};
    ((lastGuideData && lastGuideData.items) || []).forEach((g) => {
      if (!g || g.current_text == null) return;
      const k = Number(g.index);
      if (Number.isFinite(k)) textMap[k] = String(g.current_text);
    });
    // 2.7.4 件C（D2026-1007-02）：打开确认框前刷新明示行并取生效配置
    // （与修复子进程同一解析结果；拒绝时确认框 warn 行直显原因）
    const fixCfg = await bfRefreshEffective();
    const fixCfgMeta = !fixCfg
      ? null
      : (fixCfg.ok
          ? { text: MSG.batchFixUsing(
                fixCfg.provider || MSG.batchFixModelUnset,
                fixCfg.model || MSG.batchFixModelUnset) }
          : { text: fixCfg.reason || MSG.batchFixModelUnset, warn: true });
    const go = await AppModal.batchFixPreview({
      title: MSG.batchFixConfirmTitle,
      okText: MSG.batchFixConfirmOk,
      meta: [
        { text: MSG.batchFixEstimate(batch.length) },
        { text: MSG.batchFixProvider(provLabel) },
        fixCfgMeta,
        cloud ? { text: MSG.batchFixCloudCost, warn: true } : null,
        capNote ? { text: capNote, warn: true } : null,
      ].filter(Boolean),
      cats: cats,
      head: MSG.batchFixPreviewHead,
      items: batch,
      texts: textMap,
    });
    if (!go) return;
    const btn = $('refineBatchFixBtn');
    if (btn) btn.disabled = true;
    // 批4（D2026-1008-01）：修复中旁挂「停止修复」（class 锚零 id；后端
    // cancelled 分支保证取消后不再自动复跑 AI 分析）；轮询让位 pending 态
    const stopBtn = document.querySelector('.batch-fix-stop-btn');
    let stopRequested = false;
    if (stopBtn) {
      stopBtn.textContent = MSG.bfStopBtn;
      if (!stopBtn.dataset.stopBound) {
        stopBtn.dataset.stopBound = '1';
        stopBtn.addEventListener('click', () => {
          if (!window.pywebview || !window.pywebview.api) return;
          stopRequested = true;
          stopBtn.disabled = true;
          bfStatus(MSG.bfStopPending);
          Promise.resolve(window.pywebview.api.refine_cancel_batch_fix())
            .catch(() => {})
            .finally(() => { stopBtn.disabled = false; });
        });
      }
      stopBtn.style.display = '';
    }
    bfStatus(MSG.batchFixRunning(0, batch.length));
    // 批5（D2026-1008-02）：清上一轮剩余明细悬停残留（成功分支按新结果重挂）
    const bfSt = $('refineBatchFixStatus');
    if (bfSt) bfSt.title = '';
    const poll = setInterval(async () => {
      try {
        const p = await window.pywebview.api.refine_batch_fix_progress();
        if (p && p.running && p.phase === 'verify') {
          if (!stopRequested) bfStatus(MSG.batchFixVerifying);
        } else if (p && p.running && !stopRequested) {
          // 执行器无逐条进度输出契约——done=0 时用中性文案（评审修订）
          bfStatus(p.done > 0
            ? MSG.batchFixRunning(p.done, p.total)
            : MSG.batchFixRunningPlain);
        }
      } catch (e) { /* 单次轮询失败静默，主调用最终回显为准 */ }
    }, 1000);
    // 批5（D2026-1008-02）：修复结果对象提升出 try 块——finally 静默
    // 重读导读快照需读成功态（块级 const 于 finally 不可见）
    let r = null;
    try {
      // 修复执行/复验与确认框同一解析源（P2/D2026-1008-02：单源
      // analyzeResolution，后端共用 helper 同参语义）
      const runRes = analyzeResolution();
      r = await window.pywebview.api.refine_batch_fix(
        lastLoadedGuidePath, batch.map(it => it.index),
        runRes.provider, runRes.model);
      if (r && r.success) {
        let msg = MSG.batchFixDone(r.applied || 0, r.failed || 0);
        // 批6（D2026-1008-02）：已与现译一致条目单独计数——open_items 已
        // 排除终态（retranslated/nochange），批5 剩余明细不会误报这类条目
        if (r && r.nochange > 0) {
          msg += '；' + MSG.batchFixNochange(r.nochange);
        }
        if (r && r.skipped > 0) {
          msg += '；' + MSG.batchFixSkipped(r.skipped);
        }
        if (r.source_partial) msg += MSG.batchFixSourcePartial;
        const vfy = r.verify || {};
        if (vfy.error) {
          msg += MSG.batchFixVerifyFail;
        } else if (vfy.after) {
          const sum = (o) => ['glossary', 'tm', 'observations']
            .reduce((s, k) => s + ((o && o[k]) || 0), 0);
          const d = sum(vfy.after) - sum(vfy.before);
          msg += MSG.batchFixVerifyDelta(d);
          if (r.suggestions) {
            lastAiSuggestions = {
              success: true,
              parse_ok: vfy.parse_ok !== false,
              suggestions: r.suggestions,
              // D2026-1010-03 件A：复验重渲染同步透传媒体对照段
              //（缺键/旧后端回包=空数组，区块不渲染，禁止丢键静默消失）
              crosscheck_detail: Array.isArray(r.crosscheck_detail)
                ? r.crosscheck_detail : [],
              provider_name: vfy.provider_name || '',
            };
            aiRenderResult(lastAiSuggestions);
          }
        }
        // 批5（D2026-1008-02）：完成消息含剩余未修复明细——先等行动
        // 条目刷新（batchFixRefresh 后 lastActionItems 已含新
        // applied_in_ledger 标记），再与本次提交集合求差集（Number
        // 强转+null 先判，防 Number(null)=0 误配）。#refineBatchFixStatus
        // 为单行 span：主行截断前 10 个条目号，完整列表走 title 悬停
        //（截断上限常量形态，避开「预览列表禁截前 10」既有钉字面量）
        const REMAINING_SHOW_MAX = 10;
        await batchFixRefresh();
        const submittedSet = new Set(batch.map(it => Number(it.index)));
        const rem = ((lastActionItems && lastActionItems.open_items) || [])
          .filter(it => it && it.index != null && !it.applied_in_ledger
            && submittedSet.has(Number(it.index)));
        const ids = rem.map(it => '#' + String(it.index));
        if (ids.length) {
          msg += '；' + MSG.batchFixRemaining(rem.length,
            ids.slice(0, REMAINING_SHOW_MAX).join(' ')
            + (ids.length > REMAINING_SHOW_MAX ? ' …' : ''));
        }
        bfStatus(msg);
        if (bfSt) {
          bfSt.title = ids.length
            ? MSG.batchFixRemaining(rem.length, ids.join(' '))
            : '';
        }
      } else if (r && r.cancelled) {
        bfStatus(MSG.bfCancelled);
      } else {
        bfStatus(MSG.batchFixFail + '：' + ((r && r.error) || ''), true);
      }
    } catch (e) {
      bfStatus(MSG.batchFixFail + '：'
        + (e && e.message ? e.message : String(e)), true);
    } finally {
      clearInterval(poll);
      if (btn) btn.disabled = false;
      // 批4：停止按钮隐藏复位——取消/完成后均可重新发起
      if (stopBtn) stopBtn.style.display = 'none';
      batchFixRefresh();
      // 3.0 批2：修复完成后同步刷新链级状态行（last_run 计数可能变化）
      fullchainStatusRefresh(true);
      // 批5（D2026-1008-02）：修复成功且当前为 json 导读时静默重读导读
      // 快照——只更新 lastGuideData 并重渲染导读（新终稿/generated_at
      // 即时可见），禁走 loadGuide 全量链（会清空
      // lastAiSuggestions 与 AI 结果区 DOM，抹掉刚重渲染的复验建议；
      // 两容器互不相交，改内存+局部重渲染即可）。静默失败不提示（下次
      // 打开导读自然刷新）；行动条目徽标取 lastActionItems 当前内存值，
      // 不等待刷新时序
      if (r && r.success && !lastLoadedIsTxt && lastLoadedGuidePath
          && window.pywebview && window.pywebview.api) {
        window.pywebview.api.read_output_artifact(lastLoadedGuidePath)
          .then((rr) => {
            if (!rr || !rr.success || rr.kind !== 'json' || !rr.data) return;
            lastGuideData = rr.data;
            guideRender(rr.data);
          })
          .catch(() => { /* 静默：下次打开导读自然刷新 */ });
      }
    }
  }

