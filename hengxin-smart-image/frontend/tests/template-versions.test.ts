import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createMockService } from '../src/api/hengxin/mock'
import { createHttpService } from '../src/api/hengxin/http'
import { createHttpManagement } from '../src/api/management'
import { sampleImages } from '../src/api/hengxin/fixtures'
import type { TemplateInput } from '../src/types/hengxin'

const user = { id: 'mock-super-admin', name: '超管', role: 'super_admin' as const, status: 'active' as const }
const input: TemplateInput = { name: '默认绑定模板', mode: 'wallpaper', images: sampleImages('wallpaper', 2), skillVersionId: null, active: true, notes: '' }

test('默认绑定在保存时冻结；清除默认不改旧版本，重新保存变草稿并保留图片顺序历史', async t => {
  const service = createMockService({ user, delayMs: 0, empty: true })
  t.after(() => service.dispose())
  const first = await service.saveTemplate(input)
  assert.equal(first.skillBinding, 'module_default')
  assert.equal(first.skillVersionId, 'mock-wallpaper-1')
  assert.equal(first.active, true)
  const defaults = await service.getSkillDefaults()
  await service.saveSkillDefaults({ ...defaults, wallpaper: null })
  assert.deepEqual(await service.getTemplate(first.id), first)
  const second = await service.saveTemplate({ ...input, id: first.id, expectedVersion: 1, images: [...input.images].reverse() })
  assert.equal(second.skillVersionId, null); assert.equal(second.active, false)
  const history = await service.getTemplateVersions(first.id)
  assert.deepEqual(history.map(v => v.version), [2, 1])
  assert.deepEqual(history[1], first)
  assert.deepEqual(history[0].images, [...first.images].reverse())
  history[1].name = '不能改写历史'
  assert.equal((await service.getTemplateVersions(first.id))[1].name, first.name)
})

test('专用绑定优先于默认，默认管理拒绝越权和跨类型', async t => {
  const service = createMockService({ user, delayMs: 0, empty: true })
  const reader = createMockService({ user: { ...user, role: 'designer' }, delayMs: 0 })
  t.after(() => { service.dispose(); reader.dispose() })
  const defaults = await service.getSkillDefaults()
  await assert.rejects(reader.getSkillDefaults(), { code: 'FORBIDDEN' })
  await assert.rejects(reader.saveSkillDefaults(defaults), { code: 'FORBIDDEN' })
  await assert.rejects(service.saveSkillDefaults({ ...defaults, wallpaper: 'mock-product-1' }), { code: 'VALIDATION' })
  await service.saveSkillDefaults({ ...defaults, wallpaper: null })
  const saved = await service.saveTemplate({ ...input, skillVersionId: 'mock-wallpaper-1' })
  assert.equal(saved.skillBinding, 'specific'); assert.equal(saved.active, true)
  await service.setSkillStatus('mock-wallpaper-1', 'disabled')
  const draft = await service.saveTemplate({ ...input, id: saved.id, expectedVersion: 1, skillVersionId: 'mock-wallpaper-1' })
  assert.equal(draft.active, false); assert.equal(draft.skillVersionId, 'mock-wallpaper-1')
})

test('历史与默认HTTP契约编码路径、校验返回数据，错误不能伪装成功', async () => {
  const urls: string[] = []
  const defaults = { wallpaper: 'version-1', product: null, text: null }
  const api = createHttpManagement('/api/v1', async (url, init) => {
    urls.push(String(url))
    if (init?.method === 'PUT') assert.deepEqual(JSON.parse(String(init.body)), defaults)
    return Response.json(defaults)
  })
  assert.deepEqual(await api.getSkillDefaults(), defaults)
  assert.deepEqual(await api.saveSkillDefaults(defaults), defaults)
  assert.deepEqual(urls, ['/api/v1/management/skills/defaults', '/api/v1/management/skills/defaults'])
  const service = createHttpService('/api/v1', async url => { assert.equal(String(url), '/api/v1/templates/a%2Fb/versions'); return Response.json([]) })
  assert.deepEqual(await service.getTemplateVersions('a/b'), [])
  await assert.rejects(createHttpManagement('', async () => Response.json({ wallpaper: null })).getSkillDefaults(), { code: 'INVALID_RESPONSE' })
  await assert.rejects(createHttpService('', async () => Response.json([{}])).getTemplateVersions('x'), { code: 'INVALID_RESPONSE' })
})
