import { createRequest } from './hengxin/http'
import { createIdentityRequest, IdentityError, record } from './identity/request'

export type Business = 'domestic' | 'overseas'
export type Intent = 'connect' | 'renew' | 'replace'
export type AccountStatus = 'empty' | 'unchecked' | 'ready' | 'expired' | 'network'
export interface Account {
  status: AccountStatus; email: string; workspace: string; checked: string; updated: string
  audit: { time: string; operator: string; action: string; result: string }[]
  revision: number; checking: boolean
}
export interface Authorization {
  id: string; step: 'starting' | 'waiting' | 'checking' | 'expired' | 'failed' | 'mismatch' | 'verified'
  userCode: string; verificationUrl: string; expiresAt: number
  candidateEmail: string; candidateWorkspace: string; different: boolean; message: string
}
export const businessNames = { domestic: '国内业务', overseas: '海外业务' }
export const statusNames = { empty: '未配置', unchecked: '尚未检测', ready: '可用', expired: '授权已失效', network: '连接异常' }
export const statusTypes = { empty: 'info', unchecked: 'info', ready: 'success', expired: 'danger', network: 'warning' } as const
const strings = (v: Record<string, unknown>, keys: string[]) => keys.every(key => typeof v[key] === 'string')
export function isAccount(v: unknown): v is Account {
  return record(v) && typeof v.status === 'string' && Object.hasOwn(statusNames, v.status)
    && strings(v, ['email', 'workspace', 'checked', 'updated']) && Number.isInteger(v.revision) && Number(v.revision) >= 0
    && typeof v.checking === 'boolean' && Array.isArray(v.audit)
    && v.audit.every(row => record(row) && strings(row, ['time', 'operator', 'action', 'result']))
}
export function isAuthorization(v: unknown): v is Authorization {
  return record(v) && strings(v, ['id', 'step', 'userCode', 'verificationUrl', 'candidateEmail', 'candidateWorkspace', 'message'])
    && !!v.id && ['starting', 'waiting', 'checking', 'expired', 'failed', 'mismatch', 'verified'].includes(String(v.step))
    && typeof v.expiresAt === 'number' && Number.isFinite(v.expiresAt) && v.expiresAt >= 0 && typeof v.different === 'boolean'
}
export function createCodexAuthApi(side: Business, fetcher: typeof fetch = fetch) {
  const domestic = createRequest('/api/v1/management/codex-auth', fetcher)
  const overseas = createIdentityRequest(async (url, init) => {
    const response = await fetcher(url, init)
    if (response.ok) return response
    const value: unknown = await response.clone().json().catch(() => undefined)
    if (!record(value) || typeof value.message !== 'string') return response
    // Business APIs return {code,message,requestId}; the identity helper reads detail.
    const headers = new Headers(response.headers)
    headers.delete('content-length')
    return new Response(JSON.stringify({ ...value, detail: value.message }), { status: response.status, headers })
  })
  const request = <T>(path: string, guard: (v: unknown) => v is T, method: 'GET' | 'POST' | 'DELETE' = 'GET', body?: unknown) => side === 'domestic'
    ? domestic(path, guard, method, body, 15000, method === 'GET' ? {} : { 'X-HX-Request': '1' })
    : overseas('/api/overseas/v1/management/codex-auth' + path, guard, body, { method, timeoutMs: 15000 })
  const path = (id: string) => '/authorizations/' + encodeURIComponent(id)
  return {
    get: () => request('', isAccount),
    check: () => request('/check', isAccount, 'POST', {}),
    start: (intent: Intent, revision: number) => request('/authorizations', isAuthorization, 'POST', { intent, revision }),
    poll: (id: string) => request(path(id), isAuthorization),
    retry: (id: string) => request(path(id) + '/retry', isAuthorization, 'POST', {}),
    activate: (id: string, acknowledged: boolean) => request(path(id) + '/activate', isAccount, 'POST', { acknowledged }),
    cancel: (id: string) => request(path(id), (v): v is { ok: true } => record(v) && v.ok === true, 'DELETE', {}),
    remove: (revision: number) => request('', isAccount, 'DELETE', { revision })
  }
}
export type CodexAuthApi = ReturnType<typeof createCodexAuthApi>
export function authError(reason: unknown): string {
  if (record(reason) && reason.status === 409) return '账号配置或授权流程已变化，请重新读取当前配置后再试'
  if (reason instanceof IdentityError && typeof reason.detail === 'string') return reason.detail
  return reason instanceof Error ? reason.message : '服务暂不可用，请重试'
}
export function officialAuthorizationUrl(value: string): string {
  try { const url = new URL(value); return url.protocol === 'https:' && url.hostname === 'auth.openai.com' && !url.username && !url.password ? url.href : '' }
  catch { return '' }
}
