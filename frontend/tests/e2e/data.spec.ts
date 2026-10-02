import { test, expect, type Page } from './fixtures'

const avatar =
  '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48"><rect width="48" height="48" fill="#794ca6"/><circle cx="24" cy="17" r="8" fill="#eee4f6"/><path d="M8 46v-5a16 16 0 0 1 32 0v5" fill="#eee4f6"/></svg>'
const longText = '这是用于检查阅读体验的长正文，包含中文、标点与换行。\n'.repeat(15)

async function mockImages(page: Page) {
  await page.route('**/weibo_img/**', (route) =>
    route.fulfill({ contentType: 'image/svg+xml', body: avatar }),
  )
  await page.route('https://avatar.test/**', (route) =>
    route.fulfill({ contentType: 'image/svg+xml', body: avatar }),
  )
  await page.route('**/weibo_img/missing.jpg', (route) => route.fulfill({ status: 404, body: '' }))
}

test('weibo images open in-page with navigation, zoom, download and focus restoration', async ({
  page,
  context,
}) => {
  await mockImages(page)
  await page.route('**/api/v1/data/weibo?*', (route) =>
    route.fulfill({
      json: {
        data: [
          {
            UID: '1',
            用户名: '图片用户',
            images: ['/weibo_img/original-1.jpg', '/weibo_img/original-2.jpg'],
            image_thumbs: ['/weibo_img/thumb-1.jpg', '/weibo_img/thumb-2.jpg'],
          },
        ],
        total: 1,
        total_pages: 1,
      },
    }),
  )
  await page.goto('/data')
  const trigger = page.getByRole('button', { name: '查看第 2 张图片', exact: true })
  const pageCount = context.pages().length
  await trigger.click()
  const viewer = page.getByRole('dialog', { name: '微博原图预览' })
  const image = viewer.locator('.weibo-lightbox-image')
  await expect(viewer).toBeVisible()
  await expect(image).toHaveAttribute('src', '/weibo_img/original-2.jpg')
  await expect(image).toHaveJSProperty('naturalWidth', 48)
  await expect(viewer.locator('.weibo-lightbox-counter')).toHaveText('2 / 2')
  await expect(page.locator('body')).toHaveCSS('overflow', 'hidden')
  await viewer.getByRole('button', { name: '下一张', exact: true }).click()
  await expect(image).toHaveAttribute('src', '/weibo_img/original-1.jpg')
  await viewer.getByRole('button', { name: '放大图片', exact: true }).click()
  await expect(viewer.locator('.weibo-lightbox-zoom-level')).toHaveText('125%')
  await viewer.getByRole('button', { name: '适应窗口', exact: true }).click()
  await expect(viewer.locator('.weibo-lightbox-zoom-level')).toHaveText('100%')
  await page.keyboard.press('ArrowLeft')
  await expect(image).toHaveAttribute('src', '/weibo_img/original-2.jpg')
  await viewer.getByRole('button', { name: '查看第 1 张图片', exact: true }).click()
  await expect(image).toHaveAttribute('src', '/weibo_img/original-1.jpg')
  await image.dblclick()
  await expect(viewer.locator('.weibo-lightbox-zoom-level')).toHaveText('200%')
  const bounds = (await image.boundingBox())!
  const center = { x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height / 2 }
  await page.mouse.move(center.x, center.y)
  await page.mouse.down()
  await page.mouse.move(center.x + 60, center.y + 20)
  await page.mouse.up()
  await expect(image).toHaveCSS('transform', 'matrix(2, 0, 0, 2, 60, 20)')
  await page.keyboard.press('0')
  await page.mouse.move(center.x, center.y)
  await page.mouse.down()
  await page.mouse.move(center.x - 80, center.y)
  await page.mouse.up()
  await expect(image).toHaveAttribute('src', '/weibo_img/original-2.jpg')
  await viewer.getByRole('button', { name: '查看第 1 张图片', exact: true }).click()
  const downloaded = page.waitForEvent('download')
  await viewer.getByRole('link', { name: '下载当前图片' }).click()
  expect((await downloaded).suggestedFilename()).toBe('weibo-01.jpg')
  expect(context.pages()).toHaveLength(pageCount)
  await expect(page).toHaveURL(/\/data$/)
  await page.keyboard.press('Escape')
  await expect(viewer).toHaveCount(0)
  await expect(trigger).toBeFocused()
  await expect(page.locator('body')).not.toHaveCSS('overflow', 'hidden')
  await trigger.click()
  await viewer.getByRole('button', { name: '关闭大图' }).click()
  await expect(viewer).toHaveCount(0)
})

test('weibo preview preserves image pairing, handles missing thumbnails and retries failed originals', async ({
  page,
}) => {
  await mockImages(page)
  let failed = true
  await page.route('**/weibo_img/original-2.jpg', (route) =>
    route.fulfill(
      failed ? { status: 404, body: '' } : { contentType: 'image/svg+xml', body: avatar },
    ),
  )
  await page.route('**/api/v1/data/weibo?*', (route) =>
    route.fulfill({
      json: {
        data: [
          {
            UID: '1',
            images: ['/weibo_img/original-1.jpg', '/weibo_img/original-2.jpg'],
            image_thumbs: ['invalid:', '/weibo_img/thumb-2.jpg'],
          },
          { UID: '2', images: ['/weibo_img/only-original.jpg'] },
          { UID: '3', image_thumbs: ['/weibo_img/only-thumb.jpg'] },
        ],
        total: 3,
        total_pages: 1,
      },
    }),
  )
  await page.goto('/data')
  const cards = page.locator('.data-card')
  await expect(cards.first().locator('.post-images img').first()).toHaveAttribute(
    'src',
    '/weibo_img/original-1.jpg',
  )
  await cards.first().getByRole('button', { name: '查看第 2 张图片' }).click()
  const viewer = page.getByRole('dialog', { name: '微博原图预览' })
  await expect(viewer.getByRole('alert')).toContainText('原图暂时无法显示')
  failed = false
  await viewer.getByRole('button', { name: '重新加载' }).click()
  await expect(viewer.locator('.weibo-lightbox-image')).toBeVisible()
  await expect(viewer.locator('.weibo-lightbox-image')).toHaveAttribute(
    'src',
    '/weibo_img/original-2.jpg',
  )
  await expect(viewer.getByRole('alert')).toHaveCount(0)
  await page.keyboard.press('Escape')
  for (const [i, src] of [
    [1, '/weibo_img/only-original.jpg'],
    [2, '/weibo_img/only-thumb.jpg'],
  ] as const) {
    await cards.nth(i).getByRole('button', { name: '查看第 1 张图片' }).click()
    await expect(viewer.locator('.weibo-lightbox-image')).toHaveAttribute('src', src)
    await expect(viewer.getByRole('button', { name: '下一张', exact: true })).toHaveCount(0)
    await viewer.click({ position: { x: 2, y: 70 } })
    await expect(viewer).toHaveCount(0)
  }
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
  const interval = page.getByLabel('监控间隔（秒）', { exact: true })
  await interval.fill(String(Number(await interval.inputValue()) + 1))
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
