export type GenerationKind = 'initial' | 'api_edit' | 'cli_edit'
export interface ActivityQuery { view: 'people' | 'jobs'; userId?: string; unassigned?: boolean; from?: string; to?: string; generationType?: GenerationKind; status?: string; keyword?: string; currentOnly?: boolean; page: number; pageSize: number }
export interface ActivitySummary { images: number | null; api: number; cli: number }
export interface ActivityPerson extends ActivitySummary { id: string | null; name: string; latest: string | null }
export interface ActivityRecord { id: string; taskId: string; task: string; personId: string | null; person: string; kind: GenerationKind | null; status: string; createdAt: string; startedAt: string | null; finishedAt: string | null; images: number | null; seconds: number | null; retry: boolean | null; error: string | null; taskDeleted: boolean; current: boolean }
export interface ActivityReport { scope: string; checkedAt: string; users: { id: string; name: string }[]; people: ActivityPerson[]; records: ActivityRecord[]; total: number; page: number; pageSize: number; summary: ActivitySummary; live: { queued: number; running: number; uncertain: number; failed: number } }
export const generationKinds = { initial: '首次生成', api_edit: 'API 修改', cli_edit: 'CLI 修改' }
export const activityStatuses: Record<string, string> = { queued: '排队中', running: '执行中', retry_wait: '等待重试', collecting: '收图中', cancelling: '取消中', uncertain: '待核实', failed: '失败', succeeded: '已完成', cancelled: '已取消', unknown: '历史状态未记录', waiting_user: '等待补充', candidate: '已产出候选', adopted: '已采用' }
