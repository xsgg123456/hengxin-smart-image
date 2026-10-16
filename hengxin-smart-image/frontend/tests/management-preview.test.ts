import assert from 'node:assert/strict'
import test from 'node:test'
import { managementComponent } from '../src/router/management-preview'

test('management preview requires both explicit mock mode and opt-in query', () => {
  for (const mode of ['production', 'development', 'demo', undefined]) {
    assert.equal(managementComponent('usage', mode, '?managementPreview=api'), '/hengxin/admin/usage')
  }
  assert.equal(managementComponent('usage', 'mock', ''), '/hengxin/admin/usage')
  assert.equal(managementComponent('usage', 'mock', '?managementPreview=api'), '/hengxin/admin/usage')
  assert.equal(managementComponent('monitor', 'mock', '?managementPreview=api'), '/hengxin/admin/preview/MonitorPreview')
  assert.equal(managementComponent('settings', 'mock', '?managementPreview=api'), '/hengxin/admin/preview/SettingsPreview')
  assert.equal(managementComponent('users', 'mock', '?managementPreview=api'), '/hengxin/admin/users')
})

