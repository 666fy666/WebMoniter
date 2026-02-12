// 数据展示页面 JavaScript（卡片式展示）
//
// 目标：
// - 不再使用传统表格，而是改为类似平台官方的卡片/信息流展示
// - 微博：头像 + 封面图 + 文本信息流
// - 虎牙/抖音/斗鱼/B站直播：直播卡片网格
// - 其他：信息卡片列表
//

let currentTable = 'huya';
let currentPage = 1;
const pageSize = 100;

document.addEventListener('DOMContentLoaded', function () {
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
        xhs: '📕 小红书数据',
    };

    // 切换标签页
    tabButtons.forEach((btn) => {
        btn.addEventListener('click', function () {
            tabButtons.forEach((b) => b.classList.remove('active'));
            this.classList.add('active');
            currentTable = this.dataset.table;
            currentPage = 1;
            tableTitle.textContent = tableTitles[currentTable] || currentTable;
            loadTableData();
        });
    });

    // 刷新数据
    refreshBtn.addEventListener('click', function () {
        loadTableData();
    });

    // 加载数据
    async function loadTableData() {
        dataTableContainer.innerHTML = '<div class="loading">加载中...</div>';

        try {
            const response = await fetch(
                `/api/data/${currentTable}?page=${currentPage}&page_size=${pageSize}`,
            );
            const data = await response.json();

            if (data.error) {
                dataTableContainer.innerHTML = `<div class="error-message show">${escapeHtml(
                    data.error,
                )}</div>`;
                return;
            }

            renderCards(data.data || []);
            renderPagination(data.total_pages, data.total);
        } catch (error) {
            dataTableContainer.innerHTML = `<div class="error-message show">加载失败: ${escapeHtml(
                error.message,
            )}</div>`;
        }
    }

    // 微博用户名转为与后端一致的安全目录名
    function sanitizeUsername(username) {
        const raw = (username || 'unknown_user').trim();
        const replaced = raw.replace(/[\\/:*?"<>|]/g, '_');
        return (replaced || 'unknown_user').trim();
    }

    // 渲染不同平台的卡片
    function renderCards(rows) {
        if (!rows || rows.length === 0) {
            dataTableContainer.innerHTML = '<div class="loading">暂无数据</div>';
            pagination.innerHTML = '';
            return;
        }

        let html = '';

        if (currentTable === 'weibo') {
            html += '<div class="data-card-grid weibo-card-grid">';
            rows.forEach((row) => {
                const safeName = sanitizeUsername(row.用户名);
                const encodedDir = encodeURIComponent(safeName);
                const coverUrl = `/weibo_img/${encodedDir}/cover_image_phone.jpg`;
                const avatarUrl = `/weibo_img/${encodedDir}/profile_image.jpg`;
                const url =
                    row.url ||
                    (row.mid
                        ? `https://m.weibo.cn/detail/${row.mid}`
                        : `https://www.weibo.com/u/${row.UID}`);

                const textRaw = (row.文本 || '').toString();
                // 文本里原来带了一些缩进和换行，这里简化成信息流短文案
                const compactText = textRaw.replace(/\s+/g, ' ').trim();
                const brief =
                    compactText.length > 160
                        ? `${compactText.slice(0, 160)}...`
                        : compactText || '暂无最新微博内容';

                html += `
<article class="data-card weibo-card data-card-link" data-href="${escapeAttr(url)}">
  <div class="weibo-card-cover">
    <div class="weibo-card-cover-bg" style="background-image: url('${escapeAttr(
        coverUrl,
    )}');"></div>
    <div class="weibo-card-avatar-wrap">
      <img src="${escapeAttr(
          avatarUrl,
      )}" alt="头像" class="weibo-card-avatar" loading="lazy" onerror="this.classList.add('avatar-fallback')">
    </div>
  </div>
  <div class="weibo-card-body">
    <header class="weibo-card-header">
      <div class="weibo-card-user">
        <div class="weibo-card-name">${escapeHtml(row.用户名)}</div>
        <div class="weibo-card-meta">
          <span class="weibo-card-verify">${escapeHtml(row.认证信息 || '普通用户')}</span>
        </div>
      </div>
      <div class="weibo-card-stats">
        <span class="stat-item">粉丝 ${escapeHtml(row.粉丝数 ?? '')}</span>
        <span class="stat-dot">·</span>
        <span class="stat-item">微博 ${escapeHtml(row.微博数 ?? '')}</span>
      </div>
    </header>
    <div class="weibo-card-text">
      ${escapeHtml(brief)}
    </div>
    <footer class="weibo-card-footer">
      <span class="weibo-card-link-hint">点击卡片打开微博详情</span>
    </footer>
  </div>
</article>`;
            });
            html += '</div>';
        } else if (currentTable === 'douyin' || currentTable === 'bilibili_live') {
            // 抖音直播 / B站直播：与 B站动态 统一的 feed 卡片样式
            html += '<div class="data-card-grid feed-card-grid">';
            rows.forEach((row) => {
                let roomLabel = '';
                let roomValue = '';
                let platformBadgeClass = '';
                let platformLabel = '';
                let url = row.url || '';
                if (currentTable === 'douyin') {
                    roomLabel = '抖音号';
                    roomValue = row.douyin_id;
                    platformBadgeClass = 'platform-badge-douyin';
                    platformLabel = '抖音直播';
                    url = url || (row.douyin_id ? `https://live.douyin.com/${row.douyin_id}` : '');
                } else {
                    roomLabel = '房间号';
                    roomValue = row.room_id;
                    platformBadgeClass = 'platform-badge-bilibili';
                    platformLabel = '哔哩哔哩直播';
                    url = url || (row.room_id ? `https://live.bilibili.com/${row.room_id}` : '');
                }
                const isLive = row.is_live === '1' || row.is_live === 1 || row.is_live === true;
                const statusText = isLive ? '🟢 直播中' : '⚪ 未开播';
                const name = row.name || row.uname || '';

                html += `
<article class="data-card feed-card data-card-link" data-href="${escapeAttr(url)}">
  <header class="feed-card-header">
    <div class="feed-card-user">
      <div class="feed-card-name">${escapeHtml(name)}</div>
      <div class="feed-card-sub">${escapeHtml(roomLabel)} ${escapeHtml(roomValue ?? '')}</div>
    </div>
    <span class="platform-badge ${escapeAttr(platformBadgeClass)}">${escapeHtml(platformLabel)}</span>
  </header>
  <div class="feed-card-body">
    <div class="feed-card-text">${escapeHtml(statusText)}</div>
  </div>
  <footer class="feed-card-footer">
    <span class="feed-card-link-hint">点击卡片打开直播间</span>
  </footer>
</article>`;
            });
            html += '</div>';
        } else if (currentTable === 'huya' || currentTable === 'douyu') {
            // 虎牙/斗鱼：保留原直播卡片（带封面/头像的网格卡片）
            html += '<div class="data-card-grid live-card-grid">';
            rows.forEach((row) => {
                let roomLabel = '';
                let roomValue = '';
                let platformLabel = '';
                let url = row.url || '';
                const hasHuyaMedia = currentTable === 'huya';
                const coverUrl =
                    hasHuyaMedia && row.room_pic ? String(row.room_pic) : '';
                const avatarUrl =
                    hasHuyaMedia && row.avatar_url ? String(row.avatar_url) : '';

                if (currentTable === 'huya') {
                    roomLabel = '房间号';
                    roomValue = row.room;
                    platformLabel = '虎牙直播';
                    url = url || (row.room ? `https://www.huya.com/${row.room}` : '');
                } else {
                    roomLabel = '房间号';
                    roomValue = row.room;
                    platformLabel = '斗鱼直播';
                    url = url || (row.room ? `https://www.douyu.com/${row.room}` : '');
                }

                const isLive = row.is_live === '1' || row.is_live === 1 || row.is_live === true;

                html += `
<article class="data-card live-card data-card-link ${
    isLive ? 'live-card-on' : 'live-card-off'
}" data-href="${escapeAttr(url)}">
  <div class="live-card-media">
    <div class="live-card-cover${
        coverUrl ? ' live-card-cover-has-img' : ''
    }"${coverUrl ? ` style="background-image: url('${escapeAttr(coverUrl)}');"` : ''}></div>
    ${
        avatarUrl
            ? `<div class="live-card-avatar-wrap">
      <img src="${escapeAttr(
          avatarUrl,
      )}" alt="头像" class="live-card-avatar" loading="lazy">
    </div>`
            : ''
    }
  </div>
  <div class="live-card-content">
    <div class="live-card-header">
      <div class="live-card-title">
        <span class="platform-badge">${escapeHtml(platformLabel)}</span>
        <h3 class="live-anchor-name">${escapeHtml(row.name || row.uname || '')}</h3>
      </div>
      <div class="live-status-badge ${isLive ? 'status-live' : 'status-offline'}">
        ${isLive ? '🟢 直播中' : '⚪ 未开播'}
      </div>
    </div>
    <div class="live-card-body">
      <div class="live-room">
        <span class="live-room-label">${escapeHtml(roomLabel)}：</span>
        <span class="live-room-value">${escapeHtml(roomValue ?? '')}</span>
      </div>
      <div class="live-card-footer">
        <span class="live-card-link-hint">点击卡片打开直播间</span>
      </div>
    </div>
  </div>
</article>`;
            });
            html += '</div>';
        } else if (currentTable === 'bilibili_dynamic') {
            // B站动态：类似动态流
            html += '<div class="data-card-grid feed-card-grid">';
            rows.forEach((row) => {
                const url =
                    row.url ||
                    (row.dynamic_id
                        ? `https://www.bilibili.com/opus/${row.dynamic_id}`
                        : row.uid
                        ? `https://space.bilibili.com/${row.uid}`
                        : '');
                const text = (row.dynamic_text || '').toString().trim();
                const brief = text.length > 200 ? `${text.slice(0, 200)}...` : text || '暂无动态内容';

                html += `
<article class="data-card feed-card data-card-link" data-href="${escapeAttr(url)}">
  <header class="feed-card-header">
    <div class="feed-card-user">
      <div class="feed-card-name">${escapeHtml(row.uname || '')}</div>
      <div class="feed-card-sub">UID ${escapeHtml(row.uid ?? '')}</div>
    </div>
    <span class="platform-badge platform-badge-bilibili">哔哩哔哩动态</span>
  </header>
  <div class="feed-card-body">
    <div class="feed-card-text">
      ${escapeHtml(brief)}
    </div>
  </div>
  <footer class="feed-card-footer">
    <span class="feed-card-link-hint">点击卡片查看完整动态</span>
  </footer>
</article>`;
            });
            html += '</div>';
        } else if (currentTable === 'xhs') {
            // 小红书：笔记卡片
            html += '<div class="data-card-grid feed-card-grid">';
            rows.forEach((row) => {
                const url =
                    row.url ||
                    (row.profile_id
                        ? `https://www.xiaohongshu.com/user/profile/${row.profile_id}`
                        : '');

                html += `
<article class="data-card feed-card data-card-link" data-href="${escapeAttr(url)}">
  <header class="feed-card-header">
    <div class="feed-card-user">
      <div class="feed-card-name">${escapeHtml(row.user_name || '')}</div>
      <div class="feed-card-sub">ID ${escapeHtml(row.profile_id ?? '')}</div>
    </div>
    <span class="platform-badge platform-badge-xhs">小红书</span>
  </header>
  <div class="feed-card-body">
    <div class="feed-card-text">
      ${escapeHtml(row.latest_note_title || '暂无最新笔记')}
    </div>
  </div>
  <footer class="feed-card-footer">
    <span class="feed-card-link-hint">点击卡片打开用户主页</span>
  </footer>
</article>`;
            });
            html += '</div>';
        } else {
            // 兜底：简单信息卡片
            html += '<div class="data-card-grid feed-card-grid">';
            rows.forEach((row) => {
                html += `
<article class="data-card feed-card">
  <pre class="feed-card-raw">${escapeHtml(JSON.stringify(row, null, 2))}</pre>
</article>`;
            });
            html += '</div>';
        }

        dataTableContainer.innerHTML = html;

        // 卡片点击统一跳转
        dataTableContainer.querySelectorAll('.data-card-link').forEach((card) => {
            card.addEventListener('click', function (e) {
                // 若点击的是内部带 href 的链接，不拦截
                if (e.target.tagName === 'A' && e.target.href) return;
                const href = this.getAttribute('data-href');
                if (href) {
                    window.open(href, '_blank', 'noopener,noreferrer');
                }
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

    // HTML 转义
    function escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 渲染分页
    function renderPagination(totalPages, total) {
        if (!totalPages || totalPages <= 1) {
            pagination.innerHTML = '';
            return;
        }

        let html = '';

        // 上一页
        html += `<button ${
            currentPage === 1 ? 'disabled' : ''
        } onclick="goToPage(${currentPage - 1})">上一页</button>`;

        // 页码信息
        html += `<span class="page-info">第 ${currentPage} / ${totalPages} 页 (共 ${total} 条)</span>`;

        // 下一页
        html += `<button ${
            currentPage === totalPages ? 'disabled' : ''
        } onclick="goToPage(${currentPage + 1})">下一页</button>`;

        pagination.innerHTML = html;
    }

    // 跳转页面（挂到 window 以便分页按钮调用）
    window.goToPage = function (page) {
        if (!page || page < 1 || page === currentPage) return;
        currentPage = page;
        loadTableData();
    };

    // 初始加载
    loadTableData();
});
