import { computed, reactive, watch } from 'vue'
import type { Mode, Picture, Template, HengxinService } from '../../types/hengxin'
import { forgetAnnotationDraft } from './components/annotation/annotation-drafts'
import { createSubmissionState, useTaskSubmission } from './task-submission'

function createSession() {
  return { submission: createSubmissionState(), draft: reactive({
    annotationKey: crypto.randomUUID(),
    template: undefined as Template | undefined, sources: [] as Picture[], name: '', sku: '', note: ''
  }) }
}
// 仅内存保存。可信身份由 /auth/me 的登录状态提供，失去身份时不能读回或重放。
const sessions = new Map<string, ReturnType<typeof createSession>>()
export function useTaskCreationSession(identity: () => string | undefined, mode: () => Mode,
  sessionQuery: () => unknown, send: HengxinService['createTask']) {
  const empty = createSession()
  const session = computed(() => {
    const userId = identity()
    if (!userId) return empty
    const key = JSON.stringify([userId, mode(), sessionQuery()])
    if (!sessions.has(key)) sessions.set(key, createSession())
    return sessions.get(key)!
  })
  watch(() => [session.value, session.value.draft.sources.map(p => p.fileId || p.url).join('|')] as const, ([current, source], previous) => {
    if (mode() !== 'text' || !previous || current !== previous[0] || source === previous[1]) return
    forgetAnnotationDraft(current.draft.annotationKey)
    current.draft.annotationKey = crypto.randomUUID()
    current.draft.note = ''
  }, { flush: 'sync' })
  const submission = useTaskSubmission((input, key) => {
    if (!identity()) throw new Error('请重新登录后确认上次提交')
    return send(input, key)
  }, () => session.value.submission)
  function field<K extends keyof typeof empty.draft>(key: K) {
    return computed({ get: () => session.value.draft[key], set: value => { session.value.draft[key] = value } })
  }
  return { submission, session, template: field('template'), sources: field('sources'), name: field('name'), sku: field('sku'), note: field('note') }
}
