// 数据展示页面 JavaScript（卡片式展示）
//
// 目标：
// - 不再使用传统表格，而是改为类似平台官方的卡片/信息流展示
// - 微博：头像 + 封面图 + 文本信息流
// - 虎牙/抖音/斗鱼/B站直播：直播卡片网格
// - 其他：信息卡片列表
// - 支持拖拽卡片改变显示顺序，顺序持久化到 localStorage
//

let currentTable = 'weibo';
let currentPage = 1;
const DEFAULT_PAGE_SIZE = 100;
const WEIBO_PAGE_SIZE = 25;
const STORAGE_KEY_PREFIX = 'data-card-order-';
const MAX_LAZY_IMAGE_LOADS = 3;
const LAZY_IMAGE_ROOT_MARGIN = '150px 0px';
const LIGHTBOX_MIN_ZOOM = 1;
const LIGHTBOX_MAX_ZOOM = 5;
const LIGHTBOX_ZOOM_STEP = 0.25;
const LIGHTBOX_SWIPE_MIN_DISTANCE = 48;
const LIGHTBOX_SWIPE_MAX_DURATION_MS = 900;
const LIGHTBOX_SWIPE_VERTICAL_TOLERANCE = 0.75;

function getPageSize() {
    return currentTable === 'weibo' ? WEIBO_PAGE_SIZE : DEFAULT_PAGE_SIZE;
}
let sortableInstance = null;

