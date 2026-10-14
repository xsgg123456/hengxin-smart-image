import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createTasksApi, isTaskDetail, emptyTaskDraft, type TaskDetail } from '../src/api/overseas/tasks'
import { resubmitMaterialIds, taskToDraft } from '../src/views/overseas/requirements'
import { STAGES, STATUS_STEP } from '../src/views/overseas/types'
import type { Material } from '../src/api/overseas/materials'
const task: TaskDetail = { ...emptyTaskDraft(), name: '审核任务', productName: '手机壳', brand: '品牌', market: '美国', skus: [{ code: 'A' }], id: 'task/1', version: 3, status: 'pending_review', createdAt: '2026-10-13', updatedAt: '2026-10-13', createdBy: { id: 'o', name: '运营' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities: ['task.requirements.review'], events: [], requirementsReviews: [] }
const parsed = { version: 1, status: 'ready' as const, parserVersion: 'test', text: '真实资料', error: null, createdAt: '2026-10-13' }
const material: Material = { ...parsed, id: 'm', kind: 'requirement', name: '图需.pdf', sizeBytes: 30, contentType: 'application/pdf', taskId: task.id, versions: [parsed] }
test('审核与重提使用真实契约、版本和幂等键', async () => {
  const calls: {url: string; options?: RequestInit}[] = []
  const api = createTasksApi(async (url, options) => { calls.push({url: String(url), options}); return new Response(JSON.stringify(task)) })
  await api.reviewRequirements(task.id, 'reject', ' 补充尺寸 ', 3, 'review-key')
  await api.resubmit(task.id, { ...taskToDraft(task), materialIds: ['m'] }, 4, 'resubmit-key')
  assert.equal(calls[0].url, '/api/overseas/v1/tasks/task%2F1/requirements-review')
  assert.deepEqual(JSON.parse(String(calls[0].options?.body)), { decision: 'reject', comment: '补充尺寸', version: 3 })
  assert.equal((calls[0].options?.headers as Record<string,string>)['Idempotency-Key'], 'review-key')
  assert.equal(calls[1].url, '/api/overseas/v1/tasks/task%2F1/resubmit')
  const body = JSON.parse(String(calls[1].options?.body))
  assert.equal(body.version, 4); assert.equal(body.designerId, 'd'); assert.deepEqual(body.materialIds, ['m']); assert.equal(body.createdBy, undefined)
})
test('审核记录严格验证，历史未带记录兼容，七节点索引一致', () => {
  const review = { id: 'r', decision: 'reject', comment: '补充资料', actorId: 'd', actorName: '设计', createdAt: '2026-10-13', version: 3, materialIds: ['m'] }
  assert.ok(isTaskDetail({ ...task, requirementsReviews: [review] }))
  assert.ok(isTaskDetail({ ...task, status: 'returned' }))
  assert.ok(isTaskDetail({ ...task, requirementsReviews: undefined }))
  for (const r of [{ ...review, decision: 'other' }, { ...review, version: 0 }, { ...review, materialIds: [3] }]) assert.equal(isTaskDetail({ ...task, requirementsReviews: [r] }), false)
  assert.equal(STAGES.length, 7); assert.equal(STAGES[STATUS_STEP.pending_review], '设计人工审核'); assert.equal(STAGES[STATUS_STEP.analyzing], 'AI 排版分析'); assert.equal(STAGES[STATUS_STEP.archived], '归档成品库')
})
test('重提回填独立草稿，可保留绑定资料和新资料，拒绝跨任务及重复/失败资料', () => {
  const draft = taskToDraft(task); draft.skus[0].code = 'B'; assert.equal(task.skus[0].code, 'A')
  assert.deepEqual(resubmitMaterialIds([material], task.id), ['m'])
  assert.deepEqual(resubmitMaterialIds([material, { ...material, id: 'n', kind: 'competitor', taskId: null }], task.id), ['m', 'n'])
  for (const files of [[], [{ ...material, taskId: 'foreign' }], [material, { ...material, id: 'n' }]]) assert.throws(() => resubmitMaterialIds(files, task.id))
})
