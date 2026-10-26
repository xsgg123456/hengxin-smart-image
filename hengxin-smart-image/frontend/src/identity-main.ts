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
router.addRoute({ path: '/overseas', redirect: '/overseas/tasks' })
for (const [path, name, title] of [['/overseas/admin/users', 'overseas-users', '用户与角色'], ['/overseas/admin/usage', 'overseas-usage', '调用统计'], ['/overseas/admin/monitor', 'overseas-monitor', '执行监控'], ['/overseas/admin/skills', 'overseas-skills', 'Skill 管理'], ['/overseas/admin/settings', 'overseas-settings', '系统配置'], ['/overseas/admin/codex-auth', 'overseas-codex-auth', 'Codex 账号'], ['/overseas/create', 'overseas-create', '提交图需'], ['/overseas/tasks', 'overseas-tasks', '工作流任务'], ['/overseas/archive', 'overseas-archive', '成品库'], ['/overseas/tasks/:id', 'overseas-task', '任务详情'], ['/auth/business', 'identity-business', '选择业务']]) router.addRoute({ path, name, component: { render: () => h('div') }, meta: { title } })
router.addRoute({ path: '/:pathMatch(.*)*', redirect: '/auth/business' })
app.use(router)
initializeTheme()
void router.isReady().then(() => app.mount('#app'))
