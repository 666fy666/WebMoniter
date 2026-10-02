// Node 内置测试运行真实页面脚本；DOM、网络、空闲回调及时间均由内存夹具提供。
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

class Events {
    listeners = new Map();
    addEventListener(type, callback, options = {}) {
        const entries = this.listeners.get(type) || [];
        entries.push({ callback, once: options.once });
        this.listeners.set(type, entries);
    }
    async emit(type, event = {}) {
        const entries = [...(this.listeners.get(type) || [])];
        this.listeners.set(type, entries.filter(entry => !entry.once));
        await Promise.all(entries.map(entry => entry.callback.call(this, { type, ...event })));
    }
    dispatchEvent(event) { return this.emit(event.type, event); }
}

class Element extends Events {
    constructor(tagName = 'div') {
        super();
        this.tagName = tagName;
        this.dataset = {};
        this.attributes = new Map();
        this.style = {
            display: 'none',
            setProperty(name, value) { this[name] = value; },
            removeProperty(name) { delete this[name]; },
        };
        this.classes = new Set();
        this.classList = {
            add: (...names) => names.forEach(name => this.classes.add(name)),
            remove: (...names) => names.forEach(name => this.classes.delete(name)),
            contains: name => this.classes.has(name),
            toggle: (name, force = !this.classes.has(name)) => {
                if (force) this.classes.add(name); else this.classes.delete(name);
            },
        };
        this.children = [];
        this.queries = {};
        this.value = '';
        this.checked = false;
        this.disabled = false;
        this.isConnected = true;
        this.options = [{}];
        this.writes = 0;
        this.rectReads = 0;
    }
    set className(value) { this.classes = new Set(value.split(/\s+/)); }
    get innerHTML() { return this.html || ''; }
    set innerHTML(value) {
        this.writes++;
        this.html = value;
        const disconnect = child => {
            child.isConnected = false;
            child.children.forEach(disconnect);
        };
        this.children.forEach(disconnect);
        this.children = [];
        for (const match of value.matchAll(/<(button|img)\b([^>]*?)(?:>([\s\S]*?)<\/button>|>)/g)) {
            const child = new Element(match[1]);
            for (const attribute of match[2].matchAll(/([-\w]+)="([^"]*)"/g)) {
                child.setAttribute(attribute[1], attribute[2]);
            }
            child.disabled = /\bdisabled\b/.test(match[2]);
            child.innerHTML = match[3] || '';
            this.append(child);
        }
    }
    set textContent(value) {
        this.text = String(value);
        this.html = this.text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
    get textContent() { return this.text || ''; }
    setAttribute(name, value) {
        this.attributes.set(name, String(value));
        if (name === 'class') this.className = value;
        if (name.startsWith('data-')) this.dataset[this.dataKey(name)] = String(value);
    }
    getAttribute(name) { return this.attributes.get(name) ?? null; }
    removeAttribute(name) {
        this.attributes.delete(name);
        if (name.startsWith('data-')) delete this.dataset[this.dataKey(name)];
    }
    toggleAttribute(name, force) {
        if (force) this.setAttribute(name, ''); else this.removeAttribute(name);
    }
    dataKey(name) { return name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase()); }
    append(...children) {
        children.forEach(child => { child.parent = this; this.children.push(child); });
    }
    appendChild(child) { this.append(child); return child; }
    contains(child) {
        for (let node = child; node; node = node.parent) if (node === this) return true;
        return false;
    }
    querySelectorAll(selector) {
        if (this.queries[selector]) return this.queries[selector];
        return this.children.flatMap(child => {
            const matches = selector === 'img[data-src]'
                ? child.tagName === 'img' && child.dataset.src
                : selector === 'button[data-page]'
                    ? child.tagName === 'button' && child.dataset.page
                    : selector.startsWith('.') && child.classes.has(selector.slice(1));
            return [...(matches ? [child] : []), ...child.querySelectorAll(selector)];
        });
    }
    querySelector(selector) {
        if (selector === 'span' && this.html?.includes('<span')) {
            return this.queries.span || (this.queries.span = new Element('span'));
        }
        return this.querySelectorAll(selector)[0] || null;
    }
    closest(selector) {
        if (selector.includes('.btn') && this.classes.has('btn-primary')) return this;
        if (selector.includes('.card') && this.classes.has('card')) return this;
        return null;
    }
    matches(selector) { return selector === ':disabled' && this.disabled; }
    getBoundingClientRect() {
        this.rectReads++;
        return { left: 0, top: 0, width: 100, height: 100 };
    }
    focus() {}
}

