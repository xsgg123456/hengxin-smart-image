import test from 'node:test'
import assert from 'node:assert/strict'
import { createMockService } from '../src/api/hengxin/mock'
import { getPreviewUser } from '../src/api/hengxin/session'
import { apiWorkspaceRedirect } from '../src/router/business-route-access'

test('国内三角色及旧主管兼容身份，退役入口回各自工作台，管理维护权限独立', async () => {
  for (const role of ['super_admin', 'design_manager', 'designer', 'operator']) {
    const user = getPreviewUser(`?role=${role}`), service = createMockService({ user, delayMs: 0 })
    try {
      assert.deepEqual(await service.getUser(), user)
      for (const path of ['/image-processing/wallpaper', '/tasks/index', '/templates/index', '/archive/index']) assert.equal(apiWorkspaceRedirect(path, [role]), role === 'super_admin' ? '/api-image-edits/create' : '/new-product/general')
      assert.equal(apiWorkspaceRedirect('/management/skills', [role]), role !== 'super_admin' ? '/new-product/general' : undefined)
      for (const path of ['/api-image-edits', '/api-image-edits/create', '/api-image-edits/records?task=old']) {
        assert.equal(apiWorkspaceRedirect(path, [role]), role === 'super_admin' ? undefined : '/new-product/general')
      }
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
