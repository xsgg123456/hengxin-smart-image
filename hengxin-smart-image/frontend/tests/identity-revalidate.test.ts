import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createOverseasRevalidator } from '../src/api/identity/revalidate'
import { IdentityError, type Member } from '../src/api/identity/auth'
const member: Member = { id: 'one', name: '成员', status: 'active', roles: ['operator'], capabilities: ['task.create'] }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r }); return { promise, resolve } }

test('focus和visible并发只核验一次；核验前不替换成员及页面状态', async () => {
  const wait = deferred<Member>(), state = { member, draft: '未保存内容', pending: false }
  let identities = 0, members = 0, accepted = 0
  const check = createOverseasRevalidator({
    identity: async () => { identities++; return { name: member.name } },
    member: () => { members++; return wait.promise },
    accept: current => { state.member = current; accepted++ }, reject: assert.fail,
    pending: value => { state.pending = value }
  })
  const first = check.run(), second = check.run()
  assert.equal(first, second); assert.equal(state.pending, true)
  assert.equal(state.member, member); assert.equal(state.draft, '未保存内容'); assert.equal(accepted, 0)
  wait.resolve({ ...member }); await first
  assert.equal(identities, 1); assert.equal(members, 1); assert.equal(accepted, 1)
  assert.equal(state.pending, false); assert.equal(state.draft, '未保存内容')
})
for (const status of [401,403,503]) test(`重验${status}拒绝旧身份且解除等待`, async () => {
  let accepted = false, rejected: unknown, pending = false
  const reason = new IdentityError(status, 'failed')
  const check = createOverseasRevalidator({ identity: async () => ({ name: member.name }), member: async () => { throw reason },
    accept: () => { accepted = true }, reject: error => { rejected = error }, pending: value => { pending = value } })
  await check.run(); assert.equal(accepted, false); assert.equal(rejected, reason); assert.equal(pending, false)
})
test('退出或切换后晚返回的重验不得恢复旧账号', async () => {
  const wait = deferred<Member>(); let accepted = false, pending = false
  const check = createOverseasRevalidator({ identity: async () => ({ name: member.name }), member: () => wait.promise,
    accept: () => { accepted = true }, reject: assert.fail, pending: value => { pending = value } })
  const run = check.run(); await Promise.resolve(); check.invalidate(); wait.resolve(member); await run
  assert.equal(accepted, false); assert.equal(pending, false)
})
test('真实换号和撤权返回服务端新身份，不复用旧权限', async () => {
  let current = member
  const changed = { ...member, id: 'two', roles: ['designer'], capabilities: ['task.read'] }
  const check = createOverseasRevalidator({ identity: async () => ({ name: changed.name }), member: async () => changed,
    accept: value => { current = value }, reject: assert.fail, pending: () => {} })
  await check.run(); assert.equal(current.id, 'two'); assert.deepEqual(current.capabilities, ['task.read'])
})
