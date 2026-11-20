import test from 'node:test'
import assert from 'node:assert/strict'
import * as Tasks from '../src/api/overseas/tasks'
import * as Identity from '../src/api/identity/request'
import { click, compile, find, flush, mount, update } from './membership-test-harness'

const component = compile('views/overseas/center/CustomDesignDialog.vue', {
  '@/api/identity/request': Identity,
  '@/api/overseas/tasks': Tasks,
})

test('自定义生图拒绝错误格式，双击只发送一次，重开后以同一凭据重试，成功后可再建同名任务', async () => {
  const saved = new Map<string, string>()
  const original = Object.getOwnPropertyDescriptor(globalThis, 'sessionStorage')
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, value: {
    getItem: (key: string) => saved.get(key) ?? null,
    setItem: (key: string, value: string) => saved.set(key, value),
    removeItem: (key: string) => saved.delete(key),
  } })
  const requests: { value: string; key: string }[] = [], ids: string[] = []
  let fail = true
  const props = {
    actorId: 'designer',
    async create(value: string, key: string) {
      requests.push({ value, key })
      if (fail) throw Error('响应中断')
      return { id: 'task-' + requests.length }
    },
    onCreated: (id: string) => ids.push(id),
  }
  let view = mount(component, props)
  const submit = () => click(view.root, '进入 AI 设计工作台')
  const fill = (s: string) => update(find(view.root, 'ElInput', '商品名称+SKU'), s)
  try {
    fill('没有加号'); await flush(); submit(); await flush()
    assert.equal(requests.length, 0)
    assert.match(String(find(view.root, 'ElFormItem').props.error), /加号/)
    fill(' 台灯 + SKU-001 '); await flush(); submit(); submit(); await flush()
    assert.equal(requests.length, 1)
    assert.equal(requests[0].value, '台灯+SKU-001')
    assert.equal(find(view.root, 'ElFormItem').props.error, '响应中断')
    fail = false
    view.close(); view = mount(component, props)
    fill('台灯+SKU-001'); await flush(); submit(); await flush()
    assert.equal(requests[0].key, requests[1].key)
    assert.equal(saved.size, 0)
    view.close(); view = mount(component, props)
    fill('台灯+SKU-001'); await flush(); submit(); await flush()
    assert.notEqual(requests[1].key, requests[2].key)
    assert.deepEqual(ids, ['task-2', 'task-3'])
  } finally {
    view.close()
    if (original) Object.defineProperty(globalThis, 'sessionStorage', original)
    else Reflect.deleteProperty(globalThis, 'sessionStorage')
  }
})
