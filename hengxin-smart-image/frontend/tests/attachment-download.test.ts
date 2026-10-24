import { test } from 'node:test'
import assert from 'node:assert/strict'
import { downloadAttachment, formatAttachmentSize } from '../src/api/overseas/attachment-download'
import { IdentityError } from '../src/api/identity/request'

const url = '/api/overseas/v1/materials/m-1/content'
const signal = () => new AbortController().signal
test('输入输出附件和图片仅HEAD鉴权预检，原生下载保持长文件名、不读取响应体', async () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, 'document')
  const clicks: string[] = [], removed: string[] = [], methods: string[] = []
  const name = '很长的文件名称'.repeat(30) + '.pdf'
  Object.defineProperty(globalThis, 'document', { configurable: true, value: {
    body: { appendChild() {} }, createElement: () => ({ href: '', download: '', click() { assert.equal(this.download, name); clicks.push(this.href) }, remove() { removed.push(this.href) } })
  } })
  try {
    const fetcher: typeof fetch = async (_url, options) => {
      methods.push(options?.method || 'GET'); assert.equal(options?.credentials, 'include'); assert.equal(options?.redirect, 'error')
      const response = new Response(null)
      response.blob = async () => { throw Error('不得整份缓存') }
      return response
    }
    for (const path of [url, '/api/overseas/v1/tasks/t-1/studio/files/f-1/content', '/api/overseas/v1/tasks/t-1/studio/outputs/f-1/content', '/api/overseas/v1/tasks/t-1/studio/pictures/f-1/content']) await downloadAttachment(path, name, signal(), fetcher)
    assert.deepEqual(methods, ['HEAD', 'HEAD', 'HEAD', 'HEAD']); assert.equal(clicks.length, 4); assert.deepEqual(removed, clicks)
  } finally { if (original) Object.defineProperty(globalThis, 'document', original); else Reflect.deleteProperty(globalThis, 'document') }
})
test('预检失败保留中文身份错误，不发GET；拒绝外域和非法路径', async () => {
  for (const status of [401, 403, 404, 500]) {
    let count = 0
    await assert.rejects(downloadAttachment(url, 'a', signal(), async (_url, options) => { count++; assert.equal(options?.method, 'HEAD'); return new Response(null, { status }) }), e => e instanceof IdentityError && e.status === status && /身份|权限|不存在|无法下载/.test(e.message))
    assert.equal(count, 1)
  }
  for (const path of ['https://evil.test'+url, '//evil.test'+url, url+'?download=true', '/api/overseas/v1/materials/../content', '/api/overseas/v1/materials/%2f/content']) {
    await assert.rejects(downloadAttachment(path, 'a', signal(), async () => { throw Error('不得请求') }), /地址无效/)
  }
  await assert.rejects(downloadAttachment(url, 'a', signal(), async () => { throw Error('offline') }), /连接失败/)
})
test('取消前/请求中/超时和迟到成功都不会启动下载', async () => {
  const aborted = new AbortController(); aborted.abort()
  await assert.rejects(downloadAttachment(url, 'a', aborted.signal, async () => { throw Error('不得请求') }), /取消/)
  const controller = new AbortController()
  await assert.rejects(downloadAttachment(url, 'a', controller.signal, async () => { controller.abort(); return new Response(null) }), /取消/)
  const timeout = AbortSignal.timeout
  try {
    AbortSignal.timeout = () => { const c = new AbortController(); c.abort(); return c.signal }
    await assert.rejects(downloadAttachment(url, 'a', signal(), async () => new Response(null)), /超时/)
  } finally { AbortSignal.timeout = timeout }
})
test('大小按500MB十进制容量展示', () => {
  assert.equal(formatAttachmentSize(500_000_000), '500.0 MB')
  assert.equal(formatAttachmentSize(10), '10 B')
  assert.equal(formatAttachmentSize(1500), '1.5 KB')
})
