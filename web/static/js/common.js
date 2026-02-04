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

    // 初始化修改密码功能
    initChangePassword();
});
