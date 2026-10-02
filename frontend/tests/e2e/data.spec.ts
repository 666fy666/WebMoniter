import { test, expect, type Page } from '@playwright/test'

const avatar =
  '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48"><rect width="48" height="48" fill="#794ca6"/><circle cx="24" cy="17" r="8" fill="#eee4f6"/><path d="M8 46v-5a16 16 0 0 1 32 0v5" fill="#eee4f6"/></svg>'
const longText = '这是用于检查阅读体验的长正文，包含中文、标点与换行。\n'.repeat(15)

async function login(page: Page) {
  await page.goto('/login')
  await page.getByLabel('用户名', { exact: true }).fill('admin')
  await page.getByLabel('密码', { exact: true }).fill('ui-test-only-password')
  await page.getByRole('button', { name: '进入工作空间' }).click()
  await expect(page.getByRole('heading', { name: '一切，尽在掌握。' })).toBeVisible()
}

async function mockImages(page: Page) {
  await page.route('**/weibo_img/**', (route) =>
    route.fulfill({ contentType: 'image/svg+xml', body: avatar }),
  )
  await page.route('https://avatar.test/**', (route) =>
    route.fulfill({ contentType: 'image/svg+xml', body: avatar }),
  )
  await page.route('**/weibo_img/missing.jpg', (route) => route.fulfill({ status: 404, body: '' }))
}

test.beforeEach(async ({ page }) => {
  await login(page)
})

test('avatars, fallback, updated URLs and expandable posts', async ({ page }, testInfo) => {
  await mockImages(page)
  let repaired = false
  await page.route('**/api/v1/data/weibo?*', (route) =>
    route.fulfill({
      json: {
        data: [
          {
            UID: '123',
            用户名: '微博用户',
            avatar_url: '/weibo_img/user/profile_image.jpg',
            文本: longText,
            retweeted_status: { text: longText },
            url: 'https://weibo.com/u/123',
          },
          {
            UID: '456',
            用户名: '缺失头像',
            avatar_url: repaired ? '/weibo_img/repaired.jpg' : '/weibo_img/missing.jpg',
            文本: '头像加载失败时显示首字。',
          },
          {
            UID: 'long-id-'.repeat(20),
            用户名: '很长的用户名'.repeat(10),
            文本: 'https://example.test/' + 'long-path'.repeat(40),
          },
        ],
        total: 3,
        total_pages: 1,
      },
    }),
  )
  await page.route('**/api/v1/data/huya?*', (route) =>
    route.fulfill({
      json: {
        data: [
          { room: '123', name: '虎牙用户', avatar_url: '//avatar.test/huya.svg', is_live: true },
        ],
        total: 1,
        total_pages: 1,
      },
    }),
  )
  await page.goto('/data')
  const image = page.getByRole('img', { name: '微博用户的头像', exact: true })
  await expect(image).toBeVisible()
  await expect(image).toHaveJSProperty('naturalWidth', 48)
  await expect(page.getByLabel('缺失头像的默认头像', { exact: true })).toHaveText('缺')
  await expect(page.getByRole('img', { name: '缺失头像的头像', exact: true })).toHaveCount(0)
  const card = page.locator('.data-card').first()
  const expand = card.getByRole('button', { name: '展开全文', exact: true }).first()
  await expect(expand).toHaveAttribute('aria-expanded', 'false')
  await expand.click()
  await expect(card.getByRole('button', { name: '收起正文', exact: true })).toHaveAttribute(
    'aria-expanded',
    'true',
  )
  await expect(card.locator('.post-body').first()).not.toHaveClass(/collapsed/)
  await card.getByRole('button', { name: '收起正文', exact: true }).click()
  await card.locator('summary').click()
  await card.locator('.repost').getByRole('button', { name: '展开全文' }).click()
  await expect(card.locator('.repost .post-body')).not.toHaveClass(/collapsed/)
  await card.locator('summary').click()

  repaired = true
  await page.getByRole('button', { name: '刷新数据' }).click()
  await expect(page.getByRole('img', { name: '缺失头像的头像', exact: true })).toHaveJSProperty(
    'naturalWidth',
    48,
  )
  await expect(page.getByLabel('缺失头像的默认头像', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '刷新数据' })).toBeEnabled()

  for (const theme of ['light', 'dark']) {
    await page.evaluate((value) => {
      document.documentElement.dataset.theme = value
    }, theme)
    await expect(page.locator('body')).toHaveJSProperty(
      'scrollWidth',
      await page.evaluate(() => innerWidth),
    )
    await page.screenshot({
      path: `test-results/data-${theme}-${testInfo.project.name}.png`,
      fullPage: true,
    })
  }
  await page.getByRole('button', { name: '虎牙', exact: true }).click()
  const huya = page.getByRole('img', { name: '虎牙用户的头像', exact: true })
  await expect(huya).toHaveAttribute('src', 'https://avatar.test/huya.svg')
  await expect(huya).toHaveAttribute('referrerpolicy', 'no-referrer')
  await expect(huya).toHaveJSProperty('naturalWidth', 48)
  await expect(page.getByText('直播中', { exact: true })).toBeVisible()
})

