import { createApp, h, watch } from 'vue'
import { createPinia } from 'pinia'
import { RouterView } from 'vue-router'
import { router } from '@/router'
import language from '@/locales'
import { useUserStore } from '@/store/modules/user'
import { useMenuStore } from '@/store/modules/menu'
import { useSettingStore } from '@/store/modules/setting'
import { useWorktabStore } from '@/store/modules/worktab'
import { initializeTheme } from '@/hooks/core/useTheme'
import { useSettingsHandlers } from '@/components/core/layouts/art-settings-panel/composables/useSettingsHandlers'
import { setupRippleDirective } from '@/directives/business/ripple'
import type { AppRouteRecord } from '@/types/router'
import { domesticWorkspaces } from '@/api/hengxin/domestic-workspaces'
import App from './App.vue'
import { admin, previewRole, tasks } from './state'
import TaskPreview from './TaskPreview.vue'
import '@styles/core/tailwind.css'
import '@styles/index.scss'
import '@/views/hengxin/prototype.css'
import '@/views/shared/studio/studio.css'
import './style.css'

const app = createApp(App)
app.use(createPinia()).use(language)
setupRippleDirective(app)
useUserStore().info = { roles: ['super_admin'] }
const settings = useSettingStore()
settings.showFastEnter = false
settings.showSettingGuide = false
settings.showFestivalText = false
settings.uniqueOpened = false
settings.setMenuOpen(window.innerWidth >= 800)
initializeTheme()
useSettingsHandlers().domOperations.setRootAttribute('data-box-mode', settings.boxBorderMode ? 'border-mode' : 'shadow-mode')
const entry = (path: string, title: string, icon: string): AppRouteRecord => ({ path, name: `task-preview-${path}`, component: '/preview-only', meta: { title, icon, keepAlive: false } })
const menus: AppRouteRecord[] = [
  { ...entry('/api-image-edits', 'API 换套图', 'ri:exchange-2-line'), children: [entry('/api-image-edits/create', '新建换图', 'ri:image-add-line'), entry('/api-image-edits/records', '换图记录', 'ri:history-line')] },
  ...['新品生成', '产品替换'].map((group, index) => ({ ...entry(index ? '/product-replace' : '/new-product', group, index ? 'ri:shuffle-line' : 'ri:sparkling-line'), children: domesticWorkspaces.filter(w => w.group === group).map(w => entry(w.path, w.title, 'ri:chat-ai-line')) })),
  entry('/library', '成品库', 'ri:archive-line'),
  { ...entry('/management', '管理中心', 'ri:settings-3-line'), children: [
    entry('/management/activity', '调用与执行', 'ri:bar-chart-line'),
    entry('/management/task-center', '任务中心', 'ri:task-line'),
    entry('/management/retention', '自动清理', 'ri:history-line'), entry('/management/users', '用户与角色', 'ri:group-line'),
    entry('/management/skills', 'Skills 管理', 'ri:tools-line'), entry('/management/settings', '系统配置', 'ri:settings-3-line'), entry('/management/codex-auth', 'Codex 账号', 'ri:key-2-line'),
  ] },
]
const home = '/new-product/camera-accessories'
const placeholder = { render: () => h('section', { class: 'hx-page' }, [h('h1', '现有业务页面'), h('p', '此独立预览展示任务中心和五个业务入口，其他页面保持现状。'), h('a', { href: '#' + home }, '返回业务任务')]) }
watch(previewRole, value => {
  useUserStore().info = { roles: [value] }
  useMenuStore().setMenuList(admin.value ? menus : menus.filter(m => m.path !== '/management'))
  const tabs = useWorktabStore()
  tabs.opened = tabs.opened.filter(t => !t.path.startsWith('/task-center') && t.path !== '/management/workspace-sessions' && (admin.value || !t.path.startsWith('/management')))
  const current = router.currentRoute.value
  if (!admin.value && current.path.startsWith('/management')) void router.replace(home)
}, { immediate: true })
useMenuStore().setHomePath(home)
for (const route of router.getRoutes()) if (route.name) router.removeRoute(route.name)
for (const menu of menus) router.addRoute({ path: menu.path, name: menu.name, meta: menu.meta, component: menu.children ? { render: () => h(RouterView) } : menu.path === home ? TaskPreview : placeholder,
  children: menu.children?.map(child => ({ path: child.path, name: child.name, meta: child.meta, component: domesticWorkspaces.some(w => w.path === child.path) || child.path === '/management/task-center' ? TaskPreview : placeholder })) })
router.addRoute({ path: '/tasks/:id', name: 'task-preview-detail', component: TaskPreview, meta: { title: '任务工作台', keepAlive: false } })
router.addRoute({ path: '/management/task-center/:id', name: 'task-preview-readonly-detail', component: TaskPreview, meta: { title: '任务只读查看', keepAlive: false } })
router.addRoute({ path: '/task-center', redirect: () => admin.value ? '/management/task-center' : home })
router.addRoute({ path: '/task-center/:id', redirect: to => '/tasks/' + String(to.params.id) })
router.addRoute({ path: '/management/workspace-sessions', redirect: '/management/task-center' })
router.beforeEach(to => {
  if (to.path.startsWith('/management') && !admin.value) return home
  if (to.path.startsWith('/tasks/') && tasks.find(t => t.id === to.params.id)?.owner !== '我') return home
})
router.addRoute({ path: '/:pathMatch(.*)*', redirect: home })
router.afterEach(to => useWorktabStore().openTab({ title: String(to.meta.title), path: to.path, name: String(to.name), query: to.query, keepAlive: false }))
app.use(router)
void router.isReady().then(() => app.mount('#app'))

