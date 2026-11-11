import test, { type TestContext } from 'node:test'
import assert from 'node:assert/strict'
import { copyText } from '../src/utils/clipboard'

function replace(t: TestContext, name: string, value: unknown) {
  const original = Object.getOwnPropertyDescriptor(globalThis, name)
  Object.defineProperty(globalThis, name, { configurable: true, value })
  t.after(() => { if (original) Object.defineProperty(globalThis, name, original); else Reflect.deleteProperty(globalThis, name) })
}

test('可用时优先异步剪贴板并保留原文', async t => {
  const values: string[] = []
  replace(t, 'navigator', { clipboard: { writeText: async (value: string) => { values.push(value) } } })
  await copyText('授权码\nABCD-1234')
  assert.deepEqual(values, ['授权码\nABCD-1234'])
})

test('HTTP 无剪贴板 API 时使用用户手势复制，成功和失败均清理临时节点并恢复焦点', async t => {
  replace(t, 'navigator', {})
  let succeeds = true, selected = 0, removed = 0, focused = 0, appended = 0
  const field = { value: '', readOnly: false, style: { cssText: '' }, select() { selected++ }, remove() { removed++ } }
  replace(t, 'document', {
    activeElement: { focus() { focused++ } }, getSelection: () => null,
    createElement(tag: string) { assert.equal(tag, 'textarea'); return field },
    body: { appendChild(value: unknown) { assert.equal(value, field); appended++ } },
    execCommand(command: string) { assert.equal(command, 'copy'); assert.equal(selected, appended); return succeeds }
  })
  await copyText('原始\n代码')
  assert.equal(field.value, '原始\n代码'); assert.equal(field.readOnly, true)
  succeeds = false
  await assert.rejects(copyText('授权码'), /复制失败/)
  assert.equal(appended, 2); assert.equal(removed, 2); assert.equal(focused, 2)
})
