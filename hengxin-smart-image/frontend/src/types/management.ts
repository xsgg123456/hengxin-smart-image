import type { Mode, PageQuery, PageResult, Role, SkillVersion, SystemConfig, User, WorkerStatus } from './hengxin'

export type ManagementScenario = 'default' | 'empty' | 'unknown' | 'idle' | 'unavailable' | 'list-error' | 'save-error' | 'install-error' | 'worker-lost' | 'auth-rejected' | 'rate-limited' | 'timeout'
export interface UsageQuery { from?: string; to?: string; userId?: string; mode?: Mode }
export interface UsageAttempt {
  id: string; taskId: string; taskName: string; creatorId: string; operatorId: string; operatorName: string
  mode: Mode; kind: 'initial' | 'single' | 'whole'; startedAt: string; finishedAt: string | null
  state: 'running' | 'success' | 'partial' | 'failed' | 'timeout'; outputImages: number
  queueSeconds: number; durationSeconds: number | null; usage: { inputTokens: number; outputTokens: number } | null
}
export interface UsageSummary {
  tasks: number; attempts: number; initial: number; single: number; whole: number; running: number
  success: number; partial: number; failed: number; timeout: number; outputImages: number
  successRate: number | null; inputTokens: number | null; outputTokens: number | null
  averageQueueSeconds: number | null; averageDurationSeconds: number | null
}
export interface UsageRow { date: string; userId: string; userName: string; summary: UsageSummary; details: UsageAttempt[] }
export interface UsageReport { scope: 'personal' | 'all'; timezone: 'Asia/Shanghai'; summary: UsageSummary; rows: UsageRow[]; users: { id: string; name: string }[] }
export interface MonitorTask { taskId: string; name: string; operatorName: string; state: string; sessionId: string | null; elapsedSeconds: number | null; error: string | null }
export interface MonitorReport {
  issue?: { code: string; message: string }
  checkedAt: string | null; state: WorkerStatus['state']; queueSize: number; runningCount: number; tasks: MonitorTask[]
  detail: null | { workers: WorkerStatus[]; cliVersion: string | null; configured: boolean | null; lastResult: string | null; dependencies: { name: string; state: 'available' | 'unavailable' | 'unknown'; message: string }[]; freeDiskBytes: number | null }
}
export interface ManagedUser extends User { department: string; lastLoginAt: string | null }
export interface UserQuery extends PageQuery { status?: User['status']; role?: Role }
export interface UserInput { id: string; role: Role | null; status: User['status'] }
export interface ManagedSkill extends SkillVersion { installedAt: string | null; node: string | null; updatedAt: string; error: string | null; referenced: boolean }
export interface SettingsAudit { id: string; operatorId: string; operatorName: string; changedAt: string; version: number; fields: string[] }
export interface DingTalkConfig { corpId: string; appId: string; callbackDomain: string; state: 'unconfigured' | 'ready' | 'error' }
export interface ManagedSettings extends SystemConfig { dingtalk: DingTalkConfig; audit: SettingsAudit[] }
export interface SettingsInput extends SystemConfig { dingtalk: Pick<DingTalkConfig, 'corpId' | 'appId' | 'callbackDomain'> }
export interface ManagementService {
  getUsage(query: UsageQuery): Promise<UsageReport>
  getMonitor(): Promise<MonitorReport>
  listUsers(query: UserQuery): Promise<PageResult<ManagedUser>>
  saveUser(input: UserInput): Promise<ManagedUser>
  listManagedSkills(): Promise<ManagedSkill[]>
  getSkillDefaults(): Promise<SystemConfig['defaultSkillIds']>
  saveSkillDefaults(input: SystemConfig['defaultSkillIds']): Promise<SystemConfig['defaultSkillIds']>
  uploadSkill(file: File, mode: Mode, version: string): Promise<ManagedSkill>
  installSkill(id: string): Promise<ManagedSkill>
  setSkillStatus(id: string, status: 'available' | 'disabled'): Promise<ManagedSkill>
  getSettings(): Promise<ManagedSettings>
  saveSettings(input: SettingsInput): Promise<ManagedSettings>
}
