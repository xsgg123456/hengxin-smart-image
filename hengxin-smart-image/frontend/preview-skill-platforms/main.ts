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
import 'element-plus/theme-chalk/src/button.scss'

const app = createApp(App)
app.use(createPinia()).use(language)
setupRippleDirective(app)
const settings = useSettingStore()
settings.showFastEnter = false; settings.showSettingGuide = false; settings.showFestivalText = false
initializeTheme()
useSettingsHandlers().domOperations.setRootAttribute('data-box-mode', settings.boxBorderMode ? 'border-mode' : 'shadow-mode')
const empty = { render: () => h('div') }
const make = (key: string, title: string, icon: string): AppRouteRecord => ({ path: `/overseas/${key}`, name: key, component: () => Promise.resolve(empty), meta: { title, icon } })
const menus = [make('create', '提交图需', 'ri:add-box-line'), make('tasks', '工作流任务', 'ri:checkbox-line'), make('archive', '成品库', 'ri:folder-check-line'), {
  ...make('admin', '管理中心', 'ri:settings-3-line'), children: [
    make('admin/usage', '调用统计', 'ri:bar-chart-line'), make('admin/monitor', '执行监控', 'ri:pulse-line'),
    make('admin/users', '用户与角色', 'ri:group-line'), make('admin/skills', 'Skill 管理', 'ri:code-box-line'),
    make('admin/settings', '系统配置', 'ri:settings-3-line'), make('admin/codex-auth', 'Codex 账号', 'ri:code-box-line'),
  ],
}]
useMenuStore().setMenuList(menus)
useMenuStore().setHomePath('/overseas/admin/skills')
for (const route of router.getRoutes()) if (route.name) router.removeRoute(route.name)
for (const m of menus.flatMap(m => [m, ...(m.children || [])])) router.addRoute({ path: m.path, name: m.name, meta: m.meta, component: empty })
router.addRoute({ path: '/:pathMatch(.*)*', redirect: '/overseas/admin/skills' })
router.afterEach(to => useWorktabStore().openTab({ title: String(to.meta.title), path: to.path, name: String(to.name), keepAlive: false }))
app.use(router)
void router.isReady().then(() => app.mount('#app'))
