import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createMembersApi, isOverseasMember, type OverseasMember } from '../src/api/overseas/members'
import { createIdentityApi, IdentityError } from '../src/api/identity/auth'
const member: OverseasMember = { id: 'm/1', name: '成员', department: '海外', roles: ['designer'], status: 'active', version: 3, createdAt: '2026-10-12', updatedAt: '2026-10-12' }
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status })
test('成员查询编码筛选分页，PATCH只发送允许字段并使用海外会话保护头', async () => {
  let count = 0
  const api = createMembersApi(async (url, options) => {
    count++
    assert.equal(options?.credentials, 'include')
    if (options?.method === 'GET') {
      assert.equal(String(url), '/api/overseas/v1/members?search=%E6%B5%B7%E5%A4%96&status=active&role=designer&page=2&pageSize=20')
      return json({ items: [member], total: 21, page: 2, pageSize: 20 })
    }
    assert.equal(String(url), '/api/overseas/v1/members/m%2F1')
    assert.equal(options?.method, 'PATCH')
    assert.equal((options?.headers as Record<string, string>)['X-HX-Request'], '1')
    assert.deepEqual(JSON.parse(String(options?.body)), { roles: ['designer'], status: 'active', version: 3 })
    return json(member)
  })
  assert.equal((await api.list({ search: '海外', status: 'active', role: 'designer', page: 2, pageSize: 20 })).total, 21)
  await api.save({ ...member, roles: ['designer'] })
  assert.equal(count, 2)
})
test('版本冲突保留结构化detail；拒绝非法成员及分页响应', async () => {
  await assert.rejects(createMembersApi(async () => json({ detail: { code: 'version_conflict' } }, 409)).save(member), (error: unknown) => error instanceof IdentityError && error.status === 409 && (error.detail as { code: string }).code === 'version_conflict')
  for (const value of [{ ...member, roles: ['operator', 'designer'] }, { ...member, roles: [] }, { ...member, roles: ['admin'] }, { ...member, version: 0 }, { ...member, status: 'unknown' }]) assert.equal(isOverseasMember(value), false)
  await assert.rejects(createMembersApi(async () => json({ items: [member], total: -1, page: 1, pageSize: 20 })).list({ search: '', status: '', role: '', page: 1, pageSize: 20 }), /响应格式错误/)
})
test('正式海外身份必须提供服务端能力，不从角色推导管理权限', async () => {
  await assert.rejects(createIdentityApi(async () => json({ id: '1', name: '成员', status: 'active', roles: ['super_admin'] })).overseasMe(), /响应格式错误/)
  const value = await createIdentityApi(async () => json({ id: '1', name: '成员', status: 'active', identitySessionId: 'identity-1', roles: ['super_admin'], capabilities: [] })).overseasMe()
  assert.deepEqual(value.capabilities, [])
})

test('保存前拒绝多角色，启用角色不得为空', async () => {
  let calls = 0
  const api = createMembersApi(async () => { calls++; return json(member) })
  await assert.rejects(api.save({ ...member, roles: ['operator', 'designer'] }), /单角色/)
  await assert.rejects(api.save({ ...member, roles: [] }), /单角色/)
  assert.equal(calls, 0)
})
