// 通用JavaScript函数

const UI_ICON_SPRITE = '/static/icons.svg';

function uiIcon(name, className = 'ui-icon') {
    return `<svg class="${className}" aria-hidden="true" focusable="false"><use href="${UI_ICON_SPRITE}#icon-${name}"></use></svg>`;
}

function setButtonLoading(button, loading, loadingText = '处理中...') {
    if (!button) return;

    if (loading) {
        if (!button.dataset.originalHtml) {
            button.dataset.originalHtml = button.innerHTML;
        }
        button.disabled = true;
        button.classList.add('is-loading');
        button.setAttribute('aria-busy', 'true');
        button.innerHTML = `${uiIcon('refresh')}<span>${loadingText}</span>`;
        return;
    }

    if (button.dataset.originalHtml) {
        button.innerHTML = button.dataset.originalHtml;
        delete button.dataset.originalHtml;
    }
    button.disabled = false;
    button.classList.remove('is-loading');
    button.removeAttribute('aria-busy');
}

const modalOpeners = new WeakMap();

function openAccessibleModal(modal, opener = document.activeElement) {
    if (!modal) return;
    modalOpeners.set(modal, opener);
    modal.classList.add('show');
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
    document.body.style.overflow = 'hidden';
    requestAnimationFrame(() => {
        const focusTarget = modal.querySelector('[autofocus], input:not([disabled]), button:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])');
        if (focusTarget) focusTarget.focus();
    });
}

function closeAccessibleModal(modal) {
    if (!modal) return;
    modal.classList.remove('show');
    modal.setAttribute('aria-hidden', 'true');
    if (!document.querySelector('.modal.show')) {
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
    }
    const opener = modalOpeners.get(modal);
    if (opener && document.contains(opener)) opener.focus();
    modalOpeners.delete(modal);
}

window.uiIcon = uiIcon;
window.setButtonLoading = setButtonLoading;
window.openAccessibleModal = openAccessibleModal;
window.closeAccessibleModal = closeAccessibleModal;

// 根据当前路径高亮侧边栏导航
function initActiveNav() {
    const path = window.location.pathname;
    const navItems = document.querySelectorAll('.sidebar-nav .nav-item, .mobile-bottom-nav-item');
    if (!navItems.length) return;

    navItems.forEach(item => {
        item.classList.remove('active');
        item.removeAttribute('aria-current');
        const href = item.getAttribute('href');
        if (!href) return;
        if (path === href || (path === '/' && href === '/config')) {
            item.classList.add('active');
            item.setAttribute('aria-current', 'page');
        }
    });
}

// 初始化主题 (需要在 DOM 加载前就执行以避免闪烁，但保留这里作为备份和切换逻辑)
function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const currentTheme = savedTheme || (prefersDark ? 'dark' : 'light');
    
    document.documentElement.setAttribute('data-theme', currentTheme);
    updateThemeIcon(currentTheme);

    const themeToggleBtn = document.getElementById('themeToggleBtn');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', toggleTheme);
    }
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const themeIcon = document.getElementById('themeIcon');
    if (themeIcon) {
        themeIcon.innerHTML = uiIcon(theme === 'dark' ? 'moon' : 'sun');
    }
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    if (themeToggleBtn) {
        const isDark = theme === 'dark';
        themeToggleBtn.setAttribute('aria-pressed', String(isDark));
        themeToggleBtn.setAttribute('aria-label', isDark ? '切换到浅色主题' : '切换到深色主题');
    }
}

