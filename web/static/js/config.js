// 配置管理页面JavaScript

let originalConfig = null;
let pushChannelTypes = {
    'serverChan_turbo': { name: 'Server酱 Turbo', fields: ['send_key'] },
    'serverChan_3': { name: 'Server酱 3', fields: ['send_key', 'uid', 'tags'] },
    'wecom_apps': { name: '企业微信应用', fields: ['corp_id', 'agent_id', 'corp_secret', 'touser'] },
    'wecom_bot': { name: '企业微信机器人', fields: ['key'] },
    'dingtalk_bot': { name: '钉钉机器人', fields: ['access_token', 'secret'] },
    'feishu_apps': { name: '飞书自建应用', fields: ['app_id', 'app_secret', 'receive_id_type', 'receive_id'] },
    'feishu_bot': { name: '飞书机器人', fields: ['webhook_key', 'sign_secret'] },
    'telegram_bot': { name: 'Telegram机器人', fields: ['api_token', 'chat_id'] },
    'qq_bot': { name: 'QQ机器人', fields: ['base_url', 'app_id', 'app_secret', 'push_target_list'] },
    'napcat_qq': { name: 'NapCatQQ', fields: ['api_url', 'token', 'user_id', 'group_id', 'at_qq'] },
    'bark': { name: 'Bark', fields: ['server_url', 'key'] },
    'gotify': { name: 'Gotify', fields: ['web_server_url'] },
    'webhook': { name: 'Webhook', fields: ['webhook_url', 'request_method'] },
    'pushplus': { name: 'PushPlus', fields: ['token', 'channel', 'topic', 'template', 'to'] },
    'email': { name: 'Email', fields: ['smtp_host', 'smtp_port', 'smtp_ssl', 'smtp_tls', 'sender_email', 'sender_password', 'receiver_email'] },
    'wxpusher': { name: 'WxPusher', fields: ['app_token', 'uids', 'topic_ids', 'content_type'] }
};

