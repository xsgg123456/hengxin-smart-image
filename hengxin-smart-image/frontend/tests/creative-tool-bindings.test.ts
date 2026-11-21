import test from 'node:test'
import assert from 'node:assert/strict'
import { defineComponent, h, type Slots } from 'vue'
import { CREATIVE_TOOLS, type CreativeToolKey } from '../src/api/overseas/creative-tools'
import { createManagementApi, type ToolBindings } from '../src/api/overseas/management'
import { IdentityError } from '../src/api/identity/request'
import { all, click, compile, find, flush, mount, simple, text, update } from './membership-test-harness'

function snapshot(): ToolBindings {
  return {
    items: ['one', 'two'].map((id, i) => ({ id, name: id, displayName: id, enabled: i === 0,
      platforms: [], version: 1, description: '' })),
    bindings: Object.fromEntries(CREATIVE_TOOLS.map(tool => [tool.value, []])) as ToolBindings['bindings']
  }
}

test('绑定接口发往真实海外管理路径，缺少某个入口的响应会报错', async () => {
  const state = snapshot()
  const api = createManagementApi(async (url, options) => {
    assert.equal(url, '/api/overseas/v1/management/skills/tool-bindings/outonlife')
    assert.equal(options?.method, 'PUT')
    assert.deepEqual(JSON.parse(String(options?.body)), { expectedSkillIds: [], skillIds: ['two'] })
    return Response.json(state)
  })
  await api.setToolBindings('outonlife', [], ['two'])
  await assert.rejects(createManagementApi(async () => Response.json({ items: [], bindings: {} })).toolBindings(), /格式错误/)
})

const table = defineComponent({
  props: ['data'],
  setup(props, { slots }) {
    return () => h('ElTable', props.data.flatMap((row: typeof CREATIVE_TOOLS[number]) =>
      (slots.default?.() || []).map(column => {
        const content = (column.children as Slots | null)?.default
        return h('cell', content ? content({ row }) : row.label)
      })))
  }
})
const component = compile('views/overseas/admin/WorkspaceSkills.vue', {
  '@/api/overseas/creative-tools': { CREATIVE_TOOLS }, '@/api/identity/request': { IdentityError },
  'element-plus': { ElMessage: { success() {} } }
})
Object.assign(component, {
  components: { ElTable: table, ElTableColumn: simple('ElTableColumn'), ElCheckboxGroup: simple('ElCheckboxGroup'), ElCheckbox: simple('ElCheckbox') },
  directives: { loading: {} }
})

test('管理工作台切换多选、显示关闭状态、拒绝过期覆盖并刷新', async () => {
  const state = snapshot()
  const writes: unknown[] = []
  let conflict = false
  const view = mount(component, { api: {
    toolBindings: async () => structuredClone(state),
    setToolBindings: async (key: CreativeToolKey, expected: string[], ids: string[]) => {
      writes.push([key, [...expected], [...ids]])
      if (conflict) { state.bindings.outon = ['two']; throw new IdentityError(409, '冲突', '绑定已更新') }
      state.bindings[key] = [...ids]
      return structuredClone(state)
    }
  } })
  try {
    await flush()
    assert.equal(all(view.root).filter(n => n.tag === 'ElButton' && text(n) === '设置绑定').length, 8)
    click(view.root, '设置绑定'); await flush()
    update(find(view.root, 'ElInput', '搜索已安装的 Skill'), 'two'); await flush()
    assert.match(text(find(view.root, 'ElCheckboxGroup')), /two（已关闭）/)
    update(find(view.root, 'ElCheckboxGroup'), ['one', 'two']); await flush()
    click(view.root, '保存绑定'); await flush()
    assert.deepEqual(writes[0], ['outon', [], ['one', 'two']])
    assert.deepEqual(state.bindings.outonlife, [])
    assert.match(text(find(view.root, 'ElTable')), /two（已关闭）/)
    conflict = true
    click(view.root, '设置绑定'); await flush()
    update(find(view.root, 'ElCheckboxGroup'), []); await flush()
    click(view.root, '保存绑定'); await flush()
    assert.deepEqual(writes[1], ['outon', ['one', 'two'], []])
    assert.equal(find(view.root, 'ElAlert').props.title, '绑定已更新')
    click(view.root, '设置绑定'); await flush()
    assert.deepEqual(find(view.root, 'ElCheckboxGroup').props.modelValue, ['two'])
  } finally { view.close() }
})