function deferred() {
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
}
const response = body => ({ ok: true, status: 200, json: async () => body });
const settle = () => new Promise(resolve => setImmediate(resolve));

function runtime(script, fetchImpl) {
    const elements = new Map();
    const document = new Events();
    const window = new Events();
    const all = {};
    const timers = new Map(), frames = new Map(), idles = new Map();
    const requests = [], toasts = [];
    let nextId = 0;
    const el = id => {
        if (!elements.has(id)) elements.set(id, new Element());
        return elements.get(id);
    };
    document.body = new Element('body');
    document.documentElement = new Element('html');
    document.getElementById = el;
    document.createElement = tag => new Element(tag);
    document.querySelectorAll = selector => all[selector]
        || [...elements.values()].flatMap(element => element.querySelectorAll(selector));
    document.querySelector = selector => {
        const job = selector.match(/^(\.[-\w]+)\[data-job-id="([^"]+)"\]$/);
        if (job) return document.querySelectorAll(job[1]).find(button => button.dataset.jobId === job[2]);
        return document.querySelectorAll(selector)[0] || null;
    };
    const setTimeout = (callback, delay) => {
        const id = ++nextId;
        timers.set(id, { callback, delay });
        return id;
    };
    window.setTimeout = setTimeout;
    window.requestIdleCallback = callback => idles.set(++nextId, callback);
    window.matchMedia = query => ({ matches: query.includes('hover: hover') });
    window.innerWidth = 1024;
    window.innerHeight = 768;
    const storage = new Map();
    const context = vm.createContext({
        document, window, Element, AbortController, DOMException, Event,
        CustomEvent: class { constructor(type, options = {}) { this.type = type; this.detail = options.detail; } },
        navigator: { onLine: true },
        MutationObserver: class { observe() {} },
        Node: { ELEMENT_NODE: 1 },
        console: { log() {}, warn() {}, error() {} },
        performance: { now: () => 200 },
        setTimeout, clearTimeout: id => timers.delete(id),
        requestAnimationFrame: callback => { const id = ++nextId; frames.set(id, callback); return id; },
        cancelAnimationFrame: id => frames.delete(id),
        localStorage: { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) },
        showToast: (...args) => toasts.push(args), showMessage() {},
        fetch: (url, options = {}) => {
            const pending = deferred();
            const record = { url, options, ...pending };
            requests.push(record);
            if (fetchImpl) return fetchImpl(url, options);
            return pending.promise;
        },
    });
    const run = filename => vm.runInContext(readFileSync(join(__dirname, '../webUI/static/js', filename), 'utf8'), context);
    run('common.js');
    document.listeners.delete('DOMContentLoaded');
    // 页面反馈由实际按钮函数处理，消息只记录，不运行消失定时器。
    context.showToast = (...args) => toasts.push(args);
    context.showMessage = () => {};
    if (script !== 'common.js') run(script);
    const fire = (map, predicate = () => true, argument) => {
        for (const [id, value] of map) {
            if (predicate(value)) {
                map.delete(id);
                (value.callback || value)(argument);
                return;
            }
        }
        assert.fail('预期的回调未被调度');
    };
    return {
        context, document, window, el, all, requests, timers, frames, idles, toasts,
        start: () => document.emit('DOMContentLoaded'),
        reply: (record, body) => record.resolve(response(body)),
        timer: delay => fire(timers, value => value.delay === delay),
        idle: () => fire(idles, undefined, { timeRemaining: () => 12 }),
        frame: () => fire(frames, undefined, 216),
    };
}

