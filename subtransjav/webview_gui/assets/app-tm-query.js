// ============================================================
// TM 搜索区块（2.6.4 批1，D2026-1003-05 策略 B）：词库与模板页只读
// 全文检索。index.html 冻结零改动（FROZEN_IDS=213 / 静态 i18n 既有钉
// 零消耗）：区块全 createElement + class/dataset 承载（零新增静态
// id/data-i18n），文案走 MSG JS 态键，结果渲染全 textContent（禁
// innerHTML，查询词/库内容均为外部输入），错误与空态界面可见
// （吞错可见化纪律），经 window.pywebview.api.tm_search 只读查询。
// ============================================================
const TmSearch = {
    // 首次打开词库页时注入整块（.tm-search-block 定位，防重复注入）
    ensure() {
        const page = document.getElementById('tab-glossary');
        if (!page || page.querySelector('.tm-search-block')) return;
        const block = document.createElement('div');
        block.className = 'stack tm-search-block';
        block.style.marginTop = '10px';
        const title = document.createElement('div');
        title.className = 'block-title';
        title.textContent = MSG.tmSearchTitle;
        block.appendChild(title);
        // 搜索行：输入框 + 按钮 + 状态 span（回车与按钮均可触发）
        const row = document.createElement('div');
        row.className = 'action-row';
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'form-input compact grow tm-search-input';
        input.placeholder = MSG.tmSearchPlaceholder;
        input.autocomplete = 'off';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-secondary btn-compact tm-search-btn';
        btn.textContent = MSG.tmSearchBtn;
        const status = document.createElement('span');
        status.className = 'muted tm-search-status';
        row.appendChild(input);
        row.appendChild(btn);
        row.appendChild(status);
        block.appendChild(row);
        // 结果表（表头四列）+ 空态引导行
        const table = document.createElement('table');
        table.className = 'gl-table tm-search-table';
        const thead = document.createElement('thead');
        const hrow = document.createElement('tr');
        [MSG.tmSearchColSource, MSG.tmSearchColTarget,
         MSG.tmSearchColStage, MSG.tmSearchColHits].forEach(label => {
            const th = document.createElement('th');
            th.textContent = label;
            hrow.appendChild(th);
        });
        thead.appendChild(hrow);
        table.appendChild(thead);
        const tbody = document.createElement('tbody');
        table.appendChild(tbody);
        const empty = document.createElement('div');
        empty.className = 'empty-guide tm-search-empty';
        empty.style.display = 'none';
        empty.textContent = MSG.tmSearchEmpty;
        block.appendChild(table);
        block.appendChild(empty);
        const run = () => this.run(input, status, tbody, empty, btn);
        btn.addEventListener('click', run);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                run();
            }
        });
        page.appendChild(block);
    },

    // 只读查询 + 渲染：单元格全 textContent；失败/空结果状态可见
    async run(input, status, tbody, empty, btn) {
        const q = input.value.trim();
        btn.disabled = true;
        tbody.textContent = '';
        empty.style.display = 'none';
        status.textContent = MSG.tmSearchRunning;
        try {
            const r = await window.pywebview.api.tm_search(q, 50);
            if (!r || !r.success) {
                status.textContent = MSG.tmSearchFailed
                    + '：' + ((r && r.error) || MSG.unknown);
                return;
            }
            const results = r.results || [];
            status.textContent = MSG.tmSearchCount(results.length);
            if (!results.length) {
                empty.style.display = '';
                return;
            }
            for (const it of results) {
                const tr = document.createElement('tr');
                [it.source_text, it.target_text, it.stage, it.hit_count]
                    .forEach(val => {
                        const td = document.createElement('td');
                        td.textContent = (val === null || val === undefined)
                            ? '' : String(val);
                        tr.appendChild(td);
                    });
                tbody.appendChild(tr);
            }
        } catch (e) {
            status.textContent = MSG.tmSearchFailed + '：'
                + ((e && e.message) || String(e));
        } finally {
            btn.disabled = false;
        }
    }
};

