import { reactive, ref } from 'vue'
import type { Asset, StudioPicture, StudioTurn } from '@/api/overseas/studio'
import type { AnnotationMark } from '@/views/hengxin/components/annotation/annotation-model'
import { cloneMarks } from '@/views/hengxin/components/annotation/annotation-model'
import { exportAnnotation } from '@/views/hengxin/components/annotation/annotation-export'
import type { SessionView } from '@/views/overseas/studio/studio-session-state'

export interface Reference { id: string; name: string; url: string; kind: '' | 'product' | 'effect' | 'custom'; customPurpose?: string; note: string; status: 'loading' | 'ready' | 'error'; error: string; file: File }
export interface Draft { marks: AnnotationMark[]; references: Reference[] }
export interface Revision { picture: StudioPicture; marks: AnnotationMark[]; references: Reference[]; annotation: string; text: string }
export const pictures: StudioPicture[] = Array.from({ length: 6 }, (_, i) => ({ id: `preview-picture-${i + 1}`, name: `0${i + 1}.jpg`, url: new URL(`../preview-ai-studio/assets/sample-${i + 1}.jpg`, import.meta.url).href, width: 1250, height: 1600, turnId: 'preview-turn', archived: false, sku: null }))
export const materials: Asset[] = pictures.slice(0, 4).map((p, i) => ({ id: `task:sample-${i}`, name: `产品参考-${i + 1}.jpg`, url: p.url, contentType: 'image/jpeg', sizeBytes: 986247, source: 'task' }))
export const sessions: SessionView[] = ['晴天灯-冷暖-高压', 'H-CTD000501-V2', 'H-CTD000501-V2-主图', '茶几灯-主图和A+', '茶几灯-效果参考'].map((name, i) => ({ id: `session-${i}`, name, version: 1, createdAt: '', updatedAt: '', activeTurnId: null, status: 'succeeded', turnCount: 1, unread: false, draft: false }))
export const seedTurn: StudioTurn = { id: 'preview-turn', text: '请结合产品资料，制作这一组灯具图片。', skillName: null, status: 'succeeded', reply: '已整理这组图片，可逐张检查并提出修改意见。', error: null, jobId: 'preview', jobVersion: 1, attachments: [], referencePictures: [], pictures, actor: { id: 'preview', name: '张帅' }, createdAt: '2026-11-05T01:16:32Z', conversationId: 'session-3' }
export const drafts = reactive<Record<string, Draft>>({})
export const revisions = ref<Revision[]>([])
export const objectUrls = new Set<string>()
const referenceReads = new Map<string, number>()
export function draftFor(id: string): Draft { return drafts[id] ??= { marks: [], references: [] } }
export function referenceLabel(kind: Reference['kind'], customPurpose = '') { return kind === 'product' ? '本产品实拍' : kind === 'effect' ? '成品效果参考' : kind === 'custom' ? customPurpose.trim() : '未选择用途' }
export function revisionText(draft: Draft) {
  return draft.marks.map((m, i) => `标注${i + 1}（${m.kind === 'rect' ? '框选' : '画笔'}）：${m.note.trim()}`).join('\n')
}
export function validateDraft(draft: Draft) {
  if (draft.marks.some(m => !m.note.trim())) return '请填写每一处标注的修改意见'
  if (draft.references.some(r => r.status === 'loading')) return '参考图正在读取，请稍候'
  if (draft.references.some(r => r.status === 'error')) return '请重试、替换或删除无法读取的参考图'
  if (draft.references.some(r => !r.kind || !r.note.trim())) return '请为每张参考图选择用途，并填写参考说明'
  if (draft.references.some(r => r.kind === 'custom' && !r.customPurpose?.trim())) return '请填写自定义图片用途，不能只有空格'
  return ''
}
export async function readReference(item: Reference) {
  const generation = (referenceReads.get(item.id) || 0) + 1
  referenceReads.set(item.id, generation)
  const current = () => referenceReads.get(item.id) === generation
  item.status = 'loading'; item.error = ''
  try {
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(item.file.type)) throw Error('请选择 JPG、PNG 或 WebP 图片')
    if (!item.file.size || item.file.size > 20 * 1024 * 1024) throw Error('参考图不能为空，单张最大20 MB')
    const url = URL.createObjectURL(item.file); objectUrls.add(url)
    try { const img = new Image(); img.src = url; await img.decode(); if (!img.naturalWidth) throw Error(); if (current()) { item.url = url; item.status = 'ready' } }
    catch { throw Error('无法读取图片，请重试或替换文件') }
  } catch (e) { if (current()) { item.status = 'error'; item.error = e instanceof Error ? e.message : '图片读取失败' } }
}
export function addReferences(draft: Draft, files: File[]) {
  for (const file of files) {
    const id = crypto.randomUUID()
    draft.references.push({ id, file, name: file.name, url: '', kind: '', customPurpose: '', note: '', status: 'loading', error: '' })
    void readReference(draft.references.find(r => r.id === id)!)
  }
}
export async function snapshot(picture: StudioPicture): Promise<Revision> {
  const draft = draftFor(picture.id), error = validateDraft(draft)
  if (error) throw Error(`${picture.name}：${error}`)
  const marks = cloneMarks(draft.marks)
  let annotation = ''
  if (marks.length) {
    const img = new Image(); img.src = picture.url; await img.decode()
    annotation = URL.createObjectURL(await exportAnnotation(img, marks, 20 * 1024 * 1024)); objectUrls.add(annotation)
  }
  return { picture: { ...picture }, marks, references: draft.references.map(r => ({ ...r })), annotation, text: revisionText(draft) }
}
export function commitRevisions(items: Revision[]) {
  for (const item of items) {
    const index = revisions.value.findIndex(r => r.picture.id === item.picture.id)
    if (index < 0) revisions.value.push(item); else revisions.value[index] = item
  }
}
export function disposeUrls() { objectUrls.forEach(url => URL.revokeObjectURL(url)); objectUrls.clear() }
