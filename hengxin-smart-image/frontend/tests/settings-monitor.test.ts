import { test } from 'node:test'
import assert from 'node:assert/strict'
import { effectScope, ref } from 'vue'
import { ApiError, createRequest } from '../src/api/hengxin/http'
import { createMockManagement } from '../src/api/hengxin/mock-management'
import { settings } from '../src/api/hengxin/validate-management'
import { validateSettings } from '../src/api/hengxin/settings-validation'
import { settingsInput, useSettingsEditor } from '../src/views/hengxin/admin/settings-editor'
import type { ManagedSettings, SettingsInput } from '../src/types/management'
import type { User } from '../src/types/hengxin'

const admin: User = { id: 'admin', name: '管理员', role: 'super_admin', status: 'active' }
const config = (): ManagedSettings => ({
  version: 1, capacity: 2, timeoutCapacity: 3600, concurrency: 1, timeoutSeconds: 600, maxUploadBytes: 10485760,
  dingtalk: { corpId: 'corp', appId: 'app', callbackDomain: 'https://example.com', state: 'ready' }, audit: []
})

test('配置响应要求部署容量正整数及并发、超时、上传范围，容量不固定为10', async () => {
  assert.equal(settings(config()), true)
  assert.equal(settings({ ...config(), capacity: 20, concurrency: 20 }), true)
  for (const patch of [{ capacity: undefined }, { capacity: 0 }, { capacity: 1.5 }, { capacity: '2' },
    { concurrency: 3 }, { concurrency: 0 }, { timeoutSeconds: 0 }, { timeoutSeconds: 3601 },
    { maxUploadBytes: 1048575 }, { maxUploadBytes: 10485761 }]) {
    assert.equal(settings({ ...config(), ...patch }), false, JSON.stringify(patch))
  }
  const request = createRequest('/api', async () => new Response(JSON.stringify({ ...config(), capacity: null }), { headers: { 'content-type': 'application/json' } }))
  await assert.rejects(request('/management/settings', settings), { code: 'INVALID_RESPONSE' })
})

test('mock保留部署容量，拒绝钉钉修改及越界；失败无版本和审计副作用', async () => {
  const api = createMockManagement(() => admin)
  const original = await api.getSettings()
  assert.equal(original.capacity, 10)
  for (const patch of [{ concurrency: 11 }, { concurrency: 1.5 }, { timeoutSeconds: 3601 },
    { maxUploadBytes: 1048575 }, ...(['corpId', 'appId', 'callbackDomain'] as const).map(key => ({ dingtalk: { ...original.dingtalk, [key]: 'changed' } }))]) {
    await assert.rejects(api.saveSettings({ ...settingsInput(original), ...patch }), { code: 'VALIDATION' })
    assert.deepEqual(await api.getSettings(), original)
  }
  const saved = await api.saveSettings({ ...settingsInput(original), concurrency: 10, timeoutSeconds: 3600, maxUploadBytes: 1048576 })
  assert.equal(saved.capacity, 10)
  assert.equal(saved.version, 2)
  assert.equal(saved.audit[0].operatorId, admin.id)
  assert.deepEqual(saved.audit[0].fields, ['concurrency', 'timeoutSeconds', 'maxUploadBytes'])
  assert.deepEqual(saved.dingtalk, original.dingtalk)
  assert.equal(settings(saved), true)
})

function setup(persist: (input: SettingsInput) => Promise<ManagedSettings>, reload?: () => Promise<ManagedSettings>) {
  const scope = effectScope()
  const data = ref<ManagedSettings | undefined>(config()), loading = ref(false), error = ref('')
  let reads = 0
  const load = async () => {
    reads++; loading.value = true; error.value = ''
    try { data.value = await reload!() } catch (reason) { error.value = (reason as Error).message }
    finally { loading.value = false }
  }
  const editor = scope.run(() => useSettingsEditor({ data, loading, error, load }, persist))!
  return { ...editor, data, loading, error, scope, reads: () => reads }
}

test('编辑器按capacity校验、排除响应字段并保留钉钉原值且不再传递退役字段', async () => {
  const sent: SettingsInput[] = []
  const state = setup(async input => { sent.push(input); return { ...config(), ...input, version: 2, dingtalk: config().dingtalk } })
  try {
    state.form.value!.concurrency = 3
    assert.equal(await state.save(), false)
    state.form.value!.concurrency = 2
    state.uploadMiB.value = undefined
    assert.equal(await state.save(), false)
    state.uploadMiB.value = 1
    state.form.value!.timeoutSeconds = 3601
    assert.equal(await state.save(), false)
    assert.equal(sent.length, 0)
    state.form.value!.timeoutSeconds = 3600
    state.form.value!.dingtalk.corpId = 'tampered'
    assert.equal(await state.save(), true)
    assert.equal(sent[0].concurrency, 2)
    assert.equal(sent[0].maxUploadBytes, 1048576)
    assert.deepEqual(sent[0].dingtalk, settingsInput(config()).dingtalk)
    assert.equal('capacity' in sent[0], false)
    assert.equal('defaultSkillIds' in sent[0], false)
    assert.equal('audit' in sent[0], false)
    assert.equal('state' in sent[0].dingtalk, false)
    assert.equal(state.form.value!.version, 2)
  } finally { state.scope.stop() }
})

