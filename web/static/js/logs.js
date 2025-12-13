// 日志查看页面JavaScript

let autoScrollEnabled = true;
let refreshInterval = null;

document.addEventListener('DOMContentLoaded', function() {
    const logsContainer = document.getElementById('logsContainer');
    const refreshLogsBtn = document.getElementById('refreshLogsBtn');
    const clearLogsBtn = document.getElementById('clearLogsBtn');
    const autoScrollCheckbox = document.getElementById('autoScroll');

    // 加载日志
    async function loadLogs() {
        try {
            const response = await fetch('/api/logs?lines=500');
            const data = await response.json();

            if (data.error) {
                logsContainer.innerHTML = `<div class="error-message show">${data.error}</div>`;
                return;
            }

            if (data.logs && data.logs.length > 0) {
                renderLogs(data.logs);
            } else {
                logsContainer.innerHTML = '<div class="loading">今日暂无日志</div>';
            }
        } catch (error) {
            logsContainer.innerHTML = `<div class="error-message show">加载失败: ${error.message}</div>`;
        }
    }

    // 渲染日志
    function renderLogs(logs) {
        let html = '';
        logs.forEach(line => {
            const trimmedLine = line.trim();
            if (!trimmedLine) return;

            let className = 'log-line';
            if (trimmedLine.includes('ERROR') || trimmedLine.includes('错误')) {
                className += ' error';
            } else if (trimmedLine.includes('WARNING') || trimmedLine.includes('警告')) {
                className += ' warning';
            } else if (trimmedLine.includes('INFO') || trimmedLine.includes('信息')) {
                className += ' info';
            } else if (trimmedLine.includes('DEBUG') || trimmedLine.includes('调试')) {
                className += ' debug';
            }

            html += `<div class="${className}">${escapeHtml(trimmedLine)}</div>`;
        });

        logsContainer.innerHTML = html;

        // 自动滚动到底部
        if (autoScrollEnabled) {
            logsContainer.scrollTop = logsContainer.scrollHeight;
        }
    }

    // HTML转义
    function escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 刷新日志
    refreshLogsBtn.addEventListener('click', loadLogs);

    // 清空显示
    clearLogsBtn.addEventListener('click', function() {
        logsContainer.innerHTML = '<div class="loading">日志已清空</div>';
    });

    // 自动滚动开关
    autoScrollCheckbox.addEventListener('change', function() {
        autoScrollEnabled = this.checked;
        if (autoScrollEnabled) {
            logsContainer.scrollTop = logsContainer.scrollHeight;
        }
    });

    // 定期刷新日志（每5秒）
    refreshInterval = setInterval(loadLogs, 5000);

    // 初始加载
    loadLogs();

    // 页面卸载时清除定时器
    window.addEventListener('beforeunload', function() {
        if (refreshInterval) {
            clearInterval(refreshInterval);
        }
    });
});
