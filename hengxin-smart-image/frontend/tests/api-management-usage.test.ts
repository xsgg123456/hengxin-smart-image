import test from 'node:test'
import assert from 'node:assert/strict'
import { createApiUsageClient } from '../src/api/api-management-usage'
import { apiUsageReport } from '../src/api/api-management-usage-validate'
import { usageFixture } from './api-management-usage-fixture'
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
test('真实 API 统计发送独立事件分页和日期筛选，汇总与库存不被客户端分页重算', async () => {
  const report = usageFixture(), paths: string[] = []
  const client = createApiUsageClient('/api/v1/', async input => { paths.push(String(input)); return json(report) })
  const result = await client({ from: '2026-10-01', to: '2026-10-10', category: 'api_request', userId: '用户&一', page: 2, pageSize: 20 })
  const url = new URL(paths[0]!, 'http://local')
  assert.equal(url.pathname, '/api/v1/management/api-usage'); assert.equal(url.searchParams.get('userId'), '用户&一')
  assert.equal(url.searchParams.get('page'), '2'); assert.deepEqual(result.summary, report.summary); assert.deepEqual(result.inventory, report.inventory)
  await client({ unassigned: true, generationType: 'api_edit', outputsOnly: false }); assert.match(paths[1]!, /generationType=api_edit/); assert.match(paths[1]!, /outputsOnly=false/); assert.match(paths[1]!, /unassigned=true/)
})
test('未提供 Token/费用、未知重试、空操作者、已删除历史均原样保留', async () => {
  const report = usageFixture()
  assert.equal(apiUsageReport(report), true)
  const result = await createApiUsageClient('/api', async () => json(report))({})
  assert.equal(result.summary.cost, null); assert.equal(result.events[0]?.operatorId, null)
  assert.equal(result.events[0]?.isRetry, null); assert.equal(result.events[0]?.taskDeleted, true)
  assert.equal(result.summary.apiUnknown, 2); assert.equal(result.summary.cliUnverified, 1)
})
test('缺字段、负计数、畸形比例、非法归属与事件拒绝，不降级为模拟统计', async () => {
  for (const mutate of [
    (r: ReturnType<typeof usageFixture>) => { r.summary.apiAttempts = -1 },
    (r: ReturnType<typeof usageFixture>) => { r.summary.initialImages = -1 },
    (r: ReturnType<typeof usageFixture>) => { r.summary.modifiedImages = 1.5 },
    (r: ReturnType<typeof usageFixture>) => { delete (r.summary as Partial<typeof r.summary>).totalGeneratedImages },
    (r: ReturnType<typeof usageFixture>) => { r.summary.generatedTasks = NaN },
    (r: ReturnType<typeof usageFixture>) => { r.events[0]!.generatedImages = -1 },
    (r: ReturnType<typeof usageFixture>) => { Object.assign(r.events[0]!, { generationType: 'invalid' }) },
    (r: ReturnType<typeof usageFixture>) => { r.summary.requestSuccessRate = 2 },
    (r: ReturnType<typeof usageFixture>) => { r.events[0]!.occurredAt = 'bad' },
    (r: ReturnType<typeof usageFixture>) => { delete (r.summary as Partial<typeof r.summary>).apiUnknown },
    (r: ReturnType<typeof usageFixture>) => { r.inventory.sourceImages = NaN }
  ]) {
    const report = usageFixture(); mutate(report)
    assert.equal(apiUsageReport(report), false)
    await assert.rejects(createApiUsageClient('/api', async () => json(report))({}), { code: 'INVALID_RESPONSE' })
  }
  await assert.rejects(createApiUsageClient('/api', async () => json({ message: '读取失败' }, 503))({}), /读取失败/)
  await assert.rejects(createApiUsageClient('/api', async () => { throw new Error('offline') })({}), { code: 'UNAVAILABLE' })
})
test('空记录有效，成功率无已知结果保持null，不造0%', () => {
  const report = usageFixture(); report.rows = []; report.events = []; report.total = 0
  report.summary.requestSuccessRate = null; report.inventory.deliverySuccessRate = null
  assert.equal(apiUsageReport(report), true)
})