function initTablistKeyboardNavigation() {
    document.querySelectorAll('[role="tablist"]').forEach((tablist) => {
        const getTabs = () => Array.from(tablist.querySelectorAll('[role="tab"]'))
            .filter((tab) => !tab.disabled && tab.getAttribute('aria-disabled') !== 'true');
        const syncTabStops = () => {
            const tabs = getTabs();
            const selected = tabs.find((tab) => tab.getAttribute('aria-selected') === 'true');
            tabs.forEach((tab) => {
                tab.tabIndex = tab === selected || (!selected && tab === tabs[0]) ? 0 : -1;
            });
        };

        syncTabStops();
        tablist.addEventListener('click', (event) => {
            if (event.target.closest('[role="tab"]')) {
                requestAnimationFrame(syncTabStops);
            }
        });
        tablist.addEventListener('keydown', (event) => {
            const current = event.target.closest('[role="tab"]');
            if (!current) return;
            const tabs = getTabs();
            const currentIndex = tabs.indexOf(current);
            if (currentIndex < 0) return;

            let nextIndex;
            if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
                nextIndex = (currentIndex + 1) % tabs.length;
            } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
                nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
            } else if (event.key === 'Home') {
                nextIndex = 0;
            } else if (event.key === 'End') {
                nextIndex = tabs.length - 1;
            } else {
                return;
            }

            event.preventDefault();
            tabs[nextIndex].focus();
            tabs[nextIndex].click();
        });
    });
}

// 检查认证状态
async function checkAuth() {
    try {
        const response = await fetch('/api/check-auth');
        const data = await response.json();
        if (!data.authenticated) {
            window.location.href = '/login';
            return false;
        }
        return true;
    } catch (error) {
        console.error('认证检查失败:', error);
        window.location.href = '/login';
        return false;
    }
}

// 登出
async function logout() {
    try {
        const response = await fetch('/api/logout', {
            method: 'POST',
        });
        const data = await response.json();
        if (data.success) {
            window.location.href = '/login';
        }
    } catch (error) {
        console.error('登出失败:', error);
        window.location.href = '/login';
    }
}

// 创建 Toast 容器
function ensureToastContainer() {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        container.setAttribute('aria-live', 'polite');
        container.setAttribute('aria-atomic', 'false');
        document.body.appendChild(container);
    }
    return container;
}

// 显示 Toast 消息
function showToast(message, type = 'success', duration = 3000) {
    const container = ensureToastContainer();
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
    
    // 图标
    const icons = {
        success: 'check',
        error: 'error',
        warning: 'warning',
        info: 'info'
    };

    const icon = document.createElement('span');
    icon.className = 'toast-icon';
    icon.innerHTML = uiIcon(icons[type] || icons.info);
    const text = document.createElement('span');
    text.className = 'toast-message';
    text.textContent = message;
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'toast-close';
    close.setAttribute('aria-label', '关闭通知');
    close.innerHTML = uiIcon('close');
    close.addEventListener('click', () => toast.remove());
    toast.append(icon, text, close);
    
    container.appendChild(toast);
    
    // 触发动画
    requestAnimationFrame(() => {
        toast.classList.add('toast-show');
    });
    
    // 自动移除
    setTimeout(() => {
        toast.classList.remove('toast-show');
        toast.classList.add('toast-hide');
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, 300);
    }, duration);
}

// 显示消息（使用 Toast）
function showMessage(elementId, message, type = 'success') {
    showToast(message, type);
}

// 格式化日期时间
function formatDateTime(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN');
}

function setUpdateBannerVisible(visible) {
    const updateBanner = document.getElementById('updateBanner');
    if (!updateBanner) return;

    updateBanner.style.display = visible ? 'flex' : 'none';
    document.body.classList.toggle('has-update-banner', visible);

    if (visible) {
        requestAnimationFrame(() => {
            const height = Math.ceil(updateBanner.getBoundingClientRect().height);
            document.documentElement.style.setProperty('--update-banner-height', `${height}px`);
        });
        return;
    }

    document.documentElement.style.removeProperty('--update-banner-height');
}

