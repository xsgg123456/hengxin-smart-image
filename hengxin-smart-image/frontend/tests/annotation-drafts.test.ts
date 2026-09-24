import test from 'node:test'
import assert from 'node:assert/strict'
import { annotationDraft, annotationText, forgetAnnotationDraft } from '../src/views/hengxin/components/annotation/annotation-drafts'
import type { AnnotationMark } from '../src/views/hengxin/components/annotation/annotation-model'
const mark = (id: string, kind: 'rect' | 'pen', note: string): AnnotationMark => ({ id, kind, note, x: 1, y: 2, width: 30, height: 40, points: [] })
test('标注意见按实际数组顺序完整拼接，删除后重新编号，不截断', () => {
  const draft = { mode: 'direct' as const, marks: [mark('a', 'rect', '镜头右移'), mark('b', 'pen', '边缘修齐')], general: '其他保持' }
  assert.equal(annotationText(draft, 1000), '标注 1（框选）：镜头右移\n标注 2（画笔）：边缘修齐\n其他保持')
  draft.marks.shift()
  assert.equal(annotationText(draft, 1000), '标注 1（画笔）：边缘修齐\n其他保持')
  assert.throws(() => annotationText(draft, 3), /不能超过/)
  draft.marks[0].note = ' '
  assert.throws(() => annotationText(draft, 1000), /每一处/)
})
test('上传模式不夹带隐藏的画布意见；单纯文字可提交', () => {
  const onlyImage = { mode: 'upload' as const, marks: [], general: '', uploaded: new File(['png'], 'mark.png', { type: 'image/png' }) }
  assert.equal(annotationText(onlyImage, 4000), '')
  assert.throws(() => annotationText(onlyImage, 1000, false), /请填写修改意见/)
  assert.equal(annotationText({ mode: 'upload', marks: [mark('a', 'rect', '')], general: '调整红圈位置' }, 1000), '调整红圈位置')
  assert.throws(() => annotationText({ mode: 'direct', marks: [], general: '' }, 1000), /填写修改意见/)
})
test('草稿按身份任务位置版本隔离，关闭重开恢复，成功后清除', () => {
  const key = JSON.stringify(['cli', 'user1', 'task1', 0, 'v3'])
  annotationDraft(key).marks.push(mark('a', 'pen', '修正'))
  assert.equal(annotationDraft(key).marks[0].note, '修正')
  assert.equal(annotationDraft(JSON.stringify(['cli', 'user2', 'task1', 0, 'v3'])).marks.length, 0)
  forgetAnnotationDraft(key)
  assert.equal(annotationDraft(key).marks.length, 0)
})
