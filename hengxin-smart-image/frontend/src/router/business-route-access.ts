import type { AppRouteRecord } from '../types/router'
import { routeModules } from './modules'

function paths(routes: AppRouteRecord[], parent = ''): string[] {
  return routes.flatMap(route => {
    const path = (route.path.startsWith('/') ? route.path : `${parent}/${route.path}`).replace(/\/$/, '')
    return [path, ...paths(route.children ?? [], path)]
  })
}
const businessPaths = new Set(paths(routeModules))

/** 退役模块对所有角色回收；普通角色继续仅使用API工作区。 */
export function isRetiredBusinessPath(path: string) {
  return /^\/(?:image-processing|tasks|templates|archive|wallpaper|product|text)(?:\/|$)/.test(path) || /^\/management\/skills(?:\/|$)/.test(path)
}

export function apiWorkspaceRedirect(path: string, roles: string[] = []) {
  if (isRetiredBusinessPath(path.split(/[?#]/)[0])) return '/api-image-edits/create'
  const limited = roles.length === 1 && ['designer', 'operator'].includes(roles[0])
  const target = path.replace(/\/$/, '')
  return limited && businessPaths.has(target) && !target.startsWith('/api-image-edits')
    ? '/api-image-edits/create' : undefined
}

/** 已知但不在当前角色菜单中的页面显示 403；未知地址仍由原 404 逻辑处理。 */
export function isDeniedBusinessRoute(path: string, menus: AppRouteRecord[]) {
  const target = path.replace(/\/$/, '')
  return businessPaths.has(target) && !new Set(paths(menus)).has(target)
}
