import { reactive } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { emptyTaskDraft, taskError, type TaskDraft } from '@/api/overseas/tasks'
import type { DraftFields, DraftsApi, RequirementDraft } from '@/api/overseas/requirement-drafts'
import { sameFields, sameSource, type DraftSnapshot, type DraftStorage } from './requirement-draft-storage'
const copy = <T>(value: T): T => value === undefined ? value : JSON.parse(JSON.stringify(value))
export function createDraftController(api: DraftsApi, storage: DraftStorage, failure: (reason: unknown) => void = () => {}) {
  const state = reactive({ fields: emptyTaskDraft() as DraftFields, server: undefined as RequirementDraft | undefined,
    loading: true, initialized: false, saving: false, dirty: false, conflict: false, error: '', localError: '',
    querying: false, queryError: '', queryFailures: 0, queryPaused: false,
    pendingUploads: [] as string[], submission: undefined as DraftSnapshot['submission'], recoveredTaskId: '' })
  let active = true, local: DraftSnapshot | undefined, queue: Promise<unknown> = Promise.resolve(), timer: ReturnType<typeof setTimeout> | undefined
  let poll: ReturnType<typeof setTimeout> | undefined, reading: Promise<void> | undefined, initializing: Promise<void> | undefined
  let visible = true, paused = false, refreshOnResume = false, generation = 0
  const readable = () => active && visible && state.initialized && !state.loading && !state.conflict && !state.submission && !state.queryPaused
  function planQuery() {
    clearTimeout(poll)
    if (readable() && !paused && !reading && !(state.dirty && state.error) && state.server?.imports.some(i => i.state === 'queued' || i.state === 'running')) {
      poll = setTimeout(() => { void refresh() }, 2000)
    }
  }
  function querySucceeded() { state.queryError = ''; state.queryFailures = 0; state.queryPaused = false }
  function queryFailed(reason: unknown) {
    state.queryFailures++; state.queryPaused = state.queryFailures >= 3
    state.queryError = `${state.queryPaused ? '草稿查询连续失败，自动更新已暂停。' : '草稿查询失败。'}${taskError(reason)}`
    if (reason instanceof IdentityError && [401, 403].includes(reason.status)) { state.queryPaused = true; failure(reason) }
  }
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
    const result = queue.then(() => { if (!active) throw Error('页面已关闭'); return fn() }).finally(planQuery)
    queue = result.catch(() => {}); return result
  }
  function merge(value: RequirementDraft) { state.server = copy(value) }
  function initialize() {
    if (initializing) return initializing
    if (!active || state.initialized) return Promise.resolve()
    initializing = enqueue(loadInitial).catch(() => {}).finally(() => { initializing = undefined; planQuery() })
    return initializing
  }
  async function loadInitial() {
    state.loading = true
    try { local = storage.read() } catch { state.localError = '本地恢复副本无法读取；服务器草稿仍会恢复。' }
    try {
      const value = await api.get(); if (!active) return
      querySucceeded(); merge(value); state.fields = copy(value.fields)
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
    } catch (reason) { if (active) queryFailed(reason) }
    finally { if (active) state.loading = false }
  }
  function edit(fields: DraftFields) {
    if (!state.initialized || state.conflict || state.submission) return
    state.fields = copy(fields); state.dirty = true; persisted(); schedule()
  }
  function schedule() { clearTimeout(timer); timer = setTimeout(() => { void flush().catch(() => {}) }, 500) }
  async function saveNow() {
    if (!state.initialized || !state.server || state.conflict) throw Error('请先恢复草稿并处理版本冲突')
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
    if (reading) return reading
    if (!readable()) return Promise.resolve()
    clearTimeout(poll)
    reading = enqueue(async () => {
      if (!readable() || !state.server) return
      // A queued read must never overtake unsaved input, including edits made while waiting.
      if (state.dirty) { try { await saveNow() } catch { return } }
      if (!readable()) return
      const previous = state.server, current = generation
      state.querying = true
      try {
        const value = await api.get(); if (!active || current !== generation) return
        querySucceeded()
        if (value.id !== previous.id || !sameSource(value.source, previous.source) || (value.version !== previous.version && !sameFields(value.fields, previous.fields))) {
          state.conflict = true; state.error = '草稿已在其他页面更新，本地输入已保留。请选择恢复方式。'; return
        }
        merge(value); persisted()
      } catch (reason) { if (active && current === generation) queryFailed(reason) }
      finally { if (active) state.querying = false }
    }).catch(() => {}).finally(() => { reading = undefined; planQuery() })
    return reading
  }
  function retryQuery() {
    if (!active) return Promise.resolve()
    state.queryPaused = false; state.queryFailures = 0
    return state.initialized ? refresh() : initialize()
  }
  async function refreshAfterUpload() {
    // An upload may commit after the in-flight GET took its database snapshot.
    if (reading) await reading
    return refresh()
  }
  function setVisible(value: boolean) {
    if (visible === value) return
    visible = value; clearTimeout(poll)
    if (visible) {
      if (paused) { refreshOnResume = true; return }
      if (state.initialized) void refresh()
      else if (!state.queryPaused && !state.loading) void initialize()
    }
  }
  function setPaused(value: boolean) {
    paused = value
    if (!paused && visible && refreshOnResume) { refreshOnResume = false; void refresh() }
    else planQuery()
  }
  function mutate(operation: (server: RequirementDraft) => Promise<RequirementDraft>, replaceFields = false) {
    clearTimeout(timer)
    return enqueue(async () => {
      await saveNow(); if (!state.server) throw Error('草稿尚未恢复')
      state.saving = true
      try { const result = await operation(copy(state.server)); if (!active) return; state.error = ''; querySucceeded(); merge(result); if (replaceFields) state.fields = copy(result.fields); persisted(); return result }
      catch (reason) { if (active) failed(reason); throw reason }
      finally { state.saving = false }
    })
  }
  function resolve(useLocal: boolean) {
    return enqueue(async () => {
      state.loading = true
      let readingLatest = true
      try {
        const latest = await api.get(); if (!active) return
        readingLatest = false; querySucceeded()
        const fields = copy(state.fields), previousSource = local ? local.source : state.server?.source
        if (useLocal && !sameSource(previousSource ?? null, latest.source)) throw Error('来源已变化，不能把旧来源字段合并到新附件。请使用服务器草稿，或复制本地内容后重新获取需求。')
        merge(latest); state.conflict = false; state.submission = undefined; state.error = ''
        state.fields = useLocal ? fields : copy(latest.fields); state.dirty = useLocal && !sameFields(fields, latest.fields)
        if (!useLocal) state.pendingUploads = []
        persisted(); if (state.dirty) await saveNow()
      } catch (reason) { if (active) { if (readingLatest) queryFailed(reason); else failed(reason) }; throw reason }
      finally { state.loading = false }
    })
  }
  function uploads(names: string[]) { state.pendingUploads = [...names]; persisted() }
  function submission(body: TaskDraft, key: string) { generation++; state.submission = { body: copy(body), key }; clearTimeout(poll); persisted() }
  function clearSubmission() { state.submission = undefined; persisted(); planQuery() }
  function completed() { generation++; state.initialized = false; clearTimeout(timer); clearTimeout(poll); state.dirty = false; state.submission = undefined; try { storage.clear() } catch { state.localError = '任务已提交，本地恢复副本清理失败。' } }
  function dispose() { if (state.initialized && !state.conflict) persisted(); active = false; generation++; clearTimeout(timer); clearTimeout(poll) }
  return { state, initialize, edit, flush, refresh, refreshAfterUpload, retryQuery, setVisible, setPaused, mutate, resolve, uploads, submission, clearSubmission, completed, dispose }
}
