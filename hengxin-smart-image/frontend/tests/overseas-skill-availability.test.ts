import test from 'node:test'
import assert from 'node:assert/strict'
import * as Management from '../src/api/overseas/management'
import { IdentityError } from '../src/api/identity/request'
import { compile, table, mount, all, text, find, click, flush } from './membership-test-harness'

const catalog = compile('views/overseas/admin/OverseasSkillCatalog.vue', { '@/components/core/tables/art-table/index.vue': { default: table, __esModule: true } })
const component = compile('views/overseas/admin/OverseasLiveSkills.vue', {
  '@/api/overseas/management': Management, '@/api/identity/request': { IdentityError },
  './OverseasSkillCatalog.vue': { default: catalog, __esModule: true }
})
const skill = { id: 's', name: 'test', displayName: '真实 Skill', description: '完整说明', enabled: true, version: 1 }
const button = (root: Parameters<typeof all>[0], label: string) => all(root).find(n => n.tag === 'ElButton' && text(n) === label)
const rows = (root: Parameters<typeof all>[0]) => find(root, 'ArtTable').props.data as Management.ManagedSkill[]
const notice = (root: Parameters<typeof all>[0]) => String(find(root, 'ElAlert').props.title)

test('所有者切换真实SFC：请求前状态不变、禁止重入、按服务端完整目录更新', async () => {
  let reads = 0, resolve!: (v: Management.SkillCatalog) => void
  const writes: unknown[] = []
  const api = { skills: async () => { reads++; return { items: [{ ...skill }], canToggle: true } },
    setSkillAvailability: async (...args: unknown[]) => { writes.push(args); return new Promise<Management.SkillCatalog>(r => { resolve = r }) } }
  const view = mount(component, { api }); await flush()
  try {
    assert.equal(rows(view.root)[0].enabled, true)
    const handler = button(view.root, '关闭')!.props.onClick as () => void
    handler(); handler(); click(view.root, '刷新 Skill'); await flush()
    assert.equal(writes.length, 1); assert.equal(reads, 1)
    assert.equal(rows(view.root)[0].enabled, true); assert.equal(button(view.root, '关闭')!.props.disabled, true)
    assert.deepEqual(writes[0], ['s', false, 1])
    resolve({ items: [{ ...skill, enabled: false, version: 2 }], canToggle: true }); await flush()
    assert.equal(rows(view.root)[0].enabled, false); assert.ok(button(view.root, '开启'))
    assert.match(notice(view.root), /状态已更新/)
  } finally { view.close() }
})

test('非所有者只读，Demo保留原两列且不伪造开关', async () => {
  let writes = 0
  const view = mount(component, { api: { skills: async () => ({ items: [skill], canToggle: false }), setSkillAvailability: async () => { writes++; throw Error('unexpected') } } })
  await flush()
  try { assert.equal(button(view.root, '关闭'), undefined); assert.equal(writes, 0); assert.match(text(view.root), /仅指定账号可调整/); assert.equal(rows(view.root)[0].enabled, true) } finally { view.close() }
  const demo = mount(catalog, { skills: [{ id: 'd', name: 'demo', displayName: '预览', description: '预览描述' }] })
  try { assert.equal((find(demo.root, 'ArtTable').props.columns as unknown[]).length, 2); assert.equal(button(demo.root, '开启'), undefined) } finally { demo.close() }
})

test('409冲突刷新最新状态和版本；只在用户再次操作时提交', async () => {
  let reads = 0, writes = 0
  const api = { skills: async () => ({ items: [{ ...skill, enabled: ++reads === 1, version: reads }], canToggle: true }),
    setSkillAvailability: async (_id: string, enabled: boolean, version: number) => {
      if (++writes === 1) throw new IdentityError(409, '版本冲突')
      assert.equal(enabled, true); assert.equal(version, 2)
      return { items: [{ ...skill, enabled, version: 3 }], canToggle: true }
    } }
  const view = mount(component, { api }); await flush()
  try {
    click(view.root, '关闭'); await flush(); assert.equal(reads, 2); assert.equal(writes, 1)
    assert.equal(rows(view.root)[0].version, 2); assert.match(notice(view.root), /已刷新最新状态/)
    click(view.root, '开启'); await flush(); assert.equal(writes, 2); assert.equal(rows(view.root)[0].enabled, true)
  } finally { view.close() }
})

