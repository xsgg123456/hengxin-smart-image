import type { RetentionRow, RetentionSummary, RetentionRecords } from '../src/types/retention'
export const summary = (): RetentionSummary => ({
  checkedAt: '2026-10-21T07:00:00Z', statisticsSince: '2026-10-20T00:00:00+08:00',
  policy: { enabled: true, cacheIdleHours: 24, historyIdleHours: 72, batchSize: 25, scanIntervalSeconds: 3600, detailRetentionDays: 90 },
  service: { state: 'online', heartbeatAt: '2026-10-21T06:59:59Z', scanState: 'completed', lastStartedAt: '2026-10-21T06:00:00Z', lastFinishedAt: '2026-10-21T06:00:20Z', nextScanAt: '2026-10-21T07:00:20Z' },
  counts: { cacheToday: 2, cacheTotal: 4, historyToday: 1, historyTotal: 3, retry: 1, overdue: 2, protected: 1, objectsPending: 1 }
})
export const row = (): RetentionRow => ({ id: 'receipt-1', resourceId: 'conversation-1', taskId: null, taskName: '删除任务仍保留摘要', imagePosition: 2, kind: 'history', result: 'objects_pending', detailTab: 'history', processedAt: '2026-10-21T06:00:20Z', lastActivityAt: '2026-10-18T04:00:00Z', dueAt: '2026-10-21T04:00:00Z', nextAttemptAt: '2026-10-21T07:00:20Z', detail: '历史已清理，文件等待回收', turnsRemoved: 6, objectsRemoved: 2, objectsPending: 1, taskDeleted: true })
export const records = (): RetentionRecords => ({ items: [row()], total: 1, page: 1, pageSize: 20 })
