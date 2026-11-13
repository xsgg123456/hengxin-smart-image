import { IdentityError, record } from '../identity/request'

export interface Skill { id: string; name: string; displayName: string; description: string }
export interface ManagedSkill extends Skill { enabled: boolean; version: number; platforms: string[] }
export interface SkillCatalog { items: ManagedSkill[]; canToggle: boolean; canManagePlatforms: boolean }
export interface SkillPlatformUpdate { id: string; version: number; platforms: string[] }

export function isSkill(v: unknown): v is Skill {
  return record(v) && ['id', 'name', 'displayName', 'description'].every(k => typeof v[k] === 'string')
    && String(v.id).length > 0 && String(v.name).trim().length > 0 && String(v.displayName).trim().length > 0
}
export function isManagedSkill(v: unknown): v is ManagedSkill {
  return record(v) && isSkill(v) && typeof v.enabled === 'boolean' && Number.isInteger(v.version) && Number(v.version) > 0
    && Array.isArray(v.platforms) && v.platforms.every(p => typeof p === 'string')
}
export function isSkillCatalog(v: unknown): v is SkillCatalog {
  return record(v) && typeof v.canToggle === 'boolean' && typeof v.canManagePlatforms === 'boolean'
    && Array.isArray(v.items) && v.items.every(isManagedSkill)
}
export const managementError = (e: unknown) => e instanceof IdentityError && e.status === 409
  ? '记录已变化，请刷新最新版本；你的草稿已保留'
  : e instanceof IdentityError && e.status === 422 ? '配置不符合要求，请检查名称、指令内容及默认阶段绑定'
    : e instanceof Error ? e.message : '服务暂不可用，请重试'
