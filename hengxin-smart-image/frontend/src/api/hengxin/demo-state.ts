import type { ManagedSettings, ManagedUser } from '../../types/management'
export interface DemoState {
  schema: 2
  users?: ManagedUser[]
  settings?: ManagedSettings
}
/** 丢弃退役业务快照，只保留仍在使用的身份与系统设置。 */
export function migrateDemoState(value: unknown): DemoState | undefined {
  if (!value || typeof value !== 'object') return undefined
  const old = value as Omit<DemoState, 'schema'> & { schema: number }
  if (old.schema !== 1 && old.schema !== 2) throw new Error('Demo 数据版本不兼容')
  const settings = old.settings && { ...old.settings }
  if (settings) Reflect.deleteProperty(settings, 'defaultSkillIds')
  return { schema: 2, users: old.users, settings }
}
