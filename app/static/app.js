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
    async get(endpoint) {
        const res = await fetch(endpoint, { credentials: 'login' === 'login' ? 'same-origin' : 'include' });
        if (!res.ok) throw new Error(await res.text() || res.statusText);
        return res.json();
    },
    async post(endpoint, data, isFormData = false) {
        const options = { method: 'POST', credentials: 'login' === 'login' ? 'same-origin' : 'include' };
        if (isFormData) {
            options.body = data;
        } else {
            options.headers = { 'Content-Type': 'application/json' };
            options.body = JSON.stringify(data);
        }
        const res = await fetch(endpoint, options);
        if (!res.ok) throw new Error(await res.text() || res.statusText);
        return res.json();
    },
    async delete(endpoint) {
        const res = await fetch(endpoint, { method: 'DELETE', credentials: 'login' === 'login' ? 'same-origin' : 'include' });
        if (!res.ok) throw new Error(await res.text() || res.statusText);
        return res.json();
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

const handleSearch = async (query) => {
    if (!query.trim()) {
        showNormalView();
        els.ghostText.innerHTML = '';
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
    
    try {
        const data = await api.get(`/api/search?q=${encodeURIComponent(query)}&limit=20`);
        const total = (data.exact_matches?.length || 0) + (data.semantic_matches?.length || 0);
        els.searchMetaDisplay.textContent = `Found ${total} results in ${data.search_time_ms || 0}ms`;
        
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
        
        if (total === 0) {
            els.exactResultsContainer.classList.add('hidden');
            els.semanticResultsContainer.classList.add('hidden');
            els.emptyStateSearch.classList.remove('hidden');
            return;
        }
        
        // Render Exact Matches
        if (data.exact_matches && data.exact_matches.length > 0) {
            els.exactResultsContainer.classList.remove('hidden');
            els.exactResultsList.innerHTML = data.exact_matches.map(r => renderResultCard(r, query)).join('');
        } else {
            els.exactResultsContainer.classList.add('hidden');
        }
        
        // Render Semantic Matches
        if (data.semantic_matches && data.semantic_matches.length > 0) {
            els.semanticResultsContainer.classList.remove('hidden');
            els.semanticResultsList.innerHTML = data.semantic_matches.map(r => renderResultCard(r, query)).join('');
        } else {
            els.semanticResultsContainer.classList.add('hidden');
        }
        
        document.querySelectorAll('.search-result-card').forEach(card => {
            card.addEventListener('click', () => openFileDetail(card.dataset.id));
        });
        
    } catch (err) {
        showToast('Search failed', 'error');
        showNormalView();
    }
};

const debouncedSearch = debounce(handleSearch, 50);

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