test('403降级只读、401收起目录；未知结果读回失败阻止再次写入，刷新可恢复', async () => {
  for (const status of [401, 403]) {
    const failures: unknown[] = []
    const view = mount(component, { api: { skills: async () => ({ items: [skill], canToggle: true }), setSkillAvailability: async () => { throw new IdentityError(status, '权限变化') } }, onFailure: (e: unknown) => failures.push(e) })
    await flush(); click(view.root, '关闭'); await flush()
    try { assert.equal(button(view.root, '关闭'), undefined); assert.equal(failures.length, status === 401 ? 1 : 0); assert.match(notice(view.root), status === 401 ? /权限变化/ : /没有切换权限/) } finally { view.close() }
  }
  let reads = 0, failRefresh = true, writes = 0
  const view = mount(component, { api: { skills: async () => { if (++reads > 1 && failRefresh) throw Error('服务离线'); return { items: [skill], canToggle: true } }, setSkillAvailability: async () => { writes++; throw new IdentityError(0, '网络中断') } } })
  await flush(); click(view.root, '关闭'); await flush()
  try {
    assert.match(notice(view.root), /无法确认最新 Skill 状态/); assert.equal(button(view.root, '关闭'), undefined); assert.equal(writes, 1)
    failRefresh = false; click(view.root, '刷新 Skill'); await flush(); assert.ok(button(view.root, '关闭')); assert.equal(writes, 1)
  } finally { view.close() }
})

test('写入响应丢失按服务器结果恢复，卸载后迟到回包不产生反馈', async () => {
  let enabled = true, resolve!: (v: Management.SkillCatalog) => void
  const api = { skills: async () => ({ items: [{ ...skill, enabled }], canToggle: true }), setSkillAvailability: async () => { enabled = false; throw new IdentityError(500, '丢失响应') } }
  const view = mount(component, { api }); await flush(); click(view.root, '关闭'); await flush()
  try { assert.equal(rows(view.root)[0].enabled, false); assert.match(notice(view.root), /已刷新服务端状态/); assert.doesNotMatch(notice(view.root), /状态已更新/) } finally { view.close() }
  const late = mount(component, { api: { ...api, setSkillAvailability: () => new Promise<Management.SkillCatalog>(r => { resolve = r }) } })
  await flush(); click(late.root, '开启'); late.close(); resolve({ items: [skill], canToggle: true }); await flush()
  assert.equal(all(late.root).filter(n => n.tag === 'ElAlert').length, 0)
})

test('系统配置默认选项只列开启项；既有关闭绑定显示不可用且保存被挡', async () => {
  const settingsComponent = compile('views/overseas/admin/OverseasLiveSettings.vue', {
    '@/api/overseas/management': Management, '@/api/identity/auth': { IdentityError }, 'element-plus': { ElMessage: { success() {} } }
  })
  const settings: Management.Settings = { version: 1, paused: false, concurrency: 1, timeoutSeconds: 60, defaults: { analysis: 'closed', generation: null, revision: null }, autoCleanup: false }
  let writes = 0
  const view = mount(settingsComponent, { api: { settings: async () => settings, skills: async () => ({ items: [skill, { ...skill, id: 'closed', displayName: '关闭项', enabled: false }], canToggle: false }), saveSettings: async () => { writes++; return settings } } })
  await flush()
  try {
    const options = all(view.root).filter(n => n.tag === 'ElOption')
    assert.equal(options.some(n => n.props.label === '关闭项'), false)
    assert.ok(options.some(n => n.props.label === '当前绑定不可用，请重新选择' && 'disabled' in n.props))
    click(view.root, '保存配置'); await flush(); assert.equal(writes, 0); assert.match(notice(view.root), /默认 Skill/)
  } finally { view.close() }
})

test('失效选择使用可读占位而非内部ID，显式清空；可用选择及禁用状态保持', async () => {
  const selector = compile('views/overseas/studio/StudioSkillSelect.vue', {})
  const updates: string[] = []
  const stale = mount(selector, { skills: [], modelValue: 'internal-id', disabled: false, 'onUpdate:modelValue': (v: string) => updates.push(v) })
  try {
    assert.equal(find(stale.root, 'ElSelect').props['model-value'], '')
    assert.equal(find(stale.root, 'ElSelect').props.placeholder, '所选 Skill 已不可用')
    click(stale.root, '清空 Skill 选择'); assert.deepEqual(updates, [''])
  } finally { stale.close() }
  const locked = mount(selector, { skills: [], modelValue: 'internal-id', disabled: true })
  try { assert.equal(button(locked.root, '清空 Skill 选择')?.props.disabled, true) } finally { locked.close() }
  const available = mount(selector, { skills: [skill], modelValue: skill.id, disabled: false })
  try { assert.equal(find(available.root, 'ElSelect').props['model-value'], skill.id); assert.equal(button(available.root, '清空 Skill 选择'), undefined) } finally { available.close() }
})
