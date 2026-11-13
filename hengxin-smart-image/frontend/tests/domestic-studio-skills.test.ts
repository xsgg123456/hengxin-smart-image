import test from 'node:test'
import assert from 'node:assert/strict'
import { IdentityError } from '../src/api/identity/request'
import { createDomesticStudioSkillsApi, type WorkspaceBindings } from '../src/api/hengxin/domestic-studio-skills'
import { domesticWorkspaces } from '../src/api/hengxin/domestic-workspaces'
import { click, compile, find, flush, mount, text, update } from './membership-test-harness'
import { liveSkillsComponent, skillCatalogComponent } from './skill-platforms-components'

const empty = (): WorkspaceBindings => ({ camera: null, case: null, product: null, scene: null, phone: null })
const skill = { id: 'a', name: 'camera', displayName: '相机技能', description: '测试', enabled: true, version: 1, platforms: [] }
const component = compile('views/hengxin/admin/DomesticStudioBindings.vue', {
  '@/api/identity/request': { IdentityError },
  '@/api/hengxin/domestic-workspaces': { domesticWorkspaces },
  'element-plus': { ElMessage: { success: () => {}, warning: () => {} } }
})

test('国内管理客户端使用国内路径，校验响应并发送来源标识', async () => {
  const calls: { url: string; options?: RequestInit }[] = []
  const fetcher: typeof fetch = async (url, options) => {
    calls.push({ url: String(url), options })
    return Response.json(String(url).endsWith('/bindings') ? { bindings: empty() } : { items: [skill] })
  }
  const api = createDomesticStudioSkillsApi(fetcher)
  assert.equal((await api.skills()).items[0].name, 'camera')
  await api.setSkillAvailability('a', false, 1)
  await api.setBindings(empty(), empty())
  assert.deepEqual(calls.map(call => call.url), [
    '/api/v1/management/domestic-studio/skills',
    '/api/v1/management/domestic-studio/skills/a/availability',
    '/api/v1/management/domestic-studio/bindings',
  ])
  assert.equal(calls[1].options?.method, 'PATCH')
  assert.equal((calls[1].options?.headers as Record<string, string>)['X-HX-Request'], '1')
  assert.equal(calls[2].options?.credentials, 'include')
  assert.deepEqual(JSON.parse(String(calls[2].options?.body)), { bindings: empty(), expected: empty() })
  await assert.rejects(createDomesticStudioSkillsApi(async () => Response.json({ bindings: { camera: null } })).getBindings(), IdentityError)
})

test('五个绑定可保存、清空，加载失败不会伪造默认 Skill', async () => {
  let saved = empty(), writes = 0, fail = false
  const api = {
    getBindings: async () => { if (fail) throw Error('目录不可用'); return { bindings: { ...saved } } },
    skills: async () => ({ items: [skill], canToggle: true, canManagePlatforms: false }),
    setBindings: async (value: typeof saved, expected: typeof saved) => { assert.deepEqual(expected, saved); writes++; saved = { ...value }; return { bindings: saved } },
  }
  const view = mount(component, { api }); await flush()
  try {
    const selector = find(view.root, 'ElSelect', '相机配件生成绑定 Skill')
    update(selector, 'a'); await flush()
    const button = find(view.root, 'ElButton')
    assert.equal(text(button), '保存绑定'); (button.props.onClick as () => void)(); await flush()
    assert.equal(writes, 1); assert.equal(saved.camera, 'a')
    update(selector, null); await flush(); (button.props.onClick as () => void)(); await flush()
    assert.equal(writes, 2); assert.equal(saved.camera, null)
  } finally { view.close() }
  fail = true
  const failed = mount(component, { api }); await flush()
  try { assert.match(String(find(failed.root, 'ElAlert').props.title), /目录不可用/); assert.equal(writes, 2) }
  finally { failed.close() }
})

test('绑定发生并发冲突时显示服务端原因，不伪装保存成功', async () => {
  const api = {
    getBindings: async () => ({ bindings: empty() }),
    skills: async () => ({ items: [skill], canToggle: true, canManagePlatforms: false }),
    setBindings: async () => { throw new IdentityError(409, '操作失败', '工作台绑定已被其他管理员修改，请重新加载后核对') },
  }
  const view = mount(component, { api }); await flush()
  try {
    update(find(view.root, 'ElSelect', '相机配件生成绑定 Skill'), 'a'); await flush()
    ;(find(view.root, 'ElButton').props.onClick as () => void)(); await flush()
    assert.match(String(find(view.root, 'ElAlert').props.title), /其他管理员修改/)
  } finally { view.close() }
})

test('保存未完成时禁用所有下拉并通知父级，完成后恢复编辑', async () => {
  let finish!: (value: { bindings: ReturnType<typeof empty> }) => void
  const events: boolean[] = []
  const api = {
    getBindings: async () => ({ bindings: empty() }),
    skills: async () => ({ items: [skill], canToggle: true, canManagePlatforms: false }),
    setBindings: async () => new Promise<{ bindings: ReturnType<typeof empty> }>(resolve => { finish = resolve }),
  }
  const view = mount(component, { api, onSaving: (value: boolean) => events.push(value) }); await flush()
  try {
    update(find(view.root, 'ElSelect', '相机配件生成绑定 Skill'), 'a'); await flush()
    ;(find(view.root, 'ElButton').props.onClick as () => void)(); await flush()
    assert.equal(find(view.root, 'ElSelect', '手机壳生成绑定 Skill').props.disabled, true)
    assert.deepEqual(events, [true])
    finish({ bindings: { ...empty(), camera: 'a' } }); await flush()
    assert.equal(find(view.root, 'ElSelect', '手机壳生成绑定 Skill').props.disabled, false)
    assert.deepEqual(events, [true, false])
  } finally { view.close() }
})

test('国内 Skill 目录显示绑定工作台并提供设置入口，未知绑定不误显示为空', () => {
  let opened = 0
  const view = mount(skillCatalogComponent, { skills: [skill], managed: true, domestic: true, canToggle: true,
    domesticBindings: { ...empty(), camera: 'a' }, domesticWorkspaces, onBindings: () => { opened++ } })
  try { assert.match(text(view.root), /相机配件生成/); click(view.root, '设置绑定'); assert.equal(opened, 1) }
  finally { view.close() }
  const unknown = mount(skillCatalogComponent, { skills: [skill], managed: true, domestic: true, domesticBindings: null, domesticWorkspaces })
  try { assert.match(text(unknown.root), /绑定信息暂不可用/); assert.doesNotMatch(text(unknown.root), /未绑定/) }
  finally { unknown.close() }
})

test('目录读取失败后可重试，并同步重新读取绑定', async () => {
  let reloads = 0, bindingRefreshes = 0
  const api = { skills: async () => { if (++reloads === 1) throw Error('目录不可用'); return { items: [skill], canToggle: true, canManagePlatforms: false } } }
  const view = mount(liveSkillsComponent, { api, transferApi: createDomesticStudioSkillsApi().transfers, domestic: true, domesticBindings: empty(), domesticWorkspaces,
    onBindingsRefresh: () => { bindingRefreshes++ } }); await flush()
  try {
    assert.equal(reloads, 1)
    click(view.root, '重试'); await flush()
    assert.equal(reloads, 2); assert.equal(bindingRefreshes, 1)
  } finally { view.close() }
})
