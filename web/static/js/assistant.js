/**
 * AI 助手 - 悬浮「问 AI」按钮与类 DeepSeek 对话窗口
 * 在 config、tasks、data 页面加载，自动初始化
 */
(function () {
    const API = {
        status: '/api/assistant/status',
        conversations: '/api/assistant/conversations',
        chat: '/api/assistant/chat',
        applyAction: '/api/assistant/apply-action',
        reindex: '/api/assistant/reindex',
    };
    let aiEnabled = false;
    let currentConversationId = null;
    let conversations = [];
    const suggestedConfigs = {};

    async function checkStatus() {
        try {
            const r = await fetch(API.status, { credentials: 'same-origin' });
            const d = await r.json();
            aiEnabled = !!d.enabled;
        } catch (e) {
            aiEnabled = false;
        }
        return aiEnabled;
    }

    function updateButtonFromStatus() {
        const btn = document.getElementById('askAiBtn');
        if (!btn) return;
        if (aiEnabled) {
            btn.style.opacity = '1';
            btn.title = '问 AI';
        } else {
            btn.style.opacity = '0.6';
            btn.title = 'AI 助手未启用，请在 config.yml 配置 ai_assistant.enable 并安装 uv sync --extra ai';
        }
    }

    function createFloatingButton() {
        if (document.getElementById('askAiBtn')) return;
        const btn = document.createElement('button');
        btn.id = 'askAiBtn';
        btn.className = 'assistant-fab';
        btn.title = '问 AI';
        btn.innerHTML = '🤖 问 AI';
        btn.style.cssText = `
            position: fixed; bottom: 28px; right: 86px; z-index: 9998;
            padding: 12px 20px; border-radius: 24px; border: none;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; font-size: 14px; font-weight: 500;
            cursor: pointer; box-shadow: 0 4px 14px rgba(102,126,234,0.4);
            transition: transform 0.2s, box-shadow 0.2s;
        `;
        btn.onmouseenter = () => { btn.style.transform = 'scale(1.05)'; btn.style.boxShadow = '0 6px 20px rgba(102,126,234,0.5)'; };
        btn.onmouseleave = () => { btn.style.transform = 'scale(1)'; btn.style.boxShadow = '0 4px 14px rgba(102,126,234,0.4)'; };
        btn.onclick = () => togglePanel();
        document.body.appendChild(btn);
    }

    function createPanel() {
        if (document.getElementById('assistantPanel')) return;
        const panel = document.createElement('div');
        panel.id = 'assistantPanel';
        const styleEl = document.createElement('style');
        styleEl.textContent = `
            .assistant-dots{display:inline-flex;align-items:center;gap:4px;}
            .assistant-dots span{width:6px;height:6px;border-radius:50%;background:#667eea;animation:adot 1.4s infinite ease-in-out both;}
            .assistant-dots span:nth-child(1){animation-delay:0s}
            .assistant-dots span:nth-child(2){animation-delay:.2s}
            .assistant-dots span:nth-child(3){animation-delay:.4s}
            @keyframes adot{0%,80%,100%{transform:scale(0.6);opacity:0.5}40%{transform:scale(1);opacity:1}}
        `;
        document.head.appendChild(styleEl);
        panel.innerHTML = `
            <div class="assistant-panel-backdrop" id="assistantBackdrop"></div>
            <div class="assistant-panel-main" style="
                position: fixed; top: 50%; left: 50%; width: 420px; max-width: 95vw; height: 85vh;
                background: #fff; box-shadow: 0 10px 40px rgba(0,0,0,0.2); z-index: 10000;
                display: flex; flex-direction: column;
                transform: translate(-50%, -50%) scale(0.95); opacity: 0; pointer-events: none;
                transition: transform 0.3s ease, opacity 0.3s ease;
                border-radius: 12px; overflow: hidden;
            ">
                <div class="assistant-header" style="
                    padding: 16px; border-bottom: 1px solid #e2e8f0; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;
                ">
                    <h3 style="margin: 0; font-size: 16px;">🤖 AI 助手</h3>
                    <div style="display: flex; gap: 8px;">
                        <button id="assistantNewChat" class="btn btn-secondary" style="padding: 6px 12px; font-size: 12px;">新建</button>
                        <button id="assistantClose" class="btn btn-secondary" style="padding: 6px 12px; font-size: 12px;">关闭</button>
                    </div>
                </div>
                <div class="assistant-sidebar" style="
                    padding: 12px; border-bottom: 1px solid #e2e8f0; max-height: 120px; overflow-y: auto; flex-shrink: 0;
                ">
                    <div id="assistantConversationList" style="display: flex; flex-wrap: wrap; gap: 8px;"></div>
                </div>
                <div class="assistant-messages" id="assistantMessages" style="
                    flex: 1; overflow-y: auto; padding: 16px; min-height: 200px;
                "></div>
                <div class="assistant-input-wrap" style="
                    padding: 16px; border-top: 1px solid #e2e8f0; flex-shrink: 0;
                ">
                    <div style="display: flex; gap: 8px;">
                        <input type="text" id="assistantInput" placeholder="输入问题，支持配置、日志、数据相关..." style="
                            flex: 1; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 14px;
                        ">
                        <button id="assistantSend" class="btn btn-primary" style="padding: 10px 20px;">发送</button>
                    </div>
                    <p style="margin: 8px 0 0; font-size: 12px; color: #64748b;">支持配置生成、日志诊断、数据洞察、当前状态查询</p>
                </div>
            </div>
        `;
        const backdrop = panel.querySelector('.assistant-panel-backdrop');
        const main = panel.querySelector('.assistant-panel-main');
        backdrop.style.cssText = 'position: fixed; inset: 0; background: rgba(0,0,0,0.2); z-index: 9999; display: none;';
        backdrop.onclick = () => closePanel();
        document.body.appendChild(panel);

        document.getElementById('assistantClose').onclick = closePanel;
        document.getElementById('assistantNewChat').onclick = newConversation;
        document.getElementById('assistantSend').onclick = sendMessage;
        document.getElementById('assistantInput').onkeydown = (e) => { if (e.key === 'Enter') sendMessage(); };
    }

    function togglePanel() {
        const panel = document.getElementById('assistantPanel');
        if (!panel) return;
        const main = panel.querySelector('.assistant-panel-main');
        const backdrop = panel.querySelector('.assistant-panel-backdrop');
        if (backdrop.style.display === 'block') {
            closePanel();
        } else {
            main.style.transform = 'translate(-50%, -50%) scale(1)';
            main.style.opacity = '1';
            main.style.pointerEvents = 'auto';
            backdrop.style.display = 'block';
            loadConversations();
        }
    }

    function closePanel() {
        const panel = document.getElementById('assistantPanel');
        if (!panel) return;
        const main = panel.querySelector('.assistant-panel-main');
        const backdrop = panel.querySelector('.assistant-panel-backdrop');
        main.style.transform = 'translate(-50%, -50%) scale(0.95)';
        main.style.opacity = '0';
        main.style.pointerEvents = 'none';
        backdrop.style.display = 'none';
    }

    async function loadConversations() {
        if (!aiEnabled) return;
        try {
            const r = await fetch(API.conversations, { credentials: 'same-origin' });
            const d = await r.json();
            conversations = d.conversations || [];
            renderConversationList();
            if (currentConversationId) {
                const mr = await fetch(`/api/assistant/conversations/${currentConversationId}/messages`, { credentials: 'same-origin' });
                const md = await mr.json();
                renderMessages(md.messages || []);
            } else if (conversations.length > 0) {
                currentConversationId = conversations[0].id;
                renderConversationList();
                const mr = await fetch(`/api/assistant/conversations/${currentConversationId}/messages`, { credentials: 'same-origin' });
                const md = await mr.json();
                renderMessages(md.messages || []);
            } else {
                renderMessages([]);
            }
        } catch (e) {
            console.error('加载会话失败', e);
            renderMessages([]);
        }
    }

    function renderConversationList() {
        const list = document.getElementById('assistantConversationList');
        if (!list) return;
        list.innerHTML = conversations.map(c => `
            <div class="conv-item-wrap" data-id="${c.id}" style="display:flex;align-items:center;gap:4px;">
                <button class="conv-item ${c.id === currentConversationId ? 'active' : ''}" style="
                    padding: 6px 12px; border-radius: 8px; border: 1px solid #e2e8f0;
                    background: ${c.id === currentConversationId ? '#eff6ff' : '#fff'};
                    cursor: pointer; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 120px; flex:1; text-align:left;
                ">${(c.title || '新对话').slice(0, 12)}${(c.title || '').length > 12 ? '..' : ''}</button>
                <button class="conv-delete-btn" title="删除对话" style="padding:4px;border:none;background:transparent;cursor:pointer;color:#94a3b8;font-size:14px;line-height:1;">×</button>
            </div>
        `).join('');
        list.querySelectorAll('.conv-item').forEach(el => {
            el.onclick = (e) => { e.stopPropagation(); switchConversation(el.closest('.conv-item-wrap').dataset.id); };
        });
        list.querySelectorAll('.conv-delete-btn').forEach(btn => {
            btn.onclick = (e) => {
                e.stopPropagation();
                const wrap = btn.closest('.conv-item-wrap');
                const id = wrap?.dataset.id;
                if (id) deleteConversation(id);
            };
        });
    }

    async function deleteConversation(convId) {
        if (!confirm('确定删除该对话？')) return;
        try {
            const r = await fetch(`/api/assistant/conversations/${convId}`, {
                method: 'DELETE',
                credentials: 'same-origin',
            });
            const d = await r.json();
            if (d.error) {
                if (typeof showToast === 'function') showToast(d.error, 'error');
                else alert(d.error);
            } else {
                if (currentConversationId === convId) {
                    currentConversationId = null;
                    renderMessages([]);
                }
                conversations = conversations.filter(c => c.id !== convId);
                if (conversations.length > 0 && !currentConversationId) {
                    currentConversationId = conversations[0].id;
                    const mr = await fetch(`/api/assistant/conversations/${currentConversationId}/messages`, { credentials: 'same-origin' });
                    const md = await mr.json();
                    renderMessages(md.messages || []);
                }
                renderConversationList();
                if (typeof showToast === 'function') showToast('已删除');
            }
        } catch (e) {
            if (typeof showToast === 'function') showToast('删除失败: ' + e.message, 'error');
            else alert('删除失败: ' + e.message);
        }
    }

    async function switchConversation(id) {
        currentConversationId = id;
        renderConversationList();
        try {
            const r = await fetch(`/api/assistant/conversations/${id}/messages`, { credentials: 'same-origin' });
            const d = await r.json();
            renderMessages(d.messages || []);
        } catch (e) {
            renderMessages([]);
        }
    }

    async function newConversation() {
        try {
            const r = await fetch(API.conversations, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: '新对话' }),
                credentials: 'same-origin',
            });
            const d = await r.json();
            currentConversationId = d.conversation_id;
            loadConversations();
            document.getElementById('assistantMessages').innerHTML = '';
        } catch (e) {
            console.error('新建会话失败', e);
        }
    }

    function renderMessages(msgs) {
        const container = document.getElementById('assistantMessages');
        if (!container) return;
        if (!msgs || msgs.length === 0) {
            container.innerHTML = '<div style="color:#94a3b8;text-align:center;padding:24px;">开始对话吧，可询问配置、日志、数据相关问题</div>';
            return;
        }
        container.innerHTML = msgs.map(m => `
            <div class="msg ${m.role}" style="margin-bottom:12px;">
                <div style="font-size:12px;color:#64748b;margin-bottom:4px;">${m.role === 'user' ? '你' : 'AI'}</div>
                <div style="padding:10px 14px;border-radius:8px;background:${m.role === 'user' ? '#f1f5f9' : '#eff6ff'};white-space:pre-wrap;">${escapeHtml(m.content)}</div>
            </div>
        `).join('');
        container.scrollTop = container.scrollHeight;
    }

    function escapeHtml(s) {
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    function showConfirmExecuteModal(sa) {
        if (!sa || sa.type !== 'confirm_execute') return;
        const existing = document.getElementById('assistantConfirmModal');
        if (existing) existing.remove();
        const modal = document.createElement('div');
        modal.id = 'assistantConfirmModal';
        modal.style.cssText = 'position:fixed;inset:0;z-index:10001;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.4);';
        modal.innerHTML = `
            <div style="background:#fff;border-radius:12px;padding:24px;max-width:360px;box-shadow:0 10px 40px rgba(0,0,0,0.2);">
                <h4 style="margin:0 0 12px;font-size:16px;">${escapeHtml(sa.title || '确认执行')}</h4>
                <p style="margin:0 0 20px;color:#64748b;font-size:14px;line-height:1.5;">${escapeHtml(sa.description || '')}</p>
                <div style="display:flex;gap:12px;justify-content:flex-end;">
                    <button class="btn btn-secondary confirm-cancel-btn" style="padding:8px 16px;">取消</button>
                    <button class="btn btn-primary confirm-ok-btn" style="padding:8px 16px;">确认</button>
                </div>
            </div>
        `;
        modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
        modal.querySelector('.confirm-cancel-btn').onclick = () => modal.remove();
        modal.querySelector('.confirm-ok-btn').onclick = async () => {
            modal.querySelector('.confirm-ok-btn').disabled = true;
            modal.querySelector('.confirm-ok-btn').textContent = '执行中...';
            const payload = { action: sa.action };
            if (sa.action === 'config_patch') {
                payload.platform_key = sa.platform_key;
                payload.list_key = sa.list_key;
                payload.operation = sa.operation;
                payload.value = sa.value;
            } else if (sa.action === 'run_task') {
                payload.task_id = sa.task_id;
            } else {
                payload.platform_key = sa.platform_key;
                payload.enable = sa.enable;
            }
            try {
                const r = await fetch(API.applyAction, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                    credentials: 'same-origin',
                });
                const d = await r.json();
                modal.remove();
                if (d.error) {
                    if (typeof showToast === 'function') showToast(d.error, 'error');
                    else alert(d.error);
                } else {
                    if (typeof showToast === 'function') showToast(d.message || '操作成功');
                    else alert(d.message || '操作成功');
                    document.dispatchEvent(new CustomEvent('config-saved'));
                }
            } catch (e) {
                modal.querySelector('.confirm-ok-btn').disabled = false;
                modal.querySelector('.confirm-ok-btn').textContent = '确认';
                if (typeof showToast === 'function') showToast('请求失败: ' + e.message, 'error');
                else alert('请求失败: ' + e.message);
            }
        };
        document.body.appendChild(modal);
    }

    async function sendMessage() {
        const input = document.getElementById('assistantInput');
        const sendBtn = document.getElementById('assistantSend');
        const msg = (input?.value || '').trim();
        if (!msg || !aiEnabled) return;
        input.value = '';
        input.disabled = true;
        if (sendBtn) { sendBtn.disabled = true; sendBtn.textContent = '处理中...'; }

        if (!currentConversationId) {
            await newConversation();
        }
        const container = document.getElementById('assistantMessages');
        const placeholder = container.querySelector('.empty-hint');
        if (placeholder) placeholder.remove();
        container.innerHTML += `<div class="msg user"><div style="font-size:12px;color:#64748b;">你</div><div style="padding:10px 14px;border-radius:8px;background:#f1f5f9;">${escapeHtml(msg)}</div></div>`;
        container.innerHTML += `<div class="msg assistant assistant-loading"><div style="font-size:12px;color:#64748b;">AI</div><div class="assistant-reply" style="padding:10px 14px;border-radius:8px;background:#eff6ff;display:flex;align-items:center;gap:8px;"><span class="assistant-dots"><span></span><span></span><span></span></span><span>正在处理...</span></div></div>`;
        container.scrollTop = container.scrollHeight;

        try {
            const r = await fetch(API.chat, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: msg, conversation_id: currentConversationId, context: 'all' }),
                credentials: 'same-origin',
            });
            const d = await r.json();
            const replyEl = container.querySelector('.assistant-reply:last-of-type');
            if (d.error) {
                if (replyEl) replyEl.textContent = '错误: ' + d.error;
            } else {
                if (replyEl) {
                    let html = (d.reply || '').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
                    if (d.suggested_action && d.suggested_action.type === 'config_diff') {
                        const cfgId = 'cfg_' + Date.now();
                        suggestedConfigs[cfgId] = d.suggested_action.diff || '';
                        html += '<div style="margin-top:12px;"><button class="btn btn-primary copy-config-btn" data-cfg-id="' + cfgId + '" style="padding:6px 12px;font-size:12px;">📋 复制配置</button></div>';
                    }
                    if (d.suggested_action && d.suggested_action.type === 'confirm_execute') {
                        const sa = d.suggested_action;
                        const actionId = 'act_' + Date.now();
                        suggestedConfigs[actionId] = sa;
                        html += '<div style="margin-top:12px;"><button class="btn btn-primary confirm-execute-btn" data-action-id="' + actionId + '" style="padding:6px 12px;font-size:12px;">✓ 确认执行</button></div>';
                        showConfirmExecuteModal(sa);
                    }
                    replyEl.innerHTML = html;
                    replyEl.querySelectorAll('.copy-config-btn').forEach(btn => {
                        btn.onclick = () => {
                            const yaml = suggestedConfigs[btn.getAttribute('data-cfg-id')] || '';
                            navigator.clipboard.writeText(yaml).then(() => {
                                if (typeof showToast === 'function') showToast('已复制到剪贴板');
                                else alert('已复制到剪贴板');
                            }).catch(() => alert('复制失败'));
                        };
                    });
                    replyEl.querySelectorAll('.confirm-execute-btn').forEach(btn => {
                        btn.onclick = () => showConfirmExecuteModal(suggestedConfigs[btn.getAttribute('data-action-id')]);
                    });
                }
            }
            loadConversations();
        } catch (e) {
            const replyEl = container.querySelector('.assistant-reply:last-of-type');
            if (replyEl) { replyEl.innerHTML = ''; replyEl.textContent = '请求失败: ' + e.message; }
        }
        input.disabled = false;
        if (sendBtn) { sendBtn.disabled = false; sendBtn.textContent = '发送'; }
        container.querySelector('.assistant-loading')?.classList?.remove('assistant-loading');
        container.scrollTop = container.scrollHeight;
    }

    async function init() {
        await checkStatus();
        createFloatingButton();
        createPanel();
        updateButtonFromStatus();
    }

    // 暴露刷新方法，供配置保存后调用
    window.refreshAssistantStatus = async function () {
        await checkStatus();
        updateButtonFromStatus();
    };

    document.addEventListener('config-saved', function () {
        window.refreshAssistantStatus && window.refreshAssistantStatus();
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
