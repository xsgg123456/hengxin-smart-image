import { computed, reactive } from 'vue'
import { ApiError } from '../../api/hengxin/http'
import type { Accepted, HengxinService, RevisionInput, TaskDetailData } from '../../types/hengxin'

function createSession() {
  return reactive({ drafts: {} as Record<string, string>, target: null as number | null,
    pending: false, uncertain: false, error: '', settled: false,
    accepted: undefined as Accepted | undefined,
    attempt: undefined as { input: RevisionInput; key: string } | undefined })
}
// 与首次提交一致，仅保留在当前页面进程内；登录失效期间不可读取或发送旧身份请求。
const sessions = new Map<string, ReturnType<typeof createSession>>()
export function useRevisionSession(identity: () => string | undefined, taskId: () => string,
  send: HengxinService['revise']) {
  const empty = createSession()
  const session = computed(() => {
    const owner = identity()
    if (!owner) return empty
    const key = JSON.stringify([owner, taskId()])
    if (!sessions.has(key)) sessions.set(key, createSession())
    return sessions.get(key)!
  })
  const target = computed({ get: () => session.value.target, set: value => { session.value.target = value } })
  const note = computed({ get: () => session.value.drafts[String(target.value)] ?? '',
    set: value => { session.value.drafts[String(target.value)] = value } })
  const blocked = computed(() => session.value.pending || session.value.uncertain || (!!session.value.accepted && !session.value.settled))
  function observe(detail: TaskDetailData) {
    const current = session.value
    if (detail.task.id !== taskId() || !current.accepted) return
    const round = detail.rounds.find(item => item.id === current.accepted!.roundId)
    if (round?.finishedAt && !['排队中', '执行中'].includes(round.state)) current.settled = true
  }
  function begin() {
    const current = session.value
    if (blocked.value) return false
    if (current.accepted && current.settled) {
      current.accepted = undefined; current.attempt = undefined; current.settled = false
    }
    current.error = ''
    return true
  }
  async function submit(input: RevisionInput): Promise<Accepted> {
    if (!identity()) throw new Error('请重新登录后确认上次提交')
    if (input.taskId !== taskId()) throw new Error('任务已变化，请重新打开修改意见')
    const current = session.value
    if (current.accepted) return current.accepted
    if (current.pending) throw new Error('提交正在处理中，请稍候')
    if (current.uncertain && JSON.stringify(current.attempt?.input) !== JSON.stringify(input)) {
      throw new Error('上次提交结果尚未确认。当前意见已保留，请先确认上次提交。')
    }
    if (!current.attempt || JSON.stringify(current.attempt.input) !== JSON.stringify(input)) {
      current.attempt = { input: { ...input }, key: crypto.randomUUID() }
    }
    current.pending = true; current.error = ''
    try {
      current.accepted = await send({ ...current.attempt.input }, current.attempt.key)
      current.uncertain = false
      return current.accepted
    } catch (reason) {
      current.uncertain ||= !(reason instanceof ApiError && reason.status >= 400 && reason.status < 500 && reason.status !== 401)
      current.error = reason instanceof Error ? reason.message : '提交失败，请重试'
      throw reason
    } finally { current.pending = false }
  }
  function resolvePrevious() {
    if (!identity()) throw new Error('请重新登录后确认上次提交')
    if (!session.value.attempt) throw new Error('没有待确认的提交')
    return submit(session.value.attempt.input)
  }
  return { session, target, note, blocked, observe, begin, submit, resolvePrevious }
}