function initMobileMenu() {
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const sidebarCollapseHandle = document.getElementById('sidebarCollapseHandle');

    if (!sidebar || !sidebarOverlay) {
        return;
    }

    const SIDEBAR_STATE_KEY = 'sidebarCollapsed';

    function isMobileViewport() {
        return window.innerWidth <= 768;
    }

    function isSidebarCollapsed() {
        return document.body.classList.contains('sidebar-collapsed');
    }

    function syncCollapseHandle(collapsed) {
        if (!sidebarCollapseHandle) {
            return;
        }
        sidebarCollapseHandle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        sidebarCollapseHandle.setAttribute('aria-label', collapsed ? '展开侧边栏' : '收起侧边栏');
        sidebarCollapseHandle.setAttribute('title', collapsed ? '展开侧边栏' : '收起侧边栏');
        sidebarCollapseHandle.classList.toggle('is-collapsed', collapsed);
        sidebarCollapseHandle.hidden = isMobileViewport();
    }

    function syncMobileMenuBtn(open) {
        if (!mobileMenuBtn) {
            return;
        }
        mobileMenuBtn.classList.toggle('active', open);
        mobileMenuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
        mobileMenuBtn.setAttribute('aria-label', open ? '关闭账户与设置' : '打开账户与设置');
    }

    function applyDesktopCollapsedState(collapsed) {
        document.body.classList.toggle('sidebar-collapsed', collapsed);
        localStorage.setItem(SIDEBAR_STATE_KEY, collapsed ? '1' : '0');
        sidebar.toggleAttribute('inert', collapsed);
        syncCollapseHandle(collapsed);
    }

    function initDesktopSidebarState() {
        if (isMobileViewport()) {
            document.body.classList.remove('sidebar-collapsed');
            sidebar.setAttribute('aria-hidden', 'true');
            sidebar.setAttribute('inert', '');
            syncMobileMenuBtn(false);
            syncCollapseHandle(false);
            return;
        }

        const saved = localStorage.getItem(SIDEBAR_STATE_KEY);
        const collapsed = saved === '1';
        applyDesktopCollapsedState(collapsed);
        sidebar.classList.remove('show');
        sidebarOverlay.classList.remove('show');
        document.body.classList.remove('mobile-sidebar-open');
        sidebar.setAttribute('aria-hidden', collapsed ? 'true' : 'false');
        syncMobileMenuBtn(false);
    }

    function setMobileMenuState(open) {
        sidebar.classList.toggle('show', open);
        sidebarOverlay.classList.toggle('show', open);
        document.body.classList.toggle('mobile-sidebar-open', open);
        syncMobileMenuBtn(open);
        sidebar.setAttribute('aria-hidden', open ? 'false' : 'true');
        sidebar.toggleAttribute('inert', !open);
        if (open) {
            requestAnimationFrame(() => {
                const firstControl = sidebar.querySelector('.sidebar-footer button');
                if (firstControl) firstControl.focus();
            });
        }
    }

    function closeMobileMenu() {
        setMobileMenuState(false);
    }

    function toggleDesktopSidebar() {
        if (isMobileViewport()) {
            return;
        }
        applyDesktopCollapsedState(!isSidebarCollapsed());
        sidebar.setAttribute('aria-hidden', isSidebarCollapsed() ? 'true' : 'false');
    }

    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', () => {
            if (!isMobileViewport()) {
                return;
            }
            setMobileMenuState(!sidebar.classList.contains('show'));
        });
    }

    if (sidebarCollapseHandle) {
        sidebarCollapseHandle.addEventListener('click', toggleDesktopSidebar);
    }

    sidebarOverlay.addEventListener('click', closeMobileMenu);

    document.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape') {
            return;
        }
        if (document.querySelector('.modal.show')) {
            return;
        }
        if (isMobileViewport() && sidebar.classList.contains('show')) {
            closeMobileMenu();
            mobileMenuBtn?.focus();
        }
    });

    sidebar.querySelectorAll('.nav-item').forEach((item) => {
        item.addEventListener('click', () => {
            if (isMobileViewport()) {
                closeMobileMenu();
            }
        });
    });

    sidebar.querySelectorAll('.sidebar-footer button').forEach((button) => {
        button.addEventListener('click', () => {
            if (isMobileViewport()) closeMobileMenu();
        });
    });

    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            if (isMobileViewport()) {
                document.body.classList.remove('sidebar-collapsed');
                closeMobileMenu();
                sidebar.setAttribute('aria-hidden', sidebar.classList.contains('show') ? 'false' : 'true');
                syncCollapseHandle(false);
            } else {
                closeMobileMenu();
                initDesktopSidebarState();
            }
        }, 250);
    });

    initDesktopSidebarState();
}