test('未修改配置时不提交、不生成新版本，并明确提示无需保存', async () => {
  let writes = 0
  const state = setup(async input => { writes++; return { ...config(), ...input, version: 2, dingtalk: config().dingtalk } })
  try {
    assert.equal(state.dirty.value, false)
    assert.equal(await state.save(), false)
    assert.equal(writes, 0)
    assert.equal(state.saveError.value, '配置没有变化，无需保存')
    state.form.value!.concurrency = 2
    assert.equal(state.dirty.value, true)
    assert.equal(await state.save(), true)
    assert.equal(writes, 1)
    assert.equal(state.dirty.value, false)
  } finally { state.scope.stop() }
})

test('409只重读、不自动重提，新版本及容量回填后要求用户核对', async () => {
  let writes = 0
  const state = setup(async () => { writes++; throw new ApiError('CONFLICT', '冲突', 409) },
    async () => ({ ...config(), version: 2, capacity: 1 }))
  try {
    state.form.value!.concurrency = 2
    assert.equal(await state.save(), false)
    assert.equal(writes, 1)
    assert.equal(state.reads(), 1)
    assert.equal(state.data.value!.capacity, 1)
    assert.equal(state.form.value!.version, 2)
    assert.equal(state.form.value!.concurrency, 1)
    assert.match(state.saveError.value, /已读取最新配置/)
    assert.equal(state.saving.value, false)
  } finally { state.scope.stop() }
})

test('409重读失败清除旧表单并阻止再次保存，普通失败保留编辑值', async () => {
  let writes = 0
  const state = setup(async () => { writes++; throw new ApiError('CONFLICT', '冲突', 409) },
    async () => { throw new Error('断网') })
  try {
    state.form.value!.concurrency = 2
    await state.save()
    assert.equal(state.form.value, undefined)
    assert.equal(state.data.value, undefined)
    assert.match(state.saveError.value, /重新读取失败/)
    await state.save()
    assert.equal(writes, 1)
  } finally { state.scope.stop() }
  const failed = setup(async () => { throw new Error('保存失败') })
  try {
    failed.form.value!.concurrency = 2
    assert.equal(await failed.save(), false)
    assert.equal(failed.form.value!.concurrency, 2)
    assert.equal(failed.reads(), 0)
    assert.equal(failed.saving.value, false)
  } finally { failed.scope.stop() }
})

test('加载中、加载错误及重复点击不提交', async () => {
  let writes = 0, finish!: (value: ManagedSettings) => void
  const state = setup(() => { writes++; return new Promise(resolve => { finish = resolve }) })
  try {
    state.loading.value = true
    assert.equal(await state.save(), false)
    state.loading.value = false; state.error.value = '读取失败'
    assert.equal(await state.save(), false)
    state.error.value = ''
    state.form.value!.concurrency = 2
    const first = state.save()
    assert.equal(await state.save(), false)
    assert.equal(writes, 1)
    finish({ ...config(), version: 2 })
    assert.equal(await first, true)
  } finally { state.scope.stop() }
})

test('动态超时600边界；特殊部署10..59可读取但禁止保存', async () => {
  const current = { ...config(), timeoutCapacity: 600 }
  assert.equal(settings(current), true)
  assert.equal(settings({ ...current, timeoutSeconds: 601 }), false)
  assert.equal(settings({ ...current, timeoutCapacity: 7200, timeoutSeconds: 7200 }), true)
  assert.equal(settings({ ...current, timeoutCapacity: 7200, timeoutSeconds: 7201 }), false)
  for (const capacity of [undefined, null, 9, 7201, 600.5, '600']) {
    assert.equal(settings({ ...current, timeoutCapacity: capacity }), false)
  }
  let writes = 0
  const state = setup(async input => { writes++; return { ...current, ...input, dingtalk: current.dingtalk } })
  try {
    state.data.value = current
    state.form.value!.timeoutSeconds = 601
    assert.equal(await state.save(), false)
    assert.match(state.saveError.value, /60–600/)
    assert.throws(() => validateSettings({ ...settingsInput(current), timeoutSeconds: 601 }, current), { code: 'VALIDATION' })
    state.form.value!.timeoutSeconds = 600
    state.form.value!.concurrency = 2
    assert.equal(await state.save(), true)
    assert.equal(writes, 1)
    assert.equal('timeoutCapacity' in settingsInput(current), false)
    for (const timeoutCapacity of [10, 59]) {
      const low = { ...current, timeoutCapacity, timeoutSeconds: timeoutCapacity }
      assert.equal(settings(low), true)
      state.data.value = low
      assert.equal(state.form.value!.timeoutSeconds, timeoutCapacity)
      assert.equal(await state.save(), false)
      assert.equal(state.saveError.value, '部署超时上限低于60秒，请先调整部署配置')
      assert.throws(() => validateSettings(settingsInput(low), low), { code: 'VALIDATION' })
    }
    assert.equal(writes, 1)
  } finally { state.scope.stop() }
})

