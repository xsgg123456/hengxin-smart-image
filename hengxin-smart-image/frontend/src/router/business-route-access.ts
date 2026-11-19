import { domesticLandingPath } from '../release/navigation'
import type { AppRouteRecord } from '../types/router'
import { routeModules } from './modules'

function paths(routes: AppRouteRecord[], parent = ''): string[] {
  return routes.flatMap(route => {
    const path = (route.path.startsWith('/') ? route.path : `${parent}/${route.path}`).replace(/\/$/, '')
    return [path, ...paths(route.children ?? [], path)]
  })
}
const businessPaths = new Set(paths(routeModules))

/** 退役模块对所有角色回收；国内工作台对业务成员开放。 */
export function isRetiredBusinessPath(path: string) {
  return /^\/(?:image-processing|tasks|templates|archive|wallpaper|product|text)(?:\/|$)/.test(path)
}

export function apiWorkspaceRedirect(path: string, roles: string[] = []) {
  const target = path.split(/[?#]/)[0].replace(/\/$/, '')
  const admin = roles.includes('super_admin')
  if (isRetiredBusinessPath(target)) return admin ? '/api-image-edits/create' : domesticLandingPath
  if (!admin && (target === '/api-image-edits' || target.startsWith('/api-image-edits/'))) return domesticLandingPath
  if (!admin && businessPaths.has(target) && (target === '/management' || target.startsWith('/management/'))) return domesticLandingPath
}

/** 已知但不在当前角色菜单中的页面显示 403；未知地址仍由原 404 逻辑处理。 */
export function isDeniedBusinessRoute(path: string, menus: AppRouteRecord[]) {
  const target = path.replace(/\/$/, '')
  return businessPaths.has(target) && !new Set(paths(menus)).has(target)
}
