import { test, expect, type Page } from './fixtures'

const destinations = [
  { name: '概览', path: '/', heading: '一切，尽在掌握。' },
  { name: '任务', path: '/tasks', heading: '任务' },
  { name: '监控数据', path: '/data', heading: '监控数据' },
  { name: '配置', path: '/config', heading: '配置' },
  { name: '日志', path: '/logs', heading: '日志' },
  { name: '账户', path: '/account', heading: '账户与外观' },
]

function navigation(page: Page) {
  return page.locator('nav:visible').filter({ has: page.getByRole('link', { name: '概览' }) })
}

async function visit(page: Page, destination: (typeof destinations)[number]) {
  await navigation(page).getByRole('link', { name: destination.name, exact: true }).click()
  await expect(page).toHaveURL(destination.path)
  await expect(page.locator('main h1')).toHaveText(destination.heading)
  await expect(page.locator('main h1')).toBeVisible()
  if (destination.path === '/config')
    await expect(page.getByLabel('监控间隔（秒）', { exact: true })).toBeVisible()
}

test('all workspace tabs render without reloading', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  const documentId = await page.evaluate(() => {
    const id = String(Math.random())
    document.documentElement.dataset.navigationTest = id
    return id
  })
  for (const destination of destinations) await visit(page, destination)
  await expect(page.locator('html')).toHaveAttribute('data-navigation-test', documentId)
  expect(errors).toEqual([])
})

test('rapid navigation and browser history keep the current page visible', async ({ page }) => {
  await visit(page, destinations[2])
  // Dispatch clicks without waiting for the outgoing page animation to finish.
  for (const name of ['任务', '日志', '监控数据', '账户']) {
    await navigation(page).getByRole('link', { name, exact: true }).dispatchEvent('click')
    await expect(page.locator('.breadcrumb strong')).toHaveText(
      name === '账户' ? '账户与外观' : name,
    )
  }
  await expect(page.locator('main h1')).toHaveText('账户与外观')
  await expect(page.locator('main h1')).toBeVisible()
  await page.goBack()
  await expect(page.locator('main h1')).toHaveText('监控数据')
  await expect(page.locator('main h1')).toBeVisible()
  await page.goForward()
  await expect(page.locator('main h1')).toHaveText('账户与外观')
  await expect(page.locator('main h1')).toBeVisible()
})

test('leaving data during a request does not block navigation or returning to data', async ({
  page,
}) => {
  let release!: () => void
  const gate = new Promise<void>((resolve) => (release = resolve))
  await page.route('**/api/v1/data/weibo?*', async (route) => {
    await gate
    await route.fulfill({
      json: { data: [{ UID: '1', 用户名: '切换后加载成功' }], total: 1, total_pages: 1 },
    })
  })
  try {
    await visit(page, destinations[2])
    await expect(page.getByRole('heading', { name: '正在读取动态…' })).toBeVisible()
    await visit(page, destinations[1])
  } finally {
    release()
  }
  await visit(page, destinations[2])
  await expect(page.getByRole('heading', { name: '切换后加载成功' })).toBeVisible()
  await visit(page, destinations[4])
})

test('leaving data with an open preview removes the overlay and restores scrolling', async ({
  page,
}) => {
  await page.route('**/api/v1/data/weibo?*', (route) =>
    route.fulfill({
      json: {
        data: [{ UID: '1', 用户名: '图片用户', images: ['/weibo_img/navigation-test.svg'] }],
        total: 1,
        total_pages: 1,
      },
    }),
  )
  await page.route('**/weibo_img/navigation-test.svg', (route) =>
    route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48"/>',
    }),
  )
  await visit(page, destinations[2])
  await page.getByRole('button', { name: '查看第 1 张图片', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '微博原图预览' })).toBeVisible()
  await expect(page.locator('body')).toHaveCSS('overflow', 'hidden')
  await page.goBack()
  await expect(page.locator('main h1')).toHaveText('一切，尽在掌握。')
  await expect(page.locator('main h1')).toBeVisible()
  await expect(page.getByRole('dialog', { name: '微博原图预览' })).toHaveCount(0)
  await expect(page.locator('body')).not.toHaveCSS('overflow', 'hidden')
  await page.goForward()
  await expect(page.locator('main h1')).toHaveText('监控数据')
  await expect(page.getByRole('heading', { name: '图片用户' })).toBeVisible()
  await expect(page.getByRole('dialog', { name: '微博原图预览' })).toHaveCount(0)
})
