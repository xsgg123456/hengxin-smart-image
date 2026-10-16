import type { PageQuery, PageResult, Role, SystemConfig, User } from './hengxin'
import type { ApplicationsAdapter } from '../api/identity/applications'

export type ManagementScenario = 'default' | 'empty' | 'unknown' | 'idle' | 'unavailable' | 'list-error' | 'save-error' | 'worker-lost' | 'auth-rejected' | 'rate-limited' | 'timeout'
export interface ManagedUser extends User { department: string; lastLoginAt: string | null; directoryState?: 'enrolled' | 'legacy_unconfirmed' }
export interface UserQuery extends PageQuery { status?: User['status']; role?: Role; directory?: 'members' | 'legacy' }
export interface UserInput { id: string; role: Role | null; status: User['status'] }
export interface SettingsAudit { id: string; operatorId: string; operatorName: string; changedAt: string; version: number; fields: string[] }
export interface DingTalkConfig { corpId: string; appId: string; callbackDomain: string; state: 'unconfigured' | 'ready' | 'error' }
export interface ManagedSettings extends SystemConfig { capacity: number; timeoutCapacity: number; dingtalk: DingTalkConfig; audit: SettingsAudit[] }
export interface SettingsInput extends SystemConfig { dingtalk: Pick<DingTalkConfig, 'corpId' | 'appId' | 'callbackDomain'> }
export interface ManagementService extends ApplicationsAdapter {
  listUsers(query: UserQuery): Promise<PageResult<ManagedUser>>
  saveUser(input: UserInput): Promise<ManagedUser>
  getSettings(): Promise<ManagedSettings>
  saveSettings(input: SettingsInput): Promise<ManagedSettings>
}
