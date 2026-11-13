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
import Workspace from './Workspace.vue'
import Library from './Library.vue'
import Skills from './Skills.vue'
import { skillsPath, canManageSkills } from './skills-state'
import { libraryPath } from './archives'
import { workspaces } from './workspaces'
import '@styles/core/tailwind.css'
import '@styles/index.scss'
import '@/views/hengxin/prototype.css'
import './style.css'

const app = createApp(App)
document.body.classList.add('domestic-studio-preview')
app.use(createPinia()).use(language)
setupRippleDirective(app)
useUserStore().info = { roles: ['super_admin'] }
const settings = useSettingStore()
settings.showFastEnter = false
settings.showSettingGuide = false
settings.showFestivalText = false
settings.uniqueOpened = false
initializeTheme()
useSettingsHandlers().domOperations.setRootAttribute('data-box-mode', settings.boxBorderMode ? 'border-mode' : 'shadow-mode')
const entry = (path: string, title: string, icon: string): AppRouteRecord => ({ path, name: `preview-${path}`, component: '/preview-only', meta: { title, icon, keepAlive: false } })
const menus: AppRouteRecord[] = [
  { ...entry('/api-image-edits', 'API 换套图', 'ri:exchange-2-line'), children: [entry('/api-image-edits/create', '新建换图', 'ri:image-add-line'), entry('/api-image-edits/records', '换图记录', 'ri:history-line')] },
  { ...entry('/new-product', '新品生成', 'ri:sparkling-line'), children: workspaces.filter(item => item.group === 'new').map(item => entry(item.path, item.title, 'ri:chat-ai-line')) },
  { ...entry('/product-replace', '产品替换', 'ri:shuffle-line'), children: workspaces.filter(item => item.group === 'replace').map(item => entry(item.path, item.title, 'ri:chat-ai-line')) },
  entry(libraryPath, '成品库', 'ri:archive-line'),
  { ...entry('/management', '管理中心', 'ri:settings-3-line'), children: [entry('/management/activity', '调用与执行', 'ri:bar-chart-line'), entry('/management/retention', '自动清理', 'ri:history-line'), entry('/management/users', '用户与角色', 'ri:group-line'), ...(canManageSkills() ? [entry(skillsPath, 'Skills 管理', 'ri:book-open-line')] : []), entry('/management/settings', '系统配置', 'ri:settings-3-line'), entry('/management/codex-auth', 'Codex 账号', 'ri:key-2-line')] },
]
const placeholder = { render: () => h('div', { class: 'hx-page' }, [h('h1', '现有业务页面'), h('p', '本次独立预览聚焦新增工作台，请点击左侧「新品生成」或「产品替换」。')]) }
useMenuStore().setMenuList(menus)
useMenuStore().setHomePath(workspaces[0].path)
for (const route of router.getRoutes()) if (route.name) router.removeRoute(route.name)
for (const menu of menus) router.addRoute({ path: menu.path, name: menu.name, meta: menu.meta, component: menu.path === libraryPath ? Library : { render: () => h(RouterView) }, children: (menu.children || []).map(child => ({ path: child.path, name: child.name, meta: child.meta, component: child.path === skillsPath ? Skills : child.path === libraryPath ? Library : workspaces.some(item => item.path === child.path) ? Workspace : placeholder })) })
router.addRoute({ path: '/new-product/studio', redirect: workspaces[0].path })
router.addRoute({ path: '/product-replace/studio', redirect: workspaces[2].path })
router.addRoute({ path: '/:pathMatch(.*)*', redirect: workspaces[0].path })
router.beforeEach(to => to.path === skillsPath && !canManageSkills() ? workspaces[0].path : true)
router.afterEach(to => useWorktabStore().openTab({ title: String(to.meta.title), path: to.path, name: String(to.name), keepAlive: false }))
app.use(router)
void router.isReady().then(() => app.mount('#app'))
