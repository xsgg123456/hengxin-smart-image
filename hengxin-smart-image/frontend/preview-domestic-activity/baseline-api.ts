// In-memory adapters for unchanged production components; no network operations.
import type { ApiUsageQuery, ApiUsageReport, ApiUsageSummary } from '@/types/api-management-usage'
import type { ApiMonitorReport, ChannelMonitor } from '@/types/execution-management'
import { filterRecords, people, records, statuses, summary, type RecordItem } from './data'
function usage(rows: RecordItem[]): ApiUsageSummary {
  const totals = summary(rows), api = rows.filter(r => r.kind !== 'cli_edit'), cli = rows.filter(r => r.kind === 'cli_edit')
  const succeeded = api.filter(r => r.status === 'succeeded').length, failed = api.filter(r => r.status === 'failed').length
  const initial = rows.filter(r => r.kind === 'initial').reduce((sum,r) => sum + r.images, 0)
  return { initialImages: initial, modifiedImages: totals.images - initial, totalGeneratedImages: totals.images, generatedTasks: new Set(rows.filter(r => r.images).map(r => r.task)).size,
    tasksCreated: new Set(rows.map(r => r.task)).size, apiAttempts: totals.api, apiSucceeded: succeeded, apiFailed: failed, apiUnknown: api.filter(r => r.status === 'uncertain').length, apiRunning: api.filter(r => ['queued','running','retry_wait','collecting','cancelling'].includes(r.status)).length, apiRetries: api.filter(r => r.retry).length, apiRetryUnknown: 0,
    cliSubmitted: cli.length, cliStarted: totals.cli, cliUnverified: 0, cliSucceeded: cli.filter(r => r.status === 'succeeded').length, cliFailed: cli.filter(r => r.status === 'failed').length, cliUnknown: cli.filter(r => r.status === 'uncertain').length,
    cliCandidates: cli.reduce((sum,r) => sum+r.images,0), generatedVersions: totals.images, unverifiedVersions: 0, adoptions: 0, restores: 0, unverifiedAttribution: 0,
    requestSuccessRate: succeeded + failed ? succeeded / (succeeded+failed) : null, inputTokens: null, outputTokens: null, cost: null }
}
export async function getApiUsage(query: ApiUsageQuery): Promise<ApiUsageReport> {
  const rows = filterRecords(records, query.userId, query.from && query.to ? [query.from,query.to] : null, query.generationType)
  const events = rows.filter(r => !query.outputsOnly || r.images > 0)
  const groups = [...new Set(rows.map(r => `${r.createdAt.slice(0,10)}|${r.personId}`))]
  const page = query.page || 1, pageSize = query.pageSize || 20
  return { scope: 'all', timezone: 'Asia/Shanghai', users: people, summary: usage(rows),
    inventory: { tasks: 6, sourceImages: 6, withResultImages: 6, succeededImages: 6, failedImages: 0, pendingImages: 0, uncertainImages: 0, deliverySuccessRate: 1 },
    rows: groups.map(key => { const [date,userId] = key.split('|') as [string,string]; return { date, userId, userName: people.find(p=>p.id===userId)!.name, summary: usage(rows.filter(r=>r.personId===userId && r.createdAt.startsWith(date))) } }),
    events: events.slice((page-1)*pageSize,page*pageSize).map(r => ({ id:r.id, category: query.outputsOnly ? 'version_published' : r.kind === 'cli_edit' ? 'cli_round' : 'api_request', channel:r.kind === 'cli_edit' ? 'cli' : 'api', generationType:r.kind, generatedImages:r.images, kind:r.kind === 'initial' ? 'initial' : 'image_edit', taskId:r.id, taskName:r.task, taskDeleted:false, creatorId:r.personId, operatorId:r.personId, operatorName:r.person, occurredAt:r.createdAt, completedAt:r.finishedAt, state:r.status, quantity:1, isRetry:r.retry, attribution:'verified', durationSeconds:r.seconds })),
    total: events.length, page, pageSize }
}
export async function getApiMonitor(): Promise<ApiMonitorReport> {
  const channels: ChannelMonitor[] = (['api','cli'] as const).map(channel => {
    const rows = records.filter(r => channel === 'cli' ? r.kind === 'cli_edit' : r.kind !== 'cli_edit')
    return { channel, state:'available', queueState:'available', enabled:true, paused:false, pauseReason:null, concurrencyLimit:channel === 'api' ? 3 : 2, imagesPerBatch: channel === 'api' ? 5 : null, sharedActiveTurns: channel === 'cli' ? 1 : null,
      workers:[{id:`demo-${channel}-worker`,checkedAt:'2026-11-11T17:00:00+08:00',state:'available',capacity:channel === 'api' ? 5 : 2}],
      metrics:Object.keys(statuses).filter(key=>!['succeeded','cancelled'].includes(key)).map(phase=>{const items=rows.filter(r=>r.status===phase); return {phase,tasks:new Set(items.map(r=>r.task)).size,images:items.length,turns:channel==='cli'?items.length:null}}) }
  })
  return { checkedAt:'2026-11-11T17:00:00+08:00',channels,incidentsTruncated:false,incidents:records.filter(r=>['failed','uncertain'].includes(r.status)).map(r=>({taskId:r.id,name:r.task,channel:r.kind==='cli_edit'?'cli':'api',phase:r.status,images:1})) }
}

export async function getExecutionSettings(): Promise<never> { throw new Error('本次预览不提供系统配置。') }
