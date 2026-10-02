import { test, expect } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('用户名', { exact: true }).fill('admin')
  await page.getByLabel('密码', { exact: true }).fill('ui-test-only-password')
  await page.getByRole('button', { name: '进入工作空间' }).click()
  await expect(page.getByRole('heading', { name: '一切，尽在掌握。' })).toBeVisible()
})

test('responsive workspace, themes and reduced motion', async ({ page }, testInfo) => {
  await expect(page.locator('body')).toHaveJSProperty(
    'scrollWidth',
    await page.evaluate(() => innerWidth),
  )
  await page.screenshot({
    path: `test-results/overview-${testInfo.project.name}.png`,
    fullPage: true,
  })
  await page.goto('/account')
  await page.getByLabel('主题', { exact: true }).selectOption('dark')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page).toHaveScreenshot('account-dark.png', {
    animations: 'disabled',
    maxDiffPixelRatio: 0.02,
  })
  await page.screenshot({
    path: `test-results/account-dark-${testInfo.project.name}.png`,
    fullPage: true,
  })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.getByLabel('材质与动态效果').selectOption('full')
  await expect(page.locator('html')).toHaveAttribute('data-effects', 'simple')
})

test('manual task queues and reaches a terminal state', async ({ page }, testInfo) => {
  await page.goto('/tasks')
  await page.getByLabel('搜索任务', { exact: true }).fill('日志清理')
  await page.getByRole('button', { name: '运行', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('任务已加入执行队列')
  await expect(page.locator('.task-row .badge')).toHaveText('已完成', { timeout: 15000 })
  await page.screenshot({ path: `test-results/tasks-${testInfo.project.name}.png`, fullPage: true })
  await page.getByRole('link', { name: '查看日志清理日志' }).click()
  await expect(page.getByLabel('日志来源')).toHaveValue('log_cleanup')
  await page.screenshot({ path: `test-results/logs-${testInfo.project.name}.png`, fullPage: true })
  await page.getByRole('button', { name: '暂停更新' }).click()
  await expect(page.getByRole('button', { name: '继续更新' })).toBeVisible()
})

test('section save preserves secrets and has conflict protection', async ({ page }, testInfo) => {
  await page.goto('/config?section=weibo')
  await expect(page.getByRole('switch', { name: '自动刷新 Cookie' })).not.toBeChecked()
  await expect(page.getByLabel('Cookie 刷新时间', { exact: true })).toHaveAttribute('type', 'time')
  const cookie = page.getByLabel('Cookie', { exact: true })
  await expect(cookie).toHaveAttribute('placeholder', '已设置 · 留空保持不变')
  await page.screenshot({
    path: `test-results/config-${testInfo.project.name}.png`,
    fullPage: true,
  })
  await cookie.fill('test-only-cookie-fixture')
  await page.getByRole('button', { name: '保存当前模块' }).click()
  await expect(page.getByRole('status')).toContainText('配置已保存')
  await expect(cookie).toHaveValue('')
  await expect(cookie).toHaveAttribute('placeholder', '已设置 · 留空保持不变')
  await page.getByLabel('监控间隔（秒）', { exact: true }).fill('400')
  await page.evaluate(async () => {
    const session = await (await fetch('/api/v1/session')).json()
    const config = await (await fetch('/api/v1/config')).json()
    await fetch('/api/v1/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token },
      body: JSON.stringify({
        version: config.version,
        config: {
          weibo: {
            monitor_interval_seconds: Number(config.config.weibo.monitor_interval_seconds) + 1,
          },
        },
      }),
    })
  })
  await page.getByRole('button', { name: '保存当前模块' }).click()
  await expect(page.getByRole('alert')).toContainText('配置已被其他操作修改')
})

test('API rejects missing CSRF and enforces data bounds', async ({ page }) => {
  const result = await page.evaluate(async () => ({
    csrf: (await fetch('/api/v1/tasks/log_cleanup/runs', { method: 'POST' })).status,
    bounds: (await fetch('/api/v1/data/weibo?page_size=10000')).status,
  }))
  expect(result.csrf).toBe(403)
  expect(result.bounds).toBe(400)
})

test('throttled overview stays within layout and load budgets', async ({
  page,
  context,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'CDP desktop benchmark')
  const cdp = await context.newCDPSession(page)
  await cdp.send('Network.enable')
  await cdp.send('Network.setCacheDisabled', { cacheDisabled: true })
  await cdp.send('Network.emulateNetworkConditions', {
    offline: false,
    latency: 100,
    downloadThroughput: 5_000_000 / 8,
    uploadThroughput: 5_000_000 / 8,
  })
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 })
  await page.addInitScript(() => {
    const metrics = { lcp: 0, cls: 0 }
    Object.assign(window, { wmMetrics: metrics })
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) metrics.lcp = e.startTime
    }).observe({ type: 'largest-contentful-paint', buffered: true })
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) {
        const shift = e as PerformanceEntry & { hadRecentInput: boolean; value: number }
        if (!shift.hadRecentInput) metrics.cls += shift.value
      }
    }).observe({ type: 'layout-shift', buffered: true })
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '一切，尽在掌握。' })).toBeVisible()
  await page.waitForTimeout(1500)
  const metrics = await page.evaluate(
    () => (window as unknown as { wmMetrics: { lcp: number; cls: number } }).wmMetrics,
  )
  await testInfo.attach('web-vitals', {
    body: JSON.stringify(metrics),
    contentType: 'application/json',
  })
  expect(metrics.lcp).toBeLessThanOrEqual(2500)
  expect(metrics.cls).toBeLessThanOrEqual(0.1)
})
