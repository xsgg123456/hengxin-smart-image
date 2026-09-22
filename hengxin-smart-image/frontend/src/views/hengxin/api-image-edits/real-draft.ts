import { reactive } from 'vue'
import { apiImages, errorText, uncertainResponse } from '@/api/api-image-edits'
import type { ApiPicture, ApiTaskInput } from '@/types/api-image-edits'
export interface UploadPicture { id: string; name: string; url: string; fileId?: string; state: 'uploading' | 'ready' | 'failed' | 'removing'; error: string; raw: File }
interface DraftApi { upload(file: File): Promise<ApiPicture>; deleteFile(id: string): Promise<unknown>; create(input: ApiTaskInput, key: string): Promise<{ taskId: string }> }
interface Pending { key: string; input: ApiTaskInput; uncertain: boolean }
interface Persistence { load(): Pending | null; save(value: Pending | null): void }
export function createDraft(api: DraftApi, decode: (url: string) => Promise<void>, urls = URL, newKey = () => crypto.randomUUID(), persistence?: Persistence) {
  const state = reactive({ images: [] as UploadPicture[], name: '', prompt: '', error: '', busy: false, pending: null as Pending | null })
  state.pending = persistence?.load() || null
  if (state.pending) { state.name = state.pending.input.name; state.prompt = state.pending.input.prompt }
  const persist = () => persistence?.save(state.pending)
  const locked = () => state.busy || !!state.pending
  const valid = () => state.images.length >= 2 && state.images.length <= 21 && state.images.every(p => p.state === 'ready' && p.fileId)
    && !!state.name.trim() && state.name.trim().length <= 60 && !!state.prompt.trim() && state.prompt.trim().length <= 4000
  async function upload(picture: UploadPicture) {
    picture.state = 'uploading'; picture.error = ''
    try {
      await decode(picture.url)
      const saved = await api.upload(picture.raw)
      picture.fileId = saved.fileId; picture.state = 'ready'
    } catch (e) { picture.state = 'failed'; picture.error = errorText(e) }
  }
  function add(raw: File) {
    if (locked()) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(raw.type) || !raw.size || raw.size > 10 * 1024 * 1024) { state.error = '请选择不超过 10 MiB 的 JPG、PNG 或 WebP 图片。'; return }
    if (state.images.length >= 21) { state.error = '最多添加 20 张原图和 1 张素材。'; return }
    state.error = ''
    state.images.push({ id: newKey(), name: raw.name, url: urls.createObjectURL(raw), state: 'uploading', error: '', raw })
    // 使用响应式占位对象，异步上传完成顺序不会改变输入角色。
    void upload(state.images[state.images.length - 1])
  }
  async function remove(picture: UploadPicture) {
    if (locked() || ['uploading', 'removing'].includes(picture.state)) return
    const previous = picture.state; picture.state = 'removing'; picture.error = ''
    try {
      if (picture.fileId) await api.deleteFile(picture.fileId)
      state.images = state.images.filter(p => p.id !== picture.id); urls.revokeObjectURL(picture.url)
    } catch (e) { picture.state = previous; picture.error = `清理失败：${errorText(e)}` }
  }
  function move(from: number, to: number) {
    if (locked() || to < 0 || to >= state.images.length) return
    const [picture] = state.images.splice(from, 1); if (picture) state.images.splice(to, 0, picture)
  }
  async function submit() {
    if (state.busy || (!state.pending && !valid())) return
    if (!state.pending) state.pending = { key: newKey(), uncertain: false, input: { name: state.name.trim(), prompt: state.prompt.trim(), originalFileIds: state.images.slice(0, -1).map(p => p.fileId!), materialFileId: state.images.at(-1)!.fileId! } }
    persist(); state.busy = true; state.error = ''
    try {
      const result = await api.create(state.pending.input, state.pending.key)
      state.images.forEach(p => urls.revokeObjectURL(p.url)); state.images = []; state.name = ''; state.prompt = ''; state.pending = null
      return result.taskId
    } catch (e) {
      if (uncertainResponse(e)) state.pending!.uncertain = true
      else if (!state.pending?.uncertain) state.pending = null
      state.error = `${errorText(e)}${state.pending ? '。受理结果尚未确认，请使用原请求再次确认；输入已锁定，避免重复创建。' : ''}`
    } finally { persist(); state.busy = false }
  }
  return { state, valid, locked, add, remove, move, submit, retry: (p: UploadPicture) => { if (!locked() && p.state === 'failed') void upload(p) } }
}
const drafts = new Map<string, ReturnType<typeof createDraft>>()
export function draftForUser(userId: string) {
  let draft = drafts.get(userId)
  if (!draft) {
    draft = createDraft(apiImages, url => new Promise<void>((resolve, reject) => {
  const image = new Image()
  image.onload = () => resolve(); image.onerror = () => reject(new Error('图片无法解码，请重新选择有效图片'))
  image.src = url
}), URL, () => crypto.randomUUID(), pendingStorage(userId))
    drafts.set(userId, draft)
  }
  return draft
}

function pendingStorage(userId: string): Persistence {
  const key = 'api-image-pending:' + userId
  return {
    load() {
      try {
        const value: unknown = JSON.parse(sessionStorage.getItem(key) || 'null')
        if (!value || typeof value !== 'object') return null
        const pending = value as Partial<Pending>, input = pending.input
        if (typeof pending.key !== 'string' || !input || typeof input.name !== 'string' || typeof input.prompt !== 'string'
          || typeof input.materialFileId !== 'string' || !Array.isArray(input.originalFileIds) || !input.originalFileIds.every(id => typeof id === 'string')) return null
        return { key: pending.key, input, uncertain: true }
      } catch { return null }
    },
    save(value) { try { if (value) sessionStorage.setItem(key, JSON.stringify(value)); else sessionStorage.removeItem(key) } catch { /* 当前会话内仍保留原请求 */ } }
  }
}
