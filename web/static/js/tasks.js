// 任务管理页面 JavaScript

// 当前过滤器
let currentFilter = 'all';

// 任务运行状态
const runningTasks = new Set();

// 加载任务列表
async function loadTasks() {
    const container = document.getElementById('tasksContainer');
    container.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const response = await fetch('/api/tasks');
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || '加载任务失败');
        }

        renderTasks(data.tasks);
    } catch (error) {
        console.error('加载任务失败:', error);
        container.innerHTML = `
            <div class="error-state">
                <p>加载任务列表失败: ${error.message}</p>
                <button class="btn btn-primary" onclick="loadTasks()">重试</button>
            </div>
        `;
    }
}

// 渲染任务列表
function renderTasks(tasks) {
    const container = document.getElementById('tasksContainer');
    
    // 根据过滤器筛选任务
    const filteredTasks = currentFilter === 'all' 
        ? tasks 
        : tasks.filter(task => task.type === currentFilter);

    if (filteredTasks.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>暂无${getFilterLabel(currentFilter)}任务</p>
            </div>
        `;
        return;
    }

    // 生成任务卡片列表
    let html = '<div class="task-list">';
    
    filteredTasks.forEach(task => {
        const isRunning = runningTasks.has(task.job_id);
        const typeIcon = task.type === 'monitor' ? '📡' : '⏰';
        const typeClass = task.type === 'monitor' ? 'task-type-monitor' : 'task-type-task';
        
        html += `
            <div class="task-item fade-in" data-job-id="${task.job_id}">
                <div class="task-info">
                    <div class="task-header">
                        <span class="task-type-badge ${typeClass}">${typeIcon} ${task.type_label}</span>
                        <span class="task-id">${task.job_id}</span>
                    </div>
                    <div class="task-description">${task.description}</div>
                    <div class="task-meta">
                        <span class="task-trigger">触发方式: ${task.trigger === 'interval' ? '间隔执行' : 'Cron定时'}</span>
                    </div>
                </div>
                <div class="task-actions">
                    <button 
                        class="btn btn-primary run-task-btn ${isRunning ? 'running' : ''}" 
                        data-job-id="${task.job_id}"
                        ${isRunning ? 'disabled' : ''}
                    >
                        <span class="btn-icon">${isRunning ? '⏳' : '▶️'}</span>
                        <span class="btn-text">${isRunning ? '运行中...' : '运行'}</span>
                    </button>
                    <button 
                        class="btn btn-secondary view-log-btn" 
                        data-job-id="${task.job_id}"
                        title="查看今日日志"
                    >
                        <span class="btn-icon">📝</span>
                        <span class="btn-text">查看日志</span>
                    </button>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;

    // 绑定运行按钮事件
    document.querySelectorAll('.run-task-btn').forEach(btn => {
        btn.addEventListener('click', () => runTask(btn.dataset.jobId));
    });
    // 绑定查看日志按钮事件
    document.querySelectorAll('.view-log-btn').forEach(btn => {
        btn.addEventListener('click', () => openTaskLogModal(btn.dataset.jobId));
    });
}

// 当前查看日志的任务ID（用于弹窗）
let currentTaskLogJobId = null;

// 打开任务日志弹窗
function openTaskLogModal(jobId) {
    currentTaskLogJobId = jobId;
    const modal = document.getElementById('taskLogModal');
    const titleEl = document.getElementById('taskLogModalTitle');
    if (modal && titleEl) {
        titleEl.textContent = '📝 任务日志 - ' + jobId;
        modal.classList.add('show');
        loadTaskLogInModal(jobId);
    }
}

// 关闭任务日志弹窗
function closeTaskLogModal() {
    const modal = document.getElementById('taskLogModal');
    if (modal) {
        modal.classList.remove('show');
    }
    currentTaskLogJobId = null;
}

// 在弹窗中加载任务日志
async function loadTaskLogInModal(jobId) {
    const container = document.getElementById('taskLogModalContent');
    if (!container) return;
    container.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const response = await fetch('/api/logs?lines=200&task=' + encodeURIComponent(jobId));
        const data = await response.json();

        if (data.error) {
            container.innerHTML = '<div class="error-message show">' + escapeHtml(data.error) + '</div>';
            return;
        }

        if (!data.logs || data.logs.length === 0) {
            container.innerHTML = '<div class="loading">今日暂无日志</div>';
            return;
        }

        let html = '';
        data.logs.forEach(line => {
            const trimmedLine = (line || '').trim();
            if (!trimmedLine) return;
            let className = 'log-line';
            if (trimmedLine.includes('ERROR') || trimmedLine.includes('错误')) className += ' error';
            else if (trimmedLine.includes('WARNING') || trimmedLine.includes('警告')) className += ' warning';
            else if (trimmedLine.includes('INFO') || trimmedLine.includes('信息')) className += ' info';
            else if (trimmedLine.includes('DEBUG') || trimmedLine.includes('调试')) className += ' debug';
            html += '<div class="' + className + '">' + escapeHtml(trimmedLine) + '</div>';
        });
        container.innerHTML = html;
        container.scrollTop = container.scrollHeight;
    } catch (error) {
        container.innerHTML = '<div class="error-message show">加载失败: ' + escapeHtml(error.message) + '</div>';
    }
}

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 获取过滤器标签
function getFilterLabel(filter) {
    const labels = {
        'all': '全部',
        'monitor': '监控',
        'task': '定时'
    };
    return labels[filter] || '';
}

