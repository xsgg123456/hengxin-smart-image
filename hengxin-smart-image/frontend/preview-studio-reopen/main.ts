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
import 'element-plus/theme-chalk/src/button.scss'

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
const entries = [
  ['create', '提交图需', 'ri:add-box-line'],
  ['tasks', '工作流任务', 'ri:checkbox-line'], ['archive', '成品库', 'ri:folder-check-line'],
  ['management', '管理中心', 'ri:settings-3-line'],
]
const menus: AppRouteRecord[] = entries.map(([key, title, icon]) => ({ path: `/overseas/${key}`, name: key, component: () => Promise.resolve(empty), meta: { title, icon } }))
useMenuStore().setMenuList(menus)
useMenuStore().setHomePath('/preview-studio-reopen/index.html')
for (const route of router.getRoutes()) if (route.name) router.removeRoute(route.name)
for (const m of menus) router.addRoute({ path: m.path, name: m.name, meta: m.meta, component: empty })
router.addRoute({ path: '/preview-studio-reopen/index.html', name: 'reopen-preview', component: empty, meta: { title: '任务详情' } })
router.addRoute({ path: '/:pathMatch(.*)*', redirect: '/preview-studio-reopen/index.html' })
router.afterEach(to => useWorktabStore().openTab({ title: String(to.meta.title), path: to.path, name: String(to.name), keepAlive: false }))
app.use(router)
void router.isReady().then(() => app.mount('#app'))

