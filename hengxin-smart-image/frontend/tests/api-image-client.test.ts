import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createApiImageClient, uncertainResponse } from '../src/api/api-image-edits'
import { ApiError } from '../src/api/hengxin/http'
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json' } })
const input = { name: '套图', prompt: '替换屏幕', originalFileIds: ['original-2', 'original-1'], materialFileId: 'material' }
test('独立client使用专属前缀、会话认证及稳定幂等键，保留原图顺序', async () => {
  const calls: { url: string; init?: RequestInit }[] = []
  const client = createApiImageClient('/api/v1', async (url, init) => { calls.push({ url: String(url), init }); return json({ taskId: 'api-task' }, 202) })
  await client.create(input, 'same-key'); await client.create(input, 'same-key'); await client.retry('api-task', 'retry-key')
  assert.deepEqual(calls.map(c => c.url), ['/api/v1/api-image-edits/tasks', '/api/v1/api-image-edits/tasks', '/api/v1/api-image-edits/tasks/api-task/retry'])
  assert.equal(calls[0].init?.credentials, 'include')
  assert.equal(new Headers(calls[0].init?.headers).get('Idempotency-Key'), 'same-key')
  assert.equal(new Headers(calls[1].init?.headers).get('Idempotency-Key'), 'same-key')
  assert.deepEqual(JSON.parse(String(calls[0].init?.body)), input)
})
test('disabled是明确真实状态；错误响应不回退模拟数据', async () => {
  const disabled = createApiImageClient('/api/v1', async () => json({ enabled: false, paused: false, reason: null }))
  assert.equal((await disabled.status()).enabled, false)
  await assert.rejects(createApiImageClient('/api/v1', async () => json({})).list({ page: 1, pageSize: 20, search: '', status: '' }), /数据不完整/)
  await assert.rejects(createApiImageClient('/api/v1', async () => { throw new Error('offline') }).status(), /连接失败/)
  assert.equal(uncertainResponse(new ApiError('UNAVAILABLE', '网络未知')), true)
  assert.equal(uncertainResponse(new ApiError('INVALID', '无效输入', 422)), false)
})
test('真实上传、删除及单图下载不访问CLI资源；阻止错误下载内容', async () => {
  const calls: string[] = []
  const client = createApiImageClient('/api/v1', async (url, init) => {
    calls.push(String(url))
    if (init?.method === 'POST') { assert.ok(init.body instanceof FormData); return json({ fileId: 'api-file', name: 'a.png', url: '/safe.png' }) }
    if (init?.method === 'DELETE') return new Response(null, { status: 204 })
    return new Response('png', { headers: { 'content-type': 'image/png' } })
  })
  await client.upload(new File(['png'], 'a.png', { type: 'image/png' })); await client.deleteFile('api-file')
  assert.equal((await client.download('api-file')).type, 'image/png')
  assert.ok(calls.every(url => url.startsWith('/api/v1/api-image-edits/files')))
  await assert.rejects(createApiImageClient('/api/v1', async () => json({ error: 'invalid' })).download('bad'), /不是图片/)
})
