// 数据展示页面JavaScript

let currentTable = 'weibo';
let currentPage = 1;
const pageSize = 100;

document.addEventListener('DOMContentLoaded', function() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const refreshBtn = document.getElementById('refreshBtn');
    const tableTitle = document.getElementById('tableTitle');
    const dataTableContainer = document.getElementById('dataTableContainer');
    const pagination = document.getElementById('pagination');

    // 切换标签页
    tabButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            tabButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentTable = this.dataset.table;
            currentPage = 1;
            tableTitle.textContent = currentTable === 'weibo' ? '微博数据' : '虎牙数据';
            loadTableData();
        });
    });

    // 刷新数据
    refreshBtn.addEventListener('click', function() {
        loadTableData();
    });

    // 加载表格数据
    async function loadTableData() {
        dataTableContainer.innerHTML = '<div class="loading">加载中...</div>';

        try {
            const response = await fetch(
                `/api/data/${currentTable}?page=${currentPage}&page_size=${pageSize}`
            );
            const data = await response.json();

            if (data.error) {
                dataTableContainer.innerHTML = `<div class="error-message show">${data.error}</div>`;
                return;
            }

            renderTable(data.data);
            renderPagination(data.total_pages, data.total);
        } catch (error) {
            dataTableContainer.innerHTML = `<div class="error-message show">加载失败: ${error.message}</div>`;
        }
    }

    // 渲染表格
    function renderTable(rows) {
        if (rows.length === 0) {
            dataTableContainer.innerHTML = '<div class="loading">暂无数据</div>';
            return;
        }

        let html = '<table><thead><tr>';

        if (currentTable === 'weibo') {
            html += '<th>UID</th><th>用户名</th><th>认证信息</th><th>简介</th><th>粉丝数</th><th>微博数</th><th>文本</th><th>MID</th>';
            html += '</tr></thead><tbody>';
            rows.forEach(row => {
                html += `<tr>
                    <td>${escapeHtml(row.UID)}</td>
                    <td>${escapeHtml(row.用户名)}</td>
                    <td>${escapeHtml(row.认证信息)}</td>
                    <td>${escapeHtml(row.简介 || '')}</td>
                    <td>${escapeHtml(row.粉丝数)}</td>
                    <td>${escapeHtml(row.微博数)}</td>
                    <td style="max-width: 400px; word-wrap: break-word;">${escapeHtml(row.文本 || '')}</td>
                    <td>${escapeHtml(row.mid)}</td>
                </tr>`;
            });
        } else {
            html += '<th>房间号</th><th>主播名称</th><th>直播状态</th>';
            html += '</tr></thead><tbody>';
            rows.forEach(row => {
                const statusText = row.is_live === '1' ? '<span style="color: #e74c3c;">🔴 直播中</span>' : '<span style="color: #95a5a6;">⚫ 未开播</span>';
                html += `<tr>
                    <td>${escapeHtml(row.room)}</td>
                    <td>${escapeHtml(row.name)}</td>
                    <td>${statusText}</td>
                </tr>`;
            });
        }

        html += '</tbody></table>';
        dataTableContainer.innerHTML = html;
    }

    // 渲染分页
    function renderPagination(totalPages, total) {
        if (totalPages <= 1) {
            pagination.innerHTML = '';
            return;
        }

        let html = '';

        // 上一页
        html += `<button ${currentPage === 1 ? 'disabled' : ''} onclick="goToPage(${currentPage - 1})">上一页</button>`;

        // 页码信息
        html += `<span class="page-info">第 ${currentPage} / ${totalPages} 页 (共 ${total} 条)</span>`;

        // 下一页
        html += `<button ${currentPage === totalPages ? 'disabled' : ''} onclick="goToPage(${currentPage + 1})">下一页</button>`;

        pagination.innerHTML = html;
    }

    // 跳转页面
    window.goToPage = function(page) {
        currentPage = page;
        loadTableData();
    };

    // HTML转义
    function escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 初始加载
    loadTableData();
});
