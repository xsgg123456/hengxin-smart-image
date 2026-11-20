import { createApp, type Component } from 'vue'
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
export function mountIdentityPortal(overseasComponent?: Component) {
const app = createApp(IdentityPortal, { overseasComponent })
app.use(createPinia()).use(language)
setupRippleDirective(app)
const settings = useSettingStore()
settings.showFastEnter = false; settings.showSettingGuide = false; settings.showFestivalText = false
useSettingsHandlers().domOperations.setRootAttribute('data-box-mode', settings.boxBorderMode ? 'border-mode' : 'shadow-mode')
for (const route of router.getRoutes()) if (route.name) router.removeRoute(route.name)
router.addRoute({ path: '/overseas', redirect: '/overseas/design-center' })
router.addRoute({ path: '/overseas/create', redirect: '/overseas/design-center' })
router.addRoute({ path: '/overseas/tasks', redirect: to => ({ path: '/overseas/design-center', query: {...to.query,view:'tasks'} }) })
for (const [path, name, title] of [['/overseas/admin/users', 'overseas-users', '用户与角色'], ['/overseas/admin/activity', 'overseas-activity', '调用与执行'], ['/overseas/admin/skills', 'overseas-skills', 'Skill 管理'], ['/overseas/admin/settings', 'overseas-settings', '系统配置'], ['/overseas/admin/codex-auth', 'overseas-codex-auth', 'Codex 账号'], ['/overseas/design-center', 'overseas-design-center', '设计任务中心'], ['/overseas/creative-tools', 'overseas-creative-tools', '创作工具集'], ['/overseas/about', 'overseas-about', '关于我们'], ['/overseas/admin/feedback', 'overseas-feedback', '反馈管理'], ['/overseas/archive', 'overseas-archive', '成品库'], ['/overseas/tasks/:id', 'overseas-task', '任务详情'], ['/auth/business', 'identity-business', '选择业务'], ['/auth/login', 'identity-login', '企业登录'], ['/auth/callback', 'identity-callback', '企业授权']]) router.addRoute({ path, name, component: { render: () => h('div') }, meta: { title } })
for (const page of ['usage', 'monitor']) router.addRoute({ path: `/overseas/admin/${page}`, redirect: '/overseas/admin/activity' })
router.addRoute({ path: '/:pathMatch(.*)*', redirect: '/auth/business' })
app.use(router)
initializeTheme()
void router.isReady().then(() => app.mount('#app'))

}
