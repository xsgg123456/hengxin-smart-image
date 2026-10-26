import type { AppRouteRecord } from '@/types/router'
import { managementComponent } from '../management-preview'
const fullWorkspaceRoles = ['super_admin', 'design_manager']
export const routeModules: AppRouteRecord[] = [{
  name: 'HxApiImageEdits', path: '/api-image-edits', component: '/index/index',
  meta: { title: 'API 换套图', icon: 'ri:exchange-2-line' },
  children: [
    { name: 'HxApiImageCreate', path: 'create', component: '/hengxin/api-image-edits/create', meta: { title: '新建换图', icon: 'ri:image-add-line', keepAlive: false } },
    { name: 'HxApiImageRecords', path: 'records', component: '/hengxin/api-image-edits/records', meta: { title: '换图记录', icon: 'ri:history-line', keepAlive: false } }
  ]
}, {
  name: 'HxManagement', path: '/management', component: '/index/index',
  meta: { title: '管理中心', icon: 'ri:settings-3-line', roles: fullWorkspaceRoles },
  children: [
    { path: 'usage', title: '调用统计', icon: 'ri:bar-chart-line' },
    { path: 'monitor', title: '执行监控', icon: 'ri:pulse-line', roles: ['super_admin', 'design_manager'] },
    { path: 'retention', title: '自动清理', icon: 'ri:history-line', roles: ['super_admin', 'design_manager'] },
    { path: 'users', title: '用户与角色', icon: 'ri:group-line', roles: ['super_admin'] },
    { path: 'settings', title: '系统配置', icon: 'ri:settings-3-line', roles: ['super_admin'] },
    { path: 'codex-auth', title: 'Codex 账号', icon: 'ri:key-2-line', roles: ['super_admin'] }
  ].map(({ path, title, icon, roles }) => ({
    name: `HxAdmin${path}`, path, component: managementComponent(path, import.meta.env?.MODE,
      typeof window === 'undefined' ? '' : window.location.search),
    meta: { title, icon, roles, keepAlive: false }
  }))
}]
