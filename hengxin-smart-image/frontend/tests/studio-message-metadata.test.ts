import test from 'node:test'
import assert from 'node:assert/strict'
import { reactive, nextTick } from 'vue'
import { compile, mount, all, text, simple } from './membership-test-harness'
import { isStudio, type StudioTurn, type StudioTranscript } from '../src/api/overseas/studio'
import { historicalRevisions } from '../src/views/overseas/studio/studio-revisions'

const component = compile('views/shared/studio/StudioTurns.vue', {
  './studio-revisions': { historicalRevisions },
  ...Object.fromEntries(['StudioProcess', 'StudioOutputs', 'StudioAttachments', 'StudioAssetImage', 'StudioRevisionDetails'].map(name => [`./${name}.vue`, { default: simple(name) }]))
})
Object.assign(component, { components: { ElCheckbox: simple('ElCheckbox') } })
const turn = (extra: Partial<StudioTurn> = {}): StudioTurn => ({ id: 'turn', text: '要求', skillName: null, status: 'succeeded', reply: '回复', error: null, jobId: 'job', jobVersion: 1, attachments: [], pictures: [], referencePictures: [], createdAt: '2026-11-02T01:02:03Z', ...extra })
const entry = (extra: Partial<StudioTranscript> = {}): StudioTranscript => ({ id: 1, turnId: 'turn', itemId: 'message', kind: 'message', text: '流式回复', state: 'completed', createdAt: '2026-11-02T02:03:04Z', ...extra })
const headers = (root: Parameters<typeof all>[0]) => all(root).filter(n => n.props.class === 'studio-message-name').map(text)
const snapshot = (item: unknown) => ({ taskId: 't', taskVersion: 1, archiveId: null, reopened: false, completed: false, activeTurnId: null, materials: [], skills: [], turns: [item] })

test('国内复用消息组件可隐藏空态引导与 Skill 名称，海外默认不变', () => {
  const emptyProps = { turns: [], transcript: [], selected: [], disabled: false }
  const overseas = mount(component, emptyProps)
  const domestic = mount(component, { ...emptyProps, hideEmptyGuide: true })
  const defaultMessage = mount(component, { ...emptyProps, turns: [turn({ skillName: '已有 Skill' })] })
  const domesticMessage = mount(component, { ...emptyProps, turns: [turn({ skillName: '已有 Skill' })], hideSkillLabels: true })
  try {
    assert.equal(all(overseas.root).some(node => node.props.class === 'studio-empty'), true)
    assert.equal(all(domestic.root).some(node => node.props.class === 'studio-empty'), false)
    assert.equal(all(defaultMessage.root).some(node => node.tag === 'ElTag' && text(node) === '已有 Skill'), true)
    assert.equal(all(domesticMessage.root).some(node => node.tag === 'ElTag' && text(node) === '已有 Skill'), false)
    assert.deepEqual(headers(domesticMessage.root), headers(defaultMessage.root))
  } finally { overseas.close(); domestic.close(); defaultMessage.close(); domesticMessage.close() }
})

test('真实消息组件分别署名实际发送人，缺失姓名和时间诚实降级', () => {
  const view = mount(component, { turns: [
    turn({ actor: { id: 'sender-a', name: '实际发送甲' }, replyAt: '2026-11-02T02:03:04+00:00', replyTimeSource: 'message' }),
    turn({ id: 'b', actor: { id: 'sender-b', name: '实际发送乙' }, replyAt: '2026-11-02T03:04:05Z', replyTimeSource: 'completed' }),
    turn({ id: 'c', actor: { id: 'deleted', name: null }, createdAt: '' }),
    turn({ id: 'd', actor: { id: 'blank', name: '   ' }, createdAt: 'invalid' }),
    turn({ id: 'legacy' })
  ], transcript: [], selected: [], disabled: true })
  try {
    assert.deepEqual(headers(view.root), [
      '实际发送甲2026-11-02 09:02:03', 'Codex 已回复2026-11-02 10:03:04',
      '实际发送乙2026-11-02 09:02:03', 'Codex 已回复完成于 2026-11-02 11:04:05',
      '未知操作人时间未记录', 'Codex 已回复时间未记录',
      '未知操作人时间未记录', 'Codex 已回复时间未记录',
      '未知操作人2026-11-02 09:02:03', 'Codex 已回复时间未记录'
    ])
  } finally { view.close() }
})

