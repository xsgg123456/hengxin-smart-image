import type { AppRouteRecord } from '@/types/router'
const pages = [
  ['tasks', '任务中心', 'ri:time-line'],
  ['templates', '模板库', 'ri:layout-grid-line'],
  ['archive', '成品库', 'ri:folder-check-line']
]
export const routeModules: AppRouteRecord[] = [{
  name: 'HxImageProcessing', path: '/image-processing', component: '/index/index',
  meta: { title: '图片处理', icon: 'ri:image-edit-line' },
  children: [
    ['wallpaper', '替换壁纸', 'ri:landscape-line'],
    ['product', '替换商品', 'ri:box-3-line'],
    ['text', '替换文字', 'ri:font-size-2']
  ].map(([path, title, icon]) => ({
    name: `Hx${path}Page`, path, component: `/hengxin/${path}`,
    meta: { title, icon, keepAlive: false, fixedTab: path === 'wallpaper' }
  }))
}, ...pages.map(([path, title, icon]) => ({
  name: `Hx${path}Page`, path: `/${path}/index`, component: `/hengxin/${path}`,
  meta: { title, icon, keepAlive: false, fixedTab: path === 'wallpaper' }
})), {
  name: 'HxManagement', path: '/management', component: '/index/index',
  meta: { title: '管理中心', icon: 'ri:settings-3-line' },
  children: [
    { path: 'usage', title: '调用统计', icon: 'ri:bar-chart-line' },
    { path: 'monitor', title: '执行监控', icon: 'ri:pulse-line', roles: ['super_admin', 'design_manager'] },
    { path: 'users', title: '用户与角色', icon: 'ri:group-line', roles: ['super_admin'] },
    { path: 'skills', title: 'Skill 管理', icon: 'ri:code-box-line', roles: ['super_admin'] },
    { path: 'settings', title: '系统配置', icon: 'ri:settings-3-line', roles: ['super_admin'] }
  ].map(({ path, title, icon, roles }) => ({
    name: `HxAdmin${path}`, path, component: `/hengxin/admin/${path}`,
    meta: { title, icon, roles, keepAlive: false }
  }))
}]
