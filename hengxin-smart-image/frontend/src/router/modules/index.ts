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
}))]
