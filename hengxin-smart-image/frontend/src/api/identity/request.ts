export class IdentityError extends Error {
  constructor(public status: number, message: string) { super(message) }
}
export function createIdentityRequest(fetcher: typeof fetch = fetch) {
  return async function request<T>(url: string, guard: (v: unknown) => v is T, body?: unknown): Promise<T> {
    let response: Response
    try {
      response = await fetcher(url, { method: body === undefined ? 'GET' : 'POST', credentials: 'include',
        headers: { Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json', 'X-HX-Request': '1' }) },
        body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(10000) })
    } catch { throw new IdentityError(0, '服务连接失败，请稍后重试') }
    if (!response.ok) throw new IdentityError(response.status, response.status === 401 ? '身份已失效，请重新登录' : response.status === 403 ? '暂无权限' : '服务暂不可用，请重试')
    const value: unknown = response.status === 204 ? undefined : await response.json()
    if (!guard(value)) throw new IdentityError(0, '服务响应格式错误，请重试')
    return value
  }
}
export const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
