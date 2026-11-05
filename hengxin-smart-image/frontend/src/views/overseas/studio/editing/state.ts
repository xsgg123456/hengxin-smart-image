import { reactive } from 'vue'
import type { Asset, StudioPicture } from '@/api/overseas/studio'
import { overseasImageCache } from '@/api/overseas/image-cache'
import { MAX_UPLOAD_BYTES } from '@/api/overseas/upload-limits'
import { annotationDraft, forgetAnnotationDraft } from '@/views/hengxin/components/annotation/annotation-drafts'
import { cloneMarks, type AnnotationMark } from '@/views/hengxin/components/annotation/annotation-model'
import { exportAnnotation } from '@/views/hengxin/components/annotation/annotation-export'
import { imageUrl, loadStudioImage } from '../studio-images'

export interface Reference { id: string; name: string; url: string; kind: '' | 'product' | 'effect' | 'custom'; customPurpose?: string; note: string; status: 'loading' | 'ready' | 'error'; error: string; file?: File; asset?: Asset }
export interface Draft { marks: AnnotationMark[]; references: Reference[] }
export interface PreparedRevision { picture: StudioPicture; originalPreview?: string; marks: AnnotationMark[]; file?: File; annotation: string; text: string; draftKey: string; references: Reference[] }
type Seed = { asset: Asset; kind: 'product' | 'effect' | 'custom'; customPurpose?: string; note: string }
const drafts = new Map<string, Draft>()
const reads = new Map<string, AbortController>()
const referenceUrls = new Set<string>(), preparedUrls = new Set<string>()
const MAX_REFERENCE_BYTES = 20 * 1024 * 1024

