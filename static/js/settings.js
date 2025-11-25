document.addEventListener('DOMContentLoaded', async () => {
    const loginModal = document.getElementById('login-modal');
    const loginBtn = document.getElementById('login-btn');
    const authKeyInput = document.getElementById('auth-key');
    const saveBtn = document.getElementById('save-btn');

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
                loadSettings();
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
            loadSettings();
        } else {
            await showAlert('密码错误');
        }
    });

    async function loadSettings() {
        try {
            // 加载发音人下拉列表
            const spkRes = await fetch('/api/speakers');
            const speakers = await spkRes.json();
            const spkSelect = document.getElementById('default-speaker');
            spkSelect.innerHTML = ''; // 清除现有选项

            // 去重
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

            // 加载设置
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

    if (saveBtn) {
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
                    // 如果密码已更改，则更新本地密钥
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
    }

    const reloadBtn = document.getElementById('reload-btn');
    if (reloadBtn) {
        reloadBtn.addEventListener('click', async () => {
            const confirmed = await showConfirm('确定要重载配置吗？这将重新读取 config.yaml 并扫描 multitts 目录。');
            if (!confirmed) {
                return;
            }
            try {
                const res = await fetch('/api/reload_config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key: authKey })
                });
                if (res.ok) {
                    await showAlert('配置重载成功！');
                    // 重新加载发音人下拉列表
                    loadSettings();
                } else {
                    const err = await res.json();
                    await showAlert('重载失败: ' + (err.detail || '未知错误'));
                }
            } catch (e) {
                await showAlert('重载失败: ' + e.message);
            }
        });
    }

    checkAuth();

    // 密码切换
    const togglePassword = document.getElementById('toggle-password');
    const passwordInput = document.getElementById('admin-password');

    if (togglePassword && passwordInput) {
        togglePassword.addEventListener('click', () => {
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            togglePassword.textContent = type === 'password' ? '👁️' : '🔒';
        });
    }
});
