document.addEventListener('DOMContentLoaded', function () {
    const logContainer = document.getElementById('log-container');
    const autoRefreshCheckbox = document.getElementById('auto-refresh');
    const levelFilter = document.getElementById('level-filter');
    const keywordSearch = document.getElementById('keyword-search');

    let isScrolledToBottom = true;
    let allLogs = []; // 存储所有日志行

    // 检查用户是否滚动了日志容器
    logContainer.addEventListener('scroll', () => {
        isScrolledToBottom = logContainer.scrollHeight - logContainer.clientHeight <= logContainer.scrollTop + 1;
    });

    // 渲染日志
    function renderLogs() {
        const level = levelFilter.value;
        const keyword = keywordSearch.value.toLowerCase();

        // 如果启用了自动刷新，则显示所有日志
        if (autoRefreshCheckbox.checked) {
            logContainer.innerHTML = ''; // 清空
            const filteredLogs = allLogs.filter(log => {
                const lowerLog = log.toLowerCase();
                const levelMatch = !level || lowerLog.includes(level.toLowerCase());
                const keywordMatch = !keyword || lowerLog.includes(keyword);
                return levelMatch && keywordMatch;
            });

            filteredLogs.forEach(log => addLogLineToDOM(log));
        }
    }

    // 将单条日志添加到DOM
    function addLogLineToDOM(message) {
        const line = document.createElement('div');
        line.className = 'log-line';

        const lowerMessage = message.toLowerCase();
        if (lowerMessage.includes('debug')) {
            line.classList.add('debug');
        } else if (lowerMessage.includes('info')) {
            line.classList.add('info');
        } else if (lowerMessage.includes('warning')) {
            line.classList.add('warning');
        } else if (lowerMessage.includes('error')) {
            line.classList.add('error');
        } else if (lowerMessage.includes('critical')) {
            line.classList.add('critical');
        }

        line.textContent = message;
        logContainer.appendChild(line);

        if (isScrolledToBottom) {
            logContainer.scrollTop = logContainer.scrollHeight;
        }
    }

    // 添加新日志到 allLogs 数组并重新渲染
    function addNewLog(message) {
        allLogs.push(message);
        if (autoRefreshCheckbox.checked) {
            renderLogs();
        }
    }

    // 事件监听
    autoRefreshCheckbox.addEventListener('change', renderLogs);
    levelFilter.addEventListener('change', renderLogs);
    keywordSearch.addEventListener('input', renderLogs);

    // 清空初始的 "连接中..." 消息
    logContainer.innerHTML = '';

    const eventSource = new EventSource('/api/logs');

    eventSource.onopen = function () {
        addNewLog('日志流连接成功。');
    };

    eventSource.onmessage = function (event) {
        const logData = JSON.parse(event.data);
        addNewLog(logData);
    };

    eventSource.onerror = function (err) {
        addNewLog('日志流连接错误，请检查服务器状态并刷新页面。');
        console.error('EventSource failed:', err);
        eventSource.close();
    };
});