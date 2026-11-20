import { createIdentityRequest, IdentityError, record } from '../identity/request'

export const feedbackStatuses = { pending: '待处理', processing: '处理中', resolved: '已处理' } as const
export type FeedbackStatus = keyof typeof feedbackStatuses
export interface FeedbackSource { source: string; taskName?: string; sku?: string }
export interface TaskFeedbackContext { id: string; pending: boolean; name?: string; sku?: string; studio?: boolean }
export interface Feedback {
  id: string
  question: string
  source: string
  task_name: string | null
  sku: string | null
  submitter_id: string
  submitter_name: string
  status: FeedbackStatus
  public_reply: string
  screenshot_url: string | null
  created_at: string
  updated_at: string
  version: number
}
export interface ManagedFeedback extends Feedback { internal_note: string }
export interface FeedbackPage<T extends Feedback> { items: T[]; total: number }
export type FeedbackCounts = Record<FeedbackStatus, number>
interface ManagedPage extends FeedbackPage<ManagedFeedback> { counts: FeedbackCounts }
export type FeedbackEdit = Pick<ManagedFeedback, 'status' | 'public_reply' | 'internal_note' | 'version'>
const base = '/api/overseas/v1/feedback'
const management = '/api/overseas/v1/management/feedback'
const screenshotPath = (id: string) => base + '/' + encodeURIComponent(id) + '/screenshot'
const count = (value: unknown) => Number.isInteger(value) && Number(value) >= 0
function isFeedback(value: unknown): value is Feedback {
  return record(value) && typeof value.id === 'string' && !!value.id
    && ['question', 'source', 'submitter_id', 'submitter_name', 'public_reply', 'created_at', 'updated_at'].every(k => typeof value[k] === 'string')
    && ['task_name', 'sku'].every(k => value[k] === null || typeof value[k] === 'string')
    && (value.screenshot_url === null || value.screenshot_url === screenshotPath(value.id))
    && Object.hasOwn(feedbackStatuses, String(value.status)) && Number.isInteger(value.version) && Number(value.version) > 0
}
const personal = (value: unknown): value is Feedback => isFeedback(value) && !('internal_note' in value)
const managed = (value: unknown): value is ManagedFeedback =>
  isFeedback(value) && 'internal_note' in value && typeof value.internal_note === 'string'
function pageOf<T extends Feedback>(guard: (value: unknown) => value is T) {
  return (value: unknown): value is FeedbackPage<T> =>
    record(value) && count(value.total) && Array.isArray(value.items) && value.items.every(guard)
}
function managedPage(value: unknown): value is ManagedPage {
  if (!pageOf(managed)(value) || !('counts' in value)) return false
  const counts = value.counts
  return record(counts) && Object.keys(feedbackStatuses).every(status => count(counts[status]))
}

const screenshotTypes = ['image/png', 'image/jpeg', 'image/webp']
export function screenshotIssue(file: File) {
  if (!screenshotTypes.includes(file.type)) return '请选择 PNG、JPG 或 WebP 图片'
  if (file.size === 0 || file.size > 5 * 1024 * 1024) return '请上传非空且不超过 5 MB 的截图'
  return ''
}
export function feedbackSourceText(source: string, taskName?: string | null, sku?: string | null) {
  return [source, taskName, sku].filter(Boolean).join(' · ')
}
export function feedbackError(reason: unknown) {
  if (reason instanceof IdentityError) {
    if (reason.status === 409) return '这条反馈已由其他管理员更新，请刷新最新记录后再编辑。'
    if (reason.status === 422 || reason.status === 413 || reason.status === 415) return '请检查填写内容及截图格式、大小后重试'
  }
  return reason instanceof Error ? reason.message : '反馈服务暂不可用，请重试'
}
export const feedbackAccessDenied = (reason: unknown) => reason instanceof IdentityError && [401, 403].includes(reason.status)

export function createFeedbackApi(fetcher: typeof fetch, authorize: (management: boolean) => Promise<void>) {
  const request = createIdentityRequest((url, options) => fetcher(url, { ...options, cache: 'no-store', redirect: 'error' }))
  async function send(url: string, options: RequestInit) {
    let response: Response
    try {
      response = await fetcher(url, { ...options, credentials: 'include', cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(60000) })
    } catch { throw new IdentityError(0, '反馈服务连接失败，请重试') }
    if (!response.ok) {
      const message = response.status === 401 ? '身份已失效，请重新登录' : response.status === 403 ? '暂无权限' : '反馈请求失败，请重试'
      throw new IdentityError(response.status, message)
    }
    return response
  }
  return {
    async create(source: FeedbackSource, question: string, screenshot?: File) {
      if (screenshot && screenshotIssue(screenshot)) throw new Error(screenshotIssue(screenshot))
      await authorize(false)
      const body = new FormData()
      body.set('source', source.source)
      body.set('question', question.trim())
      if (source.taskName) body.set('task_name', source.taskName)
      if (source.sku) body.set('sku', source.sku)
      if (screenshot) body.set('screenshot', screenshot)
      const response = await send(base, { method: 'POST', headers: { 'X-HX-Request': '1', Accept: 'application/json' }, body })
      const value: unknown = await response.json()
      if (!personal(value)) throw new IdentityError(0, '反馈服务返回了无效记录')
      return value
    },
    async mine(offset: number, limit: number) {
      await authorize(false)
      return request(base + '/mine', pageOf(personal), undefined, { params: { offset, limit } })
    },
    async list(status: FeedbackStatus | '', offset: number, limit: number) {
      await authorize(true)
      return request(management, managedPage, undefined, { params: { status, offset, limit } })
    },
    async detail(id: string) {
      await authorize(true)
      return request(management + '/' + encodeURIComponent(id), (value): value is ManagedFeedback => managed(value) && value.id === id)
    },
    async save(id: string, edit: FeedbackEdit) {
      await authorize(true)
      return request(management + '/' + encodeURIComponent(id), (value): value is ManagedFeedback => managed(value) && value.id === id, edit, { method: 'PATCH' })
    },
    async screenshot(id: string, forManagement: boolean) {
      await authorize(forManagement)
      const response = await send(screenshotPath(id), { method: 'GET' })
      const blob = await response.blob()
      if (!screenshotTypes.includes(blob.type)) throw new IdentityError(0, '截图格式无效')
      return blob
    }
  }
}
export type FeedbackApi = ReturnType<typeof createFeedbackApi>
