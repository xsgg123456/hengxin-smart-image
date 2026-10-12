import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createPicturesApi, pictureFilename, isPictureList, pictureUrl, canArchive, type Picture, type PictureCommand } from '../src/api/overseas/pictures'
const picture: Picture = { id: 'p1', taskId: 't1', sku: 'A', position: 0, title: '主图', version: 1, status: 'ready', approved: true, url: pictureUrl('p1', 1), width: 32, height: 32, history: [{ version: 1, url: pictureUrl('p1', 1), width: 32, height: 32, note: '', createdAt: '' }] }
test('图片严格同源版本资源、任务隔离、空产物不得冒充ready', async () => {
 assert.ok(isPictureList({ items: [picture], taskVersion: 2 }))
 for (const p of [{ ...picture, url: 'https://other.test/a.png' }, { ...picture, url: pictureUrl('p2', 1) }, { ...picture, status: 'unknown' }, { ...picture, version: 0, url: null }, { ...picture, width: 0 }]) assert.equal(isPictureList({ items: [p], taskVersion: 2 }), false)
 assert.equal(isPictureList({ items: [picture, picture], taskVersion: 2 }), false)
 const empty = { ...picture, version: 0, url: null, width: null, height: null, approved: false, status: 'failed', history: [] }
 assert.ok(isPictureList({ items: [empty], taskVersion: 2 }))
 assert.equal(canArchive([picture], 'review'), true); assert.equal(canArchive([], 'review'), false); assert.equal(canArchive([picture], 'archived'), false)
 for (const status of ['pending', 'reworking', 'failed'] as const) assert.equal(canArchive([{ ...picture, status }], 'review'), false)
 await assert.rejects(createPicturesApi(async () => new Response(JSON.stringify({ items: [picture], taskVersion: 2 }))).list('other'))
})
test('所有写请求冻结版本/完整标注及幂等键，二进制下载鉴权且禁缓存', async () => {
 const calls: { url: string; options?: RequestInit }[] = []
 const task = { id: 't1', name: '', productName: '', brand: '', platform: '', market: '', remarks: '', skus: [{ code: 'A' }], status: 'review', version: 3, createdAt: '', updatedAt: '', createdBy: { id: 'a', name: 'A' }, designer: { id: 'a', name: 'A', status: 'active', eligible: true }, capabilities: [], events: [] }
 const api = createPicturesApi(async (url, options) => { calls.push({ url: String(url), options }); return new Response(JSON.stringify(task)) })
 const command: PictureCommand = { kind: 'revision', taskId: 't1', pictureId: 'p1', version: 1, taskVersion: 2, sku: 'A', note: '保留完整意见', marks: [{ id: 'm', kind: 'rect', x: 1, y: 2, width: 3, height: 4, note: '调整', points: [] }] }
 for (const kind of ['revision', 'approve', 'retry', 'archive'] as const) await api.command({ ...command, kind }, `key-${kind}`)
 assert.deepEqual(JSON.parse(String(calls[0].options?.body)), { version: 1, taskVersion: 2, note: command.note, marks: command.marks })
 assert.deepEqual(JSON.parse(String(calls[2].options?.body)), { version: 2, sku: 'A' }); assert.deepEqual(JSON.parse(String(calls[3].options?.body)), { version: 2 })
 await api.content('p1', 1); await api.download('archive/1')
 assert.equal(calls[4].url, '/api/overseas/v1/pictures/p1/versions/1/content?download=true'); assert.equal(calls[5].url, '/api/overseas/v1/archives/archive%2F1/download')
 for (const c of calls) { assert.equal(c.options?.credentials, 'include'); assert.equal(c.options?.cache, 'no-store') }
 for (const status of [401, 403, 409, 500]) await assert.rejects(createPicturesApi(async () => new Response('{}', { status })).command(command, 'same'), (e: unknown) => !!e && typeof e === 'object' && 'status' in e && e.status === status)
})

test('下载文件名保留实际图片格式', () => {
 assert.equal(pictureFilename('p', 2, 'image/jpeg'), 'p-v2.jpg'); assert.equal(pictureFilename('p', 1, 'image/webp'), 'p-v1.webp'); assert.equal(pictureFilename('p', 1, 'image/png'), 'p-v1.png')
})
