import * as validate from './validate'
import type { ManagementService } from '../../types/management'
import type { ApiErrorBody, HengxinService } from '../../types/hengxin'

export class ApiError extends Error {
  constructor(public code: string, message: string, public status = 0) { super(message) }
}

export function createRequest(baseUrl: string, fetcher: typeof fetch = fetch) {
  async function request<T>(path: string, guard: (value: unknown) => value is T, method = 'GET', body?: unknown): Promise<T> {
    let response: Response
    try {
      response = await fetcher(`${baseUrl.replace(/\/$/, '')}${path}`, {
        method, credentials: 'include', signal: AbortSignal.timeout(10000),
        headers: { Accept: 'application/json', ...(body === undefined || body instanceof FormData ? {} : { 'Content-Type': 'application/json' }) },
        body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body)
      })
    } catch {
      throw new ApiError('UNAVAILABLE', '服务连接失败，请检查网络或稍后重试')
    }
    if (!response.ok) {
      if (response.status === 401 && typeof window !== 'undefined') window.dispatchEvent(new Event('hengxin:unauthorized'))
      let error: Partial<ApiErrorBody> = {}
      try {
        const value: unknown = await response.json()
        if (value && typeof value === 'object') error = value as Partial<ApiErrorBody>
      } catch { /* 非 JSON 网关错误使用本地提示 */ }
      throw new ApiError(typeof error.code === 'string' ? error.code : 'HTTP_ERROR',
        typeof error.message === 'string' ? error.message : `服务请求失败（${response.status}）`, response.status)
    }
    if (response.status === 204 && guard(undefined)) return undefined as T
    if (!response.headers.get('content-type')?.includes('application/json')) {
      throw new ApiError('INVALID_RESPONSE', '服务响应格式错误，请稍后重试')
    }
    let value: unknown
    try { value = await response.json() } catch {
      throw new ApiError('INVALID_RESPONSE', '服务响应无法解析，请稍后重试')
    }
    if (!guard(value)) throw new ApiError('INVALID_RESPONSE', '服务返回的数据不完整，请稍后重试')
    return value
  }
  return request
}

export function createHttpService(baseUrl: string, fetcher: typeof fetch = fetch): Omit<HengxinService, keyof ManagementService> {
  const request = createRequest(baseUrl, fetcher)
  const queryString = (query: object) => {
    const params = new URLSearchParams()
    Object.entries(query).forEach(([key, value]) => { if (value !== undefined) params.set(key, String(value)) })
    return params.toString()
  }
  return {
    getUser: () => request('/auth/me', validate.user),
    getWorkspace: () => request('/workspace', validate.workspace),
    listTasks: query => request(`/tasks?${queryString(query)}`, validate.taskPage),
    getTask: id => request(`/tasks/${encodeURIComponent(id)}`, validate.taskDetail),
    deleteTask: id => request(`/tasks/${encodeURIComponent(id)}`, validate.deletion, 'DELETE'),
    listArchives: query => request(`/archives?${queryString(query)}`, validate.archivePage),
    getArchive: id => request(`/archives/${encodeURIComponent(id)}`, validate.archive),
    listTemplates: query => {
      const params = new URLSearchParams()
      Object.entries(query).forEach(([key, value]) => { if (value !== undefined) params.set(key, String(value)) })
      return request(`/templates?${params}`, validate.templatePage)
    },
    getTemplate: id => request(`/templates/${encodeURIComponent(id)}`, validate.template),
    listSkills: mode => request(`/skills${mode ? `?mode=${encodeURIComponent(mode)}` : ''}`, validate.skillList),
    uploadFile: file => {
      const data = new FormData()
      data.append('file', file)
      return request('/files', validate.uploadedPicture, 'POST', data)
    },
    saveTemplate: template => request(template.id ? `/templates/${encodeURIComponent(template.id)}` : '/templates', validate.template, template.id ? 'PUT' : 'POST', template),
    deleteTemplate: id => request(`/templates/${encodeURIComponent(id)}`, validate.noContent, 'DELETE'),
    createTask: input => request('/tasks', validate.accepted, 'POST', input),
    revise: input => request(`/tasks/${encodeURIComponent(input.taskId)}/rounds`, validate.accepted, 'POST', input),
    archive: taskId => request(`/tasks/${encodeURIComponent(taskId)}/archives`, validate.archive, 'POST'),
    deleteArchive: id => request(`/archives/${encodeURIComponent(id)}`, validate.noContent, 'DELETE'),
    dispose() {}
  }
}
