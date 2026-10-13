export class IdentityError extends Error {
  constructor(public status: number, message: string, public detail?: unknown) { super(message) }
}
export function createIdentityRequest(fetcher: typeof fetch = fetch) {
  return async function request<T>(url: string, guard: (v: unknown) => v is T, body?: unknown, options?: { method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'; params?: Record<string, string | number | undefined>; idempotencyKey?: string; timeoutMs?: number }): Promise<T> {
    const query = new URLSearchParams()
    for (const [key, value] of Object.entries(options?.params || {})) if (value !== undefined && value !== '') query.set(key, String(value))
    if (query.size) url += `?${query}`
    let response: Response
    try {
      response = await fetcher(url, { method: options?.method || (body === undefined ? 'GET' : 'POST'), credentials: 'include',
        headers: { Accept: 'application/json', ...(options?.idempotencyKey ? { 'Idempotency-Key': options.idempotencyKey } : {}), ...(body === undefined ? {} : { 'Content-Type': 'application/json', 'X-HX-Request': '1' }) },
        body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(options?.timeoutMs ?? 10000) })
    } catch { throw new IdentityError(0, '服务连接失败，请稍后重试') }
    let value: unknown
    try { value = response.status === 204 ? undefined : await response.json() } catch { value = undefined }
    if (!response.ok) {
      const detail = record(value) ? value.detail : undefined
      const message = response.status === 401 ? '身份已失效，请重新登录' : response.status === 403 ? '暂无权限' : response.status === 409 ? '成员资料已变化或操作违反管理员保护规则，请刷新后重试' : response.status === 422 ? '成员资料不符合要求，请检查角色与状态' : '服务暂不可用，请重试'
      throw new IdentityError(response.status, message, detail)
    }
    if (!guard(value)) throw new IdentityError(0, '服务响应格式错误，请重试')
    return value
  }
}
export const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
