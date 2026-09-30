import type { AppRouteRecord } from '../types/router'
import { routeModules } from './modules'

function paths(routes: AppRouteRecord[], parent = ''): string[] {
  return routes.flatMap(route => {
    const path = (route.path.startsWith('/') ? route.path : `${parent}/${route.path}`).replace(/\/$/, '')
    return [path, ...paths(route.children ?? [], path)]
  })
}
const businessPaths = new Set(paths(routeModules))

/** 普通角色保留API工作区；兼容登录默认地址及历史书签。后端权限不变。 */
export function apiWorkspaceRedirect(path: string, roles: string[] = []) {
  const limited = roles.length === 1 && ['designer', 'operator'].includes(roles[0])
  const target = path.replace(/\/$/, '').replace(/^\/(wallpaper|product|text)\/index$/, '/image-processing/$1')
  return limited && businessPaths.has(target) && !target.startsWith('/api-image-edits')
    ? '/api-image-edits/create' : undefined
}

/** 已知但不在当前角色菜单中的页面显示 403；未知地址仍由原 404 逻辑处理。 */
export function isDeniedBusinessRoute(path: string, menus: AppRouteRecord[]) {
  const target = path.replace(/\/$/, '')
  return businessPaths.has(target) && !new Set(paths(menus)).has(target)
}
