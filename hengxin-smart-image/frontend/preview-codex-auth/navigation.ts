import { h } from 'vue'
import { router } from '@/router'
import { useMenuStore } from '@/store/modules/menu'
import { useWorktabStore } from '@/store/modules/worktab'
import type { AppRouteRecord } from '@/types/router'
import type { Business } from './model'
const empty = { render: () => h('div') }
const entry = (path: string, title: string, icon: string): AppRouteRecord => ({ path, name: path, component: () => Promise.resolve(empty), meta: { title, icon } })
function menus(side: Business): AppRouteRecord[] {
  const overseas = side === 'overseas', prefix = overseas ? '/overseas/admin' : '/management'
  const admin = entry(prefix, '管理中心', 'ri:settings-3-line')
  const rows = overseas
    ? [['usage', '调用统计', 'ri:settings-3-line'], ['monitor', '执行监控', 'ri:settings-3-line'], ['users', '用户与角色', 'ri:settings-3-line'], ['skills', 'Skill 管理', 'ri:settings-3-line'], ['settings', '系统配置', 'ri:settings-3-line']]
    : [['usage', '调用统计', 'ri:bar-chart-line'], ['monitor', '执行监控', 'ri:pulse-line'], ['retention', '自动清理', 'ri:history-line'], ['users', '用户与角色', 'ri:group-line'], ['settings', '系统配置', 'ri:settings-3-line']]
  admin.children = [...rows, ['codex-auth', 'Codex 账号', 'ri:key-2-line']].map(([key, title, icon]) => entry(prefix + '/' + key, title, icon))
  if (overseas) return [entry('/overseas/create', '提交图需', 'ri:add-circle-line'), entry('/overseas/tasks', '工作流任务', 'ri:task-line'), entry('/overseas/archive', '成品库', 'ri:folder-check-line'), admin]
  return [{ ...entry('/api-image-edits', 'API 换套图', 'ri:exchange-2-line'), children: [entry('/api-image-edits/create', '新建换图', 'ri:image-add-line'), entry('/api-image-edits/records', '换图记录', 'ri:history-line')] }, admin]
}
export function syncMenus(side: Business) {
  useMenuStore().setMenuList(menus(side))
  useMenuStore().setHomePath(side === 'domestic' ? '/management/codex-auth' : '/overseas/admin/codex-auth')
  const tabs = useWorktabStore()
  tabs.opened = []; tabs.current = {}; tabs.keepAliveExclude = []
  const route = router.currentRoute.value
  tabs.openTab({ title: String(route.meta.title || 'Codex 账号'), path: route.path, name: String(route.name), keepAlive: false })
}
export function installMenus() {
  for (const side of ['domestic', 'overseas'] as const) for (const menu of menus(side)) {
    router.addRoute({ path: menu.path, name: menu.name, component: empty, meta: menu.meta,
      children: menu.children?.map(child => ({ path: child.path, name: child.name, component: empty, meta: child.meta })) })
  }
}
