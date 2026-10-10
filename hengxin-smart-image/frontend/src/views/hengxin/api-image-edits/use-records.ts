import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useUserStore } from '@/store/modules/user'
import { apiImages, errorText, uncertainResponse } from '@/api/api-image-edits'
import { bootstrap, retryBootstrap } from '@/api/hengxin/bootstrap'
import { identity } from '@/api/hengxin/identity'
import { isTaskActive } from '@/types/api-image-edits'
import type { ApiTask, ApiTaskSummary, ApiTaskState } from '@/types/api-image-edits'
// 未确认的重试请求跨详情关闭和路由切换保留原键。
const retryKeys = new Map<string, { key: string; uncertain: boolean }>()
function savedRetry(id: string) {
  if (!retryKeys.has(id)) {
    try { const key = sessionStorage.getItem('api-image-retry:' + id); if (key) retryKeys.set(id, { key, uncertain: true }) } catch { /* 内存状态仍可使用 */ }
  }
  return retryKeys.get(id)
}
function saveRetry(id: string, value?: { key: string; uncertain: boolean }) {
  if (value) retryKeys.set(id, value); else retryKeys.delete(id)
  try { if (value) sessionStorage.setItem('api-image-retry:' + id, value.key); else sessionStorage.removeItem('api-image-retry:' + id) } catch { /* 内存状态仍保留原键 */ }
}
export function useRecords() {
  const userId = String(useUserStore().getUserInfo.userId)
  const retryId = (id: string) => `${userId}:${id}`
  const tasks = ref<ApiTaskSummary[]>([]), total = ref(0), page = ref(1), pageSize = ref(20), search = ref(''), filter = ref<ApiTaskState | ''>('')
  const selectedId = ref(''), selected = ref<ApiTask>(), loading = ref(false), detailLoading = ref(false)
  const error = ref(''), detailError = ref(''), actionError = ref(''), busy = ref(false)
  const retryPending = computed(() => { void actionError.value; void selected.value; return !!savedRetry(retryId(selectedId.value)) })
  let detailLoadedAt = 0
  let alive = true, listSerial = 0, detailSerial = 0, timer: ReturnType<typeof setTimeout> | undefined, debounce: ReturnType<typeof setTimeout> | undefined
  async function load(silent = false) {
    const serial = ++listSerial; if (!silent) loading.value = true
    try {
      const result = await apiImages.list({ page: page.value, pageSize: pageSize.value, search: search.value, status: filter.value })
      if (!alive || serial !== listSerial) return
      if (page.value > 1 && !result.items.length && result.total <= (page.value - 1) * pageSize.value) { page.value = Math.max(1, Math.ceil(result.total / pageSize.value)); return }
      tasks.value = result.items; total.value = result.total; error.value = ''
    } catch (e) { if (alive && serial === listSerial) error.value = errorText(e) }
    finally { if (alive && serial === listSerial) loading.value = false }
  }
  async function loadDetail(silent = false) {
    const id = selectedId.value, serial = ++detailSerial
    if (!id) { selected.value = undefined; detailError.value = ''; detailLoading.value = false; return }
    if (!silent) detailLoading.value = true
    try { const task = await apiImages.task(id); if (alive && serial === detailSerial) { selected.value = task; detailLoadedAt = Date.now(); detailError.value = '' } }
    catch (e) { if (alive && serial === detailSerial) { detailError.value = errorText(e) } }
    finally { if (alive && serial === detailSerial) detailLoading.value = false }
  }
  async function refresh(silent = false) { await Promise.all([load(silent), loadDetail(silent)]) }
  const isHidden = () => document.visibilityState === 'hidden'
  function schedule() { clearTimeout(timer); if (alive && !isHidden() && bootstrap.ready && !bootstrap.locked) timer = setTimeout(poll, 10000) }
  async function poll() {
    if (!alive || isHidden() || !bootstrap.ready || bootstrap.locked) return
    await load(true)
    if (!alive || isHidden() || !bootstrap.ready || bootstrap.locked) return
    const listed = tasks.value.find(task => task.id === selectedId.value)
    if (selectedId.value && (!selected.value || detailError.value || Date.now() - detailLoadedAt >= 30000 || isTaskActive(selected.value) || (listed && isTaskActive(listed)))) await loadDetail(true)
    schedule()
  }
  async function visibility() {
    clearTimeout(timer)
    if (isHidden()) { ++listSerial; ++detailSerial; return }
    const epoch = identity.epoch
    await retryBootstrap.run()
    if (!alive || !identity.current(epoch) || isHidden() || !bootstrap.ready || bootstrap.locked) return
    await refresh(true); schedule()
  }
  document.addEventListener('visibilitychange', visibility)
  watch([filter, pageSize], () => { page.value = 1 }, { flush: 'sync' })
  watch([page, filter, pageSize], () => { clearTimeout(debounce); void load() })
  watch(search, () => { ++listSerial; clearTimeout(debounce); debounce = setTimeout(() => { if (page.value !== 1) page.value = 1; else void load() }, 300) })
  watch(selectedId, () => { selected.value = undefined; actionError.value = ''; void loadDetail() })
  async function action(run: () => Promise<unknown>) {
    if (busy.value) return
    busy.value = true; actionError.value = ''
    try { await run(); await refresh() } catch (e) { actionError.value = errorText(e) }
    finally { busy.value = false }
  }
  async function retry(id: string) {
    await action(async () => {
      const entry = savedRetry(retryId(id)) || { key: crypto.randomUUID(), uncertain: false }; saveRetry(retryId(id), entry)
      try { await apiImages.retry(id, entry.key); saveRetry(retryId(id)) }
      catch (e) { if (uncertainResponse(e)) entry.uncertain = true; else if (!entry.uncertain) saveRetry(retryId(id)); throw new Error(`${errorText(e)}${retryKeys.has(retryId(id)) ? '。结果尚未确认，请再次确认原重试请求。' : ''}`) }
    })
  }
  void refresh().then(schedule)
  onBeforeUnmount(() => { alive = false; document.removeEventListener('visibilitychange', visibility); clearTimeout(timer); clearTimeout(debounce) })
  return { tasks, total, page, pageSize, search, filter, selectedId, selected, loading, detailLoading, error, detailError, actionError, busy, retryPending, load, loadDetail, refresh, action, retry }
}
