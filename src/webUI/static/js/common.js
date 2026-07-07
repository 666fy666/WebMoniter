// 通用JavaScript函数

// 根据当前路径高亮侧边栏导航
function initActiveNav() {
    const path = window.location.pathname;
    const navItems = document.querySelectorAll('.sidebar-nav .nav-item');
    if (!navItems.length) return;

    navItems.forEach(item => {
        item.classList.remove('active');
        const href = item.getAttribute('href');
        if (!href) return;
        if (path === href || (path === '/' && href === '/config')) {
            item.classList.add('active');
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
        themeIcon.textContent = theme === 'dark' ? '🌙' : '☀️';
    }
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
        document.body.appendChild(container);
    }
    return container;
}

// 显示 Toast 消息
function showToast(message, type = 'success', duration = 3000) {
    const container = ensureToastContainer();
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    // 图标
    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ'
    };
    
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <span class="toast-message">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;
    
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

    if (!mobileMenuBtn || !sidebar || !sidebarOverlay) {
        return;
    }

    const SIDEBAR_STATE_KEY = 'sidebarCollapsed';

    mobileMenuBtn.setAttribute('aria-controls', 'sidebar');
    mobileMenuBtn.setAttribute('aria-expanded', 'false');

    function isMobileViewport() {
        return window.innerWidth <= 768;
    }

    function isSidebarCollapsed() {
        return document.body.classList.contains('sidebar-collapsed');
    }

    function applyDesktopCollapsedState(collapsed) {
        document.body.classList.toggle('sidebar-collapsed', collapsed);
        localStorage.setItem(SIDEBAR_STATE_KEY, collapsed ? '1' : '0');
        mobileMenuBtn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    }

    function initDesktopSidebarState() {
        if (isMobileViewport()) {
            document.body.classList.remove('sidebar-collapsed');
            sidebar.setAttribute('aria-hidden', 'true');
            return;
        }

        const saved = localStorage.getItem(SIDEBAR_STATE_KEY);
        const collapsed = saved === '1';
        applyDesktopCollapsedState(collapsed);
        sidebar.classList.remove('show');
        sidebarOverlay.classList.remove('show');
        document.body.classList.remove('mobile-sidebar-open');
        sidebar.setAttribute('aria-hidden', collapsed ? 'true' : 'false');
    }

    function setMobileMenuState(open) {
        sidebar.classList.toggle('show', open);
        sidebarOverlay.classList.toggle('show', open);
        mobileMenuBtn.classList.toggle('active', open);
        document.body.classList.toggle('mobile-sidebar-open', open);
        mobileMenuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
        sidebar.setAttribute('aria-hidden', open ? 'false' : 'true');
    }

    function closeMobileMenu() {
        setMobileMenuState(false);
    }

    function toggleMenu() {
        if (isMobileViewport()) {
            setMobileMenuState(!sidebar.classList.contains('show'));
            return;
        }

        applyDesktopCollapsedState(!isSidebarCollapsed());
        sidebar.setAttribute('aria-hidden', isSidebarCollapsed() ? 'true' : 'false');
    }

    mobileMenuBtn.addEventListener('click', toggleMenu);
    sidebarOverlay.addEventListener('click', closeMobileMenu);

    document.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape') {
            return;
        }
        if (isMobileViewport() && sidebar.classList.contains('show')) {
            closeMobileMenu();
            mobileMenuBtn.focus();
        }
    });

    sidebar.querySelectorAll('.nav-item').forEach((item) => {
        item.addEventListener('click', () => {
            if (isMobileViewport()) {
                closeMobileMenu();
            }
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
        changePasswordModal.classList.add('show');
        document.body.style.overflow = 'hidden';
    }

    // 隐藏模态框
    function hideModal() {
        changePasswordModal.classList.remove('show');
        document.body.style.overflow = '';
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
            window.scrollTo({
                top: 0,
                behavior: 'smooth',
            });
        });

        // 初始计算一次
        updateBackToTopVisibility();
    }

    // 初始化主题
    initTheme();
});
