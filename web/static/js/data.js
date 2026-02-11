// 数据展示页面JavaScript

let currentTable = 'huya';
let currentPage = 1;
const pageSize = 100;

document.addEventListener('DOMContentLoaded', function() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const refreshBtn = document.getElementById('refreshBtn');
    const tableTitle = document.getElementById('tableTitle');
    const dataTableContainer = document.getElementById('dataTableContainer');
    const pagination = document.getElementById('pagination');

    const tableTitles = {
        weibo: '📱 微博数据',
        huya: '🐯 虎牙数据',
        bilibili_live: '📺 哔哩哔哩直播',
        bilibili_dynamic: '📺 哔哩哔哩动态',
        douyin: '🎬 抖音直播',
        douyu: '🐟 斗鱼直播',
        xhs: '📕 小红书数据'
    };

    // 切换标签页
    tabButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            tabButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentTable = this.dataset.table;
            currentPage = 1;
            tableTitle.textContent = tableTitles[currentTable] || currentTable;
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
                const url = row.url || (row.mid ? `https://m.weibo.cn/detail/${row.mid}` : `https://www.weibo.com/u/${row.UID}`);
                html += `<tr class="data-row-link" data-href="${escapeAttr(url)}" title="点击跳转到微博">
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
        } else if (currentTable === 'huya' || currentTable === 'douyin' || currentTable === 'douyu') {
            const pkCol = currentTable === 'douyin' ? 'douyin_id' : 'room';
            const pkVal = currentTable === 'douyin' ? (row => row.douyin_id) : (row => row.room);
            const linkTitles = { huya: '虎牙直播间', douyin: '抖音直播间', douyu: '斗鱼直播间' };
            html += `<th>${currentTable === 'douyin' ? '抖音号' : '房间号'}</th><th>主播名称</th><th>直播状态</th>`;
            html += '</tr></thead><tbody>';
            rows.forEach(row => {
                const statusText = row.is_live === '1' ? '<span style="color: #10b981; font-weight: 500;">🟢 直播中</span>' : '<span style="color: #94a3b8;">⚪ 未开播</span>';
                const url = row.url || '';
                html += `<tr class="data-row-link" data-href="${escapeAttr(url)}" title="点击跳转到${linkTitles[currentTable]}">
                    <td>${escapeHtml(pkVal(row))}</td>
                    <td>${escapeHtml(row.name)}</td>
                    <td>${statusText}</td>
                </tr>`;
            });
        } else if (currentTable === 'bilibili_live') {
            html += '<th>UID</th><th>UP主</th><th>房间号</th><th>直播状态</th>';
            html += '</tr></thead><tbody>';
            rows.forEach(row => {
                const statusText = row.is_live === '1' ? '<span style="color: #10b981; font-weight: 500;">🟢 直播中</span>' : '<span style="color: #94a3b8;">⚪ 未开播</span>';
                html += `<tr class="data-row-link" data-href="${escapeAttr(row.url || '')}" title="点击跳转到B站直播间">
                    <td>${escapeHtml(row.uid)}</td>
                    <td>${escapeHtml(row.uname)}</td>
                    <td>${escapeHtml(row.room_id)}</td>
                    <td>${statusText}</td>
                </tr>`;
            });
        } else if (currentTable === 'bilibili_dynamic') {
            html += '<th>UID</th><th>UP主</th><th>动态ID</th><th>动态内容</th>';
            html += '</tr></thead><tbody>';
            rows.forEach(row => {
                html += `<tr class="data-row-link" data-href="${escapeAttr(row.url || '')}" title="点击跳转到B站动态">
                    <td>${escapeHtml(row.uid)}</td>
                    <td>${escapeHtml(row.uname)}</td>
                    <td>${escapeHtml(row.dynamic_id)}</td>
                    <td style="max-width: 400px; word-wrap: break-word;">${escapeHtml((row.dynamic_text || '').slice(0, 200))}${(row.dynamic_text || '').length > 200 ? '...' : ''}</td>
                </tr>`;
            });
        } else if (currentTable === 'xhs') {
            html += '<th>Profile ID</th><th>用户名</th><th>最新笔记标题</th>';
            html += '</tr></thead><tbody>';
            rows.forEach(row => {
                html += `<tr class="data-row-link" data-href="${escapeAttr(row.url || '')}" title="点击跳转到小红书">
                    <td>${escapeHtml(row.profile_id)}</td>
                    <td>${escapeHtml(row.user_name)}</td>
                    <td style="max-width: 400px; word-wrap: break-word;">${escapeHtml(row.latest_note_title || '')}</td>
                </tr>`;
            });
        }

        html += '</tbody></table>';
        dataTableContainer.innerHTML = html;

        // 行点击跳转
        dataTableContainer.querySelectorAll('.data-row-link').forEach(tr => {
            tr.addEventListener('click', function (e) {
                // 若点击的是表格内的链接，不拦截
                if (e.target.tagName === 'A' && e.target.href) return;
                const href = this.getAttribute('data-href');
                if (href) window.open(href, '_blank', 'noopener,noreferrer');
            });
        });
    }

    // 属性转义（用于 data-href 等）
    function escapeAttr(text) {
        if (text == null) return '';
        const s = String(text);
        const div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML.replace(/"/g, '&quot;');
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
