// ============================================================
// File List Management (always .srt mode)
// ============================================================
const FileListManager = {
    init() {
        this.itemStates = {};   // path -> 'pending'|'running'|'done'|'resumable'（D2026-0930-09 批2）

        const fileList = document.getElementById('fileList');

        fileList.addEventListener('click', (e) => {
            const removeBtn = e.target.closest('.file-remove-btn');
            if (removeBtn) {
                const item = removeBtn.closest('.file-item');
                if (item && item.dataset.path) {
                    this.removeOne(item.dataset.path);
                }
                return;
            }
            const item = e.target.closest('.file-item');
            if (item) {
                this.handleItemClick(item, e);
            }
        });

        fileList.addEventListener('keydown', (e) => {
            this.handleKeyboard(e);
        });

        this.initializeDragDrop();

        document.getElementById('addFilesBtn').addEventListener('click', () => this.addFiles());
        document.getElementById('addFolderBtn').addEventListener('click', () => this.addFolder());
        document.getElementById('removeSelectedBtn').addEventListener('click', () => this.removeSelected());
        document.getElementById('clearBtn').addEventListener('click', () => this.clearAll());
    },

    initializeDragDrop() {
        const fileList = document.getElementById('fileList');
        const dropzone = document.getElementById('dropzone');

        // D2026-0930-09 批2：拖拽高亮同时作用于 dropzone 本体（preventDefault 已有，防 PyWebView 打开文件）
        const highlight = (on) => {
            fileList.classList.toggle('drag-over', on);
            if (dropzone) dropzone.classList.toggle('drag-over', on);
        };

        fileList.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            highlight(true);
        });

        fileList.addEventListener('dragenter', (e) => {
            e.preventDefault();
            e.stopPropagation();
            highlight(true);
        });

        fileList.addEventListener('dragleave', () => {
            highlight(false);
        });

        fileList.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            highlight(false);
            // Actual path extraction happens in Python (main.py) via pywebviewFullPath,
            // which calls back into FileListManager.addDroppedFiles(paths).
        });
    },

    // Method called by Python DOM event handler with full file paths
    // (.srt/.ass/.ssa/.vtt only，2.7.2 件1 与对话框口径一致)
    addDroppedFiles(paths) {
        if (!Array.isArray(paths) || paths.length === 0) {
            return;
        }

        let addedCount = 0;
        let duplicates = 0;
        let skipped = 0;
        const allowedSubtitleExts = ['.srt', '.ass', '.ssa', '.vtt'];

        paths.forEach(path => {
            const p = String(path).toLowerCase();
            if (!allowedSubtitleExts.some(ext => p.endsWith(ext))) {
                skipped++;
                return;
            }
            if (!AppState.selectedFiles.includes(path)) {
                AppState.selectedFiles.push(path);
                addedCount++;
            } else {
                duplicates++;
            }
        });

        if (addedCount > 0) {
            this.render();
            ConsoleManager.log(MSG.addedViaDrop(addedCount), 'success');
        }
        if (duplicates > 0) {
            ConsoleManager.log(MSG.skippedDuplicates(duplicates), 'info');
        }
        if (skipped > 0) {
            ConsoleManager.log(MSG.skippedNonSrt(skipped), 'warning');
        }
    },

    render() {
        // A案 has-files 态单点切换（批1，C1 修正）：必须在函数体第一行、
        // 空态提前 return 之前——六条 selectedFiles 变更路径全汇 render()，
        // 单点双出口（空态 return / 正常渲染）全覆盖，清空路径可回归空态
        document.getElementById('tab-translate').classList.toggle('has-files', AppState.selectedFiles.length > 0);
        const fileList = document.getElementById('fileList');
        const emptyState = document.getElementById('emptyState');

        if (AppState.selectedFiles.length === 0) {
            emptyState.style.display = 'flex';
            fileList.querySelectorAll('.file-item').forEach(item => item.remove());
            this.updateButtons();
            return;
        }

        emptyState.style.display = 'none';

        const existingItems = Array.from(fileList.querySelectorAll('.file-item'));
        const existingPaths = existingItems.map(item => item.dataset.path);

        AppState.selectedFiles.forEach((file, index) => {
            if (!existingPaths.includes(file)) {
                const item = this.createFileItem(file, index);
                fileList.appendChild(item);
            }
        });

        existingItems.forEach(item => {
            if (!AppState.selectedFiles.includes(item.dataset.path)) {
                item.remove();
            }
        });

        const pathToIndex = new Map();
        AppState.selectedFiles.forEach((file, index) => {
            if (!pathToIndex.has(file)) pathToIndex.set(file, index);
        });
        fileList.querySelectorAll('.file-item').forEach(item => {
            const index = pathToIndex.get(item.dataset.path);
            if (index !== undefined) item.dataset.index = String(index);
        });

        this.updateChips();
        this.updateButtons();
    },

    createFileItem(path, index) {
        const item = document.createElement('div');
        item.className = 'file-item';
        item.dataset.path = path;
        item.dataset.index = index;
        item.tabIndex = 0;

        const icon = document.createElement('span');
        icon.className = 'file-ico';
        icon.innerHTML =
            '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/></svg>';

        const grow = document.createElement('span');
        grow.className = 'grow';
        const name = document.createElement('span');
        name.className = 'file-name';
        name.textContent = path.split(/[\\/]/).pop() || path;
        const sub = document.createElement('span');
        sub.className = 'file-path';
        sub.textContent = path;
        grow.appendChild(name);
        grow.appendChild(sub);

        const chip = document.createElement('span');
        chip.className = 'chip chip-pending';
        chip.textContent = MSG.chip_pending;

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'file-remove-btn';
        removeBtn.title = MSG.remove_selected;
        removeBtn.setAttribute('aria-label', MSG.remove_selected);
        removeBtn.innerHTML =
            '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 4H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5"/><path d="M10 14 21 3"/><path d="M15 3h6v6"/></svg>';

        item.appendChild(icon);
        item.appendChild(grow);
        item.appendChild(chip);
        item.appendChild(removeBtn);

        return item;
    },

    // ---- chip 态映射（D2026-0930-09 批2 三态；批 8b 增 failed 第四态：
    //      后端 files_status 四态 pending/running/done/failed，批 8a 透出）----
    chipClass(state) {
        return {
            pending: 'chip-pending',
            running: 'chip-running',
            done: 'chip-done',
            resumable: 'chip-resumable',
            failed: 'chip-failed'
        }[state] || 'chip-pending';
    },

    chipText(state) {
        return {
            pending: MSG.chip_pending,
            running: MSG.chip_running,
            done: MSG.chip_done,
            resumable: MSG.chip_resumable,
            failed: MSG.chip_failed
        }[state] || MSG.chip_pending;
    },

    setState(path, state) {
        if (!state) return;
        this.itemStates[path] = state;
        this.updateChips();
    },

    // files_status 映射（basename -> state）：只更新命中的文件，不回退其他项。
    // 批 8a 口径补充：backend pending（phase_started 前的初始态）视为无态——
    // 命中不写入，文件 chip 保持现状（默认即为 pending 等待灰，视觉等价，
    // 且不覆盖断点恢复探测已打上的 resumable 态）
    applyStates(map) {
        if (!map) return;
        const base = p => p.split(/[\\/]/).pop();
        let touched = false;
        AppState.selectedFiles.forEach(p => {
            const st = map[base(p)];
            if (st && st !== 'pending' && this.itemStates[p] !== st) {
                this.itemStates[p] = st;
                touched = true;
            }
        });
        if (touched) this.updateChips();
    },

    updateChips() {
        document.querySelectorAll('.file-item').forEach(item => {
            const state = this.itemStates[item.dataset.path] || 'pending';
            const chip = item.querySelector('.chip');
            if (chip) {
                chip.className = 'chip ' + this.chipClass(state);
                chip.textContent = this.chipText(state);
            }
        });
    },

    removeOne(path) {
        const idx = AppState.selectedFiles.indexOf(path);
        if (idx >= 0) AppState.selectedFiles.splice(idx, 1);
        delete this.itemStates[path];
        AppState.selectedIndices.clear();
        this.render();
    },

    handleItemClick(item, event) {
        const index = parseInt(item.dataset.index);

        if (event.ctrlKey || event.metaKey) {
            this.toggleSelection(index);
        } else if (event.shiftKey && AppState.selectedIndices.size > 0) {
            const lastIndex = Math.max(...Array.from(AppState.selectedIndices));
            this.selectRange(lastIndex, index);
        } else {
            this.selectSingle(index);
        }

        this.updateSelectionUI();
        this.updateButtons();
    },

    toggleSelection(index) {
        if (AppState.selectedIndices.has(index)) {
            AppState.selectedIndices.delete(index);
        } else {
            AppState.selectedIndices.add(index);
        }
    },

    selectSingle(index) {
        AppState.selectedIndices.clear();
        AppState.selectedIndices.add(index);
    },

    selectRange(start, end) {
        const [min, max] = [Math.min(start, end), Math.max(start, end)];
        for (let i = min; i <= max; i++) {
            AppState.selectedIndices.add(i);
        }
    },

    updateSelectionUI() {
        document.querySelectorAll('.file-item').forEach(item => {
            const index = parseInt(item.dataset.index);
            item.classList.toggle('selected', AppState.selectedIndices.has(index));
        });
    },

    updateButtons() {
        const hasFiles = AppState.selectedFiles.length > 0;
        const hasSelection = AppState.selectedIndices.size > 0;

        document.getElementById('removeSelectedBtn').disabled = !hasSelection || AppState.isRunning;
        document.getElementById('clearBtn').disabled = !hasFiles || AppState.isRunning;

        const countEl = document.querySelector('.card-head-count');
        if (countEl) countEl.textContent = AppState.selectedFiles.length > 0 ? MSG.selected_count(AppState.selectedFiles.length) : '';

        TranslatorManager.updateButtons();
    },

    handleKeyboard(e) {
        const items = Array.from(document.querySelectorAll('.file-item'));
        if (items.length === 0) return;

        const currentIndex = Array.from(AppState.selectedIndices).sort((a, b) => b - a)[0] || 0;

        let newIndex = currentIndex;

        if (e.key === 'ArrowDown') {
            newIndex = Math.min(items.length - 1, currentIndex + 1);
            e.preventDefault();
        } else if (e.key === 'ArrowUp') {
            newIndex = Math.max(0, currentIndex - 1);
            e.preventDefault();
        } else if (e.key === 'Delete' || e.key === 'Backspace') {
            this.removeSelected();
            e.preventDefault();
            return;
        } else {
            return;
        }

        if (e.shiftKey) {
            this.selectRange(currentIndex, newIndex);
        } else {
            this.selectSingle(newIndex);
        }

        this.updateSelectionUI();
        this.updateButtons();

        if (items[newIndex]) {
            items[newIndex].scrollIntoView({ block: 'nearest' });
        }
    },

    async addFiles() {
        const btn = document.getElementById('addFilesBtn');
        UIHelpers.showLoadingState(btn, true);

        try {
            const result = await pywebview.api.select_srt_files();

            if (result.success && result.paths && result.paths.length > 0) {
                result.paths.forEach(file => {
                    if (!AppState.selectedFiles.includes(file)) {
                        AppState.selectedFiles.push(file);
                    }
                });

                this.render();
                ConsoleManager.log(MSG.addedFiles(result.paths.length), 'info');
            }
        } catch (error) {
            ErrorHandler.show(MSG.fileSelectError, error.toString());
        } finally {
            UIHelpers.showLoadingState(btn, false);
        }
    },

    async addFolder() {
        const btn = document.getElementById('addFolderBtn');
        UIHelpers.showLoadingState(btn, true);

        try {
            const result = await pywebview.api.select_srt_folder();
            if (result.success && result.paths && result.paths.length > 0) {
                result.paths.forEach(filePath => {
                    if (!AppState.selectedFiles.includes(filePath)) {
                        AppState.selectedFiles.push(filePath);
                    }
                });
                this.render();
                ConsoleManager.log(MSG.addedFilesFromFolder(result.paths.length), 'info');
                // 2.7.3 件④：流水线中间稿/终稿被智能过滤跳过时补明细行
                if (result.skipped_count > 0) {
                    ConsoleManager.log(MSG.folderSkippedPipeline(result.skipped_count), 'info');
                }
            } else if (result.message) {
                ConsoleManager.log(result.message, 'warning');
            }
        } catch (error) {
            ErrorHandler.show(MSG.folderSelectError, error.toString());
        } finally {
            UIHelpers.showLoadingState(btn, false);
        }
    },

    removeSelected() {
        if (AppState.selectedIndices.size === 0) return;

        const indicesToRemove = Array.from(AppState.selectedIndices).sort((a, b) => b - a);
        indicesToRemove.forEach(index => {
            AppState.selectedFiles.splice(index, 1);
        });

        AppState.selectedIndices.clear();
        this.render();
        ConsoleManager.log(MSG.removedItems(indicesToRemove.length), 'info');
    },

    clearAll() {
        if (AppState.selectedFiles.length === 0) return;

        const count = AppState.selectedFiles.length;
        AppState.selectedFiles = [];
        AppState.selectedIndices.clear();
        this.itemStates = {};
        this.render();
        ConsoleManager.log(MSG.clearedItems(count), 'info');
    }
};

