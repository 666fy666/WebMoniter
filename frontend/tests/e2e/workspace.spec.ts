import { test, expect } from './fixtures'

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
  await page.screenshot({
    path: `test-results/account-dark-${testInfo.project.name}.png`,
    fullPage: true,
  })
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await page.getByLabel('材质与动态效果').selectOption('full')
  await expect(page.locator('html')).toHaveAttribute('data-effects', 'full')
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await expect(page.locator('html')).toHaveAttribute('data-effects', 'simple')
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await expect(page.locator('html')).toHaveAttribute('data-effects', 'full')
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

test('section save preserves edits and section switches made while awaiting the response', async ({
  page,
}) => {
  await page.goto('/config?section=weibo')
  const interval = page.getByLabel('监控间隔（秒）', { exact: true })
  await interval.fill('410')
  let release!: () => void
  const gate = new Promise<void>((resolve) => (release = resolve))
  let saved!: () => void
  const savedResponse = new Promise<void>((resolve) => (saved = resolve))
  await page.route('**/api/v1/config', async (route) => {
    if (route.request().method() !== 'PUT') return route.continue()
    const response = await route.fetch()
    saved()
    await gate
    await route.fulfill({ response })
  })
  try {
    await page.getByRole('button', { name: '保存当前模块' }).click()
    await savedResponse
    await interval.fill('411')
    await page
      .getByRole('navigation', { name: '配置模块' })
      .getByRole('button', { name: '虎牙直播监控', exact: true })
      .click()
    await interval.fill('412')
  } finally {
    release()
  }
  await expect(page.getByRole('status')).toContainText('配置已保存')
  await expect(interval).toHaveValue('412')
  await expect(page.getByRole('button', { name: '保存当前模块' })).toBeEnabled()
  await page
    .getByRole('navigation', { name: '配置模块' })
    .getByRole('button', { name: '微博监控', exact: true })
    .click()
  await expect(interval).toHaveValue('411')
})

test('switching log source during a request refreshes immediately and drops old lines', async ({
  page,
}) => {
  let release!: () => void
  const gate = new Promise<void>((resolve) => (release = resolve))
  let requested!: () => void
  const firstRequest = new Promise<void>((resolve) => (requested = resolve))
  await page.route('**/api/v1/logs?*', async (route) => {
    const task = new URL(route.request().url()).searchParams.get('task')
    if (!task) {
      requested()
      await gate
    }
    await route.fulfill({
      json: { lines: [task ? 'new task log' : 'old main log'], cursor: 'next', reset: true },
    })
  })
  try {
    await page.goto('/logs')
    await firstRequest
    await page.getByLabel('日志来源').selectOption('log_cleanup')
  } finally {
    release()
  }
  await expect(page.getByLabel('日志内容')).toContainText('new task log', { timeout: 2000 })
  await expect(page.getByLabel('日志内容')).not.toContainText('old main log')
})
