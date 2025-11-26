document.addEventListener('DOMContentLoaded', async () => {
    // Common elements
    const loginModal = document.getElementById('login-modal');
    const loginBtn = document.getElementById('login-btn');
    const authKeyInput = document.getElementById('auth-key');
    let authKey = localStorage.getItem('xfapi_key') || '';

    // Page containers
    const pages = document.querySelectorAll('.page-content');
    const navLinks = document.querySelectorAll('.nav-link');

    // Page-specific elements
    // Home page
    const speakerList = document.getElementById('speaker-list');
    const speakerSearch = document.getElementById('speaker-search');
    const extendUiArea = document.getElementById('extend-ui-area');
    const generateBtn = document.getElementById('generate-btn');
    const audioPlayer = document.getElementById('audio-player');

    let speakers = [];
    let selectedSpeaker = null;

    let pagesInitialized = {
        home: false,
        settings: false,
        logs: false
    };

    // --- Page Switching Logic ---
    function showPage(pageId) {
        pages.forEach(page => {
            page.classList.toggle('hidden', page.id !== `page-${pageId}`);
        });

        navLinks.forEach(link => {
            link.classList.toggle('active', link.dataset.page === pageId);
        });

        if (!pagesInitialized[pageId]) {
            switch (pageId) {
                case 'home':
                    initHomePage();
                    break;
                case 'settings':
                    initSettingsPage();
                    break;
                case 'logs':
                    initLogsPage();
                    break;
            }
            pagesInitialized[pageId] = true;
        }
    }

    navLinks.forEach(link => {
        link.addEventListener('click', (event) => {
            event.preventDefault();
            const pageId = link.dataset.page;
            showPage(pageId);
        });
    });

    // --- Authentication ---
    async function checkAuth() {
        try {
            const res = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key: authKey })
            });
            if (res.status === 401) {
                loginModal.classList.remove('hidden');
                return false;
            }
            loginModal.classList.add('hidden');
            return true;
        } catch (e) {
            console.error(e);
            return false;
        }
    }

    loginBtn.addEventListener('click', async () => {
        const key = authKeyInput.value;
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key: key })
        });
        if (res.ok) {
            authKey = key;
            localStorage.setItem('xfapi_key', authKey);
            loginModal.classList.add('hidden');
            // Re-initialize the current page after login
            const activePage = document.querySelector('.nav-link.active').dataset.page;
            pagesInitialized[activePage] = false; // Force re-initialization
            showPage(activePage);
        } else {
            await showAlert('密码错误');
        }
    });


    // --- Home Page Logic ---
    function initHomePage() {
        async function loadSpeakers() {
            try {
                const res = await fetch('/api/speakers');
                const rawSpeakers = await res.json();

                const seen = new Set();
                speakers = [];
                for (const spk of rawSpeakers) {
                    if (!seen.has(spk.name)) {
                        seen.add(spk.name);
                        speakers.push(spk);
                    }
                }

                let hasAvatars = false;
                try {
                    const settingsRes = await fetch(`/api/settings?key=${authKey}`);
                    if (settingsRes.ok) {
                        const settings = await settingsRes.json();
                        hasAvatars = settings.has_avatars;
                        window.hasAvatars = hasAvatars;

                        document.getElementById('speed').value = settings.default_speed || 100;
                        document.getElementById('speed-val').textContent = settings.default_speed || 100;
                        document.getElementById('volume').value = settings.default_volume || 100;
                        document.getElementById('volume-val').textContent = settings.default_volume || 100;
                        document.getElementById('audio-type').value = settings.default_audio_type || 'audio/mp3';

                        const defaultSpeakerName = settings.default_speaker;
                        const defaultSpk = speakers.find(s => s.name === defaultSpeakerName);
                        if (defaultSpk) {
                            selectSpeaker(defaultSpk);
                        } else if (speakers.length > 0) {
                            selectSpeaker(speakers[0]);
                        }
                    }
                } catch (e) {
                    console.error('Failed to load settings', e);
                }

                filterAndRender();

            } catch (e) {
                console.error('Failed to load speakers', e);
            }
        }

        function filterAndRender() {
            const searchVal = speakerSearch.value.toLowerCase();
            const localeVal = document.getElementById('locale-filter').value;

            const filtered = speakers.filter(spk => {
                if (searchVal && !spk.name.toLowerCase().includes(searchVal)) {
                    return false;
                }
                if (localeVal !== 'all') {
                    const loc = (spk.locale || '').toLowerCase();
                    if (localeVal === 'zh') {
                        if (!loc.includes('zh') && !loc.includes('cn')) return false;
                    } else if (localeVal === 'en') {
                        if (!loc.includes('en') && !loc.includes('us') && !loc.includes('gb')) return false;
                    } else if (localeVal === 'other') {
                        if (loc.includes('zh') || loc.includes('cn') || loc.includes('en') || loc.includes('us') || loc.includes('gb')) return false;
                    }
                }
                return true;
            });

            renderSpeakers(filtered);
        }

        function renderSpeakers(list) {
            speakerList.innerHTML = '';
            list.forEach(spk => {
                const card = document.createElement('div');
                card.className = 'speaker-card';
                if (selectedSpeaker && selectedSpeaker.name === spk.name) {
                    card.classList.add('selected');
                }

                let avatarHtml = '';
                if (spk.avatar && window.hasAvatars) {
                    const avatarUrl = `/multitts/xfpeiyin/avatar/${spk.avatar}`;
                    avatarHtml = `<img src="${avatarUrl}" class="speaker-avatar" onerror="this.onerror=null;this.outerHTML='<div class=\\'speaker-avatar\\' style=\\'display:flex;justify-content:center;align-items:center;color:#fff;font-size:1.2rem;\\'>${spk.name[0]}</div>'">`;
                } else {
                    avatarHtml = `<div class="speaker-avatar" style="display:flex;justify-content:center;align-items:center;color:#fff;font-size:1.2rem;">${spk.name[0]}</div>`;
                }

                card.innerHTML = `
                    ${avatarHtml}
                    <div class="speaker-info">
                        <div class="speaker-name">${spk.name}</div>
                        <div class="speaker-desc" title="${spk.desc || ''}">${spk.desc || '暂无描述'}</div>
                        <div class="speaker-locale">${spk.locale || '未知'}</div>
                    </div>
                `;

                card.onclick = () => selectSpeaker(spk);
                speakerList.appendChild(card);
            });
        }

        function selectSpeaker(spk) {
            selectedSpeaker = spk;
            document.querySelectorAll('.speaker-card').forEach(c => c.classList.remove('selected'));
            const cards = speakerList.children;
            for (let i = 0; i < cards.length; i++) {
                const name = cards[i].querySelector('.speaker-name').textContent;
                if (name === spk.name) {
                    cards[i].classList.add('selected');
                } else {
                    cards[i].classList.remove('selected');
                }
            }
            renderExtendUI(spk);
        }

        function renderExtendUI(spk) {
            extendUiArea.innerHTML = '';
            extendUiArea.classList.add('hidden');

            extendUiArea.classList.remove('hidden');
            const wrapper = document.createElement('div');
            wrapper.className = 'form-group';

            const label = document.createElement('label');
            label.textContent = "风格";
            wrapper.appendChild(label);

            const select = document.createElement('select');
            select.id = `extend-style`;

            let hasStyles = false;

            if (spk.extendUI) {
                try {
                    const uiConfig = JSON.parse(spk.extendUI);
                    if (Array.isArray(uiConfig)) {
                        uiConfig.forEach(item => {
                            if (item.code === 'style' && item.candidate) {
                                hasStyles = true;
                                for (const [val, name] of Object.entries(item.candidate)) {
                                    const opt = document.createElement('option');
                                    opt.value = val;
                                    opt.textContent = name;
                                    if (val === item.value) opt.selected = true;
                                    select.appendChild(opt);
                                }
                            }
                        });
                    }
                } catch (e) {
                    console.error('Error parsing extendUI', e);
                }
            }

            if (!hasStyles) {
                const opt = document.createElement('option');
                opt.value = "default";
                opt.textContent = "无";
                select.appendChild(opt);
                select.disabled = true;
            }

            wrapper.appendChild(select);
            extendUiArea.appendChild(wrapper);
        }

        speakerSearch.addEventListener('input', filterAndRender);
        document.getElementById('locale-filter').addEventListener('change', filterAndRender);

        document.getElementById('speed').addEventListener('input', (e) => {
            document.getElementById('speed-val').textContent = e.target.value;
        });
        document.getElementById('volume').addEventListener('input', (e) => {
            document.getElementById('volume-val').textContent = e.target.value;
        });

        generateBtn.addEventListener('click', async () => {
            if (!selectedSpeaker) {
                await showAlert('请选择发音人');
                return;
            }
            const text = document.getElementById('tts-text').value;
            if (!text) {
                await showAlert('请输入文本');
                return;
            }
            const speed = parseInt(document.getElementById('speed').value);
            const volume = parseInt(document.getElementById('volume').value);
            const audioType = document.getElementById('audio-type').value;
            let voiceCode = selectedSpeaker.param;
            if (voiceCode === '@style') {
                const styleSelect = document.getElementById('extend-style');
                if (styleSelect) {
                    voiceCode = styleSelect.value;
                } else {
                    try {
                        const uiConfig = JSON.parse(selectedSpeaker.extendUI);
                        const styleItem = uiConfig.find(i => i.code === 'style');
                        if (styleItem) voiceCode = styleItem.value;
                    } catch (e) {}
                }
            }
            generateBtn.disabled = true;
            generateBtn.textContent = '生成中...';
            try {
                const res = await fetch('/api/tts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        text: text,
                        voice: voiceCode,
                        speed: speed,
                        volume: volume,
                        audio_type: audioType,
                        stream: true,
                        key: authKey
                    })
                });
                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || '生成失败');
                }
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                audioPlayer.src = url;
                audioPlayer.style.display = 'block';
                audioPlayer.play();
            } catch (e) {
                await showAlert('错误: ' + e.message);
            } finally {
                generateBtn.disabled = false;
                generateBtn.textContent = '生成语音';
            }
        });

        loadSpeakers();
    }

    // --- Settings Page Logic ---
    function initSettingsPage() {
        const saveBtn = document.getElementById('save-btn');
        const reloadBtn = document.getElementById('reload-btn');
        const togglePassword = document.getElementById('toggle-password');
        const passwordInput = document.getElementById('admin-password');

        async function loadSettings() {
            try {
                const spkRes = await fetch('/api/speakers');
                const speakers = await spkRes.json();
                const spkSelect = document.getElementById('default-speaker');
                spkSelect.innerHTML = '';
                const seen = new Set();
                speakers.forEach(s => {
                    if (!seen.has(s.name)) {
                        seen.add(s.name);
                        const opt = document.createElement('option');
                        opt.value = s.name;
                        opt.textContent = s.name;
                        spkSelect.appendChild(opt);
                    }
                });

                const res = await fetch(`/api/settings?key=${authKey}`);
                if (res.ok) {
                    const settings = await res.json();
                    document.getElementById('auth-enabled').checked = settings.auth_enabled;
                    document.getElementById('admin-password').value = settings.admin_password || '';
                    document.getElementById('special-symbol-mapping').checked = settings.special_symbol_mapping;
                    document.getElementById('default-speaker').value = settings.default_speaker || '聆小糖';
                    document.getElementById('default-speed').value = settings.default_speed || 100;
                    document.getElementById('default-volume').value = settings.default_volume || 100;
                    document.getElementById('default-audio-type').value = settings.default_audio_type || 'audio/mp3';
                    document.getElementById('cache-limit').value = settings.cache_limit !== undefined ? settings.cache_limit : 100;
                    document.getElementById('log-level').value = settings.log_level || 'INFO';
                }
            } catch (e) {
                console.error('Failed to load settings', e);
            }
        }

        saveBtn.addEventListener('click', async () => {
            const settings = {
                auth_enabled: document.getElementById('auth-enabled')?.checked || false,
                admin_password: document.getElementById('admin-password')?.value || '',
                special_symbol_mapping: document.getElementById('special-symbol-mapping')?.checked || false,
                default_speaker: document.getElementById('default-speaker')?.value || '',
                default_speed: parseInt(document.getElementById('default-speed')?.value || 100),
                default_volume: parseInt(document.getElementById('default-volume')?.value || 100),
                default_audio_type: document.getElementById('default-audio-type')?.value || 'audio/mp3',
                cache_limit: parseInt(document.getElementById('cache-limit')?.value || 100),
                log_level: document.getElementById('log-level')?.value || 'INFO',
                key: authKey
            };
            try {
                const res = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });
                if (res.ok) {
                    await showAlert('设置已保存');
                    if (settings.admin_password && settings.auth_enabled) {
                        authKey = settings.admin_password;
                        localStorage.setItem('xfapi_key', authKey);
                    }
                } else {
                    const err = await res.json();
                    await showAlert('保存失败: ' + err.detail);
                }
            } catch (e) {
                await showAlert('保存失败: ' + e.message);
            }
        });

        reloadBtn.addEventListener('click', async () => {
            const confirmed = await showConfirm('确定要重载配置吗？这将重新读取 config.yaml 并扫描 multitts 目录。');
            if (!confirmed) return;
            try {
                const res = await fetch('/api/reload_config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key: authKey })
                });
                if (res.ok) {
                    await showAlert('配置重载成功！');
                    loadSettings();
                } else {
                    const err = await res.json();
                    await showAlert('重载失败: ' + (err.detail || '未知错误'));
                }
            } catch (e) {
                await showAlert('重载失败: ' + e.message);
            }
        });

        if (togglePassword && passwordInput) {
            togglePassword.addEventListener('click', () => {
                const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
                passwordInput.setAttribute('type', type);
                togglePassword.textContent = type === 'password' ? '👁️' : '🔒';
            });
        }

        loadSettings();
    }

    // --- Logs Page Logic ---
    function initLogsPage() {
        const logContainer = document.getElementById('log-container');
        const autoRefreshCheckbox = document.getElementById('auto-refresh');
        const logLimitInput = document.getElementById('log-limit');
        const levelFilter = document.getElementById('level-filter');
        const keywordSearch = document.getElementById('keyword-search');
        let isScrolledToBottom = true;
        let allLogs = [];
        let eventSource;

        function connectEventSource() {
            if (eventSource) eventSource.close();
            
            const ansi_up = new AnsiUp();
            
            eventSource = new EventSource('/api/logs');
            eventSource.onopen = () => addNewLog('日志流连接成功。');
            eventSource.onmessage = (event) => {
                const rawLog = JSON.parse(event.data);
                const htmlLog = ansi_up.ansi_to_html(rawLog);
                addNewLog(htmlLog, true); // Pass a flag to indicate it's HTML
            };
            eventSource.onerror = (err) => {
                addNewLog('日志流连接错误，请检查服务器状态并刷新页面。');
                console.error('EventSource failed:', err);
                eventSource.close();
            };
        }

        function renderLogs() {
            const level = levelFilter.value;
            const keyword = keywordSearch.value.toLowerCase();
            // 如果输入框为空，则不限制（或者使用默认值，这里使用默认值100，如果用户清空则显示全部可能不太好，还是默认100吧）
            // 需求是默认100条，如果用户清空，可以理解为不限制或者默认值。
            // 为了体验，如果为空，我们默认为100。
            let limitVal = logLimitInput.value;
            if (limitVal === '') limitVal = 100;
            const limit = parseInt(limitVal);

            if (autoRefreshCheckbox.checked) {
                logContainer.innerHTML = '';
                let filteredLogs = allLogs.filter(logData => {
                    // We filter based on the raw text content, not the HTML
                    const lowerLog = logData.raw.toLowerCase();
                    const levelMatch = !level || lowerLog.includes(level.toLowerCase());
                    const keywordMatch = !keyword || lowerLog.includes(keyword);
                    return levelMatch && keywordMatch;
                });

                // Apply limit (take last N)
                if (filteredLogs.length > limit) {
                    filteredLogs = filteredLogs.slice(-limit);
                }

                // Render the filtered HTML content
                filteredLogs.forEach(logData => addLogLineToDOM(logData.html, true));
            }
        }

        function addLogLineToDOM(message, isHtml = false) {
            const line = document.createElement('div');
            line.className = 'log-line';
            
            if (isHtml) {
                line.innerHTML = message;
            } else {
                line.textContent = message;
            }
            
            // We don't need to add classes manually anymore as ansi_up handles colors.
            // The classes below could be kept for filtering or other styling if needed.
            const lowerMessage = (isHtml ? line.textContent : message).toLowerCase();
            if (lowerMessage.includes('debug')) line.classList.add('debug');
            else if (lowerMessage.includes('info')) line.classList.add('info');
            else if (lowerMessage.includes('warning')) line.classList.add('warning');
            else if (lowerMessage.includes('error')) line.classList.add('error');
            else if (lowerMessage.includes('critical')) line.classList.add('critical');

            logContainer.appendChild(line);
            if (isScrolledToBottom) {
                logContainer.scrollTop = logContainer.scrollHeight;
            }
        }

        function addNewLog(message, isHtml = false) {
            if (isHtml) {
                // To make filtering work, we store both raw and HTML content
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = message;
                allLogs.push({ html: message, raw: tempDiv.textContent || tempDiv.innerText || '' });
            } else {
                allLogs.push({ html: message, raw: message });
            }

            // Safety cap to prevent memory issues
            if (allLogs.length > 5000) {
                allLogs = allLogs.slice(-5000);
            }

            if (autoRefreshCheckbox.checked) {
                renderLogs();
            }
        }

        logContainer.addEventListener('scroll', () => {
            isScrolledToBottom = logContainer.scrollHeight - logContainer.clientHeight <= logContainer.scrollTop + 1;
        });
        // Set default value
        // logLimitInput.value = 100; // Removed to keep it empty by default as per user request

        autoRefreshCheckbox.addEventListener('change', renderLogs);
        logLimitInput.addEventListener('change', renderLogs);
        logLimitInput.addEventListener('input', renderLogs);
        levelFilter.addEventListener('change', renderLogs);
        keywordSearch.addEventListener('input', renderLogs);

        logContainer.innerHTML = '';
        connectEventSource();
    }

    // --- Initial Load ---
    const isAuthenticated = await checkAuth();
    if (isAuthenticated) {
        showPage('home');
    }
});

// --- Dropdown Arrow Logic ---
function setupDropdownEventListeners() {
    document.querySelectorAll('select').forEach(select => {
        // A flag to track the open state, since the browser's state isn't directly accessible.
        let isOpen = false;

        select.addEventListener('mousedown', (e) => {
            if (isOpen) {
                // If it's open, this click is to close it.
                // Prevent the default action to stop it from reopening immediately.
                e.preventDefault();
                select.blur(); // This will trigger the blur event, which handles cleanup.
            }
            // The 'isOpen' state will be updated by the focus/blur events.
        });

        select.addEventListener('blur', () => {
            // When the select loses focus, it's definitely closed.
            select.classList.remove('open');
            isOpen = false;
        });

        select.addEventListener('focus', () => {
            // When the select gains focus, it's about to open.
            select.classList.add('open');
            isOpen = true;
        });

        select.addEventListener('change', () => {
            // When an option is selected, close and blur it.
            select.blur();
        });
    });
}

    setupDropdownEventListeners();
