import { createApp, h } from 'vue'
import { createPinia } from 'pinia'
import { router } from '@/router'
import language from '@/locales'
import { useMenuStore } from '@/store/modules/menu'
import { useSettingStore } from '@/store/modules/setting'
import { useWorktabStore } from '@/store/modules/worktab'
import { initializeTheme } from '@/hooks/core/useTheme'
import { useSettingsHandlers } from '@/components/core/layouts/art-settings-panel/composables/useSettingsHandlers'
import { setupRippleDirective } from '@/directives/business/ripple'
import type { AppRouteRecord } from '@/types/router'
import App from './App.vue'
import '@styles/core/tailwind.css'
import '@styles/index.scss'
import '@/views/hengxin/prototype.css'
import './style.css'
const app = createApp(App)
app.use(createPinia()).use(language)
setupRippleDirective(app)
const settings = useSettingStore()
settings.showFastEnter = false
settings.showSettingGuide = false
settings.showFestivalText = false
initializeTheme()
useSettingsHandlers().domOperations.setRootAttribute('data-box-mode', settings.boxBorderMode ? 'border-mode' : 'shadow-mode')
const empty = { render: () => h('div') }
const entry = (key: string, title: string, icon: string): AppRouteRecord => ({ path: `/overseas/${key}`, name: `light-${key}`, component: () => Promise.resolve(empty), meta: { title, icon } })
const menus = [entry('create', '提交图需', 'ri:add-circle-line'), entry('tasks', '工作流任务', 'ri:checkbox-line'), entry('archive', '成品库', 'ri:folder-check-line'),
  { ...entry('management', '管理中心', 'ri:settings-3-line'), children: [entry('management/activity', '调用与执行', 'ri:settings-3-line'), entry('management/users', '用户与角色', 'ri:settings-3-line'), entry('management/skills', 'Skill 管理', 'ri:settings-3-line'), entry('management/settings', '系统配置', 'ri:settings-3-line'), entry('management/codex-auth', 'Codex 账号', 'ri:settings-3-line')] }]
useMenuStore().setMenuList(menus)
useMenuStore().setHomePath('/overseas/management/activity')
for (const route of router.getRoutes()) if (route.name) router.removeRoute(route.name)
for (const menu of menus) {
  router.addRoute({ path: menu.path, name: menu.name, meta: menu.meta, component: empty })
  for (const child of menu.children || []) router.addRoute({ path: child.path, name: child.name, meta: child.meta, component: empty })
}
router.addRoute({ path: '/:pathMatch(.*)*', redirect: '/overseas/management/activity' })
router.afterEach(to => useWorktabStore().openTab({ title: String(to.meta.title), path: to.path, name: String(to.name), keepAlive: false }))
app.use(router)
void router.isReady().then(() => app.mount('#app'))
