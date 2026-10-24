import test from 'node:test'
import assert from 'node:assert/strict'
import { defineComponent, h, nextTick, reactive } from 'vue'
import { isStudio, type StudioTurn } from '../src/api/overseas/studio'
import { createStudioOutputsApi, isRecoverableFiles, isRecoveryResult, isStudioOutput } from '../src/api/overseas/studio-outputs'
import { formatAttachmentSize } from '../src/api/overseas/attachment-download'
import { all, compile, find, mount, simple, text } from './membership-test-harness'

const output = { id: 'f', name: '方案.zip', contentType: 'application/zip', sizeBytes: 0, url: '/api/overseas/v1/tasks/task/studio/outputs/f/content' }
const picture = { id: 'p', name: '效果.png', url: '/api/overseas/v1/tasks/task/studio/pictures/p/content', width: 20, height: 20, turnId: 'turn', sku: null, archived: false }
const turn: StudioTurn = { id: 'turn', text: '', skillName: null, status: 'succeeded', reply: '已回复', error: null, jobId: 'job', jobVersion: 1, attachments: [], pictures: [picture], outputs: [output], referencePictures: [], createdAt: '', deliveryStatus: { state: 'partial', saved: 2, expected: 3 } }
const outputComponent = compile('views/overseas/studio/StudioOutputs.vue', {
  '@/api/overseas/attachment-download': { formatAttachmentSize }, '../AttachmentDownload.vue': { default: simple('Download') }
})
test('普通输出契约接收0B和partial终态，只接受本任务同域输出路径', () => {
  const snapshot = { taskId: 'task', taskVersion: 1, completed: false, archiveId: null, reopened: false, activeTurnId: null, materials: [], skills: [], turns: [turn] }
  assert.equal(isStudio(snapshot, 'task'), true)
  for (const bad of [{ ...output, url: 'https://evil.test/' }, { ...output, sizeBytes: -1 }, { ...output, url: output.url.replace('/task/', '/other/') }]) {
    assert.equal(isStudioOutput(bad, 'task'), false)
    assert.equal(isStudio({ ...snapshot, turns: [{ ...turn, outputs: [bad] }] }, 'task'), false)
  }
})
test('实际消息混合输出保留图片选择，普通文件只有名称大小下载，partial不显示执行或自动补收', async () => {
  const component = compile('views/overseas/studio/StudioTurns.vue', {
    './StudioOutputs.vue': { default: outputComponent }, './StudioAttachments.vue': { default: defineComponent({ render: () => null }) },
    './StudioProcess.vue': { default: defineComponent({ render: () => null }) },
    './StudioAssetImage.vue': { default: defineComponent({ props: ['asset'], setup: props => () => h('picture', { id: props.asset.id }) }) }
  })
  Object.assign(component, { components: { ElCheckbox: simple('ElCheckbox') } })
  const props = reactive({ turns: [turn], transcript: [], selected: [], disabled: false })
  const view = mount(component, props)
  try {
    assert.equal(find(view.root, 'picture').props.id, 'p')
    assert.equal(find(view.root, 'Download').props.url, output.url)
    assert.match(text(view.root), /方案.zip0 B/)
    assert.match(text(view.root), /已回复/)
    const alerts = all(view.root).filter(item => item.tag === 'ElAlert').map(item => item.props.title).join('')
    assert.match(alerts, /文件收取已结束.*取回文件/)
    assert.doesNotMatch(alerts, /执行中|自动补收|保存中/)
    assert.equal(all(view.root).filter(item => item.tag === 'ElCheckbox').length, 2)
    props.turns = [{ ...turn, deliveryStatus: { state: 'complete', saved: 2, expected: 2 } }]
    await nextTick(); assert.equal(all(view.root).filter(item => item.tag === 'ElAlert').length, 0)
  } finally { view.close() }
})
test('取回API带本会话和版本，拒绝无效响应及超过100项', async () => {
  const file = { id: 'candidate', name: '结果.zip', path: '结果.zip', source: 'work', sizeBytes: 0, version: 'v1' }
  assert.equal(isRecoverableFiles({ items: [file], busy: false }), true)
  assert.equal(isRecoverableFiles({ items: [file, file], busy: false }), false)
  assert.equal(isRecoveryResult({ saved: [{ id: 'out', kind: 'file' }], errors: [] }), true)
  const calls: { url: string; body?: string; method?: string }[] = []
  const api = createStudioOutputsApi(async (url, options) => {
    calls.push({ url: String(url), method: options?.method, body: options?.body as string | undefined })
    return Response.json(String(url).endsWith('recoverable-files') ? { items: [file], busy: false } : { saved: [{ id: 'out', kind: 'file' }], errors: [] })
  })
  await api.list('task', '会话'); await api.recover('task', '会话', [{ id: file.id, version: file.version }])
  assert.match(calls[0].url, /conversations\/%E4%BC%9A%E8%AF%9D\/recoverable-files$/)
  assert.deepEqual(JSON.parse(calls[1].body!), { files: [{ id: 'candidate', version: 'v1' }] })
  assert.throws(() => api.recover('task', 'c', Array.from({ length: 101 }, () => file)), /1–100/)
})
