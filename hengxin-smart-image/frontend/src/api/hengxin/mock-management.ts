import { validateSettings } from './settings-validation'
import type { DemoState } from './demo-state'
import type { ManagementScenario, ManagementService, ManagedSettings, ManagedUser } from '../../types/management'
import type { SystemConfig, User } from '../../types/hengxin'
import { ApiError } from './http'

export function createMockManagement(getUser: () => User | Promise<User>, options: { snapshot?: DemoState; capture?: (state: Partial<DemoState>) => void; scenario?: ManagementScenario; wait?: () => Promise<void>; onSettingsChanged?: (config: SystemConfig) => void; onUserChanged?: (user: User) => void } = {}): ManagementService & { snapshot: () => Partial<DemoState> } {
  const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T
  const scenario = options.scenario ?? 'default'
  const failures = new Set<string>()
  const assignments = new Map<string, Pick<User, 'role' | 'status'>>()
  async function check(admin = false, operation = 'list') {
    await options.wait?.()
    const source = await getUser()
    const user = { ...source, ...assignments.get(source.id) }
    if (user.status !== 'active' || !user.role) throw new ApiError('UNAUTHORIZED', '账号未授权或已停用', 401)
    if (admin && user.role !== 'super_admin') throw new ApiError('FORBIDDEN', '仅超级管理员可执行此操作', 403)
    if (scenario === `${operation}-error` && !failures.has(operation)) { failures.add(operation); throw new ApiError('SIMULATED_FAILURE', '模拟请求失败，请重试', 503) }
    return user
  }
  const users: ManagedUser[] = options.snapshot?.users ? copy(options.snapshot.users).map(user => ({ ...user, identitySessionId: null })) : [
    { id: 'mock-operator', name: '模拟运营', identitySessionId: null, role: 'operator', status: 'active', department: '运营部', lastLoginAt: new Date().toISOString() },
    { id: 'mock-design-manager', name: '模拟主管', identitySessionId: null, role: 'design_manager', status: 'active', department: '设计部', lastLoginAt: null },
    { id: 'mock-designer', name: '模拟设计', identitySessionId: null, role: 'designer', status: 'active', department: '设计部', lastLoginAt: null },
    { id: 'mock-super-admin', name: '模拟超管', identitySessionId: null, role: 'super_admin', status: 'active', department: '管理部', lastLoginAt: null },
    { id: 'mock-pending', name: '新成员', identitySessionId: null, role: null, status: 'pending', department: '运营部', lastLoginAt: null }
  ]
  let settings: ManagedSettings = options.snapshot?.settings ? copy(options.snapshot.settings) : { version: 1, capacity: 10, timeoutCapacity: 3600, concurrency: 1, timeoutSeconds: 600, maxUploadBytes: 10 * 1024 * 1024,
    dingtalk: { corpId: '', appId: '', callbackDomain: '', state: 'unconfigured' }, audit: [] }
  options.snapshot?.users?.forEach(user => assignments.set(user.id, { role: user.role, status: user.status }))
  options.onSettingsChanged?.(copy(settings))
  const capture = () => options.capture?.({ users: copy(users), settings: copy(settings) })
  capture()
  const service: ManagementService & { snapshot: () => Partial<DemoState> } = {
    async listApplications(query) { await check(true); return { items: [], total: 0, page: query.page, pageSize: query.pageSize } },
    async decideApplication() { await check(true, 'save'); throw new ApiError('NOT_FOUND', '预览中暂无主动加入申请', 404) },
    async listUsers(query) {
      await check(true)
      if (!Number.isInteger(query.page) || query.page < 1 || !Number.isInteger(query.pageSize) || query.pageSize < 1 || query.pageSize > 100) throw new ApiError('VALIDATION', '分页参数无效', 422)
      const items = scenario === 'empty' ? [] : users.filter(u => (query.directory === 'legacy' ? u.status === 'pending' : u.status !== 'pending') && (!query.search || `${u.name}${u.department}`.includes(query.search.trim())) && (!query.role || u.role === query.role) && (!query.status || u.status === query.status))
      return { items: copy(items.slice((query.page - 1) * query.pageSize, query.page * query.pageSize)), page: query.page, pageSize: query.pageSize, total: items.length }
    },
    async saveUser(input) {
      const current = await check(true, 'save')
      const user = users.find(u => u.id === input.id)
      if (!user) throw new ApiError('NOT_FOUND', '用户不存在', 404)
      if (!['pending', 'active', 'disabled'].includes(input.status) || (input.role !== null && !['super_admin', 'design_manager', 'designer', 'operator'].includes(input.role)) || (input.status === 'active' && !input.role) || (input.status === 'pending' && input.role)) throw new ApiError('VALIDATION', '角色与账号状态不匹配', 422)
      if ((input.id === current.id || (user.role === 'super_admin' && user.status === 'active' && users.filter(u => u.role === 'super_admin' && u.status === 'active').length === 1)) && (input.role !== 'super_admin' || input.status !== 'active')) throw new ApiError('CONFLICT', '不能停用或降权当前/最后一位超级管理员', 409)
      assignments.set(user.id, { role: input.role, status: input.status })
      Object.assign(user, { role: input.role, status: input.status }); options.onUserChanged?.(copy(user)); capture(); return copy(user)
    },
    snapshot: () => ({ users: copy(users), settings: copy(settings) }),
    async getSettings() { await check(true); return copy(settings) },
    async saveSettings(input) {
      const user = await check(true, 'save')
      if (input.version !== settings.version) throw new ApiError('CONFLICT', '配置版本已变化，请刷新后重试', 409)
      validateSettings(input, settings)
      const fields = (['concurrency', 'timeoutSeconds', 'maxUploadBytes', 'dingtalk'] as const).filter(key => JSON.stringify(input[key]) !== JSON.stringify(key === 'dingtalk' ? { corpId: settings.dingtalk.corpId, appId: settings.dingtalk.appId, callbackDomain: settings.dingtalk.callbackDomain } : settings[key]))
      settings = { ...copy(input), capacity: settings.capacity, timeoutCapacity: settings.timeoutCapacity, version: settings.version + 1, dingtalk: { ...settings.dingtalk }, audit: [{ id: crypto.randomUUID(), operatorId: user.id, operatorName: user.name, changedAt: new Date().toISOString(), version: settings.version + 1, fields }, ...settings.audit] }
      options.onSettingsChanged?.(copy(settings)); capture()
      return copy(settings)
    }
  }
  return service
}
