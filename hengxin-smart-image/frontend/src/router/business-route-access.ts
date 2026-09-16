import type { AppRouteRecord } from '../types/router'
import { routeModules } from './modules'

function paths(routes: AppRouteRecord[], parent = ''): string[] {
  return routes.flatMap(route => {
    const path = (route.path.startsWith('/') ? route.path : `${parent}/${route.path}`).replace(/\/$/, '')
    return [path, ...paths(route.children ?? [], path)]
  })
}
const businessPaths = new Set(paths(routeModules))

/** 已知但不在当前角色菜单中的页面显示 403；未知地址仍由原 404 逻辑处理。 */
export function isDeniedBusinessRoute(path: string, menus: AppRouteRecord[]) {
  const target = path.replace(/\/$/, '')
  return businessPaths.has(target) && !new Set(paths(menus)).has(target)
}
