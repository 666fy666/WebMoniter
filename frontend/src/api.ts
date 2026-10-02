export interface Session {
  authenticated: boolean
  csrf_token: string
}
export interface Run {
  run_id: string
  job_id: string
  source: string
  status: string
  created_at: number
  started_at: number | null
  finished_at: number | null
  message: string
}
export interface Task {
  job_id: string
  description: string
  kind: string
  section: string
  enabled: boolean
  available: boolean
  next_run: string | null
  last_run: Run | null
}
export type Value = string | number | boolean | null | Value[] | { [key: string]: Value }
export type Config = Record<string, Value>
export interface ConfigResponse {
  version: string
  config: Config
}
export interface Metadata {
  defaults: Config
  fields: Record<
    string,
    Record<string, { label: string; secret: boolean; minimum?: number; maximum?: number }>
  >
  accounts: Record<string, string[]>
  strings: Record<string, string>
  tasks: { job_id: string; description: string; config_section: string }[]
  push_channels: { type: string; name: string; fields: string[] }[]
}

let csrf = ''
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public fields: { path: string; message: string }[] = [],
  ) {
    super(message)
  }
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    credentials: 'same-origin',
    ...options,
    signal: options.signal
      ? AbortSignal.any([options.signal, AbortSignal.timeout(15000)])
      : AbortSignal.timeout(15000),
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...options.headers },
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    if (response.status === 401 && path !== '/login')
      window.dispatchEvent(new Event('session-expired'))
    throw new ApiError(
      response.status,
      data.error || data.detail || '请求失败，请稍后重试',
      data.fields,
    )
  }
  if (data.csrf_token) csrf = data.csrf_token
  return data as T
}
export const send = <T>(path: string, body: unknown, method = 'POST') =>
  api<T>(path, { method, body: JSON.stringify(body) })
export const statusLabels: Record<string, string> = {
  queued: '排队中',
  running: '运行中',
  success: '已完成',
  partial: '部分成功',
  failed: '失败',
  skipped: '已跳过',
  timeout: '超时',
  interrupted: '已中断',
  idle: '尚未运行',
}
export function dateTime(value: number | string | null | undefined) {
  return value
    ? new Date(typeof value === 'number' ? value * 1000 : value).toLocaleString('zh-CN', {
        hour12: false,
      })
    : '—'
}
