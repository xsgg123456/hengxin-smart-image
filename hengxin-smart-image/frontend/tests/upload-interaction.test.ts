import assert from 'node:assert/strict'
import test from 'node:test'
import { clipboardFiles, readClipboardImages, singleImageError } from '../src/views/hengxin/components/upload-interaction'

test('单图上传拒绝多图和占满，空批次不影响既有图片', () => {
  assert.match(singleImageError(2, false), /一次选择 1 张/)
  assert.match(singleImageError(1, true), /先移除/)
  assert.equal(singleImageError(1, false), '')
  assert.equal(singleImageError(0, true), '')
})
test('Ctrl+V 只取真实图片文件，不将文本或URL转成图片', () => {
  const png = new File(['png'], 'a.png', { type: 'image/png' })
  const text = new File(['https://example.com/a.png'], 'url.txt', { type: 'text/plain' })
  assert.deepEqual(clipboardFiles({ files: [png, text] } as unknown as DataTransfer), [png])
  assert.deepEqual(clipboardFiles(null), [])
})
test('粘贴按钮每项只接收一个图片表示，保留 MIME 和可校验扩展名', async () => {
  const requested: string[] = []
  const clipboard = { read: async () => [
    { types: ['text/html', 'image/png', 'image/jpeg'], getType: async (type: string) => { requested.push(type); return new Blob(['image'], { type }) } },
    { types: ['text/plain'], getType: async () => new Blob(['url']) },
    { types: ['image/jpeg'], getType: async (type: string) => new Blob(['jpeg'], { type }) }
  ] } as unknown as Pick<Clipboard, 'read'>
  const files = await readClipboardImages(clipboard)
  assert.equal(files.length, 2)
  assert.deepEqual(requested, ['image/png'])
  assert.equal(files[0]?.type, 'image/png'); assert.match(files[0]!.name, /\.png$/)
  assert.equal(files[1]?.type, 'image/jpeg'); assert.match(files[1]!.name, /\.jpg$/)
})
test('拒绝剪贴板权限传回调用方显示快捷键和选择文件指引', async () => {
  const denied = new DOMException('denied', 'NotAllowedError')
  await assert.rejects(readClipboardImages({ read: async () => { throw denied } }), { name: 'NotAllowedError' })
})
