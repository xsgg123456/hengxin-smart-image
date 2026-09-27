import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createRouter, createMemoryHistory } from 'vue-router'
import { restoreIdentityRoutes } from '../src/api/hengxin/identity-routing'
import { createBootstrapRunner } from '../src/api/hengxin/bootstrap-runner'
import { identity } from '../src/api/hengxin/identity'

test('换号先重走真实VueRouter守卫，完成前不展示旧管理员路由', async () => {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/admin/users', name: 'admin', component: {} },
    { path: '/:pathMatch(.*)*', component: {} }
  ] })
  await router.push('/admin/users')
  router.removeRoute('admin')
  assert.equal(router.currentRoute.value.path, '/admin/users')
  let release!: () => void
  const wait = new Promise<void>(resolve => { release = resolve })
  let guardCalls = 0, visible = false, finished = false
  router.beforeEach(async to => {
    guardCalls++
    await wait
    if (!router.hasRoute('wallpaper')) {
      router.addRoute({ path: '/image-processing/wallpaper', name: 'wallpaper', component: {} })
      return { path: to.path, replace: true }
    }
    return true
  })
  identity.advance('changed')
  const run = createBootstrapRunner({
    load: async () => 'operator', start() {},
    async accept() { await restoreIdentityRoutes(router, identity.epoch); visible = true },
    fail(error) { throw error }, finish() { finished = true }
  })
  const pending = run()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(visible, false); assert.equal(finished, false)
  release(); await pending
  assert.equal(router.currentRoute.value.name, 'wallpaper')
  assert.equal(router.hasRoute('admin'), false)
  assert.ok(guardCalls >= 2); assert.equal(visible, true); assert.equal(finished, true)
})