document.addEventListener('DOMContentLoaded', function () {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const refreshBtn = document.getElementById('refreshBtn');
    const tableTitle = document.getElementById('tableTitle');
    const dataTableContainer = document.getElementById('dataTableContainer');
    const pagination = document.getElementById('pagination');
    let lightboxEl = null;
    let lightboxStageEl = null;
    let lightboxImageEl = null;
    let lightboxCounterEl = null;
    let lightboxDimensionsEl = null;
    let lightboxErrorEl = null;
    let lightboxPrevBtn = null;
    let lightboxNextBtn = null;
    let lightboxThumbsEl = null;
    let lightboxDownloadLink = null;
    let lightboxSaveAllBtn = null;
    let lightboxZoomInBtn = null;
    let lightboxZoomOutBtn = null;
    let lightboxZoomResetBtn = null;
    let lightboxZoomLevelEl = null;
    let lightboxCloseBtn = null;
    let lightboxRetryBtn = null;
    let lightboxLastFocusedEl = null;
    let lightboxImages = [];
    let lightboxThumbs = [];
    let lightboxIndex = 0;
    let lightboxZoom = 1;
    let lightboxPanX = 0;
    let lightboxPanY = 0;
    let lightboxPointers = new Map();
    let lightboxDragState = null;
    let lightboxPinchState = null;
    let lightboxSwipeState = null;
    let lazyImageObserver = null;
    let lazyImageQueue = [];
    let lazyImageQueueScheduled = false;
    let activeLazyImageLoads = 0;
    let pendingLazyObserverEntries = [];
    let lazyObserverRaf = 0;

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

    // 加载数据（虎牙：先取基础数据，再异步加载封面/头像 URL）
    async function loadTableData() {
        dataTableContainer.innerHTML = '<div class="loading">加载中...</div>';

        try {
            const isHuya = currentTable === 'huya';
            const currentPageSize = getPageSize();
            const url = isHuya
                ? `/api/data/${currentTable}?page=${currentPage}&page_size=${currentPageSize}&include_media=false`
                : `/api/data/${currentTable}?page=${currentPage}&page_size=${currentPageSize}`;
            const response = await fetch(url);
            const data = await response.json();

            if (data.error) {
                dataTableContainer.innerHTML = `<div class="error-message show">${escapeHtml(
                    data.error,
                )}</div>`;
                return;
            }

            let rows = data.data || [];
            // 微博按发布时间排序，不使用拖拽保存的顺序
            if (currentTable !== 'weibo') {
                rows = applySavedOrder(rows);
            }
            renderCards(rows);
            renderPagination(data.total_pages, data.total);

            // 虎牙：异步加载封面和头像 URL，再更新卡片
            if (isHuya && rows.length > 0) {
                loadHuyaImages(rows);
            }
        } catch (error) {
            dataTableContainer.innerHTML = `<div class="error-message show">加载失败: ${escapeHtml(
                error.message,
            )}</div>`;
        }
    }

    // 虎牙：异步获取封面/头像 URL 并更新卡片
    async function loadHuyaImages(rows) {
        const rooms = rows.map((r) => r.room).filter(Boolean);
        if (rooms.length === 0) return;
        try {
            const resp = await fetch(
                `/api/data/huya/images?rooms=${encodeURIComponent(rooms.join(','))}`,
            );
            const json = await resp.json();
            if (json.error || !json.data) return;
            const images = json.data;
            rooms.forEach((room) => {
                const info = images[room];
                if (!info) return;
                const card = dataTableContainer.querySelector(
                    `.data-card[data-room="${String(room).replace(/"/g, '\\"')}"]`,
                );
                if (!card) return;
                const cover = card.querySelector('.live-card-cover');
                const avatarImg = card.querySelector('.live-card-avatar');
                if (info.room_pic && cover) {
                    cover.classList.add('live-card-cover-has-img');
                    cover.style.backgroundImage = `url('${info.room_pic.replace(/'/g, "\\'")}')`;
                }
                if (info.avatar_url && avatarImg) {
                    avatarImg.src = info.avatar_url;
                    avatarImg.style.display = '';
                }
            });
        } catch (e) {
            console.warn('虎牙图片 URL 加载失败:', e);
        }
    }

    // 微博用户名转为与后端一致的安全目录名
    function sanitizeUsername(username) {
        const raw = (username || 'unknown_user').trim();
        const replaced = raw.replace(/[\\/:*?"<>|]/g, '_');
        return (replaced || 'unknown_user').trim();
    }

    // 从数据行提取唯一 ID，用于拖拽排序持久化
    function getCardId(row, index) {
        if (currentTable === 'weibo') return String(row.UID ?? row.mid ?? index);
        if (currentTable === 'huya' || currentTable === 'douyu') return String(row.room ?? index);
        if (currentTable === 'bilibili_live') return String(row.room_id ?? row.uid ?? index);
        if (currentTable === 'bilibili_dynamic') return String(row.dynamic_id ?? row.uid ?? index);
        if (currentTable === 'douyin') return String(row.douyin_id ?? index);
        if (currentTable === 'xhs') return String(row.profile_id ?? index);
        return String(index);
    }

    // 从 localStorage 读取保存的排序，并应用到数据行
    function applySavedOrder(rows) {
        if (!rows || rows.length === 0) return rows;
        const key = `${STORAGE_KEY_PREFIX}${currentTable}-${currentPage}`;
        try {
            const saved = localStorage.getItem(key);
            if (!saved) return rows;
            const order = JSON.parse(saved);
            const idToRow = new Map();
            rows.forEach((r, i) => idToRow.set(getCardId(r, i), r));
            const result = [];
            for (const id of order) {
                const row = idToRow.get(id);
                if (row) result.push(row);
            }
            // 若有新数据（ID 不在保存顺序中），追加到末尾
            rows.forEach((r, i) => {
                const id = getCardId(r, i);
                if (!order.includes(id)) result.push(r);
            });
            return result.length > 0 ? result : rows;
        } catch {
            return rows;
        }
    }

    // 保存当前卡片顺序到 localStorage
    function saveCardOrder() {
        const grid = dataTableContainer.querySelector('.data-card-grid');
        if (!grid) return;
        const cards = grid.querySelectorAll('.data-card[data-id]');
        const order = Array.from(cards).map((c) => c.getAttribute('data-id'));
        if (order.length === 0) return;
        const key = `${STORAGE_KEY_PREFIX}${currentTable}-${currentPage}`;
        try {
            localStorage.setItem(key, JSON.stringify(order));
        } catch (e) {
            console.warn('保存卡片顺序失败:', e);
        }
    }

    // 初始化拖拽排序
    function initSortable() {
        if (sortableInstance) {
            sortableInstance.destroy();
            sortableInstance = null;
        }
        const grid = dataTableContainer.querySelector('.data-card-grid');
        if (!grid || typeof Sortable === 'undefined') return;
        sortableInstance = new Sortable(grid, {
            handle: '.data-card-drag-handle',
            animation: 200,
            ghostClass: 'data-card-dragging',
            chosenClass: 'data-card-chosen',
            dragClass: 'data-card-drag',
            onEnd: function () {
                saveCardOrder();
            },
        });
    }

    function runWhenIdle(callback) {
        if ('requestIdleCallback' in window) {
            window.requestIdleCallback(callback, { timeout: 220 });
            return;
        }
        window.setTimeout(() => callback({ timeRemaining: () => 12 }), 16);
    }

    function updateWeiboMediaPresentation(img) {
        const videoCover = img.closest('.weibo-video-cover');
        if (videoCover && img.naturalWidth && img.naturalHeight) {
            const naturalRatio = img.naturalWidth / img.naturalHeight;
            const isPortrait = naturalRatio < 0.9;
            const displayRatio = isPortrait
                ? 3 / 4
                : Math.min(16 / 9, Math.max(1, naturalRatio));
            videoCover.classList.toggle('is-portrait', isPortrait);
            videoCover.style.setProperty('--weibo-video-aspect', displayRatio.toFixed(4));
            return;
        }

        const item = img.closest('.weibo-media-item');
        if (!item) return;

        item.classList.add('is-loaded');
        const grid = item.closest('.weibo-media-grid');
        if (
            !grid ||
            !grid.classList.contains('weibo-media-count-1') ||
            !img.naturalWidth ||
            !img.naturalHeight
        ) {
            return;
        }

        // 单图根据实际构图调整舞台比例，极端长图/宽图仍限制在舒适浏览范围内。
        const naturalRatio = img.naturalWidth / img.naturalHeight;
        const displayRatio = Math.min(16 / 9, Math.max(3 / 4, naturalRatio));
        item.style.setProperty('--weibo-media-aspect', displayRatio.toFixed(4));
    }

    function markLazyImageLoaded(img, finish) {
        if (typeof img.decode === 'function') {
            img.decode()
                .then(() => {
                    updateWeiboMediaPresentation(img);
                    img.classList.add('image-loaded');
                    finish();
                })
                .catch(() => {
                    updateWeiboMediaPresentation(img);
                    img.classList.add('image-loaded');
                    finish();
                });
            return;
        }
        updateWeiboMediaPresentation(img);
        img.classList.add('image-loaded');
        finish();
    }

    function loadLazyImage(img) {
        if (!img || !img.isConnected || !dataTableContainer.contains(img)) return;
        if (img.dataset.lazyVisible === '0') return;
        const src = img.dataset.src;
        if (!src) return;
        activeLazyImageLoads += 1;
        img.dataset.lazyLoading = '1';

        const finish = () => {
            activeLazyImageLoads = Math.max(0, activeLazyImageLoads - 1);
            img.removeAttribute('data-lazy-loading');
            scheduleLazyImageQueue();
        };
        img.addEventListener(
            'load',
            () => {
                markLazyImageLoaded(img, finish);
            },
            { once: true },
        );
        img.addEventListener(
            'error',
            () => {
                img.classList.add('image-loaded');
                finish();
            },
            { once: true },
        );

        img.src = src;
        img.removeAttribute('data-src');
        img.removeAttribute('data-lazy-queued');
    }

    function flushLazyObserverEntries() {
        lazyObserverRaf = 0;
        const entries = pendingLazyObserverEntries;
        pendingLazyObserverEntries = [];
        entries.forEach((entry) => {
            const img = entry.target;
            if (entry.isIntersecting) {
                img.dataset.lazyVisible = '1';
                enqueueLazyImage(img);
                return;
            }
            img.dataset.lazyVisible = '0';
        });
    }

    function scheduleLazyImageQueue() {
        if (lazyImageQueueScheduled || lazyImageQueue.length === 0) return;
        lazyImageQueueScheduled = true;
        runWhenIdle(processLazyImageQueue);
    }

    function processLazyImageQueue(deadline) {
        lazyImageQueueScheduled = false;
        let count = 0;
        while (
            lazyImageQueue.length > 0 &&
            activeLazyImageLoads < MAX_LAZY_IMAGE_LOADS &&
            count < MAX_LAZY_IMAGE_LOADS &&
            (!deadline || deadline.didTimeout || deadline.timeRemaining() > 4)
        ) {
            const img = lazyImageQueue.shift();
            if (img && img.dataset.lazyVisible === '0') {
                img.removeAttribute('data-lazy-queued');
                continue;
            }
            loadLazyImage(img);
            count += 1;
        }
        scheduleLazyImageQueue();
    }

    function enqueueLazyImage(img) {
        if (!img || img.dataset.lazyQueued === '1' || img.dataset.lazyLoading === '1') return;
        img.dataset.lazyQueued = '1';
        lazyImageQueue.push(img);
        scheduleLazyImageQueue();
    }

    function initLazyImages() {
        if (lazyImageObserver) {
            lazyImageObserver.disconnect();
            lazyImageObserver = null;
        }
        if (lazyObserverRaf) {
            cancelAnimationFrame(lazyObserverRaf);
            lazyObserverRaf = 0;
        }
        pendingLazyObserverEntries = [];
        lazyImageQueue = lazyImageQueue.filter((img) => img.isConnected);
        activeLazyImageLoads = 0;

        const lazyImages = Array.from(dataTableContainer.querySelectorAll('img[data-src]'));
        if (lazyImages.length === 0) return;

        if (!('IntersectionObserver' in window)) {
            lazyImages.forEach(enqueueLazyImage);
            return;
        }

        lazyImageObserver = new IntersectionObserver(
            (entries) => {
                pendingLazyObserverEntries.push(...entries);
                if (!lazyObserverRaf) {
                    lazyObserverRaf = requestAnimationFrame(flushLazyObserverEntries);
                }
            },
            {
                root: null,
                rootMargin: LAZY_IMAGE_ROOT_MARGIN,
                threshold: 0.01,
            },
        );

        lazyImages.forEach((img) => lazyImageObserver.observe(img));
    }

    function getWeiboMediaClass(count) {
        if (count === 1) return 'weibo-media-count-1';
        if (count === 2) return 'weibo-media-count-2';
        if (count === 4) return 'weibo-media-count-4';
        return 'weibo-media-count-grid';
    }

    function renderWeiboMedia(images, thumbs) {
        const allImages = Array.isArray(images)
            ? images.filter((src) => typeof src === 'string' && src.trim()).map((src) => src.trim())
            : [];
        if (allImages.length === 0) return '';

        const allThumbs = allImages.map((src, index) => {
            const thumb = Array.isArray(thumbs) ? thumbs[index] : '';
            return typeof thumb === 'string' && thumb.trim() ? thumb.trim() : src.trim();
        });
        const hasOverflow = allImages.length > 9;
        const previewImages = hasOverflow ? allImages.slice(0, 8) : allImages.slice(0, 9);
        const previewCount = previewImages.length + (hasOverflow ? 1 : 0);
        const mediaClass = getWeiboMediaClass(previewCount);
        const items = previewImages
            .map(
                (src, index) => `
        <button type="button" class="weibo-media-item" data-image-index="${index}" aria-label="打开第 ${index + 1} 张微博原图，完整尺寸预览" title="查看完整原图">
          <img class="weibo-media-img" data-src="${escapeAttr(
              allThumbs[index],
          )}" data-full-src="${escapeAttr(src.trim())}" alt="微博图片 ${index + 1}" decoding="async" fetchpriority="low" draggable="false">
        </button>`,
            )
            .join('');

        const overflowItem = hasOverflow
            ? `
        <button type="button" class="weibo-media-item weibo-media-item-more" data-image-index="${previewImages.length}" aria-label="打开图片预览，共 ${allImages.length} 张微博原图" title="查看全部原图">
          <img class="weibo-media-img" data-src="${escapeAttr(
              allThumbs[previewImages.length],
          )}" data-full-src="${escapeAttr(
                  allImages[previewImages.length],
              )}" alt="微博图片 ${previewImages.length + 1}" decoding="async" fetchpriority="low" draggable="false">
          <span class="weibo-media-more-mask" aria-hidden="true">
            <span class="weibo-media-more-label">+${allImages.length - previewImages.length}</span>
            <span class="weibo-media-more-sub">查看全部</span>
          </span>
        </button>`
            : '';

        return `<div class="weibo-media-grid ${mediaClass}" data-count="${
            allImages.length
        }" data-preview-count="${previewCount}" data-images="${escapeAttr(
            JSON.stringify(allImages),
        )}" data-thumbs="${escapeAttr(JSON.stringify(allThumbs))}">${items}${overflowItem}</div>`;
    }

    function renderWeiboTextBlock(text, className) {
        const content = (text || '').toString().trim();
        if (!content) return '';
        return `<div class="${escapeAttr(className)}">${content
            .split('\n')
            .map((line) => escapeHtml(line))
            .join('<br>')}</div>`;
    }

    function getSafeHttpUrl(value) {
        const raw = (value || '').toString().trim();
        if (!raw) return '';
        try {
            const parsed = new URL(raw, window.location.origin);
            return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? raw : '';
        } catch {
            return '';
        }
    }

    function renderSegmentText(value) {
        return escapeHtml((value || '').toString()).replace(/\n/g, '<br>');
    }

    function escapeRegExp(value) {
        return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    function stripWeiboTagsFromText(value, tags) {
        let content = (value || '').toString();
        if (!Array.isArray(tags) || tags.length === 0) return content;
        tags
            .map((tag) => (tag || '').toString().trim())
            .filter(Boolean)
            .forEach((tag) => {
                content = content.replace(new RegExp(`#${escapeRegExp(tag)}#`, 'g'), '');
            });
        return content
            .replace(/[ \t]{2,}/g, ' ')
            .replace(/[ \t]+\n/g, '\n')
            .replace(/\n[ \t]+/g, '\n')
            .replace(/\n{3,}/g, '\n\n');
    }

    function renderWeiboContentSegments(segments, fallbackText, className, tags) {
        const fallbackContent = stripWeiboTagsFromText(fallbackText, tags);
        if (!Array.isArray(segments) || segments.length === 0) {
            return renderWeiboTextBlock(fallbackContent, className);
        }
        let visibleText = '';
        const content = segments
            .map((segment) => {
                if (!segment || typeof segment !== 'object') return '';
                let label = stripWeiboTagsFromText(segment.text, tags);
                if (!label) return '';
                label = label.replace(/(?:https?:)?\/\/[^\s<>"'\]\[）)]+/gi, '网页链接');
                visibleText += label;
                const emojiSrc =
                    segment.type === 'emoji' ? getSafeHttpUrl(segment.src) : '';
                if (emojiSrc) {
                    return `<img class="weibo-inline-emoji" data-src="${escapeAttr(
                        emojiSrc,
                    )}" alt="${escapeAttr(label)}" title="${escapeAttr(
                        label,
                    )}" decoding="async" fetchpriority="low" referrerpolicy="no-referrer" draggable="false">`;
                }
                const renderedLabel = renderSegmentText(label);
                const url = segment.type === 'link' ? getSafeHttpUrl(segment.url) : '';
                if (!url) return renderedLabel;
                return `<a class="weibo-content-link" href="${escapeAttr(
                    url,
                )}" target="_blank" rel="noopener noreferrer">${renderedLabel}</a>`;
            })
            .join('')
            .trim();
        return content && visibleText.trim()
            ? `<div class="${escapeAttr(className)}">${content}</div>`
            : renderWeiboTextBlock(fallbackContent, className);
    }

    function renderWeiboContentType(contentType) {
        const typeMap = {
            repost: ['转发', 'repost'],
            video: ['视频', 'video'],
            image: ['图文', 'image'],
            text: ['文字', 'text'],
        };
        const item = typeMap[(contentType || '').toString().toLowerCase()] || typeMap.text;
        return `<span class="weibo-content-type weibo-content-type-${item[1]}">${item[0]}</span>`;
    }

    function renderWeiboTags(tags) {
        if (!Array.isArray(tags)) return '';
        const values = tags
            .map((tag) => (tag || '').toString().trim())
            .filter(Boolean);
        if (values.length === 0) return '';
        return `<div class="weibo-tag-list" aria-label="微博话题">${values
            .map((tag) => `<span class="weibo-tag">#${escapeHtml(tag)}#</span>`)
            .join('')}</div>`;
    }

    function renderWeiboVideoCover(cover, thumb, detailUrl) {
        const originalSrc = getSafeHttpUrl(cover);
        const previewSrc = getSafeHttpUrl(thumb) || originalSrc;
        if (!previewSrc) return '';
        const url = getSafeHttpUrl(detailUrl);
        const tagName = url ? 'a' : 'div';
        const href = url
            ? ` href="${escapeAttr(url)}" target="_blank" rel="noopener noreferrer"`
            : '';
        return `<${tagName} class="weibo-video-cover"${href} aria-label="打开微博视频详情">
          <img class="weibo-video-cover-img" data-src="${escapeAttr(
              previewSrc,
          )}" data-fallback-src="${escapeAttr(originalSrc)}" alt="微博视频封面" decoding="async" fetchpriority="low">
          <span class="weibo-video-play" aria-hidden="true">▶</span>
          <span class="weibo-video-label">点开微博看视频</span>
        </${tagName}>`;
    }

    function renderWeiboRetweet(retweetedStatus) {
        if (!retweetedStatus || typeof retweetedStatus !== 'object') return '';

        const userName = (retweetedStatus.user_name || '未知用户').toString().trim();
        const verified = (retweetedStatus.verified || '').toString().trim();
        const createdAt = (retweetedStatus.created_at || '').toString().trim();
        const mid = (retweetedStatus.mid || '').toString().trim();
        const url =
            (retweetedStatus.url || '').toString().trim() ||
            (mid ? `https://m.weibo.cn/detail/${mid}` : '');
        const text = (retweetedStatus.text || '').toString().trim();
        const unavailable = Boolean(retweetedStatus.source_unavailable);
        const videoHtml = renderWeiboVideoCover(
            retweetedStatus.video_cover,
            retweetedStatus.video_cover_thumb,
            url,
        );
        const mediaHtml = renderWeiboMedia(
            retweetedStatus.images || [],
            retweetedStatus.image_thumbs || [],
        );
        const textHtml =
            renderWeiboContentSegments(
                retweetedStatus.content_segments,
                text || (unavailable ? '原微博已不可见' : '原微博暂无正文'),
                'weibo-retweet-text',
                retweetedStatus.tags,
            ) || '';
        const tagHtml = renderWeiboTags(retweetedStatus.tags);
        const typeHtml = renderWeiboContentType(retweetedStatus.content_type);
        const hrefAttr = url ? ` data-href="${escapeAttr(url)}"` : '';
        const stateClass = unavailable ? ' weibo-retweet-unavailable' : '';

        return `
      <section class="weibo-retweet-block${stateClass}"${hrefAttr}>
        <div class="weibo-retweet-header">
          <span class="weibo-retweet-name">@${escapeHtml(userName)}</span>
          ${typeHtml}
          ${verified ? `<span class="weibo-retweet-verify">${escapeHtml(verified)}</span>` : ''}
          ${createdAt ? `<span class="weibo-retweet-time">${escapeHtml(createdAt)}</span>` : ''}
        </div>
        <div class="weibo-retweet-body">
          ${textHtml}
          ${tagHtml}
          ${mediaHtml}
          ${videoHtml}
        </div>
        ${url ? '<div class="weibo-retweet-hint">查看原微博</div>' : ''}
      </section>`;
    }

    function getListFromMediaGrid(grid, datasetName) {
        try {
            const values = JSON.parse(grid.dataset[datasetName] || '[]');
            return Array.isArray(values)
                ? values.filter((src) => typeof src === 'string' && src.trim()).map((src) => src.trim())
                : [];
        } catch {
            return [];
        }
    }

    function getWeiboMediaPayload(grid) {
        const images = getListFromMediaGrid(grid, 'images');
        const thumbs = getListFromMediaGrid(grid, 'thumbs');
        return {
            images,
            thumbs: images.map((src, index) => {
                const thumb = thumbs[index];
                return typeof thumb === 'string' && thumb.trim() ? thumb.trim() : src;
            }),
        };
    }

    function getEventElement(event) {
        if (event.target instanceof Element) return event.target;
        return event.target && event.target.parentElement ? event.target.parentElement : null;
    }

    function getImageDownloadName(src, index) {
        let mid = 'image';
        let extension = '.jpg';
        try {
            const url = new URL(src, window.location.href);
            const parts = url.pathname
                .split('/')
                .filter(Boolean)
                .map((part) => decodeURIComponent(part));
            const postsIndex = parts.indexOf('posts');
            if (postsIndex >= 0 && parts[postsIndex + 1]) {
                mid = parts[postsIndex + 1];
            }
            const filename = parts[parts.length - 1] || '';
            const match = filename.match(/\.([a-z0-9]{2,5})$/i);
            if (match) {
                extension = `.${match[1].toLowerCase()}`;
            }
        } catch {
            // 使用默认文件名。
        }
        const safeMid = String(mid).replace(/[^\w.-]+/g, '_') || 'image';
        return `weibo-${safeMid}-${String(index + 1).padStart(2, '0')}${extension}`;
    }

    function updateLightboxDownloadLink() {
        if (!lightboxDownloadLink || !lightboxImages.length) return;
        const src = lightboxImages[lightboxIndex];
        lightboxDownloadLink.href = src;
        lightboxDownloadLink.download = getImageDownloadName(src, lightboxIndex);
        if (lightboxSaveAllBtn) {
            lightboxSaveAllBtn.hidden = lightboxImages.length < 2;
        }
    }

    function downloadImage(src, index) {
        if (!src) return;
        const link = document.createElement('a');
        link.href = src;
        link.download = getImageDownloadName(src, index);
        link.rel = 'noopener';
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        link.remove();
    }

    function saveAllLightboxImages() {
        lightboxImages.forEach((src, index) => {
            window.setTimeout(() => downloadImage(src, index), index * 160);
        });
    }

    function clamp(value, min, max) {
        return Math.min(max, Math.max(min, value));
    }

    function resetLightboxGestureState() {
        lightboxPointers.clear();
        lightboxDragState = null;
        lightboxPinchState = null;
        lightboxSwipeState = null;
        if (lightboxImageEl) {
            lightboxImageEl.classList.remove('is-dragging');
        }
    }

    function applyLightboxTransform() {
        if (!lightboxImageEl) return;
        if (lightboxZoom <= LIGHTBOX_MIN_ZOOM) {
            lightboxPanX = 0;
            lightboxPanY = 0;
        }

        lightboxImageEl.style.transform = `translate3d(${lightboxPanX}px, ${lightboxPanY}px, 0) scale(${lightboxZoom})`;
        lightboxImageEl.classList.toggle('is-zoomed', lightboxZoom > LIGHTBOX_MIN_ZOOM);

        if (lightboxZoomLevelEl) {
            lightboxZoomLevelEl.textContent = `${Math.round(lightboxZoom * 100)}%`;
        }
        if (lightboxZoomOutBtn) {
            lightboxZoomOutBtn.disabled = lightboxZoom <= LIGHTBOX_MIN_ZOOM;
        }
        if (lightboxZoomInBtn) {
            lightboxZoomInBtn.disabled = lightboxZoom >= LIGHTBOX_MAX_ZOOM;
        }
        if (lightboxZoomResetBtn) {
            lightboxZoomResetBtn.disabled =
                lightboxZoom <= LIGHTBOX_MIN_ZOOM && lightboxPanX === 0 && lightboxPanY === 0;
        }
    }

    function setLightboxZoom(nextZoom, options = {}) {
        const previousZoom = lightboxZoom;
        lightboxZoom = clamp(nextZoom, LIGHTBOX_MIN_ZOOM, LIGHTBOX_MAX_ZOOM);

        if (lightboxZoom <= LIGHTBOX_MIN_ZOOM) {
            lightboxPanX = 0;
            lightboxPanY = 0;
        } else if (options.clientX != null && options.clientY != null && previousZoom > 0) {
            const rect = lightboxImageEl.getBoundingClientRect();
            const dx = options.clientX - (rect.left + rect.width / 2);
            const dy = options.clientY - (rect.top + rect.height / 2);
            const ratio = lightboxZoom / previousZoom;
            lightboxPanX += dx * (1 - ratio);
            lightboxPanY += dy * (1 - ratio);
        }

        applyLightboxTransform();
    }

    function resetLightboxZoom() {
        lightboxZoom = LIGHTBOX_MIN_ZOOM;
        lightboxPanX = 0;
        lightboxPanY = 0;
        resetLightboxGestureState();
        applyLightboxTransform();
    }

    function zoomLightboxBy(delta, options = {}) {
        setLightboxZoom(lightboxZoom + delta, options);
    }

    function getPointerDistance(points) {
        const [first, second] = points;
        return Math.hypot(second.x - first.x, second.y - first.y);
    }

    function getPointerCenter(points) {
        const [first, second] = points;
        return {
            x: (first.x + second.x) / 2,
            y: (first.y + second.y) / 2,
        };
    }

    function handleLightboxPointerDown(e) {
        if (!lightboxImageEl || e.button > 0) return;
        lightboxImageEl.setPointerCapture(e.pointerId);
        lightboxPointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

        if (lightboxPointers.size === 1 && lightboxZoom > LIGHTBOX_MIN_ZOOM) {
            lightboxSwipeState = null;
            lightboxDragState = {
                pointerId: e.pointerId,
                startX: e.clientX,
                startY: e.clientY,
                panX: lightboxPanX,
                panY: lightboxPanY,
            };
            lightboxImageEl.classList.add('is-dragging');
        } else if (lightboxPointers.size === 1 && lightboxImages.length > 1) {
            lightboxSwipeState = {
                pointerId: e.pointerId,
                startX: e.clientX,
                startY: e.clientY,
                lastX: e.clientX,
                lastY: e.clientY,
                startTime: performance.now(),
            };
        } else if (lightboxPointers.size === 2) {
            const points = Array.from(lightboxPointers.values());
            lightboxPinchState = {
                distance: getPointerDistance(points),
                zoom: lightboxZoom,
                center: getPointerCenter(points),
            };
            lightboxDragState = null;
            lightboxSwipeState = null;
            lightboxImageEl.classList.remove('is-dragging');
        }
    }

    function handleLightboxPointerMove(e) {
        if (!lightboxPointers.has(e.pointerId)) return;
        lightboxPointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

        if (lightboxPointers.size >= 2 && lightboxPinchState) {
            e.preventDefault();
            const points = Array.from(lightboxPointers.values()).slice(0, 2);
            const distance = getPointerDistance(points);
            const center = getPointerCenter(points);
            if (lightboxPinchState.distance > 0) {
                setLightboxZoom((lightboxPinchState.zoom * distance) / lightboxPinchState.distance, {
                    clientX: center.x,
                    clientY: center.y,
                });
            }
            return;
        }

        if (lightboxDragState && lightboxDragState.pointerId === e.pointerId) {
            e.preventDefault();
            lightboxPanX = lightboxDragState.panX + e.clientX - lightboxDragState.startX;
            lightboxPanY = lightboxDragState.panY + e.clientY - lightboxDragState.startY;
            applyLightboxTransform();
            return;
        }

        if (
            lightboxSwipeState &&
            lightboxSwipeState.pointerId === e.pointerId &&
            lightboxZoom <= LIGHTBOX_MIN_ZOOM
        ) {
            lightboxSwipeState.lastX = e.clientX;
            lightboxSwipeState.lastY = e.clientY;
            const deltaX = e.clientX - lightboxSwipeState.startX;
            const deltaY = e.clientY - lightboxSwipeState.startY;
            if (Math.abs(deltaX) > 12 && Math.abs(deltaX) > Math.abs(deltaY)) {
                e.preventDefault();
            }
        }
    }

    function handleLightboxPointerEnd(e) {
        const swipeState =
            lightboxSwipeState && lightboxSwipeState.pointerId === e.pointerId
                ? { ...lightboxSwipeState, endTime: performance.now() }
                : null;

        lightboxPointers.delete(e.pointerId);
        if (lightboxImageEl && lightboxImageEl.hasPointerCapture(e.pointerId)) {
            lightboxImageEl.releasePointerCapture(e.pointerId);
        }

        if (lightboxPointers.size < 2) {
            lightboxPinchState = null;
        }
        if (lightboxDragState && lightboxDragState.pointerId === e.pointerId) {
            lightboxDragState = null;
            if (lightboxImageEl) {
                lightboxImageEl.classList.remove('is-dragging');
            }
        }

        if (
            swipeState &&
            e.type !== 'pointercancel' &&
            !lightboxPinchState &&
            lightboxZoom <= LIGHTBOX_MIN_ZOOM &&
            lightboxImages.length > 1
        ) {
            const deltaX = swipeState.lastX - swipeState.startX;
            const deltaY = swipeState.lastY - swipeState.startY;
            const elapsed = swipeState.endTime - swipeState.startTime;
            const isHorizontalSwipe =
                Math.abs(deltaX) >= LIGHTBOX_SWIPE_MIN_DISTANCE &&
                Math.abs(deltaY) <= Math.abs(deltaX) * LIGHTBOX_SWIPE_VERTICAL_TOLERANCE &&
                elapsed <= LIGHTBOX_SWIPE_MAX_DURATION_MS;

            if (isHorizontalSwipe) {
                showLightboxImage(lightboxIndex + (deltaX < 0 ? 1 : -1));
            }
        }

        if (swipeState || lightboxPointers.size === 0) {
            lightboxSwipeState = null;
        }
    }

    function setLightboxLoadState(state) {
        if (!lightboxEl || !lightboxStageEl) return;
        const isLoading = state === 'loading';
        const hasError = state === 'error';
        lightboxEl.classList.toggle('is-loading', isLoading);
        lightboxEl.classList.toggle('is-ready', state === 'ready');
        lightboxEl.classList.toggle('has-error', hasError);
        lightboxStageEl.setAttribute('aria-busy', isLoading ? 'true' : 'false');
        if (lightboxErrorEl) lightboxErrorEl.hidden = !hasError;
    }

    function loadCurrentLightboxImage(forceReload = false) {
        if (!lightboxImageEl || !lightboxImages.length) return;
        const expectedIndex = lightboxIndex;
        const src = lightboxImages[expectedIndex];
        setLightboxLoadState('loading');
        if (lightboxDimensionsEl) lightboxDimensionsEl.textContent = '正在读取原图';

        const assignSource = () => {
            if (
                !lightboxEl?.classList.contains('show') ||
                lightboxIndex !== expectedIndex ||
                lightboxImages[expectedIndex] !== src
            ) {
                return;
            }
            lightboxImageEl.src = src;
        };

        if (forceReload) {
            lightboxImageEl.removeAttribute('src');
            requestAnimationFrame(assignSource);
            return;
        }
        assignSource();
    }

    function ensureWeiboLightbox() {
        if (lightboxEl) return;

        lightboxEl = document.createElement('div');
        lightboxEl.className = 'weibo-lightbox';
        lightboxEl.setAttribute('aria-hidden', 'true');
        lightboxEl.setAttribute('aria-label', '微博原图预览');
        lightboxEl.setAttribute('aria-modal', 'true');
        lightboxEl.setAttribute('role', 'dialog');
        lightboxEl.tabIndex = -1;
        lightboxEl.innerHTML = `
<div class="weibo-lightbox-toolbar" role="toolbar" aria-label="图片浏览工具">
  <button type="button" class="weibo-lightbox-tool weibo-lightbox-zoom-out" aria-label="缩小图片" title="缩小图片">−</button>
  <span class="weibo-lightbox-zoom-level" aria-live="polite">100%</span>
  <button type="button" class="weibo-lightbox-tool weibo-lightbox-zoom-in" aria-label="放大图片" title="放大图片">+</button>
  <button type="button" class="weibo-lightbox-tool weibo-lightbox-zoom-reset" aria-label="适应窗口" title="适应窗口">适应</button>
  <a class="weibo-lightbox-tool weibo-lightbox-download" aria-label="下载当前图片" title="下载当前图片" href="#" download>↓</a>
  <button type="button" class="weibo-lightbox-tool weibo-lightbox-save-all" aria-label="保存全部图片" title="保存全部图片">⇩</button>
  <button type="button" class="weibo-lightbox-tool weibo-lightbox-close" aria-label="关闭大图" title="关闭">×</button>
</div>
<button type="button" class="weibo-lightbox-nav weibo-lightbox-prev" aria-label="上一张">‹</button>
<figure class="weibo-lightbox-figure">
  <div class="weibo-lightbox-stage" aria-busy="true">
    <div class="weibo-lightbox-loading" role="status" aria-live="polite">
      <span class="weibo-lightbox-spinner" aria-hidden="true"></span>
      <span>正在加载原图</span>
    </div>
    <img class="weibo-lightbox-image" alt="微博原图" decoding="async" draggable="false">
    <div class="weibo-lightbox-error" role="alert" hidden>
      <span>原图加载失败</span>
      <button type="button" class="weibo-lightbox-retry">重新加载</button>
    </div>
  </div>
  <figcaption class="weibo-lightbox-caption">
    <span class="weibo-lightbox-counter" aria-live="polite"></span>
    <span class="weibo-lightbox-dimensions"></span>
    <span class="weibo-lightbox-hint">双击或滚轮缩放 · 拖动查看细节</span>
  </figcaption>
</figure>
<div class="weibo-lightbox-thumbs" role="listbox" aria-label="微博图片缩略图"></div>
<button type="button" class="weibo-lightbox-nav weibo-lightbox-next" aria-label="下一张">›</button>`;
        document.body.appendChild(lightboxEl);

        lightboxStageEl = lightboxEl.querySelector('.weibo-lightbox-stage');
        lightboxImageEl = lightboxEl.querySelector('.weibo-lightbox-image');
        lightboxCounterEl = lightboxEl.querySelector('.weibo-lightbox-counter');
        lightboxDimensionsEl = lightboxEl.querySelector('.weibo-lightbox-dimensions');
        lightboxErrorEl = lightboxEl.querySelector('.weibo-lightbox-error');
        lightboxPrevBtn = lightboxEl.querySelector('.weibo-lightbox-prev');
        lightboxNextBtn = lightboxEl.querySelector('.weibo-lightbox-next');
        lightboxThumbsEl = lightboxEl.querySelector('.weibo-lightbox-thumbs');
        lightboxDownloadLink = lightboxEl.querySelector('.weibo-lightbox-download');
        lightboxSaveAllBtn = lightboxEl.querySelector('.weibo-lightbox-save-all');
        lightboxZoomInBtn = lightboxEl.querySelector('.weibo-lightbox-zoom-in');
        lightboxZoomOutBtn = lightboxEl.querySelector('.weibo-lightbox-zoom-out');
        lightboxZoomResetBtn = lightboxEl.querySelector('.weibo-lightbox-zoom-reset');
        lightboxZoomLevelEl = lightboxEl.querySelector('.weibo-lightbox-zoom-level');
        lightboxCloseBtn = lightboxEl.querySelector('.weibo-lightbox-close');
        lightboxRetryBtn = lightboxEl.querySelector('.weibo-lightbox-retry');

        lightboxCloseBtn.addEventListener('click', closeLightbox);
        lightboxRetryBtn.addEventListener('click', () => loadCurrentLightboxImage(true));
        lightboxSaveAllBtn.addEventListener('click', (e) => {
            e.preventDefault();
            saveAllLightboxImages();
        });
        lightboxZoomInBtn.addEventListener('click', () => zoomLightboxBy(LIGHTBOX_ZOOM_STEP));
        lightboxZoomOutBtn.addEventListener('click', () => zoomLightboxBy(-LIGHTBOX_ZOOM_STEP));
        lightboxZoomResetBtn.addEventListener('click', resetLightboxZoom);
        lightboxPrevBtn.addEventListener('click', () => showLightboxImage(lightboxIndex - 1));
        lightboxNextBtn.addEventListener('click', () => showLightboxImage(lightboxIndex + 1));
        lightboxImageEl.addEventListener('wheel', (e) => {
            e.preventDefault();
            zoomLightboxBy(e.deltaY < 0 ? LIGHTBOX_ZOOM_STEP : -LIGHTBOX_ZOOM_STEP, {
                clientX: e.clientX,
                clientY: e.clientY,
            });
        });
        lightboxImageEl.addEventListener('dblclick', (e) => {
            e.preventDefault();
            if (lightboxZoom > LIGHTBOX_MIN_ZOOM) {
                resetLightboxZoom();
                return;
            }
            setLightboxZoom(2, { clientX: e.clientX, clientY: e.clientY });
        });
        lightboxImageEl.addEventListener('pointerdown', handleLightboxPointerDown);
        lightboxImageEl.addEventListener('pointermove', handleLightboxPointerMove);
        lightboxImageEl.addEventListener('pointerup', handleLightboxPointerEnd);
        lightboxImageEl.addEventListener('pointercancel', handleLightboxPointerEnd);
        lightboxImageEl.addEventListener('load', () => {
            setLightboxLoadState('ready');
            if (lightboxDimensionsEl) {
                lightboxDimensionsEl.textContent = `${lightboxImageEl.naturalWidth} × ${lightboxImageEl.naturalHeight} px`;
            }
        });
        lightboxImageEl.addEventListener('error', () => {
            if (!lightboxImageEl.getAttribute('src')) return;
            setLightboxLoadState('error');
            if (lightboxDimensionsEl) lightboxDimensionsEl.textContent = '原图暂时无法显示';
        });
        lightboxEl.addEventListener('click', (e) => {
            const target = getEventElement(e);
            if (!target) return;
            if (
                target.closest(
                    '.weibo-lightbox-image, .weibo-lightbox-tool, .weibo-lightbox-nav, .weibo-lightbox-thumbs, .weibo-lightbox-error',
                )
            ) {
                return;
            }
            closeLightbox();
        });
    }

    function renderLightboxThumbs() {
        if (!lightboxThumbsEl) return;
        lightboxThumbsEl.innerHTML = '';
        if (lightboxImages.length < 2) {
            lightboxThumbsEl.hidden = true;
            return;
        }

        lightboxThumbsEl.hidden = false;
        lightboxImages.forEach((src, index) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'weibo-lightbox-thumb';
            button.dataset.index = String(index);
            button.setAttribute('role', 'option');
            button.setAttribute('aria-label', `查看第 ${index + 1} 张图片`);
            button.addEventListener('click', () => showLightboxImage(index));

            const img = document.createElement('img');
            img.src = lightboxThumbs[index] || src;
            img.alt = '';
            img.decoding = 'async';
            img.loading = 'lazy';
            img.draggable = false;
            button.appendChild(img);
            lightboxThumbsEl.appendChild(button);
        });
    }

    function syncLightboxThumbs() {
        if (!lightboxThumbsEl || lightboxThumbsEl.hidden) return;
        const buttons = lightboxThumbsEl.querySelectorAll('.weibo-lightbox-thumb');
        buttons.forEach((button) => {
            const isActive = Number.parseInt(button.dataset.index || '0', 10) === lightboxIndex;
            button.classList.toggle('active', isActive);
            button.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });
        const activeThumb = lightboxThumbsEl.querySelector('.weibo-lightbox-thumb.active');
        if (activeThumb) {
            activeThumb.scrollIntoView({ block: 'nearest', inline: 'center' });
        }
    }

    function prefetchLightboxNeighbor(index) {
        if (lightboxImages.length < 2) return;
        const nextIndex = (index + 1 + lightboxImages.length) % lightboxImages.length;
        const prevIndex = (index - 1 + lightboxImages.length) % lightboxImages.length;
        [nextIndex, prevIndex].forEach((i) => {
            const img = new Image();
            img.decoding = 'async';
            img.src = lightboxImages[i];
        });
    }

    function showLightboxImage(index) {
        if (!lightboxImages.length) return;
        lightboxIndex = (index + lightboxImages.length) % lightboxImages.length;
        resetLightboxZoom();
        lightboxImageEl.alt = `微博原图，第 ${lightboxIndex + 1} 张，共 ${lightboxImages.length} 张`;
        lightboxCounterEl.textContent = `${lightboxIndex + 1} / ${lightboxImages.length}`;
        const hasMultiple = lightboxImages.length > 1;
        lightboxPrevBtn.hidden = !hasMultiple;
        lightboxNextBtn.hidden = !hasMultiple;
        updateLightboxDownloadLink();
        syncLightboxThumbs();
        prefetchLightboxNeighbor(lightboxIndex);
        loadCurrentLightboxImage();
    }

    function openWeiboLightbox(images, index, thumbs = [], trigger = null) {
        if (!images.length) return;
        ensureWeiboLightbox();
        lightboxLastFocusedEl = trigger || document.activeElement;
        lightboxImages = images;
        lightboxThumbs = images.map((src, imageIndex) => {
            const thumb = thumbs[imageIndex];
            return typeof thumb === 'string' && thumb.trim() ? thumb.trim() : src;
        });
        renderLightboxThumbs();
        lightboxEl.classList.toggle('has-thumbs', images.length > 1);
        lightboxEl.classList.add('show');
        lightboxEl.setAttribute('aria-hidden', 'false');
        document.body.classList.add('weibo-lightbox-open');
        showLightboxImage(index);
        requestAnimationFrame(() => lightboxCloseBtn?.focus());
    }

    function closeLightbox() {
        if (!lightboxEl || !lightboxEl.classList.contains('show')) return;
        lightboxEl.classList.remove('show', 'is-loading', 'is-ready', 'has-error', 'has-thumbs');
        lightboxEl.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('weibo-lightbox-open');
        if (lightboxImageEl) {
            lightboxImageEl.removeAttribute('src');
        }
        resetLightboxZoom();
        const restoreTarget = lightboxLastFocusedEl;
        lightboxLastFocusedEl = null;
        if (restoreTarget instanceof HTMLElement && restoreTarget.isConnected) {
            restoreTarget.focus();
        }
    }

    dataTableContainer.addEventListener('click', function (e) {
        const target = getEventElement(e);
        if (!target) return;

        const mediaButton = target.closest('.weibo-media-item');
        if (mediaButton) {
            e.preventDefault();
            e.stopPropagation();
            const grid = mediaButton.closest('.weibo-media-grid');
            const payload = grid ? getWeiboMediaPayload(grid) : { images: [], thumbs: [] };
            const index = Number.parseInt(mediaButton.dataset.imageIndex || '0', 10) || 0;
            openWeiboLightbox(payload.images, index, payload.thumbs, mediaButton);
            return;
        }

        if (target.closest('.data-card-drag-handle')) return;
        if (target.closest('a[href]')) return;
        const retweetBlock = target.closest('.weibo-retweet-block');
        if (retweetBlock && retweetBlock.dataset.href) {
            e.preventDefault();
            e.stopPropagation();
            window.open(retweetBlock.dataset.href, '_blank', 'noopener,noreferrer');
            return;
        }
        const card = target.closest('.data-card-link');
        if (!card || !dataTableContainer.contains(card)) return;
        const href = card.getAttribute('data-href');
        if (href) {
            window.open(href, '_blank', 'noopener,noreferrer');
        }
    });

    dataTableContainer.addEventListener('mousedown', function (e) {
        const target = getEventElement(e);
        if (target && target.closest('.data-card-drag-handle')) {
            e.stopPropagation();
        }
    });

    dataTableContainer.addEventListener(
        'error',
        function (e) {
            const img = e.target;
            if (!(img instanceof HTMLImageElement)) {
                return;
            }
            if (img.classList.contains('weibo-inline-emoji')) {
                const fallback = document.createElement('span');
                fallback.className = 'weibo-inline-emoji-fallback';
                fallback.textContent = img.alt || '';
                img.replaceWith(fallback);
                return;
            }
            if (img.classList.contains('weibo-video-cover-img')) {
                const fallbackSrc = img.dataset.fallbackSrc || '';
                if (fallbackSrc && img.src !== new URL(fallbackSrc, window.location.href).href) {
                    img.src = fallbackSrc;
                    img.dataset.fallbackSrc = '';
                    return;
                }
                const cover = img.closest('.weibo-video-cover');
                if (cover) cover.style.display = 'none';
                return;
            }
            if (!img.classList.contains('weibo-media-img')) return;
            const fullSrc = img.dataset.fullSrc || '';
            if (fullSrc && img.src !== new URL(fullSrc, window.location.href).href) {
                img.src = fullSrc;
                img.dataset.fullSrc = '';
                return;
            }
            const item = img.closest('.weibo-media-item');
            if (item) item.style.display = 'none';
        },
        true,
    );

    document.addEventListener('keydown', function (e) {
        if (!lightboxEl || !lightboxEl.classList.contains('show')) return;
        if (e.key === 'Tab') {
            const focusable = Array.from(
                lightboxEl.querySelectorAll('button:not([disabled]), a[href]'),
            ).filter((element) => !element.hidden && element.offsetParent !== null);
            if (focusable.length > 0) {
                const first = focusable[0];
                const last = focusable[focusable.length - 1];
                if (
                    e.shiftKey &&
                    (document.activeElement === first ||
                        !lightboxEl.contains(document.activeElement))
                ) {
                    e.preventDefault();
                    last.focus();
                } else if (!e.shiftKey && document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            }
            return;
        }
        if (['Escape', 'ArrowLeft', 'ArrowRight', '+', '=', '-', '_', '0'].includes(e.key)) {
            e.preventDefault();
        }
        if (e.key === 'Escape') closeLightbox();
        if (e.key === 'ArrowLeft') showLightboxImage(lightboxIndex - 1);
        if (e.key === 'ArrowRight') showLightboxImage(lightboxIndex + 1);
        if (e.key === '+' || e.key === '=') zoomLightboxBy(LIGHTBOX_ZOOM_STEP);
        if (e.key === '-' || e.key === '_') zoomLightboxBy(-LIGHTBOX_ZOOM_STEP);
        if (e.key === '0') resetLightboxZoom();
    });

    // 渲染不同平台的卡片
    function renderCards(rows) {
        if (!rows || rows.length === 0) {
            dataTableContainer.innerHTML = '<div class="empty-state">暂无数据</div>';
            pagination.innerHTML = '';
            return;
        }

        let html = '';

        if (currentTable === 'weibo') {
            html += '<div class="data-card-grid weibo-feed-grid data-card-sortable">';
            rows.forEach((row, idx) => {
                const cardId = escapeAttr(getCardId(row, idx));
                const safeName = sanitizeUsername(row.用户名);
                const encodedDir = encodeURIComponent(safeName);
                const avatarUrl = `/weibo_img/${encodedDir}/profile_image.jpg`;
                const url =
                    row.url ||
                    (row.mid
                        ? `https://m.weibo.cn/detail/${row.mid}`
                        : `https://www.weibo.com/u/${row.UID}`);

                const textRaw = (row.文本 || '').toString();
                // 解析发布时间：微博文本格式为 "...\n\n{created_at}"
                const parts = textRaw.split(/\n\s*\n/);
                const createdAt = parts.length > 1 ? parts.pop().trim() : '';
                const contentRaw = parts
                    .join('\n\n')
                    .replace(/^\s+/, '')
                    .replace(/\n?\s*\[图片\]\s*\*\s*\d+\s*\(详情请点击噢!\)/g, '')
                    .trim();
                const mediaHtml = renderWeiboMedia(row.images, row.image_thumbs);
                const retweetHtml = renderWeiboRetweet(row.retweeted_status);
                const videoHtml = renderWeiboVideoCover(
                    row.video_cover,
                    row.video_cover_thumb,
                    url,
                );
                const tagHtml = renderWeiboTags(row.tags);
                const typeHtml = renderWeiboContentType(row.content_type);
                const contentDisplay =
                    contentRaw || (mediaHtml || retweetHtml || videoHtml ? '' : '暂无最新微博内容');
                const textHtml = renderWeiboContentSegments(
                    row.content_segments,
                    contentDisplay,
                    'weibo-feed-text',
                    row.tags,
                );

                html += `
<article class="data-card weibo-feed-card data-card-link" data-id="${cardId}" data-href="${escapeAttr(url)}">
  <span class="data-card-drag-handle" title="拖拽调整顺序">⋮⋮</span>
  <div class="weibo-feed-inner">
    <div class="weibo-feed-header">
      <img data-src="${escapeAttr(
          avatarUrl,
      )}" alt="头像" class="weibo-feed-avatar" decoding="async" onerror="this.classList.add('avatar-fallback')">
      <div class="weibo-feed-user">
        <div class="weibo-feed-name-row">
          <span class="weibo-feed-name">${escapeHtml(row.用户名)}</span>
          ${typeHtml}
          ${row.认证信息 ? `<span class="weibo-feed-verify">${escapeHtml(row.认证信息)}</span>` : ''}
        </div>
        <div class="weibo-feed-meta">
          ${createdAt ? `<span class="weibo-feed-time">${escapeHtml(createdAt)}</span>` : ''}
          <span class="weibo-feed-source">粉丝 ${escapeHtml(row.粉丝数 ?? '')} · 微博 ${escapeHtml(row.微博数 ?? '')}</span>
        </div>
      </div>
    </div>
    <div class="weibo-feed-body">
      ${textHtml}
      ${tagHtml}
      ${retweetHtml}
      ${mediaHtml}
      ${videoHtml}
    </div>
    <footer class="weibo-feed-footer">
      <span class="weibo-feed-action"><span class="weibo-feed-action-icon">↗</span> 转发</span>
      <span class="weibo-feed-action"><span class="weibo-feed-action-icon">💬</span> 评论</span>
      <span class="weibo-feed-action"><span class="weibo-feed-action-icon">❤</span> 点赞</span>
      <span class="weibo-feed-link-hint">点击卡片打开微博详情 →</span>
    </footer>
  </div>
</article>`;
            });
            html += '</div>';
        } else if (currentTable === 'douyin' || currentTable === 'bilibili_live') {
            // 抖音直播 / B站直播：与 B站动态 统一的 feed 卡片样式
            html += '<div class="data-card-grid feed-card-grid data-card-sortable">';
            rows.forEach((row, idx) => {
                const cardId = escapeAttr(getCardId(row, idx));
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
<article class="data-card feed-card data-card-link" data-id="${cardId}" data-href="${escapeAttr(url)}">
  <span class="data-card-drag-handle" title="拖拽调整顺序">⋮⋮</span>
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
            // 虎牙使用异步加载：先渲染占位，再通过 loadHuyaImages 填充
            html += '<div class="data-card-grid live-card-grid data-card-sortable">';
            rows.forEach((row, idx) => {
                const cardId = escapeAttr(getCardId(row, idx));
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
                const dataRoomAttr = hasHuyaMedia && roomValue ? ` data-room="${escapeAttr(roomValue)}"` : '';

                html += `
<article class="data-card live-card data-card-link ${
    isLive ? 'live-card-on' : 'live-card-off'
}" data-id="${cardId}" data-href="${escapeAttr(url)}"${dataRoomAttr}>
  <span class="data-card-drag-handle" title="拖拽调整顺序">⋮⋮</span>
  <div class="live-card-media">
    <div class="live-card-cover${
        coverUrl ? ' live-card-cover-has-img' : ''
    }"${coverUrl ? ` style="background-image: url('${escapeAttr(coverUrl)}');"` : ''}></div>
    ${
        hasHuyaMedia
            ? `<div class="live-card-avatar-wrap">
      <img src="${avatarUrl ? escapeAttr(avatarUrl) : ''}" alt="头像" class="live-card-avatar" loading="lazy"${!avatarUrl ? ' style="display:none"' : ''}>
    </div>`
            : avatarUrl
            ? `<div class="live-card-avatar-wrap">
      <img src="${escapeAttr(avatarUrl)}" alt="头像" class="live-card-avatar" loading="lazy">
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
            html += '<div class="data-card-grid feed-card-grid data-card-sortable">';
            rows.forEach((row, idx) => {
                const cardId = escapeAttr(getCardId(row, idx));
                const url =
                    row.url ||
                    (row.dynamic_id
                        ? `https://www.bilibili.com/opus/${row.dynamic_id}`
                        : row.uid
                        ? `https://space.bilibili.com/${row.uid}`
                        : '');
                const text = (row.dynamic_text || '').toString().trim();
                const brief = text || '暂无动态内容';

                html += `
<article class="data-card feed-card data-card-link" data-id="${cardId}" data-href="${escapeAttr(url)}">
  <span class="data-card-drag-handle" title="拖拽调整顺序">⋮⋮</span>
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
            html += '<div class="data-card-grid feed-card-grid data-card-sortable">';
            rows.forEach((row, idx) => {
                const cardId = escapeAttr(getCardId(row, idx));
                const url =
                    row.url ||
                    (row.profile_id
                        ? `https://www.xiaohongshu.com/user/profile/${row.profile_id}`
                        : '');

                html += `
<article class="data-card feed-card data-card-link" data-id="${cardId}" data-href="${escapeAttr(url)}">
  <span class="data-card-drag-handle" title="拖拽调整顺序">⋮⋮</span>
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
            html += '<div class="data-card-grid feed-card-grid data-card-sortable">';
            rows.forEach((row, idx) => {
                const cardId = escapeAttr(getCardId(row, idx));
                html += `
<article class="data-card feed-card" data-id="${cardId}">
  <span class="data-card-drag-handle" title="拖拽调整顺序">⋮⋮</span>
  <pre class="feed-card-raw">${escapeHtml(JSON.stringify(row, null, 2))}</pre>
</article>`;
            });
            html += '</div>';
        }

        dataTableContainer.innerHTML = html;
        initLazyImages();
        initSortable();
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
