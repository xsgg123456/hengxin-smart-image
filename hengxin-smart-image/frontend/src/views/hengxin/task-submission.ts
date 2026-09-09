import { computed, reactive } from 'vue'
import type { Accepted, CreateTaskInput, HengxinService } from '../../types/hengxin'
import { ApiError } from '../../api/hengxin/http'

/** 保存送出的快照与回执；未知响应只能重放原请求，不能静默变成新任务。 */
export function createSubmissionState() {
  return reactive({ accepted: undefined as Accepted | undefined, uncertain: false, pending: false,
    attempt: undefined as { fingerprint: string; input: CreateTaskInput; key: string } | undefined })
}
export function useTaskSubmission(send: HengxinService['createTask'], state = (() => {
  const local = createSubmissionState()
  return () => local
})()) {
  const accepted = computed(() => state().accepted), uncertain = computed(() => state().uncertain)
  async function submit(input: CreateTaskInput): Promise<Accepted> {
    const current = state()
    if (current.accepted) return current.accepted
    if (current.pending) throw new Error('提交正在处理中，请稍候')
    const snapshot = JSON.parse(JSON.stringify(input)) as CreateTaskInput
    const fingerprint = JSON.stringify(snapshot)
    if (current.uncertain && current.attempt?.fingerprint !== fingerprint) {
      throw new Error('上次提交结果尚未确认。当前输入已保留，请先确认上次提交，再创建新任务。')
    }
    if (!current.attempt || current.attempt.fingerprint !== fingerprint) current.attempt = { fingerprint, input: snapshot, key: crypto.randomUUID() }
    current.pending = true
    try {
      current.accepted = await send(current.attempt.input, current.attempt.key)
      current.uncertain = false
      return current.accepted
    } catch (reason) {
      current.uncertain = current.uncertain || !(reason instanceof ApiError && reason.status >= 400 && reason.status < 500 && reason.status !== 401)
      throw reason
    } finally { current.pending = false }
  }
  async function resolvePrevious() {
    const attempt = state().attempt
    if (!attempt) throw new Error('没有待确认的提交')
    return submit(attempt.input)
  }
  function startNew() {
    const current = state()
    if (!current.accepted || current.pending) return
    current.accepted = undefined; current.attempt = undefined; current.uncertain = false
  }
  return { accepted, uncertain, submit, resolvePrevious, startNew }
}
