// 登录页面JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const errorMessage = document.getElementById('errorMessage');

    loginForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;

        // 清空错误消息
        errorMessage.textContent = '';
        errorMessage.classList.remove('show');

        try {
            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);

            const response = await fetch('/api/login', {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();

            if (data.success) {
                window.location.href = '/';
            } else {
                errorMessage.textContent = data.message || '登录失败';
                errorMessage.classList.add('show');
            }
        } catch (error) {
            errorMessage.textContent = '网络错误，请稍后重试';
            errorMessage.classList.add('show');
        }
    });
});
