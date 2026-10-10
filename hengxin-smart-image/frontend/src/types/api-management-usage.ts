export type GenerationType = 'initial' | 'api_edit' | 'cli_edit'
export type UsageCategory = 'task_created' | 'api_request' | 'cli_submission' | 'cli_round' | 'cli_candidate' | 'version_published' | 'adopt' | 'restore'
export interface ApiUsageQuery { from?: string; to?: string; userId?: string; unassigned?: boolean; category?: UsageCategory; generationType?: GenerationType; outputsOnly?: boolean; page?: number; pageSize?: number }
export interface ApiUsageSummary {
  initialImages: number; modifiedImages: number; totalGeneratedImages: number; generatedTasks: number
  tasksCreated: number; apiAttempts: number; apiSucceeded: number; apiFailed: number; apiUnknown: number; apiRunning: number; apiRetries: number; apiRetryUnknown: number
  cliSubmitted: number; cliStarted: number; cliUnverified: number; cliSucceeded: number; cliFailed: number; cliUnknown: number
  cliCandidates: number; generatedVersions: number; unverifiedVersions: number; adoptions: number; restores: number; unverifiedAttribution: number
  requestSuccessRate: number | null; inputTokens: null; outputTokens: null; cost: null
}
export interface ApiUsageInventory {
  tasks: number; sourceImages: number; withResultImages: number; succeededImages: number; failedImages: number; pendingImages: number; uncertainImages: number; deliverySuccessRate: number | null
}
export interface ApiUsageEvent {
  generationType: GenerationType | null; generatedImages: number; id: string; category: UsageCategory; channel: string; kind: string; taskId: string; taskName: string; taskDeleted: boolean
  creatorId: string; operatorId: string | null; operatorName: string; occurredAt: string; completedAt: string | null; state: string; quantity: number
  isRetry: boolean | null; attribution: 'verified' | 'historical_unverified'; durationSeconds: number | null
}
export interface ApiUsageRow { date: string; userId: string | null; userName: string; summary: ApiUsageSummary }
export interface ApiUsageReport {
  scope: 'all' | 'personal'; timezone: 'Asia/Shanghai'; users: { id: string; name: string }[]
  inventory: ApiUsageInventory; summary: ApiUsageSummary; rows: ApiUsageRow[]; events: ApiUsageEvent[]; total: number; page: number; pageSize: number
}
