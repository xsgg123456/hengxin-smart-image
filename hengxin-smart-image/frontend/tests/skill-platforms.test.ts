import test from 'node:test'
import assert from 'node:assert/strict'
import { createManagementApi, isSkillCatalog, type ManagedSkill, type SkillPlatformUpdate } from '../src/api/overseas/management'
import { IdentityError } from '../src/api/identity/request'
import { liveSkillsComponent, confirmation } from './skill-platforms-components'
import { all, click, find, flush, mount, text, update } from './membership-test-harness'
const initial: ManagedSkill[] = [
  { id: 'a', name: 'amazon', displayName: '亚马逊主图', description: '灯具完整说明', enabled: true, version: 1, platforms: ['Amazon'] },
  { id: 'b', name: 'wayfair', displayName: '威费尔主图', description: '家具完整说明', enabled: false, version: 1, platforms: ['Wayfair'] },
  { id: 'c', name: 'unknown', displayName: '未分组安装项', description: '完整长描述', enabled: true, version: 1, platforms: [] }
]
function fixture() {
  let skills = structuredClone(initial), mode = '', manage = true, reads = 0
  const writes: SkillPlatformUpdate[][] = []
  const catalog = () => ({ items: structuredClone(skills), canToggle: false, canManagePlatforms: manage })
  const api = {
    skills: async () => { reads++; if (mode === 'read-failure' && writes.length) throw Error('目录暂不可用'); return catalog() },
    setSkillAvailability: async () => { throw Error('不应切换') },
    setSkillPlatforms: async (items: SkillPlatformUpdate[]) => {
      writes.push(structuredClone(items))
      if (mode === '409') { skills[0].version++; throw new IdentityError(409, '版本冲突') }
      if (mode === '503' || mode === 'read-failure') throw new IdentityError(503, '服务中断')
      if (mode === '403') throw new IdentityError(403, '权限变化')
      for (const input of items) { const s = skills.find(s => s.id === input.id)!; assert.equal(s.version, input.version); s.platforms = [...input.platforms]; s.version++ }
      return catalog()
    }
  }
  const view = mount(liveSkillsComponent, { api })
  return { ...view, writes, reads: () => reads, setMode: (value: string) => { mode = value }, readonly: () => { manage = false }, skills: () => skills }
}
const rows = (root: Parameters<typeof find>[0]) => find(root, 'ArtTable').props.data as ManagedSkill[]
const select = (root: Parameters<typeof find>[0], skills: ManagedSkill[]) => (find(root, 'ArtTable').props.onSelectionChange as (rows: ManagedSkill[]) => void)(skills)
const firstClick = (root: Parameters<typeof find>[0], label: string) => click(root, label)

test('真实目录按平台、名称/描述、状态筛选，跨筛选保留批量选中并提示', async () => {
  const view = fixture(); await flush()
  try {
    assert.equal(rows(view.root).length, 3)
    select(view.root, [initial[0], initial[1]]); update(find(view.root, 'ElTabs'), 'Amazon'); await flush()
    assert.equal(rows(view.root).length, 1); assert.match(text(view.root), /另有 1 项已选/)
    click(view.root, '批量设置平台（2）'); await flush()
    update(find(view.root, 'ElCheckboxGroup'), ['Walmart', 'Shopee']); await flush()
    click(view.root, '保存平台设置'); await flush()
    assert.equal(view.writes.length, 1); assert.equal(view.writes[0].length, 2)
    assert.deepEqual(view.skills()[0].platforms, ['Walmart', 'Shopee']); assert.deepEqual(view.skills()[1].platforms, ['Walmart', 'Shopee'])
    assert.equal(all(view.root).some(n => n.tag === 'ElDialog'), false)
    update(find(view.root, 'ElTabs'), 'none'); await flush(); assert.deepEqual(rows(view.root).map(s => s.id), ['c'])
    update(find(view.root, 'ElTabs'), 'all'); update(find(view.root, 'ElInput', '搜索 Skill'), '家具'); await flush(); assert.deepEqual(rows(view.root).map(s => s.id), ['b'])
    update(find(view.root, 'ElSelect', '筛选启用状态'), 'enabled'); await flush(); assert.equal(rows(view.root).length, 0)
    assert.match(String(find(view.root, 'ArtTable').props['empty-text']), /调整筛选/)
  } finally { view.close() }
})

test('添加并集、跨搜索保留候选，移出确认只删除当前平台关联，取消不提交', async () => {
  const view = fixture(); await flush()
  try {
    update(find(view.root, 'ElTabs'), 'Amazon'); await flush(); click(view.root, '添加 Skill 到此平台'); await flush()
    update(find(view.root, 'ElCheckboxGroup'), ['b']); update(find(view.root, 'ElInput', '搜索待添加 Skill'), '未分组'); await flush()
    assert.match(text(view.root), /另有 1 个已选 Skill 被搜索隐藏/)
    click(view.root, '添加到 Amazon（1）'); await flush(); assert.deepEqual(view.skills()[1].platforms, ['Wayfair', 'Amazon'])
    update(find(view.root, 'ElInput', '搜索 Skill'), '威费尔'); await flush()
    confirmation.accept = false; firstClick(view.root, '移出平台'); await flush(); assert.equal(view.writes.length, 1)
    confirmation.accept = true; firstClick(view.root, '移出平台'); await flush(); assert.deepEqual(view.skills()[1].platforms, ['Wayfair'])
  } finally { confirmation.accept = true; view.close() }
})

