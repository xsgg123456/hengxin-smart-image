import type { ApiUsageReport, ApiUsageSummary } from '../src/types/api-management-usage'
export const summary: ApiUsageSummary = { initialImages: 10, modifiedImages: 3, totalGeneratedImages: 13, generatedTasks: 1, tasksCreated: 1, apiAttempts: 5, apiSucceeded: 1, apiFailed: 1, apiUnknown: 2, apiRunning: 1, apiRetries: 1, apiRetryUnknown: 2, cliSubmitted: 3, cliStarted: 2, cliUnverified: 1, cliSucceeded: 1, cliFailed: 0, cliUnknown: 1, cliCandidates: 1, generatedVersions: 1, unverifiedVersions: 2, adoptions: 1, restores: 2, unverifiedAttribution: 3, requestSuccessRate: .5, inputTokens: null, outputTokens: null, cost: null }
export function usageFixture(): ApiUsageReport {
  return { scope: 'all', timezone: 'Asia/Shanghai', users: [{ id: 'u1', name: '测试人员' }],
    inventory: { tasks: 4, sourceImages: 40, withResultImages: 35, succeededImages: 30, failedImages: 5, pendingImages: 3, uncertainImages: 2, deliverySuccessRate: 30 / 35 },
    summary: { ...summary }, rows: Array.from({ length: 10 }, (_, i) => ({ date: `2026-10-${String(i + 1).padStart(2, '0')}`, userId: 'u1', userName: '测试人员', summary: { ...summary } })),
    events: [{ generationType: 'cli_edit', generatedImages: 0, id: 'event1', category: 'cli_round', channel: 'cli', kind: 'legacy_unknown', taskId: 't1', taskName: '保留的历史任务', taskDeleted: true, creatorId: 'owner', operatorId: null, operatorName: '历史人员', occurredAt: '2026-10-10T00:00:00Z', completedAt: null, state: 'unknown', quantity: 1, isRetry: null, attribution: 'historical_unverified', durationSeconds: null }], total: 25, page: 1, pageSize: 20 }
}
