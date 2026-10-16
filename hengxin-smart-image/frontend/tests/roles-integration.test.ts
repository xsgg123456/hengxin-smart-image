import test from 'node:test'
import assert from 'node:assert/strict'
import { createMockService } from '../src/api/hengxin/mock'
import { getPreviewUser } from '../src/api/hengxin/session'
import { apiWorkspaceRedirect } from '../src/router/business-route-access'

test('四角色保留身份，退役入口回API，管理维护权限独立', async () => {
  for (const role of ['super_admin', 'design_manager', 'designer', 'operator']) {
    const user = getPreviewUser(`?role=${role}`), service = createMockService({ user, delayMs: 0 })
    try {
      assert.deepEqual(await service.getUser(), user)
      for (const path of ['/image-processing/wallpaper', '/tasks/index', '/templates/index', '/archive/index', '/management/skills']) assert.equal(apiWorkspaceRedirect(path, [role]), '/api-image-edits/create')
      assert.equal(apiWorkspaceRedirect('/api-image-edits/records', [role]), undefined)
      if (role === 'super_admin') {
        assert.ok((await service.listUsers({ page: 1, pageSize: 20 })).total)
        const settings = await service.getSettings()
        assert.equal((await service.saveSettings({ ...settings, concurrency: 2 })).version, settings.version + 1)
      } else {
        await assert.rejects(service.listUsers({ page: 1, pageSize: 20 }), { code: 'FORBIDDEN' })
        await assert.rejects(service.getSettings(), { code: 'FORBIDDEN' })
      }
    } finally { service.dispose() }
  }
})
