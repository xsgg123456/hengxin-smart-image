import * as validate from './validate'
import { identity, checkIdentityResponse } from './identity'
import type { ManagementService } from '../../types/management'
import type { ApiErrorBody, HengxinService } from '../../types/hengxin'

export class ApiError extends Error {
  constructor(public code: string, message: string, public status = 0) { super(message) }
}

export function createRequest(baseUrl: string, fetcher: typeof fetch = fetch) {
  async function request<T>(path: string, guard: (value: unknown) => value is T, method = 'GET', body?: unknown, timeoutMs = 10000, headers: Record<string, string> = {}): Promise<T> {
    const epoch = identity.epoch
    const reading = method === 'GET' ? identity.read() : undefined
    try {
    let response: Response
    try {
      response = await fetcher(`${baseUrl.replace(/\/$/, '')}${path}`, {
        method, credentials: 'include', signal: reading ? AbortSignal.any([reading.signal, AbortSignal.timeout(timeoutMs)]) : AbortSignal.timeout(timeoutMs),
        headers: { Accept: 'application/json', ...(body === undefined || body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...headers },
        body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body)
      })
    } catch {
      identity.assert(epoch)
      throw new ApiError('UNAVAILABLE', '服务连接失败，请检查网络或稍后重试')
    }
    identity.assert(epoch)
    if (!response.ok) {
      const errorEpoch = await checkIdentityResponse(response.status, epoch, path === '/auth/me')
      identity.assert(errorEpoch)
      let error: Partial<ApiErrorBody> = {}
      try {
        const value: unknown = await response.json()
        if (value && typeof value === 'object') error = value as Partial<ApiErrorBody>
      } catch { /* 非 JSON 网关错误使用本地提示 */ }
      identity.assert(errorEpoch)
      throw new ApiError(typeof error.code === 'string' ? error.code : 'HTTP_ERROR',
        typeof error.message === 'string' ? error.message : `服务请求失败（${response.status}）`, response.status)
    }
    if (response.status === 204 && guard(undefined)) return undefined as T
    if (!response.headers.get('content-type')?.includes('application/json')) {
      throw new ApiError('INVALID_RESPONSE', '服务响应格式错误，请稍后重试')
    }
    let value: unknown
    try { value = await response.json() } catch {
      identity.assert(epoch)
      throw new ApiError('INVALID_RESPONSE', '服务响应无法解析，请稍后重试')
    }
    identity.assert(epoch)
    if (!guard(value)) throw new ApiError('INVALID_RESPONSE', '服务返回的数据不完整，请稍后重试')
    return value
    } finally { reading?.release() }
  }
  return request
}

export function createHttpService(baseUrl: string, fetcher: typeof fetch = fetch): Omit<HengxinService, keyof ManagementService> {
  const request = createRequest(baseUrl, fetcher)
  return { getUser: () => request('/auth/me', validate.user), dispose() {} }
}