test('运行无回复不虚构时间，公开message和最终回复出现后更新；刷新身份字段不漂移', async () => {
  const props = reactive({ turns: [turn({ status: 'running', reply: null, actor: { id: 'a', name: '原发送人' }, replyAt: '2026-11-02T02:03:04Z', replyTimeSource: 'message' })], transcript: [] as StudioTranscript[], selected: [], disabled: false })
  const view = mount(component, props)
  try {
    assert.equal(headers(view.root)[1], 'Codex 执行中')
    props.transcript.push(entry()); await nextTick()
    assert.equal(headers(view.root)[1], 'Codex 执行中2026-11-02 10:03:04')
    props.turns[0] = { ...props.turns[0], status: 'succeeded', reply: '流式回复' }; await nextTick()
    const before = headers(view.root)
    props.turns = JSON.parse(JSON.stringify(props.turns)); await nextTick()
    assert.deepEqual(headers(view.root), before)
    props.turns[0].replyAt = 'invalid'; await nextTick()
    assert.equal(headers(view.root)[1], 'Codex 已回复时间未记录')
    props.turns[0].reply = ' '; props.transcript = []; await nextTick()
    assert.equal(headers(view.root)[1], 'Codex 已回复')
  } finally { view.close() }
})

test('消息元信息守卫兼容缺字段和null，但拒绝提供的畸形字段', () => {
  for (const extra of [{}, { actor: { id: 'a', name: null }, replyAt: null, replyTimeSource: null }, { actor: { id: 'a', name: '甲' }, replyAt: '2026-11-02T01:02:03Z', replyTimeSource: 'message' }, { replyTimeSource: 'completed' }]) assert.equal(isStudio(snapshot(turn(extra as Partial<StudioTurn>)), 't'), true)
  for (const extra of [{ actor: null }, { actor: [] }, { actor: { id: 1, name: '甲' } }, { actor: { id: 'a' } }, { actor: { id: 'a', name: false } }, { replyAt: 5 }, { replyAt: {} }, { replyTimeSource: 'updated' }, { replyTimeSource: 1 }]) assert.equal(isStudio(snapshot({ ...turn(), ...extra }), 't'), false, JSON.stringify(extra))
})

test('历史材料入口传递该轮冻结的原图、标注和完整参考用途，关闭后移除详情', async () => {
  const base = { id: 'base', name: '发送时原图.png', url: '/base', width: 800, height: 800, turnId: 'previous', sku: null, archived: false }
  const annotation = { id: 'annotation', name: '定位.png', url: '/annotation', contentType: 'image/png', sizeBytes: 30 }
  const reference = { id: 'reference', name: '发送时参考.png', url: '/reference', contentType: 'image/png', sizeBytes: 40 }
  const customPurpose = '完整用途第一行\n第二行保留', note = '只参考材质\n保留原图结构'
  const item = turn({ attachments: [annotation, reference], referencePictures: [base], imageEdits: [{ pictureId: base.id, annotationId: annotation.id, text: '修改灯罩颜色', references: [{ attachmentId: reference.id, kind: 'custom', customPurpose, note }] }] })
  const view = mount(component, { turns: [item], transcript: [], selected: [], disabled: true })
  try {
    assert.equal(all(view.root).some(n => n.tag === 'StudioRevisionDetails'), false)
    const button = all(view.root).find(n => n.tag === 'ElButton' && text(n) === '查看本轮修改材料（1张）')!
    ;(button.props.onClick as () => void)(); await nextTick()
    const details = all(view.root).find(n => n.tag === 'StudioRevisionDetails')!
    assert.deepEqual(details.props.items, [{ base, annotation, text: '修改灯罩颜色', draftKey: '', referenceImages: [{ asset: reference, kind: 'custom', customPurpose, note }] }])
    const dialog = all(view.root).find(n => n.tag === 'ElDialog' && n.props.title === '本轮修改材料')!
    assert.equal(dialog.props['model-value'], true)
    ;(dialog.props['onUpdate:modelValue'] as (open: boolean) => void)(false); await nextTick()
    assert.equal(all(view.root).some(n => n.tag === 'StudioRevisionDetails'), false)
  } finally { view.close() }
})