// 修改密码功能
function initChangePassword() {
    const changePasswordBtn = document.getElementById('changePasswordBtn');
    const changePasswordModal = document.getElementById('changePasswordModal');
    const closePasswordModal = document.getElementById('closePasswordModal');
    const cancelPasswordChange = document.getElementById('cancelPasswordChange');
    const changePasswordForm = document.getElementById('changePasswordForm');
    const passwordMessage = document.getElementById('passwordMessage');
    const modalOverlay = changePasswordModal ? changePasswordModal.querySelector('.modal-overlay') : null;

    if (!changePasswordBtn || !changePasswordModal) {
        return; // 登录页面没有这些元素
    }

    // 显示模态框
    function showModal() {
        const opener = window.innerWidth <= 768
            ? document.getElementById('mobileMenuBtn')
            : changePasswordBtn;
        openAccessibleModal(changePasswordModal, opener);
    }

    // 隐藏模态框
    function hideModal() {
        closeAccessibleModal(changePasswordModal);
        // 清空表单和消息
        if (changePasswordForm) {
            changePasswordForm.reset();
        }
        if (passwordMessage) {
            passwordMessage.textContent = '';
            passwordMessage.className = 'password-message';
        }
    }

    // 显示消息
    function showPasswordMessage(message, type) {
        if (passwordMessage) {
            passwordMessage.textContent = message;
            passwordMessage.className = `password-message ${type}`;
        }
    }

    // 绑定事件
    changePasswordBtn.addEventListener('click', showModal);
    
    if (closePasswordModal) {
        closePasswordModal.addEventListener('click', hideModal);
    }
    
    if (cancelPasswordChange) {
        cancelPasswordChange.addEventListener('click', hideModal);
    }
    
    if (modalOverlay) {
        modalOverlay.addEventListener('click', hideModal);
    }

    // 表单提交
    if (changePasswordForm) {
        changePasswordForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            const oldPassword = document.getElementById('oldPassword').value;
            const newPassword = document.getElementById('newPassword').value;
            const confirmPassword = document.getElementById('confirmPassword').value;

            // 客户端验证
            if (newPassword.length < 3) {
                showPasswordMessage('新密码长度至少为3个字符', 'error');
                return;
            }

            if (newPassword !== confirmPassword) {
                showPasswordMessage('两次输入的新密码不一致', 'error');
                return;
            }

            try {
                const formData = new FormData();
                formData.append('old_password', oldPassword);
                formData.append('new_password', newPassword);
                formData.append('confirm_password', confirmPassword);

                const response = await fetch('/api/change-password', {
                    method: 'POST',
                    body: formData,
                });

                const data = await response.json();

                if (data.success) {
                    showPasswordMessage('密码修改成功，请重新登录', 'success');
                    // 2秒后自动登出
                    setTimeout(() => {
                        logout();
                    }, 2000);
                } else {
                    showPasswordMessage(data.message || '密码修改失败', 'error');
                }
            } catch (error) {
                console.error('修改密码失败:', error);
                showPasswordMessage('网络错误，请稍后重试', 'error');
            }
        });
    }

    // ESC 键关闭模态框
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && changePasswordModal.classList.contains('show')) {
            hideModal();
        }
    });
}

document.addEventListener('keydown', function(event) {
    if (event.key !== 'Tab') return;
    const openModals = Array.from(document.querySelectorAll('.modal.show'));
    const modal = openModals[openModals.length - 1];
    if (!modal) return;

    const focusable = Array.from(modal.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'))
        .filter(element => element.getClientRects().length > 0);
    if (!focusable.length) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
    }
});

// ================= 版本检查功能 =================

// 版本比较：返回 1 (a > b), -1 (a < b), 0 (a == b)
function compareVersions(a, b) {
    // 去掉 'v' 前缀
    a = a.replace(/^v/, '');
    b = b.replace(/^v/, '');
    
    const partsA = a.split('.').map(x => parseInt(x, 10) || 0);
    const partsB = b.split('.').map(x => parseInt(x, 10) || 0);
    
    const maxLen = Math.max(partsA.length, partsB.length);
    for (let i = 0; i < maxLen; i++) {
        const numA = partsA[i] || 0;
        const numB = partsB[i] || 0;
        if (numA > numB) return 1;
        if (numA < numB) return -1;
    }
    return 0;
}

