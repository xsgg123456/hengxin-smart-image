import test, { type TestContext } from 'node:test'
import assert from 'node:assert/strict'
import { createHash, webcrypto } from 'node:crypto'
import { randomUUID, sha256 } from '../src/utils/browser-crypto'
import { createRequestKeys } from '../src/api/overseas/tasks'
import { broadcastLogout } from '../src/api/hengxin/identity-lifecycle'
import { scanFolder } from '../src/views/overseas/admin/skill-folder-read'
import { prepareFolderSave, verifyFolder, writeFolder } from '../src/views/overseas/admin/skill-folder-save'
import { dirNode, fileNode, MemoryDirectory } from './skill-folders-fixture'

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
function replaceGlobal(t: TestContext, key: string, value: unknown) {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, key)
  Object.defineProperty(globalThis, key, { configurable: true, value })
  t.after(() => {
    if (descriptor) Object.defineProperty(globalThis, key, descriptor)
    else Reflect.deleteProperty(globalThis, key)
  })
}
function httpCrypto(t: TestContext) {
  const crypto = { getRandomValues: webcrypto.getRandomValues.bind(webcrypto) }
  replaceGlobal(t, 'crypto', crypto)
  return crypto
}

test('原生 UUID 优先且保留 Crypto 方法接收者', t => {
  const crypto = { randomUUID() { assert.equal(this, crypto); return 'native-uuid' }, getRandomValues() { throw Error('不应使用回退') } }
  replaceGlobal(t, 'crypto', crypto)
  assert.equal(randomUUID(), 'native-uuid')
})

test('HTTP 缺少原生 UUID 时使用安全随机源，保持 RFC 4122 version/variant 和随机性', t => {
  const crypto = httpCrypto(t)
  t.mock.method(Math, 'random', () => { throw Error('不得使用 Math.random') })
  const values = Array.from({ length: 2048 }, randomUUID)
  assert.equal(new Set(values).size, values.length)
  assert.ok(values.every(value => uuidPattern.test(value)))
  assert.equal('randomUUID' in crypto, false)
  assert.equal('subtle' in crypto, false)
})

test('UUID 位掩码保留其余随机位，没有安全随机源时拒绝生成', t => {
  replaceGlobal(t, 'crypto', { getRandomValues(bytes: Uint8Array) { return bytes.fill(255) } })
  assert.equal(randomUUID(), 'ffffffff-ffff-4fff-bfff-ffffffffffff')
  Object.defineProperty(globalThis, 'crypto', { configurable: true, value: undefined })
  assert.throws(randomUUID, /安全随机数/)
})

test('HTTP 下任务请求键保持重试幂等且退出通知可跨标签广播', t => {
  httpCrypto(t)
  const keys = createRequestKeys(), first = keys.for({ task: 'A' })
  assert.match(first, uuidPattern)
  assert.equal(keys.for({ task: 'A' }), first)
  assert.notEqual(keys.for({ task: 'B' }), first)
  keys.clear()
  assert.notEqual(keys.for({ task: 'A' }), first)
  const writes: [string, string][] = []
  replaceGlobal(t, 'localStorage', { setItem(key: string, value: string) { writes.push([key, value]) } })
  broadcastLogout(); broadcastLogout()
  assert.equal(writes.length, 2)
  assert.ok(writes.every(([key, value]) => key === 'hengxin:logout' && uuidPattern.test(value)))
  assert.notEqual(writes[0][1], writes[1][1])
})

test('SHA-256 原生与 HTTP 回退对空、Unicode、二进制和跨分块输入逐字节一致', async t => {
  const vectors = [new Uint8Array(), new TextEncoder().encode('abc'), new TextEncoder().encode('恒鑫\u0000🖼️\r\n'), new Uint8Array([0, 255, 128, 13, 10, 0, 254]), Uint8Array.from({ length: 1025 }, (_, i) => i % 256)]
  const expected = vectors.map(bytes => createHash('sha256').update(bytes).digest('hex'))
  assert.equal(expected[0], 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')
  assert.equal(expected[1], 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
  let nativeCalls = 0
  const subtle = { digest(algorithm: string, bytes: ArrayBuffer) { assert.equal(this, subtle); nativeCalls++; return webcrypto.subtle.digest(algorithm, bytes) } }
  replaceGlobal(t, 'crypto', { subtle })
  for (const [index, bytes] of vectors.entries()) assert.equal(await sha256(bytes.buffer), expected[index])
  assert.equal(nativeCalls, vectors.length)
  Object.defineProperty(globalThis, 'crypto', { configurable: true, value: { getRandomValues: webcrypto.getRandomValues.bind(webcrypto) } })
  for (const [index, bytes] of vectors.entries()) assert.equal(await sha256(bytes.buffer), expected[index])
  assert.equal(nativeCalls, vectors.length)
})

test('原生摘要失败不静默绕过错误', async t => {
  replaceGlobal(t, 'crypto', { subtle: { digest() { throw Error('摘要操作失败') } } })
  await assert.rejects(sha256(new ArrayBuffer(0)), /摘要操作失败/)
})

test('HTTP 下技能扫描、保存读回及损坏拒绝保持完整性校验', async t => {
  httpCrypto(t)
  const bytes = new Uint8Array([0, 255, 128, 0, 13, 10])
  const folder = await scanFolder(dirNode('HTTP技能', [fileNode('SKILL.md'), dirNode('empty', []), fileNode('原图.bin', bytes)]))
  assert.deepEqual(folder.entries['原图.bin'], { size: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') })
  assert.deepEqual(folder.entries['empty/'], { directory: true })
  const descriptor = { ...folder, release: 'http-release', checksum: 'fixed-checksum' }
  const save = await prepareFolderSave(new MemoryDirectory('下载'), 'skill', descriptor)
  await writeFolder(save, { file: async (_id, _release, path) => folder.files.get(path)!.arrayBuffer() }, () => {})
  await verifyFolder(save)
  await assert.rejects(writeFolder(save, { file: async () => new ArrayBuffer(0) }, () => {}), /下载内容校验失败/)
})
