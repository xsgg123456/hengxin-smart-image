export type RetentionTab = 'history' | 'pending'
export type RetentionKind = 'cache' | 'history'
export type RetentionResult = 'cache_cleared' | 'complete' | 'objects_pending' | 'retry' | 'protected' | 'waiting' | 'due' | 'processing'
export interface RetentionSummary {
  checkedAt: string
  policy: { enabled: boolean; cacheIdleHours: number; historyIdleHours: number; batchSize: number; scanIntervalSeconds: number; detailRetentionDays: number }
  service: { state: 'online' | 'offline' | 'unknown' | 'disabled'; heartbeatAt: string | null; scanState: 'running' | 'completed' | 'failed' | 'unknown'; lastStartedAt: string | null; lastFinishedAt: string | null; nextScanAt: string | null }
  statisticsSince: string | null
  counts: Record<'cacheToday' | 'cacheTotal' | 'historyToday' | 'historyTotal' | 'retry' | 'overdue' | 'protected' | 'objectsPending', number | null>
}
export interface RetentionRow {
  id: string; resourceId: string; taskId: string | null; taskName: string; imagePosition: number
  kind: RetentionKind; result: RetentionResult; detailTab: RetentionTab
  processedAt: string | null; lastActivityAt: string; dueAt: string; nextAttemptAt: string | null
  detail: string; turnsRemoved: number; objectsRemoved: number; objectsPending: number; taskDeleted: boolean
}
export interface RetentionRecords { items: RetentionRow[]; total: number; page: number; pageSize: number }
export interface RetentionQuery {
  tab: RetentionTab; keyword?: string; kind?: RetentionKind | ''; result?: RetentionResult | ''
  dateFrom?: string; dateTo?: string; page: number; pageSize: number
}
export interface RetentionApi {
  summary(): Promise<RetentionSummary>
  records(query: RetentionQuery): Promise<RetentionRecords>
  detail(id: string, tab: RetentionTab): Promise<RetentionRow>
}