// 检查版本更新
async function checkVersionUpdate() {
    try {
        // 获取当前版本信息
        const localResp = await fetch('/api/version');
        if (!localResp.ok) return;
        const localData = await localResp.json();
        const currentVersion = localData.version;
        const githubApiUrl = localData.github_api_url;
        const tagsUrl = localData.tags_url;
        
        if (!currentVersion || currentVersion === 'unknown') return;
        
        // 更新页面上的当前版本显示
        const currentVersionEl = document.getElementById('currentVersion');
        if (currentVersionEl) {
            currentVersionEl.textContent = `v${currentVersion}`;
            currentVersionEl.href = tagsUrl;
        }
        
        // 从 GitHub Tags API 获取最新版本
        const githubResp = await fetch(githubApiUrl);
        if (!githubResp.ok) {
            console.log('无法获取最新版本信息');
            return;
        }
        const tagsData = await githubResp.json();
        // Tags API 返回数组，第一个元素是最新的 tag
        const latestVersion = tagsData.length > 0 ? tagsData[0].name : null;
        
        if (!latestVersion) return;
        
        // 比较版本
        const cmp = compareVersions(latestVersion, currentVersion);
        
        const updateBanner = document.getElementById('updateBanner');
        if (cmp > 0 && updateBanner) {
            // 有新版本
            const latestVersionEl = document.getElementById('latestVersion');
            const releasesLinkEl = document.getElementById('releasesLink');
            
            if (latestVersionEl) {
                latestVersionEl.textContent = latestVersion;
            }
            if (releasesLinkEl) {
                releasesLinkEl.href = tagsUrl;
            }
            
            setUpdateBannerVisible(true);
        }
    } catch (error) {
        console.log('版本检查失败:', error.message);
    }
}

// 关闭更新提示
function dismissUpdateBanner() {
    setUpdateBannerVisible(false);
    // 记录到 sessionStorage，本次会话不再提示
    sessionStorage.setItem('updateBannerDismissed', 'true');
}

// 登录页可能由 / 或 /login 渲染，不能仅靠 pathname 判断
function isLoginPage() {
    return document.body.classList.contains('login-body');
}

const LIQUID_LENS_SELECTOR = [
    '.btn',
    '.tab-btn',
    '.config-module-tab',
    '.nav-item',
    '.mobile-bottom-nav-item',
    '.pagination button',
    '.pagination a',
    '.page-topbar-menu',
    '.password-toggle',
    '.modal-close',
    '.back-to-top',
    '.theme-toggle-fab',
    '.data-card-drag-handle',
    '.weibo-feed-card.data-card',
    '.weibo-feed-grid .data-card',
].join(', ');

function canUseLiquidLensPointer() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return false;
    }
    return window.matchMedia('(hover: hover) and (pointer: fine)').matches;
}

function setLiquidLensPoint(el, clientX, clientY) {
    if (!el || typeof clientX !== 'number' || typeof clientY !== 'number') return;
    const rect = el.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const x = ((clientX - rect.left) / rect.width) * 100;
    const y = ((clientY - rect.top) / rect.height) * 100;
    el.style.setProperty('--lg-x', `${Math.max(0, Math.min(100, x)).toFixed(2)}%`);
    el.style.setProperty('--lg-y', `${Math.max(0, Math.min(100, y)).toFixed(2)}%`);
}

function clearLiquidLensPoint(el) {
    if (!el) return;
    el.style.removeProperty('--lg-x');
    el.style.removeProperty('--lg-y');
    el.style.removeProperty('--lg-spot-opacity');
}

/**
 * In-bounds liquid-glass lens highlight for pressable controls and Weibo cards.
 * Magnify is CSS-only; spotlight tracks the pointer only inside each control.
 */