document.addEventListener('DOMContentLoaded', async function() {
    const configMessage = document.getElementById('configMessage');
    const quietHoursEnable = document.getElementById('quiet_hours_enable');
    const quietHoursEnableLabel = document.getElementById('quiet_hours_enable_label');
    const checkinEnable = document.getElementById('checkin_enable');
    const checkinEnableLabel = document.getElementById('checkin_enable_label');
    const tiebaEnable = document.getElementById('tieba_enable');
    const tiebaEnableLabel = document.getElementById('tieba_enable_label');
    const tableView = document.getElementById('tableView');
    const textView = document.getElementById('textView');
    const tabButtons = document.querySelectorAll('.tab-btn');
    const yamlEditor = document.getElementById('yamlEditor');
    const reloadYamlBtn = document.getElementById('reloadYamlBtn');
    const saveYamlBtn = document.getElementById('saveYamlBtn');

    // 视图切换
    tabButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const view = this.dataset.view;
            tabButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            if (view === 'table') {
                tableView.style.display = 'block';
                textView.style.display = 'none';
            } else {
                tableView.style.display = 'none';
                textView.style.display = 'block';
                // 切换到文本视图时加载YAML内容
                loadYamlConfig();
            }
        });
    });

    // 加载YAML配置
    async function loadYamlConfig() {
        try {
            const response = await fetch('/api/config?format=yaml');
            const data = await response.json();
            
            if (data.error) {
                showMessage('configMessage', data.error, 'error');
                yamlEditor.value = '';
            } else {
                yamlEditor.value = data.content || '';
            }
        } catch (error) {
            showMessage('configMessage', '加载YAML配置失败: ' + error.message, 'error');
            yamlEditor.value = '';
        }
    }

    // 保存YAML配置
    async function saveYamlConfig() {
        const yamlContent = yamlEditor.value.trim();
        
        if (!yamlContent) {
            showMessage('configMessage', '配置内容不能为空', 'error');
            return;
        }

        try {
            saveYamlBtn.disabled = true;
            saveYamlBtn.textContent = '保存中...';

            const response = await fetch('/api/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ content: yamlContent })
            });

            const data = await response.json();

            if (data.error) {
                showMessage('configMessage', data.error, 'error');
            } else {
                showMessage('configMessage', data.message || '配置保存成功并已热重载', 'success');
                // 更新原始配置
                try {
                    const configResponse = await fetch('/api/config?format=json');
                    const configData = await configResponse.json();
                    if (configData.config) {
                        originalConfig = JSON.parse(JSON.stringify(configData.config));
                    }
                } catch (e) {
                    console.error('更新原始配置失败:', e);
                }
            }
        } catch (error) {
            showMessage('configMessage', '保存YAML配置失败: ' + error.message, 'error');
        } finally {
            saveYamlBtn.disabled = false;
            saveYamlBtn.textContent = '保存配置';
        }
    }

    // 绑定YAML编辑器按钮事件
    if (reloadYamlBtn) {
        reloadYamlBtn.addEventListener('click', loadYamlConfig);
    }
    if (saveYamlBtn) {
        saveYamlBtn.addEventListener('click', saveYamlConfig);
    }

    // 免打扰时段开关事件
    quietHoursEnable.addEventListener('change', function() {
        quietHoursEnableLabel.textContent = this.checked ? '开启' : '关闭';
    });

    // 每日签到开关事件
    if (checkinEnable && checkinEnableLabel) {
        checkinEnable.addEventListener('change', function() {
            checkinEnableLabel.textContent = this.checked ? '开启' : '关闭';
        });
    }

    // 贴吧签到开关事件
    if (tiebaEnable && tiebaEnableLabel) {
        tiebaEnable.addEventListener('change', function() {
            tiebaEnableLabel.textContent = this.checked ? '开启' : '关闭';
        });
    }

    // 加载配置
    async function loadConfig() {
        try {
            const response = await fetch('/api/config?format=json');
            const data = await response.json();

            if (data.error) {
                showMessage('configMessage', data.error, 'error');
                return;
            }

            const config = data.config;
            originalConfig = JSON.parse(JSON.stringify(config)); // 深拷贝

            // 填充所有配置
            loadSectionConfig('weibo', config);
            loadSectionConfig('huya', config);
            loadSectionConfig('checkin', config);
            loadSectionConfig('tieba', config);
            loadSectionConfig('scheduler', config);
            loadSectionConfig('quiet_hours', config);
            loadSectionConfig('push_channel', config);
            loadSectionConfig('plugins', config);

            showMessage('configMessage', '配置加载成功', 'success');
        } catch (error) {
            showMessage('configMessage', '加载配置失败: ' + error.message, 'error');
        }
    }

    // 渲染推送通道
    function renderPushChannels(channels) {
        const container = document.getElementById('pushChannelsContainer');
        container.innerHTML = '';

        if (channels.length === 0) {
            container.innerHTML = '<p style="color: #7f8c8d; text-align: center; padding: 20px;">暂无推送通道</p>';
            return;
        }

        channels.forEach((channel, index) => {
            const channelDiv = createPushChannelElement(channel, index);
            container.appendChild(channelDiv);
        });
    }

    // 创建推送通道元素
    function createPushChannelElement(channel, index) {
        const div = document.createElement('div');
        div.className = 'push-channel-item';
        div.dataset.index = index;

        const type = channel.type || '';
        const typeInfo = pushChannelTypes[type] || { name: '未知类型', fields: [] };
        const name = channel.name || typeInfo.name;

        let html = `
            <div class="push-channel-header">
                <div class="push-channel-title">
                    <span>${name}</span>
                    <label class="switch">
                        <input type="checkbox" class="channel-enable" ${channel.enable ? 'checked' : ''}>
                        <span class="slider"></span>
                    </label>
                </div>
                <div class="push-channel-actions">
                    <button class="btn btn-small btn-secondary reload-channel-btn">重新加载</button>
                    <button class="btn btn-small btn-primary save-channel-btn">保存配置</button>
                </div>
            </div>
            <table class="push-channel-table">
                <tr>
                    <td class="config-label">通道名称</td>
                    <td><input type="text" class="channel-name form-input" value="${name || ''}" placeholder="请输入通道名称"></td>
                </tr>
                <tr>
                    <td class="config-label">通道类型</td>
                    <td>
                        <select class="channel-type form-input">
                            ${Object.keys(pushChannelTypes).map(key => 
                                `<option value="${key}" ${key === type ? 'selected' : ''}>${pushChannelTypes[key].name}</option>`
                            ).join('')}
                        </select>
                    </td>
                </tr>
        `;

        // 根据类型添加字段
        const fields = typeInfo.fields || [];
        fields.forEach(field => {
            let value = channel[field] || '';
            if (field === 'push_target_list' && Array.isArray(value)) {
                value = JSON.stringify(value);
            }
            const fieldLabel = getFieldLabel(field);
            html += `
                <tr>
                    <td class="config-label">${fieldLabel}</td>
                    <td>
                        ${getFieldInput(field, value)}
                    </td>
                </tr>
            `;
        });

        html += '</table>';
        div.innerHTML = html;

        // 绑定事件
        const typeSelect = div.querySelector('.channel-type');
        typeSelect.addEventListener('change', function() {
            updateChannelFields(div, this.value);
        });

        // 绑定重新加载按钮事件
        const reloadBtn = div.querySelector('.reload-channel-btn');
        if (reloadBtn) {
            reloadBtn.addEventListener('click', async function() {
                await reloadChannelConfig(div, index);
            });
        }

        // 绑定保存配置按钮事件
        const saveBtn = div.querySelector('.save-channel-btn');
        if (saveBtn) {
            saveBtn.addEventListener('click', async function() {
                await saveChannelConfig(div, index, saveBtn);
            });
        }

        return div;
    }

    // 更新通道字段
    function updateChannelFields(container, newType) {
        const typeInfo = pushChannelTypes[newType] || { fields: [] };
        const table = container.querySelector('.push-channel-table');
        
        // 移除旧的字段行（保留名称和类型行）
        const rows = Array.from(table.querySelectorAll('tr'));
        rows.forEach((row, index) => {
            if (index >= 2) { // 保留前两行（名称和类型）
                row.remove();
            }
        });

        // 添加新字段
        typeInfo.fields.forEach(field => {
            const row = document.createElement('tr');
            const fieldLabel = getFieldLabel(field);
            row.innerHTML = `
                <td class="config-label">${fieldLabel}</td>
                <td>${getFieldInput(field, '')}</td>
            `;
            table.appendChild(row);
        });
    }

    // 获取字段标签
    function getFieldLabel(field) {
        const labels = {
            'send_key': 'Send Key',
            'uid': 'UID',
            'tags': 'Tags',
            'corp_id': '企业ID',
            'agent_id': '应用ID',
            'corp_secret': '应用Secret',
            'touser': '接收用户',
            'key': 'Key',
            'access_token': 'Access Token',
            'secret': 'Secret',
            'app_id': 'App ID',
            'app_secret': 'App Secret',
            'receive_id_type': '接收ID类型',
            'receive_id': '接收ID',
            'webhook_key': 'Webhook Key',
            'sign_secret': '签名密钥',
            'api_token': 'API Token',
            'chat_id': 'Chat ID',
            'base_url': 'Base URL',
            'push_target_list': '推送目标列表（JSON格式）',
            'api_url': 'API URL',
            'token': 'Token',
            'user_id': '用户ID',
            'group_id': '群组ID',
            'at_qq': '@QQ',
            'server_url': '服务器URL',
            'webhook_url': 'Webhook URL',
            'request_method': '请求方法',
            'channel': '推送渠道',
            'topic': '群组代码',
            'template': '消息模板',
            'to': '接收者标识',
            'smtp_host': 'SMTP主机',
            'smtp_port': 'SMTP端口',
            'smtp_ssl': '启用SSL',
            'smtp_tls': '启用TLS',
            'sender_email': '发送邮箱',
            'sender_password': '发送密码',
            'receiver_email': '接收邮箱',
            'app_token': '应用令牌',
            'uids': '用户ID列表',
            'topic_ids': '主题ID列表',
            'content_type': '内容类型'
        };
        return labels[field] || field;
    }

    // 获取字段输入框
    function getFieldInput(field, value) {
        if (field === 'smtp_ssl' || field === 'smtp_tls') {
            return `<label class="switch">
                <input type="checkbox" class="field-${field}" ${value ? 'checked' : ''}>
                <span class="slider"></span>
            </label>`;
        }
        if (field === 'request_method') {
            return `<select class="field-${field} form-input">
                <option value="GET" ${value === 'GET' ? 'selected' : ''}>GET</option>
                <option value="POST" ${value === 'POST' ? 'selected' : ''}>POST</option>
            </select>`;
        }
        if (field === 'channel') {
            return `<select class="field-${field} form-input">
                <option value="wechat" ${value === 'wechat' ? 'selected' : ''}>微信</option>
                <option value="mail" ${value === 'mail' ? 'selected' : ''}>邮件</option>
                <option value="webhook" ${value === 'webhook' ? 'selected' : ''}>Webhook</option>
                <option value="cp" ${value === 'cp' ? 'selected' : ''}>企业微信</option>
                <option value="sms" ${value === 'sms' ? 'selected' : ''}>短信</option>
            </select>`;
        }
        if (field === 'template') {
            return `<select class="field-${field} form-input">
                <option value="html" ${value === 'html' ? 'selected' : ''}>HTML</option>
                <option value="txt" ${value === 'txt' ? 'selected' : ''}>TXT</option>
                <option value="json" ${value === 'json' ? 'selected' : ''}>JSON</option>
                <option value="markdown" ${value === 'markdown' ? 'selected' : ''}>Markdown</option>
            </select>`;
        }
        if (field === 'content_type') {
            return `<select class="field-${field} form-input">
                <option value="1" ${value == 1 ? 'selected' : ''}>文本</option>
                <option value="2" ${value == 2 ? 'selected' : ''}>HTML</option>
                <option value="3" ${value == 3 ? 'selected' : ''}>Markdown</option>
            </select>`;
        }
        if (field === 'receive_id_type') {
            return `<select class="field-${field} form-input">
                <option value="open_id" ${value === 'open_id' ? 'selected' : ''}>Open ID</option>
                <option value="user_id" ${value === 'user_id' ? 'selected' : ''}>User ID</option>
                <option value="union_id" ${value === 'union_id' ? 'selected' : ''}>Union ID</option>
            </select>`;
        }
        if (field === 'push_target_list') {
            return `<textarea class="field-${field} form-textarea" rows="5" placeholder='[{"guild_name":"服务器名","channel_name_list":["频道1","频道2"]}]'>${value}</textarea>`;
        }
        return `<input type="text" class="field-${field} form-input" value="${value || ''}">`;
    }

    // 渲染签到多账号列表
    function renderCheckinAccounts(accounts) {
        const container = document.getElementById('checkin_accounts_list');
        if (!container) return;
        container.innerHTML = '';
        const list = accounts.length ? accounts : [{ email: '', password: '' }];
        list.forEach((acc, index) => {
            const row = document.createElement('div');
            row.className = 'multi-account-row';
            row.dataset.index = index;
            row.innerHTML = `
                <div class="account-fields">
                    <input type="text" class="form-input checkin-account-email" placeholder="邮箱或用户名">
                    <input type="password" class="form-input checkin-account-password" placeholder="密码">
                </div>
                <button type="button" class="btn btn-secondary row-remove checkin-account-remove">删除</button>
            `;
            row.querySelector('.checkin-account-email').value = acc.email || '';
            row.querySelector('.checkin-account-password').value = acc.password || '';
            container.appendChild(row);
        });
    }

    // 渲染贴吧多 Cookie 列表
    function renderTiebaCookies(cookies) {
        const container = document.getElementById('tieba_cookies_list');
        if (!container) return;
        container.innerHTML = '';
        const list = cookies.length ? cookies : [''];
        list.forEach((cookie, index) => {
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.dataset.index = index;
            row.innerHTML = `
                <div class="cookie-field">
                    <input type="text" class="form-input tieba-cookie-value" placeholder="贴吧 Cookie（须包含 BDUSS）">
                </div>
                <button type="button" class="btn btn-secondary row-remove tieba-cookie-remove">删除</button>
            `;
            row.querySelector('.tieba-cookie-value').value = cookie || '';
            container.appendChild(row);
        });
    }

    // 加载特定section的配置
    function loadSectionConfig(section, config) {
        switch(section) {
            case 'weibo':
                if (config.weibo) {
                    document.getElementById('weibo_cookie').value = config.weibo.cookie || '';
                    document.getElementById('weibo_uids').value = typeof config.weibo.uids === 'string' 
                        ? config.weibo.uids 
                        : (Array.isArray(config.weibo.uids) ? config.weibo.uids.join(',') : '');
                    document.getElementById('weibo_concurrency').value = config.weibo.concurrency || 3;
                }
                break;
            case 'checkin':
                if (config.checkin) {
                    if (checkinEnable) {
                        checkinEnable.checked = !!config.checkin.enable;
                        if (checkinEnableLabel) {
                            checkinEnableLabel.textContent = checkinEnable.checked ? '开启' : '关闭';
                        }
                    }
                    const loginUrlInput = document.getElementById('checkin_login_url');
                    const checkinUrlInput = document.getElementById('checkin_checkin_url');
                    const userPageUrlInput = document.getElementById('checkin_user_page_url');
                    const emailInput = document.getElementById('checkin_email');
                    const passwordInput = document.getElementById('checkin_password');
                    const timeInput = document.getElementById('checkin_time');

                    if (loginUrlInput) loginUrlInput.value = config.checkin.login_url || '';
                    if (checkinUrlInput) checkinUrlInput.value = config.checkin.checkin_url || '';
                    if (userPageUrlInput) userPageUrlInput.value = config.checkin.user_page_url || '';
                    if (emailInput) emailInput.value = config.checkin.email || '';
                    if (passwordInput) passwordInput.value = config.checkin.password || '';
                    if (timeInput) {
                        const timeVal = config.checkin.time || '08:00';
                        timeInput.value = timeVal.length === 5 ? timeVal : '08:00';
                    }
                    // 多账号列表：优先使用 accounts，否则用单账号组一条
                    const accountsListEl = document.getElementById('checkin_accounts_list');
                    if (accountsListEl) {
                        const accounts = Array.isArray(config.checkin.accounts) && config.checkin.accounts.length > 0
                            ? config.checkin.accounts
                            : [{ email: config.checkin.email || '', password: config.checkin.password || '' }];
                        renderCheckinAccounts(accounts);
                    }
                }
                break;
            case 'tieba':
                if (config.tieba) {
                    if (tiebaEnable) {
                        tiebaEnable.checked = !!config.tieba.enable;
                        if (tiebaEnableLabel) {
                            tiebaEnableLabel.textContent = tiebaEnable.checked ? '开启' : '关闭';
                        }
                    }
                    const tiebaCookieInput = document.getElementById('tieba_cookie');
                    const tiebaTimeInput = document.getElementById('tieba_time');
                    if (tiebaCookieInput) tiebaCookieInput.value = config.tieba.cookie || '';
                    if (tiebaTimeInput) {
                        const timeVal = config.tieba.time || '08:10';
                        tiebaTimeInput.value = timeVal.length === 5 ? timeVal : '08:10';
                    }
                    // 多 Cookie 列表：优先使用 cookies，否则用单条 cookie
                    const cookiesListEl = document.getElementById('tieba_cookies_list');
                    if (cookiesListEl) {
                        const cookies = Array.isArray(config.tieba.cookies) && config.tieba.cookies.length > 0
                            ? config.tieba.cookies
                            : (config.tieba.cookie ? [config.tieba.cookie] : ['']);
                        renderTiebaCookies(cookies);
                    }
                }
                break;
            case 'huya':
                if (config.huya) {
                    document.getElementById('huya_rooms').value = typeof config.huya.rooms === 'string' 
                        ? config.huya.rooms 
                        : (Array.isArray(config.huya.rooms) ? config.huya.rooms.join(',') : '');
                    document.getElementById('huya_concurrency').value = config.huya.concurrency || 7;
                }
                break;
            case 'scheduler':
                if (config.scheduler) {
                    document.getElementById('huya_monitor_interval_seconds').value = config.scheduler.huya_monitor_interval_seconds || 65;
                    document.getElementById('weibo_monitor_interval_seconds').value = config.scheduler.weibo_monitor_interval_seconds || 300;
                    document.getElementById('cleanup_logs_hour').value = config.scheduler.cleanup_logs_hour || 2;
                    document.getElementById('cleanup_logs_minute').value = config.scheduler.cleanup_logs_minute || 0;
                    document.getElementById('retention_days').value = config.scheduler.retention_days || 3;
                }
                break;
            case 'quiet_hours':
                if (config.quiet_hours) {
                    quietHoursEnable.checked = config.quiet_hours.enable || false;
                    quietHoursEnableLabel.textContent = quietHoursEnable.checked ? '开启' : '关闭';
                    const startTime = config.quiet_hours.start || '22:00';
                    const endTime = config.quiet_hours.end || '08:00';
                    document.getElementById('quiet_hours_start').value = startTime.length === 5 ? startTime : '22:00';
                    document.getElementById('quiet_hours_end').value = endTime.length === 5 ? endTime : '08:00';
                }
                break;
            case 'push_channel':
                renderPushChannels(config.push_channel || []);
                break;
            case 'plugins':
                try {
                    const pluginsJson = document.getElementById('plugins_json');
                    if (pluginsJson) {
                        const val = config.plugins && typeof config.plugins === 'object' ? config.plugins : {};
                        pluginsJson.value = JSON.stringify(val, null, 2);
                    }
                } catch (e) {
                    if (document.getElementById('plugins_json')) {
                        document.getElementById('plugins_json').value = '{}';
                    }
                }
                break;
        }
    }

    // 收集特定section的配置数据
    function collectSectionConfig(section) {
        const config = {};
        switch(section) {
            case 'weibo':
                config.weibo = {
                    cookie: document.getElementById('weibo_cookie').value.trim(),
                    uids: document.getElementById('weibo_uids').value.trim(),
                    concurrency: parseInt(document.getElementById('weibo_concurrency').value) || 3
                };
                break;
            case 'checkin': {
                const accounts = [];
                document.querySelectorAll('#checkin_accounts_list .multi-account-row').forEach(row => {
                    const email = (row.querySelector('.checkin-account-email')?.value || '').trim();
                    const password = (row.querySelector('.checkin-account-password')?.value || '').trim();
                    accounts.push({ email, password });
                });
                const first = accounts[0] || { email: '', password: '' };
                config.checkin = {
                    enable: checkinEnable ? checkinEnable.checked : false,
                    login_url: (document.getElementById('checkin_login_url')?.value || '').trim(),
                    checkin_url: (document.getElementById('checkin_checkin_url')?.value || '').trim(),
                    user_page_url: (document.getElementById('checkin_user_page_url')?.value || '').trim(),
                    email: (document.getElementById('checkin_email')?.value || '').trim() || first.email,
                    password: (document.getElementById('checkin_password')?.value || '').trim() || first.password,
                    time: (document.getElementById('checkin_time')?.value || '').trim() || '08:00'
                };
                if (accounts.length > 0) config.checkin.accounts = accounts;
                break;
            }
            case 'tieba': {
                const cookies = [];
                document.querySelectorAll('#tieba_cookies_list .multi-cookie-row').forEach(row => {
                    const val = (row.querySelector('.tieba-cookie-value')?.value || '').trim();
                    cookies.push(val);
                });
                const firstCookie = cookies[0] || (document.getElementById('tieba_cookie')?.value || '').trim();
                config.tieba = {
                    enable: tiebaEnable ? tiebaEnable.checked : false,
                    cookie: (document.getElementById('tieba_cookie')?.value || '').trim() || firstCookie,
                    time: (document.getElementById('tieba_time')?.value || '').trim() || '08:10'
                };
                if (cookies.length > 0) config.tieba.cookies = cookies;
                break;
            }
            case 'huya':
                config.huya = {
                    rooms: document.getElementById('huya_rooms').value.trim(),
                    concurrency: parseInt(document.getElementById('huya_concurrency').value) || 7
                };
                break;
            case 'scheduler':
                config.scheduler = {
                    huya_monitor_interval_seconds: parseInt(document.getElementById('huya_monitor_interval_seconds').value) || 65,
                    weibo_monitor_interval_seconds: parseInt(document.getElementById('weibo_monitor_interval_seconds').value) || 300,
                    cleanup_logs_hour: parseInt(document.getElementById('cleanup_logs_hour').value) || 2,
                    cleanup_logs_minute: parseInt(document.getElementById('cleanup_logs_minute').value) || 0,
                    retention_days: parseInt(document.getElementById('retention_days').value) || 3
                };
                break;
            case 'quiet_hours':
                config.quiet_hours = {
                    enable: quietHoursEnable.checked,
                    start: document.getElementById('quiet_hours_start').value || '22:00',
                    end: document.getElementById('quiet_hours_end').value || '08:00'
                };
                break;
            case 'push_channel':
                config.push_channel = [];
                const channelItems = document.querySelectorAll('.push-channel-item');
                channelItems.forEach(item => {
                    const channel = {
                        name: item.querySelector('.channel-name').value.trim(),
                        enable: item.querySelector('.channel-enable').checked,
                        type: item.querySelector('.channel-type').value
                    };

                    const typeInfo = pushChannelTypes[channel.type] || { fields: [] };
                    typeInfo.fields.forEach(field => {
                        const input = item.querySelector(`.field-${field}`);
                        if (input) {
                            if (input.type === 'checkbox') {
                                channel[field] = input.checked;
                            } else if (field === 'push_target_list') {
                                try {
                                    channel[field] = JSON.parse(input.value.trim() || '[]');
                                } catch (e) {
                                    channel[field] = [];
                                }
                            } else if (field === 'smtp_port' || field === 'content_type') {
                                const value = input.value.trim();
                                if (value) {
                                    channel[field] = field === 'content_type' ? parseInt(value) : parseInt(value);
                                }
                            } else {
                                const value = input.value.trim();
                                if (value) {
                                    channel[field] = value;
                                }
                            }
                        }
                    });

                    config.push_channel.push(channel);
                });
                break;
            case 'plugins':
                try {
                    const pluginsJson = document.getElementById('plugins_json');
                    if (pluginsJson && pluginsJson.value.trim()) {
                        config.plugins = JSON.parse(pluginsJson.value.trim());
                    } else {
                        config.plugins = {};
                    }
                } catch (e) {
                    config.plugins = {};
                }
                break;
        }
        return config;
    }

    // 收集配置数据
    function collectConfig() {
        const config = {};

        // 微博配置
        config.weibo = {
            cookie: document.getElementById('weibo_cookie').value.trim(),
            uids: document.getElementById('weibo_uids').value.trim(),
            concurrency: parseInt(document.getElementById('weibo_concurrency').value) || 3
        };

        // 虎牙配置
        config.huya = {
            rooms: document.getElementById('huya_rooms').value.trim(),
            concurrency: parseInt(document.getElementById('huya_concurrency').value) || 7
        };

        // 调度器配置
        config.scheduler = {
            huya_monitor_interval_seconds: parseInt(document.getElementById('huya_monitor_interval_seconds').value) || 65,
            weibo_monitor_interval_seconds: parseInt(document.getElementById('weibo_monitor_interval_seconds').value) || 300,
            cleanup_logs_hour: parseInt(document.getElementById('cleanup_logs_hour').value) || 2,
            cleanup_logs_minute: parseInt(document.getElementById('cleanup_logs_minute').value) || 0,
            retention_days: parseInt(document.getElementById('retention_days').value) || 3
        };

        // 免打扰时段配置
        config.quiet_hours = {
            enable: quietHoursEnable.checked,
            start: document.getElementById('quiet_hours_start').value || '22:00',
            end: document.getElementById('quiet_hours_end').value || '08:00'
        };

        // 每日签到配置（含多账号）
        const checkinAccounts = [];
        document.querySelectorAll('#checkin_accounts_list .multi-account-row').forEach(row => {
            const email = (row.querySelector('.checkin-account-email')?.value || '').trim();
            const password = (row.querySelector('.checkin-account-password')?.value || '').trim();
            checkinAccounts.push({ email, password });
        });
        const firstCheckin = checkinAccounts[0] || { email: '', password: '' };
        config.checkin = {
            enable: checkinEnable ? checkinEnable.checked : false,
            login_url: (document.getElementById('checkin_login_url')?.value || '').trim(),
            checkin_url: (document.getElementById('checkin_checkin_url')?.value || '').trim(),
            user_page_url: (document.getElementById('checkin_user_page_url')?.value || '').trim(),
            email: (document.getElementById('checkin_email')?.value || '').trim() || firstCheckin.email,
            password: (document.getElementById('checkin_password')?.value || '').trim() || firstCheckin.password,
            time: (document.getElementById('checkin_time')?.value || '').trim() || '08:00'
        };
        if (checkinAccounts.length > 0) config.checkin.accounts = checkinAccounts;

        // 贴吧签到配置（含多 Cookie）
        const tiebaCookies = [];
        document.querySelectorAll('#tieba_cookies_list .multi-cookie-row').forEach(row => {
            const val = (row.querySelector('.tieba-cookie-value')?.value || '').trim();
            tiebaCookies.push(val);
        });
        const firstTiebaCookie = tiebaCookies[0] || (document.getElementById('tieba_cookie')?.value || '').trim();
        config.tieba = {
            enable: tiebaEnable ? tiebaEnable.checked : false,
            cookie: (document.getElementById('tieba_cookie')?.value || '').trim() || firstTiebaCookie,
            time: (document.getElementById('tieba_time')?.value || '').trim() || '08:10'
        };
        if (tiebaCookies.length > 0) config.tieba.cookies = tiebaCookies;

        // 推送通道配置
        config.push_channel = [];
        const channelItems = document.querySelectorAll('.push-channel-item');
        channelItems.forEach(item => {
            const channel = {
                name: item.querySelector('.channel-name').value.trim(),
                enable: item.querySelector('.channel-enable').checked,
                type: item.querySelector('.channel-type').value
            };

            const typeInfo = pushChannelTypes[channel.type] || { fields: [] };
            typeInfo.fields.forEach(field => {
                const input = item.querySelector(`.field-${field}`);
                if (input) {
                    if (input.type === 'checkbox') {
                        channel[field] = input.checked;
                    } else if (field === 'push_target_list') {
                        try {
                            channel[field] = JSON.parse(input.value.trim() || '[]');
                        } catch (e) {
                            channel[field] = [];
                        }
                    } else if (field === 'smtp_port' || field === 'content_type') {
                        // 数字字段
                        const value = input.value.trim();
                        if (value) {
                            channel[field] = field === 'content_type' ? parseInt(value) : parseInt(value);
                        }
                    } else {
                        const value = input.value.trim();
                        if (value) {
                            channel[field] = value;
                        }
                    }
                }
            });

            config.push_channel.push(channel);
        });

        // 插件/扩展配置
        try {
            const pluginsJson = document.getElementById('plugins_json');
            if (pluginsJson && pluginsJson.value.trim()) {
                config.plugins = JSON.parse(pluginsJson.value.trim());
            } else {
                config.plugins = {};
            }
        } catch (e) {
            config.plugins = {};
        }

        return config;
    }

    // 保存配置
    async function saveConfig() {
        const config = collectConfig();

        try {
            const response = await fetch('/api/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ config: config })
            });

            const data = await response.json();

            if (data.error) {
                showMessage('configMessage', data.error, 'error');
            } else {
                originalConfig = JSON.parse(JSON.stringify(config));
                showMessage('configMessage', data.message || '配置保存成功并已热重载', 'success');
            }
        } catch (error) {
            showMessage('configMessage', '保存配置失败: ' + error.message, 'error');
        }
    }

    // 保存特定section的配置
    async function saveSectionConfig(section, btn) {
        try {
            // 先加载完整配置
            const response = await fetch('/api/config?format=json');
            const data = await response.json();

            if (data.error) {
                showMessage('configMessage', data.error, 'error');
                return;
            }

            const fullConfig = data.config;
            const sectionConfig = collectSectionConfig(section);
            
            // 合并配置
            const mergedConfig = { ...fullConfig, ...sectionConfig };

            // 保存配置
            btn.disabled = true;
            btn.textContent = '保存中...';

            const saveResponse = await fetch('/api/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ config: mergedConfig })
            });

            const saveData = await saveResponse.json();

            if (saveData.error) {
                showMessage('configMessage', saveData.error, 'error');
            } else {
                if (originalConfig) {
                    Object.assign(originalConfig, sectionConfig);
                }
                showMessage('configMessage', saveData.message || '配置保存成功并已热重载', 'success');
            }
        } catch (error) {
            showMessage('configMessage', '保存配置失败: ' + error.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = '保存配置';
        }
    }

    // 加载特定section的配置
    async function loadSectionConfigFromServer(section, btn) {
        try {
            btn.disabled = true;
            btn.textContent = '加载中...';

            const response = await fetch('/api/config?format=json');
            const data = await response.json();

            if (data.error) {
                showMessage('configMessage', data.error, 'error');
                return;
            }

            const config = data.config;
            loadSectionConfig(section, config);
            showMessage('configMessage', '配置加载成功', 'success');
        } catch (error) {
            showMessage('configMessage', '加载配置失败: ' + error.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = '重新加载';
        }
    }

    // 重新加载单个通道配置
    async function reloadChannelConfig(channelDiv, index) {
        try {
            const reloadBtn = channelDiv.querySelector('.reload-channel-btn');
            if (reloadBtn) {
                reloadBtn.disabled = true;
                reloadBtn.textContent = '加载中...';
            }

            const response = await fetch('/api/config?format=json');
            const data = await response.json();

            if (data.error) {
                showMessage('configMessage', data.error, 'error');
                return;
            }

            const channels = data.config.push_channel || [];
            const actualIndex = parseInt(channelDiv.dataset.index);
            
            if (actualIndex >= 0 && actualIndex < channels.length) {
                // 重新渲染该通道
                const container = document.getElementById('pushChannelsContainer');
                const newChannelDiv = createPushChannelElement(channels[actualIndex], actualIndex);
                
                // 替换旧的通道元素
                if (channelDiv.parentNode === container) {
                    container.replaceChild(newChannelDiv, channelDiv);
                }
                
                showMessage('configMessage', '通道配置已重新加载', 'success');
            } else {
                showMessage('configMessage', '通道索引无效', 'error');
            }
        } catch (error) {
            showMessage('configMessage', '重新加载通道配置失败: ' + error.message, 'error');
        } finally {
            const reloadBtn = channelDiv.querySelector('.reload-channel-btn');
            if (reloadBtn) {
                reloadBtn.disabled = false;
                reloadBtn.textContent = '重新加载';
            }
        }
    }

    // 保存单个通道配置
    async function saveChannelConfig(channelDiv, index, saveBtn) {
        try {
            saveBtn.disabled = true;
            saveBtn.textContent = '保存中...';

            // 先加载完整配置
            const response = await fetch('/api/config?format=json');
            const data = await response.json();

            if (data.error) {
                showMessage('configMessage', data.error, 'error');
                return;
            }

            const fullConfig = data.config;
            const channels = fullConfig.push_channel || [];
            const actualIndex = parseInt(channelDiv.dataset.index);

            // 收集当前通道的配置
            const channel = {
                name: channelDiv.querySelector('.channel-name').value.trim(),
                enable: channelDiv.querySelector('.channel-enable').checked,
                type: channelDiv.querySelector('.channel-type').value
            };

            const typeInfo = pushChannelTypes[channel.type] || { fields: [] };
            typeInfo.fields.forEach(field => {
                const input = channelDiv.querySelector(`.field-${field}`);
                if (input) {
                    if (input.type === 'checkbox') {
                        channel[field] = input.checked;
                    } else if (field === 'push_target_list') {
                        try {
                            channel[field] = JSON.parse(input.value.trim() || '[]');
                        } catch (e) {
                            channel[field] = [];
                        }
                    } else if (field === 'smtp_port' || field === 'content_type') {
                        const value = input.value.trim();
                        if (value) {
                            channel[field] = field === 'content_type' ? parseInt(value) : parseInt(value);
                        }
                    } else {
                        const value = input.value.trim();
                        if (value) {
                            channel[field] = value;
                        }
                    }
                }
            });

            // 更新通道列表中的对应通道
            if (actualIndex >= 0 && actualIndex < channels.length) {
                channels[actualIndex] = channel;
            } else {
                // 如果索引超出范围，添加到末尾
                channels.push(channel);
            }

            fullConfig.push_channel = channels;

            // 保存配置
            const saveResponse = await fetch('/api/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ config: fullConfig })
            });

            const saveData = await saveResponse.json();

            if (saveData.error) {
                showMessage('configMessage', saveData.error, 'error');
            } else {
                showMessage('configMessage', '通道配置已保存并应用', 'success');
                // 更新原始配置
                if (originalConfig) {
                    originalConfig.push_channel = channels;
                }
            }
        } catch (error) {
            showMessage('configMessage', '保存通道配置失败: ' + error.message, 'error');
        } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = '保存配置';
        }
    }

    // 多账号：添加账号
    const checkinAddAccountBtn = document.getElementById('checkin_add_account_btn');
    if (checkinAddAccountBtn) {
        checkinAddAccountBtn.addEventListener('click', function() {
            const container = document.getElementById('checkin_accounts_list');
            if (!container) return;
            const row = document.createElement('div');
            row.className = 'multi-account-row';
            row.innerHTML = `
                <div class="account-fields">
                    <input type="text" class="form-input checkin-account-email" placeholder="邮箱或用户名">
                    <input type="password" class="form-input checkin-account-password" placeholder="密码">
                </div>
                <button type="button" class="btn btn-secondary row-remove checkin-account-remove">删除</button>
            `;
            container.appendChild(row);
        });
    }
    // 多账号：删除行（事件委托）
    const checkinAccountsList = document.getElementById('checkin_accounts_list');
    if (checkinAccountsList) {
        checkinAccountsList.addEventListener('click', function(e) {
            if (e.target.classList.contains('checkin-account-remove')) {
                const row = e.target.closest('.multi-account-row');
                if (row && checkinAccountsList.querySelectorAll('.multi-account-row').length > 1) row.remove();
            }
        });
    }

    // 多 Cookie：添加 Cookie
    const tiebaAddCookieBtn = document.getElementById('tieba_add_cookie_btn');
    if (tiebaAddCookieBtn) {
        tiebaAddCookieBtn.addEventListener('click', function() {
            const container = document.getElementById('tieba_cookies_list');
            if (!container) return;
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = `
                <div class="cookie-field">
                    <input type="text" class="form-input tieba-cookie-value" placeholder="贴吧 Cookie（须包含 BDUSS）">
                </div>
                <button type="button" class="btn btn-secondary row-remove tieba-cookie-remove">删除</button>
            `;
            container.appendChild(row);
        });
    }
    // 多 Cookie：删除行（事件委托）
    const tiebaCookiesList = document.getElementById('tieba_cookies_list');
    if (tiebaCookiesList) {
        tiebaCookiesList.addEventListener('click', function(e) {
            if (e.target.classList.contains('tieba-cookie-remove')) {
                const row = e.target.closest('.multi-cookie-row');
                if (row && tiebaCookiesList.querySelectorAll('.multi-cookie-row').length > 1) row.remove();
            }
        });
    }

    // 为每个section绑定事件
    document.querySelectorAll('.config-section').forEach(section => {
        const sectionName = section.dataset.section;
        const reloadBtn = section.querySelector('.section-reload-btn');
        const saveBtn = section.querySelector('.section-save-btn');

        if (reloadBtn) {
            reloadBtn.addEventListener('click', () => {
                loadSectionConfigFromServer(sectionName, reloadBtn);
            });
        }

        if (saveBtn) {
            saveBtn.addEventListener('click', () => {
                saveSectionConfig(sectionName, saveBtn);
            });
        }
    });

    // 初始加载配置
    await loadConfig();
});
