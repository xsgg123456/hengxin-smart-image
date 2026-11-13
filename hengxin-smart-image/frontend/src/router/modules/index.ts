import type { AppRouteRecord } from '@/types/router'
import { managementComponent } from '../management-preview'
import { domesticWorkspaces } from '@/api/hengxin/domestic-workspaces'
const fullWorkspaceRoles = ['super_admin', 'design_manager']
export const routeModules: AppRouteRecord[] = [{
  name: 'HxApiImageEdits', path: '/api-image-edits', component: '/index/index',
  meta: { title: 'API 换套图', icon: 'ri:exchange-2-line' },
  children: [
    { name: 'HxApiImageCreate', path: 'create', component: '/hengxin/api-image-edits/create', meta: { title: '新建换图', icon: 'ri:image-add-line', keepAlive: false } },
    { name: 'HxApiImageRecords', path: 'records', component: '/hengxin/api-image-edits/records', meta: { title: '换图记录', icon: 'ri:history-line', keepAlive: false } }
  ]
}, ...(['新品生成', '产品替换'] as const).map((group, index) => ({
  name: index ? 'HxProductReplace' : 'HxNewProduct', path: index ? '/product-replace' : '/new-product', component: '/index/index',
  meta: { title: group, icon: index ? 'ri:shuffle-line' : 'ri:sparkling-line' },
  children: domesticWorkspaces.filter(item => item.group === group).map(item => ({
    name: `HxStudio_${item.key}`, path: item.path.split('/').pop()!, component: '/hengxin/domestic-studio/workspace',
    meta: { title: item.title, icon: 'ri:chat-ai-line', keepAlive: false }
  }))
})), {
  name: 'HxProductLibrary', path: '/product-library', component: '/hengxin/domestic-studio/library',
  meta: { title: '成品库', icon: 'ri:archive-line', keepAlive: false }
}, {
  name: 'HxManagement', path: '/management', component: '/index/index',
  meta: { title: '管理中心', icon: 'ri:settings-3-line', roles: fullWorkspaceRoles },
  children: [...(['usage','monitor'].map(path => ({name:`HxAdmin${path}`,path,component:'/hengxin/admin/activity',redirect:'/management/activity',meta:{title:'调用与执行',isHide:true,isHideTab:true,roles:fullWorkspaceRoles}}))), ...[
    { path: 'activity', title: '调用与执行', icon: 'ri:bar-chart-line', roles: fullWorkspaceRoles },
    { path: 'retention', title: '自动清理', icon: 'ri:history-line', roles: ['super_admin', 'design_manager'] },
    { path: 'users', title: '用户与角色', icon: 'ri:group-line', roles: ['super_admin'] },
    { path: 'skills', title: 'Skills 管理', icon: 'ri:tools-line', roles: ['super_admin'] },
    { path: 'settings', title: '系统配置', icon: 'ri:settings-3-line', roles: ['super_admin'] },
    { path: 'codex-auth', title: 'Codex 账号', icon: 'ri:key-2-line', roles: ['super_admin'] }
  ].map(({ path, title, icon, roles }) => ({
    name: `HxAdmin${path}`, path, component: managementComponent(path, import.meta.env?.MODE,
      typeof window === 'undefined' ? '' : window.location.search),
    meta: { title, icon, roles, keepAlive: false }
  }))]
}]
