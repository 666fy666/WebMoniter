// 配置管理页面JavaScript

let originalConfig = null;
let availablePushChannels = []; // 可用的推送通道列表
let pushChannelTypes = {
    'serverChan_turbo': { name: 'Server酱 Turbo', fields: ['send_key'] },
    'serverChan_3': { name: 'Server酱 3', fields: ['send_key', 'uid', 'tags'] },
    'wecom_apps': { name: '企业微信应用', fields: ['corp_id', 'agent_id', 'corp_secret', 'touser', 'callback_token', 'encoding_aes_key'] },
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
    const weiboChaohuaEnable = document.getElementById('weibo_chaohua_enable');
    const weiboChaohuaEnableLabel = document.getElementById('weibo_chaohua_enable_label');
    const rainyunEnable = document.getElementById('rainyun_enable');
    const rainyunEnableLabel = document.getElementById('rainyun_enable_label');
    const enshanEnable = document.getElementById('enshan_enable');
    const enshanEnableLabel = document.getElementById('enshan_enable_label');
    const tyyunEnable = document.getElementById('tyyun_enable');
    const tyyunEnableLabel = document.getElementById('tyyun_enable_label');
    const aliyunEnable = document.getElementById('aliyun_enable');
    const aliyunEnableLabel = document.getElementById('aliyun_enable_label');
    const smzdmEnable = document.getElementById('smzdm_enable');
    const smzdmEnableLabel = document.getElementById('smzdm_enable_label');
    const zdmDrawEnable = document.getElementById('zdm_draw_enable');
    const zdmDrawEnableLabel = document.getElementById('zdm_draw_enable_label');
    const fgEnable = document.getElementById('fg_enable');
    const fgEnableLabel = document.getElementById('fg_enable_label');
    const miuiEnable = document.getElementById('miui_enable');
    const miuiEnableLabel = document.getElementById('miui_enable_label');
    const iqiyiEnable = document.getElementById('iqiyi_enable');
    const iqiyiEnableLabel = document.getElementById('iqiyi_enable_label');
    const lenovoEnable = document.getElementById('lenovo_enable');
    const lenovoEnableLabel = document.getElementById('lenovo_enable_label');
    const lblyEnable = document.getElementById('lbly_enable');
    const lblyEnableLabel = document.getElementById('lbly_enable_label');
    const pinzanEnable = document.getElementById('pinzan_enable');
    const pinzanEnableLabel = document.getElementById('pinzan_enable_label');
    const dmlEnable = document.getElementById('dml_enable');
    const dmlEnableLabel = document.getElementById('dml_enable_label');
    const xiaomaoEnable = document.getElementById('xiaomao_enable');
    const xiaomaoEnableLabel = document.getElementById('xiaomao_enable_label');
    const ydwxEnable = document.getElementById('ydwx_enable');
    const ydwxEnableLabel = document.getElementById('ydwx_enable_label');
    const xingkongEnable = document.getElementById('xingkong_enable');
    const xingkongEnableLabel = document.getElementById('xingkong_enable_label');
    const qtwEnable = document.getElementById('qtw_enable');
    const qtwEnableLabel = document.getElementById('qtw_enable_label');

    // 监控任务开关
    const weiboEnable = document.getElementById('weibo_enable');
    const weiboEnableLabel = document.getElementById('weibo_enable_label');
    const huyaEnable = document.getElementById('huya_enable');
    const huyaEnableLabel = document.getElementById('huya_enable_label');
    const bilibiliEnable = document.getElementById('bilibili_enable');
    const bilibiliEnableLabel = document.getElementById('bilibili_enable_label');
    const douyinEnable = document.getElementById('douyin_enable');
    const douyinEnableLabel = document.getElementById('douyin_enable_label');
    const douyuEnable = document.getElementById('douyu_enable');
    const douyuEnableLabel = document.getElementById('douyu_enable_label');
    const xhsEnable = document.getElementById('xhs_enable');
    const xhsEnableLabel = document.getElementById('xhs_enable_label');

    // 新增任务开关
    const freenomEnable = document.getElementById('freenom_enable');
    const freenomEnableLabel = document.getElementById('freenom_enable_label');
    const weatherEnable = document.getElementById('weather_enable');
    const weatherEnableLabel = document.getElementById('weather_enable_label');
    const kuakeEnable = document.getElementById('kuake_enable');
    const kuakeEnableLabel = document.getElementById('kuake_enable_label');
    const kjwjEnable = document.getElementById('kjwj_enable');
    const kjwjEnableLabel = document.getElementById('kjwj_enable_label');
    const frEnable = document.getElementById('fr_enable');
    const frEnableLabel = document.getElementById('fr_enable_label');
    const nineEnable = document.getElementById('nine_nine_nine_enable');
    const nineEnableLabel = document.getElementById('nine_nine_nine_enable_label');
    const zgfcEnable = document.getElementById('zgfc_enable');
    const zgfcEnableLabel = document.getElementById('zgfc_enable_label');
    const ssqEnable = document.getElementById('ssq_500w_enable');
    const ssqEnableLabel = document.getElementById('ssq_500w_enable_label');
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

    // 配置卡片折叠/展开功能
    const COLLAPSED_SECTIONS_KEY = 'webmoniter_collapsed_sections';

    // 从 localStorage 加载折叠状态
    function loadCollapsedState() {
        try {
            const saved = localStorage.getItem(COLLAPSED_SECTIONS_KEY);
            return saved ? JSON.parse(saved) : [];
        } catch (e) {
            return [];
        }
    }

    // 保存折叠状态到 localStorage
    function saveCollapsedState(collapsedSections) {
        try {
            localStorage.setItem(COLLAPSED_SECTIONS_KEY, JSON.stringify(collapsedSections));
        } catch (e) {
            console.error('保存折叠状态失败:', e);
        }
    }

    // 切换单个卡片的折叠状态
    function toggleSectionCollapse(section) {
        const sectionName = section.dataset.section;
        const isCollapsed = section.classList.toggle('collapsed');
        
        // 更新 localStorage
        const collapsedSections = loadCollapsedState();
        if (isCollapsed) {
            if (!collapsedSections.includes(sectionName)) {
                collapsedSections.push(sectionName);
            }
        } else {
            const index = collapsedSections.indexOf(sectionName);
            if (index > -1) {
                collapsedSections.splice(index, 1);
            }
        }
        saveCollapsedState(collapsedSections);
    }

    // 初始化折叠状态
    function initCollapsedState() {
        const collapsedSections = loadCollapsedState();
        document.querySelectorAll('.config-section').forEach(section => {
            const sectionName = section.dataset.section;
            if (collapsedSections.includes(sectionName)) {
                section.classList.add('collapsed');
            }
        });
    }

    // 为每个配置卡片的 header 添加点击事件
    document.querySelectorAll('.config-section .card-header').forEach(header => {
        header.addEventListener('click', function(e) {
            // 如果点击的是按钮，则不触发折叠
            if (e.target.closest('.btn') || e.target.closest('.card-actions')) {
                return;
            }
            const section = this.closest('.config-section');
            if (section) {
                toggleSectionCollapse(section);
            }
        });
    });

    // 全部折叠/展开：作用范围为当前模块下可见的卡片（若尚未初始化模块过滤则作用全部）
    function getVisibleSectionsForCollapse() {
        const activeTab = document.querySelector('.config-module-tab.active');
        const currentModule = activeTab ? activeTab.dataset.module : null;
        const sections = document.querySelectorAll('.config-section');
        if (!currentModule) return sections;
        return Array.from(sections).filter(s => s.dataset.module === currentModule && !s.classList.contains('config-card-hidden'));
    }

    // 全部折叠按钮
    const collapseAllBtn = document.getElementById('collapseAllBtn');
    if (collapseAllBtn) {
        collapseAllBtn.addEventListener('click', function() {
            const visibleSections = getVisibleSectionsForCollapse();
            const allSections = document.querySelectorAll('.config-section');
            const collapsedSections = loadCollapsedState();
            visibleSections.forEach(section => {
                section.classList.add('collapsed');
                const name = section.dataset.section;
                if (name && !collapsedSections.includes(name)) collapsedSections.push(name);
            });
            saveCollapsedState(collapsedSections);
        });
    }

    // 全部展开按钮
    const expandAllBtn = document.getElementById('expandAllBtn');
    if (expandAllBtn) {
        expandAllBtn.addEventListener('click', function() {
            const visibleSections = getVisibleSectionsForCollapse();
            const collapsedSections = loadCollapsedState();
            visibleSections.forEach(section => {
                section.classList.remove('collapsed');
                const name = section.dataset.section;
                if (name) {
                    const idx = collapsedSections.indexOf(name);
                    if (idx > -1) collapsedSections.splice(idx, 1);
                }
            });
            saveCollapsedState(collapsedSections);
        });
    }

    // 初始化折叠状态
    initCollapsedState();

    // 配置模块切换与模糊搜索
    const configModuleTabs = document.querySelectorAll('.config-module-tab');
    const configModuleSearch = document.getElementById('configModuleSearch');
    const configSections = document.querySelectorAll('.config-section[data-module]');

    const MODULE_PLACEHOLDERS = {
        monitor: '在监控任务中搜索（如：微博、bilibili、虎牙...）',
        scheduled: '在定时任务中搜索（如：ikuuu、贴吧、签到...）',
        push: '在推送配置中搜索',
        ai: '在 AI 配置中搜索',
        plugins: '在插件中搜索'
    };

    function getCardSearchText(card) {
        const h2 = card.querySelector('.card-header h2');
        const section = card.dataset.section || '';
        const title = h2 ? h2.textContent.trim() : '';
        return `${title} ${section}`.toLowerCase();
    }

    function fuzzyMatch(text, query) {
        if (!query.trim()) return true;
        const q = query.trim().toLowerCase();
        const normalized = text.toLowerCase();
        let qi = 0;
        for (let i = 0; i < normalized.length && qi < q.length; i++) {
            if (normalized[i] === q[qi]) qi++;
        }
        return qi === q.length;
    }

    function applyConfigModuleFilter() {
        const activeTab = document.querySelector('.config-module-tab.active');
        const currentModule = activeTab ? activeTab.dataset.module : 'monitor';
        const searchQuery = configModuleSearch ? configModuleSearch.value : '';

        configSections.forEach(card => {
            const cardModule = card.dataset.module || '';
            const matchesModule = cardModule === currentModule;
            const searchText = getCardSearchText(card);
            const matchesSearch = fuzzyMatch(searchText, searchQuery);

            const hide = !matchesModule || !matchesSearch;
            card.classList.toggle('config-card-hidden', hide);
        });
    }

    function setActiveModule(moduleName) {
        configModuleTabs.forEach(tab => {
            tab.classList.toggle('active', tab.dataset.module === moduleName);
        });
        if (configModuleSearch) {
            configModuleSearch.placeholder = MODULE_PLACEHOLDERS[moduleName] || '搜索...';
            configModuleSearch.value = '';
        }
        applyConfigModuleFilter();
    }

    configModuleTabs.forEach(tab => {
        tab.addEventListener('click', function() {
            setActiveModule(this.dataset.module);
        });
    });

    if (configModuleSearch) {
        configModuleSearch.addEventListener('input', applyConfigModuleFilter);
        configModuleSearch.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                this.value = '';
                applyConfigModuleFilter();
                this.blur();
            }
        });
    }

    setActiveModule('monitor');

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
                document.dispatchEvent(new CustomEvent('config-saved'));
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

    // AI 助手开关事件
    const aiAssistantEnable = document.getElementById('ai_assistant_enable');
    const aiAssistantEnableLabel = document.getElementById('ai_assistant_enable_label');
    if (aiAssistantEnable && aiAssistantEnableLabel) {
        aiAssistantEnable.addEventListener('change', function() {
            aiAssistantEnableLabel.textContent = this.checked ? '开启' : '关闭';
        });
    }

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

    // 微博超话签到开关事件
    if (weiboChaohuaEnable && weiboChaohuaEnableLabel) {
        weiboChaohuaEnable.addEventListener('change', function() {
            weiboChaohuaEnableLabel.textContent = this.checked ? '开启' : '关闭';
        });
    }

    // 雨云签到开关事件
    if (rainyunEnable && rainyunEnableLabel) {
        rainyunEnable.addEventListener('change', function() {
            rainyunEnableLabel.textContent = this.checked ? '开启' : '关闭';
        });
    }
    const rainyunAutoRenew = document.getElementById('rainyun_auto_renew');
    const rainyunAutoRenewLabel = document.getElementById('rainyun_auto_renew_label');
    if (rainyunAutoRenew && rainyunAutoRenewLabel) {
        rainyunAutoRenew.addEventListener('change', function() {
            rainyunAutoRenewLabel.textContent = this.checked ? '开启' : '关闭';
        });
    }
    if (enshanEnable && enshanEnableLabel) {
        enshanEnable.addEventListener('change', function() {
            enshanEnableLabel.textContent = this.checked ? '开启' : '关闭';
        });
    }
    if (tyyunEnable && tyyunEnableLabel) {
        tyyunEnable.addEventListener('change', function() {
            tyyunEnableLabel.textContent = this.checked ? '开启' : '关闭';
        });
    }
    if (aliyunEnable && aliyunEnableLabel) {
        aliyunEnable.addEventListener('change', function() {
            aliyunEnableLabel.textContent = this.checked ? '开启' : '关闭';
        });
    }
    if (smzdmEnable && smzdmEnableLabel) {
        smzdmEnable.addEventListener('change', function() {
            smzdmEnableLabel.textContent = this.checked ? '开启' : '关闭';
        });
    }
    if (zdmDrawEnable && zdmDrawEnableLabel) {
        zdmDrawEnable.addEventListener('change', function() {
            zdmDrawEnableLabel.textContent = this.checked ? '开启' : '关闭';
        });
    }
    if (fgEnable && fgEnableLabel) {
        fgEnable.addEventListener('change', function() {
            fgEnableLabel.textContent = this.checked ? '开启' : '关闭';
        });
    }
    if (miuiEnable && miuiEnableLabel) miuiEnable.addEventListener('change', function() { miuiEnableLabel.textContent = this.checked ? '开启' : '关闭'; });
    if (iqiyiEnable && iqiyiEnableLabel) iqiyiEnable.addEventListener('change', function() { iqiyiEnableLabel.textContent = this.checked ? '开启' : '关闭'; });
    if (lenovoEnable && lenovoEnableLabel) lenovoEnable.addEventListener('change', function() { lenovoEnableLabel.textContent = this.checked ? '开启' : '关闭'; });
    if (lblyEnable && lblyEnableLabel) lblyEnable.addEventListener('change', function() { lblyEnableLabel.textContent = this.checked ? '开启' : '关闭'; });
    if (pinzanEnable && pinzanEnableLabel) pinzanEnable.addEventListener('change', function() { pinzanEnableLabel.textContent = this.checked ? '开启' : '关闭'; });
    if (dmlEnable && dmlEnableLabel) dmlEnable.addEventListener('change', function() { dmlEnableLabel.textContent = this.checked ? '开启' : '关闭'; });
    if (xiaomaoEnable && xiaomaoEnableLabel) xiaomaoEnable.addEventListener('change', function() { xiaomaoEnableLabel.textContent = this.checked ? '开启' : '关闭'; });
    if (ydwxEnable && ydwxEnableLabel) ydwxEnable.addEventListener('change', function() { ydwxEnableLabel.textContent = this.checked ? '开启' : '关闭'; });
    if (xingkongEnable && xingkongEnableLabel) xingkongEnable.addEventListener('change', function() { xingkongEnableLabel.textContent = this.checked ? '开启' : '关闭'; });
    if (qtwEnable && qtwEnableLabel) qtwEnable.addEventListener('change', function() { qtwEnableLabel.textContent = this.checked ? '开启' : '关闭'; });

    // 监控任务开关事件
    if (weiboEnable && weiboEnableLabel) weiboEnable.addEventListener('change', function() { weiboEnableLabel.textContent = this.checked ? '开启' : '关闭'; });
    const weiboCompressLlmEl = document.getElementById('weibo_compress_with_llm');
    const weiboCompressLlmLabelEl = document.getElementById('weibo_compress_with_llm_label');
    if (weiboCompressLlmEl && weiboCompressLlmLabelEl) weiboCompressLlmEl.addEventListener('change', function() { weiboCompressLlmLabelEl.textContent = this.checked ? '开启' : '关闭'; });
    if (huyaEnable && huyaEnableLabel) huyaEnable.addEventListener('change', function() { huyaEnableLabel.textContent = this.checked ? '开启' : '关闭'; });
    if (bilibiliEnable && bilibiliEnableLabel) bilibiliEnable.addEventListener('change', function() { bilibiliEnableLabel.textContent = this.checked ? '开启' : '关闭'; });
    if (douyinEnable && douyinEnableLabel) douyinEnable.addEventListener('change', function() { douyinEnableLabel.textContent = this.checked ? '开启' : '关闭'; });
    if (douyuEnable && douyuEnableLabel) douyuEnable.addEventListener('change', function() { douyuEnableLabel.textContent = this.checked ? '开启' : '关闭'; });
    if (xhsEnable && xhsEnableLabel) xhsEnable.addEventListener('change', function() { xhsEnableLabel.textContent = this.checked ? '开启' : '关闭'; });

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

            // 填充所有配置（微博监控与超话放前）
            loadSectionConfig('weibo', config);
            loadSectionConfig('weibo_chaohua', config);
            loadSectionConfig('huya', config);
            loadSectionConfig('bilibili', config);
            loadSectionConfig('douyin', config);
            loadSectionConfig('douyu', config);
            loadSectionConfig('xhs', config);
            loadSectionConfig('checkin', config);
            loadSectionConfig('rainyun', config);
            loadSectionConfig('tieba', config);
            loadSectionConfig('enshan', config);
            loadSectionConfig('tyyun', config);
            loadSectionConfig('aliyun', config);
            loadSectionConfig('smzdm', config);
            loadSectionConfig('zdm_draw', config);
            loadSectionConfig('fg', config);
            loadSectionConfig('miui', config);
            loadSectionConfig('iqiyi', config);
            loadSectionConfig('lenovo', config);
            loadSectionConfig('lbly', config);
            loadSectionConfig('pinzan', config);
            loadSectionConfig('dml', config);
            loadSectionConfig('xiaomao', config);
            loadSectionConfig('ydwx', config);
            loadSectionConfig('xingkong', config);
            loadSectionConfig('qtw', config);
            loadSectionConfig('freenom', config);
            loadSectionConfig('weather', config);
            loadSectionConfig('kuake', config);
            loadSectionConfig('kjwj', config);
            loadSectionConfig('fr', config);
            loadSectionConfig('nine_nine_nine', config);
            loadSectionConfig('zgfc', config);
            loadSectionConfig('ssq_500w', config);
            loadSectionConfig('log_cleanup', config);
            loadSectionConfig('app', config);
            loadSectionConfig('quiet_hours', config);
            loadSectionConfig('ai_assistant', config);
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

        // 更新可用推送通道列表
        availablePushChannels = channels.map(ch => ({
            name: ch.name || '',
            type: ch.type || ''
        })).filter(ch => ch.name);

        if (channels.length === 0) {
            container.innerHTML = '<p style="color: #7f8c8d; text-align: center; padding: 20px;">暂无推送通道</p>';
            return;
        }

        channels.forEach((channel, index) => {
            const channelDiv = createPushChannelElement(channel, index);
            container.appendChild(channelDiv);
        });

        // 渲染所有任务的推送通道选择
        renderAllTaskPushChannelSelects();
    }

    // 渲染任务推送通道选择
    function renderTaskPushChannelSelect(containerId, selectedChannels) {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = '';
        
        if (availablePushChannels.length === 0) {
            container.innerHTML = '<span class="no-channels">暂无可用推送通道，请先配置推送通道</span>';
            return;
        }

        const selected = Array.isArray(selectedChannels) ? selectedChannels : [];
        
        availablePushChannels.forEach(channel => {
            const label = document.createElement('label');
            label.className = 'push-channel-checkbox' + (selected.includes(channel.name) ? ' selected' : '');
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = channel.name;
            checkbox.checked = selected.includes(channel.name);
            checkbox.addEventListener('change', function() {
                label.classList.toggle('selected', this.checked);
            });
            
            const nameSpan = document.createElement('span');
            nameSpan.className = 'channel-name';
            nameSpan.textContent = channel.name;
            
            label.appendChild(checkbox);
            label.appendChild(nameSpan);
            container.appendChild(label);
        });
    }

    // 获取任务选择的推送通道
    function getTaskPushChannels(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return [];
        
        const channels = [];
        container.querySelectorAll('input[type="checkbox"]:checked').forEach(checkbox => {
            if (checkbox.value) {
                channels.push(checkbox.value);
            }
        });
        return channels;
    }

    // 渲染所有任务的推送通道选择
    function renderAllTaskPushChannelSelects() {
        const taskPushChannelConfigs = {
            'weibo_push_channels': originalConfig?.weibo?.push_channels || [],
            'weibo_chaohua_push_channels': originalConfig?.weibo_chaohua?.push_channels || [],
            'huya_push_channels': originalConfig?.huya?.push_channels || [],
            'bilibili_push_channels': originalConfig?.bilibili?.push_channels || [],
            'douyin_push_channels': originalConfig?.douyin?.push_channels || [],
            'douyu_push_channels': originalConfig?.douyu?.push_channels || [],
            'xhs_push_channels': originalConfig?.xhs?.push_channels || [],
            'checkin_push_channels': originalConfig?.checkin?.push_channels || [],
            'rainyun_push_channels': originalConfig?.rainyun?.push_channels || [],
            'tieba_push_channels': originalConfig?.tieba?.push_channels || [],
            'enshan_push_channels': originalConfig?.enshan?.push_channels || [],
            'tyyun_push_channels': originalConfig?.tyyun?.push_channels || [],
            'aliyun_push_channels': originalConfig?.aliyun?.push_channels || [],
            'smzdm_push_channels': originalConfig?.smzdm?.push_channels || [],
            'zdm_draw_push_channels': originalConfig?.zdm_draw?.push_channels || [],
            'fg_push_channels': originalConfig?.fg?.push_channels || [],
            'miui_push_channels': originalConfig?.miui?.push_channels || [],
            'iqiyi_push_channels': originalConfig?.iqiyi?.push_channels || [],
            'lenovo_push_channels': originalConfig?.lenovo?.push_channels || [],
            'lbly_push_channels': originalConfig?.lbly?.push_channels || [],
            'pinzan_push_channels': originalConfig?.pinzan?.push_channels || [],
            'dml_push_channels': originalConfig?.dml?.push_channels || [],
            'xiaomao_push_channels': originalConfig?.xiaomao?.push_channels || [],
            'ydwx_push_channels': originalConfig?.ydwx?.push_channels || [],
            'xingkong_push_channels': originalConfig?.xingkong?.push_channels || [],
            'qtw_push_channels': originalConfig?.qtw?.push_channels || [],
            'freenom_push_channels': originalConfig?.freenom?.push_channels || [],
            'weather_push_channels': originalConfig?.weather?.push_channels || [],
            'kuake_push_channels': originalConfig?.kuake?.push_channels || [],
            'kjwj_push_channels': originalConfig?.kjwj?.push_channels || [],
            'fr_push_channels': originalConfig?.fr?.push_channels || [],
            'nine_nine_nine_push_channels': originalConfig?.nine_nine_nine?.push_channels || [],
            'zgfc_push_channels': originalConfig?.zgfc?.push_channels || [],
            'ssq_500w_push_channels': originalConfig?.ssq_500w?.push_channels || []
        };

        Object.keys(taskPushChannelConfigs).forEach(containerId => {
            renderTaskPushChannelSelect(containerId, taskPushChannelConfigs[containerId]);
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

    function renderEnshanCookies(cookies) {
        const container = document.getElementById('enshan_cookies_list');
        if (!container) return;
        container.innerHTML = '';
        const list = cookies.length ? cookies : [''];
        list.forEach((cookie, index) => {
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.dataset.index = index;
            row.innerHTML = `
                <div class="cookie-field">
                    <input type="text" class="form-input enshan-cookie-value" placeholder="恩山 Cookie">
                </div>
                <button type="button" class="btn btn-secondary row-remove enshan-cookie-remove">删除</button>
            `;
            row.querySelector('.enshan-cookie-value').value = cookie || '';
            container.appendChild(row);
        });
    }

    function renderTyyunAccounts(accounts) {
        const container = document.getElementById('tyyun_accounts_list');
        if (!container) return;
        container.innerHTML = '';
        const list = accounts.length ? accounts : [{ username: '', password: '' }];
        list.forEach((acc, index) => {
            const row = document.createElement('div');
            row.className = 'multi-account-row';
            row.dataset.index = index;
            row.innerHTML = `
                <div class="account-fields">
                    <input type="text" class="form-input tyyun-account-username" placeholder="手机号">
                    <input type="password" class="form-input tyyun-account-password" placeholder="密码">
                </div>
                <button type="button" class="btn btn-secondary row-remove tyyun-account-remove">删除</button>
            `;
            row.querySelector('.tyyun-account-username').value = acc.username || '';
            row.querySelector('.tyyun-account-password').value = acc.password || '';
            container.appendChild(row);
        });
    }

    function renderAliyunTokens(tokens) {
        const container = document.getElementById('aliyun_refresh_tokens_list');
        if (!container) return;
        container.innerHTML = '';
        const list = tokens.length ? tokens : [''];
        list.forEach((token, index) => {
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.dataset.index = index;
            row.innerHTML = `
                <div class="cookie-field">
                    <input type="password" class="form-input aliyun-token-value" placeholder="refresh_token">
                </div>
                <button type="button" class="btn btn-secondary row-remove aliyun-token-remove">删除</button>
            `;
            row.querySelector('.aliyun-token-value').value = token || '';
            container.appendChild(row);
        });
    }

    function renderSmzdmCookies(cookies) {
        const container = document.getElementById('smzdm_cookies_list');
        if (!container) return;
        container.innerHTML = '';
        const list = cookies.length ? cookies : [''];
        list.forEach((cookie, index) => {
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.dataset.index = index;
            row.innerHTML = `
                <div class="cookie-field">
                    <input type="text" class="form-input smzdm-cookie-value" placeholder="值得买 Cookie">
                </div>
                <button type="button" class="btn btn-secondary row-remove smzdm-cookie-remove">删除</button>
            `;
            row.querySelector('.smzdm-cookie-value').value = cookie || '';
            container.appendChild(row);
        });
    }

    function renderZdmDrawCookies(cookies) {
        const container = document.getElementById('zdm_draw_cookies_list');
        if (!container) return;
        container.innerHTML = '';
        const list = cookies.length ? cookies : [''];
        list.forEach((cookie, index) => {
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.dataset.index = index;
            row.innerHTML = `
                <div class="cookie-field">
                    <input type="text" class="form-input zdm-draw-cookie-value" placeholder="值得买 Cookie">
                </div>
                <button type="button" class="btn btn-secondary row-remove zdm-draw-cookie-remove">删除</button>
            `;
            row.querySelector('.zdm-draw-cookie-value').value = cookie || '';
            container.appendChild(row);
        });
    }

    function renderFgCookies(cookies) {
        const container = document.getElementById('fg_cookies_list');
        if (!container) return;
        container.innerHTML = '';
        const list = cookies.length ? cookies : [''];
        list.forEach((cookie, index) => {
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.dataset.index = index;
            row.innerHTML = `
                <div class="cookie-field">
                    <input type="text" class="form-input fg-cookie-value" placeholder="富贵论坛 Cookie">
                </div>
                <button type="button" class="btn btn-secondary row-remove fg-cookie-remove">删除</button>
            `;
            row.querySelector('.fg-cookie-value').value = cookie || '';
            container.appendChild(row);
        });
    }

    function renderMiuiAccounts(accounts) {
        const container = document.getElementById('miui_accounts_list');
        if (!container) return;
        container.innerHTML = '';
        const list = accounts.length ? accounts : [{ account: '', password: '' }];
        list.forEach((acc, index) => {
            const row = document.createElement('div');
            row.className = 'multi-account-row';
            row.dataset.index = index;
            row.innerHTML = '<div class="account-fields"><input type="text" class="form-input miui-account-value" placeholder="手机号"><input type="password" class="form-input miui-password-value" placeholder="密码"></div><button type="button" class="btn btn-secondary row-remove miui-account-remove">删除</button>';
            row.querySelector('.miui-account-value').value = acc.account || '';
            row.querySelector('.miui-password-value').value = acc.password || '';
            container.appendChild(row);
        });
    }
    function renderIqiyiCookies(cookies) {
        const container = document.getElementById('iqiyi_cookies_list');
        if (!container) return;
        container.innerHTML = '';
        const list = cookies.length ? cookies : [''];
        list.forEach((c, i) => {
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><input type="text" class="form-input iqiyi-cookie-value" placeholder="爱奇艺 Cookie"></div><button type="button" class="btn btn-secondary row-remove iqiyi-cookie-remove">删除</button>';
            row.querySelector('.iqiyi-cookie-value').value = c || '';
            container.appendChild(row);
        });
    }
    function renderLenovoTokens(tokens) {
        const container = document.getElementById('lenovo_access_tokens_list');
        if (!container) return;
        container.innerHTML = '';
        const list = tokens.length ? tokens : [''];
        list.forEach((t, i) => {
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><input type="text" class="form-input lenovo-token-value" placeholder="access_token"></div><button type="button" class="btn btn-secondary row-remove lenovo-token-remove">删除</button>';
            row.querySelector('.lenovo-token-value').value = t || '';
            container.appendChild(row);
        });
    }
    function renderLblyBodies(bodies) {
        const container = document.getElementById('lbly_request_bodies_list');
        if (!container) return;
        container.innerHTML = '';
        const list = bodies.length ? bodies : [''];
        list.forEach((b, i) => {
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><textarea class="form-input lbly-body-value" rows="2" placeholder="请求体 JSON"></textarea></div><button type="button" class="btn btn-secondary row-remove lbly-body-remove">删除</button>';
            row.querySelector('.lbly-body-value').value = b || '';
            container.appendChild(row);
        });
    }
    function renderPinzanAccounts(accounts) {
        const container = document.getElementById('pinzan_accounts_list');
        if (!container) return;
        container.innerHTML = '';
        const list = accounts.length ? accounts : [{ account: '', password: '' }];
        list.forEach((acc, i) => {
            const row = document.createElement('div');
            row.className = 'multi-account-row';
            row.innerHTML = '<div class="account-fields"><input type="text" class="form-input pinzan-account-value" placeholder="账号"><input type="password" class="form-input pinzan-password-value" placeholder="密码"></div><button type="button" class="btn btn-secondary row-remove pinzan-account-remove">删除</button>';
            row.querySelector('.pinzan-account-value').value = acc.account || '';
            row.querySelector('.pinzan-password-value').value = acc.password || '';
            container.appendChild(row);
        });
    }
    function renderDmlOpenids(openids) {
        const container = document.getElementById('dml_openids_list');
        if (!container) return;
        container.innerHTML = '';
        const list = openids.length ? openids : [''];
        list.forEach((o, i) => {
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><input type="text" class="form-input dml-openid-value" placeholder="openid"></div><button type="button" class="btn btn-secondary row-remove dml-openid-remove">删除</button>';
            row.querySelector('.dml-openid-value').value = o || '';
            container.appendChild(row);
        });
    }
    function renderXiaomaoTokens(tokens) {
        const container = document.getElementById('xiaomao_tokens_list');
        if (!container) return;
        container.innerHTML = '';
        const list = tokens.length ? tokens : [''];
        list.forEach((t) => {
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><input type="text" class="form-input xiaomao-token-value" placeholder="省份,城市,经度,纬度,设备id,token,MT-Token-Wap"></div><button type="button" class="btn btn-secondary row-remove xiaomao-token-remove">删除</button>';
            row.querySelector('.xiaomao-token-value').value = t || '';
            container.appendChild(row);
        });
    }
    function renderYdwxAccounts(accounts) {
        const container = document.getElementById('ydwx_accounts_list');
        if (!container) return;
        container.innerHTML = '';
        const list = accounts.length ? accounts : [{ device_params: '', token: '' }];
        list.forEach((a) => {
            const row = document.createElement('div');
            row.className = 'multi-account-row';
            row.innerHTML = '<div class="account-fields"><input type="text" class="form-input ydwx-dp-value" placeholder="deviceParams"><input type="text" class="form-input ydwx-token-value" placeholder="token"></div><button type="button" class="btn btn-secondary row-remove ydwx-account-remove">删除</button>';
            row.querySelector('.ydwx-dp-value').value = a.device_params || '';
            row.querySelector('.ydwx-token-value').value = a.token || '';
            container.appendChild(row);
        });
    }
    function renderXingkongAccounts(accounts) {
        const container = document.getElementById('xingkong_accounts_list');
        if (!container) return;
        container.innerHTML = '';
        const list = accounts.length ? accounts : [{ username: '', password: '' }];
        list.forEach((a) => {
            const row = document.createElement('div');
            row.className = 'multi-account-row';
            row.innerHTML = '<div class="account-fields"><input type="text" class="form-input xingkong-user-value" placeholder="用户名"><input type="password" class="form-input xingkong-pwd-value" placeholder="密码"></div><button type="button" class="btn btn-secondary row-remove xingkong-account-remove">删除</button>';
            row.querySelector('.xingkong-user-value').value = a.username || '';
            row.querySelector('.xingkong-pwd-value').value = a.password || '';
            container.appendChild(row);
        });
    }
    function renderQtwCookies(cookies) {
        const container = document.getElementById('qtw_cookies_list');
        if (!container) return;
        container.innerHTML = '';
        const list = cookies.length ? cookies : [''];
        list.forEach((c) => {
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><input type="text" class="form-input qtw-cookie-value" placeholder="千图网 Cookie"></div><button type="button" class="btn btn-secondary row-remove qtw-cookie-remove">删除</button>';
            row.querySelector('.qtw-cookie-value').value = c || '';
            container.appendChild(row);
        });
    }

    // Freenom 多账号
    function renderFreenomAccounts(accounts) {
        const container = document.getElementById('freenom_accounts_list');
        if (!container) return;
        container.innerHTML = '';
        const list = accounts.length ? accounts : [{ email: '', password: '' }];
        list.forEach((acc) => {
            const row = document.createElement('div');
            row.className = 'multi-account-row';
            row.innerHTML = '<div class="account-fields"><input type="text" class="form-input freenom-account-email" placeholder="邮箱"><input type="password" class="form-input freenom-account-password" placeholder="密码"></div><button type="button" class="btn btn-secondary row-remove freenom-account-remove">删除</button>';
            row.querySelector('.freenom-account-email').value = acc.email || '';
            row.querySelector('.freenom-account-password').value = acc.password || '';
            container.appendChild(row);
        });
    }

    // 夸克 Cookie 列表
    function renderKuakeCookies(cookies) {
        const container = document.getElementById('kuake_cookies_list');
        if (!container) return;
        container.innerHTML = '';
        const list = cookies.length ? cookies : [''];
        list.forEach((c) => {
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><input type="text" class="form-input kuake-cookie-value" placeholder="夸克 Cookie"></div><button type="button" class="btn btn-secondary row-remove kuake-cookie-remove">删除</button>';
            row.querySelector('.kuake-cookie-value').value = c || '';
            container.appendChild(row);
        });
    }

    // 科技玩家多账号
    function renderKjwjAccounts(accounts) {
        const container = document.getElementById('kjwj_accounts_list');
        if (!container) return;
        container.innerHTML = '';
        const list = accounts.length ? accounts : [{ username: '', password: '' }];
        list.forEach((acc) => {
            const row = document.createElement('div');
            row.className = 'multi-account-row';
            row.innerHTML = '<div class="account-fields"><input type="text" class="form-input kjwj-account-username" placeholder="用户名/邮箱"><input type="password" class="form-input kjwj-account-password" placeholder="密码"></div><button type="button" class="btn btn-secondary row-remove kjwj-account-remove">删除</button>';
            row.querySelector('.kjwj-account-username').value = acc.username || '';
            row.querySelector('.kjwj-account-password').value = acc.password || '';
            container.appendChild(row);
        });
    }

    // 999 tokens
    function renderNineTokens(tokens) {
        const container = document.getElementById('nine_nine_nine_tokens_list');
        if (!container) return;
        container.innerHTML = '';
        const list = tokens.length ? tokens : [''];
        list.forEach((t) => {
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><input type="text" class="form-input nine-token-value" placeholder="Authorization"></div><button type="button" class="btn btn-secondary row-remove nine-token-remove">删除</button>';
            row.querySelector('.nine-token-value').value = t || '';
            container.appendChild(row);
        });
    }

    // 福彩 tokens
    function renderZgfcTokens(tokens) {
        const container = document.getElementById('zgfc_tokens_list');
        if (!container) return;
        container.innerHTML = '';
        const list = tokens.length ? tokens : [''];
        list.forEach((t) => {
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><input type="text" class="form-input zgfc-token-value" placeholder="Authorization"></div><button type="button" class="btn btn-secondary row-remove zgfc-token-remove">删除</button>';
            row.querySelector('.zgfc-token-value').value = t || '';
            container.appendChild(row);
        });
    }

    function renderWeiboChaohuaCookies(cookies) {
        const container = document.getElementById('weibo_chaohua_cookies_list');
        if (!container) return;
        container.innerHTML = '';
        const list = cookies.length ? cookies : [''];
        list.forEach((cookie, index) => {
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.dataset.index = index;
            row.innerHTML = `
                <div class="cookie-field">
                    <input type="text" class="form-input weibo-chaohua-cookie-value" placeholder="微博 Cookie（须包含 XSRF-TOKEN）">
                </div>
                <button type="button" class="btn btn-secondary row-remove weibo-chaohua-cookie-remove">删除</button>
            `;
            row.querySelector('.weibo-chaohua-cookie-value').value = cookie || '';
            container.appendChild(row);
        });
    }

    // 渲染雨云多账号列表（username, password, api_key）
    function renderRainyunAccounts(accounts) {
        const container = document.getElementById('rainyun_accounts_list');
        if (!container) return;
        container.innerHTML = '';
        const list = accounts.length ? accounts : [{ username: '', password: '', api_key: '' }];
        list.forEach((acc, index) => {
            const row = document.createElement('div');
            row.className = 'multi-account-row';
            row.dataset.index = index;
            row.innerHTML = `
                <div class="account-fields">
                    <input type="text" class="form-input rainyun-account-username" placeholder="用户名">
                    <input type="password" class="form-input rainyun-account-password" placeholder="密码">
                    <input type="password" class="form-input rainyun-account-api-key" placeholder="API Key（续费用，可选）">
                </div>
                <button type="button" class="btn btn-secondary row-remove rainyun-account-remove">删除</button>
            `;
            row.querySelector('.rainyun-account-username').value = acc.username || '';
            row.querySelector('.rainyun-account-password').value = acc.password || '';
            row.querySelector('.rainyun-account-api-key').value = acc.api_key || '';
            container.appendChild(row);
        });
    }

    // 加载特定section的配置
    function loadSectionConfig(section, config) {
        switch(section) {
            case 'app':
                if (config.app) {
                    const input = document.getElementById('app_base_url');
                    if (input) {
                        input.value = config.app.base_url || '';
                    }
                }
                break;
            case 'weibo':
                if (config.weibo) {
                    if (weiboEnable) {
                        const enableVal = config.weibo.enable;
                        weiboEnable.checked = enableVal !== false && enableVal !== 'false';
                        if (weiboEnableLabel) weiboEnableLabel.textContent = weiboEnable.checked ? '开启' : '关闭';
                    }
                    document.getElementById('weibo_cookie').value = config.weibo.cookie || '';
                    document.getElementById('weibo_uids').value = typeof config.weibo.uids === 'string' 
                        ? config.weibo.uids 
                        : (Array.isArray(config.weibo.uids) ? config.weibo.uids.join(',') : '');
                    document.getElementById('weibo_concurrency').value = config.weibo.concurrency || 3;
                    const intervalInput = document.getElementById('weibo_monitor_interval_seconds');
                    if (intervalInput) {
                        const val = config.weibo.monitor_interval_seconds || 300;
                        intervalInput.value = val;
                    }
                    // 渲染推送通道选择
                    renderTaskPushChannelSelect('weibo_push_channels', config.weibo.push_channels || []);
                    const weiboCompressLlm = document.getElementById('weibo_compress_with_llm');
                    const weiboCompressLlmLabel = document.getElementById('weibo_compress_with_llm_label');
                    if (weiboCompressLlm) {
                        const cv = config.weibo.compress_with_llm;
                        weiboCompressLlm.checked = cv === true || cv === 'true';
                        if (weiboCompressLlmLabel) weiboCompressLlmLabel.textContent = weiboCompressLlm.checked ? '开启' : '关闭';
                    }
                }
                break;
            case 'checkin':
                if (config.checkin) {
                    if (checkinEnable) {
                        const enableVal = config.checkin.enable;
                        checkinEnable.checked = enableVal === true || enableVal === 'true';
                        if (checkinEnableLabel) {
                            checkinEnableLabel.textContent = checkinEnable.checked ? '开启' : '关闭';
                        }
                    }
                    const emailInput = document.getElementById('checkin_email');
                    const passwordInput = document.getElementById('checkin_password');
                    const timeInput = document.getElementById('checkin_time');

                    if (emailInput) emailInput.value = config.checkin.email || '';
                    if (passwordInput) passwordInput.value = config.checkin.password || '';
                    if (timeInput) {
                        const timeVal = config.checkin.time || '08:00';
                        timeInput.value = timeVal.length === 5 ? timeVal : '08:00';
                    }
                    // 多账号列表：仅当配置中明确有多条 accounts 时显示；单账号时只填单账号输入框，多账号区显示空行
                    const accountsListEl = document.getElementById('checkin_accounts_list');
                    if (accountsListEl) {
                        const accounts = Array.isArray(config.checkin.accounts) && config.checkin.accounts.length > 0
                            ? config.checkin.accounts
                            : [{ email: '', password: '' }];
                        renderCheckinAccounts(accounts);
                    }
                    // 渲染推送通道选择
                    renderTaskPushChannelSelect('checkin_push_channels', config.checkin.push_channels || []);
                }
                break;
            case 'tieba':
                if (config.tieba) {
                    if (tiebaEnable) {
                        const enableVal = config.tieba.enable;
                        tiebaEnable.checked = enableVal === true || enableVal === 'true';
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
                    // 多 Cookie 列表：仅当配置中明确有多条 cookies 时显示；单条时只填单条输入框，多 Cookie 区显示空行
                    const cookiesListEl = document.getElementById('tieba_cookies_list');
                    if (cookiesListEl) {
                        const cookies = Array.isArray(config.tieba.cookies) && config.tieba.cookies.length > 0
                            ? config.tieba.cookies
                            : [''];
                        renderTiebaCookies(cookies);
                    }
                    // 渲染推送通道选择
                    renderTaskPushChannelSelect('tieba_push_channels', config.tieba.push_channels || []);
                }
                break;
            case 'weibo_chaohua':
                if (config.weibo_chaohua) {
                    if (weiboChaohuaEnable) {
                        const enableVal = config.weibo_chaohua.enable;
                        weiboChaohuaEnable.checked = enableVal === true || enableVal === 'true';
                        if (weiboChaohuaEnableLabel) {
                            weiboChaohuaEnableLabel.textContent = weiboChaohuaEnable.checked ? '开启' : '关闭';
                        }
                    }
                    const weiboChaohuaCookieInput = document.getElementById('weibo_chaohua_cookie');
                    const weiboChaohuaTimeInput = document.getElementById('weibo_chaohua_time');
                    if (weiboChaohuaCookieInput) weiboChaohuaCookieInput.value = config.weibo_chaohua.cookie || '';
                    if (weiboChaohuaTimeInput) {
                        const timeVal = config.weibo_chaohua.time || '23:45';
                        weiboChaohuaTimeInput.value = timeVal.length === 5 ? timeVal : '23:45';
                    }
                    // 多 Cookie 列表：仅当配置中明确有多条 cookies 时显示；单条时只填单条输入框，多 Cookie 区显示空行
                    const cookiesListEl = document.getElementById('weibo_chaohua_cookies_list');
                    if (cookiesListEl) {
                        const cookies = Array.isArray(config.weibo_chaohua.cookies) && config.weibo_chaohua.cookies.length > 0
                            ? config.weibo_chaohua.cookies
                            : [''];
                        renderWeiboChaohuaCookies(cookies);
                    }
                    // 渲染推送通道选择
                    renderTaskPushChannelSelect('weibo_chaohua_push_channels', config.weibo_chaohua.push_channels || []);
                }
                break;
            case 'huya':
                if (config.huya) {
                    if (huyaEnable) {
                        const enableVal = config.huya.enable;
                        huyaEnable.checked = enableVal !== false && enableVal !== 'false';
                        if (huyaEnableLabel) huyaEnableLabel.textContent = huyaEnable.checked ? '开启' : '关闭';
                    }
                    document.getElementById('huya_rooms').value = typeof config.huya.rooms === 'string' 
                        ? config.huya.rooms 
                        : (Array.isArray(config.huya.rooms) ? config.huya.rooms.join(',') : '');
                    document.getElementById('huya_concurrency').value = config.huya.concurrency || 7;
                    const intervalInput = document.getElementById('huya_monitor_interval_seconds');
                    if (intervalInput) {
                        const val = config.huya.monitor_interval_seconds || 65;
                        intervalInput.value = val;
                    }
                    renderTaskPushChannelSelect('huya_push_channels', config.huya.push_channels || []);
                }
                break;
            case 'bilibili':
                if (config.bilibili) {
                    if (bilibiliEnable) {
                        const enableVal = config.bilibili.enable;
                        bilibiliEnable.checked = enableVal !== false && enableVal !== 'false';
                        if (bilibiliEnableLabel) bilibiliEnableLabel.textContent = bilibiliEnable.checked ? '开启' : '关闭';
                    }
                    document.getElementById('bilibili_cookie').value = config.bilibili.cookie || '';
                    document.getElementById('bilibili_uids').value = typeof config.bilibili.uids === 'string' 
                        ? config.bilibili.uids 
                        : (Array.isArray(config.bilibili.uids) ? config.bilibili.uids.join(',') : '');
                    const skipEl = document.getElementById('bilibili_skip_forward');
                    if (skipEl) skipEl.checked = config.bilibili.skip_forward !== false;
                    document.getElementById('bilibili_concurrency').value = config.bilibili.concurrency || 2;
                    const blInterval = document.getElementById('bilibili_monitor_interval_seconds');
                    if (blInterval) blInterval.value = config.bilibili.monitor_interval_seconds || 60;
                    renderTaskPushChannelSelect('bilibili_push_channels', config.bilibili.push_channels || []);
                }
                break;
            case 'douyin':
                if (config.douyin) {
                    if (douyinEnable) {
                        const enableVal = config.douyin.enable;
                        douyinEnable.checked = enableVal !== false && enableVal !== 'false';
                        if (douyinEnableLabel) douyinEnableLabel.textContent = douyinEnable.checked ? '开启' : '关闭';
                    }
                    document.getElementById('douyin_douyin_ids').value = typeof config.douyin.douyin_ids === 'string' 
                        ? config.douyin.douyin_ids 
                        : (Array.isArray(config.douyin.douyin_ids) ? config.douyin.douyin_ids.join(',') : '');
                    document.getElementById('douyin_concurrency').value = config.douyin.concurrency || 2;
                    const dyInterval = document.getElementById('douyin_monitor_interval_seconds');
                    if (dyInterval) dyInterval.value = config.douyin.monitor_interval_seconds || 30;
                    renderTaskPushChannelSelect('douyin_push_channels', config.douyin.push_channels || []);
                }
                break;
            case 'douyu':
                if (config.douyu) {
                    if (douyuEnable) {
                        const enableVal = config.douyu.enable;
                        douyuEnable.checked = enableVal !== false && enableVal !== 'false';
                        if (douyuEnableLabel) douyuEnableLabel.textContent = douyuEnable.checked ? '开启' : '关闭';
                    }
                    document.getElementById('douyu_rooms').value = typeof config.douyu.rooms === 'string' 
                        ? config.douyu.rooms 
                        : (Array.isArray(config.douyu.rooms) ? config.douyu.rooms.join(',') : '');
                    document.getElementById('douyu_concurrency').value = config.douyu.concurrency || 2;
                    const dyuInterval = document.getElementById('douyu_monitor_interval_seconds');
                    if (dyuInterval) dyuInterval.value = config.douyu.monitor_interval_seconds || 300;
                    renderTaskPushChannelSelect('douyu_push_channels', config.douyu.push_channels || []);
                }
                break;
            case 'xhs':
                if (config.xhs) {
                    if (xhsEnable) {
                        const enableVal = config.xhs.enable;
                        xhsEnable.checked = enableVal !== false && enableVal !== 'false';
                        if (xhsEnableLabel) xhsEnableLabel.textContent = xhsEnable.checked ? '开启' : '关闭';
                    }
                    document.getElementById('xhs_cookie').value = config.xhs.cookie || '';
                    document.getElementById('xhs_profile_ids').value = typeof config.xhs.profile_ids === 'string' 
                        ? config.xhs.profile_ids 
                        : (Array.isArray(config.xhs.profile_ids) ? config.xhs.profile_ids.join(',') : '');
                    document.getElementById('xhs_concurrency').value = config.xhs.concurrency || 2;
                    const xhsInterval = document.getElementById('xhs_monitor_interval_seconds');
                    if (xhsInterval) xhsInterval.value = config.xhs.monitor_interval_seconds || 300;
                    renderTaskPushChannelSelect('xhs_push_channels', config.xhs.push_channels || []);
                }
                break;
            case 'rainyun':
                if (config.rainyun) {
                    if (rainyunEnable) {
                        const enableVal = config.rainyun.enable;
                        rainyunEnable.checked = enableVal === true || enableVal === 'true';
                        if (rainyunEnableLabel) {
                            rainyunEnableLabel.textContent = rainyunEnable.checked ? '开启' : '关闭';
                        }
                    }
                    const timeInput = document.getElementById('rainyun_time');
                    if (timeInput) {
                        const timeVal = config.rainyun.time || '08:30';
                        timeInput.value = timeVal.length === 5 ? timeVal : '08:30';
                    }
                    // 多账号列表
                    const rainyunAccountsListEl = document.getElementById('rainyun_accounts_list');
                    if (rainyunAccountsListEl) {
                        const accounts = Array.isArray(config.rainyun.accounts) && config.rainyun.accounts.length > 0
                            ? config.rainyun.accounts
                            : [{ username: '', password: '', api_key: '' }];
                        renderRainyunAccounts(accounts);
                    }
                    // 渲染推送通道选择
                    renderTaskPushChannelSelect('rainyun_push_channels', config.rainyun.push_channels || []);
                    // 自动续费配置
                    const rainyunAutoRenewEl = document.getElementById('rainyun_auto_renew');
                    const rainyunAutoRenewLabelEl = document.getElementById('rainyun_auto_renew_label');
                    if (rainyunAutoRenewEl) {
                        rainyunAutoRenewEl.checked = config.rainyun.auto_renew !== false;
                        if (rainyunAutoRenewLabelEl) rainyunAutoRenewLabelEl.textContent = rainyunAutoRenewEl.checked ? '开启' : '关闭';
                    }
                    const rainyunThresholdEl = document.getElementById('rainyun_renew_threshold_days');
                    if (rainyunThresholdEl) rainyunThresholdEl.value = config.rainyun.renew_threshold_days || 7;
                    const rainyunProductIdsEl = document.getElementById('rainyun_renew_product_ids');
                    if (rainyunProductIdsEl) {
                        const ids = config.rainyun.renew_product_ids;
                        rainyunProductIdsEl.value = Array.isArray(ids) ? ids.join(',') : (ids || '');
                    }
                }
                break;
            case 'enshan':
                if (config.enshan) {
                    if (enshanEnable) {
                        enshanEnable.checked = config.enshan.enable === true || config.enshan.enable === 'true';
                        if (enshanEnableLabel) enshanEnableLabel.textContent = enshanEnable.checked ? '开启' : '关闭';
                    }
                    const enshanCookieInput = document.getElementById('enshan_cookie');
                    const enshanTimeInput = document.getElementById('enshan_time');
                    if (enshanCookieInput) enshanCookieInput.value = config.enshan.cookie || '';
                    if (enshanTimeInput) enshanTimeInput.value = (config.enshan.time || '02:00').length === 5 ? config.enshan.time : '02:00';
                    const enshanCookiesList = document.getElementById('enshan_cookies_list');
                    if (enshanCookiesList) {
                        const cookies = Array.isArray(config.enshan.cookies) && config.enshan.cookies.length > 0 ? config.enshan.cookies : [''];
                        renderEnshanCookies(cookies);
                    }
                    renderTaskPushChannelSelect('enshan_push_channels', config.enshan.push_channels || []);
                }
                break;
            case 'tyyun':
                if (config.tyyun) {
                    if (tyyunEnable) {
                        tyyunEnable.checked = config.tyyun.enable === true || config.tyyun.enable === 'true';
                        if (tyyunEnableLabel) tyyunEnableLabel.textContent = tyyunEnable.checked ? '开启' : '关闭';
                    }
                    const tyyunUser = document.getElementById('tyyun_username');
                    const tyyunPwd = document.getElementById('tyyun_password');
                    if (tyyunUser) tyyunUser.value = config.tyyun.username || '';
                    if (tyyunPwd) tyyunPwd.value = config.tyyun.password || '';
                    const tyyunTimeInput = document.getElementById('tyyun_time');
                    if (tyyunTimeInput) tyyunTimeInput.value = (config.tyyun.time || '04:30').length === 5 ? config.tyyun.time : '04:30';
                    const tyyunAccountsList = document.getElementById('tyyun_accounts_list');
                    if (tyyunAccountsList) {
                        const accounts = Array.isArray(config.tyyun.accounts) && config.tyyun.accounts.length > 0 ? config.tyyun.accounts : [{ username: '', password: '' }];
                        renderTyyunAccounts(accounts);
                    }
                    renderTaskPushChannelSelect('tyyun_push_channels', config.tyyun.push_channels || []);
                }
                break;
            case 'aliyun':
                if (config.aliyun) {
                    if (aliyunEnable) {
                        aliyunEnable.checked = config.aliyun.enable === true || config.aliyun.enable === 'true';
                        if (aliyunEnableLabel) aliyunEnableLabel.textContent = aliyunEnable.checked ? '开启' : '关闭';
                    }
                    const aliyunTokenInput = document.getElementById('aliyun_refresh_token');
                    if (aliyunTokenInput) aliyunTokenInput.value = config.aliyun.refresh_token || '';
                    const aliyunTimeInput = document.getElementById('aliyun_time');
                    if (aliyunTimeInput) aliyunTimeInput.value = (config.aliyun.time || '05:30').length === 5 ? config.aliyun.time : '05:30';
                    const aliyunTokensList = document.getElementById('aliyun_refresh_tokens_list');
                    if (aliyunTokensList) {
                        const tokens = Array.isArray(config.aliyun.refresh_tokens) && config.aliyun.refresh_tokens.length > 0 ? config.aliyun.refresh_tokens : [''];
                        renderAliyunTokens(tokens);
                    }
                    renderTaskPushChannelSelect('aliyun_push_channels', config.aliyun.push_channels || []);
                }
                break;
            case 'smzdm':
                if (config.smzdm) {
                    if (smzdmEnable) {
                        smzdmEnable.checked = config.smzdm.enable === true || config.smzdm.enable === 'true';
                        if (smzdmEnableLabel) smzdmEnableLabel.textContent = smzdmEnable.checked ? '开启' : '关闭';
                    }
                    const smzdmCookieInput = document.getElementById('smzdm_cookie');
                    if (smzdmCookieInput) smzdmCookieInput.value = config.smzdm.cookie || '';
                    const smzdmTimeInput = document.getElementById('smzdm_time');
                    if (smzdmTimeInput) smzdmTimeInput.value = (config.smzdm.time || '00:30').length === 5 ? config.smzdm.time : '00:30';
                    const smzdmCookiesList = document.getElementById('smzdm_cookies_list');
                    if (smzdmCookiesList) {
                        const cookies = Array.isArray(config.smzdm.cookies) && config.smzdm.cookies.length > 0 ? config.smzdm.cookies : [''];
                        renderSmzdmCookies(cookies);
                    }
                    renderTaskPushChannelSelect('smzdm_push_channels', config.smzdm.push_channels || []);
                }
                break;
            case 'zdm_draw':
                if (config.zdm_draw) {
                    if (zdmDrawEnable) {
                        zdmDrawEnable.checked = config.zdm_draw.enable === true || config.zdm_draw.enable === 'true';
                        if (zdmDrawEnableLabel) zdmDrawEnableLabel.textContent = zdmDrawEnable.checked ? '开启' : '关闭';
                    }
                    const zdmDrawCookieInput = document.getElementById('zdm_draw_cookie');
                    if (zdmDrawCookieInput) zdmDrawCookieInput.value = config.zdm_draw.cookie || '';
                    const zdmDrawTimeInput = document.getElementById('zdm_draw_time');
                    if (zdmDrawTimeInput) zdmDrawTimeInput.value = (config.zdm_draw.time || '07:30').length === 5 ? config.zdm_draw.time : '07:30';
                    const zdmDrawCookiesList = document.getElementById('zdm_draw_cookies_list');
                    if (zdmDrawCookiesList) {
                        const cookies = Array.isArray(config.zdm_draw.cookies) && config.zdm_draw.cookies.length > 0 ? config.zdm_draw.cookies : [''];
                        renderZdmDrawCookies(cookies);
                    }
                    renderTaskPushChannelSelect('zdm_draw_push_channels', config.zdm_draw.push_channels || []);
                }
                break;
            case 'fg':
                if (config.fg) {
                    if (fgEnable) {
                        fgEnable.checked = config.fg.enable === true || config.fg.enable === 'true';
                        if (fgEnableLabel) fgEnableLabel.textContent = fgEnable.checked ? '开启' : '关闭';
                    }
                    const fgCookieInput = document.getElementById('fg_cookie');
                    if (fgCookieInput) fgCookieInput.value = config.fg.cookie || '';
                    const fgTimeInput = document.getElementById('fg_time');
                    if (fgTimeInput) fgTimeInput.value = (config.fg.time || '00:01').length === 5 ? config.fg.time : '00:01';
                    const fgCookiesList = document.getElementById('fg_cookies_list');
                    if (fgCookiesList) {
                        const cookies = Array.isArray(config.fg.cookies) && config.fg.cookies.length > 0 ? config.fg.cookies : [''];
                        renderFgCookies(cookies);
                    }
                    renderTaskPushChannelSelect('fg_push_channels', config.fg.push_channels || []);
                }
                break;
            case 'miui':
                if (config.miui) {
                    if (miuiEnable) { miuiEnable.checked = config.miui.enable === true || config.miui.enable === 'true'; if (miuiEnableLabel) miuiEnableLabel.textContent = miuiEnable.checked ? '开启' : '关闭'; }
                    const miuiAcc = document.getElementById('miui_account'); const miuiPwd = document.getElementById('miui_password'); const miuiTime = document.getElementById('miui_time');
                    if (miuiAcc) miuiAcc.value = config.miui.account || ''; if (miuiPwd) miuiPwd.value = config.miui.password || '';
                    if (miuiTime) miuiTime.value = (config.miui.time || '08:30').length === 5 ? config.miui.time : '08:30';
                    const miuiList = document.getElementById('miui_accounts_list');
                    if (miuiList) { const accs = Array.isArray(config.miui.accounts) && config.miui.accounts.length > 0 ? config.miui.accounts : [{ account: '', password: '' }]; renderMiuiAccounts(accs); }
                    renderTaskPushChannelSelect('miui_push_channels', config.miui.push_channels || []);
                }
                break;
            case 'iqiyi':
                if (config.iqiyi) {
                    if (iqiyiEnable) { iqiyiEnable.checked = config.iqiyi.enable === true || config.iqiyi.enable === 'true'; if (iqiyiEnableLabel) iqiyiEnableLabel.textContent = iqiyiEnable.checked ? '开启' : '关闭'; }
                    const iqiyiCookie = document.getElementById('iqiyi_cookie'); const iqiyiTime = document.getElementById('iqiyi_time');
                    if (iqiyiCookie) iqiyiCookie.value = config.iqiyi.cookie || ''; if (iqiyiTime) iqiyiTime.value = (config.iqiyi.time || '06:00').length === 5 ? config.iqiyi.time : '06:00';
                    const iqiyiList = document.getElementById('iqiyi_cookies_list');
                    if (iqiyiList) { const cks = Array.isArray(config.iqiyi.cookies) && config.iqiyi.cookies.length > 0 ? config.iqiyi.cookies : ['']; renderIqiyiCookies(cks); }
                    renderTaskPushChannelSelect('iqiyi_push_channels', config.iqiyi.push_channels || []);
                }
                break;
            case 'lenovo':
                if (config.lenovo) {
                    if (lenovoEnable) { lenovoEnable.checked = config.lenovo.enable === true || config.lenovo.enable === 'true'; if (lenovoEnableLabel) lenovoEnableLabel.textContent = lenovoEnable.checked ? '开启' : '关闭'; }
                    const lenovoToken = document.getElementById('lenovo_access_token'); const lenovoTime = document.getElementById('lenovo_time');
                    if (lenovoToken) lenovoToken.value = config.lenovo.access_token || ''; if (lenovoTime) lenovoTime.value = (config.lenovo.time || '05:30').length === 5 ? config.lenovo.time : '05:30';
                    const lenovoList = document.getElementById('lenovo_access_tokens_list');
                    if (lenovoList) { const toks = Array.isArray(config.lenovo.access_tokens) && config.lenovo.access_tokens.length > 0 ? config.lenovo.access_tokens : ['']; renderLenovoTokens(toks); }
                    renderTaskPushChannelSelect('lenovo_push_channels', config.lenovo.push_channels || []);
                }
                break;
            case 'lbly':
                if (config.lbly) {
                    if (lblyEnable) { lblyEnable.checked = config.lbly.enable === true || config.lbly.enable === 'true'; if (lblyEnableLabel) lblyEnableLabel.textContent = lblyEnable.checked ? '开启' : '关闭'; }
                    const lblyBody = document.getElementById('lbly_request_body'); const lblyTime = document.getElementById('lbly_time');
                    if (lblyBody) lblyBody.value = config.lbly.request_body || ''; if (lblyTime) lblyTime.value = (config.lbly.time || '05:30').length === 5 ? config.lbly.time : '05:30';
                    const lblyList = document.getElementById('lbly_request_bodies_list');
                    if (lblyList) { const bodies = Array.isArray(config.lbly.request_bodies) && config.lbly.request_bodies.length > 0 ? config.lbly.request_bodies : ['']; renderLblyBodies(bodies); }
                    renderTaskPushChannelSelect('lbly_push_channels', config.lbly.push_channels || []);
                }
                break;
            case 'pinzan':
                if (config.pinzan) {
                    if (pinzanEnable) { pinzanEnable.checked = config.pinzan.enable === true || config.pinzan.enable === 'true'; if (pinzanEnableLabel) pinzanEnableLabel.textContent = pinzanEnable.checked ? '开启' : '关闭'; }
                    const pzAcc = document.getElementById('pinzan_account'); const pzPwd = document.getElementById('pinzan_password'); const pzTime = document.getElementById('pinzan_time');
                    if (pzAcc) pzAcc.value = config.pinzan.account || ''; if (pzPwd) pzPwd.value = config.pinzan.password || ''; if (pzTime) pzTime.value = (config.pinzan.time || '08:00').length === 5 ? config.pinzan.time : '08:00';
                    const pzList = document.getElementById('pinzan_accounts_list');
                    if (pzList) { const accs = Array.isArray(config.pinzan.accounts) && config.pinzan.accounts.length > 0 ? config.pinzan.accounts : [{ account: '', password: '' }]; renderPinzanAccounts(accs); }
                    renderTaskPushChannelSelect('pinzan_push_channels', config.pinzan.push_channels || []);
                }
                break;
            case 'dml':
                if (config.dml) {
                    if (dmlEnable) { dmlEnable.checked = config.dml.enable === true || config.dml.enable === 'true'; if (dmlEnableLabel) dmlEnableLabel.textContent = dmlEnable.checked ? '开启' : '关闭'; }
                    const dmlOpenid = document.getElementById('dml_openid'); const dmlTime = document.getElementById('dml_time');
                    if (dmlOpenid) dmlOpenid.value = config.dml.openid || ''; if (dmlTime) dmlTime.value = (config.dml.time || '06:00').length === 5 ? config.dml.time : '06:00';
                    const dmlList = document.getElementById('dml_openids_list');
                    if (dmlList) { const ids = Array.isArray(config.dml.openids) && config.dml.openids.length > 0 ? config.dml.openids : ['']; renderDmlOpenids(ids); }
                    renderTaskPushChannelSelect('dml_push_channels', config.dml.push_channels || []);
                }
                break;
            case 'xiaomao':
                if (config.xiaomao) {
                    if (xiaomaoEnable) { xiaomaoEnable.checked = config.xiaomao.enable === true || config.xiaomao.enable === 'true'; if (xiaomaoEnableLabel) xiaomaoEnableLabel.textContent = xiaomaoEnable.checked ? '开启' : '关闭'; }
                    const xmToken = document.getElementById('xiaomao_token'); const xmVer = document.getElementById('xiaomao_mt_version'); const xmTime = document.getElementById('xiaomao_time');
                    if (xmToken) xmToken.value = config.xiaomao.token || ''; if (xmVer) xmVer.value = config.xiaomao.mt_version || ''; if (xmTime) xmTime.value = (config.xiaomao.time || '09:00').length === 5 ? config.xiaomao.time : '09:00';
                    const xmList = document.getElementById('xiaomao_tokens_list');
                    if (xmList) { const toks = Array.isArray(config.xiaomao.tokens) && config.xiaomao.tokens.length > 0 ? config.xiaomao.tokens : ['']; renderXiaomaoTokens(toks); }
                    renderTaskPushChannelSelect('xiaomao_push_channels', config.xiaomao.push_channels || []);
                }
                break;
            case 'ydwx':
                if (config.ydwx) {
                    if (ydwxEnable) { ydwxEnable.checked = config.ydwx.enable === true || config.ydwx.enable === 'true'; if (ydwxEnableLabel) ydwxEnableLabel.textContent = ydwxEnable.checked ? '开启' : '关闭'; }
                    const ydDp = document.getElementById('ydwx_device_params'); const ydTk = document.getElementById('ydwx_token'); const ydTime = document.getElementById('ydwx_time');
                    if (ydDp) ydDp.value = config.ydwx.device_params || ''; if (ydTk) ydTk.value = config.ydwx.token || ''; if (ydTime) ydTime.value = (config.ydwx.time || '06:00').length === 5 ? config.ydwx.time : '06:00';
                    const ydList = document.getElementById('ydwx_accounts_list');
                    if (ydList) { const accs = Array.isArray(config.ydwx.accounts) && config.ydwx.accounts.length > 0 ? config.ydwx.accounts : [{ device_params: '', token: '' }]; renderYdwxAccounts(accs); }
                    renderTaskPushChannelSelect('ydwx_push_channels', config.ydwx.push_channels || []);
                }
                break;
            case 'xingkong':
                if (config.xingkong) {
                    if (xingkongEnable) { xingkongEnable.checked = config.xingkong.enable === true || config.xingkong.enable === 'true'; if (xingkongEnableLabel) xingkongEnableLabel.textContent = xingkongEnable.checked ? '开启' : '关闭'; }
                    const xkU = document.getElementById('xingkong_username'); const xkP = document.getElementById('xingkong_password'); const xkTime = document.getElementById('xingkong_time');
                    if (xkU) xkU.value = config.xingkong.username || ''; if (xkP) xkP.value = config.xingkong.password || ''; if (xkTime) xkTime.value = (config.xingkong.time || '07:30').length === 5 ? config.xingkong.time : '07:30';
                    const xkList = document.getElementById('xingkong_accounts_list');
                    if (xkList) { const accs = Array.isArray(config.xingkong.accounts) && config.xingkong.accounts.length > 0 ? config.xingkong.accounts : [{ username: '', password: '' }]; renderXingkongAccounts(accs); }
                    renderTaskPushChannelSelect('xingkong_push_channels', config.xingkong.push_channels || []);
                }
                break;
            case 'qtw':
                if (config.qtw) {
                    if (qtwEnable) { qtwEnable.checked = config.qtw.enable === true || config.qtw.enable === 'true'; if (qtwEnableLabel) qtwEnableLabel.textContent = qtwEnable.checked ? '开启' : '关闭'; }
                    const qtwC = document.getElementById('qtw_cookie'); const qtwTime = document.getElementById('qtw_time');
                    if (qtwC) qtwC.value = config.qtw.cookie || ''; if (qtwTime) qtwTime.value = (config.qtw.time || '01:30').length === 5 ? config.qtw.time : '01:30';
                    const qtwList = document.getElementById('qtw_cookies_list');
                    if (qtwList) { const cks = Array.isArray(config.qtw.cookies) && config.qtw.cookies.length > 0 ? config.qtw.cookies : ['']; renderQtwCookies(cks); }
                    renderTaskPushChannelSelect('qtw_push_channels', config.qtw.push_channels || []);
                }
                break;
            case 'freenom':
                if (config.freenom) {
                    if (freenomEnable) {
                        freenomEnable.checked = config.freenom.enable === true || config.freenom.enable === 'true';
                        if (freenomEnableLabel) freenomEnableLabel.textContent = freenomEnable.checked ? '开启' : '关闭';
                    }
                    const freenomTime = document.getElementById('freenom_time');
                    if (freenomTime) freenomTime.value = (config.freenom.time || '07:33').length === 5 ? config.freenom.time : '07:33';
                    const listEl = document.getElementById('freenom_accounts_list');
                    if (listEl) {
                        const accounts = Array.isArray(config.freenom.accounts) && config.freenom.accounts.length > 0 ? config.freenom.accounts : [{ email: '', password: '' }];
                        renderFreenomAccounts(accounts);
                    }
                    renderTaskPushChannelSelect('freenom_push_channels', config.freenom.push_channels || []);
                }
                break;
            case 'weather':
                if (config.weather) {
                    if (weatherEnable) {
                        weatherEnable.checked = config.weather.enable === true || config.weather.enable === 'true';
                        if (weatherEnableLabel) weatherEnableLabel.textContent = weatherEnable.checked ? '开启' : '关闭';
                    }
                    const cityInput = document.getElementById('weather_city_code');
                    const timeInput = document.getElementById('weather_time');
                    if (cityInput) cityInput.value = config.weather.city_code || '';
                    if (timeInput) timeInput.value = (config.weather.time || '07:30').length === 5 ? config.weather.time : '07:30';
                    renderTaskPushChannelSelect('weather_push_channels', config.weather.push_channels || []);
                }
                break;
            case 'kuake':
                if (config.kuake) {
                    if (kuakeEnable) {
                        kuakeEnable.checked = config.kuake.enable === true || config.kuake.enable === 'true';
                        if (kuakeEnableLabel) kuakeEnableLabel.textContent = kuakeEnable.checked ? '开启' : '关闭';
                    }
                    const single = document.getElementById('kuake_cookie');
                    const timeInput = document.getElementById('kuake_time');
                    if (single) single.value = config.kuake.cookie || '';
                    if (timeInput) timeInput.value = (config.kuake.time || '02:00').length === 5 ? config.kuake.time : '02:00';
                    const listEl = document.getElementById('kuake_cookies_list');
                    if (listEl) {
                        const list = Array.isArray(config.kuake.cookies) && config.kuake.cookies.length > 0 ? config.kuake.cookies : [''];
                        renderKuakeCookies(list);
                    }
                    renderTaskPushChannelSelect('kuake_push_channels', config.kuake.push_channels || []);
                }
                break;
            case 'kjwj':
                if (config.kjwj) {
                    if (kjwjEnable) {
                        kjwjEnable.checked = config.kjwj.enable === true || config.kjwj.enable === 'true';
                        if (kjwjEnableLabel) kjwjEnableLabel.textContent = kjwjEnable.checked ? '开启' : '关闭';
                    }
                    const timeInput = document.getElementById('kjwj_time');
                    if (timeInput) timeInput.value = (config.kjwj.time || '07:30').length === 5 ? config.kjwj.time : '07:30';
                    const listEl = document.getElementById('kjwj_accounts_list');
                    if (listEl) {
                        const list = Array.isArray(config.kjwj.accounts) && config.kjwj.accounts.length > 0 ? config.kjwj.accounts : [{ username: '', password: '' }];
                        renderKjwjAccounts(list);
                    }
                    renderTaskPushChannelSelect('kjwj_push_channels', config.kjwj.push_channels || []);
                }
                break;
            case 'fr':
                if (config.fr) {
                    if (frEnable) {
                        frEnable.checked = config.fr.enable === true || config.fr.enable === 'true';
                        if (frEnableLabel) frEnableLabel.textContent = frEnable.checked ? '开启' : '关闭';
                    }
                    const cookieInput = document.getElementById('fr_cookie');
                    const timeInput = document.getElementById('fr_time');
                    if (cookieInput) cookieInput.value = config.fr.cookie || '';
                    if (timeInput) timeInput.value = (config.fr.time || '06:30').length === 5 ? config.fr.time : '06:30';
                    renderTaskPushChannelSelect('fr_push_channels', config.fr.push_channels || []);
                }
                break;
            case 'nine_nine_nine':
                if (config.nine_nine_nine) {
                    if (nineEnable) {
                        nineEnable.checked = config.nine_nine_nine.enable === true || config.nine_nine_nine.enable === 'true';
                        if (nineEnableLabel) nineEnableLabel.textContent = nineEnable.checked ? '开启' : '关闭';
                    }
                    const timeInput = document.getElementById('nine_nine_nine_time');
                    if (timeInput) timeInput.value = (config.nine_nine_nine.time || '15:15').length === 5 ? config.nine_nine_nine.time : '15:15';
                    const listEl = document.getElementById('nine_nine_nine_tokens_list');
                    if (listEl) {
                        const list = Array.isArray(config.nine_nine_nine.tokens) && config.nine_nine_nine.tokens.length > 0 ? config.nine_nine_nine.tokens : [''];
                        renderNineTokens(list);
                    }
                    renderTaskPushChannelSelect('nine_nine_nine_push_channels', config.nine_nine_nine.push_channels || []);
                }
                break;
            case 'zgfc':
                if (config.zgfc) {
                    if (zgfcEnable) {
                        zgfcEnable.checked = config.zgfc.enable === true || config.zgfc.enable === 'true';
                        if (zgfcEnableLabel) zgfcEnableLabel.textContent = zgfcEnable.checked ? '开启' : '关闭';
                    }
                    const timeInput = document.getElementById('zgfc_time');
                    if (timeInput) timeInput.value = (config.zgfc.time || '08:00').length === 5 ? config.zgfc.time : '08:00';
                    const listEl = document.getElementById('zgfc_tokens_list');
                    if (listEl) {
                        const list = Array.isArray(config.zgfc.tokens) && config.zgfc.tokens.length > 0 ? config.zgfc.tokens : [''];
                        renderZgfcTokens(list);
                    }
                    renderTaskPushChannelSelect('zgfc_push_channels', config.zgfc.push_channels || []);
                }
                break;
            case 'ssq_500w':
                if (config.ssq_500w) {
                    if (ssqEnable) {
                        ssqEnable.checked = config.ssq_500w.enable === true || config.ssq_500w.enable === 'true';
                        if (ssqEnableLabel) ssqEnableLabel.textContent = ssqEnable.checked ? '开启' : '关闭';
                    }
                    const timeInput = document.getElementById('ssq_500w_time');
                    if (timeInput) timeInput.value = (config.ssq_500w.time || '21:30').length === 5 ? config.ssq_500w.time : '21:30';
                    renderTaskPushChannelSelect('ssq_500w_push_channels', config.ssq_500w.push_channels || []);
                }
                break;
            case 'log_cleanup':
                if (config.log_cleanup) {
                    const enableEl = document.getElementById('log_cleanup_enable');
                    const enableLabelEl = document.getElementById('log_cleanup_enable_label');
                    if (enableEl) {
                        enableEl.checked = config.log_cleanup.enable === true || config.log_cleanup.enable === 'true';
                        if (enableLabelEl) enableLabelEl.textContent = enableEl.checked ? '开启' : '关闭';
                    }
                    const timeInput = document.getElementById('log_cleanup_time');
                    if (timeInput) {
                        const val = config.log_cleanup.time || '02:10';
                        timeInput.value = (val && val.length === 5) ? val : '02:10';
                    }
                    const retentionInput = document.getElementById('retention_days');
                    if (retentionInput) {
                        retentionInput.value = config.log_cleanup.retention_days || 3;
                    }
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
            case 'ai_assistant':
                if (config.ai_assistant) {
                    const a = config.ai_assistant;
                    const aiEnable = document.getElementById('ai_assistant_enable');
                    const aiEnableLabel = document.getElementById('ai_assistant_enable_label');
                    if (aiEnable) aiEnable.checked = a.enable || false;
                    if (aiEnableLabel) aiEnableLabel.textContent = (a.enable ? '开启' : '关闭');
                    const provider = document.getElementById('ai_assistant_provider');
                    if (provider) {
                        const pv = (a.provider || 'openai').toLowerCase().trim();
                        provider.value = ['openai','deepseek','qwen','zhipu','moonshot','ollama','openai_compatible'].includes(pv) ? pv : 'openai';
                    }
                    const apiBase = document.getElementById('ai_assistant_api_base');
                    if (apiBase) apiBase.value = a.api_base || '';
                    const apiKey = document.getElementById('ai_assistant_api_key');
                    if (apiKey) apiKey.value = a.api_key || '';
                    const model = document.getElementById('ai_assistant_model');
                    if (model) model.value = a.model || '';
                    const emb = document.getElementById('ai_assistant_embedding_model');
                    if (emb) emb.value = a.embedding_model || '';
                    const chroma = document.getElementById('ai_assistant_chroma_persist_dir');
                    if (chroma) chroma.value = a.chroma_persist_dir || '';
                    const ragInterval = document.getElementById('ai_assistant_rag_index_refresh_interval_seconds');
                    if (ragInterval) ragInterval.value = a.rag_index_refresh_interval_seconds ?? 1800;
                    const rate = document.getElementById('ai_assistant_rate_limit_per_minute');
                    if (rate) rate.value = a.rate_limit_per_minute ?? 10;
                    const maxRounds = document.getElementById('ai_assistant_max_history_rounds');
                    if (maxRounds) maxRounds.value = a.max_history_rounds ?? 10;
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
            case 'app': {
                const baseUrlInput = document.getElementById('app_base_url');
                config.app = {
                    base_url: (baseUrlInput?.value || '').trim()
                };
                break;
            }
            case 'weibo':
                config.weibo = {
                    enable: weiboEnable ? weiboEnable.checked : true,
                    cookie: document.getElementById('weibo_cookie').value.trim(),
                    uids: document.getElementById('weibo_uids').value.trim(),
                    concurrency: parseInt(document.getElementById('weibo_concurrency').value) || 3,
                    monitor_interval_seconds: parseInt(document.getElementById('weibo_monitor_interval_seconds').value) || 300,
                    push_channels: getTaskPushChannels('weibo_push_channels'),
                    compress_with_llm: document.getElementById('weibo_compress_with_llm')?.checked || false
                };
                break;
            case 'checkin': {
                const accounts = [];
                document.querySelectorAll('#checkin_accounts_list .multi-account-row').forEach(row => {
                    const email = (row.querySelector('.checkin-account-email')?.value || '').trim();
                    const password = (row.querySelector('.checkin-account-password')?.value || '').trim();
                    if (email || password) accounts.push({ email, password });
                });
                const singleEmail = (document.getElementById('checkin_email')?.value || '').trim();
                const singlePassword = (document.getElementById('checkin_password')?.value || '').trim();
                const first = accounts[0] || { email: singleEmail, password: singlePassword };
                config.checkin = {
                    enable: checkinEnable ? checkinEnable.checked : false,
                    email: first.email,
                    password: first.password,
                    time: (document.getElementById('checkin_time')?.value || '').trim() || '08:00',
                    push_channels: getTaskPushChannels('checkin_push_channels')
                };
                if (accounts.length > 0) config.checkin.accounts = accounts;
                break;
            }
            case 'tieba': {
                const cookies = [];
                document.querySelectorAll('#tieba_cookies_list .multi-cookie-row').forEach(row => {
                    const val = (row.querySelector('.tieba-cookie-value')?.value || '').trim();
                    if (val) cookies.push(val);
                });
                const singleCookie = (document.getElementById('tieba_cookie')?.value || '').trim();
                config.tieba = {
                    enable: tiebaEnable ? tiebaEnable.checked : false,
                    cookie: cookies.length > 0 ? cookies[0] : singleCookie,
                    time: (document.getElementById('tieba_time')?.value || '').trim() || '08:10',
                    push_channels: getTaskPushChannels('tieba_push_channels')
                };
                if (cookies.length > 0) config.tieba.cookies = cookies;
                break;
            }
            case 'weibo_chaohua': {
                const cookies = [];
                document.querySelectorAll('#weibo_chaohua_cookies_list .multi-cookie-row').forEach(row => {
                    const val = (row.querySelector('.weibo-chaohua-cookie-value')?.value || '').trim();
                    if (val) cookies.push(val);
                });
                const singleCookie = (document.getElementById('weibo_chaohua_cookie')?.value || '').trim();
                config.weibo_chaohua = {
                    enable: weiboChaohuaEnable ? weiboChaohuaEnable.checked : false,
                    cookie: cookies.length > 0 ? cookies[0] : singleCookie,
                    time: (document.getElementById('weibo_chaohua_time')?.value || '').trim() || '23:45',
                    push_channels: getTaskPushChannels('weibo_chaohua_push_channels')
                };
                if (cookies.length > 0) config.weibo_chaohua.cookies = cookies;
                break;
            }
            case 'huya':
                config.huya = {
                    enable: huyaEnable ? huyaEnable.checked : true,
                    rooms: document.getElementById('huya_rooms').value.trim(),
                    concurrency: parseInt(document.getElementById('huya_concurrency').value) || 7,
                    monitor_interval_seconds: parseInt(document.getElementById('huya_monitor_interval_seconds').value) || 65,
                    push_channels: getTaskPushChannels('huya_push_channels')
                };
                break;
            case 'bilibili':
                config.bilibili = {
                    enable: bilibiliEnable ? bilibiliEnable.checked : true,
                    cookie: (document.getElementById('bilibili_cookie')?.value || '').trim(),
                    uids: document.getElementById('bilibili_uids').value.trim(),
                    skip_forward: document.getElementById('bilibili_skip_forward')?.checked !== false,
                    concurrency: parseInt(document.getElementById('bilibili_concurrency').value) || 2,
                    monitor_interval_seconds: parseInt(document.getElementById('bilibili_monitor_interval_seconds').value) || 60,
                    push_channels: getTaskPushChannels('bilibili_push_channels')
                };
                break;
            case 'douyin':
                config.douyin = {
                    enable: douyinEnable ? douyinEnable.checked : true,
                    douyin_ids: document.getElementById('douyin_douyin_ids').value.trim(),
                    concurrency: parseInt(document.getElementById('douyin_concurrency').value) || 2,
                    monitor_interval_seconds: parseInt(document.getElementById('douyin_monitor_interval_seconds').value) || 30,
                    push_channels: getTaskPushChannels('douyin_push_channels')
                };
                break;
            case 'douyu':
                config.douyu = {
                    enable: douyuEnable ? douyuEnable.checked : true,
                    rooms: document.getElementById('douyu_rooms').value.trim(),
                    concurrency: parseInt(document.getElementById('douyu_concurrency').value) || 2,
                    monitor_interval_seconds: parseInt(document.getElementById('douyu_monitor_interval_seconds').value) || 300,
                    push_channels: getTaskPushChannels('douyu_push_channels')
                };
                break;
            case 'xhs':
                config.xhs = {
                    enable: xhsEnable ? xhsEnable.checked : true,
                    cookie: (document.getElementById('xhs_cookie')?.value || '').trim(),
                    profile_ids: document.getElementById('xhs_profile_ids').value.trim(),
                    concurrency: parseInt(document.getElementById('xhs_concurrency').value) || 2,
                    monitor_interval_seconds: parseInt(document.getElementById('xhs_monitor_interval_seconds').value) || 300,
                    push_channels: getTaskPushChannels('xhs_push_channels')
                };
                break;
            case 'rainyun': {
                const rainyunAccounts = [];
                document.querySelectorAll('#rainyun_accounts_list .multi-account-row').forEach(row => {
                    const username = (row.querySelector('.rainyun-account-username')?.value || '').trim();
                    const password = (row.querySelector('.rainyun-account-password')?.value || '').trim();
                    const api_key = (row.querySelector('.rainyun-account-api-key')?.value || '').trim();
                    if (username || password) rainyunAccounts.push({ username, password, api_key });
                });
                const renewIdsRaw = (document.getElementById('rainyun_renew_product_ids')?.value || '').trim();
                const renewIds = renewIdsRaw ? renewIdsRaw.split(/[,\s]+/).map(s => parseInt(s, 10)).filter(n => !isNaN(n)) : [];
                config.rainyun = {
                    enable: rainyunEnable ? rainyunEnable.checked : false,
                    accounts: rainyunAccounts,
                    time: (document.getElementById('rainyun_time')?.value || '').trim() || '08:30',
                    push_channels: getTaskPushChannels('rainyun_push_channels'),
                    auto_renew: (document.getElementById('rainyun_auto_renew')?.checked ?? true),
                    renew_threshold_days: parseInt(document.getElementById('rainyun_renew_threshold_days')?.value || '7', 10) || 7,
                    renew_product_ids: renewIds.length > 0 ? renewIds : []
                };
                break;
            }
            case 'enshan': {
                const cookies = [];
                document.querySelectorAll('#enshan_cookies_list .multi-cookie-row').forEach(row => {
                    const val = (row.querySelector('.enshan-cookie-value')?.value || '').trim();
                    if (val) cookies.push(val);
                });
                const singleCookie = (document.getElementById('enshan_cookie')?.value || '').trim();
                config.enshan = {
                    enable: enshanEnable ? enshanEnable.checked : false,
                    cookie: cookies.length > 0 ? cookies[0] : singleCookie,
                    time: (document.getElementById('enshan_time')?.value || '').trim() || '02:00',
                    push_channels: getTaskPushChannels('enshan_push_channels')
                };
                if (cookies.length > 0) config.enshan.cookies = cookies;
                break;
            }
            case 'tyyun': {
                const accounts = [];
                document.querySelectorAll('#tyyun_accounts_list .multi-account-row').forEach(row => {
                    const username = (row.querySelector('.tyyun-account-username')?.value || '').trim();
                    const password = (row.querySelector('.tyyun-account-password')?.value || '').trim();
                    if (username || password) accounts.push({ username, password });
                });
                const singleUser = (document.getElementById('tyyun_username')?.value || '').trim();
                const singlePwd = (document.getElementById('tyyun_password')?.value || '').trim();
                const first = accounts[0] || { username: singleUser, password: singlePwd };
                config.tyyun = {
                    enable: tyyunEnable ? tyyunEnable.checked : false,
                    username: first.username,
                    password: first.password,
                    time: (document.getElementById('tyyun_time')?.value || '').trim() || '04:30',
                    push_channels: getTaskPushChannels('tyyun_push_channels')
                };
                if (accounts.length > 0) config.tyyun.accounts = accounts;
                break;
            }
            case 'aliyun': {
                const tokens = [];
                document.querySelectorAll('#aliyun_refresh_tokens_list .multi-cookie-row').forEach(row => {
                    const val = (row.querySelector('.aliyun-token-value')?.value || '').trim();
                    if (val) tokens.push(val);
                });
                const singleToken = (document.getElementById('aliyun_refresh_token')?.value || '').trim();
                config.aliyun = {
                    enable: aliyunEnable ? aliyunEnable.checked : false,
                    refresh_token: tokens.length > 0 ? tokens[0] : singleToken,
                    time: (document.getElementById('aliyun_time')?.value || '').trim() || '05:30',
                    push_channels: getTaskPushChannels('aliyun_push_channels')
                };
                if (tokens.length > 0) config.aliyun.refresh_tokens = tokens;
                break;
            }
            case 'smzdm': {
                const cookies = [];
                document.querySelectorAll('#smzdm_cookies_list .multi-cookie-row').forEach(row => {
                    const val = (row.querySelector('.smzdm-cookie-value')?.value || '').trim();
                    if (val) cookies.push(val);
                });
                const singleCookie = (document.getElementById('smzdm_cookie')?.value || '').trim();
                config.smzdm = {
                    enable: smzdmEnable ? smzdmEnable.checked : false,
                    cookie: cookies.length > 0 ? cookies[0] : singleCookie,
                    time: (document.getElementById('smzdm_time')?.value || '').trim() || '00:30',
                    push_channels: getTaskPushChannels('smzdm_push_channels')
                };
                if (cookies.length > 0) config.smzdm.cookies = cookies;
                break;
            }
            case 'zdm_draw': {
                const cookies = [];
                document.querySelectorAll('#zdm_draw_cookies_list .multi-cookie-row').forEach(row => {
                    const val = (row.querySelector('.zdm-draw-cookie-value')?.value || '').trim();
                    if (val) cookies.push(val);
                });
                const singleCookie = (document.getElementById('zdm_draw_cookie')?.value || '').trim();
                config.zdm_draw = {
                    enable: zdmDrawEnable ? zdmDrawEnable.checked : false,
                    cookie: cookies.length > 0 ? cookies[0] : singleCookie,
                    time: (document.getElementById('zdm_draw_time')?.value || '').trim() || '07:30',
                    push_channels: getTaskPushChannels('zdm_draw_push_channels')
                };
                if (cookies.length > 0) config.zdm_draw.cookies = cookies;
                break;
            }
            case 'fg': {
                const cookies = [];
                document.querySelectorAll('#fg_cookies_list .multi-cookie-row').forEach(row => {
                    const val = (row.querySelector('.fg-cookie-value')?.value || '').trim();
                    if (val) cookies.push(val);
                });
                const singleCookie = (document.getElementById('fg_cookie')?.value || '').trim();
                config.fg = {
                    enable: fgEnable ? fgEnable.checked : false,
                    cookie: cookies.length > 0 ? cookies[0] : singleCookie,
                    time: (document.getElementById('fg_time')?.value || '').trim() || '00:01',
                    push_channels: getTaskPushChannels('fg_push_channels')
                };
                if (cookies.length > 0) config.fg.cookies = cookies;
                break;
            }
            case 'miui': {
                const accs = [];
                document.querySelectorAll('#miui_accounts_list .multi-account-row').forEach(row => {
                    const a = (row.querySelector('.miui-account-value')?.value || '').trim();
                    const p = (row.querySelector('.miui-password-value')?.value || '').trim();
                    if (a || p) accs.push({ account: a, password: p });
                });
                const singleA = (document.getElementById('miui_account')?.value || '').trim();
                const singleP = (document.getElementById('miui_password')?.value || '').trim();
                config.miui = { enable: miuiEnable ? miuiEnable.checked : false, account: accs[0]?.account || singleA, password: accs[0]?.password || singleP, time: (document.getElementById('miui_time')?.value || '').trim() || '08:30', push_channels: getTaskPushChannels('miui_push_channels') };
                if (accs.length > 0) config.miui.accounts = accs;
                break;
            }
            case 'iqiyi': {
                const cks = [];
                document.querySelectorAll('#iqiyi_cookies_list .multi-cookie-row').forEach(row => { const v = (row.querySelector('.iqiyi-cookie-value')?.value || '').trim(); if (v) cks.push(v); });
                const single = (document.getElementById('iqiyi_cookie')?.value || '').trim();
                config.iqiyi = { enable: iqiyiEnable ? iqiyiEnable.checked : false, cookie: cks[0] || single, time: (document.getElementById('iqiyi_time')?.value || '').trim() || '06:00', push_channels: getTaskPushChannels('iqiyi_push_channels') };
                if (cks.length > 0) config.iqiyi.cookies = cks;
                break;
            }
            case 'lenovo': {
                const toks = [];
                document.querySelectorAll('#lenovo_access_tokens_list .multi-cookie-row').forEach(row => { const v = (row.querySelector('.lenovo-token-value')?.value || '').trim(); if (v) toks.push(v); });
                const single = (document.getElementById('lenovo_access_token')?.value || '').trim();
                config.lenovo = { enable: lenovoEnable ? lenovoEnable.checked : false, access_token: toks[0] || single, time: (document.getElementById('lenovo_time')?.value || '').trim() || '05:30', push_channels: getTaskPushChannels('lenovo_push_channels') };
                if (toks.length > 0) config.lenovo.access_tokens = toks;
                break;
            }
            case 'lbly': {
                const bodies = [];
                document.querySelectorAll('#lbly_request_bodies_list .multi-cookie-row').forEach(row => { const v = (row.querySelector('.lbly-body-value')?.value || '').trim(); if (v) bodies.push(v); });
                const single = (document.getElementById('lbly_request_body')?.value || '').trim();
                config.lbly = { enable: lblyEnable ? lblyEnable.checked : false, request_body: bodies[0] || single, time: (document.getElementById('lbly_time')?.value || '').trim() || '05:30', push_channels: getTaskPushChannels('lbly_push_channels') };
                if (bodies.length > 0) config.lbly.request_bodies = bodies;
                break;
            }
            case 'pinzan': {
                const accs = [];
                document.querySelectorAll('#pinzan_accounts_list .multi-account-row').forEach(row => {
                    const a = (row.querySelector('.pinzan-account-value')?.value || '').trim();
                    const p = (row.querySelector('.pinzan-password-value')?.value || '').trim();
                    if (a || p) accs.push({ account: a, password: p });
                });
                const singleA = (document.getElementById('pinzan_account')?.value || '').trim();
                const singleP = (document.getElementById('pinzan_password')?.value || '').trim();
                config.pinzan = { enable: pinzanEnable ? pinzanEnable.checked : false, account: accs[0]?.account || singleA, password: accs[0]?.password || singleP, time: (document.getElementById('pinzan_time')?.value || '').trim() || '08:00', push_channels: getTaskPushChannels('pinzan_push_channels') };
                if (accs.length > 0) config.pinzan.accounts = accs;
                break;
            }
            case 'dml': {
                const ids = [];
                document.querySelectorAll('#dml_openids_list .multi-cookie-row').forEach(row => { const v = (row.querySelector('.dml-openid-value')?.value || '').trim(); if (v) ids.push(v); });
                const single = (document.getElementById('dml_openid')?.value || '').trim();
                config.dml = { enable: dmlEnable ? dmlEnable.checked : false, openid: ids[0] || single, time: (document.getElementById('dml_time')?.value || '').trim() || '06:00', push_channels: getTaskPushChannels('dml_push_channels') };
                if (ids.length > 0) config.dml.openids = ids;
                break;
            }
            case 'xiaomao': {
                const toks = [];
                document.querySelectorAll('#xiaomao_tokens_list .multi-cookie-row').forEach(row => { const v = (row.querySelector('.xiaomao-token-value')?.value || '').trim(); if (v) toks.push(v); });
                const single = (document.getElementById('xiaomao_token')?.value || '').trim();
                config.xiaomao = { enable: xiaomaoEnable ? xiaomaoEnable.checked : false, token: toks[0] || single, mt_version: (document.getElementById('xiaomao_mt_version')?.value || '').trim(), time: (document.getElementById('xiaomao_time')?.value || '').trim() || '09:00', push_channels: getTaskPushChannels('xiaomao_push_channels') };
                if (toks.length > 0) config.xiaomao.tokens = toks;
                break;
            }
            case 'ydwx': {
                const accs = [];
                document.querySelectorAll('#ydwx_accounts_list .multi-account-row').forEach(row => {
                    const dp = (row.querySelector('.ydwx-dp-value')?.value || '').trim();
                    const tk = (row.querySelector('.ydwx-token-value')?.value || '').trim();
                    if (dp || tk) accs.push({ device_params: dp, token: tk });
                });
                const singleDp = (document.getElementById('ydwx_device_params')?.value || '').trim();
                const singleTk = (document.getElementById('ydwx_token')?.value || '').trim();
                config.ydwx = { enable: ydwxEnable ? ydwxEnable.checked : false, device_params: accs[0]?.device_params || singleDp, token: accs[0]?.token || singleTk, time: (document.getElementById('ydwx_time')?.value || '').trim() || '06:00', push_channels: getTaskPushChannels('ydwx_push_channels') };
                if (accs.length > 0) config.ydwx.accounts = accs;
                break;
            }
            case 'xingkong': {
                const accs = [];
                document.querySelectorAll('#xingkong_accounts_list .multi-account-row').forEach(row => {
                    const u = (row.querySelector('.xingkong-user-value')?.value || '').trim();
                    const p = (row.querySelector('.xingkong-pwd-value')?.value || '').trim();
                    if (u || p) accs.push({ username: u, password: p });
                });
                const singleU = (document.getElementById('xingkong_username')?.value || '').trim();
                const singleP = (document.getElementById('xingkong_password')?.value || '').trim();
                config.xingkong = { enable: xingkongEnable ? xingkongEnable.checked : false, username: accs[0]?.username || singleU, password: accs[0]?.password || singleP, time: (document.getElementById('xingkong_time')?.value || '').trim() || '07:30', push_channels: getTaskPushChannels('xingkong_push_channels') };
                if (accs.length > 0) config.xingkong.accounts = accs;
                break;
            }
            case 'qtw': {
                const cks = [];
                document.querySelectorAll('#qtw_cookies_list .multi-cookie-row').forEach(row => { const v = (row.querySelector('.qtw-cookie-value')?.value || '').trim(); if (v) cks.push(v); });
                const single = (document.getElementById('qtw_cookie')?.value || '').trim();
                config.qtw = { enable: qtwEnable ? qtwEnable.checked : false, cookie: cks[0] || single, time: (document.getElementById('qtw_time')?.value || '').trim() || '01:30', push_channels: getTaskPushChannels('qtw_push_channels') };
                if (cks.length > 0) config.qtw.cookies = cks;
                break;
            }
            case 'freenom': {
                const accounts = [];
                document.querySelectorAll('#freenom_accounts_list .multi-account-row').forEach(row => {
                    const email = (row.querySelector('.freenom-account-email')?.value || '').trim();
                    const password = (row.querySelector('.freenom-account-password')?.value || '').trim();
                    if (email || password) accounts.push({ email, password });
                });
                config.freenom = {
                    enable: freenomEnable ? freenomEnable.checked : false,
                    time: (document.getElementById('freenom_time')?.value || '').trim() || '07:33',
                    push_channels: getTaskPushChannels('freenom_push_channels')
                };
                if (accounts.length > 0) config.freenom.accounts = accounts;
                break;
            }
            case 'weather': {
                config.weather = {
                    enable: weatherEnable ? weatherEnable.checked : false,
                    city_code: (document.getElementById('weather_city_code')?.value || '').trim(),
                    time: (document.getElementById('weather_time')?.value || '').trim() || '07:30',
                    push_channels: getTaskPushChannels('weather_push_channels')
                };
                break;
            }
            case 'kuake': {
                const cks = [];
                document.querySelectorAll('#kuake_cookies_list .multi-cookie-row').forEach(row => {
                    const v = (row.querySelector('.kuake-cookie-value')?.value || '').trim();
                    if (v) cks.push(v);
                });
                const single = (document.getElementById('kuake_cookie')?.value || '').trim();
                config.kuake = {
                    enable: kuakeEnable ? kuakeEnable.checked : false,
                    cookie: cks[0] || single,
                    time: (document.getElementById('kuake_time')?.value || '').trim() || '02:00',
                    push_channels: getTaskPushChannels('kuake_push_channels')
                };
                if (cks.length > 0) config.kuake.cookies = cks;
                break;
            }
            case 'kjwj': {
                const accs = [];
                document.querySelectorAll('#kjwj_accounts_list .multi-account-row').forEach(row => {
                    const u = (row.querySelector('.kjwj-account-username')?.value || '').trim();
                    const p = (row.querySelector('.kjwj-account-password')?.value || '').trim();
                    if (u || p) accs.push({ username: u, password: p });
                });
                config.kjwj = {
                    enable: kjwjEnable ? kjwjEnable.checked : false,
                    time: (document.getElementById('kjwj_time')?.value || '').trim() || '07:30',
                    push_channels: getTaskPushChannels('kjwj_push_channels')
                };
                if (accs.length > 0) config.kjwj.accounts = accs;
                break;
            }
            case 'fr': {
                config.fr = {
                    enable: frEnable ? frEnable.checked : false,
                    cookie: (document.getElementById('fr_cookie')?.value || '').trim(),
                    time: (document.getElementById('fr_time')?.value || '').trim() || '06:30',
                    push_channels: getTaskPushChannels('fr_push_channels')
                };
                break;
            }
            case 'nine_nine_nine': {
                const toks = [];
                document.querySelectorAll('#nine_nine_nine_tokens_list .multi-cookie-row').forEach(row => {
                    const v = (row.querySelector('.nine-token-value')?.value || '').trim();
                    if (v) toks.push(v);
                });
                config.nine_nine_nine = {
                    enable: nineEnable ? nineEnable.checked : false,
                    time: (document.getElementById('nine_nine_nine_time')?.value || '').trim() || '15:15',
                    push_channels: getTaskPushChannels('nine_nine_nine_push_channels')
                };
                if (toks.length > 0) config.nine_nine_nine.tokens = toks;
                break;
            }
            case 'zgfc': {
                const toks = [];
                document.querySelectorAll('#zgfc_tokens_list .multi-cookie-row').forEach(row => {
                    const v = (row.querySelector('.zgfc-token-value')?.value || '').trim();
                    if (v) toks.push(v);
                });
                config.zgfc = {
                    enable: zgfcEnable ? zgfcEnable.checked : false,
                    time: (document.getElementById('zgfc_time')?.value || '').trim() || '08:00',
                    push_channels: getTaskPushChannels('zgfc_push_channels')
                };
                if (toks.length > 0) config.zgfc.tokens = toks;
                break;
            }
            case 'ssq_500w': {
                config.ssq_500w = {
                    enable: ssqEnable ? ssqEnable.checked : false,
                    time: (document.getElementById('ssq_500w_time')?.value || '').trim() || '21:30',
                    push_channels: getTaskPushChannels('ssq_500w_push_channels')
                };
                break;
            }
            case 'log_cleanup':
                config.log_cleanup = {
                    enable: document.getElementById('log_cleanup_enable')?.checked ?? true,
                    time: (document.getElementById('log_cleanup_time')?.value || '').trim() || '02:10',
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
            case 'ai_assistant': {
                const aiEnableEl = document.getElementById('ai_assistant_enable');
                config.ai_assistant = {
                    enable: aiEnableEl ? aiEnableEl.checked : false,
                    provider: (document.getElementById('ai_assistant_provider')?.value || 'openai').trim(),
                    api_base: (document.getElementById('ai_assistant_api_base')?.value || '').trim(),
                    api_key: (document.getElementById('ai_assistant_api_key')?.value || '').trim(),
                    model: (document.getElementById('ai_assistant_model')?.value || 'gpt-4o-mini').trim(),
                    embedding_model: (document.getElementById('ai_assistant_embedding_model')?.value || 'text-embedding-3-small').trim(),
                    chroma_persist_dir: (document.getElementById('ai_assistant_chroma_persist_dir')?.value || 'data/ai_assistant_chroma').trim(),
                    rag_index_refresh_interval_seconds: parseInt(document.getElementById('ai_assistant_rag_index_refresh_interval_seconds')?.value || '1800', 10) || 1800,
                    rate_limit_per_minute: parseInt(document.getElementById('ai_assistant_rate_limit_per_minute')?.value || '10', 10) || 10,
                    max_history_rounds: parseInt(document.getElementById('ai_assistant_max_history_rounds')?.value || '10', 10) || 10
                };
                break;
            }
            case 'push_channel':
                config.push_channel = [];
                const channelItems = document.querySelectorAll('.push-channel-item');
                channelItems.forEach(item => {
                    const channel = {
                        name: item.querySelector('.channel-name').value.trim(),
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

        // 微博监控配置
        config.weibo = {
            enable: weiboEnable ? weiboEnable.checked : true,
            cookie: document.getElementById('weibo_cookie').value.trim(),
            uids: document.getElementById('weibo_uids').value.trim(),
            concurrency: parseInt(document.getElementById('weibo_concurrency').value) || 3,
            monitor_interval_seconds: parseInt(document.getElementById('weibo_monitor_interval_seconds')?.value) || 300,
            push_channels: getTaskPushChannels('weibo_push_channels')
        };

        // 微博超话签到配置（含多 Cookie）
        const weiboChaohuaCookies = [];
        document.querySelectorAll('#weibo_chaohua_cookies_list .multi-cookie-row').forEach(row => {
            const val = (row.querySelector('.weibo-chaohua-cookie-value')?.value || '').trim();
            if (val) weiboChaohuaCookies.push(val);
        });
        const singleWeiboChaohuaCookie = (document.getElementById('weibo_chaohua_cookie')?.value || '').trim();
        config.weibo_chaohua = {
            enable: weiboChaohuaEnable ? weiboChaohuaEnable.checked : false,
            cookie: weiboChaohuaCookies.length > 0 ? weiboChaohuaCookies[0] : singleWeiboChaohuaCookie,
            time: (document.getElementById('weibo_chaohua_time')?.value || '').trim() || '23:45',
            push_channels: getTaskPushChannels('weibo_chaohua_push_channels')
        };
        if (weiboChaohuaCookies.length > 0) config.weibo_chaohua.cookies = weiboChaohuaCookies;

        // 虎牙配置
        config.huya = {
            enable: huyaEnable ? huyaEnable.checked : true,
            rooms: document.getElementById('huya_rooms').value.trim(),
            concurrency: parseInt(document.getElementById('huya_concurrency').value) || 7,
            monitor_interval_seconds: parseInt(document.getElementById('huya_monitor_interval_seconds')?.value) || 65,
            push_channels: getTaskPushChannels('huya_push_channels')
        };

        // 哔哩哔哩 / 抖音 / 斗鱼 / 小红书配置
        config.bilibili = collectSectionConfig('bilibili').bilibili;
        config.douyin = collectSectionConfig('douyin').douyin;
        config.douyu = collectSectionConfig('douyu').douyu;
        config.xhs = collectSectionConfig('xhs').xhs;

        // 雨云签到配置（含多账号、自动续费）
        const rainyunAccounts = [];
        document.querySelectorAll('#rainyun_accounts_list .multi-account-row').forEach(row => {
            const username = (row.querySelector('.rainyun-account-username')?.value || '').trim();
            const password = (row.querySelector('.rainyun-account-password')?.value || '').trim();
            const api_key = (row.querySelector('.rainyun-account-api-key')?.value || '').trim();
            if (username || password) rainyunAccounts.push({ username, password, api_key });
        });
        const rainyunRenewIdsRaw = (document.getElementById('rainyun_renew_product_ids')?.value || '').trim();
        const rainyunRenewIds = rainyunRenewIdsRaw ? rainyunRenewIdsRaw.split(/[,\s]+/).map(s => parseInt(s, 10)).filter(n => !isNaN(n)) : [];
        config.rainyun = {
            enable: rainyunEnable ? rainyunEnable.checked : false,
            accounts: rainyunAccounts,
            time: (document.getElementById('rainyun_time')?.value || '').trim() || '08:30',
            push_channels: getTaskPushChannels('rainyun_push_channels'),
            auto_renew: (document.getElementById('rainyun_auto_renew')?.checked ?? true),
            renew_threshold_days: parseInt(document.getElementById('rainyun_renew_threshold_days')?.value || '7', 10) || 7,
            renew_product_ids: rainyunRenewIds.length > 0 ? rainyunRenewIds : []
        };

        // 恩山 / 天翼云盘 / 阿里云盘 / 什么值得买 / 值得买抽奖 / 富贵论坛（由 collectSectionConfig 合并到 config）
        config.enshan = collectSectionConfig('enshan').enshan;
        config.tyyun = collectSectionConfig('tyyun').tyyun;
        config.aliyun = collectSectionConfig('aliyun').aliyun;
        config.smzdm = collectSectionConfig('smzdm').smzdm;
        config.zdm_draw = collectSectionConfig('zdm_draw').zdm_draw;
        config.fg = collectSectionConfig('fg').fg;
        config.miui = collectSectionConfig('miui').miui;
        config.iqiyi = collectSectionConfig('iqiyi').iqiyi;
        config.lenovo = collectSectionConfig('lenovo').lenovo;
        config.lbly = collectSectionConfig('lbly').lbly;
        config.pinzan = collectSectionConfig('pinzan').pinzan;
        config.dml = collectSectionConfig('dml').dml;
        config.xiaomao = collectSectionConfig('xiaomao').xiaomao;
        config.ydwx = collectSectionConfig('ydwx').ydwx;
        config.xingkong = collectSectionConfig('xingkong').xingkong;
        config.qtw = collectSectionConfig('qtw').qtw;
        config.freenom = collectSectionConfig('freenom').freenom;
        config.weather = collectSectionConfig('weather').weather;
        config.kuake = collectSectionConfig('kuake').kuake;
        config.kjwj = collectSectionConfig('kjwj').kjwj;
        config.fr = collectSectionConfig('fr').fr;
        config.nine_nine_nine = collectSectionConfig('nine_nine_nine').nine_nine_nine;
        config.zgfc = collectSectionConfig('zgfc').zgfc;
        config.ssq_500w = collectSectionConfig('ssq_500w').ssq_500w;

        // 免打扰时段配置
        config.quiet_hours = {
            enable: quietHoursEnable.checked,
            start: document.getElementById('quiet_hours_start').value || '22:00',
            end: document.getElementById('quiet_hours_end').value || '08:00'
        };

        // AI 助手配置
        const aiEnableEl = document.getElementById('ai_assistant_enable');
        config.ai_assistant = {
            enable: aiEnableEl ? aiEnableEl.checked : false,
            provider: (document.getElementById('ai_assistant_provider')?.value || 'openai').trim(),
            api_base: (document.getElementById('ai_assistant_api_base')?.value || '').trim(),
            api_key: (document.getElementById('ai_assistant_api_key')?.value || '').trim(),
            model: (document.getElementById('ai_assistant_model')?.value || 'gpt-4o-mini').trim(),
            embedding_model: (document.getElementById('ai_assistant_embedding_model')?.value || 'text-embedding-3-small').trim(),
            chroma_persist_dir: (document.getElementById('ai_assistant_chroma_persist_dir')?.value || 'data/ai_assistant_chroma').trim(),
            rag_index_refresh_interval_seconds: parseInt(document.getElementById('ai_assistant_rag_index_refresh_interval_seconds')?.value || '1800', 10) || 1800,
            rate_limit_per_minute: parseInt(document.getElementById('ai_assistant_rate_limit_per_minute')?.value || '10', 10) || 10,
            max_history_rounds: parseInt(document.getElementById('ai_assistant_max_history_rounds')?.value || '10', 10) || 10
        };

        // 日志清理配置
        config.log_cleanup = collectSectionConfig('log_cleanup').log_cleanup;

        // 每日签到配置（含多账号）：多账号区仅收集非空行；单账号用单账号输入框
        const checkinAccounts = [];
        document.querySelectorAll('#checkin_accounts_list .multi-account-row').forEach(row => {
            const email = (row.querySelector('.checkin-account-email')?.value || '').trim();
            const password = (row.querySelector('.checkin-account-password')?.value || '').trim();
            if (email || password) checkinAccounts.push({ email, password });
        });
        const singleCheckinEmail = (document.getElementById('checkin_email')?.value || '').trim();
        const singleCheckinPassword = (document.getElementById('checkin_password')?.value || '').trim();
        const firstCheckin = checkinAccounts[0] || { email: singleCheckinEmail, password: singleCheckinPassword };
        config.checkin = {
            enable: checkinEnable ? checkinEnable.checked : false,
            email: firstCheckin.email,
            password: firstCheckin.password,
            time: (document.getElementById('checkin_time')?.value || '').trim() || '08:00',
            push_channels: getTaskPushChannels('checkin_push_channels')
        };
        if (checkinAccounts.length > 0) config.checkin.accounts = checkinAccounts;

        // 贴吧签到配置（含多 Cookie）：多 Cookie 区仅收集非空行
        const tiebaCookies = [];
        document.querySelectorAll('#tieba_cookies_list .multi-cookie-row').forEach(row => {
            const val = (row.querySelector('.tieba-cookie-value')?.value || '').trim();
            if (val) tiebaCookies.push(val);
        });
        const singleTiebaCookie = (document.getElementById('tieba_cookie')?.value || '').trim();
        config.tieba = {
            enable: tiebaEnable ? tiebaEnable.checked : false,
            cookie: tiebaCookies.length > 0 ? tiebaCookies[0] : singleTiebaCookie,
            time: (document.getElementById('tieba_time')?.value || '').trim() || '08:10',
            push_channels: getTaskPushChannels('tieba_push_channels')
        };
        if (tiebaCookies.length > 0) config.tieba.cookies = tiebaCookies;

        // 推送通道配置
        config.push_channel = [];
        const channelItems = document.querySelectorAll('.push-channel-item');
        channelItems.forEach(item => {
            const channel = {
                name: item.querySelector('.channel-name').value.trim(),
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
                document.dispatchEvent(new CustomEvent('config-saved'));
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
                document.dispatchEvent(new CustomEvent('config-saved'));
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
                document.dispatchEvent(new CustomEvent('config-saved'));
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

    // 微博超话多 Cookie：添加 Cookie
    const weiboChaohuaAddCookieBtn = document.getElementById('weibo_chaohua_add_cookie_btn');
    if (weiboChaohuaAddCookieBtn) {
        weiboChaohuaAddCookieBtn.addEventListener('click', function() {
            const container = document.getElementById('weibo_chaohua_cookies_list');
            if (!container) return;
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = `
                <div class="cookie-field">
                    <input type="text" class="form-input weibo-chaohua-cookie-value" placeholder="微博 Cookie（须包含 XSRF-TOKEN）">
                </div>
                <button type="button" class="btn btn-secondary row-remove weibo-chaohua-cookie-remove">删除</button>
            `;
            container.appendChild(row);
        });
    }
    // 微博超话多 Cookie：删除行（事件委托）
    const weiboChaohuaCookiesList = document.getElementById('weibo_chaohua_cookies_list');
    if (weiboChaohuaCookiesList) {
        weiboChaohuaCookiesList.addEventListener('click', function(e) {
            if (e.target.classList.contains('weibo-chaohua-cookie-remove')) {
                const row = e.target.closest('.multi-cookie-row');
                if (row && weiboChaohuaCookiesList.querySelectorAll('.multi-cookie-row').length > 1) row.remove();
            }
        });
    }

    // 雨云多账号：添加账号
    const rainyunAddAccountBtn = document.getElementById('rainyun_add_account_btn');
    if (rainyunAddAccountBtn) {
        rainyunAddAccountBtn.addEventListener('click', function() {
            const container = document.getElementById('rainyun_accounts_list');
            if (!container) return;
            const row = document.createElement('div');
            row.className = 'multi-account-row';
            row.innerHTML = `
                <div class="account-fields">
                    <input type="text" class="form-input rainyun-account-username" placeholder="用户名">
                    <input type="password" class="form-input rainyun-account-password" placeholder="密码">
                    <input type="password" class="form-input rainyun-account-api-key" placeholder="API Key（续费用，可选）">
                </div>
                <button type="button" class="btn btn-secondary row-remove rainyun-account-remove">删除</button>
            `;
            container.appendChild(row);
        });
    }
    // 雨云多账号：删除行（事件委托）
    const rainyunAccountsList = document.getElementById('rainyun_accounts_list');
    if (rainyunAccountsList) {
        rainyunAccountsList.addEventListener('click', function(e) {
            if (e.target.classList.contains('rainyun-account-remove')) {
                const row = e.target.closest('.multi-account-row');
                if (row && rainyunAccountsList.querySelectorAll('.multi-account-row').length > 1) row.remove();
            }
        });
    }

    // 恩山多 Cookie
    const enshanAddCookieBtn = document.getElementById('enshan_add_cookie_btn');
    if (enshanAddCookieBtn) {
        enshanAddCookieBtn.addEventListener('click', function() {
            const container = document.getElementById('enshan_cookies_list');
            if (!container) return;
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><input type="text" class="form-input enshan-cookie-value" placeholder="恩山 Cookie"></div><button type="button" class="btn btn-secondary row-remove enshan-cookie-remove">删除</button>';
            container.appendChild(row);
        });
    }
    const enshanCookiesList = document.getElementById('enshan_cookies_list');
    if (enshanCookiesList) {
        enshanCookiesList.addEventListener('click', function(e) {
            if (e.target.classList.contains('enshan-cookie-remove')) {
                const row = e.target.closest('.multi-cookie-row');
                if (row && enshanCookiesList.querySelectorAll('.multi-cookie-row').length > 1) row.remove();
            }
        });
    }

    // 天翼云盘多账号
    const tyyunAddAccountBtn = document.getElementById('tyyun_add_account_btn');
    if (tyyunAddAccountBtn) {
        tyyunAddAccountBtn.addEventListener('click', function() {
            const container = document.getElementById('tyyun_accounts_list');
            if (!container) return;
            const row = document.createElement('div');
            row.className = 'multi-account-row';
            row.innerHTML = '<div class="account-fields"><input type="text" class="form-input tyyun-account-username" placeholder="手机号"><input type="password" class="form-input tyyun-account-password" placeholder="密码"></div><button type="button" class="btn btn-secondary row-remove tyyun-account-remove">删除</button>';
            container.appendChild(row);
        });
    }
    const tyyunAccountsList = document.getElementById('tyyun_accounts_list');
    if (tyyunAccountsList) {
        tyyunAccountsList.addEventListener('click', function(e) {
            if (e.target.classList.contains('tyyun-account-remove')) {
                const row = e.target.closest('.multi-account-row');
                if (row && tyyunAccountsList.querySelectorAll('.multi-account-row').length > 1) row.remove();
            }
        });
    }

    // 阿里云盘多 Token
    const aliyunAddTokenBtn = document.getElementById('aliyun_add_token_btn');
    if (aliyunAddTokenBtn) {
        aliyunAddTokenBtn.addEventListener('click', function() {
            const container = document.getElementById('aliyun_refresh_tokens_list');
            if (!container) return;
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><input type="password" class="form-input aliyun-token-value" placeholder="refresh_token"></div><button type="button" class="btn btn-secondary row-remove aliyun-token-remove">删除</button>';
            container.appendChild(row);
        });
    }
    const aliyunTokensList = document.getElementById('aliyun_refresh_tokens_list');
    if (aliyunTokensList) {
        aliyunTokensList.addEventListener('click', function(e) {
            if (e.target.classList.contains('aliyun-token-remove')) {
                const row = e.target.closest('.multi-cookie-row');
                if (row && aliyunTokensList.querySelectorAll('.multi-cookie-row').length > 1) row.remove();
            }
        });
    }

    // 什么值得买多 Cookie
    const smzdmAddCookieBtn = document.getElementById('smzdm_add_cookie_btn');
    if (smzdmAddCookieBtn) {
        smzdmAddCookieBtn.addEventListener('click', function() {
            const container = document.getElementById('smzdm_cookies_list');
            if (!container) return;
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><input type="text" class="form-input smzdm-cookie-value" placeholder="值得买 Cookie"></div><button type="button" class="btn btn-secondary row-remove smzdm-cookie-remove">删除</button>';
            container.appendChild(row);
        });
    }
    const smzdmCookiesList = document.getElementById('smzdm_cookies_list');
    if (smzdmCookiesList) {
        smzdmCookiesList.addEventListener('click', function(e) {
            if (e.target.classList.contains('smzdm-cookie-remove')) {
                const row = e.target.closest('.multi-cookie-row');
                if (row && smzdmCookiesList.querySelectorAll('.multi-cookie-row').length > 1) row.remove();
            }
        });
    }
    // 值得买抽奖多 Cookie
    const zdmDrawAddCookieBtn = document.getElementById('zdm_draw_add_cookie_btn');
    if (zdmDrawAddCookieBtn) {
        zdmDrawAddCookieBtn.addEventListener('click', function() {
            const container = document.getElementById('zdm_draw_cookies_list');
            if (!container) return;
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><input type="text" class="form-input zdm-draw-cookie-value" placeholder="值得买 Cookie"></div><button type="button" class="btn btn-secondary row-remove zdm-draw-cookie-remove">删除</button>';
            container.appendChild(row);
        });
    }
    const zdmDrawCookiesList = document.getElementById('zdm_draw_cookies_list');
    if (zdmDrawCookiesList) {
        zdmDrawCookiesList.addEventListener('click', function(e) {
            if (e.target.classList.contains('zdm-draw-cookie-remove')) {
                const row = e.target.closest('.multi-cookie-row');
                if (row && zdmDrawCookiesList.querySelectorAll('.multi-cookie-row').length > 1) row.remove();
            }
        });
    }
    // 富贵论坛多 Cookie
    const fgAddCookieBtn = document.getElementById('fg_add_cookie_btn');
    if (fgAddCookieBtn) {
        fgAddCookieBtn.addEventListener('click', function() {
            const container = document.getElementById('fg_cookies_list');
            if (!container) return;
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><input type="text" class="form-input fg-cookie-value" placeholder="富贵论坛 Cookie"></div><button type="button" class="btn btn-secondary row-remove fg-cookie-remove">删除</button>';
            container.appendChild(row);
        });
    }
    const fgCookiesList = document.getElementById('fg_cookies_list');
    if (fgCookiesList) {
        fgCookiesList.addEventListener('click', function(e) {
            if (e.target.classList.contains('fg-cookie-remove')) {
                const row = e.target.closest('.multi-cookie-row');
                if (row && fgCookiesList.querySelectorAll('.multi-cookie-row').length > 1) row.remove();
            }
        });
    }

    // 小米社区多账号
    const miuiAddBtn = document.getElementById('miui_add_account_btn');
    if (miuiAddBtn) {
        miuiAddBtn.addEventListener('click', function() {
            const container = document.getElementById('miui_accounts_list');
            if (!container) return;
            const row = document.createElement('div');
            row.className = 'multi-account-row';
            row.innerHTML = '<div class="account-fields"><input type="text" class="form-input miui-account-value" placeholder="手机号"><input type="password" class="form-input miui-password-value" placeholder="密码"></div><button type="button" class="btn btn-secondary row-remove miui-account-remove">删除</button>';
            container.appendChild(row);
        });
    }
    const miuiAccountsList = document.getElementById('miui_accounts_list');
    if (miuiAccountsList) {
        miuiAccountsList.addEventListener('click', function(e) {
            if (e.target.classList.contains('miui-account-remove')) {
                const row = e.target.closest('.multi-account-row');
                if (row && miuiAccountsList.querySelectorAll('.multi-account-row').length > 1) row.remove();
            }
        });
    }
    // 爱奇艺多 Cookie
    const iqiyiAddBtn = document.getElementById('iqiyi_add_cookie_btn');
    if (iqiyiAddBtn) {
        iqiyiAddBtn.addEventListener('click', function() {
            const container = document.getElementById('iqiyi_cookies_list');
            if (!container) return;
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><input type="text" class="form-input iqiyi-cookie-value" placeholder="爱奇艺 Cookie"></div><button type="button" class="btn btn-secondary row-remove iqiyi-cookie-remove">删除</button>';
            container.appendChild(row);
        });
    }
    const iqiyiCookiesList = document.getElementById('iqiyi_cookies_list');
    if (iqiyiCookiesList) {
        iqiyiCookiesList.addEventListener('click', function(e) {
            if (e.target.classList.contains('iqiyi-cookie-remove')) {
                const row = e.target.closest('.multi-cookie-row');
                if (row && iqiyiCookiesList.querySelectorAll('.multi-cookie-row').length > 1) row.remove();
            }
        });
    }
    // 联想乐豆多 token
    const lenovoAddBtn = document.getElementById('lenovo_add_token_btn');
    if (lenovoAddBtn) {
        lenovoAddBtn.addEventListener('click', function() {
            const container = document.getElementById('lenovo_access_tokens_list');
            if (!container) return;
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><input type="text" class="form-input lenovo-token-value" placeholder="access_token"></div><button type="button" class="btn btn-secondary row-remove lenovo-token-remove">删除</button>';
            container.appendChild(row);
        });
    }
    const lenovoTokensList = document.getElementById('lenovo_access_tokens_list');
    if (lenovoTokensList) {
        lenovoTokensList.addEventListener('click', function(e) {
            if (e.target.classList.contains('lenovo-token-remove')) {
                const row = e.target.closest('.multi-cookie-row');
                if (row && lenovoTokensList.querySelectorAll('.multi-cookie-row').length > 1) row.remove();
            }
        });
    }
    // 丽宝乐园多请求体
    const lblyAddBtn = document.getElementById('lbly_add_body_btn');
    if (lblyAddBtn) {
        lblyAddBtn.addEventListener('click', function() {
            const container = document.getElementById('lbly_request_bodies_list');
            if (!container) return;
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><textarea class="form-input lbly-body-value" rows="2" placeholder="请求体 JSON"></textarea></div><button type="button" class="btn btn-secondary row-remove lbly-body-remove">删除</button>';
            container.appendChild(row);
        });
    }
    const lblyBodiesList = document.getElementById('lbly_request_bodies_list');
    if (lblyBodiesList) {
        lblyBodiesList.addEventListener('click', function(e) {
            if (e.target.classList.contains('lbly-body-remove')) {
                const row = e.target.closest('.multi-cookie-row');
                if (row && lblyBodiesList.querySelectorAll('.multi-cookie-row').length > 1) row.remove();
            }
        });
    }
    // 品赞多账号
    const pinzanAddBtn = document.getElementById('pinzan_add_account_btn');
    if (pinzanAddBtn) {
        pinzanAddBtn.addEventListener('click', function() {
            const container = document.getElementById('pinzan_accounts_list');
            if (!container) return;
            const row = document.createElement('div');
            row.className = 'multi-account-row';
            row.innerHTML = '<div class="account-fields"><input type="text" class="form-input pinzan-account-value" placeholder="账号"><input type="password" class="form-input pinzan-password-value" placeholder="密码"></div><button type="button" class="btn btn-secondary row-remove pinzan-account-remove">删除</button>';
            container.appendChild(row);
        });
    }
    const pinzanAccountsList = document.getElementById('pinzan_accounts_list');
    if (pinzanAccountsList) {
        pinzanAccountsList.addEventListener('click', function(e) {
            if (e.target.classList.contains('pinzan-account-remove')) {
                const row = e.target.closest('.multi-account-row');
                if (row && pinzanAccountsList.querySelectorAll('.multi-account-row').length > 1) row.remove();
            }
        });
    }
    // 达美乐多 openid
    const dmlAddBtn = document.getElementById('dml_add_openid_btn');
    if (dmlAddBtn) {
        dmlAddBtn.addEventListener('click', function() {
            const container = document.getElementById('dml_openids_list');
            if (!container) return;
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><input type="text" class="form-input dml-openid-value" placeholder="openid"></div><button type="button" class="btn btn-secondary row-remove dml-openid-remove">删除</button>';
            container.appendChild(row);
        });
    }
    const dmlOpenidsList = document.getElementById('dml_openids_list');
    if (dmlOpenidsList) {
        dmlOpenidsList.addEventListener('click', function(e) {
            if (e.target.classList.contains('dml-openid-remove')) {
                const row = e.target.closest('.multi-cookie-row');
                if (row && dmlOpenidsList.querySelectorAll('.multi-cookie-row').length > 1) row.remove();
            }
        });
    }
    // 小茅预约多 token
    const xiaomaoAddBtn = document.getElementById('xiaomao_add_token_btn');
    if (xiaomaoAddBtn) {
        xiaomaoAddBtn.addEventListener('click', function() {
            const container = document.getElementById('xiaomao_tokens_list');
            if (!container) return;
            const row = document.createElement('div');
            row.className = 'multi-cookie-row';
            row.innerHTML = '<div class="cookie-field"><input type="text" class="form-input xiaomao-token-value" placeholder="省份,城市,经度,纬度,设备id,token,MT-Token-Wap"></div><button type="button" class="btn btn-secondary row-remove xiaomao-token-remove">删除</button>';
            container.appendChild(row);
        });
    }
    const xiaomaoTokensList = document.getElementById('xiaomao_tokens_list');
    if (xiaomaoTokensList) {
        xiaomaoTokensList.addEventListener('click', function(e) {
            if (e.target.classList.contains('xiaomao-token-remove')) {
                const row = e.target.closest('.multi-cookie-row');
                if (row && xiaomaoTokensList.querySelectorAll('.multi-cookie-row').length > 1) row.remove();
            }
        });
    }
    // 一点万象多账号
    const ydwxAddBtn = document.getElementById('ydwx_add_account_btn');
    if (ydwxAddBtn) ydwxAddBtn.addEventListener('click', function() {
        const c = document.getElementById('ydwx_accounts_list');
        if (!c) return;
        const row = document.createElement('div');
        row.className = 'multi-account-row';
        row.innerHTML = '<div class="account-fields"><input type="text" class="form-input ydwx-dp-value" placeholder="deviceParams"><input type="text" class="form-input ydwx-token-value" placeholder="token"></div><button type="button" class="btn btn-secondary row-remove ydwx-account-remove">删除</button>';
        c.appendChild(row);
    });
    const ydwxList = document.getElementById('ydwx_accounts_list');
    if (ydwxList) ydwxList.addEventListener('click', function(e) {
        if (e.target.classList.contains('ydwx-account-remove')) {
            const row = e.target.closest('.multi-account-row');
            if (row && ydwxList.querySelectorAll('.multi-account-row').length > 1) row.remove();
        }
    });
    // 星空代理多账号
    const xingkongAddBtn = document.getElementById('xingkong_add_account_btn');
    if (xingkongAddBtn) xingkongAddBtn.addEventListener('click', function() {
        const c = document.getElementById('xingkong_accounts_list');
        if (!c) return;
        const row = document.createElement('div');
        row.className = 'multi-account-row';
        row.innerHTML = '<div class="account-fields"><input type="text" class="form-input xingkong-user-value" placeholder="用户名"><input type="password" class="form-input xingkong-pwd-value" placeholder="密码"></div><button type="button" class="btn btn-secondary row-remove xingkong-account-remove">删除</button>';
        c.appendChild(row);
    });
    const xingkongList = document.getElementById('xingkong_accounts_list');
    if (xingkongList) xingkongList.addEventListener('click', function(e) {
        if (e.target.classList.contains('xingkong-account-remove')) {
            const row = e.target.closest('.multi-account-row');
            if (row && xingkongList.querySelectorAll('.multi-account-row').length > 1) row.remove();
        }
    });
    // 千图网多 Cookie
    const qtwAddBtn = document.getElementById('qtw_add_cookie_btn');
    if (qtwAddBtn) qtwAddBtn.addEventListener('click', function() {
        const c = document.getElementById('qtw_cookies_list');
        if (!c) return;
        const row = document.createElement('div');
        row.className = 'multi-cookie-row';
        row.innerHTML = '<div class="cookie-field"><input type="text" class="form-input qtw-cookie-value" placeholder="千图网 Cookie"></div><button type="button" class="btn btn-secondary row-remove qtw-cookie-remove">删除</button>';
        c.appendChild(row);
    });
    const qtwList = document.getElementById('qtw_cookies_list');
    if (qtwList) qtwList.addEventListener('click', function(e) {
        if (e.target.classList.contains('qtw-cookie-remove')) {
            const row = e.target.closest('.multi-cookie-row');
            if (row && qtwList.querySelectorAll('.multi-cookie-row').length > 1) row.remove();
        }
    });

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

    // 监听 config-saved（如 AI 助手 apply-action 成功后），刷新配置表单以反映最新状态
    document.addEventListener('config-saved', async function () {
        await loadConfig();
        if (textView && textView.style.display !== 'none') {
            await loadYamlConfig();
        }
    });
});
