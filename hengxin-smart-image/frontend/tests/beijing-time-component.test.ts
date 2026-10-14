import test from 'node:test'
import assert from 'node:assert/strict'
import * as Tasks from '../src/api/overseas/tasks'
import { compile, mount, table, text } from './membership-test-harness'

const timestamp = '2026-10-14T00:59:59.091561+00:00'
const task = { ...Tasks.emptyTaskDraft(), id: 't', name: '时间回归任务', status: 'pending_review', version: 1,
  createdAt: timestamp, updatedAt: timestamp, events: [{ title: '提交任务', at: timestamp }],
  createdBy: { id: 'o', name: '运营' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true },
  requirementsReviews: [{ id: 'r', decision: 'approve', actorName: '设计', version: 1, createdAt: timestamp }] }

test('实际海外列表 SFC 将原始 UTC 列渲染为北京时间', () => {
  const component = compile('views/overseas/OverseasWorkspace.vue', {
    '@/api/overseas/tasks': Tasks,
    '@/components/core/tables/art-table/index.vue': { default: table, __esModule: true }
  })
  const view = mount(component, { tasks: [task], total: 1, allowed: true, query: '', scope: 'all', status: '' })
  try {
    assert.ok(text(view.root).includes('2026-10-14 08:59:59'))
    assert.ok(!text(view.root).includes(timestamp))
  } finally { view.close() }
})

test('实际任务信息 SFC 的提交、审核、事件时间均转换且不泄漏 ISO', () => {
  const view = mount(compile('views/overseas/OverseasTaskInfo.vue', {}), { task })
  try {
    assert.equal(text(view.root).match(/2026-10-14 08:59:59/g)?.length, 3)
    assert.ok(!text(view.root).includes(timestamp))
  } finally { view.close() }
})
