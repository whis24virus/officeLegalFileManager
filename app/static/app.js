// State
let state = {
    department: null,
    files: [],
    categories: [],
    searchQuery: '',
    isUploading: false
};

// DOM Elements
const els = {
    views: {
        department: document.getElementById('view-department'),
        dashboard: document.getElementById('view-dashboard')
    },
    deptGrid: document.getElementById('department-grid'),
    currentDeptDisplay: document.getElementById('current-dept-display'),
    fileGrid: document.getElementById('file-grid'),
    fileCountDisplay: document.getElementById('file-count-display'),
    emptyStateFiles: document.getElementById('empty-state-files'),
    
    // Search
    searchInput: document.getElementById('search-input'),
    normalViewContainer: document.getElementById('normal-view-container'),
    searchViewContainer: document.getElementById('search-view-container'),
    exactResultsContainer: document.getElementById('exact-results-container'),
    semanticResultsContainer: document.getElementById('semantic-results-container'),
    exactResultsList: document.getElementById('exact-results-list'),
    semanticResultsList: document.getElementById('semantic-results-list'),
    aiAnswerCard: document.getElementById('ai-answer-card'),
    aiAnswerText: document.getElementById('ai-answer-text'),
    aiSourceFile: document.getElementById('ai-source-file'),
    didYouMeanContainer: document.getElementById('did-you-mean-container'),
    didYouMeanLink: document.getElementById('did-you-mean-link'),
    searchDropdown: document.getElementById('search-dropdown'),
    searchMetaDisplay: document.getElementById('search-meta-display'),
    btnClearSearch: document.getElementById('btn-clear-search'),
    emptyStateSearch: document.getElementById('empty-state-search'),
    
    // Buttons
    btnSwitchDept: document.getElementById('btn-switch-dept'),
    btnOpenUpload: document.getElementById('btn-open-upload'),
    
    // Modals
    modalUpload: document.getElementById('modal-upload'),
    modalDetail: document.getElementById('modal-file-detail'),
    
    // Upload Form
    uploadForm: document.getElementById('upload-form'),
    dropZone: document.getElementById('drop-zone'),
    fileInput: document.getElementById('file-input'),
    filePreview: document.getElementById('file-preview'),
    uploadCategory: document.getElementById('upload-category'),
    progressContainer: document.getElementById('upload-progress-container'),
    progressFill: document.getElementById('upload-progress-fill'),
    btnCloseUpload: document.getElementById('btn-close-upload'),
    btnCancelUpload: document.getElementById('btn-cancel-upload'),
    
    // Detail Modal
    detailIcon: document.getElementById('detail-icon'),
    detailTitle: document.getElementById('detail-title'),
    detailCategory: document.getElementById('detail-category'),
    detailDate: document.getElementById('detail-date'),
    detailSize: document.getElementById('detail-size'),
    detailTags: document.getElementById('detail-tags'),
    detailPreview: document.getElementById('detail-preview'),
    btnCloseDetail: document.getElementById('btn-close-detail'),
    btnCloseDetailAlt: document.getElementById('btn-close-detail-alt'),
    btnDeleteFile: document.getElementById('btn-delete-file'),
    btnDownloadFile: document.getElementById('btn-download-file')
};

// Helpers
const getCookie = (name) => {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
};

const formatBytes = (bytes, decimals = 2) => {
    if (!+bytes) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
};

const formatDate = (dateString) => {
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return new Date(dateString).toLocaleDateString(undefined, options);
};

const getFileIcon = (filename = '', type = '') => {
    const ext = filename.split('.').pop().toLowerCase();
    if (['pdf'].includes(ext)) return '📄';
    if (['doc', 'docx'].includes(ext)) return '📋';
    if (['xls', 'xlsx', 'csv'].includes(ext)) return '📊';
    if (['png', 'jpg', 'jpeg', 'gif'].includes(ext)) return '🖼️';
    if (['txt', 'md'].includes(ext)) return '📝';
    return '📁';
};

