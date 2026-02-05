// 登录页面JavaScript

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

// 检查版本更新（登录页专用）
async function checkVersionUpdateOnLogin() {
    try {
        // 获取当前版本信息
        const localResp = await fetch('/api/version');
        if (!localResp.ok) return;
        const localData = await localResp.json();
        const currentVersion = localData.version;
        const githubApiUrl = localData.github_api_url;
        const tagsUrl = localData.tags_url;
        
        // 更新页面上的当前版本显示
        const currentVersionEl = document.getElementById('currentVersion');
        if (currentVersionEl) {
            if (currentVersion && currentVersion !== 'unknown') {
                currentVersionEl.textContent = `v${currentVersion}`;
            } else {
                currentVersionEl.textContent = '版本未知';
            }
        }
        
        if (!currentVersion || currentVersion === 'unknown') return;
        
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
            
            updateBanner.style.display = 'flex';
        }
    } catch (error) {
        console.log('版本检查失败:', error.message);
        // 即使版本检查失败，也显示本地版本（如果已获取）
    }
}

// 关闭更新提示
function dismissUpdateBanner() {
    const updateBanner = document.getElementById('updateBanner');
    if (updateBanner) {
        updateBanner.style.display = 'none';
        // 记录到 sessionStorage，本次会话不再提示
        sessionStorage.setItem('updateBannerDismissed', 'true');
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const errorMessage = document.getElementById('errorMessage');

    // 登录表单提交
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

    // 绑定关闭更新提示按钮
    const dismissBtn = document.getElementById('dismissUpdateBanner');
    if (dismissBtn) {
        dismissBtn.addEventListener('click', dismissUpdateBanner);
    }

    // 检查版本更新（如果本次会话未关闭过提示）
    if (!sessionStorage.getItem('updateBannerDismissed')) {
        checkVersionUpdateOnLogin();
    } else {
        // 即使关闭了提示，也更新当前版本显示
        fetch('/api/version')
            .then(resp => resp.json())
            .then(data => {
                const currentVersionEl = document.getElementById('currentVersion');
                if (currentVersionEl && data.version) {
                    currentVersionEl.textContent = `v${data.version}`;
                }
            })
            .catch(() => {
                const currentVersionEl = document.getElementById('currentVersion');
                if (currentVersionEl) {
                    currentVersionEl.textContent = '版本未知';
                }
            });
    }
});