test('单项编辑保存失败与409不关闭、不丢草稿；新版本只在明确重试时提交', async () => {
  const view = fixture(); await flush()
  try {
    firstClick(view.root, '编辑平台'); await flush(); update(find(view.root, 'ElCheckboxGroup'), ['Mercado Libre']); await flush()
    view.setMode('409'); click(view.root, '保存平台设置'); await flush()
    assert.equal(view.writes.length, 1); assert.equal(view.reads(), 2)
    assert.deepEqual(find(view.root, 'ElCheckboxGroup').props.modelValue, ['Mercado Libre'])
    assert.ok(all(view.root).some(n => n.tag === 'ElAlert' && String(n.props.title).includes('草稿和勾选已保留')))
    view.setMode('503'); click(view.root, '保存平台设置'); await flush(); assert.equal(view.writes[1][0].version, 2)
    assert.deepEqual(view.skills()[0].platforms, ['Amazon'])
    view.setMode(''); click(view.root, '保存平台设置'); await flush()
    assert.deepEqual(view.skills()[0].platforms, ['Mercado Libre']); assert.equal(all(view.root).some(n => n.tag === 'ElDialog'), false)
  } finally { view.close() }
})

test('平台管理权限独立于开关；403收回保存权限且保留草稿', async () => {
  const view = fixture(); await flush()
  try {
    assert.equal(all(view.root).some(n => n.tag === 'ElButton' && text(n) === '关闭'), false)
    firstClick(view.root, '编辑平台'); await flush(); view.setMode('403'); click(view.root, '保存平台设置'); await flush()
    const save = all(view.root).find(n => n.tag === 'ElButton' && text(n) === '保存平台设置')!
    assert.equal(save.props.disabled, true); assert.deepEqual(find(view.root, 'ElCheckboxGroup').props.modelValue, ['Amazon'])
    click(view.root, '保存平台设置'); await flush(); assert.equal(view.writes.length, 1)
    click(view.root, '取消'); view.readonly(); click(view.root, '刷新 Skill'); await flush()
    assert.equal(all(view.root).some(n => n.tag === 'ElButton' && text(n) === '编辑平台'), false)
  } finally { view.close() }
})

test('平台PATCH只发送版本、ID与平台，返回严格校验且保留HTTP冲突', async () => {
  const result = { items: initial, canToggle: false, canManagePlatforms: true }
  const api = createManagementApi(async (url, options) => {
    assert.equal(url, '/api/overseas/v1/management/skills/platforms'); assert.equal(options?.method, 'PATCH')
    assert.equal(options?.credentials, 'include')
    assert.deepEqual(JSON.parse(String(options?.body)), { items: [{ id: 'a', version: 1, platforms: ['Wayfair'] }] })
    return new Response(JSON.stringify(result))
  })
  assert.deepEqual(await api.setSkillPlatforms([{ id: 'a', version: 1, platforms: ['Wayfair'] }]), result)
  assert.equal(isSkillCatalog({ ...result, canManagePlatforms: undefined }), false)
  for (const platforms of [undefined, 'Amazon', [1]]) assert.equal(isSkillCatalog({ ...result, items: [{ ...initial[0], platforms }] }), false)
  await assert.rejects(createManagementApi(async () => new Response('{}', { status: 409 })).setSkillPlatforms([]), (e: unknown) => e instanceof IdentityError && e.status === 409)
})


test('写入和读回同时失败，弹窗内刷新最新目录恢复权限且保留草稿后重试', async () => {
  const view = fixture(); await flush()
  try {
    firstClick(view.root, '编辑平台'); await flush(); update(find(view.root, 'ElCheckboxGroup'), ['Amazon', 'Wayfair', 'Walmart']); await flush()
    view.setMode('read-failure'); click(view.root, '保存平台设置'); await flush()
    assert.ok(all(view.root).some(n => n.tag === 'ElAlert' && String(n.props.title).includes('无法确认最新平台归属')))
    assert.deepEqual(find(view.root, 'ElCheckboxGroup').props.modelValue, ['Amazon', 'Wayfair', 'Walmart'])
    view.setMode(''); click(view.root, '刷新最新目录'); await flush()
    assert.deepEqual(find(view.root, 'ElCheckboxGroup').props.modelValue, ['Amazon', 'Wayfair', 'Walmart'])
    click(view.root, '保存平台设置'); await flush()
    assert.deepEqual(view.skills()[0].platforms, ['Amazon', 'Wayfair', 'Walmart'])
    assert.equal(all(view.root).some(n => n.tag === 'ElDialog'), false)
  } finally { view.close() }
})