test('配置控件保留标签关联与 ARIA 名称，并为缺失名称提供原有回退', () => {
    const r = runtime('config.js');
    const controlSelector = 'input:not([type="hidden"]), select, textarea';
    const root = new Element();
    const row = new Element('tr');
    const labelCell = new Element('td');
    labelCell.textContent = '原有表格标签';
    const rowControl = new Element('input');
    const labelledControl = new Element('input');
    const ariaControl = new Element('input');
    const fallbackControl = new Element('input');
    const emptyLabelControl = new Element('input');
    const controls = [rowControl, labelledControl, ariaControl, fallbackControl, emptyLabelControl];
    controls.forEach(control => {
        Object.defineProperty(control, 'labels', { get() { assert.fail('不应逐控件扫描 labels'); } });
    });
    const label = new Element('label');
    label.control = labelledControl;
    label.textContent = '已有 HTML 标签';
    const emptyLabel = new Element('label');
    emptyLabel.control = emptyLabelControl;
    emptyLabel.textContent = ' ';
    r.all.label = [label, emptyLabel];
    row.queries['.config-label'] = [labelCell];
    row.queries[controlSelector] = [rowControl, labelledControl, ariaControl];
    root.queries.tr = [row];
    root.queries[controlSelector] = controls;
    ariaControl.setAttribute('aria-label', '自定义 ARIA 名称');
    fallbackControl.setAttribute('placeholder', '原有占位文字');
    emptyLabelControl.setAttribute('placeholder', '空标签回退');
    r.context.ensureConfigControlAccessibleNames(root);
    assert.equal(rowControl.getAttribute('aria-labelledby'), labelCell.id);
    assert.equal(labelledControl.getAttribute('aria-labelledby'), null);
    assert.equal(labelledControl.getAttribute('aria-label'), null);
    assert.equal(ariaControl.getAttribute('aria-label'), '自定义 ARIA 名称');
    assert.equal(fallbackControl.getAttribute('aria-label'), '原有占位文字');
    assert.equal(emptyLabelControl.getAttribute('aria-label'), '空标签回退');

    const dynamicRoot = new Element();
    const dynamicControl = new Element('input');
    const dynamicLabel = new Element('label');
    dynamicLabel.control = dynamicControl;
    dynamicLabel.textContent = '新插入的标签';
    r.all.label.push(dynamicLabel);
    dynamicRoot.queries[controlSelector] = [dynamicControl];
    r.context.ensureConfigControlAccessibleNames(dynamicRoot);
    assert.equal(dynamicControl.getAttribute('aria-label'), null);
});

test('数据页只渲染最新平台和页码的响应', async () => {
    const r = runtime('data.js');
    const huya = new Element('button'), douyu = new Element('button');
    huya.dataset.table = 'huya'; douyu.dataset.table = 'douyu';
    r.all['.tab-btn'] = [huya, douyu];
    await r.start();
    await huya.emit('click');
    const old = r.requests.at(-1);
    await douyu.emit('click');
    r.reply(r.requests.at(-1), { data: [{ room: '1', name: 'NEW_DOUYU' }], total: 200, total_pages: 2 });
    await settle();
    r.reply(old, { data: [{ room: '1', name: 'STALE_HUYA' }], total: 1, total_pages: 1 });
    await settle();
    assert.equal(old.options.signal.aborted, true);
    assert.match(r.el('dataTableContainer').innerHTML, /NEW_DOUYU/);
    assert.doesNotMatch(r.el('dataTableContainer').innerHTML, /STALE_HUYA/);
    await r.el('pagination').querySelectorAll('button[data-page]')[1].emit('click');
    assert.match(r.requests.at(-1).url, /page=2/);
    r.reply(r.requests.at(-1), { data: [], total: 200, total_pages: 2 });
    await settle();
    assert.match(r.el('pagination').innerHTML, /第 2 \/ 2 页/);
    assert.equal(r.el('dataTableContainer').getAttribute('aria-busy'), null);
});

