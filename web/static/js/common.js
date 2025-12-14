// 通用JavaScript函数

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

// 显示消息
function showMessage(elementId, message, type = 'success') {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = message;
        element.className = `message ${type}`;
        setTimeout(() => {
            element.className = 'message';
            element.style.display = 'none';
        }, 5000);
    }
}

// 格式化日期时间
function formatDateTime(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN');
}

// 移动端菜单切换
function initMobileMenu() {
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    if (!mobileMenuBtn || !sidebar || !sidebarOverlay) {
        return; // 登录页面没有这些元素
    }

    // 切换菜单显示/隐藏
    function toggleMenu() {
        const isOpen = sidebar.classList.contains('show');
        if (isOpen) {
            sidebar.classList.remove('show');
            sidebarOverlay.classList.remove('show');
            mobileMenuBtn.classList.remove('active');
            document.body.style.overflow = ''; // 恢复滚动
        } else {
            sidebar.classList.add('show');
            sidebarOverlay.classList.add('show');
            mobileMenuBtn.classList.add('active');
            document.body.style.overflow = 'hidden'; // 禁止背景滚动
        }
    }

    // 关闭菜单
    function closeMenu() {
        sidebar.classList.remove('show');
        sidebarOverlay.classList.remove('show');
        mobileMenuBtn.classList.remove('active');
        document.body.style.overflow = '';
    }

    // 绑定事件
    mobileMenuBtn.addEventListener('click', toggleMenu);
    sidebarOverlay.addEventListener('click', closeMenu);

    // 点击导航项后关闭菜单（移动端）
    const navItems = sidebar.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                closeMenu();
            }
        });
    });

    // 窗口大小改变时，如果切换到桌面端，自动关闭移动端菜单
    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            if (window.innerWidth > 768) {
                closeMenu();
            }
        }, 250);
    });
}

// 页面加载时检查认证
document.addEventListener('DOMContentLoaded', function() {
    // 如果不是登录页，检查认证
    if (!window.location.pathname.includes('/login')) {
        checkAuth();
    }

    // 绑定登出按钮
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }

    // 初始化移动端菜单
    initMobileMenu();
});
