import test from 'node:test'
import assert from 'node:assert/strict'
import { defineComponent, h, reactive, nextTick } from 'vue'
import { compile, mount, find, all, text, simple } from './membership-test-harness'
import { splitStudioReply } from '../src/views/overseas/studio/studio-process'
import { languageLabel } from '../src/views/overseas/languages'
import type { StudioTranscript, StudioTurn } from '../src/api/overseas/studio'
import { historicalRevisions } from '../src/views/overseas/studio/studio-revisions'

const markdown = defineComponent({ props: ['text'], setup: p => () => h('markdown', p.text) })
const transcript = compile('views/overseas/studio/StudioTranscript.vue', { './StudioMarkdown.vue': { default: markdown } })
const process = compile('views/overseas/studio/StudioProcess.vue', {
  './StudioMarkdown.vue': { default: markdown }, './StudioTranscript.vue': { default: transcript }, './studio-process': { splitStudioReply }
})
const entry = (id: number, kind: StudioTranscript['kind'], value: string): StudioTranscript => ({ id, turnId: 'turn', itemId: String(id), kind, text: value, state: 'completed', createdAt: '' })
const turn = (status = 'running', reply: string | null = null): StudioTurn => ({ id: 'turn', status, reply, text: '', skillName: null, error: null, jobId: 'job', jobVersion: 1, attachments: [], pictures: [], referencePictures: [], createdAt: '' })

test('正式组件执行时展开，成功自动收起，最终正文仅在过程之外出现一次', async () => {
  const props = reactive({ turn: turn(), entries: [entry(1, 'message', '准备构图'), entry(2, 'tool', '图片生成')] })
  const view = mount(process, props)
  try {
    assert.equal(find(view.root, 'details').props.open, true)
    props.entries.push(entry(3, 'message', '最终正文'))
    props.turn = turn('succeeded', '最终正文')
    await nextTick()
    const group = find(view.root, 'details')
    assert.equal(group.props.open, false)
    assert.ok(text(group).includes('准备构图'))
    assert.ok(!text(group).includes('最终正文'))
    assert.equal(all(view.root).filter(n => n.tag === 'markdown' && n.text === '最终正文').length, 1)
    ;(group.props.onToggle as (e: unknown) => void)({ target: { open: true } })
    await nextTick()
    assert.equal(group.props.open, true)
    props.turn = { ...props.turn, jobVersion: 2 }
    await nextTick()
    assert.equal(group.props.open, true, '轮询不覆盖用户手动展开')
  } finally { view.close() }
})

test('历史成功默认关闭，失败和停止的公开过程及独立回复不丢失', () => {
  for (const status of ['succeeded', 'failed', 'cancelled']) {
    const view = mount(process, { turn: turn(status, '独立回复'), entries: [entry(1, 'message', '公开进展'), entry(2, 'notice', '保留通知')] })
    try {
      assert.equal(find(view.root, 'details').props.open, status !== 'succeeded')
      assert.ok(text(view.root).includes('公开进展'))
      assert.ok(text(view.root).includes('独立回复'))
    } finally { view.close() }
  }
})

test('最终回复不同于stream消息仍显示；空历史回复回退最后消息；迟到消息不重复', () => {
  const entries = [entry(1, 'message', '前言'), entry(2, 'message', '结论')]
  assert.deepEqual(splitStudioReply(turn('succeeded', '权威结论'), entries), { entries, reply: '权威结论' })
  assert.deepEqual(splitStudioReply(turn('succeeded'), entries), { entries: [entries[0]], reply: '结论' })
  assert.deepEqual(splitStudioReply(turn('succeeded', '结论'), []), { entries: [], reply: '结论' })
  assert.deepEqual(splitStudioReply(turn('succeeded', '结论'), entries), { entries: [entries[0]], reply: '结论' })
  assert.deepEqual(splitStudioReply(turn('cancelled', '结论'), entries), { entries, reply: '' })
})

