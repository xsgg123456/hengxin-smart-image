import { onScopeDispose, reactive, ref, shallowRef, watch } from 'vue'
import { createDomesticTasksApi, type DomesticTask, type TaskList, type ManagedTaskDetail } from '@/api/hengxin/domestic-tasks'
import { IdentityError } from '@/api/identity/request'
import { identity } from '@/api/hengxin/identity'
import { randomUUID } from '@/utils/browser-crypto'

type Operation = { key: string; kind: 'create'; name: string; workspace: string }
  | { key: string; kind: 'update'; id: string; version: number; name?: string; completed?: boolean }
  | { key: string; kind: 'delete'; id: string; version: number }
interface Context { actor: string; workspace: string; management: boolean; id: string }
export function useTasks(context: () => Context, entered: (task: DomesticTask) => void, removed: () => void, api = createDomesticTasksApi()) {
  const filters = reactive({ workspace: '', ownerId: '', search: '', status: '', page: 1, pageSize: 20 })
  const list = shallowRef<TaskList>(), task = shallowRef<DomesticTask>(), managed = shallowRef<ManagedTaskDetail>()
  const loading = ref(false), busy = ref(false), error = ref(''), denied = ref(false), notice = ref('')
  const pending = shallowRef<Operation>(), autoSync = ref(true), lastSuccess = ref('')
  let epoch = 0, controller: AbortController | undefined, alive = true, requesting = false
  const scope = () => JSON.stringify([context().actor, context().workspace, context().management])
  const storageKey = () => `hx-domestic-task-operation:${scope()}`
  function save(value?: Operation) {
    pending.value = value
    try { if (value) sessionStorage.setItem(storageKey(), JSON.stringify(value)); else sessionStorage.removeItem(storageKey()) }
    catch { notice.value = '浏览器无法保存待核实操作，请保持当前页面打开。' }
  }
  function clear() { list.value = undefined; task.value = undefined; managed.value = undefined; lastSuccess.value = '' }
  function failure(reason: unknown) {
    if (reason instanceof IdentityError && [401, 403].includes(reason.status)) {
      ++epoch; controller?.abort(); denied.value = true; autoSync.value = false; loading.value = false; clear()
      error.value = '查看权限已失效，已清除任务内容，请重新登录后核实权限。'
    } else error.value = reason instanceof IdentityError && typeof reason.detail === 'string' ? reason.detail : reason instanceof Error ? reason.message : '任务请求失败，请重试'
  }
  async function refreshData(background = false) {
    if (!alive || denied.value || !context().actor) return
    const token = ++epoch, current = { ...context() }
    controller?.abort(); controller = new AbortController(); const signal = controller.signal
    requesting = true
    loading.value = !background || !(current.id ? task.value : list.value)
    try {
      if (current.id) {
        if (current.management) {
          const value = await api.managedDetail(current.id, signal)
          if (token !== epoch) return
          managed.value = value; task.value = value.task
        } else {
          if (task.value?.deletionStatus) {
            const receipt = await api.deletion(current.id, signal)
            if (token !== epoch) return
            if (receipt.status === 'deleted') { clear(); removed(); return }
          }
          const value = await api.detail(current.id, signal)
          if (token !== epoch) return
          if (value.workspace !== current.workspace) throw Error('任务不属于当前业务，请从原业务菜单进入。')
          task.value = value
        }
      } else {
        const value = await api.list({ ...filters, workspace: current.management ? filters.workspace : current.workspace }, current.management, signal)
        if (token !== epoch) return
        list.value = value
        if (filters.page > 1 && !value.items.length && value.total) { filters.page = Math.ceil(value.total / filters.pageSize); return }
      }
      error.value = ''; lastSuccess.value = new Date().toISOString()
    } catch (reason) {
      if (token !== epoch || signal.aborted) return
      if (reason instanceof IdentityError && [404, 410].includes(reason.status) && current.id) { task.value = undefined; managed.value = undefined }
      failure(reason)
    } finally { if (token === epoch) { requesting = false; loading.value = false } }
  }
  const refresh = () => refreshData()
  async function run(operation: Operation) {
    if (busy.value || context().management || denied.value) return false
    const owner = scope(), originalId = context().id
    busy.value = true; error.value = ''; save(operation)
    try {
      if (operation.kind === 'delete') {
        const receipt = await api.remove(operation.id, operation.version, operation.key)
        if (!alive || owner !== scope()) return false
        save()
        if (receipt.status === 'deleted' && originalId === operation.id && context().id === originalId) removed()
        else if (receipt.status === 'delete_failed') error.value = receipt.error || '任务删除失败，可重试删除。'
      } else {
        const value = operation.kind === 'create'
          ? await api.create({ name: operation.name, workspace: operation.workspace }, operation.key)
          : await api.update(operation.id, { version: operation.version, ...(operation.name === undefined ? {} : { name: operation.name }), ...(operation.completed === undefined ? {} : { completed: operation.completed }) }, operation.key)
        if (!alive || owner !== scope()) return false
        save()
        if (operation.kind === 'create' && context().id === originalId) entered(value)
        else if (context().id === value.id) task.value = value
      }
      void refresh(); return true
    } catch (reason) {
      if (!alive || owner !== scope()) return false
      if (reason instanceof IdentityError && reason.status >= 400 && reason.status < 500 && reason.status !== 408) save()
      failure(reason); return false
    } finally {
      if (alive && owner === scope()) busy.value = false
    }
  }
  function reset() { Object.assign(filters, { workspace: '', ownerId: '', search: '', status: '', page: 1 }) }
  let previousScope = scope()
  watch(() => [context().actor, context().workspace, context().management, context().id], () => {
    ++epoch; controller?.abort(); clear(); error.value = ''; pending.value = undefined
    if (previousScope !== scope()) busy.value = false
    previousScope = scope()
    try { const raw = sessionStorage.getItem(storageKey()); if (raw) pending.value = JSON.parse(raw) as Operation } catch { notice.value = '待核实操作暂时无法恢复，请检查浏览器存储。' }
    void refresh()
  }, { immediate: true })
  watch(() => [filters.workspace, filters.ownerId, filters.search, filters.status], () => { filters.page = 1; list.value = undefined; void refresh() })
  watch(() => filters.page, () => { void refresh() })
  watch(autoSync, value => { if (value) void refresh() })
  const timer = setInterval(() => { if (autoSync.value && !requesting && !busy.value && (typeof document === 'undefined' || document.visibilityState === 'visible')) void refreshData(true) }, 3000)
  const unsubscribe = identity.subscribe(reason => {
    // 暂时隐藏由全局身份锁保护，返回重验成功后继续使用当前任务。
    if (reason !== 'suspended') failure(new IdentityError(403, '身份已变化'))
  })
  onScopeDispose(() => { alive = false; ++epoch; controller?.abort(); clearInterval(timer); unsubscribe(); clear() })
  return { filters, list, task, managed, loading, busy, error, notice, denied, pending, autoSync, lastSuccess, refresh, reset, failure,
    create: (name: string) => pending.value ? Promise.resolve(false) : run({ kind: 'create', name, workspace: context().workspace, key: randomUUID() }),
    update: (value: DomesticTask, changes: { name?: string; completed?: boolean }) => pending.value ? Promise.resolve(false) : run({ kind: 'update', id: value.id, version: value.version, ...changes, key: randomUUID() }),
    remove: (value: DomesticTask) => pending.value ? Promise.resolve(false) : run({ kind: 'delete', id: value.id, version: value.version, key: randomUUID() }),
    retry: () => pending.value && run(pending.value) }
}
