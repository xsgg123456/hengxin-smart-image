import { test } from 'node:test'
import assert from 'node:assert/strict'
import { computed, effectScope, ref } from 'vue'
import type { ExecutionData } from '../src/api/hengxin/execution-data'
import { formatExecutionTime, isExecutionData } from '../src/api/hengxin/execution-data'
import { executionEventTime, presentExecutionEvents, timelineDetail, useExecutionDisclosure } from '../src/views/hengxin/components/execution-presentation'

const at = '2026-09-11T00:00:00Z', later = '2026-09-11T00:01:00Z'
type Event = ExecutionData['events'][number]
const event = (sequence: number, message: string, patch: Partial<Event> = {}): Event =>
  ({ sequence, message, stage: 'generating', at, ...patch })

test('播报只认固定前缀，系统记录里的 Codex 字样不误分类', () => {
  const events = [event(1, '准备 Codex 执行器'), event(2, 'Codex：开始处理'), event(3, 'Codex: old platform event')]
  const result = presentExecutionEvents(events)
  assert.deepEqual(result.broadcasts.map(item => item.sequence), [2])
  assert.deepEqual(result.timeline.map(item => item.sequence), [1, 3])
})

test('默认最近三条按接收顺序展示，展开保留全部及重复播报和换行', () => {
  const text = 'Codex：查看素材\n\n逐张处理 <b>原文</b>'
  const events = [event(1, text), event(2, '系统事件'), event(3, text), event(4, 'Codex：第二张'),
    event(5, 'Codex：结果说明', { at: null }), event(6, 'Codex：完成说明')]
  const snapshot = structuredClone(events)
  assert.deepEqual(presentExecutionEvents(events).broadcasts.map(item => item.sequence), [4, 5, 6])
  const expanded = presentExecutionEvents(events, true)
  assert.equal(expanded.total, 5)
  assert.deepEqual(expanded.broadcasts.map(item => item.sequence), [1, 3, 4, 5, 6])
  assert.equal(expanded.broadcasts[0].message, text)
  assert.equal(expanded.broadcasts[1].message, text)
  assert.deepEqual(events, snapshot)
})

test('连续相同系统事件合并并保留次数和时间范围，不修改原事件', () => {
  const events = [event(1, '检测到 1 张图片'), event(2, 'Codex：处理第一张'),
    event(3, '检测到 1 张图片', { at: later }), event(4, '检测到 2 张图片'), event(5, '检测到 1 张图片')]
  const snapshot = structuredClone(events)
  const { timeline } = presentExecutionEvents(events)
  assert.equal(timeline.length, 3)
  assert.deepEqual(timeline[0], { ...events[0], repeats: 2, lastAt: later })
  assert.equal(timeline[2].repeats, 1)
  assert.deepEqual(events, snapshot)
})

test('不同阶段以及有无时间的系统记录不合并，标题重复时省略内容', () => {
  const events = [event(1, '模型处理'), event(2, '模型处理', { stage: 'validating' }),
    event(3, '模型处理', { stage: 'validating', at: null })]
  assert.equal(presentExecutionEvents(events).timeline.length, 3)
  assert.equal(timelineDetail(events[0]), '')
  assert.equal(timelineDetail(events[1]), '模型处理')
  assert.equal(timelineDetail(event(4, ' 模型处理 ')), '')
  assert.equal(timelineDetail(event(5, '检测到图片\n等待校验')), '检测到图片\n等待校验')
})

test('历史 null 时间通过既有协议并明确缺失，实时播报使用接收时间', () => {
  const historical = event(1, 'Codex：历史结果说明', { at: null })
  const data: ExecutionData = { taskId: 'task', roundId: 'round', status: 'failed', source: 'cli',
    diagnosticId: null, stage: 'failed', label: '执行失败', startedAt: null, finishedAt: null,
    updatedAt: at, lastActivityAt: null, totalImages: 3, detectedImages: null, legacy: true,
    events: [historical], failure: null }
  assert.equal(isExecutionData(data), true)
  assert.equal(executionEventTime(presentExecutionEvents(data.events).broadcasts[0]), '历史输出，未记录时间')
  assert.equal(executionEventTime(event(2, '系统历史记录', { at: null })), '未记录时间')
  assert.equal(executionEventTime(event(3, 'Codex：正在处理')), formatExecutionTime(at))
  assert.equal(data.events[0].at, null)
})

test('空记录与只有旧系统事件的任务没有虚构播报', () => {
  assert.deepEqual(presentExecutionEvents([]), { broadcasts: [], total: 0, timeline: [] })
  const result = presentExecutionEvents([event(1, '模型处理'), event(2, '执行失败', { stage: 'failed' })])
  assert.equal(result.total, 0)
  assert.deepEqual(result.broadcasts, [])
  assert.equal(result.timeline.length, 2)
})

test('切任务、轮次、当前轮次、轮次选择、身份与关闭时同步重置展开偏好，返回不恢复旧偏好', () => {
  const initial = { taskId: 'task', roundId: 'round', selected: 'current', currentRoundId: 'round', identity: 'user', active: true }
  for (const patch of [{ taskId: 'other' }, { roundId: 'history' }, { currentRoundId: 'next' },
    { selected: 'history' }, { identity: 'other-user' }, { active: false }]) {
    const scope = effectScope()
    try {
      scope.run(() => {
        const context = ref({ ...initial })
        const { expanded, timelineOpen } = useExecutionDisclosure(() => context.value)
        assert.equal(expanded.value, false)
        assert.deepEqual(timelineOpen.value, [])
        expanded.value = true; timelineOpen.value = ['events']
        Object.assign(context.value, patch)
        assert.equal(expanded.value, false)
        assert.deepEqual(timelineOpen.value, [])
        expanded.value = true; timelineOpen.value = ['events']
        Object.assign(context.value, initial)
        assert.equal(expanded.value, false)
        assert.deepEqual(timelineOpen.value, [])
      })
    } finally { scope.stop() }
  }
})

test('同上下文刷新保留展开状态，收起后显示更新后的最近三条', () => {
  const scope = effectScope()
  try {
    scope.run(() => {
      const context = ref({ taskId: 'task', roundId: 'round', selected: 'current', currentRoundId: 'round', identity: 'user', active: true })
      const events = ref([1, 2, 3, 4].map(id => event(id, `Codex：旧轮 ${id}`)))
      const { expanded, timelineOpen } = useExecutionDisclosure(() => context.value)
      const display = computed(() => presentExecutionEvents(events.value, expanded.value))
      expanded.value = true; timelineOpen.value = ['events']
      events.value = [...events.value, event(5, 'Codex：新增播报')]
      assert.equal(display.value.broadcasts.length, 5)
      assert.deepEqual(timelineOpen.value, ['events'])
      expanded.value = false
      assert.deepEqual(display.value.broadcasts.map(item => item.sequence), [3, 4, 5])
      assert.equal(display.value.total, 5)
    })
  } finally { scope.stop() }
})
