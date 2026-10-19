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

  // ---- 角色卡编辑器 ----
  // 下拉动态化（D2026-0930-07-追加1 范围定稿2）：refineTemplateStage 的
  // 选项由后端 refine_list_templates 动态填充（canonical A/B 精确匹配
  // V2_TEMPLATE_FILES 文件名排最前并带阶段标注，其余文件按文件名列示，
  // "所见即所编"）；目录空/pkg_fallback 回落固定 A/B 两项（MSG 渲染，
  // HTML 骨架不留裸中文）。readdir 结果是外部输入 → 渲染全量 esc()。
  let tplDirState = null;   // 最近一次 refine_list_templates 结果缓存

  function tplRenderOptions(r) {
    const sel = $('refineTemplateStage');
    if (!sel) return;
    const files = (r && r.success && Array.isArray(r.files)) ? r.files : [];
    const canon = (r && r.success && r.canonical) || {};
    const items = [];
    if (files.length) {
      // canonical 精确匹配（复合后缀卡如 角色-净语翻译.en2zh.txt 不是 canonical）
      for (const tag of Object.keys(canon)) {
        if (files.some(f => f.name === canon[tag])) {
          items.push({ value: tag, label: MSG['tpl_stage_' + tag.toLowerCase()] });
        }
      }
      for (const f of files) {
        if (Object.values(canon).indexOf(f.name) !== -1) continue;
        items.push({ value: f.name, label: f.name });
      }
    } else {
      // 目录空 → 回落固定 A/B 两项（JS 按 MSG 渲染）
      items.push({ value: 'A', label: MSG.tpl_stage_a });
      items.push({ value: 'B', label: MSG.tpl_stage_b });
    }
    const prev = sel.value;
    sel.innerHTML = items.map(it =>
      '<option value="' + esc(it.value) + '">' + esc(it.label) + '</option>'
    ).join('');
    if (prev && items.some(it => it.value === prev)) sel.value = prev;
  }

  // 高级参数页 #directionCardS1/#directionCardS3 的 datalist（范围定稿3、
  // 建议⑩）：option value=完整路径（目录+文件名）、不带 label；自由输入
  // 与空=自动查找语义不变。空目录注入一条 disabled 提示项。
  function tplRenderDatalist(r) {
    const dl = $('directionCardList');
    if (!dl) return;
    const files = (r && r.success && Array.isArray(r.files)) ? r.files : [];
    const dir = (r && r.success && r.dir) || '';
    if (!files.length) {
      dl.innerHTML = '<option value="" disabled>' + esc(MSG.tpl_dir_empty_datalist) + '</option>';
      return;
    }
    const sep = dir.indexOf('\\') !== -1 ? '\\' : '/';
    dl.innerHTML = files.map(f =>
      '<option value="' + esc(dir ? dir + sep + f.name : f.name) + '">'
    ).join('');
  }

  // 打开词库页（switchTab 钩子）/点"重新加载"/启动时：列目录 → 填下拉
  // 与 datalist；load=true 时按当前选中项加载（选中即加载 load-by-name）。
  async function tplRefreshSelect(load) {
    const dir = $('refineTemplatesDir') ? $('refineTemplatesDir').value : '';
    const st = $('refineTemplateStatus');
    try {
      const r = await pywebview.api.refine_list_templates(dir || null);
      tplDirState = r;
      tplRenderOptions(r);
      tplRenderDatalist(r);
      if (st && r && r.success && r.pkg_fallback) {
        st.style.color = 'var(--status-warn, #b8860b)';
        st.textContent = MSG.tpl_dir_empty_hint;
      }
    } catch (e) {
      // 列举失败也回落固定 A/B，编辑器不空转
      tplDirState = null;
      tplRenderOptions(null);
      tplRenderDatalist(null);
    }
    if (load) tplLoad();
  }

  async function tplLoad() {
    const sel = $('refineTemplateStage');
    const idx = (sel || {}).value;
    const dir = $('refineTemplatesDir') ? $('refineTemplatesDir').value : '';
    const st = $('refineTemplateStatus');
    // 非 'A'/'B' 值 = 动态填充的文件名选项 → load-by-name（必要⑤）
    const isStageTag = idx === 'A' || idx === 'B';
    try {
      const r = isStageTag
        ? await pywebview.api.refine_get_template(idx, dir)
        : await pywebview.api.refine_get_template(idx, dir, idx);
      if (r.success) {
        $('refineTemplateText').value = r.text;
        if (st) {
          st.style.color = 'var(--text-muted)';
          st.textContent = (r.note ? '📌 ' + r.note + '  ' : '') + r.path;
        }
        const lp = $('refineTplLoadedPath');
        if (lp) lp.textContent = MSG.tpl_loaded_path(r.path);
      } else if (st) {
        st.style.color = 'var(--status-err)'; st.textContent = r.error;
      }
    } catch (e) { if (st) st.textContent = '❌ ' + e; }
  }

  // 2.5.0 修复D：高级参数阶段A/B 角色卡"去编辑"跳转——两分支写死：
  // 显式卡路径父目录恰为模板服务端目录且文件名∈refine_list_templates 返回集
  // （"目录内"定义，子目录属目录外）=跳词库页+编辑器精确打开（canonical→
  // 下拉 tag 值映射）；目录外=降级跳词库页+定位角色卡目录+状态行提示
  async function tplGotoEdit(stage) {
    const inp = $('directionCard' + stage);
    const p = ((inp && inp.value) || '').trim();
    switchTab('tab-glossary');
    const st = $('refineTemplateStatus');
    if (!p) {
      if (st) {
        st.style.color = '';
        st.textContent = MSG.tpl_goto_empty_hint;
      }
      tplRefreshSelect(false);
      return;
    }
    // 列举刷新（显式路径可能刚填，缓存或已过期）
    const dir = $('refineTemplatesDir') ? $('refineTemplatesDir').value : '';
    let listing = tplDirState;
    try {
      listing = await pywebview.api.refine_list_templates(dir || null);
      tplDirState = listing;
      tplRenderOptions(listing);
      tplRenderDatalist(listing);
    } catch (e) { listing = null; }
    const files = (listing && listing.success && Array.isArray(listing.files))
      ? listing.files : [];
    const canon = (listing && listing.success && listing.canonical) || {};
    const serverDir = (listing && listing.success && listing.dir) || '';
    const norm = (s) => String(s || '').replace(/\//g, '\\').toLowerCase();
    const parentDir = p.replace(/[\\/][^\\/]*$/, '');
    const fileName = p.split(/[\\/]/).pop() || '';
    const inDir = serverDir && norm(parentDir) === norm(serverDir)
      && files.some(f => f.name === fileName);
    if (!inDir) {
      if (st) {
        st.style.color = 'var(--status-warn, #b8860b)';
        st.textContent = MSG.tpl_goto_outside_hint;
      }
      const show = $('refineTemplatesDirShow');
      if (show) show.focus();   // 定位角色卡目录
      return;
    }
    // 目录内：canonical→tag 映射（A/B tag）或动态文件名选项精确打开
    const tag = Object.keys(canon).find(t => canon[t] === fileName);
    const sel = $('refineTemplateStage');
    if (sel && (tag || files.some(f => f.name === fileName))) {
      sel.value = tag || fileName;
    }
    tplLoad();
  }

  // 2.6.3 批D（D2026-1003-01 P5）：tplSave 改为 AppModal.editor 的 onSave
  // 实现（入参 (stage, text) 由模态传入，缺省回落 DOM 现值；返回
  // {ok, message} 供模态收口：成功清脏+自动关闭，失败弹窗保持）。
  // refine_save_template 四参形态（isStageTag ? null : idx）保持函数钉不变；
  // 保存后按显式卡路径动态提示回落语义（原提示逻辑保留，随 message 回传，
  // 由模态统一写 #refineTemplateStatus 与入口摘要）。
  async function tplSave(stage, text) {
    const idx = (stage != null && stage !== '') ? stage
      : (($('refineTemplateStage') || {}).value);
    const isStageTag = idx === 'A' || idx === 'B';
    const ta = $('refineTemplateText');
    const bodyText = (text != null) ? text : ((ta || {}).value || '');
    let r = null;
    try {
      r = await pywebview.api.refine_save_template(
        idx, bodyText,
        $('refineTemplatesDir') ? $('refineTemplatesDir').value : null,
        isStageTag ? null : idx);
    } catch (e) {
      r = { success: false, error: String(e) };
    }
    if (r && r.success) {
      const savedName = (r.path || '').split(/[\\/]/).pop() || '';
      const c1 = (($('directionCardS1') || {}).value || '').trim();
      const c3 = (($('directionCardS3') || {}).value || '').trim();
      const sameName = [c1, c3].some(v =>
        v && (v.split(/[\\/]/).pop() || '') === savedName);
      const hint = sameName ? MSG.tpl_save_hint_explicit
        : (!c1 && !c3) ? MSG.tpl_save_hint_auto : '';
      return { ok: true, message: (r.path || '') + (hint ? ' ' + hint : '') };
    }
    return { ok: false, message: (r && r.error) || MSG.unknownError };
  }

  // 2.6.3 批D：编辑器入口（词库页+高级参数页两枚 .tpl-editor-entry-btn）——
  // 先列目录+按选中加载（高级页直达时下拉可能尚未初始化），再迁节点开模态。
  // 弹窗内「重新加载/切阶段」经 onStageChange 走原链路（reload=tplRefreshSelect
  // 列目录+加载；change=tplLoad 按当前选中加载，语义同原 bindDom 直绑）。
  async function openTplEditor() {
    if (AppModal._busy) return;
    await tplRefreshSelect(true);
    AppModal.editor({
      title: MSG.tplEditorTitle,
      onSave: tplSave,
      onStageChange: (stage, mode) =>
        (mode === 'reload' ? tplRefreshSelect(true) : tplLoad()),
      onDiscard: () => { tplLoad(); }   // 放弃=按当前阶段重载（丢未保存修改）
    });
  }

  async function pickDir() {
    // 批1a 件3：角色卡目录对话框收口——输入框只读回显（手输不提交），
    // 仅本按钮经原生对话框变更；purpose='templates' 让后端把选择
    // 持久化为角色卡目录（user_dirs.json），重启仍生效。
    const r = await pywebview.api.refine_pick_folder('templates');
    if (r.success && r.path) {
      $('refineTemplatesDir').value = r.path;
      const show = $('refineTemplatesDirShow');
      if (show) show.value = r.path;
      tplRefreshSelect(true);
    }
  }

  async function pickCleanerDir() {
    const r = await pywebview.api.refine_pick_folder();
    if (r.success && r.path) {
      $('refineCleanerConfig').value = r.path;
      const show = $('refineCleanerConfigShow');
      if (show) show.value = r.path;
      saveCleanerDir();   // 程序性赋值不触发 change，显式持久化
    }
  }

  async function openDir(path) {
    if (!path) {
      ConsoleManager.log(MSG.dir_not_set, 'warning');
      return;
    }
    try {
      const r = await pywebview.api.open_output_folder(path, false);
      if (r.success) {
        ConsoleManager.log(MSG.dir_opened(path), 'info');
      } else {
        ConsoleManager.log(MSG.dir_open_failed(r.message), 'error');
      }
    } catch (e) {
      ConsoleManager.log(MSG.dir_open_error(e), 'error');
    }
  }

  // ---- 保存/读取 每阶段服务商+接口地址+密钥 ----
  async function saveStageKey(n) {
    const prov = ($('refineS' + n + 'Provider') || {}).value;
    const key = stageKeyOrNull(n) || '';
    if (!prov) { stageStatus(n, MSG.provider_required, 'err'); return; }
    if (prov === 'lmstudio') { stageStatus(n, MSG.lmstudio_no_key, ''); return; }
    if (prov === 'ollama') { stageStatus(n, MSG.ollama_no_key, ''); return; }
    try {
      const r = await pywebview.api.refine_save_stage_settings(null,
        [{ stage: n, provider: prov, key: key }]);
      if (r.success) {
        stageStatus(n, key ? MSG.key_saved(prov) : MSG.key_cleared, 'ok');
        const inp = $('refineS' + n + 'Key');
        if (inp) { inp.value = ''; inp.placeholder = key ? MSG.key_saved_placeholder : inp.placeholder; }
      } else {
        stageStatus(n, '❌ ' + r.error, 'err');
      }
    } catch (e) { stageStatus(n, '❌ ' + e, 'err'); }
  }

  async function saveStageEndpoints() {
    const st = $('refineEndpointStatus');
    const stages = [];
    for (const n of [1, 3]) {
      stages.push({
        stage: n,
        provider: ($('refineS' + n + 'Provider') || {}).value || '',
        endpoint: stageEndpoint(n),
        model: ($('refineS' + n + 'Model') || {}).value || ''
      });
    }
    try {
      const r = await pywebview.api.refine_save_stage_settings(stages, null,
        { v2_concurrency: readRefineConcurrency(),
          // A1：留空存空串（回填侧 parseInt('')=NaN 忽略），null 由后端
          // 跳过不入库——空串即可覆盖清除旧存档值
          v2_ctx: readRefineCtx() || '' });
      if (r.success) {
        // 批2（D2026-1002-12）：保存成功即更新已存模型名（refreshModels
        // 恢复选中的唯一依据，与后端 settings 保持同源）
        savedStageModels[1] = stages[0].model;
        savedStageModels[3] = stages[1].model;
      }
      if (st) {
        st.style.color = r.success ? 'var(--status-ok)' : 'var(--status-err)';
        // P1-9 格8/9（D2026-1015-05）：保存接口状态补失败状态类（零新 CSS）
        st.classList.toggle('status-err', !r.success);
        st.textContent = r.success
          ? MSG.endpoints_saved + MSG.resume_fingerprint_hint
          : '❌ ' + r.error;
      }
    } catch (e) {
      if (st) {
        st.style.color = 'var(--status-err)';
        st.classList.toggle('status-err', true);
        st.textContent = '❌ ' + e;
      }
    }
  }

  async function applySavedStageSettings() {
    try {
      const r = await pywebview.api.refine_get_stage_settings();
      if (!r.success) return;
      // v1.5 用户模式选择器已取消：画像回填（模式记忆/首启默认）随之删除，
      // 初始安装即默认参数（全部自定义收进左侧 TAB 页）
      // 回填并行度（1-5，越界忽略；缺省时保持控件默认值1）
      if (r.settings && r.settings.v2_concurrency != null) {
        const n = parseInt(r.settings.v2_concurrency, 10);
        const sel = $('refineConcurrency');
        if (sel && n >= 1 && n <= 5) sel.value = String(n);
      }
      // 回填上下文窗口（非法/缺省保持控件默认值）
      if (r.settings && r.settings.v2_ctx != null) {
        const c = parseInt(r.settings.v2_ctx, 10);
        const ctxEl = $('refineV2Ctx');
        if (ctxEl && Number.isFinite(c) && c >= 4096) ctxEl.value = String(c);
      }
      for (const s of (r.stages || [])) {
        const n = parseInt(s.stage);
        if (!n || n < 1 || n > 4) continue;
        const pv = $('refineS' + n + 'Provider');
        const ep = $('refineS' + n + 'Endpoint');
        if (pv && s.provider) pv.value = s.provider;
        if (ep && s.endpoint) ep.value = s.endpoint;
        else if (ep && !ep.value) applyProviderEndpoint(n);
        // 批2（D2026-1002-12 拍板点2）：记录已存模型名作为恢复依据；
        // 无列表状态（空态占位）下注入标记 option 显示已存名并选中
        // （老用户无感）——不匹配警告仅保留给"刷新所得列表"场景
        if (n === 1 || n === 3) {
          savedStageModels[n] = (s.model || '').trim();
          if (savedStageModels[n]) {
            const sel = $('refineS' + n + 'Model');
            if (sel && ![...sel.options].some(o => o.value === savedStageModels[n])) {
              const marker = document.createElement('option');
              marker.value = savedStageModels[n];
              marker.textContent = savedStageModels[n];
              sel.appendChild(marker);
            }
            if (sel) sel.value = savedStageModels[n];
          }
        }
      }
      for (const n of [1, 3]) {
        const ep = $('refineS' + n + 'Endpoint');
        if (ep && !ep.value) applyProviderEndpoint(n);
        const prov = ($('refineS' + n + 'Provider') || {}).value;
        if (prov && r.key_status && r.key_status[prov]) {
          const inp = $('refineS' + n + 'Key');
          if (inp && prov !== 'lmstudio' && prov !== 'ollama')
            inp.placeholder = MSG.key_saved_placeholder;
        }
      }
      // v1.5 翻译服务快捷下拉回填（settings KV 键 service_quick）+ key 行联动
      if (r.settings && r.settings.service_quick && $('refineServiceQuick')) {
        $('refineServiceQuick').value = String(r.settings.service_quick);
      }
      // 2.1 翻译方向（D2026-0930-04 定案①）：回填方向与配套指令卡路径
      // （缺省 ja/zh/空——控件 HTML selected 即缺省，缺键不动）
      if (r.settings) {
        const dSrc = $('directionSource');
        const dTgt = $('directionTarget');
        if (dSrc && r.settings.direction_source) {
          dSrc.value = String(r.settings.direction_source);
        }
        if (dTgt && r.settings.direction_target) {
          dTgt.value = String(r.settings.direction_target);
        }
        const dC1 = $('directionCardS1');
        if (dC1 && r.settings.direction_card_s1 != null) {
          dC1.value = String(r.settings.direction_card_s1);
        }
        const dC3 = $('directionCardS3');
        if (dC3 && r.settings.direction_card_s3 != null) {
          dC3.value = String(r.settings.direction_card_s3);
        }
        // 净语配置目录回填（空串=未指定，走自动查找回落链）
        const ccd = $('refineCleanerConfig');
        if (ccd && r.settings.cleaner_config_dir != null) {
          ccd.value = String(r.settings.cleaner_config_dir);
          const show = $('refineCleanerConfigShow');
          if (show) show.value = ccd.value;
        }
        // 2.4.0 S2 首启引导（HRO-1 翻转句）：first_run marker 一次性消费——
        // 显示横幅后立即写惰性 marker（refine_save_stage_settings 空参=静默
        // no-op 不落盘，必须带 settings 实参；first_run_seen 对现有消费端惰性
        // 零污染），os.makedirs+json.dump 建档 → 次启 first_run=false 确定性
        // 翻转；写回失败仅 console 告警留痕（次启重播属可接受降级）。
        // first_run 非 true 时零动作；横幅保留至用户点击关闭（不自动消失）
        // 2.5.0 批5（D2026-1001-07）：AI 分析独立配置回填+生效显示
        // （C3：AI 设置写入会建档 → first_run 折叠为 false，已显性入设计；
        //   跟随态不写键、独立态才写，最小化建档面）
        const aiProvSel = $('aiProviderSel');
        const aiModelInput = $('aiModelInput');
        if (aiProvSel) {
          aiProvSel.value = (r.settings.ai_analyze_provider) || 'follow';
          // 2.5.0 批5：option/label 中文走 MSG（HTML 留英文占位，防未收编中文钉）
          const provOpts = { follow: MSG.ai_prov_follow, lmstudio: MSG.ai_prov_lmstudio, ollama: MSG.ai_prov_ollama, deepseek: MSG.ai_prov_deepseek, siliconflow: MSG.ai_prov_siliconflow, zen: MSG.ai_prov_zen };
          [...aiProvSel.options].forEach(o => { if (provOpts[o.value]) o.textContent = provOpts[o.value]; });
          const lblP = document.querySelector('label[for="aiProviderSel"]');
          if (lblP) lblP.textContent = MSG.ai_cfg_provider_label;
          const lblM = document.querySelector('label[for="aiModelInput"]');
          if (lblM) lblM.textContent = MSG.ai_cfg_model_label;
        }
        if (aiModelInput) {
          // 批3（D2026-1008-01）：模型文本框→下拉——回填改"follow 态单源
          // 应用（禁用+占位，刷新/测试按钮随禁）+ 独立态注入标记 option 后
          // 选中"（阶段页先例）；placeholder 语义随文本框一并退役
          savedAiModel = (r.settings.ai_analyze_model || '').trim();
          const aiFollow = !aiProvSel || aiProvSel.value === 'follow';
          aiModelApplyFollowState();
          if (!aiFollow) {
            if (savedAiModel
                && ![...aiModelInput.options].some(o => o.value === savedAiModel)) {
              const marker = document.createElement('option');
              marker.value = savedAiModel;
              marker.textContent = savedAiModel;
              aiModelInput.appendChild(marker);
            }
            if (savedAiModel) aiModelInput.value = savedAiModel;
          }
        }
        // P2（D2026-1008-02）：修复模型独立配置行已删除——batch_fix_* KV
        // 不再读写（旧键留在用户配置文件无害，不迁移）
        // 2.6.0 批2 修订（D2026-1002-05）：跨片统计窗口三档（填充/恢复/保存）
        const aggWin = $('aggregateWindowSel');
        if (aggWin) {
          if (!aggWin.dataset.filled) {
            aggWin.dataset.filled = '1';
            const winOpts = { 7: MSG.aggregateWindow7, 30: MSG.aggregateWindow30, all: MSG.aggregateWindowAll };
            Object.keys(winOpts).forEach(k => {
              const o = document.createElement('option');
              o.value = k;
              o.textContent = winOpts[k];
              aggWin.appendChild(o);
            });
            const lblW = document.querySelector('label[for="aggregateWindowSel"]');
            if (lblW) lblW.textContent = MSG.aggregateWindowLabel;
            aggWin.addEventListener('change', () => {
              window.pywebview.api.refine_save_stage_settings(null, null,
                { tm_stats_window: aggWin.value });
            });
          }
          aggWin.value = (r.settings.tm_stats_window) || '30';
        }
        if (aiProvSel && !aiProvSel.dataset.bound) {
          aiProvSel.dataset.bound = '1';
          const saveAiConfig = () => {
            window.pywebview.api.refine_save_stage_settings(null, null, {
              ai_analyze_provider: aiProvSel.value,
              ai_analyze_model: ((($('aiModelInput') || {}).value) || '').trim()
            }).then(rv => {
              if (!rv || rv.success !== true) console.warn('[refine] AI 分析设置保存失败');
            }).catch(e => console.warn('[refine] AI 分析设置保存失败', e));
          };
          // 批3（D2026-1008-01）：切 provider 只重置模型下拉空态（follow=
          // 禁用+占位，刷新/测试按钮随禁），不自动拉取（阶段页先例）
          aiProvSel.addEventListener('change', () => {
            aiModelApplyFollowState();
            saveAiConfig();
          });
          const aiModelSel = $('aiModelInput');
          if (aiModelSel) aiModelSel.addEventListener('change', saveAiConfig);
        }
        if (r.settings.first_run === true) {
          const banner = $('firstRunBanner');
          if (banner) {
            const txt = banner.querySelector('.first-run-text');
            const closeBtn = banner.querySelector('.first-run-close');
            if (txt) txt.textContent = MSG.first_run_guide;
            if (closeBtn) {
              closeBtn.textContent = MSG.ui_ok;
              if (!closeBtn.dataset.bound) {
                closeBtn.dataset.bound = '1';
                closeBtn.addEventListener('click', () => { banner.style.display = 'none'; });
              }
            }
            banner.style.display = '';
            pywebview.api.refine_save_stage_settings(null, null, { first_run_seen: true })
              .then((s) => {
                if (!s || s.success !== true) {
                  console.warn('[refine] first_run_seen 翻转写回失败（次启将重播引导横幅）:',
                    s && s.error);
                }
              })
              .catch((e) => console.warn('[refine] first_run_seen 翻转写回异常:', e));
          }
        }
      }
      refreshServiceQuickRow();
    } catch (e) { console.warn('[refine] 读取已保存接口配置失败', e); }
  }

  // 2.1 翻译方向控件持久化（D2026-0930-04 定案①）：change 即写 settings
  // 顶层字典（direction_* 四键），程序性回填 .value 不触发 change 不打架
  function bindDirectionControls() {
    const saveDirection = () => {
      pywebview.api.refine_save_stage_settings(null, null, {
        direction_source: ($('directionSource') || {}).value || 'ja',
        direction_target: ($('directionTarget') || {}).value || 'zh',
        direction_card_s1: ($('directionCardS1') || {}).value || '',
        direction_card_s3: ($('directionCardS3') || {}).value || ''
      }).catch((e) => console.warn('[refine] 翻译方向保存失败', e));
    };
    // input 防抖兜底程序化赋值（自动填充等）不触发 change 的场景
    let t = null;
    const saveDebounced = () => {
      clearTimeout(t);
      t = setTimeout(saveDirection, 400);
    };
    for (const id of ['directionSource', 'directionTarget',
                      'directionCardS1', 'directionCardS3']) {
      const el = $(id);
      if (!el) continue;
      el.addEventListener('change', saveDirection);   // select 即时保存保留
      el.addEventListener('input', saveDebounced);    // text input 双通道
    }
  }

  // 净语配置目录持久化（批1 D2026-0930-07 bug 修复：浏览/输入值经
  // settings 键 cleaner_config_dir 保存，重启由 applySavedStageSettings
  // 回填；trim 后空串=未指定，后端走 config/templates→包内默认回落链）
  function saveCleanerDir() {
    pywebview.api.refine_save_stage_settings(null, null, {
      cleaner_config_dir: (($('refineCleanerConfig') || {}).value || '').trim()
    }).catch((e) => console.warn('[refine] 净语配置目录保存失败', e));
  }

  // 与方向控件同款双通道：change 即存 + input 400ms 防抖兜底
  // （show 输入框当前 readonly，input 通道为防御性保留）
  function bindCleanerDirControls() {
    let t = null;
    const saveDebounced = () => {
      clearTimeout(t);
      t = setTimeout(saveCleanerDir, 400);
    };
    for (const id of ['refineCleanerConfig', 'refineCleanerConfigShow']) {
      const el = $(id);
      if (!el) continue;
      el.addEventListener('change', saveCleanerDir);
      el.addEventListener('input', saveDebounced);
    }
  }

  // ---- 兜底档位（v2：local=strict / cloud=lenient，无 UI 联动需求）----

  // ---- v1.5 翻译服务快捷下拉（tab-translate 页；原小白模式顶栏迁入）----
  // 本地提示行联动：本地 lmstudio/ollama 显示启动提示行，云服务隐藏。
  // （API Key 填写已收口至「引擎与模型」TAB，主页不再提供 key 输入域）
  function refreshServiceQuickRow() {
    const prov = ($('refineServiceQuick') || {}).value || '';
    const cloud = (prov === 'deepseek' || prov === 'siliconflow'
      || prov === 'custom');
    const hint = $('refineServiceQuickLocalHint');
    if (hint) hint.style.display = cloud ? 'none' : '';
    return cloud;
  }

  // 服务快捷下拉联动：同步引擎页阶段A/B provider（写 stage A 并同步
  // stage B），endpoint 缺省沿用 applyProviderEndpoint 既有映射（不新造）；
  // 持久化复用 saveStageEndpoints 的 stages 数组通道 + settings KV 键
  // service_quick（v1.5 由旧小白模式持久化键改名；回填在
  // applySavedStageSettings / pywebviewready 链路）
  function applyServiceQuickProvider(persist) {
    const prov = ($('refineServiceQuick') || {}).value || 'lmstudio';
    for (const n of [1, 3]) {
      const pv = $('refineS' + n + 'Provider');
      if (pv) pv.value = prov;
      // 与引擎页 provider change 行为一致：重置模型下拉为空态占位并填充
      // 缺省地址（批2 D2026-1002-12 拍板点2：不自动拉取模型列表）
      const sel = $('refineS' + n + 'Model');
      if (sel) {
        sel.innerHTML = modelEmptyOptionHTML();
      }
      applyProviderEndpoint(n);
    }
    refreshServiceQuickRow();
    if (persist && window.__pywebviewReady) {
      saveStageEndpoints();
      try {
        const p = window.pywebview && pywebview.api
          ? pywebview.api.refine_save_stage_settings(null, null,
              { service_quick: prov })
          : null;
        if (p && typeof p.catch === 'function') p.catch(() => {});
      } catch (e) { /* 静默降级 */ }
    }
  }

  // 反向同步（批1 D2026-0930-07）：引擎页阶段A/B provider 变化后刷新
  // 快捷条显示——A/B 一致且为快捷条已知选项时跟随显示该值；否则置空
  // （中性态）。只改显示不写 settings：engine 页 provider 的持久化仍走
  // 「保存接口」按钮通道，service_quick 键仅在快捷条自身变更时写。
  function syncServiceQuickFromStages() {
    const quick = $('refineServiceQuick');
    if (!quick) return;
    const p1 = ($('refineS1Provider') || {}).value || '';
    const p3 = ($('refineS3Provider') || {}).value || '';
    const known = [...quick.options].some(o => o.value === p1);
    quick.value = (p1 && p1 === p3 && known) ? p1 : '';
    refreshServiceQuickRow();
  }

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
  };

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

  // ---- 性暗示词替换（legacy 功能，已随 legacy 管线删除）----

  // ---- DOM 绑定（不依赖 pywebview 就绪）----
  function bindDom() {
    if (!$('refineStartBtn') || window.__refineBound) {
      if (!window.__refineBound) setTimeout(bindDom, 300);
      return;
    }
    window.__refineBound = true;

    $('refineStartBtn').addEventListener('click', () => TranslatorManager.startTranslation());
    $('refineCancelBtn').addEventListener('click', () => TranslatorManager.cancelTranslation());

    for (const n of [1, 3]) {
      // 批2（D2026-1002-12）：空态占位文案 JS 态填充（HTML 不挂静态 data-i18n）
      const msel = $('refineS' + n + 'Model');
      const mph = msel ? msel.querySelector('option[value=""]') : null;
      if (mph) mph.textContent = MSG.model_list_empty_hint;
      const rb = $('refineRefreshS' + n);
      if (rb) rb.addEventListener('click', () => refreshModels(n));
      const tb = $('refineTestS' + n);
      if (tb) tb.addEventListener('click', () => testStage(n));
      // 批2（D2026-1002-12 拍板点2）：切服务商不自动拉取模型列表，只认
      // 「刷新/测试」两个显式入口——此处仅重置空态占位并填充缺省地址
      const pv = $('refineS' + n + 'Provider');
      if (pv) pv.addEventListener('change', () => {
        const sel = $('refineS' + n + 'Model');
        if (sel) sel.innerHTML = modelEmptyOptionHTML();
        applyProviderEndpoint(n);
        syncServiceQuickFromStages();
      });
      const kb = $('refineSaveS' + n + 'KeyBtn');
      if (kb) kb.addEventListener('click', () => saveStageKey(n));
    }

    $('refreshFallbackModels').addEventListener('click', refreshFallbackModels);

    // 2.6.3 批C（D2026-1003-01 P4 IA 重排）：接口地址行迁段后，保存键拆为
    // 主键（#refineSaveEndpointsBtn，阶段A 段，携带状态 span）与阶段B 段
    // class-only 孪生按钮（无 id，零 id 预算消耗），两者绑同一 handler
    document.querySelectorAll('#refineSaveEndpointsBtn, .endpoint-save-twin')
      .forEach(b => b.addEventListener('click', saveStageEndpoints));

    // v1.5 翻译服务快捷下拉绑定（tab-translate 页）
    const quickProv = $('refineServiceQuick');
    if (quickProv) quickProv.addEventListener('change',
      () => applyServiceQuickProvider(true));
    // 「打开其他质量报告导读」：弹原生文件对话框选择导读 json
    // （D2026-0930-07 owner 痛点批，替代原粘贴路径行）；选中即走
    // guideLoad 显式路径链路，用户取消静默返回，无窗口/异常显示在状态 span
    const guideOtherBtn = $('guideOpenOtherBtn');
    if (guideOtherBtn) guideOtherBtn.addEventListener('click', async () => {
      if (!window.pywebview || !window.pywebview.api) {
        // 2.7.4 件1 收敛：错误回显唯一走 #guideStatus 状态行
        // （guideCustomStatus 已收敛为来源 chip，不承载错误文案）
        guideStatus(MSG.api_not_ready, true);
        return;
      }
      try {
        const r = await window.pywebview.api.refine_pick_guide_json();
        if (r && r.success && r.path) {
          guideLoad(false, r.path);
        } else if (!r || !r.cancelled) {
          // 用户取消（cancelled）静默返回；其余错误（如无活动窗口）显示在状态行，不弹窗
          guideStatus(
            MSG.guide_load_failed((r && r.error) || MSG.unknownError), true);
        }
      } catch (e) {
        guideStatus(MSG.guide_load_failed(
          e && e.message ? e.message : String(e)), true);
      }
    });

    // v1.5 左侧 TAB 栏绑定（SmartSub 式功能选择）
    document.querySelectorAll('.side-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // 2.6.5 段2（D2026-1004-01 #3）：引擎页 seg 分段控件已删除（三段改
    // stage-group 纵向堆叠，纯 CSS 布局零 JS 绑定），原绑定循环一并移除

    const glAddBtn = $('refineGlAdd');
    if (glAddBtn) glAddBtn.addEventListener('click', glAdd);
    // 2.5.0 修复D：高级参数阶段A/B 角色卡"去编辑"跳转（class 承载零 id 预算）
    document.querySelectorAll('.tpl-goto-btn').forEach((b) => {
      b.textContent = MSG.tpl_goto_edit;
      b.addEventListener('click', () => tplGotoEdit(b.dataset.tplStage));
    });
    // 学习词库只读刷新（词库与模板页）
    const glLearnedReload = $('glLearnedReloadBtn');
    if (glLearnedReload) glLearnedReload.addEventListener('click', glLearnedLoad);
    // 词库页区块折叠（2.1.1 owner 痛点批：默认展开；点标题或箭头按钮均可切换，
    // 会话内生效不持久化；刷新按钮等标题行内其余控件不受影响）
    document.querySelectorAll('.gl-collapsible').forEach(stack => {
      const btn = stack.querySelector('.gl-collapse-btn');
      const title = stack.querySelector('.gl-collapse-header .block-title');
      const toggle = () => {
        const collapsed = stack.classList.toggle('collapsed');
        if (btn) btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      };
      if (btn) {
        btn.setAttribute('aria-label', MSG.collapse_toggle);
        btn.addEventListener('click', (e) => { e.stopPropagation(); toggle(); });
      }
      if (title) title.addEventListener('click', toggle);
    });
    const glDelBtn = $('refineGlDel');
    if (glDelBtn) glDelBtn.addEventListener('click', glDel);
    const glImpBtn = $('refineGlImport');
    if (glImpBtn) glImpBtn.addEventListener('click', glImport);
    const glExpBtn = $('refineGlExport');
    if (glExpBtn) glExpBtn.addEventListener('click', glExport);
    const glSaveBtn = $('refineGlSave');
    if (glSaveBtn) glSaveBtn.addEventListener('click', glSave);

    // 2.6.3 批D（D2026-1003-01 P5）：编辑器整体迁入 AppModal.editor 模态——
    // 保存（#refineTemplateSave）/重新加载（#refineTemplateReload）/切阶段
    // （#refineTemplateStage change）改由 editor() 开态一次性绑定弹窗感知
    // 路径（脏确认守卫 + _edSaving 保存中禁关闭），原 bindDom 直绑
    // tplLoad / tplRefreshSelect(true) / tplSave 移除（既有绑定必要随改）。
    // 编辑器入口两枚（词库页+高级参数页）：class 承载零 id，文案 JS 态填充；
    // 入口行提示 span 复用既有键 tpl_explicit_card_hint（JS 态写入零静态消耗）
    document.querySelectorAll('.tpl-editor-entry-btn').forEach((b) => {
      b.textContent = MSG.tplOpenEditor;
      b.addEventListener('click', openTplEditor);
    });
    const tplEntryHint = document.querySelector('[data-testid="tpl-entry-hint"]');
    if (tplEntryHint) tplEntryHint.textContent = MSG.tpl_explicit_card_hint;
    const pickBtn = $('refinePickDirBtn');
    if (pickBtn) pickBtn.addEventListener('click', pickDir);

    // 角色卡目录打开按钮
    const openDirBtn = $('refineOpenDirBtn');
    if (openDirBtn) openDirBtn.addEventListener('click', () => {
      openDir($('refineTemplatesDir') ? $('refineTemplatesDir').value : '');
    });

    // 净语配置目录浏览按钮
    const pickCleanerBtn = $('refinePickCleanerDir');
    if (pickCleanerBtn) pickCleanerBtn.addEventListener('click', pickCleanerDir);

    // 净语配置目录打开按钮
    const openCleanerBtn = $('refineOpenCleanerDir');
    if (openCleanerBtn) openCleanerBtn.addEventListener('click', () => {
      openDir($('refineCleanerConfig') ? $('refineCleanerConfig').value : '');
    });

    // S3 引擎联动已随 v2 移除（原 updateS3EngineUI）
    // 性暗示词替换按钮已随 legacy 管线删除

    // 质量报告导读查看器（W1b）
    const guideBtn = $('refineGuideLoadBtn');
    if (guideBtn) guideBtn.addEventListener('click', () => guideLoad(false));
    // AI 质量分析（D2026-0929）
    const aiBtn = $('refineAiAnalyzeBtn');
    if (aiBtn) aiBtn.addEventListener('click', () => refineAiAnalyze());
    // 批3 补刀（D2026-1002-12 空载复测）：AI 分析区顶置标签中文填充
    // （HTML 英文留兜底；三键均既有，绑 DOM 即填不依赖设置回填路径，
    //   设置回填路径的同名填充保留为幂等二次写）
    const aiCfgLabels = { aiProviderSel: 'ai_cfg_provider_label',
                          aiModelInput: 'ai_cfg_model_label',
                          aggregateWindowSel: 'aggregateWindowLabel' };
    Object.keys(aiCfgLabels).forEach((k) => {
      const lbl = document.querySelector('label[for="' + k + '"]');
      if (lbl) lbl.textContent = MSG[aiCfgLabels[k]];
    });
    // 批3（D2026-1008-01）：分析模型三件套接线（文案/图标 JS 态填充，
    // 绑 DOM 即填不依赖设置回填路径；follow 缺省态单源应用）
    const aiRow = document.querySelector('.ai-config-row');
    if (aiRow) {
      const aiRefreshBtn = aiRow.querySelector('.ai-model-refresh');
      const aiTestBtn = aiRow.querySelector('.ai-model-test');
      if (aiRefreshBtn) {
        aiRefreshBtn.title = MSG.refresh_model_title;
        aiRefreshBtn.innerHTML = MODEL_REFRESH_SVG;
        aiRefreshBtn.addEventListener('click', () => refreshAnalysisModels());
      }
      if (aiTestBtn) {
        aiTestBtn.title = MSG.test_stage_title;
        aiTestBtn.textContent = MSG.test_stage_btn;
        aiTestBtn.addEventListener('click', () => testAnalysisModel());
      }
      aiModelApplyFollowState();
      const aiProvBind = $('aiProviderSel');
      if (aiProvBind && !aiProvBind.dataset.trioBound) {
        aiProvBind.dataset.trioBound = '1';
        aiProvBind.addEventListener('change', () => aiModelApplyFollowState());
      }
    }
    // P2（D2026-1008-02）：修复模型独立配置行接线随删行退役——修复生效
    // 模型唯一来源=分析独立配置（analyzeResolution 单源），旧 batch_fix_*
    // KV 不再读写
    // 质量闭环一键批次修复（2.6.0 批1）
    const bfBtn = $('refineBatchFixBtn');
    if (bfBtn) bfBtn.addEventListener('click', () => batchFixRun());
    // 3.0 批2：一键回滚按钮（文案 JS 态填充零静态键；导读 json 就绪后
    // 由 batchFixRefresh 显隐）
    const rbBind = document.querySelector('.fullchain-rollback-btn');
    if (rbBind) {
      rbBind.textContent = MSG.fullchainRollbackBtn;
      rbBind.addEventListener('click', () => fullchainRollbackRun());
    }
    // ASR 模型管理（2.6.0 批3；批2 D2026-1002-12 卡重整：空态/说明/占位文案
    // JS 态填充，HTML 不留英文占位）
    const asrBtn = $('asrRefreshBtn');
    if (asrBtn) {
      const t = asrBtn.querySelector('span');
      if (t) t.textContent = MSG.asrRefreshBtn;
      asrBtn.addEventListener('click', () => asrRefresh(true));   // 强制刷新（绕过快照缓存）
    }
    const asrEnv = $('asrEnvStatus');
    if (asrEnv) asrEnv.textContent = MSG.asr_env_undetected;
    // 2.7.1：模型管理面板入口（.asr-models-btn class 锚，零新增 id）
    const asrModelsBtn = document.querySelector('.asr-models-btn');
    if (asrModelsBtn) {
      const t = asrModelsBtn.querySelector('span');
      if (t) t.textContent = MSG.asrModelsBtn;
      asrModelsBtn.addEventListener('click', () => asrOpenModelsPanel());
    }
    const asrSelPh = $('asrModelSel');
    if (asrSelPh) {
      const ph = asrSelPh.querySelector('option[value=""]');
      if (ph) ph.textContent = MSG.asrSelectPlaceholder;
    }
    // 批3 扩展（D2026-1002-12）：系统状态卡 ASR 行「重新探测」事件委托——
    // 行由 SystemSummary 动态渲染（零新增静态 id），委托绑卡上按
    // data-sys-action 分流；首屏不自动探测（上游 selfcheck 慢）
    const sysCard = $('systemSummaryCard');
    if (sysCard) sysCard.addEventListener('click', (e) => {
      if (e.target.closest('[data-sys-action="asr-probe"]')) {
        SystemSummary.probeAsr();
      }
    });
    // 2.6.1 修订（D2026-1002-06）：验证开关 + 上游 Python 路径（下载按钮删除）；
    // 批2：asrSaved 仅在保存成功后写入（失败透出错误，与空态占位区分）
    const asrTgl = $('asrCrosscheckToggle');
    if (asrTgl) {
      const lbl = asrTgl.parentElement
        ? asrTgl.parentElement.querySelector('span') : null;
      if (lbl) lbl.textContent = MSG.asrCrosscheckLabel;
      // 2.7.1：入口说明独立行删除，说明文案并入开关 title 悬停
      asrTgl.title = MSG.asrCrosscheckTitle;
      asrTgl.addEventListener('change', async () => {
        if (!window.pywebview || !window.pywebview.api) return;
        try {
          const r = await window.pywebview.api.refine_save_stage_settings(
            null, null,
            { media_crosscheck_enabled: asrTgl.checked ? '1' : '0' });
          asrStatus(r && r.success ? MSG.asrSaved
            : '❌ ' + ((r && r.error) || MSG.unknown));
        } catch (e) {
          asrStatus('❌ ' + e);
        }
      });
    }
    const asrPy = $('asrPythonInput');
    if (asrPy) {
      asrPy.placeholder = MSG.asrPythonPlaceholder;
      asrPy.title = MSG.asrPythonPlaceholder;
      asrPy.addEventListener('change', async () => {
        if (!window.pywebview || !window.pywebview.api) return;
        try {
          const r = await window.pywebview.api.refine_save_stage_settings(
            null, null, { asr_python: asrPy.value.trim() });
          asrStatus(r && r.success ? MSG.asrSaved
            : '❌ ' + ((r && r.error) || MSG.unknown));
        } catch (e) {
          asrStatus('❌ ' + e);
        }
      });
    }
    const asrSel = $('asrModelSel');
    if (asrSel) asrSel.addEventListener('change', async () => {
      if (!window.pywebview || !window.pywebview.api) return;
      // 2.7.3 件③（评议员条件⑥）：占位空值不保存、不覆盖既有 saved_model
      // （占位项恰为当前选中时用户点选=空操作）
      if (asrSel.value === '') return;
      try {
        const r = await window.pywebview.api.refine_save_stage_settings(
          null, null, { asr_model: asrSel.value });
        asrStatus(r && r.success ? MSG.asrSaved
          : '❌ ' + ((r && r.error) || MSG.unknown));
      } catch (e) {
        asrStatus('❌ ' + e);
      }
    });

    // 快速试听（D2026-0929-09）：条目试听按钮事件委托 + 浮层关闭 +
    // 媒体来源条「更换」展开 + 覆盖路径应用
    const guideItemsEl = $('guideItems');
    if (guideItemsEl) guideItemsEl.addEventListener('click', (e) => {
      const btn = e.target.closest('.btn-audio-preview');
      if (btn) openAudioPreview(btn.dataset.timing);
    });
    const pvCloseBtn = $('audioPreviewCloseBtn');
    if (pvCloseBtn) pvCloseBtn.addEventListener('click', closeAudioPreview);
    // C4（D2026-1007-02）：direct 播放失败可见化——audio error 监听入独立
    // 错误槽（no-src guard 照抄 review.js：showPreviewError/closeAudioPreview
    // 清 src 触发的无源 error 忽略，防幽灵红字闪回）
    const pvPlayer = $('audioPreviewPlayer');
    if (pvPlayer) pvPlayer.addEventListener('error', () => {
      if (!pvPlayer.getAttribute('src')) return;
      console.error('[guide] audio preview error:',
        (pvPlayer.error && pvPlayer.error.code) || 'unknown');
      showPreviewError(MSG.audio_preview_play_error, '');
    });
    const msToggleBtn = $('mediaSourceToggleBtn');
    if (msToggleBtn) msToggleBtn.addEventListener('click', () => {
      const row = $('mediaSourceEditRow');
      if (row) row.style.display =
        row.style.display === 'none' ? '' : 'none';
    });
    const msApplyBtn = $('mediaOverrideApplyBtn');
    if (msApplyBtn) msApplyBtn.addEventListener('click', () => {
      const inp = $('mediaOverrideInput');
      const st = $('mediaOverrideStatus');
      mediaOverridePath = inp && inp.value.trim() ? inp.value.trim() : '';
      if (st) {
        st.textContent = mediaOverridePath
          ? MSG.media_override_applied : MSG.media_override_cleared;
      }
      // 2.7.4 件2：override 变更 → 推断缓存失效；显式路径持久化写入
      // （media_overrides KV，空串=删除该条；失败静默——会话内覆盖已生效）
      delete inferredMediaCache[lastLoadedGuidePath];
      if (lastLoadedGuidePath && window.pywebview
          && window.pywebview.api
          && window.pywebview.api.refine_save_media_override) {
        try {
          window.pywebview.api.refine_save_media_override(
            lastLoadedGuidePath, mediaOverridePath).catch(() => {});
        } catch (e) { /* 桥缺席静默（会话内覆盖已生效） */ }
      }
      updateMediaSourceBar(lastGuideData);
    });

    // 数据保存目录（高级参数页）：浏览选择目录（与角色卡同款原生目录对话框）
    const drToggleBtn = $('dataRootToggleBtn');
    if (drToggleBtn) drToggleBtn.addEventListener('click', dataRootBrowse);
    const drRestoreBtn = $('dataRootRestoreBtn');
    if (drRestoreBtn) drRestoreBtn.addEventListener('click',
      () => dataRootSave(''));
  }

  // ---- 数据保存目录（高级参数页；pointer 写入 .data-root，重启应用后生效）----
  function dataRootSourceLabel(src) {
    const k = 'data_root_source_' + (src || '');
    return typeof MSG[k] === 'string' ? MSG[k] : (src || '');
  }
  function dataRootLoad() {
    if (!window.pywebview || !pywebview.api ||
        !pywebview.api.refine_get_data_root) return;
    pywebview.api.refine_get_data_root().then(r => {
      if (!r || !r.success) return;
      const pathEl = $('dataRootCurrentPath');
      const tagEl = $('dataRootSourceTag');
      // P1-9 格14②（D2026-1015-05）覆写核验：成功回包但 data_root 为空串时
      // 会覆写掉静态「—」占位 → 补占位兜底保持语义（失败分支已提前 return，
      // 静态占位天然保留）。「—」与 index.html 占位同字面，零新键。
      if (pathEl) pathEl.textContent = r.data_root || '—';
      if (tagEl) tagEl.textContent = dataRootSourceLabel(r.source);
    }).catch(() => {});
  }
  async function dataRootBrowse() {
    const st = $('dataRootStatus');
    try {
      const r = await pywebview.api.refine_pick_folder();
      if (!r || !r.success || !r.path) return; // 取消/失败静默返回
      const cur = $('dataRootCurrentPath');
      if (cur && cur.textContent && cur.textContent === r.path) {
        if (st) st.textContent = MSG.data_root_unchanged;
        return;
      }
      await dataRootSave(r.path);
    } catch (e) {
      if (st) st.textContent = String(e);
    }
  }
  async function dataRootSave(value) {
    const st = $('dataRootStatus');
    try {
      const r = await pywebview.api.refine_set_data_root(value || '');
      if (st) {
        st.textContent = (r && r.success)
          ? (value ? MSG.data_root_saved_restart
                   : MSG.data_root_default_restored)
          : ((r && r.error) || '');
      }
      if (r && r.success) {
        dataRootLoad();
        // 批1a 件5：数据根变更后阻断式提示（AppModal 模态须点确认关闭；
        // 重启前后续写入仍落旧根的说明随文案带出）
        await AppModal.alert(MSG.data_root_restart_title,
                             MSG.data_root_restart_body);
      }
    } catch (e) {
      if (st) st.textContent = String(e);
    }
  }

  // ---- 词典管理（2.1 引擎页三区块：日/中/英 状态/下载/路径）----
  const DICT_KINDS = [
    { kind: 'sudachi', label: MSG.dict_sudachi_label,
      desc: MSG.dict_sudachi_desc, downloadable: true },
    { kind: 'sudachi_full', label: MSG.dict_sudachi_full_label,
      desc: MSG.dict_sudachi_full_desc, downloadable: true },
    { kind: 'jieba', label: MSG.dict_jieba_label,
      desc: MSG.dict_jieba_desc, downloadable: false },
    { kind: 'english_rules', label: MSG.dict_english_label,
      desc: MSG.dict_english_desc, downloadable: false },
  ];
  // 修复A：词典卡分母单一事实源——顶层 SystemSummary 经此桥取 DICT_KINDS 长度
  window.AppDictKindsCount = DICT_KINDS.length;
  // 词典状态缓存（B2 案批3）：dictLoad 拉取后写入，dictSelect change 复渲染读取
  let _dictStatusCache = {};
  let _dictDirCache = '';
  // 下载中词典占位（2.6.5 段2 D2026-1004-01 #5「下载中禁整行」收口：
  // code-review 发现下载中切词典→dictRenderDetail 重渲染复位共享操作行，
  // 可对另一 kind 并发发起下载——以模块级占位在渲染与入口双端钉死）
  let _dictBusyKind = null;
  // 2.7.3 件⑤（词典下载停止按钮）：停止中过渡态标记 + 请求时刻（过渡
  // 兜底量纲用）。停止过渡期 _dictBusyKind 保持占用直到终态（防提前
  // 解锁邀请重下——与后端 HRO-1.3「不乐观写 stopped 快照」对齐）
  let _dictStopPending = false;
  let _dictStopRequestedAt = 0;
  // 过渡兜底显式常数（评议员条件③）：单分块 socket 超时 10s（后端
  // opener.open timeout=10，停止信号最迟等当前 1MB 分块读返回才到检查
  // 点）+ 2 拍轮询间隔（实测轮询 1000ms/拍）；超时未见终态→本地按失败
  // 收口（后端线程终会写 stopped 快照，后续状态查询自纠）
  const DICT_STOP_GRACE_MS = 10000 + 2000;
  // 批1b 件1/件2：自定义词典目录态（custom_dir=设置值|null；
  // needs_migration/old_dir=选新目录后由 refine_pick_dict_dir 返回的迁移提示）
  let _dictCustomDir = null;
  let _dictNeedsMigration = false;
  let _dictOldDir = '';
  // 2.6.3 批B（D2026-1003-06 条件②）：源摘要缓存（{kind: {has_official,
  // has_mirror}}），「仅镜像」键 disabled 门控读取
  let _dictSourcesCache = {};
  // 2.6.5 段2（D2026-1004-01 #4）：四 kind 摘要行展示序=日语·中文·英文·
  // 完整版（owner 定夺，独立于 DICT_KINDS 数组序）
  const DICT_KIND_DISPLAY_ORDER = ['sudachi', 'jieba', 'english_rules',
    'sudachi_full'];
  // 四 kind 状态摘要行（空态三件套①）：全 createElement 零静态 id；实心点=
  // 已装（--ok）/空心=未装（--text-3）/内置 english_rules=primary 点；
  // 完整版 chip title「与日语二选一」；点击 chip→切 #dictSelect 并刷新详情
  function _dictEnsureKindRow() {
    const box = $('dictRows');
    if (!box || box.querySelector('.dict-kind-row')) return;
    const row = document.createElement('div');
    row.className = 'dict-kind-row';
    DICT_KIND_DISPLAY_ORDER.forEach(kind => {
      const item = DICT_KINDS.find(k => k.kind === kind) || {};
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'dict-kind-chip';
      chip.dataset.kind = kind;
      const dot = document.createElement('span');
      dot.className = 'dot';
      chip.appendChild(dot);
      chip.appendChild(document.createTextNode(item.label || kind));
      if (kind === 'sudachi_full') chip.title = MSG.dict_sudachi_full_chip_title;
      chip.addEventListener('click', () => {
        const sel = $('dictSelect');
        if (sel && sel.value !== kind) {
          sel.value = kind;
          _dictRefreshKindRow();
          _dictRefreshHint();              // 与下拉 change 同路径：hint 显隐随词典切换
          dictRenderDetail();
        }
      });
      row.appendChild(chip);
    });
    box.insertBefore(row, box.firstChild);
  }
  // chip 状态刷新：active=当前选中词典；on/builtin=安装态（点色）
  function _dictRefreshKindRow() {
    const row = document.querySelector('#dictRows .dict-kind-row');
    const sel = $('dictSelect');
    if (!row || !sel) return;
    row.querySelectorAll('.dict-kind-chip').forEach(chip => {
      const kind = chip.dataset.kind;
      const info = _dictStatusCache[kind] || {};
      chip.classList.toggle('active', sel.value === kind);
      chip.classList.toggle('on',
        !!(info.available && kind !== 'english_rules'));
      chip.classList.toggle('builtin', kind === 'english_rules');
    });
  }
  // warn-soft 提示条（空态三件套②，空态三件套承载原 #dictEmpty 后果语义）
  function _dictEnsureHint() {
    const box = $('dictRows');
    if (!box || box.querySelector('.dict-install-hint')) return;
    const hint = document.createElement('div');
    hint.className = 'dict-install-hint';
    hint.style.display = 'none';
    hint.textContent = MSG.dict_install_hint;
    const kindRow = box.querySelector('.dict-kind-row');
    if (kindRow) box.insertBefore(hint, kindRow.nextSibling);
    else box.insertBefore(hint, box.firstChild);
  }
  // hint 条显隐：仅当前选中 kind downloadable&&!available 时显示
  function _dictRefreshHint() {
    const box = $('dictRows');
    const hint = box ? box.querySelector('.dict-install-hint') : null;
    const sel = $('dictSelect');
    if (!hint || !sel) return;
    const kind = sel.value;
    const item = DICT_KINDS.find(k => k.kind === kind) || {};
    const info = _dictStatusCache[kind] || {};
    hint.style.display = (item.downloadable && !info.available) ? '' : 'none';
  }
  // 2.6.5 段2（D2026-1004-01 #6）：失败一行人话映射——校验失败/网络失败
  // 短句（诊断数据来自后端 failed 快照 diag 字段，段1 已落契约），磁盘/
  // 未知沿用原文；技术串下沉 details 诊断网格
  function dictFailureText(error, diag) {
    if (/SHA256/.test(error)) return MSG.dict_fail_checksum;
    if (diag && (diag.url || diag.attempts)) return MSG.dict_fail_network;
    return error || MSG.dict_download_failed;
  }
  // 状态行统一出口：isErr=true 加 status-err 红 + 技术详情 <details> 网格
  // （重渲染前清空旧 details；诊断值一律 TextNode 禁 innerHTML；URL 行带
  // 复制键，file:// clipboard 被拒降级为点击全选该值）
  function dictShowStatus(st, text, isErr, diag) {
    if (!st) return;
    st.textContent = text || '';
    st.classList.toggle('status-err', !!isErr);
    const card = st.parentElement;
    if (card) {
      const old = card.querySelector('.dict-diag');
      if (old) old.remove();
    }
    if (!isErr || !diag || typeof diag !== 'object') return;
    const details = document.createElement('details');
    details.className = 'dict-diag';
    const summary = document.createElement('summary');
    const chev = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    chev.setAttribute('viewBox', '0 0 24 24');
    chev.setAttribute('width', '14');
    chev.setAttribute('height', '14');
    chev.setAttribute('fill', 'none');
    chev.setAttribute('stroke', 'currentColor');
    chev.setAttribute('stroke-width', '2');
    chev.setAttribute('stroke-linecap', 'round');
    chev.setAttribute('stroke-linejoin', 'round');
    chev.setAttribute('aria-hidden', 'true');
    const chevPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    chevPath.setAttribute('d', 'm9 18 6-6-6-6');
    chev.appendChild(chevPath);
    summary.appendChild(chev);
    summary.appendChild(document.createTextNode(MSG.dict_diag_summary));
    details.appendChild(summary);
    const grid = document.createElement('div');
    grid.className = 'dict-diag-grid';
    // 字段按存在性逐行降级（proxy 取值=段1 定稿 "system"/"direct"）
    const addRow = (label, value) => {
      const k = document.createElement('span');
      k.className = 'k';
      k.textContent = label;
      const v = document.createElement('span');
      v.className = 'v';
      v.textContent = value;
      grid.appendChild(k);
      grid.appendChild(v);
      return v;
    };
    const defined = (x) => x !== undefined && x !== null && x !== '';
    if (defined(diag.expected_bytes))
      addRow(MSG.dict_diag_expected_bytes, String(diag.expected_bytes));
    if (defined(diag.actual_bytes))
      addRow(MSG.dict_diag_actual_bytes, String(diag.actual_bytes));
    if (defined(diag.content_encoding))
      addRow(MSG.dict_diag_encoding, String(diag.content_encoding));
    if (defined(diag.part_prefix_hex))
      addRow(MSG.dict_diag_part_hex, String(diag.part_prefix_hex));
    if (defined(diag.url)) {
      const v = addRow(MSG.dict_diag_url, String(diag.url));
      const copy = document.createElement('button');
      copy.type = 'button';
      copy.className = 'copy';
      copy.textContent = MSG.dict_diag_copy;
      copy.addEventListener('click', () => {
        const flash = (t) => {
          copy.textContent = t;
          setTimeout(() => { copy.textContent = MSG.dict_diag_copy; }, 1500);
        };
        const selectAll = () => {
          try {
            const range = document.createRange();
            range.selectNodeContents(v);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
          } catch (e) { /* ignore */ }
          flash(MSG.dict_diag_selected);
        };
        try {
          navigator.clipboard.writeText(String(diag.url)).then(
            () => flash(MSG.ui_copied), selectAll);
        } catch (e) {
          selectAll();
        }
      });
      v.appendChild(copy);
    }
    if (defined(diag.proxy))
      addRow(MSG.dict_diag_proxy,
        diag.proxy === 'system' ? MSG.dict_diag_proxy_system
          : diag.proxy === 'direct' ? MSG.dict_diag_proxy_direct
            : String(diag.proxy));
    if (defined(diag.attempts))
      addRow(MSG.dict_diag_attempts, String(diag.attempts));
    details.appendChild(grid);
    if (card) card.insertBefore(details, st.nextSibling);
  }
  function dictLoad() {
    const box = $('dictRows');
    if (!box || !window.pywebview || !pywebview.api ||
        !pywebview.api.refine_dict_status) return;
    pywebview.api.refine_dict_status().then(r => {
      if (!r || !r.success) {
        const st = $('dictStatus');
        // 2.6.5 段2（D2026-1004-01 #6）：加载失败也红（status-err）
        if (st) dictShowStatus(st,
          `${MSG.dict_load_failed}${r && r.error ? '：' + r.error : ''}`,
          true, null);
        return;
      }
      _dictStatusCache = (r && r.dicts) || {};
      _dictDirCache = (r && r.effective_dir) || (r && r.dict_dir) || '';
      _dictCustomDir = (r && r.custom_dir) || null;
      _dictSourcesCache = (r && r.sources) || {};
      // 2.6.5 段2（D2026-1004-01 #4）：#dictEmpty 空态引导条已删（C2 决议
      // 反转记档，FROZEN_IDS 215→214 显式解冻）——空态语义由四 kind 摘要
      // 行 + pill-warning「未安装」+ warn-soft hint 条承接
      _dictEnsureKindRow();
      // 下拉填充（label=词典名，可用性由状态行/chip 承载去重复），
      // change→详情刷新（静态骨架只填充不建行）
      const sel = $('dictSelect');
      if (sel) {
        sel.innerHTML = '';
        DICT_KINDS.forEach(item => {
          const opt = document.createElement('option');
          opt.value = item.kind;
          opt.textContent = item.label;
          sel.appendChild(opt);
        });
        if (!sel.dataset.bound) {          // 一次性绑定，数据经缓存读取防陈旧闭包
          sel.dataset.bound = '1';
          sel.addEventListener('change', () => {
            _dictRefreshKindRow();
            _dictRefreshHint();            // 黑盒缺陷#1 修复：切词典须同步 hint 显隐
            dictRenderDetail();            // （否则 downloadable→非 downloadable 残留误导文案）
          });
        }
      }
      _dictEnsureHint();
      _dictRefreshKindRow();
      _dictRefreshHint();
      // 打开文件夹（R3：复用现成 openDir(path)→open_output_folder 链，零新 API）
      const openBtn = $('dictOpenDir');
      if (openBtn && !openBtn.dataset.bound) {
        openBtn.dataset.bound = '1';
        openBtn.addEventListener('click', () => openDir($('dictPath') && $('dictPath').textContent));
      }
      // 批1b 件1/件2：目录行三键一次性绑定（浏览/恢复默认/迁移；
      // 标签 JS 态 MSG 键填充，与 dictActionBtn 同款空 HTML 骨架）
      const browseBtn = $('dictBrowseBtn');
      if (browseBtn && !browseBtn.dataset.bound) {
        browseBtn.dataset.bound = '1';
        browseBtn.textContent = MSG.data_root_change_btn;
        browseBtn.addEventListener('click', dictPickDir);
      }
      const restoreBtn = $('dictRestoreBtn');
      if (restoreBtn && !restoreBtn.dataset.bound) {
        restoreBtn.dataset.bound = '1';
        restoreBtn.textContent = MSG.data_root_restore_btn;
        restoreBtn.addEventListener('click', dictRestoreDir);
      }
      const migBtn = $('dictMigrateBtn');
      if (migBtn && !migBtn.dataset.bound) {
        migBtn.dataset.bound = '1';
        migBtn.textContent = MSG.dict_migrate_btn;
        migBtn.addEventListener('click', () => dictMigrate());
      }
      dictRenderDetail();
    }).catch((e) => {
      const st = $('dictStatus');
      // 2.6.5 段2（D2026-1004-01 #6）：加载异常也红（status-err）
      if (st) dictShowStatus(st, MSG.dict_load_failed + '：' + String(e),
        true, null);
    });
  }
  function dictRenderDetail() {
    const detail = $('dictDetail');
    const sel = $('dictSelect');
    if (!detail || !sel) return;
    const kind = sel.value || (DICT_KINDS[0] && DICT_KINDS[0].kind);
    const info = _dictStatusCache[kind] || {};
    const item = DICT_KINDS.find(k => k.kind === kind) || {};
    detail.style.display = '';
    // 状态 pill 四态（2.6.5 段2 D2026-1004-01 定表）：available&&english_rules
    // →「内置」/available→「可用」/!available&&downloadable→新 JS 态键
    // 「未安装」+pill-warning（删 inline style hack）/其余→「不可用」
    // （jieba 未装落此格）
    const pill = $('dictPill');
    if (pill) {
      const dlItem0 = DICT_KINDS.find(k => k.kind === kind) || {};
      if (info.available) {
        pill.textContent = kind === 'english_rules'
          ? MSG.dict_status_builtin : MSG.dict_status_available;
        pill.className = 'pill pill-success';
      } else if (dlItem0.downloadable) {
        pill.textContent = MSG.dict_status_not_installed;
        pill.className = 'pill pill-warning';
      } else {
        pill.textContent = MSG.dict_status_unavailable;
        pill.className = 'pill';
      }
      pill.style.color = '';
    }
    const desc = $('dictDesc');
    if (desc) {
      desc.textContent = info.description || item.desc || '';
      desc.title = desc.textContent;
    }
    // 安装目录行（批1b：dict_dir=现生效目录，悬停 title 全文）+ 目录行按钮
    const path = $('dictPath');
    if (path) {
      path.textContent = _dictDirCache;
      path.title = _dictDirCache;       // 悬停全文（长路径截断可读）
    }
    const pathRow = $('dictPathRow');
    if (pathRow) pathRow.style.display = '';
    // 恢复默认键：仅设置了自定义目录时显示
    const restoreBtn = $('dictRestoreBtn');
    if (restoreBtn) restoreBtn.style.display = _dictCustomDir ? '' : 'none';
    // 迁移键：仅更改目录且旧目录有词典文件时显示（迁移成功/恢复默认后隐藏）
    const migBtn = $('dictMigrateBtn');
    if (migBtn) migBtn.style.display = _dictNeedsMigration ? '' : 'none';
    // R2 三态门控：可下载 kind（sudachi/sudachi_full）未装=primary「下载」/
    // 已装=ghost「重新下载」；jieba 无按钮只显 desc 指引（downloadable=false）；
    // english 恒内置隐藏按钮（修复A：下载门泛化由 DICT_KINDS.downloadable 驱动）
    const btn = $('dictActionBtn');
    const dlItem = DICT_KINDS.find(k => k.kind === kind) || {};
    if (btn) {
      if (dlItem.downloadable) {
        btn.style.display = '';
        btn.className = info.available ? 'btn btn-ghost btn-compact' : 'btn btn-primary btn-compact';
        btn.textContent = info.available ? MSG.dict_redownload : MSG.dict_download;
      } else {
        btn.style.display = 'none';
        btn.textContent = '';
      }
      // 一次性 click 绑定（静态 DOM 不重建，dataset.bound 防重复挂监听）；
      // 2.7.3 件⑤ 四态分派：下载中=主按钮已转停止键（调停止端点），
      // 空闲=发起下载。回调读当前 sel.value 保证通用性
      if (!btn.dataset.bound) {
        btn.dataset.bound = '1';
        btn.addEventListener('click', () => {
          if (_dictBusyKind) {
            dictRequestStop($('dictSelect').value, btn);
          } else {
            dictDownload($('dictSelect').value, btn);
          }
        });
      }
      // 源选择双按钮（2.6.3 批B，D2026-1003-06 条件②①）：JS 注入零 id
      // （FROZEN_IDS 冻结）。2.6.5 段2（D2026-1004-01 #5 收单操作行 路线1）：
      // #dictActionBtn 已静态入 .dict-action-row 包裹层（无内层 group），
      // 注入序修正为 官方│镜像（原 镜像│官方）；行首「下载源」前缀标签走
      // JS 态 MSG（禁 index.html 静态中文）；无操作 kind 整行隐藏不留空行
      const row = btn.parentElement;
      if (row && dlItem.downloadable) {
        row.style.display = '';
        let srcLabel = row.querySelector('.dict-src-label');
        if (!srcLabel) {
          srcLabel = document.createElement('span');
          srcLabel.className = 'dict-src-label';
          srcLabel.textContent = MSG.dict_download_source;
          row.insertBefore(srcLabel, row.firstChild);
        }
        let offBtn = row.querySelector('.dict-src-official');
        if (!offBtn) {
          offBtn = document.createElement('button');
          offBtn.type = 'button';
          offBtn.className = 'btn btn-ghost btn-compact dict-src-official';
          offBtn.textContent = MSG.dictSrcOfficialOnly;
          offBtn.title = MSG.dictSrcOfficialHint;   // CN 可达性提示
          offBtn.addEventListener('click', () =>
            dictDownload($('dictSelect').value, offBtn, 'official'));
          row.insertBefore(offBtn, btn);
        }
        let mirBtn = row.querySelector('.dict-src-mirror');
        if (!mirBtn) {
          mirBtn = document.createElement('button');
          mirBtn.type = 'button';
          mirBtn.className = 'btn btn-ghost btn-compact dict-src-mirror';
          mirBtn.textContent = MSG.dictSrcMirrorOnly;
          mirBtn.addEventListener('click', () =>
            dictDownload($('dictSelect').value, mirBtn, 'mirror'));
          row.insertBefore(mirBtn, btn);   // 插入序=官方│镜像│主下载键
        }
        offBtn.style.display = '';
        mirBtn.style.display = '';
        // 无镜像 kind（sudachi_full=官方 CDN 单源）→ disabled + 离线导入指引
        const srcInfo = _dictSourcesCache[kind] || {};
        const hasMirror = srcInfo.has_mirror !== false;
        mirBtn.disabled = !hasMirror;
        mirBtn.title = hasMirror ? '' : MSG.dictSrcMirrorlessHint;
        // 下载中禁整行（跨 kind 切换洞收口，见 _dictBusyKind 注）：任一词典
        // 下载进行中，无论当前选中谁，整行三键禁用+is-busy——切走的用户看到
        // 禁用态，切回下载中的 kind 也不会误读为可重入；终态由 finally 的
        // dictLoad() 重渲染自然解除
        if (_dictBusyKind) {
          row.classList.add('is-busy');
          btn.disabled = true;
          offBtn.disabled = true;
          mirBtn.disabled = true;
        } else {
          row.classList.remove('is-busy');
        }
      } else if (row) {
        // 无操作 kind（jieba/english_rules，无下载按钮/无源组）：整行隐藏
        row.style.display = 'none';
      }
    }
  }
  async function dictDownload(kind, btn, source) {
    const st = $('dictStatus');
    // 下载中占位（D2026-1004-01 #5 跨 kind 并发洞收口）：已有下载进行中
    // 直接拒绝重入（按钮禁用态是第一道，此处兜底防编程态/竞态双击）
    if (_dictBusyKind) return;
    _dictBusyKind = kind;
    _dictStopPending = false;         // 件⑤：新会话复位停止过渡态
    // 终态按钮文案（2.6.3 批B）：双按钮路径恢复各自标签，主按钮恢复「下载」
    const doneLabel = source === 'official' ? MSG.dictSrcOfficialOnly
      : source === 'mirror' ? MSG.dictSrcMirrorOnly : MSG.dict_download;
    // 进度迁移（2.3.1 批1）：实时进度显示在详情区独立进度条 #dictProgress，
    // #dictStatus 降级为终态行+错误兜底（轮询中的 MB 文本不再写 #dictStatus）
    const prog = $('dictProgress');
    const bar = prog ? prog.querySelector('.progress-bar') : null;
    const fill = prog ? prog.querySelector('.progress-fill') : null;
    const text = prog ? prog.querySelector('.progress-text') : null;
    const showProgress = (visible) => { if (prog) prog.style.display = visible ? '' : 'none'; };
    const fmtMB = (n) => (n / 1048576).toFixed(1);
    // 每次轮询按 p.phase 全量刷新进度条状态（相位往返安全：切换须重置旧态——
    // download→verify 清 fill 宽度、verify→download 移除 indeterminate）
    const renderProgress = (phase, downloaded, total, owned) => {
      if (!prog) return;
      const prefix = owned ? '' : `${kind} `;   // 下载中切换下拉：文本标注词典归属
      if (phase === 'download' && total) {
        if (bar) bar.classList.remove('indeterminate');
        const pct = Math.min(100, Math.round(downloaded / total * 100));
        if (fill) fill.style.width = pct + '%';
        if (text) text.textContent = `${prefix}${fmtMB(downloaded)}/${fmtMB(total)}MB`;
      } else {
        // verify/extract 相位与无 total 的 download 相位走不定态
        if (fill) fill.style.width = '';
        if (bar) bar.classList.add('indeterminate');
        const label = phase === 'verify' ? MSG.dict_verify
          : phase === 'extract' ? MSG.dict_extract : MSG.dict_downloading;
        if (text) text.textContent = prefix + label;
      }
    };
    // 下载中禁整行（2.6.5 段2 D2026-1004-01 #5）：三键 setDisabled + 行
    // .is-busy（disabled 态走 --surface-3 底，非仅 opacity）
    const actionRow = btn ? btn.parentElement : null;
    const srcBtns = actionRow
      ? [actionRow.querySelector('.dict-src-official'),
         actionRow.querySelector('.dict-src-mirror')]
      : [];
    if (actionRow) actionRow.classList.add('is-busy');
    srcBtns.forEach((b) => { if (b) b.disabled = true; });
    if (btn) { btn.disabled = true; btn.textContent = MSG.dict_downloading; }
    if (st) dictShowStatus(st, '', false, null);
    let poller = null;
    let lastBytes = 0;
    const stopPoll = () => { if (poller) { clearInterval(poller); poller = null; } };
    // 2.7.3 件⑤：终态收口（done/failed/stopped/互斥拒绝/兜底超时共用）——
    // 原同步 await 的 finally 解锁链整体前移至此，终态改由轮询驱动
    // （会话制下 refine_dict_download 立即返回，不再以该 await 为终态）；
    // finished 单次闸防轮询多拍并发重复收口
    let finished = false;
    const finish = (statusText, isErr, diag) => {
      if (finished) return;
      finished = true;
      stopPoll();                       // 防重复 poller 泄漏
      showProgress(false);              // 隐藏统一放收口（覆盖成功/失败/停止三路径）
      _dictBusyKind = null;             // 先清占位再 dictLoad()：重渲染据此解除整行禁用
      _dictStopPending = false;
      if (actionRow) actionRow.classList.remove('is-busy');
      srcBtns.forEach((b) => { if (b) b.disabled = false; });
      const sel = $('dictSelect');
      if (!sel || sel.value === kind) {
        // 终态与当前选中词典一致才直改按钮（className 同步复位：下载中
        // 挂过 btn-danger 停止态）；不一致交由 dictLoad()→dictRenderDetail()
        // 重刷详情区对齐（重渲染不触碰静态进度条）
        if (btn) {
          btn.disabled = false;
          const finInfo = _dictStatusCache[kind] || {};
          btn.className = finInfo.available ? 'btn btn-ghost btn-compact'
            : 'btn btn-primary btn-compact';
          btn.textContent = doneLabel;
        }
      }
      if (st) dictShowStatus(st, statusText, isErr, diag);
      dictLoad();
    };
    showProgress(true);
    poller = setInterval(async () => {
      try {
        const p = await pywebview.api.refine_dict_download_progress(kind);
        if (!p || !p.success || !p.phase) return;
        if (typeof p.downloaded === 'number' && p.downloaded > 0) {
          lastBytes = p.downloaded;
        }
        // kind 归属校验（批清单条件 3）：下载中切换下拉→进度条标注词典归属，
        // 且不覆盖当前选中词典的按钮态
        const sel = $('dictSelect');
        const owned = !sel || sel.value === kind;
        renderProgress(p.phase, p.downloaded || 0, p.total, owned);
        // 回退可见提示（2.6.3 批B 评议员条件①）：auto 轮换不再静默，
        // note 写 #dictStatus（后端快照粘滞字段，轮询必能采样）
        if (p.note && owned && st) st.textContent = p.note;
        // 过渡兜底（2.7.3 件⑤ 评议员条件③）：停止请求后超时未见终态→
        // 本地按失败收口（后端线程终会写 stopped，后续状态查询自纠）
        if (_dictStopPending &&
            Date.now() - _dictStopRequestedAt > DICT_STOP_GRACE_MS) {
          finish(MSG.dict_stop_note, true, null);
          return;
        }
        if (!owned) return;
        // 2.7.3 件⑤ 四态状态机：download/verify/extract=下载中可停止
        // （主按钮转 btn-danger「停止」，复用既有 .btn-danger 样式与
        // MSG.stop_btn 键）；done/failed/stopped=终态收口
        if (p.phase === 'download' || p.phase === 'verify' ||
            p.phase === 'extract') {
          if (btn && _dictStopPending) {
            // 停止中过渡：按钮禁用防连点，_dictBusyKind 保持占用直到终态
            btn.disabled = true;
            btn.textContent = MSG.dict_stop_pending;
          } else if (btn) {
            btn.disabled = false;               // 停止键须可点
            btn.className = 'btn btn-danger btn-compact';
            btn.textContent = MSG.stop_btn;
          }
          if (st && _dictStopPending) st.textContent = MSG.dict_stopping;
          return;
        }
        if (p.phase === 'stopped') {
          // 已停止：回未安装态，状态行人话指引（finish 解锁链覆盖 stopped
          // ——dictLoad() 重渲染后源 pill/整行立即解锁）
          finish(MSG.dict_stop_note, false, null);
        } else if (p.phase === 'done') {
          // 终态大小以 done 快照链路的 lastBytes 为准（会话制下无同步
          // 返回 path，改为字节数口径）
          finish(`${MSG.dict_download_done}（${fmtMB(lastBytes)}MB）`,
            false, null);
        } else if (p.phase === 'failed') {
          finish(dictFailureText(`${p.error || ''}`, p.diag), true, p.diag);
        }
      } catch (e) { /* 进度轮询失败不干扰主流程 */ }
    }, 1000);
    try {
      // 2.7.3 件⑤ 会话制：refine_dict_download 立即返回 session_id，
      // 下载在后端线程执行，终态（done/failed/stopped）由上方轮询驱动；
      // 本 await 仅处理「启动失败」（kind 校验/同 kind 互斥拒绝等）
      const r = await pywebview.api.refine_dict_download(kind, source || 'auto');
      if (r && r.success) {
        // 已启动：读取一次当前快照校准计数（后端可能已推进）
        try {
          const f = await pywebview.api.refine_dict_download_progress(kind);
          if (f && f.success && typeof f.downloaded === 'number' &&
              f.downloaded > 0) lastBytes = f.downloaded;
        } catch (e) { /* ignore */ }
        return;
      }
      // 启动失败（含 dict_download_busy 互斥拒绝）：立即按失败收口
      finish((r && (r.message || r.error)) || MSG.dict_download_failed,
        true, null);
    } catch (e) {
      // 异常路径=未知错误：一行人话沿用原文（红），无诊断网格
      finish(dictFailureText(String(e), null), true, null);
    }
  }
  // 2.7.3 件⑤：停止请求（下载中主按钮=停止键）。本地立即进入停止中
  // 过渡（按钮禁用防连点 + 状态行「停止中…」），后端经 stop 端点置位
  // Event，下载线程在检查点收口写 stopped 快照（后端绝不乐观代写）；
  // 超时未见终态由轮询兜底（DICT_STOP_GRACE_MS）本地按失败收口
  async function dictRequestStop(kind, btn) {
    if (_dictStopPending) return;       // 防连点（按钮禁用是第一道）
    // 跨 kind 守卫（code-review 触碰式修复②，与 _dictBusyKind 跨 kind
    // 并发洞收口同口径）：A 下载中把下拉切到 B 再点停止——kind 参数读自
    // 当前 sel.value，不校验会对 B 调 stop 端点（后端幂等 False 无害，
    // 但 UI 误入停止中过渡、绕过 _dictBusyKind 跨 kind 互斥占位）。只认
    // _dictBusyKind 本尊：当前选中 kind ≠ 下载中 kind 一律忽略
    if (_dictBusyKind !== kind) return;
    _dictStopPending = true;
    _dictStopRequestedAt = Date.now();
    const st = $('dictStatus');
    if (btn) { btn.disabled = true; btn.textContent = MSG.dict_stop_pending; }
    if (st) dictShowStatus(st, MSG.dict_stopping, false, null);
    try {
      await pywebview.api.refine_dict_download_stop(kind);
    } catch (e) { /* 停止请求失败不本地解锁——轮询/兜底收口 */ }
  }

  // ---- 词典目录设置 + 一键迁移（批1b D2026-1002-12 件1/件2）----
  // 更改目录：refine_pick_dict_dir 收口（对话框+持久化+注入生效）；
  // needs_migration 时弹 AppModal 确认（不静默自动迁移），确认后走迁移
  async function dictPickDir() {
    const st = $('dictStatus');
    try {
      const r = await pywebview.api.refine_pick_dict_dir();
      if (!r || !r.success || !r.path) return;   // 取消/失败静默返回
      _dictOldDir = r.old_dir || '';
      _dictNeedsMigration = !!r.needs_migration;
      if (_dictNeedsMigration) {
        const ok = await AppModal.confirm(
          MSG.dict_migrate_title,
          MSG.dict_migrate_confirm(_dictOldDir, r.old_files || 0),
          { okText: MSG.dict_migrate_btn });
        if (ok) {
          await dictMigrate();
          return;                       // dictMigrate 内部已 dictLoad 收尾
        }
        // 用户暂不迁移：保留迁移键（旧文件仍在旧目录，可稍后点按钮）
      }
      if (st) st.textContent = MSG.dict_dir_set_ok;
      dictLoad();
    } catch (e) {
      if (st) st.textContent = String(e);
    }
  }
  // 恢复默认：refine_clear_dict_dir 收口（不做任何文件删除/迁移）
  async function dictRestoreDir() {
    const st = $('dictStatus');
    try {
      const r = await pywebview.api.refine_clear_dict_dir();
      if (st) st.textContent = (r && r.success)
        ? MSG.dict_dir_restored
        : ((r && r.error) || '');
      _dictNeedsMigration = false;
      dictLoad();
    } catch (e) {
      if (st) st.textContent = String(e);
    }
  }
  // 一键迁移：refine_dict_migrate 执行引擎（复制+校验+原子改名，源不删）；
  // 进度复用下载进度通道（伪 kind '__migrate__'）1s 轮询 #dictProgress
  async function dictMigrate() {
    const st = $('dictStatus');
    const migBtn = $('dictMigrateBtn');
    const prog = $('dictProgress');
    const bar = prog ? prog.querySelector('.progress-bar') : null;
    const fill = prog ? prog.querySelector('.progress-fill') : null;
    const text = prog ? prog.querySelector('.progress-text') : null;
    const showProgress = (visible) => { if (prog) prog.style.display = visible ? '' : 'none'; };
    const fmtMB = (n) => (n / 1048576).toFixed(1);
    if (migBtn) { migBtn.disabled = true; migBtn.textContent = MSG.dict_migrating; }
    if (st) st.textContent = '';
    showProgress(true);
    if (bar) bar.classList.add('indeterminate');
    let poller = null;
    const stopPoll = () => { if (poller) { clearInterval(poller); poller = null; } };
    poller = setInterval(async () => {
      try {
        const p = await pywebview.api.refine_dict_download_progress('__migrate__');
        if (!p || !p.success || !p.phase) return;
        if (typeof p.total === 'number' && p.total > 0) {
          if (bar) bar.classList.remove('indeterminate');
          const pct = Math.min(100, Math.round((p.downloaded || 0) / p.total * 100));
          if (fill) fill.style.width = pct + '%';
          if (text) text.textContent = `${MSG.dict_migrating} ${fmtMB(p.downloaded || 0)}/${fmtMB(p.total)}MB`;
        } else if (text) {
          const xy = p.file_count ? `（${p.file_index || 0}/${p.file_count}）` : '';
          text.textContent = MSG.dict_migrating + xy;
        }
      } catch (e) { /* 进度轮询失败不干扰主流程 */ }
    }, 1000);
    try {
      const r = await pywebview.api.refine_dict_migrate(_dictOldDir);
      if (r && r.success) {
        _dictNeedsMigration = false;      // 成功才消迁移态（失败可重试续传）
        if (st) st.textContent = MSG.dict_migrate_done(
          (r.migrated || []).length, (r.skipped || []).length);
      } else {
        if (st) st.textContent = `${MSG.dict_migrate_failed}：${(r && r.error) || ''}`;
      }
    } catch (e) {
      if (st) st.textContent = `${MSG.dict_migrate_failed}：${String(e)}`;
    } finally {
      stopPoll();                         // 防重复 poller 泄漏
      showProgress(false);
      if (fill) fill.style.width = '';    // 复位填充（bar 相位态由下次使用方全量刷新）
      if (migBtn) { migBtn.disabled = false; migBtn.textContent = MSG.dict_migrate_btn; }
      dictLoad();
    }
  }

  // ---- 首启数据目录引导（批1b 件4）：frozen-only，哨兵防再弹 ----
  // AppModal.confirm 自定义双键：ok=选择其他目录（原生对话框→
  // refine_set_data_root 复用既有重启提示文案），cancel=使用当前目录；
  // 引导交互过即写哨兵（mark_data_guide_done），任何分支不重复骚扰
  async function maybeShowDataGuide() {
    try {
      if (!window.pywebview || !pywebview.api ||
          !pywebview.api.should_show_data_guide) return;
      const r = await pywebview.api.should_show_data_guide();
      if (!r || !r.success || !r.show) return;
      const pick = await AppModal.confirm(
        MSG.data_guide_title,
        MSG.data_guide_body(r.data_root || ''),
        { okText: MSG.data_guide_pick, cancelText: MSG.data_guide_keep });
      if (pick) {
        const sel = await pywebview.api.refine_pick_folder();
        if (sel && sel.success && sel.path) {
          const s = await pywebview.api.refine_set_data_root(sel.path);
          if (s && s.success) {
            // 复用批1a 件5 的重启阻断提示文案（改根后重启生效语义一致）
            await AppModal.alert(MSG.data_root_restart_title,
                                 MSG.data_root_restart_body);
          }
        }
      }
      pywebview.api.mark_data_guide_done();
    } catch (e) { /* 引导失败静默（不阻塞主流程） */ }
  }

  // ---- 远程数据加载（pywebview 就绪后调用一次）----
  async function loadRemote() {
    applySavedStageSettings();
    bindDirectionControls();
    bindCleanerDirControls();
    dataRootLoad();
    dictLoad();
    maybeShowDataGuide();   // 批1b 件4：首启数据目录引导（frozen-only，哨兵防再弹）
    // 角色卡下拉动态化（追加1）：启动时列目录填充下拉与方向卡 datalist
    // （不自动加载编辑器内容——保持现状，打开词库页/切换选中时才加载）
    tplRefreshSelect(false);
    window.__refineTplTabHook = () => tplRefreshSelect(true);
    // 净语配置目录：不再硬编码填充——留空=自动查找（回落链
    // config/templates→包内默认）；已存值由 applySavedStageSettings 回填
    glLoad();
    glLearnedLoad();
    // 批2（D2026-1002-12 拍板点2）：页面就绪不再自动拉取模型列表，只认
    // 「刷新/测试」两个显式入口；已存模型名由 applySavedStageSettings 注入
    refreshPipelineMirror();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindDom);
  } else {
    bindDom();
  }

  window.__refineLoadRemote = loadRemote;

