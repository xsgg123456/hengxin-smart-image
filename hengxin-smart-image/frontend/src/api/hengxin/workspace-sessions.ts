import { createIdentityRequest, IdentityError, record } from '../identity/request'
import { isStudio, isTranscriptPage, type Studio } from '../shared/studio'
import { isWorkspaceKey, type WorkspaceKey } from '../shared/domestic-workspace-keys'

export const sessionStatuses = ['empty', 'queued', 'running', 'succeeded', 'failed', 'cancelled', 'unknown'] as const
export type SessionStatus = typeof sessionStatuses[number]
export interface ManagedSession {
  id: string; name: string; ownerId: string; ownerName: string; workspace: WorkspaceKey
  status: SessionStatus; turnCount: number; createdAt: string; updatedAt: string
  activeTurnId: string | null; version: number; taskId?: string; taskName?: string
}
export interface SessionFilters { ownerId: string; workspace: string; status: string; search: string; page: number; pageSize: number }
export interface SessionList {
  items: ManagedSession[]; total: number; page: number; pageSize: number
  counters: Record<SessionStatus | 'total', number>; members: { id: string; name: string }[]
}
export interface SessionDetail { session: ManagedSession; siblingSessions: ManagedSession[]; workspace: Studio }
const root = '/api/v1/management/domestic-studio/sessions'
const integer = (value: unknown) => Number.isSafeInteger(value) && Number(value) >= 0
export const taskViewBase = (id: string, workspace: string) => {
  if (!isWorkspaceKey(workspace)) throw Error('工作台入口无效')
  return `/api/v1/domestic-studio/tasks/${encodeURIComponent(id)}/view/${workspace}`
}
export const sessionBase = (id: string, base = root) => `${base}/${encodeURIComponent(id)}`
export function isManagedSession(value: unknown): value is ManagedSession {
  return record(value) && ['id', 'name', 'ownerId', 'ownerName', 'createdAt', 'updatedAt'].every(key => typeof value[key] === 'string')
    && isWorkspaceKey(value.workspace)
    && sessionStatuses.includes(value.status as SessionStatus) && integer(value.turnCount) && integer(value.version)
    && (value.taskId === undefined || typeof value.taskId === 'string') && (value.taskName === undefined || typeof value.taskName === 'string')
    && (value.activeTurnId === null || typeof value.activeTurnId === 'string')
}
export function isSessionList(value: unknown): value is SessionList {
  if (!record(value) || !record(value.counters)) return false
  const counters = value.counters
  return Array.isArray(value.items) && value.items.every(isManagedSession)
    && ['total', 'page', 'pageSize'].every(key => integer(value[key]))
    && ['total', ...sessionStatuses].every(key => integer(counters[key]))
    && Array.isArray(value.members) && value.members.every(member => record(member) && typeof member.id === 'string' && typeof member.name === 'string')
}
export function isSessionDetail(value: unknown, id: string, base = root): value is SessionDetail {
  if (!record(value) || !isManagedSession(value.session) || value.session.id !== id) return false
  const session = value.session
  return Array.isArray(value.siblingSessions) && value.siblingSessions.every(item => isManagedSession(item) && item.ownerId === session.ownerId && item.workspace === session.workspace && (!session.taskId || item.taskId === session.taskId))
    && isStudio(value.workspace, session.taskId || session.workspace, sessionBase(id, base), true)
    && value.workspace.conversationId === id
}
export function createWorkspaceSessionsApi(fetcher: typeof fetch = fetch, task?: { id: string; workspace: WorkspaceKey; ownerId: string }) {
  const base = task ? `${taskViewBase(task.id, task.workspace)}/sessions` : root
  const request = (signal?: AbortSignal) => createIdentityRequest((url, options) => fetcher(url, {
    ...options, cache: 'no-store', signal: signal && options?.signal ? AbortSignal.any([signal, options.signal]) : signal || options?.signal
  }))
  return {
    list: (filters: SessionFilters, signal?: AbortSignal) => request(signal)(base, isSessionList, undefined, { params: { ...filters } }),
    detail: (id: string, signal?: AbortSignal) => request(signal)(sessionBase(id, base), (v): v is SessionDetail => isSessionDetail(v, id, base)
      && (!task || v.session.taskId === task.id && v.session.workspace === task.workspace && v.session.ownerId === task.ownerId)),
    transcript: (id: string, after: number, signal?: AbortSignal) => request(signal)(`${sessionBase(id, base)}/transcript`, isTranscriptPage, undefined, { params: { after } })
  }
}
export async function readManagedAsset(url: string, signal: AbortSignal, fetcher: typeof fetch = fetch, thumbnail = false) {
  if (!/^\/api\/v1\/(?:management\/domestic-studio|domestic-studio\/tasks\/[a-zA-Z0-9-]+\/view\/[a-zA-Z0-9-]+)\/sessions\/[a-zA-Z0-9-]+\/(?:files|pictures|outputs)\/[a-zA-Z0-9-]+\/content$/.test(url)) throw Error('文件地址无效')
  const response = await fetcher(thumbnail ? `${url}?thumbnail=true` : url, { credentials: 'include', cache: 'no-store', redirect: 'error', signal: AbortSignal.any([signal, AbortSignal.timeout(120000)]) })
  if (!response.ok) throw new IdentityError(response.status, response.status === 404 ? '文件不存在或已不可用' : response.status === 403 ? '查看权限已撤销' : '文件加载失败，请重试')
  return response.blob()
}
