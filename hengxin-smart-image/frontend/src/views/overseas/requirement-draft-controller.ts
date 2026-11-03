import { reactive } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { emptyTaskDraft, taskError, type TaskDraft } from '@/api/overseas/tasks'
import type { DraftFields, DraftsApi, RequirementDraft } from '@/api/overseas/requirement-drafts'
import { sameFields, sameSource, type DraftSnapshot, type DraftStorage } from './requirement-draft-storage'
const copy = <T>(value: T): T => value === undefined ? value : JSON.parse(JSON.stringify(value))
export function createDraftController(api: DraftsApi, storage: DraftStorage, failure: (reason: unknown) => void = () => {}) {
  const state = reactive({ fields: emptyTaskDraft() as DraftFields, server: undefined as RequirementDraft | undefined,
    loading: true, initialized: false, saving: false, dirty: false, conflict: false, error: '', localError: '',
    pendingUploads: [] as string[], submission: undefined as DraftSnapshot['submission'], recoveredTaskId: '' })
  let active = true, local: DraftSnapshot | undefined, queue: Promise<unknown> = Promise.resolve(), timer: ReturnType<typeof setTimeout> | undefined
  function persisted() {
    if (!state.server) return
    const snapshot: DraftSnapshot = { id: state.server.id, version: state.server.version, fields: copy(state.fields), source: copy(state.server.source), pendingUploads: [...state.pendingUploads], ...(state.submission ? { submission: copy(state.submission) } : {}) }
    local = snapshot
    try { storage.write(snapshot); state.localError = '' } catch { state.localError = '浏览器无法保存恢复副本；请等待服务器显示已保存后再离开。' }
  }
  function failed(reason: unknown) {
    state.error = reason instanceof IdentityError && reason.status === 409 ? '草稿已在其他页面更新，本地输入已保留。请选择恢复方式。' : taskError(reason)
    if (reason instanceof IdentityError && reason.status === 409) state.conflict = true
    if (reason instanceof IdentityError && [401, 403].includes(reason.status)) failure(reason)
  }
  function enqueue<T>(fn: () => Promise<T>): Promise<T> {
    const result = queue.then(() => { if (!active) throw Error('页面已关闭'); return fn() })
    queue = result.catch(() => {}); return result
  }
  function merge(value: RequirementDraft) { state.server = copy(value) }
  async function initialize() {
    state.loading = true; state.error = ''
    try { local = storage.read() } catch { state.localError = '本地恢复副本无法读取；服务器草稿仍会恢复。' }
    try {
      const value = await api.get(); if (!active) return
      merge(value); state.fields = copy(value.fields)
      if (local) {
        state.pendingUploads = [...local.pendingUploads]
        if (local.submission && value.lastSubmittedTaskId && value.lastSubmittedKey === local.submission.key) { state.recoveredTaskId = value.lastSubmittedTaskId; storage.clear() }
        else if (local.id === value.id && (local.version === value.version || sameFields(local.fields, value.fields)) && sameSource(local.source, value.source)) {
          state.fields = copy(local.fields); state.submission = copy(local.submission); state.dirty = !sameFields(local.fields, value.fields)
        } else { state.fields = copy(local.fields); state.conflict = true; state.error = '服务器草稿与本地恢复副本不同，请选择保留哪一份。' }
      }
      if (state.recoveredTaskId) return
      state.initialized = true
      if (!state.conflict) { persisted(); if (state.dirty) schedule() }
    } catch (reason) { if (active) failed(reason) }
    finally { if (active) state.loading = false }
  }
  function edit(fields: DraftFields) {
    if (!state.initialized || state.conflict || state.submission) return
    state.fields = copy(fields); state.dirty = true; persisted(); schedule()
  }
  function schedule() { clearTimeout(timer); timer = setTimeout(() => { void flush().catch(() => {}) }, 500) }
  async function saveNow() {
    if (!state.initialized || !state.server || state.conflict) throw Error('请先恢复草稿并处理版本冲突')
    state.error = ''
    while (state.dirty && active) {
      const fields = copy(state.fields), version = state.server.version
      state.saving = true; state.error = ''
      try {
        const result = await api.save(version, fields); if (!active) return
        merge(result); state.dirty = !sameFields(fields, state.fields); persisted()
      } catch (reason) { if (active) failed(reason); throw reason }
      finally { state.saving = false }
    }
  }
  function flush() { clearTimeout(timer); return enqueue(saveNow) }
  function refresh() {
    return enqueue(async () => {
      if (!state.server || state.loading || state.conflict || state.submission) return
      const previous = state.server, value = await api.get(); if (!active) return
      if (value.id !== previous.id || !sameSource(value.source, previous.source) || (value.version !== previous.version && !sameFields(value.fields, previous.fields))) {
        state.conflict = true; state.error = '草稿已在其他页面更新，本地输入已保留。请选择恢复方式。'; return
      }
      merge(value); if (!state.dirty) state.error = ''; persisted()
    }).catch(reason => { if (active) failed(reason) })
  }
  function mutate(operation: (server: RequirementDraft) => Promise<RequirementDraft>, replaceFields = false) {
    clearTimeout(timer)
    return enqueue(async () => {
      await saveNow(); if (!state.server) throw Error('草稿尚未恢复')
      state.saving = true
      try { const result = await operation(copy(state.server)); if (!active) return; merge(result); if (replaceFields) state.fields = copy(result.fields); persisted(); return result }
      catch (reason) { if (active) failed(reason); throw reason }
      finally { state.saving = false }
    })
  }
  function resolve(useLocal: boolean) {
    return enqueue(async () => {
      state.loading = true
      try {
        const latest = await api.get(); if (!active) return
        const fields = copy(state.fields), previousSource = local ? local.source : state.server?.source
        if (useLocal && !sameSource(previousSource ?? null, latest.source)) throw Error('来源已变化，不能把旧来源字段合并到新附件。请使用服务器草稿，或复制本地内容后重新获取需求。')
        merge(latest); state.conflict = false; state.submission = undefined; state.error = ''
        state.fields = useLocal ? fields : copy(latest.fields); state.dirty = useLocal && !sameFields(fields, latest.fields)
        if (!useLocal) state.pendingUploads = []
        persisted(); if (state.dirty) await saveNow()
      } catch (reason) { if (active) failed(reason); throw reason }
      finally { state.loading = false }
    })
  }
  function uploads(names: string[]) { state.pendingUploads = [...names]; persisted() }
  function submission(body: TaskDraft, key: string) { state.submission = { body: copy(body), key }; persisted() }
  function clearSubmission() { state.submission = undefined; persisted() }
  function completed() { state.initialized = false; clearTimeout(timer); state.dirty = false; state.submission = undefined; try { storage.clear() } catch { state.localError = '任务已提交，本地恢复副本清理失败。' } }
  function dispose() { if (state.initialized && !state.conflict) persisted(); active = false; clearTimeout(timer) }
  return { state, initialize, edit, flush, refresh, mutate, resolve, uploads, submission, clearSubmission, completed, dispose }
}
