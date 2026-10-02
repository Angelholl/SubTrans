# SubTransJAV GUI 现代化改版 · 交接文档（ZCode 执行依据）

> 本文档由 2026-09-30 设计评审会话沉淀，是界面改版的**唯一事实来源**。
> ZCode 接手执行时：先完整阅读本文档与 `docs/design/redesign-prototype.html`，再动生产代码。

---

## 1. 背景与已确认决策

**项目**：SubTransJAV（净语翻译），PyWebView 桌面应用，前端为纯 HTML/CSS/JS（无构建链，离线运行）。

**用户已确认的三项决策**：

| 决策项 | 结论 |
|---|---|
| 改动范围 | **彻底重构**（布局重新组织为三栏工作台） |
| 主题策略 | **5 套主题收敛为 2 套**（现代浅色 + 现代深色） |
| 视觉方向 | 现代极简 SaaS 工作台（Notion / Vercel 浅色 Dashboard 风格），用户提供了详细 brief，已全盘采纳 |

**用户 brief 的核心要求（必须全部满足）**：
- 三栏布局：左侧导航栏（浅灰背景）+ 中间主工作区（白色卡片）+ 右侧配置面板（白色卡片）
- SRT 字幕上传区放中间主工作区顶部：**科技蓝虚线边框（dashed）拖拽区，大圆角**
- 「翻译服务选择」和「输出目录」移到**右侧面板**，做成整洁表单组件
- CONSOLE 终端放主工作区下方，**保留深色背景**，加圆角（rounded-lg）和内边距
- 配色：白底、科技蓝 `#3B82F6` 主色、浅灰 `#F3F4F6` 背景、警告色橙色
- 按钮扁平化：主操作蓝色、取消/停止浅红色、次要白底灰边；去除粗边框和渐变；柔和阴影（shadow-sm）+ 大圆角
- 图标使用 **Lucide Icons**

**技术栈修正（与 brief 不同之处，已向用户说明并获认可）**：
- ❌ 不引入 Tailwind CDN（应用离线运行；也不引入 npm 构建链）
- ✅ 用原生 CSS 变量实现同款视觉，色值直接采用 Tailwind 灰阶/蓝色阶数值
- ❌ 不换 Vue3/React（2947 行 app.js 与 Python API 深度绑定，重写风险极高）
- ✅ 保留原生 JS，只动布局与样式层
- ✅ Lucide 图标以内联 SVG 方式引入（零运行时依赖）

---

## 2. 现状诊断（为什么显得陈旧）

1. **字号历轮极限压缩**：区块标题 10px、正文 13px、辅助 10px（style.css 中大量 "AGGRESSIVE: Reduced" 注释）——最大痛点
2. **配色陈旧**：深蓝 `#024873` 主色 + 灰底白卡，三层表面明度差几乎为零，层次扁平
3. **图标体系混乱**：导航是线性 SVG，内容区全是 emoji（📂💾▶⏹⟳🤖）
4. **组件不精致**：原生 checkbox/select、6px 小圆角、浅阴影、无过渡动效
5. **5 套主题并行**（default/google/carbon/primer/dark），后三套风格已过时

---

## 3. 涉及的生产文件

| 文件 | 作用 | 改动方式 |
|---|---|---|
| `subtransjav/webview_gui/assets/index.html` | 全部界面结构（677 行，5 个 tab 页） | 重写布局骨架，**保留全部元素 id 与 data-i18n** |
| `subtransjav/webview_gui/assets/style.css` | 默认主题（1377 行，含 v1.6 token 层） | 按新 token 全量重写 |
| `subtransjav/webview_gui/assets/style.dark.css` | 深色主题（126 行，变量覆盖层） | 按新 token 重写变量层 |
| `style.google.css` / `style.carbon.css` / `style.primer.css` | 3 套过时主题 | **删除**，并同步清理 app.js 中的主题注册项（ThemeManager 相关）与 index.html 主题菜单 |
| `subtransjav/webview_gui/assets/app.js` | 全部逻辑（2947 行） | **不改功能逻辑**；仅允许改主题注册/切换处的枚举列表 |

## 4. 硬性约束（违反即回归）

1. **所有元素 id 原样保留**——app.js 全靠 id 取元素，一个都不能丢
2. **`data-i18n` / `data-i18n-placeholder` / `data-i18n-title` 属性原样保留**——i18n 系统依赖
3. **3 个 JS 依赖的 class 原样保留**：`.file-item`、`.console-section`、`.btn-audio-preview`（app.js 用 `closest()` 查找）
4. **控件类型不可变更**：checkbox → 可改为 toggle 按钮样式，但底层 input[type=checkbox] 必须保留（JS 读写 checked）；select/input 同理
5. **不引入任何外部网络资源**（CDN、字体、图标库运行时）
6. **窗口基准尺寸**：1920×1080 的 63%/85%（约 1210×918），可缩放；窄屏（<1180px）左栏折叠为 64px 图标栏
7. i18n 文案文件 `strings.py` 不动

---

## 5. 设计 Token（与原型文件完全一致，直接照抄）