test('invalid avatar URLs stay as placeholders without loading remote content', async ({
  page,
}) => {
  await page.route('**/api/v1/data/weibo?*', (route) =>
    route.fulfill({
      json: {
        data: [
          { UID: '1', 用户名: '非法协议', avatar_url: 'javascript:alert(1)' },
          { UID: '2', 用户名: '嵌入图片', avatar_url: 'data:image/svg+xml,invalid' },
          { UID: '3', 用户名: '非图片路径', avatar_url: '/api/v1/config' },
        ],
        total: 3,
        total_pages: 1,
      },
    }),
  )
  await page.goto('/data')
  await expect(page.getByLabel('非法协议的默认头像')).toBeVisible()
  await expect(page.getByLabel('嵌入图片的默认头像')).toBeVisible()
  await expect(page.getByLabel('非图片路径的默认头像')).toBeVisible()
  await expect(page.locator('.avatar img')).toHaveCount(0)
})

test('loading, failure, retry and empty data remain distinct', async ({ page }) => {
  let release!: () => void
  const gate = new Promise<void>((resolve) => (release = resolve))
  let failed = true
  await page.route('**/api/v1/data/weibo?*', async (route) => {
    await gate
    await route.fulfill(
      failed
        ? { status: 500, json: { error: '测试读取失败' } }
        : { json: { data: [], total: 0, total_pages: 0 } },
    )
  })
  await page.goto('/data')
  await expect(page.getByRole('heading', { name: '正在读取动态…' })).toBeVisible()
  await expect(page.getByRole('link', { name: '前往配置', exact: true })).toHaveCount(0)
  release()
  await expect(page.getByRole('alert')).toContainText('测试读取失败')
  await expect(page.getByRole('heading', { name: '等待第一条动态' })).toHaveCount(0)
  failed = false
  await page.getByRole('button', { name: '重新加载' }).click()
  await expect(page.getByRole('heading', { name: '等待第一条动态' })).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
})

test('switching platform during an in-flight request loads the new platform immediately', async ({
  page,
}) => {
  let release!: () => void
  const gate = new Promise<void>((resolve) => (release = resolve))
  await page.route('**/api/v1/data/weibo?*', async (route) => {
    await gate
    await route.fulfill({
      json: { data: [{ UID: '1', 用户名: '旧平台数据' }], total: 1, total_pages: 1 },
    })
  })
  await page.route('**/api/v1/data/huya?*', (route) =>
    route.fulfill({
      json: {
        data: [{ room: '1', name: '新平台数据' }],
        total: 1,
        total_pages: 1,
      },
    }),
  )
  await page.goto('/data')
  await expect(page.getByRole('heading', { name: '正在读取动态…' })).toBeVisible()
  await page.getByRole('button', { name: '虎牙', exact: true }).click()
  release()
  await expect(page.getByRole('heading', { name: '新平台数据' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '旧平台数据' })).toHaveCount(0)
})

test('refresh failure retains the last successful data', async ({ page }) => {
  let failed = false
  await page.route('**/api/v1/data/weibo?*', (route) =>
    route.fulfill(
      failed
        ? {
            status: 500,
            json: { error: '暂时不可用' },
          }
        : { json: { data: [{ UID: '1', 用户名: '已读取的数据' }], total: 1, total_pages: 1 } },
    ),
  )
  await page.goto('/data')
  await expect(page.getByRole('heading', { name: '已读取的数据' })).toBeVisible()
  failed = true
  await page.getByRole('button', { name: '刷新数据' }).click()
  await expect(page.getByRole('alert')).toContainText('当前显示上次成功读取的数据')
  await expect(page.getByRole('heading', { name: '已读取的数据' })).toBeVisible()
})

test('task times and sticky save controls remain usable', async ({ page }, testInfo) => {
  await page.goto('/tasks')
  const nextRun = page.locator('.next-run').first()
  await expect(nextRun).toBeVisible()
  await expect(page.locator('body')).toHaveJSProperty(
    'scrollWidth',
    await page.evaluate(() => innerWidth),
  )
  await page.goto('/config?section=weibo')
  await expect(page.getByLabel('监控间隔（秒）', { exact: true })).toBeVisible()
  const save = page.getByRole('button', { name: '保存当前模块' })
  await expect(save).toBeInViewport()
  await page.getByLabel('监控间隔（秒）', { exact: true }).fill('410')
  await expect(save).toBeEnabled()
  const bounds = await save.boundingBox()
  expect(bounds).not.toBeNull()
  expect(bounds!.height).toBeGreaterThanOrEqual(44)
  const nav = page.getByRole('navigation', { name: '移动导航' })
  if (await nav.isVisible()) {
    const navBounds = await nav.boundingBox()
    expect(bounds!.y + bounds!.height).toBeLessThan(navBounds!.y)
  }
  const clickable = await save.evaluate((button) => {
    const rect = button.getBoundingClientRect()
    return button.contains(
      document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2),
    )
  })
  expect(clickable).toBe(true)
  await page.screenshot({ path: `test-results/config-sticky-${testInfo.project.name}.png` })
  await save.click()
  await expect(page.getByRole('status')).toContainText('配置已保存')
})

test('all workspace pages fit a narrow phone in both themes', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'Smallest phone viewport')
  await page.setViewportSize({ width: 320, height: 740 })
  for (const theme of ['light', 'dark']) {
    for (const path of ['/', '/tasks', '/data', '/config', '/logs', '/account']) {
      await page.goto(path)
      await page.evaluate((value) => {
        document.documentElement.dataset.theme = value
      }, theme)
      await expect(page.locator('main h1')).toBeVisible()
      await expect(page.locator('body')).toHaveJSProperty('scrollWidth', 320)
    }
  }
})
