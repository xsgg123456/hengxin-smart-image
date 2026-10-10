export type ExecutionKind = 'initial' | 'text' | 'copy' | 'cli'
export interface PreviewTask {
  id: string; name: string; owner: string; created: string; currentImages: number
}
export interface UsageEvent {
  id: string; taskId: string; user: string; date: string; outputDate: string; publishedDate: string; adoptedDate: string
  kind: ExecutionKind; requests: number; retries: number; requestSuccess: number
  requestFailed: number; requestUnknown: number; cliRounds: number
  targets: number; delivered: number; unknown: number; versions: number; candidates: number; adopted: number
}
export interface UsageFilter { from?: string; to?: string; user?: string; kind?: ExecutionKind | '' }
export const people = ['设计师甲', '设计师乙', '运营丙']
export const kindLabels: Record<ExecutionKind, string> = {
  initial: 'API 首次生成', text: 'API 文字修改', copy: 'API 文案修复', cli: 'CLI 图片修改'
}
const date = (day: number) => `2026-10-${String(day).padStart(2, '0')}`
export const previewTasks: PreviewTask[] = Array.from({ length: 52 }, (_, i) => ({
  id: `API-${String(i + 1).padStart(3, '0')}`, name: `手机商品图 · 第 ${i + 1} 套`,
  owner: people[i % 3]!, created: date(1 + i % 7), currentImages: i < 12 ? 8 : 7
}))
export const usageEvents: UsageEvent[] = previewTasks.flatMap((task, i) => {
  const make = (kind: ExecutionKind, offset: number): UsageEvent => {
    const targets = kind === 'initial' ? task.currentImages : 1
    const cli = kind === 'cli', retries = !cli && i % 4 === 0 ? 2 : 0
    const unknown = offset && i % 11 === 0 ? 1 : 0
    const failed = offset && !unknown && i % 5 === 0 ? 1 : 0
    const delivered = targets - unknown - failed
    const adopted = cli && i % 4 === 0 ? delivered : 0
    const outputDate = delivered ? date(2 + i % 7 + offset) : ''
    const adoptedDate = adopted ? date(3 + i % 7 + offset) : ''
    return {
      id: `${task.id}-${kind}`, taskId: task.id, user: task.owner,
      date: date(1 + i % 7 + offset), outputDate, publishedDate: cli ? adoptedDate : outputDate,
      adoptedDate, kind,
      requests: cli ? 0 : targets + retries, retries,
      requestSuccess: cli ? 0 : delivered, requestFailed: cli ? 0 : failed + retries,
      requestUnknown: cli ? 0 : unknown, cliRounds: cli ? 1 : 0,
      targets, delivered, unknown, versions: cli ? adopted : delivered, candidates: cli ? delivered : 0,
      adopted
    }
  }
  return [make('initial', 0), ...(i % 2 === 0 ? [make(i % 6 === 0 ? 'cli' : i % 4 === 0 ? 'copy' : 'text', 1)] : [])]
})
export const within = (day: string, filter: UsageFilter) =>
  Boolean(day) && (!filter.from || day >= filter.from) && (!filter.to || day <= filter.to)
export const eligible = (event: UsageEvent, filter: UsageFilter) =>
  (!filter.user || event.user === filter.user) && (!filter.kind || event.kind === filter.kind)
export function aggregate(events: UsageEvent[]) {
  const sum = (key: 'requests' | 'retries' | 'requestSuccess' | 'requestFailed' | 'requestUnknown' | 'cliRounds' | 'targets' | 'delivered' | 'unknown' | 'versions' | 'candidates' | 'adopted') => events.reduce((total, e) => total + e[key], 0)
  return { executions: events.length, requests: sum('requests'), retries: sum('retries'),
    requestSuccess: sum('requestSuccess'), requestFailed: sum('requestFailed'), requestUnknown: sum('requestUnknown'),
    cliRounds: sum('cliRounds'), targets: sum('targets'), delivered: sum('delivered'), unknown: sum('unknown'),
    versions: sum('versions'), candidates: sum('candidates'), adopted: sum('adopted') }
}
export function buildUsage(filter: UsageFilter) {
  const scoped = usageEvents.filter(e => eligible(e, filter))
  const executions = scoped.filter(e => within(e.date, filter))
  const outputs = scoped.filter(e => within(e.outputDate, filter))
  const publications = scoped.filter(e => within(e.publishedDate, filter))
  const adoptions = scoped.filter(e => within(e.adoptedDate, filter))
  const inventory = previewTasks.filter(t => !filter.user || t.owner === filter.user)
  const created = inventory.filter(t => within(t.created, filter) && (!filter.kind || filter.kind === 'initial'))
  const keys = new Set([
    ...executions.map(e => `${e.date}|${e.user}`), ...outputs.map(e => `${e.outputDate}|${e.user}`),
    ...publications.map(e => `${e.publishedDate}|${e.user}`), ...adoptions.map(e => `${e.adoptedDate}|${e.user}`), ...created.map(t => `${t.created}|${t.owner}`)
  ])
  const rows = [...keys].sort().reverse().map(key => {
    const [day = '', user = ''] = key.split('|')
    const details = scoped.filter(e => e.user === user && [e.date, e.outputDate, e.publishedDate, e.adoptedDate].includes(day))
    return { key, day, user, details,
      created: created.filter(t => t.created === day && t.owner === user).length,
      summary: aggregate(executions.filter(e => e.date === day && e.user === user)),
      versions: aggregate(publications.filter(e => e.publishedDate === day && e.user === user)).versions,
      candidates: aggregate(outputs.filter(e => e.outputDate === day && e.user === user)).candidates,
      adopted: aggregate(adoptions.filter(e => e.adoptedDate === day && e.user === user)).adopted }
  })
  return { rows, inventory, created: created.length, summary: aggregate(executions),
    versions: aggregate(publications).versions, candidates: aggregate(outputs).candidates, adopted: aggregate(adoptions).adopted }
}
export type UsageDailyRow = ReturnType<typeof buildUsage>['rows'][number]
export const percentage = (numerator: number, denominator: number) => denominator ? `${(numerator / denominator * 100).toFixed(1)}%` : '无数据'
