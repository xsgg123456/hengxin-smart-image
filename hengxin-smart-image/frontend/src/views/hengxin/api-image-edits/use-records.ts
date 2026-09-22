import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useUserStore } from '@/store/modules/user'
import { apiImages, errorText, uncertainResponse } from '@/api/api-image-edits'
import type { ApiTask, ApiTaskState } from '@/types/api-image-edits'
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
  const tasks = ref<ApiTask[]>([]), total = ref(0), page = ref(1), search = ref(''), filter = ref<ApiTaskState | ''>('')
  const selectedId = ref(''), selected = ref<ApiTask>(), loading = ref(false), detailLoading = ref(false)
  const error = ref(''), detailError = ref(''), actionError = ref(''), busy = ref(false)
  const retryPending = computed(() => { void actionError.value; void selected.value; return !!savedRetry(retryId(selectedId.value)) })
  let alive = true, listSerial = 0, detailSerial = 0, timer: ReturnType<typeof setTimeout> | undefined, debounce: ReturnType<typeof setTimeout> | undefined
  async function load() {
    const serial = ++listSerial; loading.value = true
    try {
      const result = await apiImages.list({ page: page.value, pageSize: 20, search: search.value, status: filter.value })
      if (!alive || serial !== listSerial) return
      if (page.value > 1 && !result.items.length && result.total <= (page.value - 1) * 20) { page.value = Math.max(1, Math.ceil(result.total / 20)); return }
      tasks.value = result.items; total.value = result.total; error.value = ''
    } catch (e) { if (alive && serial === listSerial) error.value = errorText(e) }
    finally { if (alive && serial === listSerial) loading.value = false }
  }
  async function loadDetail() {
    const id = selectedId.value, serial = ++detailSerial
    if (!id) { selected.value = undefined; detailError.value = ''; detailLoading.value = false; return }
    detailLoading.value = true
    try { const task = await apiImages.task(id); if (alive && serial === detailSerial) { selected.value = task; detailError.value = '' } }
    catch (e) { if (alive && serial === detailSerial) { detailError.value = errorText(e); selected.value = undefined } }
    finally { if (alive && serial === detailSerial) detailLoading.value = false }
  }
  async function refresh() { await Promise.all([load(), loadDetail()]) }
  async function poll() { await refresh(); if (alive) timer = setTimeout(poll, 3000) }
  watch([page, filter], () => { void load() })
  watch(filter, () => { page.value = 1 })
  watch(search, () => { clearTimeout(debounce); debounce = setTimeout(() => { if (page.value !== 1) page.value = 1; else void load() }, 300) })
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
  void poll()
  onBeforeUnmount(() => { alive = false; clearTimeout(timer); clearTimeout(debounce) })
  return { tasks, total, page, search, filter, selectedId, selected, loading, detailLoading, error, detailError, actionError, busy, retryPending, load, loadDetail, refresh, action, retry }
}