function initLiquidGlassLens() {
    if (!canUseLiquidLensPointer()) return;

    let frameId = 0;
    let pending = null;

    const flush = () => {
        frameId = 0;
        if (!pending) return;
        const { el, clientX, clientY } = pending;
        pending = null;
        setLiquidLensPoint(el, clientX, clientY);
        if (el.matches('.btn, .tab-btn, .config-module-tab, .nav-item, .mobile-bottom-nav-item, .pagination button, .pagination a, .page-topbar-menu, .password-toggle, .modal-close, .back-to-top, .theme-toggle-fab, .data-card-drag-handle')) {
            el.style.setProperty('--lg-spot-opacity', '1');
        }
    };

    const schedule = (el, clientX, clientY) => {
        pending = { el, clientX, clientY };
        if (!frameId) {
            frameId = requestAnimationFrame(flush);
        }
    };

    document.addEventListener('pointermove', (event) => {
        if (event.pointerType && event.pointerType !== 'mouse') return;
        const el = event.target.closest(LIQUID_LENS_SELECTOR);
        if (!el || el.disabled || el.getAttribute('aria-disabled') === 'true') return;
        schedule(el, event.clientX, event.clientY);
    }, { passive: true });

    document.addEventListener('pointerleave', (event) => {
        const el = event.target.closest?.(LIQUID_LENS_SELECTOR);
        if (el) clearLiquidLensPoint(el);
    }, true);

    document.addEventListener('pointerout', (event) => {
        const el = event.target.closest?.(LIQUID_LENS_SELECTOR);
        if (!el) return;
        const related = event.relatedTarget;
        if (related && el.contains(related)) return;
        clearLiquidLensPoint(el);
    }, true);
}

window.initLiquidGlassLens = initLiquidGlassLens;

const CUSTOM_CURSOR_HOVER_SELECTOR = [
    'a[href]',
    'button',
    'summary',
    '[role="button"]',
    '[role="tab"]',
    '[data-cursor-hover]',
    '.data-card',
    'input',
    'textarea',
    'select',
].join(', ');

const CUSTOM_CURSOR_TEXT_SELECTOR = [
    'textarea',
    '[contenteditable="true"]',
    'input:not([type])',
    'input[type="text"]',
    'input[type="search"]',
    'input[type="email"]',
    'input[type="password"]',
    'input[type="url"]',
    'input[type="tel"]',
    'input[type="number"]',
].join(', ');

const CURSOR_MAGNET_SELECTOR = [
    '.btn:not(.theme-toggle-fab)',
    '.tab-btn',
    '.config-module-tab',
    '.nav-item',
    '.mobile-bottom-nav-item',
    '.pagination button',
    '.pagination a',
].join(', ');

function canUseCustomCursor() {
    return canUseLiquidLensPointer()
        && !window.matchMedia('(forced-colors: active)').matches;
}

function isDisabledControl(el) {
    return Boolean(el && (el.matches(':disabled') || el.getAttribute('aria-disabled') === 'true'));
}

/**
 * Moonshot-inspired two-layer cursor with liquid-glass feedback.
 * The dot stays close to the pointer while the ring eases behind it. Cards and
 * primary controls react locally, so no layout or touch behavior is changed.
 */
