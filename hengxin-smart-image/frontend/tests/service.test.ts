import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createHttpService, ApiError } from '../src/api/hengxin/http'


test('HTTP 真实模式网络断连直接报错，不返回模拟数据', async () => {
  const service = createHttpService('/api/v1', async () => { throw new TypeError('offline') })
  await assert.rejects(service.getUser(), { code: 'UNAVAILABLE' })
})

test('HTTP 拒绝 HTML fallback、无效 JSON、未授权响应', async () => {
  const html = createHttpService('/api/v1', async () => new Response('<html>SPA</html>', { headers: { 'content-type': 'text/html' } }))
  await assert.rejects(html.getUser(), { code: 'INVALID_RESPONSE' })
  const broken = createHttpService('/api/v1', async () => new Response('{', { headers: { 'content-type': 'application/json' } }))
  await assert.rejects(broken.getUser(), { code: 'INVALID_RESPONSE' })
  const denied = createHttpService('/api/v1', async () => new Response(JSON.stringify({ code: 'UNAUTHORIZED', message: '请重新登录' }), { status: 401 }))
  await assert.rejects(denied.getUser(), (error: unknown) => error instanceof ApiError && error.status === 401 && error.message === '请重新登录')
})

test('合法 JSON 的错误结构被拒绝，不能误受理或导致页面崩溃', async () => {
  const responder = (value: unknown) => createHttpService('/api/v1', async () => new Response(JSON.stringify(value), { headers: { 'content-type': 'application/json' } }))
  await assert.rejects(responder({ id: 'u', name: '陌生身份', role: 'root', status: 'active' }).getUser(), { code: 'INVALID_RESPONSE' })
  await assert.rejects(responder(null).getUser(), { code: 'INVALID_RESPONSE' })
})


