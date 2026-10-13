import test from 'node:test'
import assert from 'node:assert/strict'
import { reactive } from 'vue'
import { compile, mount, all, text, find, update, flush, click, table } from './membership-test-harness'
import { mayEnter } from '../src/api/identity/access'
import { applicationStatuses, type ApplicationsAdapter, type ApplicationDecision } from '../src/api/identity/applications'
import { IdentityError } from '../src/api/identity/auth'
const entry = compile('views/auth/BusinessEntry.vue', { '@/api/identity/access': { mayEnter } })
test('真实入口SFC区分明确申请、撤回、拒绝重申、停用和预览无权限', async () => {
  const props = reactive({ identity: { authenticated: true, domestic: false, overseas: false }, states: { domestic: { state: 'unregistered' }, overseas: { state: 'pending' } }, busy: false })
  const events: string[] = []
  const view = mount(entry, { ...props, states: props.states, onApply: (b: string) => events.push(`apply:${b}`), onWithdraw: (b: string) => events.push(`withdraw:${b}`) })
  try {
    click(view.root, '申请国内权限'); click(view.root, '撤回海外申请'); assert.deepEqual(events, ['apply:domestic', 'withdraw:overseas'])
    props.states.domestic.state = 'disabled'; props.states.overseas.state = 'rejected'; await flush()
    assert.ok(text(view.root).includes('已停用，请联系本业务管理员')); assert.ok(text(view.root).includes('重新申请海外权限'))
    assert.equal(all(view.root).filter(n => n.tag === 'ElButton' && text(n) === '申请国内权限').length, 0)
  } finally { view.close() }
  const preview = mount(entry, { identity: { authenticated: true, domestic: true, overseas: false } })
  assert.ok(text(preview.root).includes('暂无权限')); assert.equal(all(preview.root).filter(n => n.tag === 'ElButton' && text(n).includes('申请')).length, 0); preview.close()
})
const pending = { id: 'a1', name: '申请人', status: 'pending' as const, version: 4, createdAt: '2026-10-13', updatedAt: '2026-10-13' }
let confirm = true
const applications = compile('views/auth/MembershipApplications.vue', {
  'element-plus': { ElMessage: { success() {} }, ElMessageBox: { async confirm() { if (!confirm) throw new Error('cancel') }, close() {} } },
  '@/components/core/tables/art-table/index.vue': { default: table }, '@/api/identity/applications': { applicationStatuses }
})
test('真实申请SFC：合法角色必填、取消不写、拒绝原因必填、成功发送准确版本并刷新', async () => {
  const writes: ApplicationDecision[] = []; let status = 'pending', reads = 0
  const adapter: ApplicationsAdapter = {
    async listApplications(q) { reads++; return { items: status === 'pending' ? [{ ...pending }] : [], total: status === 'pending' ? 1 : 0, page: q.page, pageSize: q.pageSize } },
    async decideApplication(_id, input) { writes.push(input); status = 'rejected'; return { ...pending, status: 'rejected', version: 5 } }
  }
  const view = mount(applications, { adapter, roles: { designer: '设计' }, businessName: '海外' })
  try {
    await flush(); assert.ok(text(view.root).includes('共 1 条申请')); click(view.root, '审批申请'); await flush()
    click(view.root, '确认审批'); await flush(); assert.equal(find(view.root, 'ElAlert').props.title, '请选择本业务的有效角色'); assert.equal(writes.length, 0)
    update(find(view.root, 'ElSelect', '审批业务角色'), 'designer'); confirm = false; click(view.root, '确认审批'); await flush(); assert.equal(writes.length, 0)
    confirm = true; update(find(view.root, 'ElRadioGroup'), 'reject'); await flush(); click(view.root, '确认审批'); await flush(); assert.equal(find(view.root, 'ElAlert').props.title, '请填写拒绝原因')
    update(find(view.root, 'ElInput', '拒绝原因'), '  应向国内申请  '); click(view.root, '确认审批'); await flush()
    assert.deepEqual(writes, [{ decision: 'reject', reason: '应向国内申请', version: 4 }]); assert.equal(reads, 2); assert.ok(text(view.root).includes('共 0 条申请'))
  } finally { confirm = true; view.close() }
})
for (const status of [401, 403, 409, 503]) test(`真实申请SFC：${status}保留可恢复结果或清理敏感内容`, async () => {
  const failures: unknown[] = []; let writes = 0
  const adapter: ApplicationsAdapter = {
    async listApplications(q) { return { items: [{ ...pending }], total: 1, page: q.page, pageSize: q.pageSize } },
    async decideApplication() { writes++; throw new IdentityError(status, '审批失败') }
  }
  const view = mount(applications, { adapter, roles: { designer: '设计' }, businessName: '国内', onFailure: (e: unknown) => failures.push(e) })
  try {
    await flush(); click(view.root, '审批申请'); await flush(); update(find(view.root, 'ElSelect', '审批业务角色'), 'designer'); click(view.root, '确认审批'); await flush()
    assert.equal(writes, 1)
    if ([401, 403].includes(status)) { assert.equal(find(view.root, 'ElDialog').props.modelValue, false); assert.ok(text(view.root).includes('共 0 条申请')); assert.equal(failures.length, 1) }
    else if (status === 409) { click(view.root, '确认审批'); await flush(); assert.equal(writes, 1); click(view.root, '刷新最新申请'); await flush(); assert.equal(find(view.root, 'ElDialog').props.modelValue, false) }
    else { assert.equal(find(view.root, 'ElDialog').props.modelValue, true); assert.equal(find(view.root, 'ElAlert').props.title, '审批失败') }
  } finally { view.close() }
})
test('申请加载中可见，离开页面迟到响应不再接收', async () => {
  let done!: (value: { items: typeof pending[]; total: number; page: number; pageSize: number }) => void
  const adapter: ApplicationsAdapter = { listApplications: () => new Promise(resolve => { done = resolve }), decideApplication: async () => pending }
  const view = mount(applications, { adapter, roles: {}, businessName: '海外' }); await flush(); assert.equal(find(view.root, 'ArtTable').props.loading, true)
  view.close(); done({ items: [pending], total: 1, page: 1, pageSize: 20 }); await flush(); assert.equal(view.root.children.length, 0)
})
test('申请读取失败清旧结果显示错误，重试空列表按真实零申请显示', async () => {
  let fail = false, empty = false
  const adapter: ApplicationsAdapter = { async listApplications(q) { if (fail) throw new IdentityError(503, '读取失败'); return { items: empty ? [] : [pending], total: empty ? 0 : 1, page: q.page, pageSize: q.pageSize } }, decideApplication: async () => pending }
  const view = mount(applications, { adapter, roles: {}, businessName: '海外' })
  try {
    await flush(); assert.equal((find(view.root, 'ArtTable').props.data as unknown[]).length, 1)
    fail = true; click(view.root, '刷新申请'); await flush(); assert.deepEqual(find(view.root, 'ArtTable').props.data, []); assert.equal(find(view.root, 'ElAlert').props.title, '读取失败')
    fail = false; empty = true; click(view.root, '重试加载申请'); await flush(); assert.ok(text(view.root).includes('共 0 条申请')); assert.equal(all(view.root).filter(n => n.tag === 'ElAlert').length, 0)
  } finally { view.close() }
})
