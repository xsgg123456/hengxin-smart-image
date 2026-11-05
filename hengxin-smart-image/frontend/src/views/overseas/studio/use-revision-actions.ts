import type { Ref } from 'vue'
import type { Asset, Studio, StudioApi, StudioPicture } from '@/api/overseas/studio'
import { turnLimitError } from '@/api/overseas/upload-limits'
import { cloneMarks, type AnnotationMark } from '@/views/hengxin/components/annotation/annotation-model'
import { forgetAnnotationDraft } from '@/views/hengxin/components/annotation/annotation-drafts'
import { forgetDraft, type Reference } from './editing/state'
import { revisionAssetIds, type RevisionReference, type StudioRevision } from './studio-revisions'

export interface RevisionInput { picture: StudioPicture; text: string; file?: File; marks?: AnnotationMark[]; references?: Reference[] }
interface Context {
  data: Ref<Studio | undefined>; attachments: Ref<Asset[]>; references: Ref<StudioPicture[]>; revisions: Ref<StudioRevision[]>
  locked: Readonly<Ref<boolean>>; editable: Readonly<Ref<boolean>>; uploading: Ref<boolean>; error: Ref<string>
  api: StudioApi; signal: AbortSignal; alive: () => boolean; taskId: () => string; conversationId: () => string | undefined
  draftKey: (p: StudioPicture) => string; fail: (e: unknown) => void; refresh: () => Promise<void>
}
export function useRevisionActions(c: Context) {
  let uploaded = new WeakMap<File, Asset>()
  function forget(key: string) { forgetDraft(key); forgetAnnotationDraft(key) }
  function clearRevisions() { c.revisions.value.forEach(r => forget(r.draftKey)); c.revisions.value = [] }
  function removeRevision(id: string) {
    if (c.locked.value) return
    const old = c.revisions.value.find(r => r.base.id === id), rest = c.revisions.value.filter(r => r.base.id !== id)
    const stillUsed = new Set(rest.flatMap(revisionAssetIds)), removed = new Set(old ? revisionAssetIds(old) : [])
    c.attachments.value = c.attachments.value.filter(a => !removed.has(a.id) || stillUsed.has(a.id))
    if (old) forget(old.draftKey)
    c.revisions.value = rest; c.references.value = c.references.value.filter(p => p.id !== id)
  }
  function validate(item: RevisionInput) {
    if (item.text.length > 4000) throw Error('单张图片完整修改意见不能超过4000字')
    if (item.file && !item.text.trim()) throw Error('请填写每一处标注的修改意见')
    for (const r of item.references || []) {
      if (r.status !== 'ready') throw Error('请重试、替换或删除未读取完成的参考图')
      if (!['product', 'effect', 'custom'].includes(r.kind) || !r.note.trim() || r.note.length > 2000) throw Error('请填写每张参考图的用途和参考说明（最多2000字）')
      if (r.kind === 'custom' && (!r.customPurpose?.trim() || r.customPurpose.length > 2000)) throw Error('请填写自定义图片用途（最多2000字）')
      const size = r.file?.size ?? r.asset?.sizeBytes ?? 0, type = r.file?.type ?? r.asset?.contentType
      if (!size || size > 20 * 1024 * 1024 || !['image/png', 'image/jpeg', 'image/webp'].includes(type || '')) throw Error('参考图仅支持非空JPG、PNG、WebP，单张最大20 MB')
    }
  }
  async function confirmRevisions(items: RevisionInput[], groupIds?: string[]) {
    if (c.locked.value || (!items.length && !groupIds?.length)) return false
    const conversation = c.data.value?.conversationId, taskId = c.taskId()
    const affected = new Set(groupIds || items.map(i => i.picture.id))
    const kept = c.revisions.value.filter(r => !affected.has(r.base.id)), old = c.revisions.value.filter(r => affected.has(r.base.id))
    const used = new Set(kept.flatMap(revisionAssetIds)), removed = new Set(old.flatMap(revisionAssetIds))
    const ordinary = c.attachments.value.filter(a => !removed.has(a.id) || used.has(a.id))
    const existingPictures = c.references.value.filter(p => !old.some(r => r.base.id === p.id))
    try {
      if (new Set(items.map(i => i.picture.id)).size !== items.length) throw Error('修改图片不能重复')
      for (const item of items) validate(item)
      const known = new Set(ordinary.map(a => a.id)), fresh = new Set<File>()
      const countFile = (file: File) => { const cached = uploaded.get(file); if (cached) known.add(cached.id); else fresh.add(file) }
      for (const item of items) {
        if (item.file) countFile(item.file)
        for (const r of item.references || []) { if (r.file) countFile(r.file); else if (r.asset) known.add(r.asset.id) }
      }
      const limit = turnLimitError(known.size + fresh.size, new Set([...existingPictures.map(p => p.id), ...items.map(i => i.picture.id)]).size)
      if (limit) throw Error(limit)
    } catch (e) { c.fail(e); return false }
    c.uploading.value = true; c.error.value = ''
    const valid = () => c.alive() && c.editable.value && c.taskId() === taskId && c.data.value?.conversationId === conversation
    async function upload(file: File) {
      if (!valid()) throw Error('当前对话已变化，请重新选择图片进行修改')
      const found = uploaded.get(file)
      if (found) return found
      const asset = await c.api.upload(taskId, file, c.signal, c.conversationId())
      uploaded.set(file, asset)
      return asset
    }
    try {
      const next: StudioRevision[] = []
      for (const item of items) {
        const annotation = item.file ? await upload(item.file) : undefined
        const referenceImages: RevisionReference[] = []
        for (const r of item.references || []) {
          const asset = r.file ? await upload(r.file) : r.asset
          if (!asset) throw Error('参考图文件已失效，请重新上传')
          if (referenceImages.some(v => v.asset.id === asset.id) || asset.id === annotation?.id) throw Error('同一图片的参考图不能重复，也不能与标注图相同')
          referenceImages.push({ asset: { ...asset }, kind: r.kind as RevisionReference['kind'], customPurpose: r.customPurpose || '', note: r.note })
        }
        next.push({ base: { ...item.picture }, annotation, text: item.text, draftKey: c.draftKey(item.picture), referenceImages,
          ...(item.marks ? { marks: cloneMarks(item.marks) } : {}) })
      }
      if (!c.alive() || !c.editable.value) return false
      if (!valid()) throw Error('当前对话已变化，请重新选择图片进行修改')
      const assets = [...ordinary, ...next.flatMap(r => [...(r.annotation ? [r.annotation] : []), ...(r.referenceImages || []).map(ref => ref.asset)])]
      c.attachments.value = [...new Map(assets.map(a => [a.id, a])).values()]
      c.references.value = [...new Map([...existingPictures, ...items.map(i => i.picture)].map(p => [p.id, p])).values()]
      c.revisions.value = [...kept, ...next]
      uploaded = new WeakMap<File, Asset>()
      return true
    } catch (e) { c.fail(e); return false }
    finally { c.uploading.value = false; if (c.alive()) void c.refresh() }
  }
  function confirmRevision(picture: StudioPicture, prepared: Omit<RevisionInput, 'picture'>) { return confirmRevisions([{ picture, ...prepared }]) }
  return { confirmRevisions, confirmRevision, removeRevision, clearRevisions }
}
