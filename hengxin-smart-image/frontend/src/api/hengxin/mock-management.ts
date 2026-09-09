import type { ManagementScenario, ManagementService, ManagedSettings, ManagedSkill, ManagedUser, UsageAttempt } from '../../types/management'
import type { SkillVersion, SystemConfig, Task, User, Workspace } from '../../types/hengxin'
import { ApiError } from './http'
import { buildUsage, mockAttempts } from './mock-management-usage'
import { createSkillManagement, validateSettings } from './mock-management-skills'

export function createMockManagement(db: Workspace, skills: SkillVersion[], getUser: () => User | Promise<User>, options: { scenario?: ManagementScenario; wait?: () => Promise<void>; installMs?: number; attempts?: UsageAttempt[]; getAttempts?: () => UsageAttempt[]; getHistoricalTasks?: () => Task[]; onSettingsChanged?: (config: SystemConfig) => void; onUserChanged?: (user: User) => void } = {}): ManagementService {
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
  const users: ManagedUser[] = [
    { id: 'mock-operator', name: '模拟运营', role: 'operator', status: 'active', department: '运营部', lastLoginAt: new Date().toISOString() },
    { id: 'mock-design-manager', name: '模拟主管', role: 'design_manager', status: 'active', department: '设计部', lastLoginAt: null },
    { id: 'mock-designer', name: '模拟设计', role: 'designer', status: 'active', department: '设计部', lastLoginAt: null },
    { id: 'mock-super-admin', name: '模拟超管', role: 'super_admin', status: 'active', department: '管理部', lastLoginAt: null },
    { id: 'mock-pending', name: '新成员', role: null, status: 'pending', department: '运营部', lastLoginAt: null }
  ]
  let settings: ManagedSettings = { version: 1, concurrency: 1, timeoutSeconds: 600, maxUploadBytes: 10 * 1024 * 1024,
    defaultSkillIds: { wallpaper: skills.find(s => s.mode === 'wallpaper' && s.isDefault)?.id ?? null, product: skills.find(s => s.mode === 'product' && s.isDefault)?.id ?? null, text: skills.find(s => s.mode === 'text' && s.isDefault)?.id ?? null },
    dingtalk: { corpId: '', appId: '', callbackDomain: '', state: 'unconfigured' }, audit: [] }
  const skillService = createSkillManagement(db, skills, check, options)
  return {
    ...skillService,
    async getUsage(query) {
      const user = await check()
      const names = [...users, ...(users.some(u => u.id === user.id) ? [] : [{ ...user, department: '', lastLoginAt: null }])]
      return copy(buildUsage({ ...db, tasks: scenario === 'empty' ? [] : options.getHistoricalTasks?.() ?? db.tasks }, scenario === 'empty' ? [] : options.getAttempts?.() ?? options.attempts ?? mockAttempts(db, 'mock-operator'), user, query, names))
    },
    async getMonitor() {
      const user = await check()
      if (!['super_admin', 'design_manager'].includes(user.role!)) throw new ApiError('FORBIDDEN', '请在任务中心查看业务状态', 403)
      const tasks = scenario === 'idle' || scenario === 'empty' ? [] : db.tasks.filter(t => t.state !== '待查看')
      const incidents: Partial<Record<ManagementScenario, string>> = { 'worker-lost': 'Worker 心跳失联，请检查后台执行服务', 'auth-rejected': 'CLI 认证被拒绝，请由管理员检查服务端认证', 'rate-limited': '执行服务被限流，请稍后重试', timeout: '最近执行超时，已保留成功结果', unavailable: 'MinIO 当前不可达，请检查存储连接' }
      const issue = incidents[scenario] ? { code: scenario, message: incidents[scenario]! } : undefined
      const state = scenario === 'unknown' ? 'unknown' : issue ? 'unavailable' : tasks.some(t => t.state === '执行中') ? 'running' : 'idle'
      const checkedAt = state === 'unknown' ? null : new Date().toISOString()
      const queueSize = tasks.filter(t => t.state === '排队中').length
      const runningCount = tasks.filter(t => t.state === '执行中').length
      const latest = (taskId: string) => options.getAttempts?.().filter(attempt => attempt.taskId === taskId).sort((a,b) => b.startedAt.localeCompare(a.startedAt))[0]
      const recent = (options.getAttempts?.() ?? options.attempts ?? []).filter(attempt => attempt.finishedAt).sort((a,b) => b.finishedAt!.localeCompare(a.finishedAt!))[0]
      const resultNames = { running: '执行中', success: '成功', partial: '部分失败', failed: '失败', timeout: '超时' }
      return { checkedAt, state, issue, queueSize, runningCount, tasks: tasks.map(t => { const attempt = latest(t.id); return { taskId: t.id, name: t.name, operatorName: attempt?.operatorName ?? t.ownerId, state: t.state, sessionId: t.sessionId, elapsedSeconds: t.state === '执行中' && attempt ? Math.max(0, Math.floor((Date.now() - Date.parse(attempt.startedAt)) / 1000)) : null, error: t.error ?? null } }),
        detail: user.role !== 'super_admin' ? null : { workers: scenario === 'empty' ? [] : [{ id: '模拟 Worker', checkedAt: checkedAt ?? new Date(Date.now() - 3600000).toISOString(), state, queueSize, runningCount, concurrency: settings.concurrency }], cliVersion: state === 'unknown' ? null : '模拟 CLI', configured: state === 'unknown' ? null : state !== 'unavailable', lastResult: recent && scenario !== 'empty' ? recent.taskName + ' · ' + resultNames[recent.state] + ' · ' + recent.finishedAt : null, freeDiskBytes: null,
          dependencies: ['PostgreSQL', 'Redis', 'MinIO'].map(name => ({ name, state: state === 'unknown' ? 'unknown' : scenario === 'unavailable' && name === 'MinIO' ? 'unavailable' : 'available', message: scenario === 'unavailable' && name === 'MinIO' ? '模拟存储连接失败' : '模拟检查；未连接真实依赖' })) } }
    },
    async listUsers(query) {
      await check(true)
      if (!Number.isInteger(query.page) || query.page < 1 || !Number.isInteger(query.pageSize) || query.pageSize < 1 || query.pageSize > 100) throw new ApiError('VALIDATION', '分页参数无效', 422)
      const items = scenario === 'empty' ? [] : users.filter(u => (!query.search || `${u.name}${u.department}`.includes(query.search.trim())) && (!query.role || u.role === query.role) && (!query.status || u.status === query.status))
      return { items: copy(items.slice((query.page - 1) * query.pageSize, query.page * query.pageSize)), page: query.page, pageSize: query.pageSize, total: items.length }
    },
    async saveUser(input) {
      const current = await check(true, 'save')
      const user = users.find(u => u.id === input.id)
      if (!user) throw new ApiError('NOT_FOUND', '用户不存在', 404)
      if (!['pending', 'active', 'disabled'].includes(input.status) || (input.role !== null && !['super_admin', 'design_manager', 'designer', 'operator'].includes(input.role)) || (input.status === 'active' && !input.role) || (input.status === 'pending' && input.role)) throw new ApiError('VALIDATION', '角色与账号状态不匹配', 422)
      if ((input.id === current.id || (user.role === 'super_admin' && user.status === 'active' && users.filter(u => u.role === 'super_admin' && u.status === 'active').length === 1)) && (input.role !== 'super_admin' || input.status !== 'active')) throw new ApiError('CONFLICT', '不能停用或降权当前/最后一位超级管理员', 409)
      assignments.set(user.id, { role: input.role, status: input.status })
      Object.assign(user, { role: input.role, status: input.status }); options.onUserChanged?.(copy(user)); return copy(user)
    },
    async getSettings() { await check(true); return copy(settings) },
    async saveSettings(input) {
      const user = await check(true, 'save')
      if (input.version !== settings.version) throw new ApiError('CONFLICT', '配置版本已变化，请刷新后重试', 409)
      validateSettings(input, skills)
      const fields = (['concurrency', 'timeoutSeconds', 'maxUploadBytes', 'defaultSkillIds', 'dingtalk'] as const).filter(key => JSON.stringify(input[key]) !== JSON.stringify(key === 'dingtalk' ? { corpId: settings.dingtalk.corpId, appId: settings.dingtalk.appId, callbackDomain: settings.dingtalk.callbackDomain } : settings[key]))
      settings = { ...copy(input), version: settings.version + 1, dingtalk: { ...input.dingtalk, state: 'unconfigured' }, audit: [{ id: crypto.randomUUID(), operatorId: user.id, operatorName: user.name, changedAt: new Date().toISOString(), version: settings.version + 1, fields }, ...settings.audit] }
      skills.forEach(s => { s.isDefault = settings.defaultSkillIds[s.mode] === s.id })
      options.onSettingsChanged?.(copy(settings))
      return copy(settings)
    }
  }
}
