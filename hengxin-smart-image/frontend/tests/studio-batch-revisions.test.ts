import test from 'node:test'
import assert from 'node:assert/strict'
import { fixture, flush, asset, deferred } from './studio-sessions-fixture'
import type { Studio, StudioPicture, TurnInput } from '../src/api/overseas/studio'
import type { Reference } from '../src/views/overseas/studio/editing/state'
import { annotationDraft } from '../src/views/hengxin/components/annotation/annotation-drafts'
const picture = (id: string): StudioPicture => ({ id, name: `${id}.png`, width: 20, height: 30, turnId: 'r', url: `/api/overseas/v1/tasks/t/studio/pictures/${id}/content`, sku: null, archived: false })
const refFile = (id: string): Reference => ({ id, name: `${id}.png`, file: new File([id], `${id}.png`, { type: 'image/png' }), url: '', kind: 'custom', customPurpose: '材质与配色\n保留结构', note: '只参考木色', status: 'ready', error: '' })
const item = (id: string) => ({ picture: picture(id), text: `修改${id}`, file: new File(['mark'], `${id}-mark.png`, { type: 'image/png' }), references: [refFile(id)] })
function setup() {
  const f = fixture(), original = f.api.get
  const withPictures = (s: Studio): Studio => ({ ...s, turns: [{ id: 'r', text: '', skillName: null, status: 'succeeded', reply: '', error: null, jobId: 'j', jobVersion: 1, attachments: [], referencePictures: [], pictures: ['p2', 'p4'].map(picture), conversationId: s.conversationId || undefined, createdAt: '' }] })
  f.api.get = async (...args) => withPictures(await original(...args))
  const uploads: string[] = [], sends: TurnInput[] = []
  f.api.upload = async (_task, file) => { uploads.push(file.name); return { ...asset(String(uploads.length)), name: file.name, contentType: 'image/png' } }
  f.api.send = async (_task, body) => { sends.push(body); return withPictures(f.snapshot(body.conversationId)) }
  return { ...f, uploads, sends }
}
test('批量原子带回2/4图，各自参考用途和文件绑定，手动发送后清草稿', async () => {
  const f = setup(), v = f.mount(); await flush()
  try {
    const rows = [item('p2'), item('p4')]
    assert.equal(await v.state.confirmRevisions(rows, ['p1', 'p2', 'p3', 'p4']), true)
    assert.deepEqual(v.state.references.value.map(p => p.id), ['p2', 'p4']); assert.equal(f.sends.length, 0)
    rows[0].references[0].note = '之后的草稿'
    await v.state.send()
    assert.equal(f.sends.length, 1)
    assert.deepEqual(f.sends[0].referencePictureIds, ['p2', 'p4'])
    assert.deepEqual(f.sends[0].imageEdits?.map(e => e.references?.[0].attachmentId), ['upload:2', 'upload:4'])
    assert.equal(f.sends[0].imageEdits?.[0].references?.[0].note, '只参考木色')
    assert.equal(f.sends[0].imageEdits?.[0].references?.[0].customPurpose, '材质与配色\n保留结构')
    assert.equal(v.state.revisions.value.length, 0)
  } finally { v.close() }
})
test('第二张上传失败保留原摘要，重试复用成功文件，不丢第一张或混入半批', async () => {
  const f = setup(), v = f.mount(); await flush()
  try {
    await v.state.confirmRevision(picture('p2'), { text: '已确认旧版' })
    const upload = f.api.upload; let failed = false
    f.api.upload = async (...args) => { if (!failed && args[1].name === 'p4-mark.png') { failed = true; throw Error('断网') }; return upload(...args) }
    const rows = [item('p2'), item('p4')]
    assert.equal(await v.state.confirmRevisions(rows), false)
    assert.equal(v.state.revisions.value.length, 1); assert.equal(v.state.revisions.value[0].text, '已确认旧版'); assert.equal(v.state.attachments.value.length, 0)
    assert.equal(await v.state.confirmRevisions(rows), true); assert.equal(f.uploads.length, 4)
  } finally { v.close() }
})
test('已确认参考说明与标注快照刷新恢复，未确认编辑不污染；预设不发送隐藏用途', async () => {
  const f = setup(), v = f.mount(); await flush()
  const row = item('p2'); row.references[0].kind = 'product'
  const marks = [{ id: 'm', kind: 'rect' as const, x: 1, y: 1, width: 2, height: 2, points: [], note: '原标注' }]
  await v.state.confirmRevisions([{ ...row, marks }])
  annotationDraft(v.state.draftKey(row.picture)).marks = [{ ...marks[0], note: '未确认改动' }]
  v.close(); const next = f.mount(); await flush()
  try {
    assert.equal(next.state.revisions.value[0].referenceImages?.[0].customPurpose, '材质与配色\n保留结构')
    assert.equal(next.state.revisions.value[0].marks?.[0].note, '原标注')
    await next.state.send(); assert.equal(f.sends[0].imageEdits?.[0].references?.[0].customPurpose, '')
  } finally { next.close() }
})
test('重确认批量移除本组清空项，取消保留其他图共享附件和普通附件', async () => {
  const f = setup(), v = f.mount(); await flush()
  try {
    v.state.add(['upload:a'])
    await v.state.confirmRevisions([item('p2'), item('p4')])
    await v.state.confirmRevisions([item('p2')], ['p2', 'p4'])
    assert.deepEqual(v.state.references.value.map(p => p.id), ['p2']); assert.equal(v.state.attachments.value.length, 3)
    await v.state.confirmRevisions([], ['p2', 'p4'])
    assert.equal(v.state.revisions.value.length, 0); assert.deepEqual(v.state.attachments.value.map(a => a.id), ['upload:a'])
    await v.state.confirmRevisions([item('p2')])
    v.state.removeRevision('p2'); assert.deepEqual(v.state.attachments.value.map(a => a.id), ['upload:a'])
  } finally { v.close() }
})
test('会话切换时迟到上传仅回原会话，其他会话没有材料', async () => {
  const f = setup(), v = f.mount(); await flush(); const pending = deferred<ReturnType<typeof asset>>()
  f.api.upload = async () => pending.promise
  try {
    const work = v.state.confirmRevisions([{ picture: picture('p2'), text: '修改', file: new File(['x'], 'a.png') }])
    await v.state.selectSession('b'); pending.resolve({ ...asset('mark'), contentType: 'image/png' }); await work
    assert.equal(v.state.revisions.value.length, 0)
    await v.state.selectSession('a'); assert.equal(v.state.revisions.value.length, 1)
  } finally { v.close() }
})
test('用途空白、无说明、超限和非图片参考均在上传前拒绝', async () => {
  const f = setup(), v = f.mount(); await flush()
  try {
    for (const change of [(r: Reference) => r.customPurpose = ' ', (r: Reference) => r.note = '', (r: Reference) => r.note = 'x'.repeat(2001), (r: Reference) => r.file = new File(['x'], 'a.svg', { type: 'image/svg+xml' })]) {
      const row = item('p2'); change(row.references[0]); assert.equal(await v.state.confirmRevisions([row]), false)
    }
    assert.equal(f.uploads.length, 0); assert.equal(v.state.revisions.value.length, 0)
  } finally { v.close() }
})
