import { ref, watch, type Ref } from 'vue'
import { isAsset, type Asset, type Studio, type StudioPicture } from '@/api/overseas/studio'
import { record } from '@/api/identity/request'
import { annotationDraft } from '@/views/hengxin/components/annotation/annotation-drafts'
import type { AnnotationMark } from '@/views/hengxin/components/annotation/annotation-model'
import { studioDraftKey, type StudioRevision } from './studio-revisions'

interface Composer {
  text: Ref<string>; skill: Ref<string>; attachments: Ref<Asset[]>
  references: Ref<StudioPicture[]>; revisions: Ref<StudioRevision[]>
}
const storageWarning = '浏览器无法保存草稿，请保持此页面打开，刷新或离开可能丢失未发送内容。'
const skillWarning = '草稿中的 Skill 已不可用，请重新选择后发送。'
export const composerDraftKey = (actor: string, task: string, conversation?: string | null) =>
  `hx-studio-draft:${JSON.stringify([actor, task, conversation || ''])}`

function isMark(value: unknown): value is AnnotationMark {
  return record(value) && typeof value.id === 'string' && ['rect', 'pen'].includes(String(value.kind))
    && typeof value.note === 'string' && ['x', 'y', 'width', 'height'].every(k => typeof value[k] === 'number' && Number.isFinite(value[k]))
    && Array.isArray(value.points) && value.points.every(p => record(p) && typeof p.x === 'number' && Number.isFinite(p.x) && typeof p.y === 'number' && Number.isFinite(p.y))
}

export function useComposerDraft(actor: string, task: string, state: Composer) {
  const notice = ref('')
  let key = '', changing = false
  let availableSkills = new Set<string>()
  function clearFields() {
    state.text.value = ''; state.skill.value = ''; state.attachments.value = []
    state.references.value = []; state.revisions.value = []
  }
  function save() {
    if (!key || changing || !actor) return
    const { text, skill, attachments, references, revisions } = state
    try {
      if (!text.value && !skill.value && !attachments.value.length && !references.value.length && !revisions.value.length) localStorage.removeItem(key)
      else localStorage.setItem(key, JSON.stringify({ version: 1, text: text.value, skill: skill.value,
        attachments: attachments.value, references: references.value.map(p => p.id),
        revisions: revisions.value.map(r => ({ pictureId: r.base.id, annotationId: r.annotation?.id || null,
          text: r.text, marks: annotationDraft(r.draftKey).marks })) }))
      notice.value = skill.value && !availableSkills.has(skill.value) ? skillWarning : ''
    } catch { notice.value = storageWarning }
  }
  function activate(value: Studio) {
    availableSkills = new Set(value.skills.map(s => s.id))
    const next = composerDraftKey(actor, task, value.conversationId)
    if (!actor || next === key) {
      if (state.skill.value && !availableSkills.has(state.skill.value)) notice.value = skillWarning
      else if (notice.value === skillWarning) notice.value = ''
      return
    }
    changing = true
    if (key) clearFields()
    key = next
    try {
      const raw = localStorage.getItem(key)
      if (!raw) return
      const saved: unknown = JSON.parse(raw)
      if (!record(saved) || saved.version !== 1 || typeof saved.text !== 'string' || typeof saved.skill !== 'string'
        || !Array.isArray(saved.attachments) || !saved.attachments.every(a => isAsset(a, task))
        || !Array.isArray(saved.references) || !saved.references.every(id => typeof id === 'string') || !Array.isArray(saved.revisions)) throw Error('invalid draft')
      const pictures = value.turns.flatMap(t => [...t.pictures, ...t.referencePictures])
      const revisions: StudioRevision[] = []
      for (const item of saved.revisions) {
        if (!record(item) || typeof item.pictureId !== 'string' || typeof item.text !== 'string'
          || !(item.annotationId === null || typeof item.annotationId === 'string') || !Array.isArray(item.marks) || !item.marks.every(isMark)) throw Error('invalid revision')
        const base = pictures.find(p => p.id === item.pictureId)
        const annotation = saved.attachments.find(a => a.id === item.annotationId)
        if (!base || (item.annotationId && !annotation) || !saved.references.includes(item.pictureId)) throw Error('missing revision')
        const draftKey = studioDraftKey(actor, task, value.conversationId, base.id)
        annotationDraft(draftKey).marks = item.marks
        revisions.push({ base, annotation, text: item.text, draftKey })
      }
      const references = saved.references.map(id => pictures.find(p => p.id === id)).filter((p): p is StudioPicture => !!p)
      if (references.length !== saved.references.length) throw Error('missing reference')
      state.text.value = saved.text; state.skill.value = saved.skill; state.attachments.value = saved.attachments
      state.references.value = references; state.revisions.value = revisions
      notice.value = saved.skill && !availableSkills.has(saved.skill) ? skillWarning : ''
    } catch { notice.value = '草稿暂时无法恢复，请检查浏览器存储或重新添加内容；任务素材仍可引用。' }
    finally { changing = false }
  }
  function clear(conversation?: string | null) {
    // A late receipt may target a different draft than the currently activated one.
    if (conversation === undefined || key === composerDraftKey(actor, task, conversation)) {
      changing = true; clearFields(); changing = false; save()
    }
    if (actor && conversation !== undefined) {
      try { localStorage.removeItem(composerDraftKey(actor, task, conversation)) } catch { notice.value = storageWarning }
    }
  }
  watch([state.text, state.skill, state.attachments, state.references, state.revisions,
    () => state.revisions.value.map(r => annotationDraft(r.draftKey).marks)], save, { deep: true, flush: 'sync' })
  return { activate, clear, notice }
}