function initCustomCursorExperience() {
    if (!canUseCustomCursor() || document.querySelector('.custom-cursor-ring')) return;

    const ring = document.createElement('span');
    const dot = document.createElement('span');
    ring.className = 'custom-cursor-ring';
    dot.className = 'custom-cursor-dot';
    ring.setAttribute('aria-hidden', 'true');
    dot.setAttribute('aria-hidden', 'true');
    document.body.append(ring, dot);

    const targetPoint = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    const ringPoint = { ...targetPoint };
    const dotPoint = { ...targetPoint };
    let frameId = 0;
    let lastFrameTime = performance.now();
    let magnetTarget = null;
    let tiltTarget = null;

    const setVisible = (visible) => {
        ring.classList.toggle('is-visible', visible);
        dot.classList.toggle('is-visible', visible);
        document.documentElement.classList.toggle('custom-cursor-enabled', visible);
    };

    const animate = (time) => {
        const frameScale = Math.min(2, Math.max(0.25, (time - lastFrameTime) / (1000 / 60)));
        lastFrameTime = time;
        const ringEase = 1 - Math.pow(0.8, frameScale);
        const dotEase = 1 - Math.pow(0.28, frameScale);

        ringPoint.x += (targetPoint.x - ringPoint.x) * ringEase;
        ringPoint.y += (targetPoint.y - ringPoint.y) * ringEase;
        dotPoint.x += (targetPoint.x - dotPoint.x) * dotEase;
        dotPoint.y += (targetPoint.y - dotPoint.y) * dotEase;
        ring.style.translate = `${ringPoint.x}px ${ringPoint.y}px`;
        dot.style.translate = `${dotPoint.x}px ${dotPoint.y}px`;

        const settled = Math.abs(targetPoint.x - ringPoint.x) < 0.1
            && Math.abs(targetPoint.y - ringPoint.y) < 0.1
            && Math.abs(targetPoint.x - dotPoint.x) < 0.1
            && Math.abs(targetPoint.y - dotPoint.y) < 0.1;
        frameId = settled ? 0 : requestAnimationFrame(animate);
    };

    const clearMagnet = () => {
        if (!magnetTarget) return;
        magnetTarget.style.removeProperty('--cursor-pull-x');
        magnetTarget.style.removeProperty('--cursor-pull-y');
        magnetTarget = null;
    };

    const clearTilt = () => {
        if (!tiltTarget) return;
        tiltTarget.style.removeProperty('--cursor-tilt-x');
        tiltTarget.style.removeProperty('--cursor-tilt-y');
        clearLiquidLensPoint(tiltTarget);
        tiltTarget = null;
    };

    const syncTargetEffects = (target, clientX, clientY) => {
        const interactive = target.closest(CUSTOM_CURSOR_HOVER_SELECTOR);
        const isText = Boolean(target.closest(CUSTOM_CURSOR_TEXT_SELECTOR));
        const isDisabled = isDisabledControl(interactive);
        ring.classList.toggle('is-hover', Boolean(interactive) && !isText && !isDisabled);
        ring.classList.toggle('is-text', isText && !isDisabled);
        ring.classList.toggle('is-disabled', isDisabled);
        dot.classList.toggle('is-text', isText && !isDisabled);
        dot.classList.toggle('is-disabled', isDisabled);

        const nextMagnet = isDisabled ? null : target.closest(CURSOR_MAGNET_SELECTOR);
        if (nextMagnet !== magnetTarget) clearMagnet();
        magnetTarget = nextMagnet;
        if (magnetTarget) {
            const rect = magnetTarget.getBoundingClientRect();
            const pullX = Math.max(-4, Math.min(4, (clientX - rect.left - rect.width / 2) * 0.08));
            const pullY = Math.max(-3, Math.min(3, (clientY - rect.top - rect.height / 2) * 0.08));
            magnetTarget.style.setProperty('--cursor-pull-x', `${pullX.toFixed(2)}px`);
            magnetTarget.style.setProperty('--cursor-pull-y', `${pullY.toFixed(2)}px`);
        }

        let nextTilt = target.closest('.card:not(.data-card)');
        if (nextTilt?.matches('body.page-data .content-body > .card')) nextTilt = null;
        if (nextTilt !== tiltTarget) clearTilt();
        tiltTarget = nextTilt;
        if (tiltTarget) {
            const rect = tiltTarget.getBoundingClientRect();
            const localX = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
            const localY = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height));
            tiltTarget.classList.add('cursor-reactive-card');
            tiltTarget.style.setProperty('--cursor-tilt-x', `${((0.5 - localY) * 2.4).toFixed(2)}deg`);
            tiltTarget.style.setProperty('--cursor-tilt-y', `${((localX - 0.5) * 3.2).toFixed(2)}deg`);
            setLiquidLensPoint(tiltTarget, clientX, clientY);
        }
    };

    document.addEventListener('pointermove', (event) => {
        if (event.pointerType && event.pointerType !== 'mouse') return;
        const target = event.target instanceof Element ? event.target : null;
        if (!target) return;

        targetPoint.x = event.clientX;
        targetPoint.y = event.clientY;
        if (!ring.classList.contains('is-visible')) {
            ringPoint.x = dotPoint.x = targetPoint.x;
            ringPoint.y = dotPoint.y = targetPoint.y;
            ring.style.translate = `${targetPoint.x}px ${targetPoint.y}px`;
            dot.style.translate = `${targetPoint.x}px ${targetPoint.y}px`;
            setVisible(true);
        }
        syncTargetEffects(target, event.clientX, event.clientY);
        if (!frameId) {
            lastFrameTime = performance.now();
            frameId = requestAnimationFrame(animate);
        }
    }, { passive: true });

    document.addEventListener('pointerdown', (event) => {
        if (!event.pointerType || event.pointerType === 'mouse') {
            ring.classList.add('is-pressed');
        }
    }, { passive: true });
    document.addEventListener('pointerup', () => ring.classList.remove('is-pressed'), { passive: true });
    document.addEventListener('pointercancel', () => ring.classList.remove('is-pressed'), { passive: true });
    document.addEventListener('mouseleave', () => {
        setVisible(false);
        clearMagnet();
        clearTilt();
    });
    window.addEventListener('blur', () => {
        setVisible(false);
        clearMagnet();
        clearTilt();
    });
}

