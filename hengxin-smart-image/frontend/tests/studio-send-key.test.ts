import test from 'node:test'
import assert from 'node:assert/strict'
import { handleStudioSendKey } from '../src/views/overseas/studio/studio-send-key'

function event(overrides: Partial<KeyboardEvent> = {}) {
  let prevented = false
  const value = { key: 'Enter', isComposing: false, keyCode: 13, shiftKey: false, altKey: false, ctrlKey: false, repeat: false, preventDefault() { prevented = true }, ...overrides } as KeyboardEvent
  return { value, prevented: () => prevented }
}
test('Enter和Ctrl+Enter调用同一个send，Shift/IME/229/其他键不误发，长按不重复', () => {
  for (const overrides of [{}, { ctrlKey: true }]) {
    const key = event(overrides); let sends = 0
    handleStudioSendKey(key.value, () => sends++)
    assert.equal(sends, 1); assert.equal(key.prevented(), true)
  }
  for (const overrides of [{ shiftKey: true }, { shiftKey: true, ctrlKey: true }, { isComposing: true }, { keyCode: 229 }, { altKey: true }, { key: 'a' }]) {
    const key = event(overrides); let sends = 0
    handleStudioSendKey(key.value, () => sends++)
    assert.equal(sends, 0); assert.equal(key.prevented(), false)
  }
  const held = event({ repeat: true }); let sends = 0
  handleStudioSendKey(held.value, () => sends++)
  assert.equal(sends, 0); assert.equal(held.prevented(), true)
})