test('过期的虎牙图片请求不访问新页面卡片', async () => {
    const r = runtime('data.js');
    const tab = new Element('button'); tab.dataset.table = 'huya';
    r.all['.tab-btn'] = [tab];
    await r.start(); await tab.emit('click');
    r.reply(r.requests.at(-1), { data: [{ room: '1', name: '主播' }], total_pages: 2, total: 200 });
    await settle();
    const images = r.requests.at(-1);
    await r.el('pagination').querySelectorAll('button[data-page]')[1].emit('click');
    let cardReads = 0;
    const container = r.el('dataTableContainer');
    const query = container.querySelector.bind(container);
    container.querySelector = selector => {
        if (selector.startsWith('.data-card[data-room=')) cardReads++;
        return query(selector);
    };
    r.reply(images, { data: { '1': { room_pic: 'old.jpg' } } });
    await settle();
    assert.equal(images.options.signal.aborted, true);
    assert.equal(cardReads, 0);
});

test('图片队列满载时停止调度，旧代次完成不会释放新槽位', async () => {
    const r = runtime('data.js');
    await r.start();
    const page = { data: [{ UID: '1', 用户名: '测试', 文本: '正文', images: ['1.jpg', '2.jpg', '3.jpg', '4.jpg', '5.jpg'] }], total: 50, total_pages: 2 };
    r.reply(r.requests.at(-1), page);
    await settle();
    const oldImages = r.el('dataTableContainer').querySelectorAll('img[data-src]');
    r.idle();
    assert.equal(oldImages.filter(img => img.src).length, 3);
    assert.equal(r.idles.size, 0);
    await oldImages[0].emit('load'); r.idle();
    assert.equal(oldImages.filter(img => img.src).length, 4);
    await r.el('pagination').querySelectorAll('button[data-page]')[1].emit('click');
    r.reply(r.requests.at(-1), page);
    await settle();
    const newImages = r.el('dataTableContainer').querySelectorAll('img[data-src]');
    r.idle();
    await oldImages[1].emit('load');
    assert.equal(r.idles.size, 0);
    assert.equal(newImages.filter(img => img.src).length, 3);
});

test('日志强制刷新和切换来源能恢复；相同内容不重建，清空后可重新显示', async () => {
    const r = runtime('logs.js');
    await r.start();
    const old = r.requests.find(record => record.url.startsWith('/api/logs?'));
    const refresh = r.el('refreshLogsBtn').emit('click');
    const latest = r.requests.at(-1);
    r.reply(latest, { logs: ['INFO NEW_LOG'] });
    r.reply(r.requests.findLast(record => record.url === '/api/logs/tasks'), { all_tasks: [] });
    await refresh;
    r.reply(old, { logs: ['OLD_LOG'] });
    await settle();
    assert.equal(old.options.signal.aborted, true);
    assert.equal(vm.runInContext('isRequestInProgress', r.context), false);
    assert.match(r.el('logsContainer').innerHTML, /NEW_LOG/);
    const writes = r.el('logsContainer').writes;
    r.timer(5000); r.reply(r.requests.at(-1), { logs: ['INFO NEW_LOG'] });
    await settle();
    assert.equal(r.el('logsContainer').writes, writes);
    await r.el('clearLogsBtn').emit('click');
    r.timer(7000); r.reply(r.requests.at(-1), { logs: ['INFO NEW_LOG'] });
    await settle();
    assert.match(r.el('logsContainer').innerHTML, /NEW_LOG/);
    r.el('logSourceSelect').value = 'another_task';
    await r.el('logSourceSelect').emit('change');
    assert.match(r.requests.at(-1).url, /task=another_task/);
});

