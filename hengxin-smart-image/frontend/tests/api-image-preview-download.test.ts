import { test } from 'node:test'
import assert from 'node:assert/strict'
import { prepareTaskZip, downloadTaskZip } from '../src/views/hengxin/api-image-edits/preview-download'
import { type EditTask } from '../src/views/hengxin/api-image-edits/preview-state'
import { crc32 } from '../src/views/hengxin/download-helpers'
const jpeg = (n: number) => new Uint8Array([255, 216, 255, n, 255, 217])
function task(): EditTask {
  return { id: 'zip', name: '测试', prompt: '', material: { name: '', url: '' }, created: '', scenario: 'success', events: [],
    items: [1, 3].map(n => ({ source: { name: '', url: '' }, state: '成功', retries: 0, nextAt: 0,
      result: { name: `示例-${n}.jpg`, url: `/demo-images/sample-${n}.jpg` } })) }
}
test('ZIP按原图顺序编号，使用最新结果并保留有效CRC', async () => {
  const originalFetch = globalThis.fetch, current = task(), urls: string[] = []
  current.items[0].result = { name: '最新修改.jpg', url: '/demo-images/sample-4.jpg' }
  globalThis.fetch = async input => {
    const url = String(input); urls.push(url)
    return new Response(jpeg(Number(url.match(/sample-(\d)/)?.[1])), { headers: { 'Content-Type': 'image/jpeg' } })
  }
  try {
    const zip = await prepareTaskZip(current), bytes = new Uint8Array(await zip.arrayBuffer())
    const view = new DataView(bytes.buffer), names: string[] = [], payloads: number[] = []
    let offset = 0
    while (view.getUint32(offset, true) === 0x04034b50) {
      const length = view.getUint16(offset + 26, true), size = view.getUint32(offset + 18, true)
      names.push(new TextDecoder().decode(bytes.slice(offset + 30, offset + 30 + length)))
      const payload = bytes.slice(offset + 30 + length, offset + 30 + length + size)
      assert.equal(view.getUint32(offset + 14, true), crc32(payload))
      payloads.push(payload[3]); offset += 30 + length + size
    }
    assert.deepEqual(names, ['01-最新修改.jpg', '02-示例-3.jpg'])
    assert.deepEqual(payloads, [4, 3])
    assert.deepEqual(urls, ['/demo-images/sample-4.jpg', '/demo-images/sample-3.jpg'])
    assert.equal(view.getUint32(offset, true), 0x02014b50)
    assert.equal(view.getUint16(bytes.length - 12, true), 2)
  } finally { globalThis.fetch = originalFetch }
})
test('拒绝失败/未完成修改、外部地址、损坏图片；下载失败可再试', async () => {
  const originalFetch = globalThis.fetch, current = task()
  current.items[0].state = '失败'
  await assert.rejects(prepareTaskZip(current), /全部图片成功/)
  current.items[0].state = '成功'
  current.items[0].revision = { state: '失败', text: '改', operator: '张三', retries: 3, nextAt: 0, scenario: 'partial', base: current.items[0].result! }
  await assert.rejects(prepareTaskZip(current), /全部图片成功/)
  current.items[0].revision.state = '处理中'
  await assert.rejects(prepareTaskZip(current), /全部图片成功/)
  current.items[0].revision = undefined
  current.items[0].result!.url = 'https://example.com/image.jpg'
  await assert.rejects(prepareTaskZip(current), /本地示例/)
  current.items[0].result!.url = '/demo-images/sample-1.jpg'
  globalThis.fetch = async () => new Response('invalid', { headers: { 'Content-Type': 'image/jpeg' } })
  try {
    await assert.rejects(downloadTaskZip(current), /有效/)
    await assert.rejects(downloadTaskZip(current), /有效/)
  } finally { globalThis.fetch = originalFetch }
})
test('打包途中修改结果，拒绝下载旧结果', async () => {
  const originalFetch = globalThis.fetch, current = task()
  globalThis.fetch = async () => {
    current.items[0].result!.url = '/demo-images/sample-4.jpg'
    return new Response(jpeg(1), { headers: { 'Content-Type': 'image/jpeg' } })
  }
  try { await assert.rejects(prepareTaskZip(current), /结果已更新/) }
  finally { globalThis.fetch = originalFetch }
})