// 运行任务
async function runTask(jobId) {
    if (runningTasks.has(jobId)) {
        return;
    }

    const btn = document.querySelector(`.run-task-btn[data-job-id="${jobId}"]`);
    if (!btn) return;

    // 设置运行状态
    runningTasks.add(jobId);
    btn.disabled = true;
    btn.classList.add('running');
    btn.querySelector('.btn-icon').textContent = '⏳';
    btn.querySelector('.btn-text').textContent = '运行中...';

    try {
        const response = await fetch(`/api/tasks/${jobId}/run`, {
            method: 'POST',
        });
        const data = await response.json();

        if (data.success) {
            showToast(`任务 ${jobId} 执行成功`, 'success');
        } else {
            showToast(data.message || `任务 ${jobId} 执行失败`, 'error');
        }
    } catch (error) {
        console.error('运行任务失败:', error);
        showToast(`运行任务失败: ${error.message}`, 'error');
    } finally {
        // 恢复按钮状态
        runningTasks.delete(jobId);
        btn.disabled = false;
        btn.classList.remove('running');
        btn.querySelector('.btn-icon').textContent = '▶️';
        btn.querySelector('.btn-text').textContent = '运行';
    }
}

// 更新标题
function updateTitle(filter) {
    const titleEl = document.getElementById('tasksTitle');
    const titles = {
        'all': '🔮 全部任务',
        'monitor': '📡 监控任务',
        'task': '⏰ 定时任务'
    };
    titleEl.textContent = titles[filter] || titles['all'];
}

// 页面初始化
document.addEventListener('DOMContentLoaded', function() {
    // 加载任务列表
    loadTasks();

    // 绑定刷新按钮
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadTasks);
    }

    // 绑定过滤器标签切换
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            // 移除所有active状态
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            // 添加当前active状态
            this.classList.add('active');
            
            // 更新过滤器
            currentFilter = this.dataset.filter;
            updateTitle(currentFilter);
            
            // 重新加载任务列表
            loadTasks();
        });
    });

    // 任务日志弹窗：关闭按钮、遮罩点击、刷新按钮
    const closeTaskLogModalBtn = document.getElementById('closeTaskLogModal');
    const closeTaskLogBtn = document.getElementById('closeTaskLogBtn');
    const refreshTaskLogBtn = document.getElementById('refreshTaskLogBtn');
    const taskLogModal = document.getElementById('taskLogModal');

    if (closeTaskLogModalBtn) {
        closeTaskLogModalBtn.addEventListener('click', closeTaskLogModal);
    }
    if (closeTaskLogBtn) {
        closeTaskLogBtn.addEventListener('click', closeTaskLogModal);
    }
    if (taskLogModal && taskLogModal.querySelector('.modal-overlay')) {
        taskLogModal.querySelector('.modal-overlay').addEventListener('click', closeTaskLogModal);
    }
    if (refreshTaskLogBtn) {
        refreshTaskLogBtn.addEventListener('click', function() {
            if (currentTaskLogJobId) {
                loadTaskLogInModal(currentTaskLogJobId);
            }
        });
    }
});