test('日志超时覆盖请求及 JSON 读取，并允许重试恢复', async () => {
    for (const phase of ['headers', 'body']) {
        const r = runtime('logs.js');
        await r.start();
        const request = r.requests.at(-1);
        const abort = () => new DOMException('aborted', 'AbortError');
        if (phase === 'headers') {
            request.options.signal.addEventListener('abort', () => request.reject(abort()));
        } else {
            const body = deferred();
            request.options.signal.addEventListener('abort', () => body.reject(abort()));
            request.resolve({ ok: true, json: () => body.promise });
            await settle();
        }
        r.timer(60000); await settle();
        assert.equal(request.options.signal.aborted, true);
        assert.equal(vm.runInContext('isRequestInProgress', r.context), false);
        r.timer(1000);
        r.reply(r.requests.at(-1), { logs: ['RECOVERED'] });
        await settle();
        assert.match(r.el('logsContainer').innerHTML, /RECOVERED/);
    }
});

test('任务列表重绘后，完成状态恢复当前按钮并显示失败反馈', async () => {
    const r = runtime('tasks.js');
    await r.start();
    const tasks = [{ job_id: 'demo', description: 'Demo', type: 'task', type_label: '定时', trigger: 'cron' }];
    r.reply(r.requests.at(-1), { tasks });
    await settle();
    const completion = r.context.runTask('demo');
    r.context.renderTasks(tasks);
    const button = r.document.querySelector('.run-task-btn[data-job-id="demo"]');
    assert.equal(button.disabled, true);
    r.reply(r.requests.at(-1), { success: false, message: '任务未完成' });
    await completion;
    assert.equal(button.disabled, false);
    assert.equal(button.classList.contains('running'), false);
    assert.match(button.innerHTML, /icon-play/);
    assert.equal(r.toasts.at(-1)[1], 'error');
});

test('任务日志弹窗切换和关闭后忽略旧响应', async () => {
    const r = runtime('tasks.js');
    r.context.openTaskLogModal('a');
    const old = r.requests.at(-1);
    r.context.openTaskLogModal('b');
    r.reply(r.requests.at(-1), { logs: ['B_LOG'] });
    r.reply(old, { logs: ['A_LOG'] });
    await settle();
    assert.match(r.el('taskLogModalContent').innerHTML, /B_LOG/);
    assert.doesNotMatch(r.el('taskLogModalContent').innerHTML, /A_LOG/);
    r.context.openTaskLogModal('c');
    const closed = r.requests.at(-1);
    r.context.closeTaskLogModal();
    r.reply(closed, { logs: ['C_LOG'] });
    await settle();
    assert.equal(closed.options.signal.aborted, true);
    assert.doesNotMatch(r.el('taskLogModalContent').innerHTML, /C_LOG/);
});

test('配置分区仅提交自身字段，元数据失败时开关标签可用且状态只刷新一次', async () => {
    const r = runtime('config.js', (url, options) => {
        if (url === '/api/config/metadata') return Promise.reject(new Error('offline'));
        if (options.method === 'POST') return Promise.resolve(response({ success: true }));
        if (url === '/api/config?format=json') return Promise.resolve(response({ config: { app: { base_url: 'http://initial' } } }));
        return Promise.resolve(response({ active_backend: 'sqlite', sync_state: 'sqlite_only' }));
    });
    const section = new Element(), button = new Element('button');
    section.dataset.section = 'app';
    section.queries['.section-save-btn'] = [button];
    r.all['.config-section'] = [section];
    await r.start();
    const input = r.el('weibo_enable');
    input.checked = true; await input.emit('change');
    assert.equal(r.el('weibo_enable_label').textContent, '开启');
    r.el('app_base_url').value = 'http://changed';
    const before = r.requests.length;
    await button.emit('click'); await settle();
    const saves = r.requests.slice(before);
    assert.equal(saves[0].options.method, 'POST');
    assert.deepEqual(JSON.parse(saves[0].options.body), { config: { app: { base_url: 'http://changed' } } });
    assert.equal(saves.filter(record => record.url === '/api/database/status').length, 1);
});

