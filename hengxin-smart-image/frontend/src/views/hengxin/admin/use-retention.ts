import { onBeforeUnmount, onMounted, reactive, ref, shallowRef, watch } from 'vue'
import { identity } from '../../../api/hengxin/identity'
import { ApiError } from '../../../api/hengxin/http'
import type { RetentionApi, RetentionQuery, RetentionRecords, RetentionRow, RetentionSummary } from '../../../types/retention'

export function useRetention(api: RetentionApi) {
  const summary = shallowRef<RetentionSummary>(), records = shallowRef<RetentionRecords>(), selected = shallowRef<RetentionRow>()
  const summaryError = ref(''), recordsError = ref(''), detailError = ref('')
  const summaryLoading = ref(false), recordsLoading = ref(false), detailLoading = ref(false), detailOpen = ref(false), auto = ref(true)
  const query = reactive<RetentionQuery>({ tab: 'history', keyword: '', kind: '', result: '', page: 1, pageSize: 20 })
  const dates = ref<[string, string] | null>(null)
  let summarySequence = 0, recordsSequence = 0, detailSequence = 0, alive = true
  const epoch = identity.epoch
  const active = () => alive && identity.current(epoch)
  const message = (e: unknown) => e instanceof Error ? e.message : '读取失败，请重试'
  const denied = (e: unknown) => e instanceof ApiError && [401, 403].includes(e.status)
  async function loadSummary() {
    if (!active()) return
    const sequence = ++summarySequence; summaryLoading.value = true
    try { const value = await api.summary(); if (active() && sequence === summarySequence) { summary.value = value; summaryError.value = '' } }
    catch (e) { if (active() && sequence === summarySequence) { summaryError.value = message(e); if (denied(e)) summary.value = undefined } }
    finally { if (active() && sequence === summarySequence) summaryLoading.value = false }
  }
  async function loadRecords(clear = false) {
    if (!active()) return
    const sequence = ++recordsSequence; recordsLoading.value = true
    if (clear) { records.value = undefined; recordsError.value = '' }
    try { const value = await api.records({ ...query }); if (active() && sequence === recordsSequence) { records.value = value; recordsError.value = '' } }
    catch (e) { if (active() && sequence === recordsSequence) { recordsError.value = message(e); if (denied(e)) records.value = undefined } }
    finally { if (active() && sequence === recordsSequence) recordsLoading.value = false }
  }
  async function openDetail(row: RetentionRow) {
    if (!active()) return
    const sequence = ++detailSequence; detailOpen.value = true; detailLoading.value = true; detailError.value = ''; selected.value = undefined
    try { const value = await api.detail(row.id, row.detailTab); if (active() && sequence === detailSequence) selected.value = value }
    catch (e) { if (active() && sequence === detailSequence) detailError.value = message(e) }
    finally { if (active() && sequence === detailSequence) detailLoading.value = false }
  }
  function closeDetail() { detailSequence++; detailOpen.value = false; selected.value = undefined; detailLoading.value = false; detailError.value = '' }
  function reset() { query.keyword = ''; query.kind = ''; query.result = ''; dates.value = null; query.page = 1 }
  function refresh() { return Promise.all([loadSummary(), loadRecords()]) }
  watch(dates, value => { query.dateFrom = value?.[0]; query.dateTo = value?.[1] }, { flush: 'sync' })
  watch(() => query.tab, reset, { flush: 'sync' })
  watch(() => [query.tab, query.keyword, query.kind, query.result, query.dateFrom, query.dateTo, query.pageSize], () => { query.page = 1 }, { flush: 'sync' })
  watch(query, () => { void loadRecords(true) })
  let timer: ReturnType<typeof setInterval> | undefined
  function stop() { if (timer !== undefined) clearInterval(timer); timer = undefined }
  const unsubscribe = identity.subscribe(() => {
    stop(); summarySequence++; recordsSequence++; closeDetail(); summary.value = undefined; records.value = undefined
    summaryLoading.value = false; recordsLoading.value = false; summaryError.value = '身份已变化，请重新打开自动清理页面'; recordsError.value = ''
  })
  onMounted(() => {
    void refresh()
    timer = setInterval(() => { if (active() && auto.value && !document.hidden && !summaryLoading.value && !recordsLoading.value) void refresh() }, 15000)
  })
  onBeforeUnmount(() => { alive = false; stop(); unsubscribe() })
  return { summary, records, selected, summaryError, recordsError, detailError, summaryLoading, recordsLoading, detailLoading, detailOpen, auto, query, dates, refresh, loadRecords, openDetail, closeDetail, reset }
}
