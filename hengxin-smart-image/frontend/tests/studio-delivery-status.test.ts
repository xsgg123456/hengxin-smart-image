import test from 'node:test'
import assert from 'node:assert/strict'
import { defineComponent, h, nextTick, reactive } from 'vue'
import { isStudio, type StudioDeliveryStatus, type StudioTurn } from '../src/api/overseas/studio'
import { all, compile, find, mount, simple } from './membership-test-harness'

const picture = { id: 'p', name: '已保存.jpg', url: '/api/overseas/v1/tasks/task/studio/pictures/p/content', width: 1600, height: 1600, turnId: 'turn', sku: null, archived: false }
const turn = (): StudioTurn => ({ id: 'turn', text: '', skillName: null, status: 'collecting', reply: '最终回复', error: null, jobId: 'job', jobVersion: 1, attachments: [], pictures: [picture], referencePictures: [], createdAt: '' })
const snapshot = (deliveryStatus: unknown) => ({ taskId: 'task', taskVersion: 1, archiveId: null, reopened: false, completed: false, turns: [{ ...turn(), deliveryStatus }], materials: [], skills: [], activeTurnId: 'turn' })

test('保存进度DTO兼容旧响应并接收真实数量，拒绝未知状态和非法数字', () => {
  for (const deliveryStatus of [undefined, null,
    { state: 'capturing', expected: null, saved: 0 },
    { state: 'saving', expected: 8, saved: 3 },
    { state: 'waiting', expected: 8, saved: 3 },
    { state: 'complete', expected: 8, saved: 8 }]) assert.equal(isStudio(snapshot(deliveryStatus), 'task'), true)
  for (const deliveryStatus of [false, {},
    { state: 'unknown', expected: 8, saved: 3 },
    { state: ['saving'], expected: 8, saved: 3 },
    { state: 'saving', expected: -1, saved: 0 },
    { state: 'saving', expected: 8, saved: 9 },
    { state: 'saving', expected: 8, saved: -1 },
    { state: 'saving', expected: 8, saved: 1.5 },
    { state: 'saving', expected: '8', saved: 3 }]) assert.equal(isStudio(snapshot(deliveryStatus), 'task'), false)
})

const turns = compile('views/overseas/studio/StudioTurns.vue', {
  './StudioProcess.vue': { default: defineComponent({ render: () => null }) },
  './StudioAttachments.vue': { default: defineComponent({ render: () => null }) },
  './StudioAssetImage.vue': { default: defineComponent({ props: ['asset'], setup: p => () => h('picture', { id: p.asset.id }) }) }
})
Object.assign(turns, { components: { ElCheckbox: simple('ElCheckbox') } })
const progress = (root: Parameters<typeof all>[0]) => all(root).filter(n => n.tag === 'ElAlert' && n.props.type === 'info')

test('真实消息组件收图期间立即展示已存图片并更新进度，完成后移除提示', async () => {
  const props = reactive({ turns: [{ ...turn(), deliveryStatus: { state: 'capturing', expected: null, saved: 0 } as StudioDeliveryStatus }], transcript: [], selected: [], disabled: false })
  const view = mount(turns, props)
  try {
    assert.equal(progress(view.root)[0].props.title, '正在接收图片')
    assert.equal(find(view.root, 'picture').props.id, 'p')
    props.turns[0].deliveryStatus = { state: 'saving', expected: 8, saved: 1 }
    await nextTick()
    assert.equal(progress(view.root)[0].props.title, '图片保存中 1/8，系统会自动补收')
    props.turns[0].deliveryStatus = { state: 'waiting', expected: 8, saved: 4 }
    await nextTick()
    assert.equal(progress(view.root)[0].props.title, '图片保存中 4/8，系统会自动补收')
    props.turns[0].deliveryStatus = { state: 'saving', expected: null, saved: 4 }
    await nextTick()
    assert.equal(progress(view.root)[0].props.title, '图片保存中 4 张，系统会自动补收')
    props.turns[0].deliveryStatus = { state: 'complete', expected: 8, saved: 8 }
    await nextTick()
    assert.equal(progress(view.root).length, 0)
    assert.equal(find(view.root, 'picture').props.id, 'p')
  } finally { view.close() }
})

test('旧轮次没有收图状态时不增加提示或额外操作', () => {
  const view = mount(turns, { turns: [turn()], transcript: [], selected: [], disabled: false })
  try {
    assert.equal(progress(view.root).length, 0)
    assert.equal(all(view.root).filter(n => n.tag === 'ElButton').length, 1)
  } finally { view.close() }
})
