import assert from 'node:assert/strict'
import test from 'node:test'
import { createDraft } from '../src/views/hengxin/api-image-edits/real-draft'
import { identity } from '../src/api/hengxin/identity'

test('API解码期间身份失效阻断上传，正常会话仍可上传', async () => {
  for (const reason of ['changed', 'suspended', 'none'] as const) {
    let decoded!: () => void, calls = 0
    const draft = createDraft({
      upload: async raw => { calls++; return { fileId: 'saved', name: raw.name, url: '/saved' } },
      deleteFile: async () => {}, create: async () => ({ taskId: 'unused' })
    }, () => new Promise(resolve => { decoded = resolve }), { createObjectURL: () => 'blob:test', revokeObjectURL() {} } as typeof URL)
    draft.add(new File(['image'], 'A.png', { type: 'image/png' }))
    if (reason !== 'none') identity.advance(reason)
    decoded(); await new Promise(resolve => setImmediate(resolve))
    assert.equal(calls, reason === 'none' ? 1 : 0)
    assert.equal(draft.state.images[0].state, reason === 'none' ? 'ready' : 'failed')
  }
})
