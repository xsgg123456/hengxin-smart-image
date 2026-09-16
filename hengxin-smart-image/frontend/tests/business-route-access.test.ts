import { test } from 'node:test'
import assert from 'node:assert/strict'
import { isDeniedBusinessRoute } from '../src/router/business-route-access'
import { routeModules } from '../src/router/modules'

test('普通用户直达管理子页不因父菜单存在而被视为有权访问', () => {
  const menus = routeModules.map(route => ({ ...route, children: route.children?.filter(child => !child.meta.roles) }))
  assert.equal(isDeniedBusinessRoute('/management/skills', menus), true)
  assert.equal(isDeniedBusinessRoute('/management/users/', menus), true)
  assert.equal(isDeniedBusinessRoute('/management/monitor', menus), true)
  assert.equal(isDeniedBusinessRoute('/management/usage', menus), false)
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
