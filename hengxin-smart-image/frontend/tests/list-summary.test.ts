import { test } from 'node:test'
import assert from 'node:assert/strict'
import { page, task } from '../src/api/api-image-edits-validate'
import { createBootstrapUserHandoff } from '../src/api/hengxin/bootstrap-user'
import { identity } from '../src/api/hengxin/identity'

test('列表只接受完整摘要，详情继续要求完整历史契约', () => {
  const summary = { id: 'one', name: '任务', created: '2026-01-01', status: 'running', operator: '操作人',
    cover: { fileId: 'image', name: '原图', url: '/image' },
    counts: { total: 4, success: 1, failed: 1, uncertain: 1 }, batch: { total: 1, current: 1, running: 1 } }
  const wrap = (item: unknown) => ({ items: [item], total: 1, page: 1, pageSize: 20 })
  assert.equal(page(wrap(summary)), true)
  assert.equal(task(summary), false)
  assert.equal(page(wrap({ ...summary, counts: { ...summary.counts, success: 5 } })), false)
  assert.equal(page(wrap({ ...summary, cover: {} })), false)
  assert.equal(page(wrap({ ...summary, counts: undefined })), false)
})

test('启动身份仅复用一次，清理和代次变化均不能再复用', () => {
  const handoff = createBootstrapUserHandoff<{ id: string }>()
  handoff.offer({ id: 'a' })
  assert.deepEqual(handoff.take(), { id: 'a' })
  assert.equal(handoff.take(), undefined)
  handoff.offer({ id: 'a' }); handoff.clear()
  assert.equal(handoff.take(), undefined)
  handoff.offer({ id: 'a' }); identity.advance('suspended')
  assert.equal(handoff.take(), undefined)
})
