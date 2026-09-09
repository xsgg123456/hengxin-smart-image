import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createMockService } from '../src/api/hengxin/mock'
import { createHttpService } from '../src/api/hengxin/http'
import { sampleImages } from '../src/api/hengxin/fixtures'
import { MAX_IMAGE_BYTES } from '../src/api/hengxin/limits'
import type { TemplateInput } from '../src/types/hengxin'

const draft: TemplateInput = { name: '测试模板', mode: 'wallpaper', images: sampleImages('wallpaper', 2),
  skillVersionId: null, notes: '保持边框', active: true }
const taskInput = { mode: 'wallpaper' as const, name: '测试任务', sources: sampleImages('wallpaper', 1), note: '', sku: 'SKU-123' }
const file = () => new File([Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGL5//8/AwMDEwMYAAAAAP//aYxtrAAAAAZJREFUAwAkMAMEkRkhTQAAAABJRU5ErkJggg==', 'base64')], 'pixel.png', { type: 'image/png' })

test('模板分页/筛选/排序，页界互斥且查询不污染存量', async t => {
  const service = createMockService({ delayMs: 0, empty: true }); t.after(() => service.dispose())
  for (let i = 0; i < 15; i++) await service.saveTemplate({ ...draft, name: `模板 ${String(i).padStart(2, '0')}` })
  const a = await service.listTemplates({ page: 1, pageSize: 12, sort: 'name' })
  const b = await service.listTemplates({ page: 2, pageSize: 12, sort: 'name' })
  assert.equal(a.total, 15); assert.equal(a.items.length, 12); assert.equal(b.items.length, 3)
  assert.equal(new Set([...a.items, ...b.items].map(item => item.id)).size, 15)
  assert.equal((await service.listTemplates({ page: 1, pageSize: 12, search: '  03 ' })).total, 1)
  assert.equal((await service.listTemplates({ page: 1, pageSize: 12, mode: 'product' })).total, 0)
  assert.equal((await service.listTemplates({ page: 1, pageSize: 12, activeOnly: true })).total, 0)
  a.items[0].name = '篡改'; assert.notEqual((await service.getTemplate(a.items[0].id)).name, '篡改')
  await assert.rejects(service.listTemplates({ page: 0, pageSize: 12 }), { code: 'VALIDATION' })
})

test('草稿不可生成，类型匹配 Skill、版本冲突及历史快照不被编辑删除覆盖', async t => {
  const service = createMockService({ delayMs: 0 }); t.after(() => service.dispose())
  const initial = await service.saveTemplate(draft)
  assert.equal(initial.active, false); assert.equal(initial.skillVersionId, null)
  await assert.rejects(service.createTask({ ...taskInput, templateId: initial.id }), { code: 'VALIDATION' })
  await assert.rejects(service.saveTemplate({ ...draft, skillVersionId: 'mock-product-1' }), { code: 'SKILL_UNAVAILABLE' })
  const linked = await service.saveTemplate({ ...draft, id: initial.id, expectedVersion: 1, skillVersionId: 'mock-wallpaper-1' })
  assert.equal(linked.version, 2); assert.equal(linked.active, true)
  await assert.rejects(service.createTask({ ...taskInput, templateId: linked.id, templateVersion: 1 }), { code: 'CONFLICT' })
  const accepted = await service.createTask({ ...taskInput, templateId: linked.id, templateVersion: 2 })
  const snapshot = (await service.getWorkspace()).tasks.find(task => task.id === accepted.taskId)!
  assert.equal(snapshot.templateVersion, 2); assert.equal(snapshot.skillVersionId, 'mock-wallpaper-1'); assert.equal(snapshot.sku, 'SKU-123')
  const edited = await service.saveTemplate({ ...draft, id: linked.id, expectedVersion: 2, name: '新版模板', images: sampleImages('wallpaper', 4), skillVersionId: 'mock-wallpaper-1' })
  assert.equal(edited.version, 3)
  await assert.rejects(service.saveTemplate({ ...draft, id: linked.id, expectedVersion: 2 }), { code: 'CONFLICT' })
  await service.deleteTemplate(linked.id)
  await assert.rejects(service.getTemplate(linked.id), { code: 'NOT_FOUND' })
  await assert.rejects(service.createTask({ ...taskInput, templateId: linked.id }), { code: 'VALIDATION' })
  const current = (await service.getWorkspace()).tasks.find(task => task.id === accepted.taskId)!
  assert.equal(current.templateVersion, 2); assert.equal(current.template, snapshot.template)
  assert.deepEqual(current.sources, snapshot.sources); assert.equal(current.images.length, 2)
  assert.deepEqual(current.templateSnapshot, linked)
  assert.deepEqual(current.templateSnapshot?.images, draft.images)
})

test('无 Skill 场景允许草稿但阻止文字默认与模板执行', async t => {
  const service = createMockService({ delayMs: 0, scenario: 'no-skills' }); t.after(() => service.dispose())
  assert.deepEqual(await service.listSkills(), [])
  assert.equal((await service.saveTemplate(draft)).active, false)
  assert.equal((await service.listTemplates({ page: 1, pageSize: 12, activeOnly: true })).total, 0)
  await assert.rejects(service.createTask({ ...taskInput, mode: 'text', note: '替换标题' }), { code: 'SKILL_UNAVAILABLE' })
})

test('上传 MIME/大小/空文件、文件引用及20张边界，文字输出数等于输入', async t => {
  const service = createMockService({ delayMs: 0 }); t.after(() => service.dispose())
  for (const invalid of [new File([], 'a.png', { type: 'image/png' }), new File(['x'], 'a.svg', { type: 'image/svg+xml' }),
    new File([new Uint8Array(MAX_IMAGE_BYTES + 1)], 'a.png', { type: 'image/png' })]) {
    await assert.rejects(service.uploadFile(invalid), { code: 'VALIDATION' })
  }
  const picture = await service.uploadFile(file()); assert.ok(picture.fileId); assert.match(picture.url, /^blob:/)
  await assert.rejects(service.createTask({ ...taskInput, templateId: 't1', sources: [{ name: '伪造', url: '/fake' }] }), { code: 'VALIDATION' })
  await assert.rejects(service.createTask({ ...taskInput, mode: 'text', note: '替换标题', sources: Array(21).fill(picture) }), { code: 'VALIDATION' })
  const accepted = await service.createTask({ ...taskInput, mode: 'text', note: '替换标题', sources: Array(20).fill({ ...picture, url: '/tampered' }) })
  const task = (await service.getWorkspace()).tasks.find(task => task.id === accepted.taskId)!
  assert.equal(task.images.length, 20); assert.equal(task.skillVersionId, 'mock-text-1'); assert.equal(task.sources[0].url, picture.url)
})

test('模拟失败可重试，失败操作没有写入副作用', async t => {
  for (const scenario of ['upload-error', 'save-error', 'submit-error', 'list-error'] as const) {
    const service = createMockService({ delayMs: 0, scenario }); t.after(() => service.dispose())
    const before = await service.getWorkspace()
    const action = () => scenario === 'upload-error' ? service.uploadFile(file()) : scenario === 'save-error' ? service.saveTemplate(draft)
      : scenario === 'list-error' ? service.listTemplates({ page: 1, pageSize: 12 }) : service.createTask({ ...taskInput, templateId: 't1' })
    await assert.rejects(action(), { code: 'SIMULATED_FAILURE' })
    assert.deepEqual(await service.getWorkspace(), before)
    await action()
  }
})

test('HTTP 模板查询、创建POST/编辑PUT、Skill目录、文件multipart契约及坏响应', async () => {
  const sample = { ...draft, id: 't/1', skill: '', ownerId: 'u1', version: 1, updatedAt: '2026-09-09T00:00:00Z' }
  const urls: string[] = []
  const service = createHttpService('/api/v1', async (url, init) => {
    urls.push(String(url))
    let body: unknown = sample
    if (String(url).endsWith('/files')) {
      assert.ok(init?.body instanceof FormData); assert.ok(init.body.get('file') instanceof File)
      assert.equal(new Headers(init.headers).get('content-type'), null)
      body = { fileId: 'f1', name: 'pixel.png', url: '/files/f1' }
    } else if (String(url).includes('/templates?')) body = { items: [sample], total: 1, page: 2, pageSize: 12 }
    else if (String(url).includes('/skills')) body = []
    else if (init?.method !== 'GET') {
      assert.equal(init?.method, String(url).endsWith('/t%2F1') ? 'PUT' : 'POST')
      assert.equal(new Headers(init?.headers).get('content-type'), 'application/json')
    }
    return new Response(JSON.stringify(body), { headers: { 'content-type': 'application/json' } })
  })
  await service.listTemplates({ page: 2, pageSize: 12, search: 'A&B', activeOnly: true })
  assert.match(urls[0], /search=A%26B/)
  await service.getTemplate('t/1'); await service.saveTemplate(draft); await service.saveTemplate({ ...draft, id: 't/1', expectedVersion: 1 })
  await service.listSkills('text'); await service.uploadFile(file())
  const bad = createHttpService('/api/v1', async () => new Response('{}', { headers: { 'content-type': 'application/json' } }))
  await assert.rejects(bad.listTemplates({ page: 1, pageSize: 12 }), { code: 'INVALID_RESPONSE' })
  await assert.rejects(bad.listSkills(), { code: 'INVALID_RESPONSE' })
  await assert.rejects(bad.uploadFile(file()), { code: 'INVALID_RESPONSE' })
})