const showToast = (message, type = 'success') => {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${type === 'success' ? '✅' : '❌'}</span>
        <span class="toast-msg">${message}</span>
    `;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('hiding');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
};

const debounce = (func, wait) => {
    let timeout;
    return function executedFunction(...args) {
        const later = () => { clearTimeout(timeout); func(...args); };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
};

// API Wrapper
const api = {
    get: async (url, timeoutMs = 45000) => {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
        try {
            const res = await fetch(url, { signal: controller.signal });
            clearTimeout(timeoutId);
            if (!res.ok) throw new Error(await res.text());
            return res.json();
        } catch (err) {
            clearTimeout(timeoutId);
            throw err;
        }
    },
    async post(endpoint, data, isFormData = false) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000);
        const options = { method: 'POST', signal: controller.signal, credentials: 'login' === 'login' ? 'same-origin' : 'include' };
        if (isFormData) {
            options.body = data;
        } else {
            options.headers = { 'Content-Type': 'application/json' };
            options.body = JSON.stringify(data);
        }
        try {
            const res = await fetch(endpoint, options);
            clearTimeout(timeoutId);
            if (!res.ok) throw new Error(await res.text() || res.statusText);
            return res.json();
        } catch (err) {
            clearTimeout(timeoutId);
            throw err;
        }
    },
    async delete(endpoint) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000);
        try {
            const res = await fetch(endpoint, { method: 'DELETE', signal: controller.signal, credentials: 'login' === 'login' ? 'same-origin' : 'include' });
            clearTimeout(timeoutId);
            if (!res.ok) throw new Error(await res.text() || res.statusText);
            return res.json();
        } catch (err) {
            clearTimeout(timeoutId);
            throw err;
        }
    }
};

// Initialize App
const init = async () => {
    setupEventListeners();
    
    const deptCookie = getCookie('olfm_department');
    if (deptCookie) {
        state.department = deptCookie;
        await loadDashboard();
    } else {
        await loadDepartmentSelection();
    }
};

const loadDepartmentSelection = async () => {
    showView('department');
    try {
        els.deptGrid.innerHTML = '<div class="spinner"></div>';
        const depts = await api.get('/api/departments');
        
        const icons = { 'Legal': '⚖️', 'HR': '👥', 'Finance': '💰', 'Operations': '⚙️' };
        
        els.deptGrid.innerHTML = depts.map(dept => `
            <div class="dept-card glass-panel" data-dept="${dept}">
                <div class="dept-icon">${icons[dept] || '🏢'}</div>
                <div class="dept-name">${dept}</div>
            </div>
        `).join('');
        
        document.querySelectorAll('.dept-card').forEach(card => {
            card.addEventListener('click', () => selectDepartment(card.dataset.dept));
        });
    } catch (err) {
        showToast('Failed to load departments', 'error');
        els.deptGrid.innerHTML = '<p class="text-error">Error loading departments.</p>';
    }
};

const selectDepartment = async (deptName) => {
    try {
        await api.post('/api/session', { department: deptName.toLowerCase() });
        state.department = deptName;
        await loadDashboard();
        showToast(`Switched to ${deptName} department`);
    } catch (err) {
        alert('Error selecting department: ' + err.message);
        console.error(err);
        showToast('Failed to set department', 'error');
    }
};

const loadDashboard = async () => {
    showView('dashboard');
    els.currentDeptDisplay.textContent = state.department;
    els.searchInput.value = '';
    showNormalView();
    
    try {
        // Load Categories
        state.categories = await api.get('/api/categories');
        els.uploadCategory.innerHTML = `
            <option value="" disabled selected>Select category...</option>
            ${state.categories.map(c => `<option value="${c}">${c}</option>`).join('')}
        `;
        
        // Load Files
        await fetchAndRenderFiles();
    } catch (err) {
        alert('Error loading dashboard: ' + err.message);
        console.error(err);
        showToast('Failed to load dashboard data', 'error');
    }
};

const fetchAndRenderFiles = async () => {
    try {
        els.fileGrid.innerHTML = '<div class="spinner"></div>';
        state.files = await api.get('/api/files/');
        renderFileGrid();
    } catch (err) {
        console.error(err);
        showToast('Failed to load files', 'error');
    }
};

const renderFileGrid = () => {
    els.fileCountDisplay.textContent = `${state.files.length} file${state.files.length !== 1 ? 's' : ''}`;
    
    if (state.files.length === 0) {
        els.fileGrid.innerHTML = '';
        els.emptyStateFiles.classList.remove('hidden');
        return;
    }
    
    els.emptyStateFiles.classList.add('hidden');
    els.fileGrid.innerHTML = state.files.map(file => `
        <div class="file-card glass-panel" data-id="${file.id}">
            <div class="file-header">
                <span class="file-icon">${getFileIcon(file.filename)}</span>
                <span class="badge">${file.category || 'General'}</span>
            </div>
            <div>
                <div class="file-title" title="${file.title}">${file.title}</div>
                <div class="file-meta">
                    <span>${formatBytes(file.filesize)}</span>
                    <span>${formatDate(file.created_at || new Date())}</span>
                </div>
            </div>
            <div class="tag-container">
                ${(file.auto_tags || []).slice(0,3).map(tag => `<span class="tag">${tag}</span>`).join('')}
                ${(file.auto_tags && file.auto_tags.length > 3) ? `<span class="tag">+${file.auto_tags.length - 3}</span>` : ''}
            </div>
        </div>
    `).join('');
    
    document.querySelectorAll('.file-card').forEach(card => {
        card.addEventListener('click', () => openFileDetail(card.dataset.id));
    });
};

let currentSuggestion = '';

// Search Logic
const formatMatchedBadge = (keywords, query) => {
    if (!keywords || !keywords.length) return '';
    const queryWord = query.trim().split(/\s+/).pop().toLowerCase();
    
    let badges = [];
    const maxToShow = 3;
    for (let i = 0; i < Math.min(keywords.length, maxToShow); i++) {
        let kw = keywords[i];
        if (queryWord && kw.toLowerCase().startsWith(queryWord)) {
            const prefix = kw.substring(0, queryWord.length);
            const suffix = kw.substring(queryWord.length);
            badges.push(`<span class="matched-badge">Matched: <span class="matched-prefix">${prefix}</span><span class="matched-suffix">${suffix}</span></span>`);
        } else {
            badges.push(`<span class="matched-badge">Matched: ${kw}</span>`);
        }
    }
    
    let html = badges.join(' ');
    if (keywords.length > maxToShow) {
        html += `<span class="matched-badge" style="background:transparent; border:none; color:var(--text-muted); padding:0.2rem;">...</span>`;
    }
    return html;
};

const renderResultCard = (res, query) => {
    const scorePercent = res.match_source === 'exact' ? 100 : Math.min(100, Math.max(0, (res.relevance_score || 0) * 100));
    const matchedBadge = res.matched_keywords ? formatMatchedBadge(res.matched_keywords, query) : '';
        
    return `
    <div class="search-result-card glass-panel" data-id="${res.id}">
        <div class="sr-icon">${getFileIcon(res.filename || '')}</div>
        <div class="sr-content">
            <div class="sr-header">
                <div class="sr-title">${res.title}</div>
                <span class="badge">${res.match_source || 'match'}</span>
            </div>
            ${matchedBadge}
            <div class="sr-snippet">...${res.snippet || ''}...</div>
            <div class="sr-footer">
                ${res.match_source === 'semantic' ? `
                <div class="relevance-bar-wrapper" title="Relevance: ${Math.round(scorePercent)}%">
                    <div class="relevance-fill" style="width: ${scorePercent}%"></div>
                </div>` : ''}
                <div class="tag-container" style="margin-top:0;">
                    ${(res.auto_tags || []).slice(0,4).map(tag => `<span class="tag">${tag}</span>`).join('')}
                </div>
            </div>
        </div>
    </div>
    `;
};

const fetchSemanticSearch = async (query, excludeIds) => {
    try {
        els.semanticResultsList.innerHTML = '<div class="spinner" style="margin: 2rem auto; zoom: 0.5;"></div>';
        els.semanticResultsContainer.classList.remove('hidden');
        
        const data = await api.get(`/api/search/semantic?q=${encodeURIComponent(query)}&limit=10&exclude_ids=${excludeIds.join(',')}`);
        
        if (data.semantic_matches && data.semantic_matches.length > 0) {
            els.semanticResultsList.innerHTML = data.semantic_matches.map(r => renderResultCard(r, query)).join('');
            document.querySelectorAll('#semantic-results-list .search-result-card').forEach(card => {
                card.addEventListener('click', () => openFileDetail(card.dataset.id));
            });
        } else {
            els.semanticResultsContainer.classList.add('hidden');
        }
    } catch (err) {
        if (err.name !== 'AbortError') {
            els.semanticResultsContainer.classList.add('hidden');
            console.error('Semantic search failed:', err);
        }
    }
};

const debouncedSemanticSearch = debounce(fetchSemanticSearch, 500);

let currentExactIds = [];

const handleSearch = async (query) => {
    if (!query.trim()) {
        showNormalView();
        if (els.ghostText) els.ghostText.innerHTML = '';
        currentSuggestion = '';
        return;
    }
    
    showSearchView();
    els.exactResultsList.innerHTML = '<div class="spinner" style="margin: 2rem auto;"></div>';
    els.semanticResultsList.innerHTML = '';
    els.exactResultsContainer.classList.remove('hidden');
    els.semanticResultsContainer.classList.add('hidden');
    els.didYouMeanContainer.classList.add('hidden');
    els.emptyStateSearch.classList.add('hidden');
    if(els.aiAnswerCard) els.aiAnswerCard.classList.add('hidden');
    
    try {
        const data = await api.get(`/api/search/exact?q=${encodeURIComponent(query)}&limit=20`);
        const total = (data.exact_matches?.length || 0);
        els.searchMetaDisplay.textContent = `Found ${total} exact results in ${data.search_time_ms || 0}ms`;
        
        // Handle Dropdown Suggestions
        els.searchDropdown.innerHTML = '';
        if (data.word_completions && data.word_completions.length > 0 && query.trim().toLowerCase() === els.searchInput.value.trim().toLowerCase()) {
            currentSuggestion = data.word_completions[0];
            els.searchDropdown.classList.remove('hidden');
            
            data.word_completions.forEach((word, index) => {
                const li = document.createElement('li');
                li.textContent = word;
                if (index === 0) li.classList.add('active'); // Highlight first one for Tab
                
                li.addEventListener('click', () => {
                    // Replace the last word in the input with the selected completion
                    const words = els.searchInput.value.trim().split(/\s+/);
                    words.pop();
                    words.push(word);
                    els.searchInput.value = words.join(' ') + ' ';
                    els.searchDropdown.classList.add('hidden');
                    els.searchInput.focus();
                    handleSearch(els.searchInput.value);
                });
                els.searchDropdown.appendChild(li);
            });
        } else {
            els.searchDropdown.classList.add('hidden');
            currentSuggestion = '';
        }
        
        // Handle "Did you mean?"
        if (data.did_you_mean) {
            els.didYouMeanContainer.classList.remove('hidden');
            els.didYouMeanLink.textContent = data.did_you_mean;
            els.didYouMeanLink.onclick = (e) => {
                e.preventDefault();
                els.searchInput.value = data.did_you_mean;
                handleSearch(data.did_you_mean);
            };
        }
        
        // Render Exact Matches
        if (data.exact_matches && data.exact_matches.length > 0) {
            els.exactResultsContainer.classList.remove('hidden');
            els.exactResultsList.innerHTML = data.exact_matches.map(r => renderResultCard(r, query)).join('');
            currentExactIds = data.exact_matches.map(r => r.id);
        } else {
            els.exactResultsContainer.classList.add('hidden');
            currentExactIds = [];
        }
        
        document.querySelectorAll('#exact-results-list .search-result-card').forEach(card => {
            card.addEventListener('click', () => openFileDetail(card.dataset.id));
        });

        // Fire Semantic Search in the background with a 500ms debounce
        if (query.trim().length >= 3) {
            debouncedSemanticSearch(query, currentExactIds);
        }

        // V3: Two-Phase Async Response — fire RAG request in background
        if (data.is_question && (total > 0 || query.trim().length >= 3)) {
            // Show "Thinking..." animation immediately
            els.aiAnswerCard.classList.remove('hidden');
            els.aiAnswerText.innerHTML = '<span class="ai-thinking">Thinking<span class="dot-1">.</span><span class="dot-2">.</span><span class="dot-3">.</span></span>';
            els.aiSourceFile.textContent = '';
            
            // Fire async RAG request
            debouncedFetchRAGAnswer(query);
        } else {
            if(els.aiAnswerCard) els.aiAnswerCard.classList.add('hidden');
        }
        
        if (total === 0 && query.trim().length < 3 && !data.did_you_mean) {
            els.emptyStateSearch.classList.remove('hidden');
        }
        
    } catch (err) {
        if (err.name !== 'AbortError') {
            showToast('Search failed', 'error');
            showNormalView();
        }
    }
};

const debouncedSearch = debounce(handleSearch, 50);
const debouncedFetchRAGAnswer = debounce((query) => fetchRAGAnswer(query), 500);

// Simple Markdown Parser for AI Answer
const parseMarkdown = (text) => {
    if (!text) return '';
    // Escape HTML to prevent XSS
    let safe = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    
    // Auto-fix Flan-T5 collapsed lists (e.g., "Item 1 2. Item 2" -> "Item 1\n2. Item 2")
    safe = safe.replace(/ (\d+\.\s)/g, '\n$1');
    safe = safe.replace(/ (\*\s)/g, '\n$1');
    safe = safe.replace(/ (-\s)/g, '\n$1');
    
    // Parse lists (* or -)
    const lines = safe.split('\n');
    let inList = false;
    let html = '';
    
    for (let i = 0; i < lines.length; i++) {
        let line = lines[i].trim();
        
        if (line.startsWith('* ') || line.startsWith('- ') || /^\d+\.\s/.test(line)) {
            let content = line.replace(/^(\* |- |\d+\.\s)/, '');
            if (!inList) {
                html += '<ul>\n';
                inList = true;
            }
            html += `<li>${content}</li>\n`;
        } else {
            if (inList) {
                html += '</ul>\n';
                inList = false;
            }
            if (line) {
                html += `<p>${line}</p>\n`;
            }
        }
    }
    if (inList) html += '</ul>\n';
    
    // Parse bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    return html;
};

// V5: Async RAG Answer Fetcher using SSE Streaming
const fetchRAGAnswer = async (query) => {
    let controller = new AbortController();
    try {
        const response = await fetch(`/api/rag?q=${encodeURIComponent(query)}`, {
            signal: controller.signal
        });
        
        if (!response.ok) {
            throw new Error(await response.text());
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let fullAnswer = "";
        let buffer = "";
        
        els.aiAnswerText.innerHTML = '';
        els.aiAnswerCard.classList.remove('hidden');

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            
            let newlineIndex;
            while ((newlineIndex = buffer.indexOf('\n\n')) >= 0) {
                const message = buffer.slice(0, newlineIndex).trim();
                buffer = buffer.slice(newlineIndex + 2);
                
                if (message.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(message.substring(6));
                        
                        if (data.source) {
                            els.aiSourceFile.textContent = data.source;
                        }
                        
                        if (data.chunk) {
                            fullAnswer += data.chunk;
                            els.aiAnswerText.innerHTML = parseMarkdown(fullAnswer);
                        }
                        
                        if (data.done) {
                            reader.cancel();
                            break;
                        }
                    } catch (e) {
                        console.error("Error parsing SSE chunk:", e, message);
                    }
                }
            }
        }
    } catch (err) {
        console.error('RAG fetch failed:', err);
        if (err.name === 'AbortError') {
            els.aiAnswerText.textContent = "Answer generation timed out. Please try again.";
        } else {
            els.aiAnswerText.textContent = "An error occurred while generating the answer.";
        }
        els.aiSourceFile.textContent = '';
    }
};

// File Detail Logic
const openFileDetail = async (id) => {
    els.modalDetail.classList.remove('hidden');
    els.detailPreview.innerHTML = '<div class="spinner"></div> Loading content preview...';
    
    // Reset state slightly
    els.btnDeleteFile.dataset.id = id;
    els.btnDownloadFile.dataset.id = id;
    
    try {
        const file = await api.get(`/api/files/${id}`);
        
        els.detailIcon.textContent = getFileIcon(file.filename);
        els.detailTitle.textContent = file.title;
        els.detailCategory.textContent = file.category || 'General';
        els.detailDate.textContent = formatDate(file.created_at || new Date());
        els.detailSize.textContent = formatBytes(file.filesize);
        
        els.detailTags.innerHTML = (file.auto_tags || []).map(tag => `<span class="tag">${tag}</span>`).join('') || '<span class="text-muted">No tags</span>';
        els.detailPreview.textContent = file.extracted_text_preview || 'No preview available.';
        
    } catch (err) {
        showToast('Failed to load file details', 'error');
        closeModal(els.modalDetail);
    }
};

const deleteFile = async (id) => {
    if(!confirm('Are you sure you want to delete this file?')) return;
    try {
        await api.delete(`/api/files/${id}`);
        showToast('File deleted successfully');
        closeModal(els.modalDetail);
        await fetchAndRenderFiles();
        // If in search view, might want to refresh search. For now, just clear it.
        if (!els.searchViewContainer.classList.contains('hidden')) {
            els.searchInput.value = '';
            showNormalView();
        }
    } catch (err) {
        showToast('Failed to delete file', 'error');
    }
};

const downloadFile = (id) => {
    // Basic approach: open download endpoint in new tab
    window.open(`/api/files/${id}/download`, '_blank');
};

// Upload Logic
const handleUploadSubmit = async (e) => {
    e.preventDefault();
    const files = els.fileInput.files;
    if (!files || files.length === 0) return showToast('Please select a file', 'error');
    
    const baseTitle = document.getElementById('upload-title').value.trim();
    const category = els.uploadCategory.value;
    const notes = document.getElementById('upload-notes').value;
    
    els.progressContainer.classList.remove('hidden');
    const progressText = document.getElementById('upload-progress-text');
    document.getElementById('btn-submit-upload').disabled = true;
    
    try {
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const formData = new FormData();
            formData.append('file', file);
            
            // Calculate title
            let title = baseTitle;
            if (title) {
                if (files.length > 1) {
                    title = `${baseTitle} ${i + 1}`;
                }
            } else {
                title = file.name.split('.').slice(0, -1).join('.') || file.name;
            }
            
            formData.append('title', title);
            formData.append('category', category);
            formData.append('notes', notes);
            
            progressText.textContent = `Uploading ${i + 1} of ${files.length}...`;
            const progress = (i / files.length) * 100;
            els.progressFill.style.width = `${progress}%`;
            
            await api.post('/api/files/upload', formData, true);
        }
        
        els.progressFill.style.width = '100%';
        progressText.textContent = 'Upload complete!';
        
        setTimeout(() => {
            showToast(`${files.length} file(s) uploaded successfully!`);
            closeModal(els.modalUpload);
            fetchAndRenderFiles();
        }, 500);
        
    } catch (err) {
        showToast('Upload failed', 'error');
        els.progressContainer.classList.add('hidden');
        document.getElementById('btn-submit-upload').disabled = false;
    }
};

const handleFileSelect = () => {
    const files = els.fileInput.files;
    if (!files || files.length === 0) return;
    
    // Auto fill title if empty and only 1 file
    const titleInput = document.getElementById('upload-title');
    if (!titleInput.value && files.length === 1) {
        titleInput.value = files[0].name.split('.').slice(0, -1).join('.') || files[0].name;
    }
    
    if (files.length === 1) {
        document.getElementById('preview-icon').textContent = getFileIcon(files[0].name);
        document.getElementById('preview-name').textContent = files[0].name;
        document.getElementById('preview-size').textContent = `(${formatBytes(files[0].size)})`;
    } else {
        document.getElementById('preview-icon').textContent = '📁';
        document.getElementById('preview-name').textContent = `${files.length} files selected`;
        const totalSize = Array.from(files).reduce((acc, f) => acc + f.size, 0);
        document.getElementById('preview-size').textContent = `(${formatBytes(totalSize)} total)`;
    }
    els.filePreview.classList.remove('hidden');
};

// View Management
const showView = (viewName) => {
    Object.values(els.views).forEach(v => v.classList.remove('active'));
    els.views[viewName].classList.add('active');
};

const showNormalView = () => {
    els.searchViewContainer.classList.add('hidden');
    els.normalViewContainer.classList.remove('hidden');
};

const showSearchView = () => {
    els.normalViewContainer.classList.add('hidden');
    els.searchViewContainer.classList.remove('hidden');
};

const closeModal = (modalEl) => {
    modalEl.classList.add('hidden');
    if (modalEl === els.modalUpload) {
        els.uploadForm.reset();
        els.filePreview.classList.add('hidden');
        els.progressContainer.classList.add('hidden');
        els.progressFill.style.width = '0%';
        document.getElementById('btn-submit-upload').disabled = false;
    }
};

// Events Setup
const setupEventListeners = () => {
    // Top Nav
    els.btnSwitchDept.addEventListener('click', () => {
        document.cookie = "olfm_department=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
        loadDepartmentSelection();
    });
    
    els.searchInput.addEventListener('input', (e) => {
        // Clear suggestions immediately on typing before debounce resolves
        els.searchDropdown.classList.add('hidden');
        currentSuggestion = '';
        debouncedSearch(e.target.value);
    });
    
    els.searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Tab' && currentSuggestion && !els.searchDropdown.classList.contains('hidden')) {
            e.preventDefault(); // Prevent moving focus
            // Replace the last word
            const words = els.searchInput.value.trim().split(/\s+/);
            words.pop();
            words.push(currentSuggestion);
            els.searchInput.value = words.join(' ') + ' ';
            els.searchDropdown.classList.add('hidden');
            currentSuggestion = '';
            handleSearch(els.searchInput.value);
        } else if (e.key === 'Escape') {
            els.searchDropdown.classList.add('hidden');
        }
    });
    
    // Hide dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-wrapper')) {
            if(els.searchDropdown) els.searchDropdown.classList.add('hidden');
        }
    });
    
    els.btnClearSearch.addEventListener('click', () => {
        els.searchInput.value = '';
        showNormalView();
    });
    
    // Upload Modal
    els.btnOpenUpload.addEventListener('click', () => els.modalUpload.classList.remove('hidden'));
    els.btnCloseUpload.addEventListener('click', () => closeModal(els.modalUpload));
    els.btnCancelUpload.addEventListener('click', () => closeModal(els.modalUpload));
    
    // Drag & Drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        els.dropZone.addEventListener(eventName, preventDefaults, false);
    });
    function preventDefaults(e) { e.preventDefault(); e.stopPropagation(); }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        els.dropZone.addEventListener(eventName, () => els.dropZone.classList.add('dragover'), false);
    });
    ['dragleave', 'drop'].forEach(eventName => {
        els.dropZone.addEventListener(eventName, () => els.dropZone.classList.remove('dragover'), false);
    });
    
    els.dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        if (dt.files && dt.files.length > 0) {
            els.fileInput.files = dt.files;
            handleFileSelect();
        }
    });
    
    els.dropZone.addEventListener('click', () => els.fileInput.click());
    els.fileInput.addEventListener('change', () => handleFileSelect());
    els.uploadForm.addEventListener('submit', handleUploadSubmit);
    
    // Detail Modal
    els.btnCloseDetail.addEventListener('click', () => closeModal(els.modalDetail));
    els.btnCloseDetailAlt.addEventListener('click', () => closeModal(els.modalDetail));
    els.btnDeleteFile.addEventListener('click', (e) => deleteFile(e.target.dataset.id));
    els.btnDownloadFile.addEventListener('click', (e) => downloadFile(e.target.dataset.id));
    
    // Click outside to close modals
    window.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal-backdrop')) {
            closeModal(e.target);
        }
    });
};

// Boot
document.addEventListener('DOMContentLoaded', init);