export function draftFor(key: string, seed: Seed[] = []): Draft {
  let draft = drafts.get(key)
  if (!draft) {
    draft = reactive<Draft>({
      get marks() { return annotationDraft(key).marks },
      set marks(value) { annotationDraft(key).marks = value },
      references: seed.map(s => ({ ...s, id: crypto.randomUUID(), name: s.asset.name, url: '', status: 'loading', error: '' }))
    })
    drafts.set(key, draft)
    draft.references.forEach(r => { void readReference(r) })
  }
  return draft
}
function disposeReference(item: Reference) {
  reads.get(item.id)?.abort(); reads.delete(item.id)
  if (referenceUrls.delete(item.url)) URL.revokeObjectURL(item.url)
  item.url = ''
}
export function removeReference(draft: Draft, item: Reference) {
  disposeReference(item); draft.references = draft.references.filter(r => r.id !== item.id)
}
export function clearDraft(draft: Draft) { draft.references.forEach(disposeReference); draft.references = []; draft.marks = [] }
export function forgetDraft(key: string) { const draft = drafts.get(key); if (draft) clearDraft(draft); drafts.delete(key); forgetAnnotationDraft(key) }
export function referenceLabel(kind: Reference['kind'], purpose = '') { return kind === 'product' ? '本产品实拍' : kind === 'effect' ? '成品效果参考' : kind === 'custom' ? purpose.trim() : '未选择用途' }
export function revisionText(draft: Draft) { return draft.marks.map((m, i) => `标注${i + 1}（${m.kind === 'rect' ? '框选' : '画笔'}）：${m.note.trim()}`).join('\n') }
export function validateDraft(draft: Draft) {
  if (draft.marks.some(m => !m.note.trim())) return '请填写每一处标注的修改意见'
  if (revisionText(draft).length > 4000) return '完整修改意见不能超过 4000 字，请调整后提交'
  if (draft.references.some(r => r.status === 'loading')) return '参考图正在读取，请稍候'
  if (draft.references.some(r => r.status === 'error')) return '请重试、替换或删除无法读取的参考图'
  if (draft.references.some(r => !r.kind || !r.note.trim())) return '请为每张参考图选择用途，并填写参考说明'
  if (draft.references.some(r => r.kind === 'custom' && !r.customPurpose?.trim())) return '请填写自定义图片用途，不能只有空格'
  if (draft.references.some(r => r.note.length > 2000 || (r.kind === 'custom' && (r.customPurpose?.length || 0) > 2000))) return '参考说明和自定义用途每项不能超过 2000 字'
  if (draft.references.some(r => !r.file && !r.asset)) return '参考图文件已失效，请重新上传'
  return ''
}
export async function decodeImage(blob: Blob) {
  const url = URL.createObjectURL(blob)
  try {
    const image = new Image(); image.src = url; await image.decode()
    if (!image.naturalWidth || !image.naturalHeight) throw Error('图片无法解码')
    return { url, image }
  } catch (error) { URL.revokeObjectURL(url); throw error }
}
export async function readReference(item: Reference) {
  disposeReference(item)
  const controller = new AbortController(); reads.set(item.id, controller)
  const current = () => reads.get(item.id) === controller && !controller.signal.aborted
  item.status = 'loading'; item.error = ''
  let url = ''
  try {
    const source = item.file || item.asset
    const type = item.file?.type || item.asset?.contentType, size = item.file?.size ?? item.asset?.sizeBytes ?? 0
    if (!source || !['image/jpeg', 'image/png', 'image/webp'].includes(type || '')) throw Error('请选择 JPG、PNG 或 WebP 图片')
    if (!size || size > MAX_REFERENCE_BYTES) throw Error('参考图不能为空，单张最大20 MiB')
    let blob: Blob
    if (item.file) blob = item.file
    else {
      const lease = await overseasImageCache.acquire(imageUrl(item.asset!), { signal: controller.signal })
      try { blob = lease.blob } finally { lease.release() }
    }
    if (!current()) return
    if (!blob.size || blob.size > MAX_REFERENCE_BYTES) throw Error('参考图不能为空，单张最大20 MiB')
    const decoded = await decodeImage(blob); url = decoded.url
    if (current()) { item.url = url; referenceUrls.add(url); url = ''; item.status = 'ready' }
  } catch (error) { if (current()) { item.status = 'error'; item.error = error instanceof Error ? error.message : '图片读取失败，请重试或替换文件' } }
  finally { if (url) URL.revokeObjectURL(url); if (current()) reads.delete(item.id) }
}
export function addReferences(draft: Draft, files: File[]) {
  for (const file of files) {
    draft.references.push({ id: crypto.randomUUID(), file, name: file.name, url: '', kind: '', customPurpose: '', note: '', status: 'loading', error: '' })
    void readReference(draft.references[draft.references.length - 1])
  }
}
export async function snapshot(picture: StudioPicture, key: string, signal: AbortSignal): Promise<PreparedRevision> {
  const draft = draftFor(key), error = validateDraft(draft)
  if (error) throw Error(`${picture.name}：${error}`)
  const marks = cloneMarks(draft.marks), text = revisionText(draft), references = draft.references.map(r => ({ ...r }))
  const { url, image } = await decodeImage(await loadStudioImage(picture, signal))
  let annotation = ''
  try {
    if (signal.aborted) throw Error('已取消读取')
    const file = marks.length ? await exportAnnotation(image, marks, MAX_UPLOAD_BYTES) : undefined
    if (signal.aborted) throw Error('已取消读取')
    if (file) { annotation = URL.createObjectURL(file); preparedUrls.add(annotation) }
    preparedUrls.add(url)
    return { picture: { ...picture }, originalPreview: url, marks, file, annotation, text, draftKey: key, references }
  } catch (error) { URL.revokeObjectURL(url); if (annotation) { URL.revokeObjectURL(annotation); preparedUrls.delete(annotation) }; throw error }
}
export function disposePrepared(items: PreparedRevision[]) {
  for (const item of items) for (const url of [item.annotation, item.originalPreview || '']) if (preparedUrls.delete(url)) URL.revokeObjectURL(url)
}
