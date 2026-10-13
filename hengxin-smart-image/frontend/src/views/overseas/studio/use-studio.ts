import { computed, onUnmounted, ref } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { createStudioApi, type Asset, type Studio, type StudioEvent, type StudioPicture, type TurnInput } from '@/api/overseas/studio'
import type { TaskDetail } from '@/api/overseas/tasks'
type Pending = { key: string; kind: 'send'; body: TurnInput } | { key: string; kind: 'archive'; body: { pictureIds: string[]; sku: string } } | { key: string; kind: 'complete' }
export function useStudio(task: () => TaskDetail, failure: (reason: unknown) => void, changed: () => void, api = createStudioApi(), actorId = '') {
  const data = ref<Studio>(), text = ref(''), skill = ref(''), attachments = ref<Asset[]>([]), references = ref<StudioPicture[]>([])
  const selected = ref<string[]>([]), events = ref<StudioEvent[]>([]), error = ref(''), busy = ref(false), uploading = ref(false), loading = ref(false)
  const pending = ref<Pending>(), storageKey = `hx-studio-pending:${actorId}:${task().id}`
  try { const saved = sessionStorage.getItem(storageKey); if (saved) pending.value = JSON.parse(saved) as Pending } catch { /* Storage may be disabled. */ }
  const editable = computed(() => !!data.value && !data.value.completed && task().capabilities.includes('task.design'))
  const activeTurn = computed(() => data.value?.turns.find(t => t.id === data.value?.activeTurnId))
  const locked = computed(() => !editable.value || busy.value || uploading.value || !!pending.value)
  const canSend = computed(() => !locked.value && !data.value?.activeTurnId && !!(text.value.trim() || attachments.value.length || references.value.length))
  let alive = true, cursor = 0, operation = 0, refreshError = false, timer: ReturnType<typeof setTimeout> | undefined
  const controller = new AbortController()
  function fail(reason: unknown, fromRefresh = false) {
    if (!alive) return
    refreshError = fromRefresh
    error.value = reason instanceof IdentityError && [409,422].includes(reason.status)
      ? (typeof reason.detail === 'string' ? reason.detail : '任务状态或输入已变化，请检查附件、SKU 与执行状态后重试')
      : reason instanceof Error ? reason.message : '工作台请求失败，请重试'
    if (reason instanceof IdentityError && [401,403,404].includes(reason.status)) { data.value = undefined; failure(reason) }
  }
  function savePending(value?: Pending) { pending.value = value; try { if (value) sessionStorage.setItem(storageKey, JSON.stringify(value)); else sessionStorage.removeItem(storageKey) } catch { /* Same-page key remains available. */ } }
  async function refresh() {
    if (loading.value || busy.value || !alive) return
    const snapshot = operation
    loading.value = true
    try {
      const value = await api.get(task().id)
      if (!alive || snapshot !== operation) return
      data.value = value
      const result = await api.events(task().id, cursor)
      if (!alive || snapshot !== operation) return
      const ids = new Set(events.value.map(e => e.id)); events.value.push(...result.items.filter(e => !ids.has(e.id))); cursor = result.cursor
      if (refreshError) { error.value = ''; refreshError = false }
    } catch (reason) { fail(reason, true) }
    finally { loading.value = false }
  }
  async function poll() { await refresh(); if (alive) timer = setTimeout(poll, 2500) }
  void poll()
  async function run(value: Pending) {
    if (busy.value || !task().capabilities.includes('task.design') || (!editable.value && pending.value?.key !== value.key)) return
    savePending(value); ++operation; busy.value = true; error.value = ''
    try {
      const result = value.kind === 'send' ? await api.send(task().id, value.body, value.key)
        : value.kind === 'archive' ? await api.archive(task().id, value.body.pictureIds, value.body.sku, value.key)
          : await api.complete(task().id, value.key)
      if (!alive) return false
      data.value = result; savePending()
      if (value.kind === 'send') { text.value = ''; attachments.value = []; references.value = [] }
      if (value.kind === 'archive') selected.value = []
      changed(); return true
    } catch (reason) {
      // Unknown response keeps the exact payload/key, including across a browser refresh.
      if (reason instanceof IdentityError && reason.status >= 400 && reason.status < 500 && reason.status !== 408) savePending()
      fail(reason); return false
    } finally { busy.value = false }
  }
  function send() { if (canSend.value) return run({ key: crypto.randomUUID(), kind: 'send', body: { text: text.value.trim(), skillId: skill.value || null, attachmentIds: attachments.value.map(a => a.id), referencePictureIds: references.value.map(p => p.id) } }) }
  function retry() { if (pending.value) return run(pending.value) }
  function archive(sku: string) { if (!locked.value && selected.value.length) return run({ key: crypto.randomUUID(), kind: 'archive', body: { pictureIds: [...selected.value], sku } }) }
  function complete() { if (!locked.value && !data.value?.activeTurnId) return run({ key: crypto.randomUUID(), kind: 'complete' }) }
  async function stop() {
    if (!activeTurn.value || !editable.value || busy.value) return
    ++operation; busy.value = true; error.value = ''
    try { const value = await api.cancel(task().id, activeTurn.value); if (alive) data.value = value }
    catch (reason) { fail(reason) } finally { busy.value = false }
  }
  function add(ids: string[]) { if (locked.value) return; for (const id of ids) { const asset = data.value?.materials.find(a => a.id === id); if (asset && !attachments.value.some(a => a.id === id)) attachments.value.push(asset) } }
  async function receive(files: File[]) {
    if (locked.value) return
    uploading.value = true; error.value = ''
    try { for (const file of files) { const asset = await api.upload(task().id, file, controller.signal); if (alive) attachments.value.push(asset) } }
    catch (reason) { fail(reason) } finally { uploading.value = false }
  }
  function modify(picture: StudioPicture) { if (!locked.value && !references.value.some(p => p.id === picture.id)) references.value.push(picture) }
  function toggle(id: string) { selected.value = selected.value.includes(id) ? selected.value.filter(p => p !== id) : [...selected.value, id] }
  function toggleGroup(pictures: StudioPicture[]) { const ids = pictures.map(p => p.id), all = ids.every(id => selected.value.includes(id)); selected.value = all ? selected.value.filter(id => !ids.includes(id)) : [...new Set([...selected.value, ...ids])] }
  onUnmounted(() => { alive = false; clearTimeout(timer); controller.abort() })
  return { api, data, text, skill, attachments, references, selected, events, error, busy, uploading, loading, pending, editable, activeTurn, locked, canSend, refresh, send, retry, archive, complete, stop, add, receive, modify, toggle, toggleGroup, fail }
}
