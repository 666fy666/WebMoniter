import { test as base, expect } from '@playwright/test'

export { expect }
export type { Page } from '@playwright/test'
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.goto('/login')
    await page.getByLabel('用户名', { exact: true }).fill('admin')
    await page.getByLabel('密码', { exact: true }).fill('ui-test-only-password')
    await page.getByRole('button', { name: '进入工作空间' }).click()
    await expect(page.getByRole('heading', { name: '一切，尽在掌握。' })).toBeVisible()
    await use(page)
  },
})
