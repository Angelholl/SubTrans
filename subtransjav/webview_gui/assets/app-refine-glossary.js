  // P2（D2026-1008-02）：修复模型独立配置行随「修复=分析模型完全统一」
  // 删除（其元素定位/follow 态/刷新/测试函数族一并退役）；修复生效模型
  // 以分析独立配置为唯一来源。

  function glStatus(t) {
    const el = $('refineGlStatus');
    if (el) { el.style.color = 'var(--text-muted)'; el.textContent = t; }
  }

  // ---- 词库表格 ----
  function glRows() {
    const rows = [];
    document.querySelectorAll('#refineGlossTable tbody tr').forEach(tr => {
      const i = tr.querySelector('input.gl-src');
      const o = tr.querySelector('input.gl-dst');
      if (i && o && i.value.trim() && o.value.trim())
        rows.push([i.value.trim(), o.value.trim()]);
    });
    return rows;
  }

  function glRender(rows) {
    const tb = document.querySelector('#refineGlossTable tbody');
    tb.innerHTML = rows.map(r =>
      '<tr>' +
      '<td><input class="form-input compact gl-src" value="' + esc(r[0]) + '"></td>' +
      '<td><input class="form-input compact gl-dst" value="' + esc(r[1]) + '">' +
      // 别名第三列只读展示（不由前端编辑；无别名不渲染，保存时后端保留）
      (r[2] ? '<div class="gl-alias">' + MSG.alias_label +
        esc(r[2]) + '</div>' : '') + '</td>' +
      '<td class="gl-sel-cell"><input type="checkbox" class="gl-sel"></td>' +
      '</tr>').join('');
    const cnt = $('refineGlCount');
    if (cnt) cnt.textContent = rows.length;
    const eh = $('glEmptyHint');
    if (eh) eh.style.display = rows.length ? 'none' : '';
  }

  async function glLoad() {
    try {
      const d = await pywebview.api.refine_default_paths();
      if (d.success) {
        if ($('refineGlossary'))
          $('refineGlossary').value = d.glossary_path;
        if ($('refineTemplatesDir')) {
          $('refineTemplatesDir').value = d.templates_dir;
          const show = $('refineTemplatesDirShow');
          if (show) show.value = d.templates_dir;
        }
        const p = $('refineGlossary') ? $('refineGlossary').value : '';
        const gp = $('refineGlPath');
        if (gp) gp.textContent = p;
      }
      const g = $('refineGlossary') ? $('refineGlossary').value : '';
      if (!g) return;
      const r = await pywebview.api.refine_get_glossary(g);
      if (r.success) glRender(r.rows);
    } catch (e) { console.warn('[refine] 词库加载失败', e); }
  }

  // 学习词库只读查看（config/glossary_learned.csv；自学习产物，优先级低于全局词库）
  // P1-9 格11（D2026-1015-05）：空态显隐交 JS 全权——index.html 移除
  // #glLearnedEmpty 静态 display:none 后，本入口先隐防加载中闪烁，
  // !r.exists 显（下方分支）、成功加载隐；样式类（虚线框）零改动。
  async function glLearnedLoad() {
    const st = $('glLearnedStatus');
    const stats = $('glLearnedStats');
    const empty = $('glLearnedEmpty');
    const more = $('glLearnedMore');
    const tb = document.querySelector('#glLearnedTable tbody');
    if (empty) empty.style.display = 'none';
    if (!tb) return;
    try {
      const r = await window.pywebview.api.refine_get_learned_glossary();
      if (!r || r.success === false) {
        if (st) st.textContent = MSG.gl_learned_load_failed(
          (r && r.error) || MSG.unknown);
        return;
      }
      if (st) st.textContent = '';
      if (!r.exists) {
        tb.innerHTML = '';
        if (stats) stats.textContent = '';
        if (more) more.style.display = 'none';
        if (empty) empty.style.display = '';
        return;
      }
      if (empty) empty.style.display = 'none';
      const rows = r.rows || [];
      tb.innerHTML = rows.map(row =>
        '<tr>' +
        '<td>' + esc(row.source || '') + '</td>' +
        '<td>' + esc(row.target || '') + '</td>' +
        '<td>' + esc(row.aliases || '') + '</td>' +
        '</tr>').join('');
      if (stats) {
        stats.textContent = MSG.gl_learned_stats(
          r.count != null ? r.count : rows.length,
          r.total != null ? r.total : rows.length);
      }
      if (more) {
        const rest = (r.total || 0) - rows.length;
        more.textContent = rest > 0 ? MSG.gl_learned_more(rest) : '';
        more.style.display = rest > 0 ? '' : 'none';
      }
    } catch (e) {
      if (st) st.textContent = MSG.gl_learned_load_failed(
        e && e.message ? e.message : String(e));
    }
  }

  async function glSave() {
    const r = await pywebview.api.refine_save_glossary(
      glRows(), $('refineGlossary') ? $('refineGlossary').value : null);
    glStatus(r.success ? MSG.gl_saved(r.count) : '❌ ' + r.error);
  }

  async function glAdd() {
    const src = await AppModal.prompt(MSG.gl_prompt_src);
    if (!src || !src.trim()) return;
    const dst = await AppModal.prompt(MSG.gl_prompt_dst(src.trim()));
    if (!dst || !dst.trim()) return;
    const rows = glRows().filter(r => r[0] !== src.trim());
    rows.push([src.trim(), dst.trim()]);
    glRender(rows);
  }

  async function glDel() {
    document.querySelectorAll('#refineGlossTable tbody tr').forEach(tr => {
      const cb = tr.querySelector('.gl-sel');
      if (cb && cb.checked) tr.remove();
    });
    const cnt = $('refineGlCount');
    if (cnt) cnt.textContent = glRows().length;
    await glSave();
  }

  async function glImport() {
    const pick = await pywebview.api.refine_pick_csv_open();
    if (!pick.success) return;
    const r = await pywebview.api.refine_get_glossary(pick.path);
    if (!r.success) { glStatus('❌ ' + r.error); return; }
    // 合并基准 = 文件中的既有词条（权威来源），而非 DOM 表格
    const target = $('refineGlossary') ? $('refineGlossary').value : null;
    let merged = [];
    try {
      const baseR = await pywebview.api.refine_get_glossary(target || null);
      if (baseR && baseR.success) merged = baseR.rows;
    } catch (e) { console.warn('[refine] 读取既有词库失败，将仅导入所选文件', e); }
    const have = new Set(merged.map(x => x[0]));
    let added = 0;
    r.rows.forEach(row => {
      if (!have.has(row[0])) { merged.push(row); have.add(row[0]); added++; }
    });
    glRender(merged);
    glStatus(MSG.gl_imported(added));
    await pywebview.api.refine_save_glossary(merged, target || null);
  }

  async function glExport() {
    const pick = await pywebview.api.refine_pick_csv_save();
    if (!pick.success) return;
    const r = await pywebview.api.refine_save_glossary(glRows(), pick.path);
    glStatus(r.success ? MSG.gl_exported(r.count, r.path) : '❌ ' + r.error);
  }

