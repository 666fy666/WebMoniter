import { afterEach, expect, test, vi } from 'vitest'
import { api, ApiError, dateTime } from '../src/api'
afterEach(() => {
  vi.unstubAllGlobals()
})
test('session token is sent on subsequent writes', async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({ csrf_token: 'fixture' }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ success: true }) })
  vi.stubGlobal('fetch', fetcher)
  await api('/session')
  await api('/config', { method: 'PUT', body: '{}' })
  expect(fetcher.mock.calls[1][1].headers['X-CSRF-Token']).toBe('fixture')
  expect(fetcher.mock.calls[1][1].credentials).toBe('same-origin')
})
test('safe API errors preserve status and field information', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue({ ok: false, status: 409, json: async () => ({ detail: '配置已变化' }) }),
  )
  await expect(api('/config')).rejects.toMatchObject({ status: 409, message: '配置已变化' })
})
test('empty timestamps render an explicit placeholder', () => {
  expect(dateTime(null)).toBe('—')
})
