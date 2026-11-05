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

