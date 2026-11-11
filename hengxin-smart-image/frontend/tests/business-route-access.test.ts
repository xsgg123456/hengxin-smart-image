import { test } from 'node:test'
import assert from 'node:assert/strict'
import { isDeniedBusinessRoute } from '../src/router/business-route-access'
import { routeModules } from '../src/router/modules'

test('普通用户直达管理子页不因父菜单存在而被视为有权访问', () => {
  const menus = routeModules.map(route => ({ ...route, children: route.children?.filter(child => !child.meta.roles) }))
  assert.equal(isDeniedBusinessRoute('/management/settings', menus), true)
  assert.equal(isDeniedBusinessRoute('/management/users/', menus), true)
  assert.equal(isDeniedBusinessRoute('/management/monitor', menus), true)
  assert.equal(isDeniedBusinessRoute('/management/usage', menus), true)
  assert.equal(isDeniedBusinessRoute('/management/activity', menus), true)
  assert.equal(isDeniedBusinessRoute('/tasks/index', menus), false)
  assert.equal(isDeniedBusinessRoute('/403', menus), false)
  assert.equal(isDeniedBusinessRoute('/no-such-page', menus), false)
})
test('超管菜单和规范化后的绝对子菜单保持可访问', () => {
  assert.equal(isDeniedBusinessRoute('/management/skills', routeModules), false)
  const menus = routeModules.map(route => ({ ...route, children: route.children?.map(child => ({ ...child, path: `${route.path}/${child.path}` })) }))
  assert.equal(isDeniedBusinessRoute('/image-processing/product', menus), false)
  assert.equal(isDeniedBusinessRoute('/management/skills', menus), false)
})

test('合并页旧入口保留组件使菜单处理器注册兼容跳转', () => {
  const management = routeModules.find(route => route.path === '/management')!
  for (const path of ['usage', 'monitor']) {
    const route = management.children!.find(route => route.path === path)!
    assert.equal(route.redirect, '/management/activity')
    assert.equal(route.component, '/hengxin/admin/activity')
    assert.equal(route.meta.isHide, true)
    assert.deepEqual(route.meta.roles, ['super_admin', 'design_manager'])
  }
})
