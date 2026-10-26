import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { router } from '@/router'
import language from '@/locales'
import { useSettingStore } from '@/store/modules/setting'
import { initializeTheme } from '@/hooks/core/useTheme'
import { useSettingsHandlers } from '@/components/core/layouts/art-settings-panel/composables/useSettingsHandlers'
import { setupRippleDirective } from '@/directives/business/ripple'
import App from './App.vue'
import { installMenus } from './navigation'
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
for (const route of router.getRoutes()) if (route.name) router.removeRoute(route.name)
installMenus()
router.addRoute({ path: '/:pathMatch(.*)*', redirect: '/management/codex-auth' })
app.use(router)
void router.isReady().then(() => app.mount('#app'))
