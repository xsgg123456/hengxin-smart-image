import test from 'node:test'
import assert from 'node:assert/strict'
import { compile, mount, all, text, find, update, flush, click, table, simple } from './membership-test-harness'
import { memberRoles, type MembersAdapter, type MemberQuery } from '../src/api/overseas/members'
import { IdentityError } from '../src/api/identity/auth'
import { ApiError } from '../src/api/hengxin/http'
import type { UserQuery, UserInput } from '../src/types/management'
const ui = { ElMessage: { success() {} }, ElMessageBox: { confirm: async () => {}, close() {} } }
const application = { default: simple('Applications') }
const foreign = compile('views/overseas/admin/OverseasMembers.vue', {
  'element-plus': ui, '@/components/core/tables/art-table/index.vue': { default: table },
  '@/api/overseas/members': { memberRoles }, '@/api/identity/auth': { IdentityError }, '@/views/auth/MembershipApplications.vue': application
})
const member = { id: 'm1', name: '成员', department: '', roles: ['designer'] as ['designer'], status: 'active' as const, version: 1, createdAt: '', updatedAt: '' }
test('真实海外目录SFC：分页加载保留总数不弹回首页，历史只读，401清理数据', async () => {
  const queries: MemberQuery[] = [], failures: unknown[] = []
  let pending: Promise<void> | undefined, finish!: () => void, fail = false
  const adapter: MembersAdapter = {
    async list(q) { queries.push({ ...q }); await pending; if (fail) throw new IdentityError(401, '身份过期'); return { items: [{ ...member }], total: q.directory === 'legacy' ? 1 : 41, page: q.page, pageSize: q.pageSize } },
    async get() { return { ...member } }, async save(value) { return value }
  }
  const view = mount(foreign, { adapter, onFailure: (e: unknown) => failures.push(e) })
  try {
    await flush(); assert.ok(text(view.root).includes('共 41 位成员'))
    pending = new Promise(resolve => { finish = resolve }); (find(view.root, 'ElPagination').props.onCurrentChange as (v: number) => void)(2); await flush()
    assert.equal(find(view.root, 'ElPagination').props.total, 41); assert.equal(find(view.root, 'ElPagination').props['current-page'], 2); assert.deepEqual(find(view.root, 'ArtTable').props.data, [])
    finish(); pending = undefined; await flush(); assert.equal(queries.at(-1)?.page, 2)
    update(find(view.root, 'ElTabs'), 'legacy'); await flush()
    assert.equal(queries.at(-1)?.directory, 'legacy'); assert.ok(text(view.root).includes('共 1 条待核对记录')); assert.equal(all(view.root).filter(n => n.tag === 'ElButton' && text(n) === '编辑').length, 0)
    fail = true; click(view.root, '刷新成员'); await flush(); assert.deepEqual(find(view.root, 'ArtTable').props.data, []); assert.equal(failures.length, 1)
  } finally { finish?.(); view.close() }
})
test('真实国内目录SFC：成员/历史独立query与总数，普通编辑不授权legacy，403清敏感表单', async () => {
  const queries: UserQuery[] = [], writes: UserInput[] = []; let reject = false
  const user = { id: 'u1', name: '国内成员', identitySessionId: null, role: 'designer', status: 'active', department: '', lastLoginAt: null }
  const domestic = compile('views/hengxin/admin/users.vue', {
    'element-plus': ui, '@/components/core/tables/art-table/index.vue': { default: table },
    '@/api/management': { managementApi: {}, async listUsers(q: UserQuery) { queries.push(q); return { items: [user], total: q.directory === 'legacy' ? 3 : 30, page: q.page, pageSize: q.pageSize } }, async saveUser(input: UserInput) { if (reject) throw new ApiError('FORBIDDEN', '权限已移除', 403); writes.push(input); return user } },
    '@/api/hengxin/http': { ApiError }, '@/views/auth/MembershipApplications.vue': application, './AdminPreview.vue': { default: simple('Preview') }
  })
  const view = mount(domestic)
  try {
    await flush(); assert.equal(queries.at(-1)?.directory, 'members'); assert.ok(text(view.root).includes('共 30 位成员'))
    update(find(view.root, 'ElTabs'), 'legacy'); await flush(); assert.equal(queries.at(-1)?.directory, 'legacy'); assert.ok(text(view.root).includes('共 3 条待核对记录'))
    assert.equal(all(view.root).filter(n => n.tag === 'ElButton' && text(n) === '分配角色 / 状态').length, 0); assert.equal(writes.length, 0)
    update(find(view.root, 'ElTabs'), 'members'); await flush(); click(view.root, '分配角色 / 状态'); await flush(); reject = true; click(view.root, '保存授权'); await flush()
    assert.equal(find(view.root, 'ElDialog').props.modelValue, false); assert.deepEqual(find(view.root, 'ArtTable').props.data, []); assert.ok(text(view.root).includes('共 0 位成员'))
  } finally { view.close() }
})
