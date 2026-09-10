import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildZip, crc32, safeFilename, readImage, prepareSet, imageExtension, requestDownload } from '../src/views/hengxin/download-helpers'
const png = new Uint8Array(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jD1sAAAAASUVORK5CYII=', 'base64'))
test('下载命名去路径与非法字符，替换旧后缀', () => {
  assert.equal(safeFilename('../产品\\主图.jpg.png', 'webp'), '.._产品_主图.webp')
  assert.equal(safeFilename('CON', 'png'), '图片_CON.png')
  assert.equal(safeFilename('套图.zip', 'zip'), '套图.zip')
})
test('MIME 与字节匹配，HTML/JSON/空文件不能伪装图片', () => {
  assert.equal(imageExtension(png, 'image/png'), 'png')
  for (const mime of ['text/html', 'application/json', 'image/jpeg']) assert.throws(() => imageExtension(png, mime))
  for (const body of ['<html>错误</html>', '{"error":1}', '']) assert.throws(() => imageExtension(new TextEncoder().encode(body), 'image/png'))
  assert.equal(imageExtension(new TextEncoder().encode('<svg xmlns="http://www.w3.org/2000/svg"><rect /></svg>'), 'image/svg+xml'), 'svg')
})
test('ZIP 目录、UTF8、存储内容及标准 CRC 正确', async () => {
  const data = new TextEncoder().encode('123456789'), filename = '01-主图.png'
  assert.equal(crc32(data), 0xcbf43926)
  const bytes = new Uint8Array(await buildZip([{ name: filename, data }, { name: '02.png', data: png }]).arrayBuffer())
  const view = new DataView(bytes.buffer), end = bytes.length - 22
  assert.equal(view.getUint32(end, true), 0x06054b50)
  assert.equal(view.getUint16(end + 10, true), 2)
  let cursor = view.getUint32(end + 16, true)
  const directoryStart = cursor
  for (const [name, expected] of [[filename, data], ['02.png', png]] as const) {
    assert.equal(view.getUint32(cursor, true), 0x02014b50)
    assert.equal(view.getUint16(cursor + 8, true), 0x800)
    const local = view.getUint32(cursor + 42, true), nameSize = view.getUint16(cursor + 28, true), size = view.getUint32(cursor + 24, true)
    assert.equal(view.getUint32(local, true), 0x04034b50)
    assert.equal(view.getUint16(local + 8, true), 0)
    assert.equal(new TextDecoder().decode(bytes.slice(local + 30, local + 30 + nameSize)), name)
    assert.equal(view.getUint32(local + 14, true), view.getUint32(cursor + 16, true))
    assert.deepEqual(bytes.slice(local + 30 + nameSize, local + 30 + nameSize + size), expected)
    cursor += 46 + nameSize
  }
  assert.equal(cursor, end)
  assert.equal(view.getUint32(end + 12, true), end - directoryStart)
  assert.throws(() => buildZip([]))
})
test('下载保留 bytes、凭据限定同源，错误/超时/整套任一失败拒绝', async () => {
  const original = globalThis.fetch
  let count = 0
  globalThis.fetch = async (_url, options) => {
    assert.equal(options?.credentials, 'same-origin'); count++
    return count === 2 ? new Response('<html>登录</html>', { headers: { 'content-type': 'text/html' } }) : new Response(png, { headers: { 'content-type': 'image/png' } })
  }
  try {
    assert.deepEqual((await readImage('https://example.com/image')).data, png)
    await assert.rejects(readImage('/login'))
    count = 0
    await assert.rejects(prepareSet([{ name: 'a', url: '/a' }, { name: 'b', url: '/b' }]))
    await assert.rejects(prepareSet([]))
    globalThis.fetch = async () => new Response('error', { status: 500 })
    await assert.rejects(readImage('/error'))
    globalThis.fetch = async (_url, options) => new Promise((_resolve, reject) => options?.signal?.addEventListener('abort', () => reject(new Error('aborted'))))
    await assert.rejects(readImage('/slow', 5), /aborted/)
  } finally { globalThis.fetch = original }
})

test('仓库示例 SVG 均可下载，整套成功保留实际格式', async () => {
  const { readdir, readFile } = await import('node:fs/promises')
  const folder = new URL('../public/samples/', import.meta.url)
  for (const file of await readdir(folder)) {
    if (file.endsWith('.svg')) assert.equal(imageExtension(new Uint8Array(await readFile(new URL(file, folder))), 'image/svg+xml'), 'svg')
  }
  const original = globalThis.fetch
  globalThis.fetch = async () => new Response(png, { headers: { 'content-type': 'image/png' } })
  try {
    const zip = await prepareSet([{ name: '第一张.jpg', url: '/first' }, { name: '第二张', url: '/second' }])
    assert.equal(zip.type, 'application/zip')
    const bytes = new Uint8Array(await zip.arrayBuffer()), view = new DataView(bytes.buffer)
    const filenameLength = view.getUint16(26, true)
    assert.equal(new TextDecoder().decode(bytes.slice(30, 30 + filenameLength)), '01-第一张.png')
    assert.equal(view.getUint16(bytes.length - 12, true), 2)
  } finally { globalThis.fetch = original }
})


test('合法 JPEG 结束标记后的附加字节下载时完整保留', async () => {
  const { readFile } = await import('node:fs/promises')
  const bytes = new Uint8Array(await readFile(new URL('./fixtures/jpeg-with-trailer.jpg', import.meta.url)))
  assert.equal(imageExtension(bytes, 'image/jpeg'), 'jpg')
  assert.notEqual(bytes.at(-1), 217)
  const original = globalThis.fetch
  globalThis.fetch = async () => new Response(bytes, { headers: { 'content-type': 'image/jpeg' } })
  try { assert.deepEqual((await readImage('/api/v1/files/test/content')).data, bytes) }
  finally { globalThis.fetch = original }
})

test('真实下载携带授权、走文件ID和服务端ZIP且保留顺序', async () => {
  const original = globalThis.fetch
  const ids = ['00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000002']
  const calls: string[] = []
  globalThis.fetch = async (url, options) => {
    calls.push(String(url))
    assert.equal(options?.credentials, 'include')
    if (options?.method === 'POST') {
      assert.deepEqual(JSON.parse(String(options.body)), { fileIds: ids, name: '套图' })
      return new Response(buildZip(ids.map((id) => ({ name: `${id}.png`, data: png }))))
    }
    return new Response(png, { headers: { 'content-type': 'image/png' } })
  }
  try {
    assert.deepEqual(new Uint8Array(await (await requestDownload('/api/v1/', [ids[0]])).arrayBuffer()), png)
    assert.equal((await requestDownload('/api/v1', ids, '套图')).type, 'application/zip')
    assert.deepEqual(calls, [`/api/v1/files/${ids[0]}/content?download=true`, '/api/v1/files/download-zip'])
    await assert.rejects(requestDownload('/api/v1', [undefined], '套图'), /标识/)
    assert.equal(calls.length, 2)
  } finally { globalThis.fetch = original }
})

test('真实下载拒绝授权错误、伪ZIP及数量不完整的套图', async () => {
  const original = globalThis.fetch
  const ids = ['00000000-0000-4000-8000-000000000001']
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({ message: '成员已停用' }), { status: 403 })
    await assert.rejects(requestDownload('/api/v1', ids, '套图'), /成员已停用/)
    globalThis.fetch = async () => new Response('<html>login</html>', { headers: { 'content-type': 'text/html' } })
    await assert.rejects(requestDownload('/api/v1', ids, '套图'), /响应无效/)
    globalThis.fetch = async () => new Response(buildZip([{ name: 'a.png', data: png }, { name: 'b.png', data: png }]))
    await assert.rejects(requestDownload('/api/v1', ids, '套图'), /不完整/)
    globalThis.fetch = async () => { throw new Error('断开连接') }
    await assert.rejects(requestDownload('/api/v1', ids, '套图'), /断开连接/)
  } finally { globalThis.fetch = original }
})
