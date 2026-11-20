import { addCollection } from '@iconify/vue'
import shellIcons from './shell-icons.json'
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

addCollection(shellIcons)
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
const center = '/overseas/design-center'
const make = (path: string, title: string, icon: string) => ({ path, name: path.split('/').pop(), component: empty, meta: { title, icon } })
const menu = [
  make(center, '设计任务中心', 'ri:layout-grid-line'),
  make('/overseas/archive', '成品库', 'ri:folder-check-line'),
  { ...make('/overseas/admin', '管理中心', 'ri:settings-3-line'), children: [make('/overseas/admin/users', '用户与角色', 'ri:group-line'), make('/overseas/admin/feedback', '反馈管理', 'ri:message-3-line')] },
]
useMenuStore().setMenuList(menu as unknown as AppRouteRecord[])
useMenuStore().setHomePath(center)
const tabs = useWorktabStore()
tabs.opened = []; tabs.current = {}
for (const r of router.getRoutes()) if (r.name) router.removeRoute(r.name)
for (const m of [menu[0], menu[1], ...menu[2].children!, make('/overseas/about', '关于我们', 'ri:information-line'), make(center + '/task/:id', 'AI 设计工作台', '')]) router.addRoute(m)
router.addRoute({ path: '/:pathMatch(.*)*', redirect: center })
router.afterEach(to => tabs.openTab({ title: String(to.meta.title), path: to.path, name: String(to.name), keepAlive: false }))
app.use(router)
void router.isReady().then(() => app.mount('#app'))



