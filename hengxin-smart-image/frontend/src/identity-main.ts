import { createApp } from 'vue'
import { createPinia } from 'pinia'
import language from './locales'
import IdentityPortal from './views/auth/IdentityPortal.vue'
import { initializeTheme } from './hooks/core/useTheme'
import { router } from './router'
import { h } from 'vue'
import { useSettingStore } from './store/modules/setting'
import { setupRippleDirective } from './directives/business/ripple'
import { useSettingsHandlers } from './components/core/layouts/art-settings-panel/composables/useSettingsHandlers'
import '@styles/core/tailwind.css'
import '@styles/index.scss'
import '@/views/hengxin/prototype.css'
const app = createApp(IdentityPortal)
app.use(createPinia()).use(language)
setupRippleDirective(app)
const settings = useSettingStore()
settings.showFastEnter = false; settings.showSettingGuide = false; settings.showFestivalText = false
useSettingsHandlers().domOperations.setRootAttribute('data-box-mode', settings.boxBorderMode ? 'border-mode' : 'shadow-mode')
for (const route of router.getRoutes()) if (route.name) router.removeRoute(route.name)
for (const [path, name, title] of [['/overseas', 'overseas-home', '海外业务'], ['/overseas/admin/users', 'overseas-users', '用户与角色'], ['/auth/business', 'identity-business', '选择业务']]) router.addRoute({ path, name, component: { render: () => h('div') }, meta: { title } })
router.addRoute({ path: '/:pathMatch(.*)*', redirect: '/auth/business' })
app.use(router)
initializeTheme()
void router.isReady().then(() => app.mount('#app'))