test('归档确认与成品详情共用六字段，真实值及历史缺失一致', async () => {
  const detail = compile('views/overseas/OverseasArchiveFields.vue', { './languages': { languageLabel } })
  const fields = compile('views/overseas/studio/StudioArchiveFields.vue', { '../OverseasArchiveFields.vue': { default: detail } })
  const task = reactive({ name: '任务名称', productName: '真实产品', brand: '真实品牌', platform: 'Amazon', language: 'de' as string | null, skus: [{ code: 'A' }, { code: 'B' }] })
  const view = mount(fields, { task })
  const archived = mount(detail, { archive: { ...task, taskName: task.name } })
  try {
    assert.deepEqual(all(view.root).filter(n => n.tag === 'dt').map(text), ['SKU', '目标平台', '品牌', '任务名称', '品名', '语言'])
    assert.deepEqual(all(view.root).filter(n => n.tag === 'dd').map(text), ['A · B', 'Amazon', '真实品牌', '任务名称', '真实产品', '德语'])
    assert.equal(text(view.root), text(archived.root))
    task.language = null; task.name = ''; await nextTick()
    assert.equal(all(view.root).filter(n => n.tag === 'dd' && text(n) === '未设置').length, 2)
    for (const [code, label] of [['en', '英语'], ['fr', '法语'], ['es', '西班牙语']]) {
      task.language = code; await nextTick(); assert.equal(text(all(view.root).filter(n => n.tag === 'dd').at(-1)!), label)
    }
    assert.ok(!text(view.root).includes('归档人'))
  } finally { view.close(); archived.close() }
})

test('正式StudioTurns将正式图片置于折叠组之外并保留图片选择事件', () => {
  const image = defineComponent({ props: ['asset'], setup: p => () => h('picture', { id: p.asset.id }) })
  const turns = compile('views/overseas/studio/StudioTurns.vue', {
    './studio-revisions': { historicalRevisions },
    './StudioRevisionDetails.vue': { default: simple('StudioRevisionDetails') },
    './StudioOutputs.vue': { default: simple('StudioOutputs') },
    './StudioProcess.vue': { default: process },
    './StudioAttachments.vue': { default: defineComponent({ render: () => null }) },
    './StudioAssetImage.vue': { default: image }
  })
  Object.assign(turns, { components: { ElCheckbox: simple('ElCheckbox') } })
  const selected: string[] = []
  const batches: unknown[] = []
  const picture = { id: 'real-picture', name: '正式图片.png', turnId: 'turn', url: '/picture', width: 800, height: 800, archived: false, sku: null }
  const pictures = [picture, { ...picture, id: 'second-picture', name: '第二张.png' }]
  const view = mount(turns, { turns: [{ ...turn('succeeded', '最终回复'), pictures }], transcript: [entry(1, 'tool', '执行消息'), entry(2, 'message', '最终回复')], selected: [], disabled: false, onToggle: (id: string) => selected.push(id), onBatchModify: (items: unknown) => batches.push(items) })
  try {
    assert.equal(find(view.root, 'details').props.open, false)
    const result = find(view.root, 'picture')
    assert.equal(result.props.id, 'real-picture')
    for (let parent = result.parent; parent; parent = parent.parent) assert.notEqual(parent.tag, 'details')
    const checkbox = all(view.root).find(n => n.props.onChange && text(n).includes('正式图片.png'))
    assert.ok(checkbox)
    ;(checkbox.props.onChange as () => void)()
    assert.deepEqual(selected, ['real-picture'])
    const batch = all(view.root).find(n => n.tag === 'ElButton' && text(n) === '批量标注')!
    ;(batch.props.onClick as () => void)()
    assert.deepEqual(batches, [pictures], '批量入口传递完整原组，不受归档勾选影响')
    assert.deepEqual(selected, ['real-picture'], '打开标注不改变归档勾选')
  } finally { view.close() }
})