```css
/* 浅色（默认） */
--bg: #F3F4F6;            /* 应用背景，brief 指定 */
--surface: #FFFFFF;       /* 卡片 */
--surface-2: #F9FAFB;     /* 次级表面/悬停 */
--surface-3: #F3F4F6;
--border: #E5E7EB;
--border-strong: #D1D5DB;
--text-1: #111827;  --text-2: #6B7280;  --text-3: #9CA3AF;
--primary: #3B82F6;       /* brief 指定科技蓝 */
--primary-strong: #2563EB;
--primary-soft: #EFF6FF;
--primary-border: #BFDBFE;
--ok: #10B981;   --ok-soft: #ECFDF5;
--warn: #F59E0B; --warn-soft: #FFFBEB;   /* brief 指定警告橙 */
--danger: #DC2626; --danger-soft: #FEF2F2; --danger-border: #FECACA;
--console-bg: #0F172A; --console-border: #1E293B; --console-text: #CBD5E1;
--radius-sm: 8px; --radius: 12px; --radius-lg: 16px;
--shadow-sm: 0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.08);
--shadow-md: 0 2px 4px rgba(16,24,40,.06), 0 4px 12px rgba(16,24,40,.08);
--font: 14px; --font-sm: 13px; --font-xs: 12px;   /* 字号恢复可读水平 */
```

深色主题变量覆盖值见原型文件 `[data-theme="dark"]` 段（bg #0B0F17 / surface #141821 / primary #60A5FA 等）。

---

## 6. 三栏布局规格

```
grid-template-columns: 220px minmax(0,1fr) 316px
```

- **左栏（导航，浅灰 #F9FAFB）**：品牌区（蓝底圆角 logo + 「净语翻译 / SubTransJAV Translate」）→ 分组「工作区」：字幕翻译、校对（2.6.1 起为灰色占位项）、质量与建议 → 分组「设置」：引擎与模型、词库与模板、高级参数 → 底部：主题切换（深/浅）
  （2026-10-02 D2026-1002-07 批 1 已更新为上述三分；原「工作区」=字幕翻译/引擎与模型/词库与模板、「质量与设置」=质量与建议/高级参数 的分组规格作废）
- **中栏（主工作区，白卡片）**：页头 → 蓝色虚线拖拽区（大圆角 16px，含「添加文件/添加文件夹」按钮）→ 文件列表卡片（每项：文件图标 + 文件名 + 路径 + 状态 chip + 移除按钮；chip 三态：翻译中/已完成/等待中）→ 深色控制台（圆角 12px、内边距 12-14px、等宽字体、日志分色：INFO 灰 / OK 绿 / WARN 琥珀 / ERROR 红）
- **右栏（配置面板，白卡片×3）**：
  1. 运行控制：翻译服务下拉、模型下拉+刷新按钮、开始（蓝色主按钮）、停止（浅红）、进度条（8px 圆角胶囊）
  2. 输出设置：保存到字幕同目录 toggle、输出目录输入+浏览+打开
  3. 两阶段流水线：阶段A/阶段B 状态、并行数

原 5 个 tab 页的其余内容（阶段A/B 完整配置、词典管理、角色卡、词库表格、质量导读、高级参数组）归属：
- 阶段A/B 的 provider/model/key/endpoint 配置 → 右栏「运行控制」展开区或「引擎与模型」页（保留独立页，从导航进入）
- 词库表格、角色卡编辑 → 「词库与模板」页
- 质量导读、AI 分析 → 「质量与建议」页
- 兜底/并发/TM/断点日志等 → 「高级参数」页
- 主工作区默认只显示：拖拽区 + 文件列表 + 控制台；其余全部收进对应导航页

---

## 7. 落地路线（ZCode 按此顺序执行）

**阶段 1：骨架与主题**
1. 备份现状（git 分支或复制 assets 目录）
2. 按第 6 节重写 index.html 三栏骨架（tab 页结构转为导航页结构，id 全保留）
3. 全量重写 style.css（浅色 token）与 style.dark.css（深色覆盖层）
4. 删除 3 套过时主题 css，清理 app.js ThemeManager 枚举与 index.html 主题菜单（改为浅/深两项）

**阶段 2：组件替换**
5. 全部 emoji 图标换 Lucide 内联 SVG（导航、按钮、空状态、状态徽章）
6. 原生 checkbox → toggle 样式（底层 input 保留）、select 加自定义箭头、进度条重做
7. 控制台按深色圆角规格重做
8. 文件列表行富化：文件名/路径分行、三态状态 chip（翻译中/已完成/等待中，接后端 completed/resumable/none 状态）、行内移除按钮（D2026-0930-08 D 项修正，规格见第 6 节）

**阶段 3：逐页套规范**
9. 引擎与模型页：阶段A/B 卡片按新表单规范重排
10. 词库与模板页：表格按原型 `.gl-table` 规范（细边框、行悬停、状态 tag）
11. 质量页与高级参数页：adv-group 改为卡片分组

**验收标准**：
- [ ] 所有功能可用（对照 id 清单逐个验证）
- [ ] 双主题切换正常，深色下对比度达标
- [ ] 窗口缩放至 ~1000px 宽时左栏折叠不破版
- [ ] 无任何外部网络请求
- [ ] 翻译全流程（添加文件→开始→进度→控制台→产物）走通

---

## 8. 参考文件

- 高保真原型（视觉与布局的最终目标）：`docs/design/redesign-prototype.html`
- 原型即离线静态页，浏览器直接打开可查看浅色/深色两套效果与设计系统速览
