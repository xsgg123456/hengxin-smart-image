import { createIdentityRequest, record } from '../identity/request'
import { isManagedSession, type ManagedSession } from './workspace-sessions'
import { isWorkspaceKey, type WorkspaceKey } from '../shared/domestic-workspace-keys'

export interface DomesticTask {
  id: string; name: string; workspace: WorkspaceKey; ownerId: string; ownerName: string
  version: number; completed: boolean; conversationCount: number; activeConversationCount: number
  createdAt: string; updatedAt: string; deletionStatus: null | 'deleting' | 'delete_failed'; deletionError: string | null
}
export interface TaskFilters { workspace: string; ownerId: string; search: string; status: string; page: number; pageSize: number }
export interface TaskList {
  items: DomesticTask[]; total: number; page: number; pageSize: number
  counters: { total: number; active: number; completed: number }; members?: { id: string; name: string }[]
}
export interface ManagedTaskDetail { task: DomesticTask; sessions: ManagedSession[] }
export interface TaskDeletion { status: 'deleting' | 'delete_failed' | 'deleted'; error?: string | null }
const root = '/api/v1/domestic-studio/tasks', managementRoot = '/api/v1/management/domestic-studio/tasks'
const integer = (value: unknown) => Number.isSafeInteger(value) && Number(value) >= 0
export function isDomesticTask(value: unknown): value is DomesticTask {
  return record(value) && ['id', 'name', 'ownerId', 'ownerName', 'createdAt', 'updatedAt'].every(key => typeof value[key] === 'string')
    && isWorkspaceKey(value.workspace)
    && integer(value.version) && Number(value.version) > 0 && typeof value.completed === 'boolean'
    && integer(value.conversationCount) && integer(value.activeConversationCount)
    && (value.deletionStatus === null || ['deleting', 'delete_failed'].includes(String(value.deletionStatus)))
    && (value.deletionError === null || typeof value.deletionError === 'string')
}
export function isTaskList(value: unknown): value is TaskList {
  if (!record(value) || !record(value.counters)) return false
  const counters = value.counters
  return Array.isArray(value.items) && value.items.every(isDomesticTask)
    && ['total', 'page', 'pageSize'].every(key => integer(value[key]))
    && ['total', 'active', 'completed'].every(key => integer(counters[key]))
    && (value.members === undefined || Array.isArray(value.members) && value.members.every(member => record(member) && typeof member.id === 'string' && typeof member.name === 'string'))
}
export function isManagedTaskDetail(value: unknown, id: string): value is ManagedTaskDetail {
  if (!record(value) || !isDomesticTask(value.task) || value.task.id !== id) return false
  const task = value.task
  return Array.isArray(value.sessions) && value.sessions.every(session => isManagedSession(session) && session.ownerId === task.ownerId && session.workspace === task.workspace && session.taskId === id)
}
export function createDomesticTasksApi(fetcher: typeof fetch = fetch) {
  const request = (signal?: AbortSignal) => createIdentityRequest((url, options) => fetcher(url, {
    ...options, cache: 'no-store', signal: signal && options?.signal ? AbortSignal.any([signal, options.signal]) : signal || options?.signal
  }))
  const taskPath = (id: string) => `${root}/${encodeURIComponent(id)}`
  const deletion = (value: unknown): value is TaskDeletion => record(value) && ['deleting', 'delete_failed', 'deleted'].includes(String(value.status)) && (value.error == null || typeof value.error === 'string')
  return {
    list: (filters: TaskFilters, management = false, signal?: AbortSignal) => request(signal)(management ? managementRoot : root, isTaskList, undefined, { params: { ...filters } }),
    detail: (id: string, signal?: AbortSignal) => request(signal)(taskPath(id), (value): value is DomesticTask => isDomesticTask(value) && value.id === id),
    managedDetail: (id: string, signal?: AbortSignal) => request(signal)(`${managementRoot}/${encodeURIComponent(id)}`, (value): value is ManagedTaskDetail => isManagedTaskDetail(value, id)),
    create: (body: { name: string; workspace: string }, key: string) => request()(root, isDomesticTask, body, { idempotencyKey: key }),
    update: (id: string, body: { version: number; name?: string; completed?: boolean }, key: string) => request()(taskPath(id), isDomesticTask, body, { method: 'PATCH', idempotencyKey: key }),
    remove: (id: string, version: number, key: string) => request()(taskPath(id), deletion, { version }, { method: 'DELETE', idempotencyKey: key }),
    deletion: (id: string, signal?: AbortSignal) => request(signal)(`${taskPath(id)}/deletion`, deletion)
  }
}