window.initCustomCursorExperience = initCustomCursorExperience;

// 页面加载时检查认证
document.addEventListener('DOMContentLoaded', function() {
    // 登录页（含未登录时访问 /）不做认证检查，避免重复跳转
    if (!isLoginPage()) {
        checkAuth();
        
        // 检查版本更新（如果本次会话未关闭过提示）
        if (!sessionStorage.getItem('updateBannerDismissed')) {
            checkVersionUpdate();
        } else {
            // 即使关闭了提示，也更新当前版本显示
            fetch('/api/version')
                .then(resp => resp.json())
                .then(data => {
                    const currentVersionEl = document.getElementById('currentVersion');
                    if (currentVersionEl && data.version) {
                        currentVersionEl.textContent = `v${data.version}`;
                        if (data.tags_url) {
                            currentVersionEl.href = data.tags_url;
                        }
                    }
                })
                .catch(() => {});
        }
    }

    // 绑定登出按钮
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }

    // 初始化移动端菜单
    initMobileMenu();

    // 高亮当前导航
    initActiveNav();

    // 初始化修改密码功能
    initChangePassword();
    
    // 绑定关闭更新提示按钮
    const dismissBtn = document.getElementById('dismissUpdateBanner');
    if (dismissBtn) {
        dismissBtn.addEventListener('click', dismissUpdateBanner);
    }

    window.addEventListener('resize', () => {
        const updateBanner = document.getElementById('updateBanner');
        if (updateBanner && window.getComputedStyle(updateBanner).display !== 'none') {
            setUpdateBannerVisible(true);
        }
    }, { passive: true });

    // 返回顶部按钮
    const backToTopBtn = document.getElementById('backToTopBtn');
    if (backToTopBtn) {
        function updateBackToTopVisibility() {
            const scrollTop =
                window.pageYOffset ||
                document.documentElement.scrollTop ||
                document.body.scrollTop ||
                0;
            if (scrollTop > 300) {
                backToTopBtn.classList.add('show');
            } else {
                backToTopBtn.classList.remove('show');
            }
        }

        window.addEventListener('scroll', updateBackToTopVisibility, { passive: true });

        backToTopBtn.addEventListener('click', function () {
            const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            window.scrollTo({
                top: 0,
                behavior: reduceMotion ? 'auto' : 'smooth',
            });
        });

        // 初始计算一次
        updateBackToTopVisibility();
    }

    // 初始化主题
    initTheme();

    // 标签组支持方向键、Home 和 End，保持焦点与选中状态一致
    initTablistKeyboardNavigation();

    // 液态玻璃：按钮区域内高光跟随
    initLiquidGlassLens();

    // Moonshot 风格：双层缓动光标、控件磁吸与卡片微倾斜
    initCustomCursorExperience();
});