test('快手配置支持目标列表、默认关闭及独立保存', async () => {
    const r = runtime('config.js', (url, options) => {
        if (url === '/api/config/metadata') return Promise.reject(new Error('offline'));
        if (options.method === 'POST') return Promise.resolve(response({ success: true }));
        if (url === '/api/config?format=json') return Promise.resolve(response({ config: {
            kuaishou: { targets: ['alice', 'https://v.kuaishou.com/share'], cookie: '', push_channels: [] }
        } }));
        return Promise.resolve(response({ active_backend: 'sqlite', sync_state: 'sqlite_only' }));
    });
    const section = new Element(), button = new Element('button');
    section.dataset.section = 'kuaishou';
    section.queries['.section-save-btn'] = [button];
    r.all['.config-section'] = [section];
    await r.start();
    assert.equal(r.el('kuaishou_enable').checked, false);
    assert.equal(r.el('kuaishou_targets').value, 'alice,https://v.kuaishou.com/share');
    r.el('kuaishou_enable').checked = true;
    await r.el('kuaishou_enable').emit('change');
    assert.equal(r.el('kuaishou_enable_label').textContent, '开启');
    r.el('kuaishou_targets').value = 'bob';
    await button.emit('click'); await settle();
    const save = r.requests.find(record => record.options.method === 'POST');
    assert.deepEqual(JSON.parse(save.options.body), { config: { kuaishou: {
        enable: true, targets: 'bob', cookie: '', concurrency: 2,
        monitor_interval_seconds: 60, push_channels: []
    } } });
});

test('快手数据页展示状态、主播 ID 和直播链接并转义名称', async () => {
    const r = runtime('data.js');
    const tab = new Element('button'); tab.dataset.table = 'kuaishou';
    r.all['.tab-btn'] = [tab];
    await r.start(); await tab.emit('click');
    assert.match(r.requests.at(-1).url, /api\/data\/kuaishou/);
    r.reply(r.requests.at(-1), { data: [
        { principal_id: 'alice', name: '<b>主播</b>', is_live: '1', url: 'https://live.kuaishou.com/u/alice' },
        { principal_id: 'bob', name: '未开播主播', is_live: '0' }
    ], total: 2, total_pages: 1 });
    await settle();
    const html = r.el('dataTableContainer').innerHTML;
    assert.match(html, /快手直播/);
    assert.match(html, /直播中/);
    assert.match(html, /未开播/);
    assert.match(html, /&lt;b&gt;主播&lt;\/b&gt;/);
    assert.match(html, /https:\/\/live.kuaishou.com\/u\/alice/);
});

test('高频指针事件在一帧内合并布局读取，离开页面清理待处理更新', async () => {
    const r = runtime('common.js');
    r.context.initCustomCursorExperience();
    const button = new Element('button'); button.className = 'btn btn-primary';
    for (let i = 0; i < 10; i++) {
        await r.document.emit('pointermove', { target: button, pointerType: 'mouse', clientX: i, clientY: i });
    }
    assert.equal(button.rectReads, 0);
    r.frame();
    assert.equal(button.rectReads, 1);
    await r.document.emit('pointermove', { target: button, clientX: 30, clientY: 30 });
    await r.window.emit('blur');
    assert.equal(r.frames.size, 0);
    assert.equal(button.rectReads, 1);
    assert.equal(button.style['--cursor-pull-x'], undefined);
});

