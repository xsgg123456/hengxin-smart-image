import { test } from 'node:test'
import assert from 'node:assert/strict'
import { logoutDestination, logoutSession } from '../src/api/hengxin/logout'

test('退出向后端发送携带会话的 POST 并接受 204', async () => {
  await logoutSession('/api/v1', async (url, options) => {
    assert.equal(url, '/api/v1/auth/logout')
    assert.equal(options?.method, 'POST')
    assert.equal(options?.credentials, 'include')
    return new Response(null, { status: 204 })
  })
})

test('服务不可用时退出失败，不吞掉错误', async () => {
  await assert.rejects(logoutSession('/api/v1', async () => new Response(null, { status: 503 })), /503/)
})

test('退出进入登录页并保留安全业务返回地址，清除预览参数', () => {
  const url = new URL(logoutDestination('https://zhitu.qhhengxin.top/?role=super_admin#/tasks/index?task=123'))
  assert.equal(url.origin, 'https://zhitu.qhhengxin.top')
  assert.equal(url.search, '')
  assert.equal(url.hash, '#/auth/login?redirect=%2Ftasks%2Findex%3Ftask%3D123')
  assert.equal(new URL(logoutDestination('https://zhitu.qhhengxin.top/#//evil.example')).hash,
    '#/auth/login?redirect=%2Fimage-processing%2Fwallpaper')
})
