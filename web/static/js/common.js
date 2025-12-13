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
});