test('玻璃高光与光标共用一帧内的几何读取，隐藏时停止动效', async () => {
    const r = runtime('common.js');
    r.context.initLiquidGlassLens();
    r.context.initCustomCursorExperience();
    const button = new Element('button'); button.className = 'btn btn-primary';
    await r.document.emit('pointermove', { target: button, clientX: 20, clientY: 20 });
    r.frame();
    r.frame();
    assert.equal(button.rectReads, 1);
    await r.document.emit('pointermove', { target: button, clientX: 35, clientY: 35 });
    r.document.hidden = true;
    await r.document.emit('visibilitychange');
    assert.equal(r.frames.size, 0);
    assert.equal(button.style['--lg-x'], undefined);
});

test('卡片倾斜复用几何读取并在离开时释放合成层提示', async () => {
    const r = runtime('common.js');
    r.context.initCustomCursorExperience();
    const card = new Element(); card.className = 'card';
    await r.document.emit('pointermove', { target: card, clientX: 20, clientY: 20 });
    r.frame();
    assert.equal(card.rectReads, 1);
    assert.equal(card.classList.contains('cursor-reactive-card'), true);
    await r.document.emit('mouseleave');
    assert.equal(card.classList.contains('cursor-reactive-card'), false);
    assert.equal(card.style['--cursor-tilt-x'], undefined);
});

test('读取超时覆盖响应头和响应体，数据页允许重试恢复', async () => {
    for (const phase of ['headers', 'body']) {
        const r = runtime('data.js');
        await r.start();
        const request = r.requests.at(-1);
        const abort = () => new DOMException('aborted', 'AbortError');
        if (phase === 'headers') {
            request.options.signal.addEventListener('abort', () => request.reject(abort()));
        } else {
            const body = deferred();
            request.options.signal.addEventListener('abort', () => body.reject(abort()));
            request.resolve({ ok: true, json: () => body.promise });
            await settle();
        }
        r.timer(30000);
        await settle();
        assert.equal(request.options.signal.aborted, true);
        assert.match(r.el('dataTableContainer').innerHTML, /请求超时/);
        assert.equal(r.el('dataTableContainer').getAttribute('aria-busy'), null);
        const retry = r.el('dataTableContainer').querySelector('.retry-data-btn').emit('click');
        r.reply(r.requests.at(-1), { data: [], total: 0, total_pages: 0 });
        await retry;
        await settle();
        assert.doesNotMatch(r.el('dataTableContainer').innerHTML, /请求超时/);
    }
});

test('任务列表并发刷新取消旧请求并恢复刷新按钮', async () => {
    const r = runtime('tasks.js');
    const button = new Element('button');
    button.innerHTML = '刷新';
    const first = r.context.loadTasks(button);
    const old = r.requests.at(-1);
    const latest = r.context.loadTasks();
    const tasks = [{ job_id: 'new', type: 'task', description: '最新任务' }];
    r.reply(r.requests.at(-1), { tasks });
    await latest;
    r.reply(old, { tasks: [{ job_id: 'old', type: 'task', description: '旧任务' }] });
    await first;
    assert.equal(old.options.signal.aborted, true);
    assert.equal(button.disabled, false);
    assert.match(r.el('tasksContainer').innerHTML, /最新任务/);
    assert.doesNotMatch(r.el('tasksContainer').innerHTML, /旧任务/);
});

test('日志在隐藏及离线时停止自动轮询，恢复后继续', async () => {
    const r = runtime('logs.js', url => Promise.resolve(response(url.includes('/tasks')
        ? { all_tasks: [] } : { logs: ['INFO 初始日志'] })));
    await r.start();
    await settle();
    const refreshTimers = () => [...r.timers.values()].filter(timer => timer.delay === 5000);
    assert.equal(refreshTimers().length, 1);
    r.document.hidden = true;
    await r.document.emit('visibilitychange');
    assert.equal(refreshTimers().length, 0);
    r.context.navigator.onLine = false;
    r.document.hidden = false;
    await r.document.emit('visibilitychange');
    await settle();
    assert.equal(refreshTimers().length, 0);
    r.context.navigator.onLine = true;
    await r.window.emit('online');
    await settle();
    assert.equal(refreshTimers().length, 1);
    await r.window.emit('pagehide');
    assert.equal(refreshTimers().length, 0);
});

