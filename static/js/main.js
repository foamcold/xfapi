document.addEventListener('DOMContentLoaded', async () => {
    const speakerList = document.getElementById('speaker-list');
    const speakerSearch = document.getElementById('speaker-search');
    const extendUiArea = document.getElementById('extend-ui-area');
    const generateBtn = document.getElementById('generate-btn');
    const audioPlayer = document.getElementById('audio-player');
    const loginModal = document.getElementById('login-modal');
    const loginBtn = document.getElementById('login-btn');
    const authKeyInput = document.getElementById('auth-key');

    let speakers = [];
    let selectedSpeaker = null;
    let authKey = localStorage.getItem('xfapi_key') || '';

    // 检查认证
    async function checkAuth() {
        try {
            const res = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key: authKey })
            });
            if (res.status === 401) {
                loginModal.classList.remove('hidden');
            } else {
                loadSpeakers();
            }
        } catch (e) {
            console.error(e);
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
            loadSpeakers();
        } else {
            await showAlert('密码错误');
        }
    });

    async function loadSpeakers() {
        try {
            const res = await fetch('/api/speakers');
            const rawSpeakers = await res.json();

            // 去重：保留每个名称第一次出现时的记录
            const seen = new Set();
            speakers = [];
            for (const spk of rawSpeakers) {
                if (!seen.has(spk.name)) {
                    seen.add(spk.name);
                    speakers.push(spk);
                }
            }

            // 首先加载默认值以获取 has_avatars
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

                    // 选择默认发音人
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

            // 初始渲染
            filterAndRender();

        } catch (e) {
            console.error('Failed to load speakers', e);
        }
    }
    function filterAndRender() {
        const searchVal = speakerSearch.value.toLowerCase();
        const localeVal = document.getElementById('locale-filter').value;

        const filtered = speakers.filter(spk => {
            // 搜索过滤器
            if (searchVal && !spk.name.toLowerCase().includes(searchVal)) {
                return false;
            }
            // 语言环境过滤器
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
        // 注意：此处不进行排序以保留配置顺序

        list.forEach(spk => {
            const card = document.createElement('div');
            card.className = 'speaker-card';
            if (selectedSpeaker && selectedSpeaker.name === spk.name) {
                card.classList.add('selected');
            }

            // 头像逻辑
            let avatarHtml = '';
            if (spk.avatar && window.hasAvatars) {
                // 首先尝试 multitts 路径
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
        // 重新渲染以突出显示（效率不高但简单）
        const cards = speakerList.children;
        for (let i = 0; i < cards.length; i++) {
            const name = cards[i].querySelector('.speaker-name').textContent;
            if (name === spk.name) {
                cards[i].classList.add('selected');
            } else {
                cards[i].classList.remove('selected');
            }
        }

        // 处理 extendUI
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

    // 滑块
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

        // 处理带风格的语音代码
        let voiceCode = selectedSpeaker.param; // 例如 '565854553' 或 '@style'

        if (voiceCode === '@style') {
            const styleSelect = document.getElementById('extend-style');
            if (styleSelect) {
                voiceCode = styleSelect.value;
            } else {
                // 如果可能，回退到 extendUI 中的默认值
                try {
                    const uiConfig = JSON.parse(selectedSpeaker.extendUI);
                    const styleItem = uiConfig.find(i => i.code === 'style');
                    if (styleItem) voiceCode = styleItem.value;
                } catch (e) { }
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

    checkAuth();
});
