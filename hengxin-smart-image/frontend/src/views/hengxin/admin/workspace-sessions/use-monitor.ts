import { onScopeDispose, reactive, ref, shallowRef } from 'vue'
import { IdentityError } from '../../../../api/identity/request'
import { createWorkspaceSessionsApi, type SessionDetail, type SessionFilters, type SessionList } from '../../../../api/hengxin/workspace-sessions'
import type { StudioTranscript } from '../../../../api/shared/studio'
import { identity } from '../../../../api/hengxin/identity'

export function useMonitor(api = createWorkspaceSessionsApi()) {
  const filters = reactive<SessionFilters>({ ownerId: '', workspace: '', status: '', search: '', page: 1, pageSize: 10 })
  const list = shallowRef<SessionList>(), detail = shallowRef<SessionDetail>()
  const transcript = shallowRef<StudioTranscript[]>([])
  const selectedId = ref(''), autoSync = ref(true), loading = ref(false), denied = ref(false)
  const error = ref(''), lastSuccess = ref('')
  let epoch = 0, controller: AbortController | undefined, cursor = 0
  function clear() { list.value = undefined; detail.value = undefined; transcript.value = []; cursor = 0; lastSuccess.value = '' }
  function failure(reason: unknown) {
    if (reason instanceof IdentityError && [401, 403].includes(reason.status)) {
      ++epoch; controller?.abort(); denied.value = true; autoSync.value = false; clear(); loading.value = false
      error.value = '查看权限已失效，已清除会话内容，请重新登录后核实权限。'
    } else error.value = reason instanceof Error ? reason.message : '同步失败，请重试'
  }
  async function refresh() {
    if (denied.value) return
    const token = ++epoch, id = selectedId.value
    controller?.abort(); controller = new AbortController()
    const signal = controller.signal
    loading.value = true
    try {
      if (id) {
        const next = await api.detail(id, signal)
        let after = cursor
        const entries = new Map(transcript.value.map(item => [`${item.turnId}:${item.itemId}`, item]))
        while (true) {
          const page = await api.transcript(id, after, signal)
          if (token !== epoch) return
          for (const item of page.items) entries.set(`${item.turnId}:${item.itemId}`, item)
          if (page.hasMore && page.cursor <= after) throw Error('会话过程同步未推进，请重试')
          after = page.cursor
          if (!page.hasMore) break
        }
        if (token !== epoch) return
        detail.value = next; cursor = after
        transcript.value = [...entries.values()].sort((a, b) => a.id - b.id)
      } else {
        const next = await api.list({ ...filters }, signal)
        if (token !== epoch) return
        list.value = next
      }
      error.value = ''; lastSuccess.value = new Date().toISOString()
    } catch (reason) {
      if (token !== epoch || signal.aborted) return
      if (reason instanceof IdentityError && reason.status === 404 && id) {
        detail.value = undefined; transcript.value = []; cursor = 0; lastSuccess.value = ''
        error.value = '会话已删除或不可用，请返回列表。'
      } else failure(reason)
    } finally { if (token === epoch) loading.value = false }
  }
  function select(id: string) {
    ++epoch; controller?.abort(); selectedId.value = id
    detail.value = undefined; transcript.value = []; cursor = 0; error.value = ''; lastSuccess.value = ''
    void refresh()
  }
  function filterChanged() {
    ++epoch; controller?.abort(); filters.page = 1; list.value = undefined; lastSuccess.value = ''
    void refresh()
  }
  function reset() { Object.assign(filters, { ownerId: '', workspace: '', status: '', search: '', page: 1 }); filterChanged() }
  const timer = setInterval(() => {
    if (autoSync.value && !loading.value && (typeof document === 'undefined' || document.visibilityState === 'visible')) void refresh()
  }, 3000)
  const unsubscribe = identity.subscribe(() => failure(new IdentityError(403, '身份已变化')))
  onScopeDispose(() => { ++epoch; controller?.abort(); clearInterval(timer); unsubscribe(); clear() })
  return { filters, list, detail, transcript, selectedId, autoSync, loading, denied, error, lastSuccess, refresh, select, filterChanged, reset, failure }
}