test('局部保存不覆盖其他分区或保存期间的新编辑，首屏读取并发启动', async () => {
    const r = runtime('config.js');
    const app = new Element(), button = new Element('button');
    app.dataset.section = 'app';
    app.queries['.section-save-btn'] = [button];
    r.all['.config-section'] = [app];
    const start = r.start();
    assert.deepEqual(r.requests.map(request => request.url), [
        '/api/config/metadata', '/api/config?format=json', '/api/database/status',
    ]);
    for (const request of r.requests) r.reply(request, request.url.includes('format=json')
        ? { config: { app: { base_url: 'http://initial' }, huya: { rooms: 'initial-room' } } }
        : {});
    await start;
    r.el('app_base_url').value = 'http://submitted';
    r.el('huya_rooms').value = 'unsaved-room';
    const saving = button.emit('click');
    const submit = r.requests.at(-1);
    r.el('app_base_url').value = 'http://new-edit';
    const target = { closest: () => app };
    await r.el('mainContent').emit('input', { target });
    r.reply(submit, { success: true });
    await saving;
    const reload = r.requests.findLast(request => request.url.includes('format=json'));
    r.reply(reload, { config: { app: { base_url: 'http://submitted' }, huya: { rooms: 'server-room' } } });
    r.reply(r.requests.findLast(request => request.url.includes('database/status')), {});
    await settle();
    assert.equal(r.el('app_base_url').value, 'http://new-edit');
    assert.equal(r.el('huya_rooms').value, 'unsaved-room');
});

test('YAML 忽略旧响应，切换视图和保存期间均保留新编辑', async () => {
    const reads = [], writes = [];
    const r = runtime('config.js', (url, options) => {
        if (url.includes('format=yaml')) {
            const pending = deferred(); reads.push(pending); return pending.promise;
        }
        if (options.method === 'POST') {
            const pending = deferred(); writes.push(pending); return pending.promise;
        }
        return Promise.resolve(response(url.includes('format=json') ? { config: {} } : {}));
    });
    const table = new Element('button'), text = new Element('button');
    table.dataset.view = 'table'; text.dataset.view = 'text';
    r.all['.tab-btn'] = [table, text];
    await r.start();
    await text.emit('click');
    const old = r.requests.at(-1);
    const reload = r.el('reloadYamlBtn').emit('click');
    reads[1].resolve(response({ content: 'latest: true' }));
    await reload;
    reads[0].resolve(response({ content: 'old: true' }));
    await settle();
    assert.equal(old.options.signal.aborted, true);
    assert.equal(r.el('yamlEditor').value, 'latest: true');
    r.el('yamlEditor').value = 'draft: one';
    await r.el('yamlEditor').emit('input');
    await table.emit('click'); await text.emit('click');
    assert.equal(reads.length, 2);
    const refreshing = r.el('reloadYamlBtn').emit('click');
    r.el('yamlEditor').value = 'draft: two';
    await r.el('yamlEditor').emit('input');
    reads[2].resolve(response({ content: 'server: true' }));
    await refreshing;
    assert.equal(r.el('yamlEditor').value, 'draft: two');
    const saving = r.el('saveYamlBtn').emit('click');
    r.el('yamlEditor').value = 'draft: three';
    await r.el('yamlEditor').emit('input');
    writes[0].resolve(response({ success: true }));
    await saving; await settle();
    assert.equal(r.el('yamlEditor').value, 'draft: three');
    assert.equal(reads.length, 3);
});
