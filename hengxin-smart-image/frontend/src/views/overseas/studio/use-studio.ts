import { computed, onUnmounted, ref } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { createStudioApi, type Asset, type Studio, type StudioTranscript, type StudioPicture, type TurnInput } from '@/api/overseas/studio'
import type { TaskDetail } from '@/api/overseas/tasks'
import { mergeTranscript } from './studio-transcript'
import { turnLimitError } from '@/api/overseas/upload-limits'
import { forgetAnnotationDraft } from '@/views/hengxin/components/annotation/annotation-drafts'
import { studioDraftKey, type StudioRevision } from './studio-revisions'
type Pending = { key: string; kind: 'send'; body: TurnInput; draftKeys?: string[] } | { key: string; kind: 'archive'; body: { pictureIds: string[]; sku: string } } | { key: string; kind: 'complete' | 'conversation' }
export function useStudio(task: () => TaskDetail, failure: (reason: unknown) => void, changed: () => void, api = createStudioApi(), actorId = '') {
  const data = ref<Studio>(), text = ref(''), skill = ref(''), attachments = ref<Asset[]>([]), references = ref<StudioPicture[]>([])
  const revisions = ref<StudioRevision[]>([])
  const selected = ref<string[]>([]), transcript = ref<StudioTranscript[]>([]), error = ref(''), busy = ref(false), uploading = ref(false), loading = ref(false)
  const pending = ref<Pending>(), storageKey = `hx-studio-pending:${actorId}:${task().id}`
  const materialNotice = ref('')
  try { const saved = sessionStorage.getItem(storageKey); if (saved) pending.value = JSON.parse(saved) as Pending } catch { /* Storage may be disabled. */ }
  const editable = computed(() => !!data.value && !data.value.completed && task().capabilities.includes('task.design'))
  const activeTurn = computed(() => data.value?.turns.find(t => t.id === data.value?.activeTurnId))
  const locked = computed(() => !editable.value || busy.value || uploading.value || !!pending.value)
  const limitError = computed(() => turnLimitError(attachments.value.length, references.value.length))
  const revisionError = computed(() => revisions.value.some(r => (!r.text.trim() && (!text.value.trim() || !!r.annotation))) ? '请在工作台输入区补充修改要求' : '')
  const canSend = computed(() => !locked.value && !limitError.value && !revisionError.value && !data.value?.activeTurnId && !!(text.value.trim() || attachments.value.length || references.value.length))
  const canNewConversation = computed(() => !locked.value && !data.value?.activeTurnId)
  let alive = true, cursor = 0, operation = 0, refreshError = false, denied = false, timer: ReturnType<typeof setTimeout> | undefined
  let reading: Promise<void> | undefined
  let readController: AbortController | undefined
  const page = typeof document === 'undefined' ? undefined : document
  const visible = () => page?.visibilityState !== 'hidden'
  const controller = new AbortController()
  function fail(reason: unknown, fromRefresh = false) {
    if (!alive) return
    refreshError = fromRefresh
    error.value = reason instanceof IdentityError && [409,422].includes(reason.status)
      ? (typeof reason.detail === 'string' ? reason.detail : '任务状态或输入已变化，请检查附件、SKU 与执行状态后重试')
      : reason instanceof Error ? reason.message : '工作台请求失败，请重试'
    if (reason instanceof IdentityError && [401,403,404].includes(reason.status)) { denied = true; clearTimeout(timer); data.value = undefined; failure(reason) }
  }
  function savePending(value?: Pending) { pending.value = value; try { if (value) sessionStorage.setItem(storageKey, JSON.stringify(value)); else sessionStorage.removeItem(storageKey) } catch { /* Same-page key remains available. */ } }
  function restoreOversizedDraft(value: Studio) {
    const saved = pending.value
    if (saved?.kind !== 'send' || !turnLimitError(saved.body.attachmentIds.length, saved.body.referencePictureIds.length)) return
    const pictures = value.turns.flatMap(turn => [...turn.pictures, ...turn.referencePictures])
    text.value = saved.body.text; skill.value = saved.body.skillId || ''
    attachments.value = saved.body.attachmentIds.map(id => value.materials.find(asset => asset.id === id)).filter((asset): asset is Asset => !!asset)
    references.value = saved.body.referencePictureIds.map(id => pictures.find(picture => picture.id === id)).filter((picture): picture is StudioPicture => !!picture)
    const missing = saved.body.attachmentIds.length + saved.body.referencePictureIds.length - attachments.value.length - references.value.length
    error.value = missing ? `超限消息已恢复为草稿，其中 ${missing} 项文件已不可访问，请检查并重新添加` : ''
    // The server's unchanged schema cannot have accepted this oversized request.
    savePending()
  }
  function schedule(delay?: number) {
    clearTimeout(timer)
    if (alive && visible() && !denied && !busy.value && !data.value?.completed) timer = setTimeout(() => { void sync() }, delay ?? (data.value?.activeTurnId ? 1000 : 30000))
  }
  async function read() {
    const snapshot = operation
    const request = new AbortController(); readController = request
    try {
      const value = await api.get(task().id, request.signal)
      if (!alive || snapshot !== operation || request.signal.aborted) return
      data.value = value; denied = false; restoreOversizedDraft(value)
      do {
        const result = await api.transcript(task().id, cursor, request.signal)
        if (!alive || snapshot !== operation || request.signal.aborted) return
        if (result.cursor < cursor || (result.hasMore && result.cursor <= cursor)) throw Error('对话同步游标异常，请重试')
        transcript.value = mergeTranscript(transcript.value, result.items); cursor = result.cursor
        if (!result.hasMore) break
      } while (visible())
      if (refreshError) { error.value = ''; refreshError = false }
    } catch (reason) { if (alive && snapshot === operation && !request.signal.aborted) fail(reason, true) }
  }
  async function sync(manual = false) {
    if (!alive || busy.value || (!manual && (!visible() || denied))) return
    clearTimeout(timer)
    if (manual) loading.value = true
    // A manual refresh can join an automatic read without creating a second request.
    if (!reading) reading = read().finally(() => { reading = undefined; if (alive) { loading.value = false; schedule() } })
    await reading
  }
  function refresh() { return sync(true) }
  function visibilityChanged() { clearTimeout(timer); if (visible()) void (reading ? reading.then(() => sync()) : sync()); else readController?.abort() }
  page?.addEventListener('visibilitychange', visibilityChanged)
  void sync()
  async function run(value: Pending) {
    if (busy.value || !task().capabilities.includes('task.design') || (!editable.value && pending.value?.key !== value.key)) return
    if (value.kind === 'send') {
      const reason = turnLimitError(value.body.attachmentIds.length, value.body.referencePictureIds.length)
      if (reason) {
        // This payload exceeds the unchanged server schema and cannot be accepted.
        error.value = reason; return false
      }
    }
    savePending(value); ++operation; readController?.abort(); clearTimeout(timer); busy.value = true; error.value = ''
    try {
      const result = value.kind === 'send' ? await api.send(task().id, value.body, value.key)
        : value.kind === 'archive' ? await api.archive(task().id, value.body.pictureIds, value.body.sku, value.key)
          : value.kind === 'conversation' ? await api.newConversation(task().id, value.key) : await api.complete(task().id, value.key)
      if (!alive) return false
      data.value = result; savePending()
      if (value.kind === 'send') { (value.draftKeys || []).forEach(forgetAnnotationDraft); clearRevisions(); text.value = ''; attachments.value = []; references.value = [] }
      if (value.kind === 'conversation') { clearRevisions(); text.value = ''; skill.value = ''; attachments.value = []; references.value = []; selected.value = [] }
      if (value.kind === 'archive') selected.value = []
      changed(); return true
    } catch (reason) {
      // Unknown response keeps the exact payload/key, including across a browser refresh.
      if (reason instanceof IdentityError && reason.status >= 400 && reason.status < 500 && reason.status !== 408) savePending()
      fail(reason); return false
    } finally { busy.value = false; schedule(0) }
  }
  function send() {
    if (!canSend.value) return
    const body: TurnInput = { text: text.value, skillId: skill.value || null, attachmentIds: attachments.value.map(a => a.id), referencePictureIds: references.value.map(p => p.id) }
    if (revisions.value.length) body.imageEdits = revisions.value.map(r => ({ pictureId: r.base.id, annotationId: r.annotation?.id || null, text: r.text }))
    return run({ key: crypto.randomUUID(), kind: 'send', body, draftKeys: revisions.value.map(r => r.draftKey) })
  }
  function newConversation() { if (canNewConversation.value) return run({ key: crypto.randomUUID(), kind: 'conversation' }) }
  function retry() { if (pending.value) return run(pending.value) }
  function archive(sku: string) { if (!locked.value && selected.value.length) return run({ key: crypto.randomUUID(), kind: 'archive', body: { pictureIds: [...selected.value], sku } }) }
  function complete() { if (!locked.value && !data.value?.activeTurnId) return run({ key: crypto.randomUUID(), kind: 'complete' }) }
  async function stop() {
    if (!activeTurn.value || !editable.value || busy.value) return
    ++operation; readController?.abort(); clearTimeout(timer); busy.value = true; error.value = ''
    try { const value = await api.cancel(task().id, activeTurn.value); if (alive) data.value = value }
    catch (reason) { fail(reason) } finally { busy.value = false; schedule(0) }
  }
  function add(ids: string[]) {
    if (locked.value) return
    const additions = [...new Set(ids)].filter(id => !attachments.value.some(a => a.id === id))
      .map(id => data.value?.materials.find(a => a.id === id)).filter((asset): asset is Asset => !!asset)
    const reason = turnLimitError(attachments.value.length + additions.length, references.value.length)
    if (reason) { error.value = reason; return }
    attachments.value.push(...additions); error.value = ''
  }
  async function removeMaterial(assetId: string) {
    if (locked.value) return false
    ++operation; readController?.abort(); clearTimeout(timer); busy.value = true; error.value = ''
    try {
      const value = await api.removeMaterial(task().id, assetId)
      if (!alive) return false
      data.value = value
      return true
    } catch (reason) { fail(reason); return false }
    finally { busy.value = false; schedule(0) }
  }
  async function receive(files: File[]) {
    if (locked.value) return
    const reason = turnLimitError(attachments.value.length + files.length, references.value.length)
    if (reason) { error.value = reason; return }
    uploading.value = true; error.value = ''; materialNotice.value = ''
    try { for (const file of files) {
      const asset = await api.upload(task().id, file, controller.signal)
      if (alive) {
        attachments.value.push(asset)
        if (asset.materialState === 'existing') materialNotice.value = '该文件已在任务素材中'
        else if (asset.materialState === 'restored') materialNotice.value = '已恢复到任务素材列表'
      }
    } }
    catch (reason) { fail(reason) } finally { uploading.value = false; if (alive) void sync() }
  }
  function modify(picture: StudioPicture) {
    if (locked.value || references.value.some(p => p.id === picture.id)) return
    const reason = turnLimitError(attachments.value.length, references.value.length + 1)
    if (reason) { error.value = reason; return }
    references.value.push(picture); error.value = ''
  }
  const draftKey = (picture: StudioPicture) => studioDraftKey(actorId, task().id, data.value?.conversationId, picture.id)
  function clearRevisions() { revisions.value.forEach(r => forgetAnnotationDraft(r.draftKey)); revisions.value = [] }
  function removeRevision(id: string) {
    if (locked.value) return
    const old = revisions.value.find(r => r.base.id === id)
    if (old?.annotation) attachments.value = attachments.value.filter(a => a.id !== old.annotation!.id)
    if (old) forgetAnnotationDraft(old.draftKey)
    revisions.value = revisions.value.filter(r => r.base.id !== id); references.value = references.value.filter(p => p.id !== id)
  }
  async function confirmRevision(picture: StudioPicture, prepared: { text: string; file?: File }) {
    if (locked.value) return false
    const conversation = data.value?.conversationId, taskId = task().id
    const old = revisions.value.find(r => r.base.id === picture.id)
    const count = attachments.value.length - (old?.annotation && attachments.value.some(a => a.id === old.annotation!.id) ? 1 : 0) + (prepared.file ? 1 : 0)
    const reason = turnLimitError(count, references.value.length + (references.value.some(p => p.id === picture.id) ? 0 : 1))
    if (reason) { error.value = reason; return false }
    if (prepared.file && !prepared.text.trim()) { error.value = '请填写每一处标注的修改意见'; return false }
    uploading.value = true; error.value = ''
    try {
      const annotation = prepared.file ? await api.upload(taskId, prepared.file, controller.signal) : undefined
      if (!alive || !editable.value) return false
      if (task().id !== taskId || data.value?.conversationId !== conversation) throw Error('当前对话已变化，请重新选择图片进行修改')
      if (old?.annotation) attachments.value = attachments.value.filter(a => a.id !== old.annotation!.id)
      if (annotation) attachments.value.push(annotation)
      if (!references.value.some(p => p.id === picture.id)) references.value.push(picture)
      const revision: StudioRevision = { base: picture, annotation, text: prepared.text, draftKey: draftKey(picture) }
      revisions.value = [...revisions.value.filter(r => r.base.id !== picture.id), revision]
      return true
    } catch (reason) { fail(reason); return false } finally { uploading.value = false; if (alive) void sync() }
  }
  function toggle(id: string) { selected.value = selected.value.includes(id) ? selected.value.filter(p => p !== id) : [...selected.value, id] }
  function toggleGroup(pictures: StudioPicture[]) { const ids = pictures.map(p => p.id), all = ids.every(id => selected.value.includes(id)); selected.value = all ? selected.value.filter(id => !ids.includes(id)) : [...new Set([...selected.value, ...ids])] }
  onUnmounted(() => { alive = false; clearRevisions(); clearTimeout(timer); page?.removeEventListener('visibilitychange', visibilityChanged); controller.abort(); readController?.abort() })
  return { api, data, text, skill, attachments, references, revisions, revisionError, draftKey, confirmRevision, removeRevision, selected, transcript, error, limitError, busy, uploading, loading, pending, editable, activeTurn, locked, canSend, canNewConversation, refresh, send, newConversation, retry, archive, complete, stop, add, receive, modify, toggle, toggleGroup, fail, removeMaterial, materialNotice }
}
