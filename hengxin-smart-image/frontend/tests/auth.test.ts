import { test } from 'node:test'
import assert from 'node:assert/strict'
import { getPreviewUser, getLoginScenario, safeReturnPath } from '../src/api/hengxin/session'

test('预览身份默认运营，四角色拥有稳定独立标识，未知角色不提权', () => {
  assert.equal(getPreviewUser('').id, 'mock-operator')
  const roles = ['operator', 'designer', 'design_manager', 'super_admin']
  assert.equal(new Set(roles.map(role => getPreviewUser(`?role=${role}`).id)).size, 4)
  assert.equal(getPreviewUser('?role=admin').role, 'operator')
  assert.equal(getPreviewUser('?role=super_admin&auth=pending').role, null)
  assert.equal(getPreviewUser('?auth=disabled').status, 'disabled')
  assert.equal(getLoginScenario('?auth=unknown'), 'success')
})
test('登录回跳仅允许业务站内路径，拒绝外域、反斜杠、登录循环与非业务地址', () => {
  for (const value of ['https://evil.test', '//evil.test', '/\\evil.test', '/auth/login', '/%2f%2fevil.test', '/management/users\n']) {
    assert.equal(safeReturnPath(value), '/image-processing/wallpaper')
  }
  assert.equal(safeReturnPath('/management/usage?date=2026-09-09'), '/management/usage?date=2026-09-09')
  assert.equal(safeReturnPath('/tasks/index'), '/tasks/index')
})
