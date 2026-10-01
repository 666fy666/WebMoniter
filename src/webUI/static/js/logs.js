// 日志查看页面JavaScript

let autoScrollEnabled = true;
let refreshInterval = null;
let retryCount = 0;
let currentLogTask = ''; // 当前选中的任务ID，空表示今日总日志
const MAX_RETRIES = 5; // 增加重试次数，适应手机端网络不稳定
const REQUEST_TIMEOUT = 60000; // 60秒超时，适应手机端网络延迟
const BASE_RETRY_DELAY = 1000; // 基础重试延迟1秒

// 请求控制：防止并发请求
let currentRequestController = null;
let isRequestInProgress = false;
let lastRequestId = 0; // 请求ID，用于去重
let consecutiveFailures = 0; // 连续失败次数
let cachedLogs = null; // 缓存上一次成功加载的日志内容
let cachedLogsTime = null; // 缓存日志的时间戳

document.addEventListener('DOMContentLoaded', function() {
    const logsContainer = document.getElementById('logsContainer');
    const refreshLogsBtn = document.getElementById('refreshLogsBtn');
    const clearLogsBtn = document.getElementById('clearLogsBtn');
    const autoScrollCheckbox = document.getElementById('autoScroll');
    const logSourceSelect = document.getElementById('logSourceSelect');

    // 加载任务列表并填充下拉框
    async function loadLogTasks() {
        if (!logSourceSelect) return;
        try {
            const response = await fetch('/api/logs/tasks');
            const data = await response.json();
            if (data.error) return;
            // 保留「今日总日志」，追加各任务选项
            while (logSourceSelect.options.length > 1) {
                logSourceSelect.remove(1);
            }
            (data.all_tasks || []).forEach(function(t) {
                const opt = document.createElement('option');
                opt.value = t.job_id;
                opt.textContent = (t.has_log_today ? '今日 · ' : '') + t.job_id;
                logSourceSelect.appendChild(opt);
            });
        } catch (e) {
            console.warn('加载任务列表失败:', e);
        }
    }

    // 日志来源切换
    if (logSourceSelect) {
        logSourceSelect.addEventListener('change', function() {
            currentLogTask = this.value || '';
            cachedLogs = null; // 切换任务时清除缓存，避免显示错误日志
            loadLogs(true, true);
        });
    }

    // 带超时的fetch请求，支持AbortController
    async function fetchWithTimeout(url, controller, timeout = REQUEST_TIMEOUT) {
        let timedOut = false;
        const timeoutId = setTimeout(() => {
            timedOut = true;
            controller.abort();
        }, timeout);

        // 添加请求时间戳，避免缓存问题（特别是手机端）
        const separator = url.includes('?') ? '&' : '?';
        const urlWithTimestamp = url + separator + '_t=' + Date.now() + '&_r=' + Math.random();

        try {
            const response = await fetch(urlWithTimestamp, {
                method: 'GET',
                signal: controller.signal,
                headers: {
                    'Accept': 'application/json',
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0',
                },
            });
            if (!response.ok) throw new Error(`HTTP错误: ${response.status}`);
            return await response.json();
        } catch (error) {
            if (timedOut) {
                const timeoutError = new Error('请求超时，请稍后重试');
                timeoutError.name = 'TimeoutError';
                throw timeoutError;
            }
            throw error;
        } finally {
            clearTimeout(timeoutId);
        }
    }

    // 加载日志
    async function loadLogs(showLoading = true, forceRefresh = false) {
        if (isRequestInProgress && !forceRefresh) return;
        if (currentRequestController) currentRequestController.abort();
        const requestId = ++lastRequestId;

        // 创建新的AbortController
        const controller = new AbortController();
        currentRequestController = controller;
        isRequestInProgress = true;

        if (showLoading && retryCount === 0) {
            // 如果有缓存的日志，先显示缓存，然后尝试刷新
            if (cachedLogs && cachedLogs.length > 0) {
                renderLogs(cachedLogs, true);
            } else {
                logsContainer.innerHTML = '<div class="loading">加载中...</div>';
            }
        }

        const logsUrl = currentLogTask
            ? '/api/logs?lines=500&task=' + encodeURIComponent(currentLogTask)
            : '/api/logs?lines=500';
        try {
            const data = await fetchWithTimeout(logsUrl, controller);
            
            // 再次检查请求是否被取消或已被新请求替代
            if (controller.signal.aborted || requestId !== lastRequestId) {
                return;
            }

            // 请求成功，重置所有错误计数
            retryCount = 0;
            consecutiveFailures = 0;

            if (data.error) {
                // 如果有缓存的日志，显示缓存而不是错误
                if (cachedLogs) {
                    renderLogs(cachedLogs, true);
                    return;
                }
                logsContainer.innerHTML = `<div class="error-message show">${escapeHtml(data.error)}</div>`;
                return;
            }

            if (data.logs && data.logs.length > 0) {
                // 保存到缓存
                cachedLogs = data.logs;
                cachedLogsTime = Date.now();
                renderLogs(data.logs);
            } else {
                // 空日志也保存到缓存
                cachedLogs = [];
                cachedLogsTime = Date.now();
                logsContainer.innerHTML = '<div class="logs-empty">今日暂无日志</div>';
            }
        } catch (error) {
            // 如果请求被取消或已被新请求替代，不处理错误（静默失败）
            if (requestId !== lastRequestId || (error.name !== 'TimeoutError'
                && (error.name === 'AbortError' || controller.signal.aborted))) {
                return;
            }

            // 判断是否为网络错误或超时错误
            const isNetworkError = error.name === 'TypeError' || 
                                 error.name === 'NetworkError' ||
                                 error.name === 'AbortError' ||
                                 error.message.includes('fetch') || 
                                 error.message.includes('网络') || 
                                 error.message.includes('超时') ||
                                 error.message.includes('timeout') ||
                                 error.message.includes('Failed to fetch') ||
                                 error.message.includes('Network request failed') ||
                                 error.message.includes('Load failed') ||
                                 error.message.includes('aborted');

            // 记录错误信息（仅在非取消的情况下）
            console.error('日志加载失败:', {
                name: error.name,
                message: error.message,
                isNetworkError: isNetworkError,
                retryCount: retryCount,
                consecutiveFailures: consecutiveFailures
            });

            if (isNetworkError) {
                retryCount++;
                consecutiveFailures++;
                
                // 如果是网络错误且未达到最大重试次数，自动重试
                if (retryCount <= MAX_RETRIES) {
                    // 递增延迟：1s, 2s, 3s, 4s, 5s
                    const retryDelay = Math.min(BASE_RETRY_DELAY * retryCount, 5000);
                    console.warn(`日志加载失败（网络错误），${retryDelay/1000}秒后自动重试 (${retryCount}/${MAX_RETRIES})...`);
                    
                    // 延迟后重试
                    setTimeout(() => {
                        // 检查是否仍然是最新的请求ID
                        if (requestId === lastRequestId && !isRequestInProgress) {
                            loadLogs(false, false);
                        }
                    }, retryDelay);
                    return;
                }
            } else {
                // 非网络错误，重置重试计数
                retryCount = 0;
            }

            // 达到最大重试次数或非网络错误，如果有缓存的日志，显示缓存而不是错误
            if (cachedLogs && cachedLogs.length > 0) {
                // 显示缓存的日志，并添加提示信息
                renderLogs(cachedLogs, true);
                return;
            }
            
            // 如果没有缓存，才显示错误信息
            const errorMsg = error.message || error.name || '未知错误';
            logsContainer.innerHTML = `
                <div class="error-message show">
                    <div class="error-recovery-message">加载失败: ${escapeHtml(errorMsg)}</div>
                    ${isNetworkError ? '<div class="error-recovery-hint">请检查网络连接后点击刷新按钮重试</div>' : ''}
                    <button type="button" class="btn btn-primary logs-reload-page-btn">刷新页面</button>
                </div>
            `;
            logsContainer.querySelector('.logs-reload-page-btn')?.addEventListener('click', () => {
                window.location.reload();
            });
        } finally {
            // 清除请求状态（仅当这是当前请求时）
            if (currentRequestController === controller && requestId === lastRequestId) {
                currentRequestController = null;
                isRequestInProgress = false;
            }
        }
    }

    // 渲染日志
    function renderLogs(logs, isCached = false) {
        let html = '';
        
        // 如果是缓存的日志，添加提示信息
        if (isCached && cachedLogsTime) {
            const cacheAge = Math.floor((Date.now() - cachedLogsTime) / 1000);
            let cacheAgeText;
            if (cacheAge < 60) {
                cacheAgeText = `${cacheAge}秒前`;
            } else if (cacheAge < 3600) {
                cacheAgeText = `${Math.floor(cacheAge / 60)}分钟前`;
            } else {
                cacheAgeText = `${Math.floor(cacheAge / 3600)}小时前`;
            }
            html += `<div class="cache-notice">
                <span>${uiIcon('warning')} 显示缓存数据</span>（${cacheAgeText}的数据，正在尝试刷新...）
            </div>`;
        }
        
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

        if (logsContainer.innerHTML !== html) logsContainer.innerHTML = html;

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

    // 刷新日志（手动刷新时强制刷新，并更新任务列表）
    refreshLogsBtn.addEventListener('click', async function() {
        setButtonLoading(refreshLogsBtn, true, '刷新中...');
        try {
            await Promise.all([loadLogTasks(), loadLogs(true, true)]);
        } finally {
            setButtonLoading(refreshLogsBtn, false);
        }
    });

    // 清空显示
    clearLogsBtn.addEventListener('click', function() {
        logsContainer.innerHTML = '<div class="logs-empty">日志已清空</div>';
    });

    // 自动滚动开关
    autoScrollCheckbox.addEventListener('change', function() {
        autoScrollEnabled = this.checked;
        if (autoScrollEnabled) {
            logsContainer.scrollTop = logsContainer.scrollHeight;
        }
    });

    // 定期刷新日志（智能间隔）
    // 使用智能刷新：根据网络状况和失败次数动态调整刷新间隔
    function scheduleNextRefresh() {
        // 根据连续失败次数调整刷新间隔
        // 连续失败越多，刷新间隔越长，避免频繁失败
        let refreshDelay = 5000; // 默认5秒
        
        if (consecutiveFailures > 0) {
            // 有连续失败，延长刷新间隔
            refreshDelay = Math.min(5000 + consecutiveFailures * 2000, 30000); // 最多30秒
        }
        
        // 如果请求在进行中，延长等待时间
        if (isRequestInProgress) {
            refreshDelay += 2000; // 额外等待2秒
        }
        
        // 清除旧的定时器
        if (refreshInterval) {
            clearTimeout(refreshInterval);
        }
        
        // 设置新的定时器
        refreshInterval = setTimeout(function() {
            // 如果请求不在进行中，执行刷新
            if (!isRequestInProgress) {
                loadLogs(false, false);
            }
            // 递归调用，继续下一次刷新
            scheduleNextRefresh();
        }, refreshDelay);
    }
    
    // 启动智能刷新
    scheduleNextRefresh();

    // 初始加载：先加载任务列表，再加载日志
    loadLogTasks();
    loadLogs();

    // 页面可见性变化时重新加载（移动端切换应用后回来时）
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            // 页面变为可见时，重置失败计数并立即刷新
            consecutiveFailures = 0;
            retryCount = 0;
            // 如果请求不在进行，立即刷新一次日志
            if (!isRequestInProgress) {
                loadLogs(true, false);
            }
        }
    });

    // 页面卸载时清除定时器和取消请求
    window.addEventListener('beforeunload', function() {
        if (refreshInterval) {
            clearTimeout(refreshInterval);
            refreshInterval = null;
        }
        // 取消正在进行的请求
        if (currentRequestController) {
            currentRequestController.abort();
            currentRequestController = null;
        }
        isRequestInProgress = false;
    });

    // 网络状态变化时重新加载
    window.addEventListener('online', function() {
        console.log('网络已连接，重新加载日志');
        // 重置所有错误计数
        retryCount = 0;
        consecutiveFailures = 0;
        // 如果请求不在进行，立即刷新
        if (!isRequestInProgress) {
            loadLogs(true, false);
        }
    });

    window.addEventListener('offline', function() {
        console.log('网络已断开');
        // 网络断开时，增加失败计数，延长刷新间隔
        consecutiveFailures++;
    });
});
