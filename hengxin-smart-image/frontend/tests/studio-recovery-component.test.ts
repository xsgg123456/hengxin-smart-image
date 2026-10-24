import test from 'node:test'
import assert from 'node:assert/strict'
import { reactive } from 'vue'
import { IdentityError } from '../src/api/identity/request'
import { formatAttachmentSize } from '../src/api/overseas/attachment-download'
import type { createStudioOutputsApi, RecoverableFiles, RecoveryResult } from '../src/api/overseas/studio-outputs'
import { useStudioRecovery } from '../src/views/overseas/studio/use-studio-recovery'
import { all, click, compile, flush, mount, simple, text } from './membership-test-harness'

const files = ['a', 'b'].map(id => ({ id, version: 'v1', name: `${id}.zip`, path: `${id}.zip`, source: 'work' as const, sizeBytes: id === 'a' ? 0 : 500_000_000 }))
type Api = ReturnType<typeof createStudioOutputsApi>
function setup(api: Api, overrides = {}) {
  const props = reactive({ taskId: 'task', conversationId: 'one', readonly: false, busy: false, ...overrides })
  let saves = 0; const failures: unknown[] = []
  const component = compile('views/overseas/studio/StudioRecoveryDialog.vue', {
    '@/api/overseas/attachment-download': { formatAttachmentSize },
    './use-studio-recovery': { useStudioRecovery: (context: Parameters<typeof useStudioRecovery>[0]) => useStudioRecovery(context, () => saves++, reason => failures.push(reason), api) }
  })
  Object.assign(component, { components: { ElCheckbox: simple('ElCheckbox') } })
  const view = mount(component, props)
  const checks = () => all(view.root).filter(item => item.tag === 'ElCheckbox')
  return { ...view, props, saves: () => saves, failures, checks, select: (index: number) => (checks()[index].props.onChange as (value: boolean) => void)(true) }
}
test('真实取回对话框部分成功后只保留失败项，再次点击按原版本重试', async () => {
  const requests: { id: string; version: string }[][] = []
  const view = setup({ list: async () => ({ items: files, busy: false }), recover: async (_task, _conversation, selected) => {
    requests.push(selected)
    return requests.length === 1 ? { saved: [{ id: 'saved-output', kind: 'file' }], errors: [{ id: 'b', name: 'b.zip', message: '上传超时，请重试' }] } : { saved: [{ id: 'saved-again', kind: 'file' }], errors: [] }
  } })
  try {
    await flush(); assert.match(text(view.root), /0 B/); assert.match(text(view.root), /500.0 MB/)
    view.select(0); view.select(1); await flush(); click(view.root, '取回所选文件'); await flush()
    assert.match(text(view.root), /b.zip：上传超时/); assert.equal(view.saves(), 1)
    assert.equal(view.checks()[0].props['model-value'], false); assert.equal(view.checks()[1].props['model-value'], true)
    click(view.root, '重试所选文件'); await flush()
    assert.deepEqual(requests[1], [{ id: 'b', version: 'v1' }]); assert.equal(view.saves(), 2)
    assert.equal(view.checks()[1].props['model-value'], false)
  } finally { view.close() }
})
test('列表错误具体可重试，空态与完成只读、当前会话busy均明确展示', async () => {
  let attempts = 0, recoveries = 0
  const view = setup({ list: async () => { if (++attempts === 1) throw new IdentityError(503, '服务暂不可用', '工作文件目录暂不可用'); return { items: [], busy: false } }, recover: async () => { recoveries++; return { saved: [], errors: [] } } })
  try {
    await flush(); assert.equal(all(view.root).find(item => item.tag === 'ElAlert')?.props.title, '工作文件目录暂不可用')
    click(view.root, '刷新列表'); await flush(); assert.match(text(view.root), /没有可取回的文件/)
    assert.equal(recoveries, 0)
  } finally { view.close() }
  for (const overrides of [{ readonly: true }, { busy: true }]) {
    const readonly = setup({ list: async () => ({ items: files, busy: false }), recover: async () => { recoveries++; return { saved: [], errors: [] } } }, overrides)
    try {
      await flush(); assert.equal(readonly.checks()[0].props.disabled, true); readonly.select(0); await flush()
      assert.equal(all(readonly.root).find(item => item.tag === 'ElButton' && text(item) === '取回所选文件')?.props.disabled, true)
      assert.equal(recoveries, 0)
    } finally { readonly.close() }
  }
})
test('请求超时保留勾选，重复点击不重复请求，切会话不接收旧保存结果', async () => {
  let resolve!: (value: RecoveryResult) => void, calls = 0
  const view = setup({ list: async () => ({ items: files, busy: false }), recover: async () => { calls++; if (calls === 1) throw Error('连接中断，请重试'); return new Promise(done => { resolve = done }) } })
  try {
    await flush(); view.select(0); await flush(); click(view.root, '取回所选文件'); await flush()
    assert.equal(view.checks()[0].props['model-value'], true)
    click(view.root, '取回所选文件'); click(view.root, '取回所选文件'); await flush(); assert.equal(calls, 2)
    view.props.conversationId = 'two'; await flush()
    resolve({ saved: [{ id: 'old-output', kind: 'file' }], errors: [] }); await flush()
    assert.equal(view.saves(), 0); assert.equal(view.checks()[0].props['model-value'], false)
  } finally { view.close() }
})
test('切换会话和卸载会中断旧列表，迟到响应不串入新列表', async () => {
  let resolve!: (value: RecoverableFiles) => void, oldSignal: AbortSignal | undefined
  const view = setup({ list: async (_task, conversation, signal) => { if (conversation === 'one') { oldSignal = signal; return new Promise(done => { resolve = done }) }; return { items: [files[1]], busy: false } }, recover: async () => ({ saved: [], errors: [] }) })
  try {
    view.props.conversationId = 'two'; await flush(); assert.equal(oldSignal?.aborted, true)
    resolve({ items: [files[0]], busy: false }); await flush()
    assert.doesNotMatch(text(view.root), /a.zip/); assert.match(text(view.root), /b.zip/)
  } finally { view.close() }
})

test('服务端忙碌禁用取回，刷新解锁后最多选择100项', async () => {
  let busy = true, count = 0
  const many = Array.from({ length: 101 }, (_, index) => ({ ...files[0], id: String(index), name: `${index}.zip` }))
  const view = setup({ list: async () => ({ items: many, busy }), recover: async (_task, _conversation, selected) => { count = selected.length; return { saved: [], errors: selected.map(file => ({ id: file.id, name: file.id, message: '尚未保存' })) } } })
  try {
    await flush(); assert.equal(view.checks()[0].props.disabled, true)
    busy = false; click(view.root, '刷新列表'); await flush()
    for (let index = 0; index < many.length; index++) view.select(index)
    await flush(); assert.equal(view.checks()[100].props.disabled, true)
    click(view.root, '取回所选文件'); await flush(); assert.equal(count, 100)
  } finally { view.close() }
})
