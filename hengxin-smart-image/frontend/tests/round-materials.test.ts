import assert from 'node:assert/strict'
import test from 'node:test'
import { createRoundMaterialsApi, isRoundMaterials } from '../src/api/hengxin/round-materials'

function material() {
  return {
    taskId: 'task-1',
    roundId: 'round-1',
    note: '修改意见',
    status: 'succeeded',
    systemPrompts: [{ label: '任务提示词', text: '完整任务原文\n'.repeat(3000) }],
    toolCalls: [
      { label: '调用 1', prompt: '<script>用户文本</script>', images: ['/work/current/00.png'] },
    ],
    inputs: [
      {
        role: 'current',
        label: '基础成品',
        version: 1,
        picture: { name: 'v1.png', fileId: 'file-1', url: '/api/v1/files/file-1/content' },
      },
    ],
    outputs: [],
    notices: ['尚无结果'],
  }
}
test('轮次材料通过鉴权HTTP独立加载，保留完整长文本与换行', async () => {
  const input = material(),
    calls: { url: string; options?: RequestInit }[] = []
  const fetcher: typeof fetch = async (url, options) => {
    calls.push({ url: String(url), options })
    return new Response(JSON.stringify(input), { headers: { 'Content-Type': 'application/json' } })
  }
  const result = await createRoundMaterialsApi('/api/v1', fetcher)('task-1', 'round-1')
  assert.deepEqual(result, input)
  assert.equal(calls[0].url, '/api/v1/tasks/task-1/rounds/round-1/materials')
  assert.equal(calls[0].options?.credentials, 'include')
  assert.equal(calls.length, 1)
})
test('拒绝串轮次响应、格式错误和未鉴权的外部图片地址', async () => {
  const input = material()
  const fetcher: typeof fetch = async () =>
    new Response(JSON.stringify(input), { headers: { 'Content-Type': 'application/json' } })
  await assert.rejects(
    createRoundMaterialsApi('/api/v1', fetcher)('task-1', 'round-other'),
    /所选轮次不一致/,
  )
  assert.equal(
    isRoundMaterials({
      ...input,
      toolCalls: [{ label: 'x', prompt: 'x', images: ['/etc/private'] }],
    }),
    false,
  )
  assert.equal(
    isRoundMaterials({
      ...input,
      inputs: [
        { ...input.inputs[0], picture: { name: 'x', url: 'https://external.example/image.png' } },
      ],
    }),
    false,
  )
  assert.equal(isRoundMaterials({ ...input, systemPrompts: [{ label: 'x' }] }), false)
  assert.equal(
    isRoundMaterials({
      ...input,
      outputs: [{ role: 'output', label: '结果', picture: null, reason: '图片已删除' }],
    }),
    true,
  )
})
test('服务不可用不伪造材料，错误可供前端重试', async () => {
  const fetcher: typeof fetch = async () => new Response('{}', { status: 503 })
  await assert.rejects(createRoundMaterialsApi('/api/v1', fetcher)('task-1', 'round-1'), /503/)
})
