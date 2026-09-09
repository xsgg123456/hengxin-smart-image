import type { Role, User } from '../../types/hengxin'

export const previewRoles: { value: Role; label: string }[] = [
  { value: 'super_admin', label: '超级管理员' },
  { value: 'design_manager', label: '设计主管' },
  { value: 'designer', label: '设计' },
  { value: 'operator', label: '运营' }
]
export const loginScenarios = ['success', 'authorizing', 'denied', 'expired', 'pending', 'disabled', 'enterprise-mismatch', 'unavailable'] as const
export type LoginScenario = typeof loginScenarios[number]
export function getLoginScenario(search = globalThis.location?.search ?? ''): LoginScenario {
  const value = new URLSearchParams(search).get('auth')
  return loginScenarios.find(item => item === value) ?? 'success'
}
/** 仅由模拟服务消费；真实服务必须使用服务端身份。 */
export function getPreviewUser(search = globalThis.location?.search ?? ''): User {
  const value = new URLSearchParams(search).get('role')
  const role = previewRoles.find(item => item.value === value) ?? previewRoles[3]
  const scenario = getLoginScenario(search)
  return { id: `mock-${role.value.replaceAll('_', '-')}`, name: `模拟${role.label}`,
    role: scenario === 'pending' ? null : role.value,
    status: scenario === 'pending' ? 'pending' : scenario === 'disabled' ? 'disabled' : 'active' }
}
export function safeReturnPath(value: unknown): string {
  if (typeof value !== 'string' || !value.startsWith('/') || /[\\\r\n]/.test(value) || value.startsWith('//')) return '/image-processing/wallpaper'
  const path = value.split(/[?#]/)[0]
  return /^\/(image-processing\/(wallpaper|product|text)|(?:tasks|templates|archive)\/index|management\/(usage|monitor|users|skills|settings))$/.test(path)
    ? value : '/image-processing/wallpaper'
}
