import { createApp, h } from 'vue'
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
import App from './App.vue'
import Activity from './Activity.vue'
import Usage from '@/views/hengxin/admin/ApiUsage.vue'
import Monitor from '@/views/hengxin/admin/monitor.vue'
import './style.css'
import '@styles/core/tailwind.css'
import '@styles/index.scss'
import '@/views/hengxin/prototype.css'

const app = createApp(App)
app.use(createPinia()).use(language)
setupRippleDirective(app)
useUserStore().info = { roles: ['super_admin'] }
const settings = useSettingStore()
settings.showFastEnter = false
settings.showSettingGuide = false
settings.showFestivalText = false
initializeTheme()
useSettingsHandlers().domOperations.setRootAttribute('data-box-mode', settings.boxBorderMode ? 'border-mode' : 'shadow-mode')
const placeholder = { render: () => h('div', { class: 'hx-page' }, [h('h1', '独立交互预览'), h('p', '本次聚焦调用与执行，请从左侧菜单返回。')]) }
const entry = (key: string, title: string, icon: string): AppRouteRecord => ({ path: key, name: `preview-${key}`, component: '/preview-only', meta: { title, icon, keepAlive: false } })
const menus: AppRouteRecord[] = [
  { ...entry('/api-image-edits', 'API 换套图', 'ri:exchange-2-line'), children: [entry('/api-image-edits/create', '新建换图', 'ri:image-add-line'), entry('/api-image-edits/records', '换图记录', 'ri:history-line')] },
  { ...entry('/management', '管理中心', 'ri:settings-3-line'), children: [
    entry('/management/activity', '调用与执行', 'ri:bar-chart-line'), entry('/management/retention', '自动清理', 'ri:history-line'),
    entry('/management/users', '用户与角色', 'ri:group-line'), entry('/management/settings', '系统配置', 'ri:settings-3-line'), entry('/management/codex-auth', 'Codex 账号', 'ri:key-2-line'),
  ] },
]
useMenuStore().setMenuList(menus)
useMenuStore().setHomePath('/management/activity')
for (const route of router.getRoutes()) if (route.name) router.removeRoute(route.name)
for (const menu of menus) router.addRoute({ path: menu.path, name: menu.name, meta: menu.meta, component: { render: () => h(RouterView) }, children: (menu.children || []).map(child => ({ path: child.path, name: child.name, meta: child.meta, component: child.path === '/management/activity' ? Activity : placeholder })) })
router.addRoute({ path: '/management/usage', name: 'baseline-usage', component: Usage, meta: { title: '调用统计（原版）' } })
router.addRoute({ path: '/management/monitor', name: 'baseline-monitor', component: Monitor, meta: { title: '执行监控（原版）' } })
router.addRoute({ path: '/:pathMatch(.*)*', redirect: '/management/activity' })
router.afterEach(to => useWorktabStore().openTab({ title: String(to.meta.title), path: to.path, name: String(to.name), keepAlive: false }))
app.use(router)
void router.isReady().then(() => app.mount('#app'))
