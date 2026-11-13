import test from 'node:test'
import assert from 'node:assert/strict'
import type { TurnInput } from '../src/api/shared/studio'
import { fixture, flush } from './studio-sessions-fixture'

test('国内每轮选择独立：成功后清空，下一轮不沿用，未绑定仍能发送', async () => {
  const f = fixture(), bodies: TurnInput[] = []
  const originalGet = f.api.get
  f.api.get = async (...args) => ({ ...await originalGet(...args), fixedSkillReady: false, materials: [] })
  f.api.send = async (_task, body) => { bodies.push(JSON.parse(JSON.stringify(body)) as TurnInput); return { ...f.snapshot(body.conversationId), fixedSkillReady: false, materials: [] } }
  const view = f.mount('domestic-user')
  try {
    await flush()
    assert.equal(view.state.skill.value, '')
    view.state.text.value = '按技能替换产品'; view.state.skill.value = 's'
    await view.state.send(); await flush()
    assert.equal(bodies[0].skillId, 's')
    assert.equal(view.state.skill.value, '')
    view.state.text.value = '上一张产品缩小一点'
    await view.state.send(); await flush()
    assert.equal(bodies[1].skillId, null)
    view.state.data.value = { ...view.state.data.value!, skills: [], fixedSkillReady: false }
    view.state.text.value = '继续调整阴影'
    assert.equal(view.state.canSend.value, true)
    await view.state.send(); await flush()
    assert.equal(bodies[2].skillId, null)
  } finally { view.close() }
})

test('未知发送保留原选择和请求，核实成功后才清空', async () => {
  const f = fixture(), calls: { body: TurnInput; key: string }[] = []
  f.api.send = async (_task, body, key) => {
    calls.push({ body: JSON.parse(JSON.stringify(body)) as TurnInput, key })
    if (calls.length === 1) throw Error('网络中断')
    return f.snapshot(body.conversationId)
  }
  const view = f.mount('domestic-user')
  try {
    await flush(); view.state.text.value = '替换产品'; view.state.skill.value = 's'
    await view.state.send(); await flush()
    assert.equal(view.state.skill.value, 's')
    assert.equal(view.state.pending.value?.kind, 'send')
    await view.state.retry(); await flush()
    assert.deepEqual(calls[1], calls[0])
    assert.equal(view.state.skill.value, '')
    assert.equal(view.state.pending.value, undefined)
  } finally { view.close() }
})

test('会话切换保留各自选择，失效选择阻止误发且可取消', async () => {
  const f = fixture(), view = f.mount('domestic-user')
  try {
    await flush(); view.state.text.value = '会话A草稿'; view.state.skill.value = 's'
    await view.state.selectSession('b'); await flush()
    assert.equal(view.state.skill.value, '')
    view.state.text.value = '会话B普通修改'
    await view.state.selectSession('a'); await flush()
    assert.equal(view.state.skill.value, 's')
    assert.equal(view.state.text.value, '会话A草稿')
    view.state.data.value = { ...view.state.data.value!, skills: [], fixedSkillReady: false }
    assert.equal(view.state.canSend.value, false)
    assert.ok(view.state.skillError.value)
    view.state.skill.value = ''
    assert.equal(view.state.canSend.value, true)
  } finally { view.close() }
})

