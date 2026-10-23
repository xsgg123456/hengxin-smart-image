import { computed, effectScope, onScopeDispose, ref, shallowRef, watch, type Ref, type EffectScope } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { createStudioApi, type Studio, type StudioApi, type StudioConversation } from '@/api/overseas/studio'
import type { TaskDetail } from '@/api/overseas/tasks'
import { composerDraftKey } from './studio-composer-draft'
import { useStudio } from './use-studio'
import { legacyPending } from './studio-pending'
import { sessionOrderedApi } from './studio-session-api'
import { completionStamp, forwardController, sessionPreferenceKey, type StudioController, type SessionView } from './studio-session-state'

type Management = { key: string; kind: 'create' } | { key: string; kind: 'rename' | 'delete'; id: string; version: number; name?: string }
export function useStudioSessions(task: () => TaskDetail, failure: (reason: unknown) => void, changed: () => void, api: StudioApi = createStudioApi(), actor = '') {
  const ordered = sessionOrderedApi(api)
  api = ordered
  const key = sessionPreferenceKey(actor, task().id), preferenceNotice = ref('')
  const legacy = legacyPending(actor, task().id, preferenceNotice)
  const summaries = ref<StudioConversation[]>([]), seen = ref<Record<string, string>>({}), scrolls = ref<Record<string, number>>({})
  const activeId = ref(''), sessionBusy = ref(false), sessionError = ref(''), sessionPending = ref<Management>()
  const engines = new Map<string, { controller: StudioController; scope: EffectScope }>()
  let applyingShared = false
  let alive = true, latestVersion = 0, taskState: Pick<Studio, 'completed' | 'reopened' | 'archiveId'> | undefined
  try {
    const value = JSON.parse(localStorage.getItem(key) || '{}')
    if (typeof value.activeId === 'string') activeId.value = value.activeId
    if (value.scrolls && typeof value.scrolls === 'object') for (const [id, n] of Object.entries(value.scrolls)) if (typeof n === 'number' && Number.isFinite(n) && n >= 0) scrolls.value[id] = n
    if (value.seen && typeof value.seen === 'object') for (const [id, n] of Object.entries(value.seen)) if (typeof n === 'string') seen.value[id] = n
    const pending = JSON.parse(sessionStorage.getItem(`${key}:pending`) || 'null')
    if (pending && typeof pending.key === 'string' && ['create', 'rename', 'delete'].includes(pending.kind)) sessionPending.value = pending
  } catch { preferenceNotice.value = '浏览器无法恢复会话选择；当前页面仍可使用。' }
  function persist() {
    if (!actor) return
    try { localStorage.setItem(key, JSON.stringify({ activeId: activeId.value, scrolls: scrolls.value, seen: seen.value })) }
    catch { preferenceNotice.value = '浏览器无法保存会话选择和滚动位置，请保持页面打开。' }
  }
  function pending(value?: Management) {
    sessionPending.value = value
    try { if (value) sessionStorage.setItem(`${key}:pending`, JSON.stringify(value)); else sessionStorage.removeItem(`${key}:pending`) }
    catch { preferenceNotice.value = '浏览器无法保存操作状态，请在当前页面核实重试。' }
  }
  const current = shallowRef<StudioController>()
  function accept(value: Studio, owner?: StudioController) {
    value = ordered.currentSnapshot(value)
    if (!alive || value.taskVersion < latestVersion) return
    latestVersion = value.taskVersion
    taskState = { completed: value.completed, reopened: value.reopened, archiveId: value.archiveId }
    if (value.conversations) {
      const previous = new Map(summaries.value.map(s => [s.id, s]))
      summaries.value = value.conversations.map(s => {
        const old = previous.get(s.id)
        return old && old.updatedAt > s.updatedAt ? old : s
      })
      for (const s of summaries.value) {
        if (!(s.id in seen.value) || s.id === activeId.value) seen.value[s.id] = completionStamp(s)
      }
      // Removed controllers stop polling only after deletion has actually completed.
      for (const [id, entry] of engines) if (id && !summaries.value.some(s => s.id === id) && entry.controller !== owner) {
        if (entry.controller.pending.value) {
          preferenceNotice.value = '已删除会话仍有待核实请求；请求及原草稿已保留，请核实历史记录。'
        } else {
          entry.scope.stop(); engines.delete(id)
          try { localStorage.removeItem(composerDraftKey(actor, task().id, id)) } catch { /* storage notice is handled by the composer */ }
        }
      }
    }
    applyingShared = true
    for (const entry of engines.values()) {
      const old = entry.controller.data.value
      if (old && (old.taskVersion !== latestVersion || old.completed !== value.completed || old.reopened !== value.reopened || old.archiveId !== value.archiveId || old.conversations !== value.conversations || old.activeConversationCount !== value.activeConversationCount))
        entry.controller.data.value = { ...old, ...taskState, taskVersion: latestVersion, conversations: value.conversations, activeConversationCount: value.activeConversationCount }
    }
    applyingShared = false
    if (!activeId.value && value.conversationId) {
      activeId.value = value.conversationId
      const first = engines.get(''); if (first) { engines.delete(''); engines.set(activeId.value, first) }
    }
    if (value.conversations) {
      const recovered = legacy.recover(value.conversations)
      if (recovered) {
        const controller = engines.get(recovered.id)?.controller || make(recovered.id)
        controller.pending.value = recovered.value
      }
    }
    if (value.conversations?.length === 0 && activeId.value) { activeId.value = ''; current.value = engines.get('')?.controller || make('') }
    if (summaries.value.length && !summaries.value.some(s => s.id === activeId.value)) void selectSession(summaries.value[0].id)
    persist()
  }
  function make(id: string) {
    const scope = effectScope(true)
    const controller = scope.run(() => {
      const scopedApi: StudioApi = { ...api, get: async (taskId, signal, requested) => {
        try { return await api.get(taskId, signal, requested) }
        catch (reason) {
          if (reason instanceof IdentityError && [404, 410].includes(reason.status) && alive && !signal?.aborted) {
            const fallback = await api.get(taskId, signal)
            accept(fallback)
            if (fallback.conversationId && activeId.value === id) await selectSession(fallback.conversationId)
          }
          throw reason
        }
      } }
      const c = useStudio(task, failure, changed, scopedApi, actor, { id: id || undefined, normalize: ordered.currentSnapshot,
        available: () => !taskState?.completed && summaries.value.some(s => s.id === (id || c.data.value?.conversationId) && !s.deletionStatus) })
      watch(c.data, value => { if (value && !applyingShared) accept(value, c) }, { flush: 'sync' })
      return c
    })!
    engines.set(id, { controller, scope })
    return controller
  }
  current.value = make(activeId.value)
  async function selectSession(id: string) {
    if (!alive || (summaries.value.length && !summaries.value.some(s => s.id === id))) return
    activeId.value = id
    current.value = engines.get(id)?.controller || make(id)
    const row = summaries.value.find(s => s.id === id); if (row) seen.value[id] = completionStamp(row)
    persist()
    await current.value.refresh()
  }
  const forwarded = forwardController(current as Ref<StudioController>)
  const sessions = computed<SessionView[]>(() => summaries.value.map(s => ({ ...s, unread: s.turnCount > 0 && !s.activeTurnId && ['succeeded', 'failed', 'cancelled'].includes(s.status) && s.id !== activeId.value && seen.value[s.id] !== completionStamp(s),
    draft: !!(engines.get(s.id)?.controller.text.value || engines.get(s.id)?.controller.attachments.value.length || engines.get(s.id)?.controller.references.value.length || storedDraft(s.id)) })))
  function storedDraft(id: string) { try { return actor && localStorage.getItem(composerDraftKey(actor, task().id, id)) } catch { return false } }
  const currentSession = computed(() => sessions.value.find(s => s.id === activeId.value))
  const runningCount = computed(() => summaries.value.filter(s => !!s.activeTurnId).length)
  const canManage = computed(() => !!forwarded.data.value && !taskState?.completed && task().capabilities.includes('task.design') && !sessionBusy.value && !sessionPending.value)
  const canNewConversation = computed(() => canManage.value && summaries.value.length < 10)
  const canComplete = computed(() => canManage.value && !legacy.unresolved.value && !!forwarded.data.value?.archiveId && !runningCount.value && ![...engines.values()].some(e => e.controller.busy.value || e.controller.uploading.value || e.controller.pending.value))
  async function manage(action: Management) {
    if (sessionBusy.value || !task().capabilities.includes('task.design') || (taskState?.completed && sessionPending.value?.key !== action.key)) return false
    const requestedFrom = activeId.value
    sessionBusy.value = true; sessionError.value = ''; pending(action)
    try {
      const value = action.kind === 'create' ? await api.newConversation(task().id, action.key)
        : action.kind === 'rename' ? await api.renameConversation(task().id, action.id, action.name!, action.version, action.key)
          : await api.deleteConversation(task().id, action.id, action.version, action.key)
      if (!alive) return false
      pending(); accept(value)
      if (action.kind === 'create' && value.conversationId && activeId.value === requestedFrom) await selectSession(value.conversationId)
      else await current.value?.refresh()
      changed(); return true
    } catch (reason) {
      if (!alive) return false
      if (reason instanceof IdentityError && reason.status >= 400 && reason.status < 500 && reason.status !== 408) pending()
      sessionError.value = reason instanceof IdentityError && typeof reason.detail === 'string' ? reason.detail : reason instanceof Error ? reason.message : '会话操作失败，请重试'
      if (reason instanceof IdentityError && [401, 403].includes(reason.status)) failure(reason)
      void current.value?.refresh(); return false
    } finally { sessionBusy.value = false }
  }
  function newConversation() { if (canNewConversation.value) return manage({ kind: 'create', key: crypto.randomUUID() }) }
  function renameConversation(s: StudioConversation, name: string) {
    if (!canManage.value || s.deletionStatus) return
    if (!name.trim() || name.trim().length > 30) { sessionError.value = '请输入 1–30 个字'; return }
    return manage({ kind: 'rename', id: s.id, version: s.version, name: name.trim(), key: crypto.randomUUID() })
  }
  function deleteConversation(s: StudioConversation) {
    if (canManage.value && !s.activeTurnId && s.deletionStatus !== 'deleting' && !engines.get(s.id)?.controller.busy.value && !engines.get(s.id)?.controller.uploading.value && !engines.get(s.id)?.controller.pending.value)
      return manage({ kind: 'delete', id: s.id, version: s.version, key: crypto.randomUUID() })
  }
  function saveScroll(position: number, id = activeId.value) { if (id) { scrolls.value[id] = position; persist() } }
  onScopeDispose(() => { alive = false; for (const entry of engines.values()) entry.scope.stop() })
  return { ...forwarded, sessions, activeId, currentSession, runningCount, canManage, canComplete, canNewConversation, newConversation, renameConversation, deleteConversation, selectSession,
    sessionBusy, sessionError, sessionPending, retrySession: () => sessionPending.value && manage(sessionPending.value), preferenceNotice, saveScroll,
    scrollPosition: computed(() => scrolls.value[activeId.value] ?? null) }
}
