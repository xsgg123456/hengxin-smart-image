import { reactive } from 'vue'
import type { AnnotationMark } from './annotation-model'

export interface AnnotationDraft {
  mode: 'direct' | 'upload'
  marks: AnnotationMark[]
  general: string
  uploaded?: File
}
const drafts = new Map<string, AnnotationDraft>()
export function annotationDraft(key: string): AnnotationDraft {
  let draft = drafts.get(key)
  if (!draft) { draft = reactive<AnnotationDraft>({ mode: 'direct', marks: [], general: '' }); drafts.set(key, draft) }
  return draft
}
export function forgetAnnotationDraft(key: string) { drafts.delete(key) }
export function annotationText(draft: AnnotationDraft, limit: number, allowImageOnly = true): string {
  const marks = draft.mode === 'direct' ? draft.marks : []
  if (marks.some(mark => !mark.note.trim())) throw new Error('请填写每一处标注的修改意见')
  const text = [...marks.map((mark, i) => `标注 ${i + 1}（${mark.kind === 'rect' ? '框选' : '画笔'}）：${mark.note.trim()}`), draft.general.trim()].filter(Boolean).join('\n')
  if (!text && !(allowImageOnly && draft.mode === 'upload' && draft.uploaded)) throw new Error(allowImageOnly ? '请填写修改意见或上传标注图' : '请填写修改意见，说明标注位置需要如何调整')
  if (text.length > limit) throw new Error(`完整修改意见不能超过 ${limit} 字，请调整后提交`)
  return text
}
