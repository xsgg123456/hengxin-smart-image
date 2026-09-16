import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { requestContainerAuthCode } from '../src/api/hengxin/container-auth'

const config = {
  configured: true,
  corpId: 'ding-corp',
  clientId: 'ding-app',
  callbackPath: '/api/v1/auth/dingtalk/callback',
}

test('容器免登不依赖已下线的阿里 CDN 脚本', () => {
  const root = join(dirname(fileURLToPath(import.meta.url)), '../src/api/hengxin')
  const source = ['dingtalk.ts', 'container-auth.ts']
    .map(name => readFileSync(join(root, name), 'utf8'))
    .join('\n')
  assert.doesNotMatch(source, /g\.alicdn\.com/)
  assert.doesNotMatch(source, /2\.15\.15/)
})

test('容器免登把 corpId 和 clientId 交给 JSAPI，并用 onSuccess 取得授权码', async () => {
  const calls: Array<{ corpId: string; clientId: string }> = []
  const code = await requestContainerAuthCode(config, (options) => {
    calls.push({ corpId: options.corpId, clientId: options.clientId })
    options.onSuccess({ code: 'auth-code-1' })
  })
  assert.equal(code, 'auth-code-1')
  assert.deepEqual(calls, [{ corpId: 'ding-corp', clientId: 'ding-app' }])
})

test('容器免登在 JSAPI 失败和空授权码时拒绝', async () => {
  await assert.rejects(
    requestContainerAuthCode(config, (options) => options.onFail(new Error('bridge missing'))),
    /钉钉免登授权失败|bridge missing/,
  )
  await assert.rejects(
    requestContainerAuthCode(config, (options) => options.onSuccess({})),
    /钉钉未返回授权码/,
  )
})
