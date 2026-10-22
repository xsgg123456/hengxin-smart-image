import { createApp, h } from 'vue'
import { createPinia } from 'pinia'
import { RouterView } from 'vue-router'
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
import Records from './Records.vue'
import Baseline from './Baseline.vue'
import '@styles/core/tailwind.css'
import '@styles/index.scss'
import '@/views/hengxin/prototype.css'

const app = createApp(App)
app.use(createPinia()).use(language)
setupRippleDirective(app)
const settings = useSettingStore()
settings.showFastEnter = false
settings.showSettingGuide = false
settings.showFestivalText = false
initializeTheme()
useSettingsHandlers().domOperations.setRootAttribute('data-box-mode', settings.boxBorderMode ? 'border-mode' : 'shadow-mode')
const baseline = new URLSearchParams(location.search).has('baseline')
const placeholder = { render: () => h('div', { class: 'hx-page' }, [h('h1', '独立交互预览'), h('p', '本轮仅预览换图记录筛选，请点击左侧“换图记录”返回。')]) }
const menus: AppRouteRecord[] = [{ name: 'HxApiImageEdits', path: '/api-image-edits', component: '/preview-only', meta: { title: 'API 换套图', icon: 'ri:exchange-2-line' }, children: [
  { name: 'HxApiImageCreate', path: '/api-image-edits/create', component: '/preview-only', meta: { title: '新建换图', icon: 'ri:image-add-line' } },
  { name: 'HxApiImageRecords', path: '/api-image-edits/records', component: '/preview-only', meta: { title: '换图记录', icon: 'ri:history-line' } },
] }, { name: 'HxManagement', path: '/management', component: '/preview-only', meta: { title: '管理中心', icon: 'ri:settings-3-line' }, children: [
  { name: 'HxUsage', path: '/management/usage', component: '/preview-only', meta: { title: '调用统计', icon: 'ri:bar-chart-line' } },
] }]
useMenuStore().setMenuList(menus)
useMenuStore().setHomePath('/api-image-edits/records')
for (const route of router.getRoutes()) if (route.name) router.removeRoute(route.name)
for (const menu of menus) router.addRoute({ path: menu.path, name: menu.name, meta: menu.meta, component: { render: () => h(RouterView) }, children: (menu.children || []).map(child => ({ path: child.path, name: child.name, meta: child.meta, component: child.name === 'HxApiImageRecords' ? (baseline ? Baseline : Records) : placeholder })) })
router.addRoute({ path: '/:pathMatch(.*)*', redirect: '/api-image-edits/records' })
router.afterEach(to => useWorktabStore().openTab({ title: String(to.meta.title), path: to.path, name: String(to.name), keepAlive: false }))
app.use(router)
void router.isReady().then(() => app.mount('#app'))
