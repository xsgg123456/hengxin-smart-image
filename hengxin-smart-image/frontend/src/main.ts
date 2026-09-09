import App from './App.vue'
import { useUserStore } from './store/modules/user'
import { bootstrap, retryBootstrap } from './api/hengxin/bootstrap'
import { refreshWorkspace } from './views/hengxin/model'
import { fetchGetUserInfo } from './api/auth'
import { createApp } from 'vue'
import { initStore } from './store'                 // Store
import { initRouter, router } from './router'               // Router
import { useWorktabStore } from './store/modules/worktab'
import { resetRouterState } from './router/guards/beforeEach'
import { isMockMode } from './api/hengxin/client'
import { getLoginScenario } from './api/hengxin/session'
import { ApiError } from './api/hengxin/http'
import language from './locales'                    // 国际化
import '@styles/core/tailwind.css'                  // tailwind
import '@/views/hengxin/prototype.css'
import '@styles/index.scss'                         // 样式
import '@utils/sys/console.ts'                      // 控制台输出内容
import { setupGlobDirectives } from './directives'
import { setupErrorHandle } from './utils/sys/error-handle'

document.addEventListener(
  'touchstart',
  function () {},
  { passive: false }
)

const app = createApp(App)
initStore(app)
useUserStore().setLoginStatus(false)
useUserStore().info = {}
useWorktabStore().opened = []
useWorktabStore().keepAliveExclude = []
useUserStore().setSearchHistory([])
setupGlobDirectives(app)
setupErrorHandle(app)

app.use(language)
app.mount('#app')

let routerInitialized = false
window.addEventListener('hengxin:unauthorized', () => {
  bootstrap.ready = false
  bootstrap.authRequired = true
  bootstrap.error = '会话已过期，请重新登录'
  useUserStore().setLoginStatus(false)
  useUserStore().info = {}
  useUserStore().setSearchHistory([])
  useWorktabStore().opened = []
  useWorktabStore().keepAliveExclude = []
  resetRouterState(0)
})
window.addEventListener('hengxin:identity-changed', async () => {
  bootstrap.ready = false
  useUserStore().setLoginStatus(false)
  useUserStore().info = {}
  useUserStore().setSearchHistory([])
  useWorktabStore().opened = []
  useWorktabStore().keepAliveExclude = []
  resetRouterState(0)
  await retryBootstrap.run()
  if (bootstrap.ready) {
    bootstrap.ready = false
    await router.replace('/image-processing/wallpaper')
    bootstrap.ready = useUserStore().isLogin
  }
})
retryBootstrap.run = async () => {
  if (bootstrap.loading) return
  bootstrap.loading = true
  bootstrap.error = ''
  try {
    const user = await fetchGetUserInfo()
    await refreshWorkspace()
    useUserStore().setUserInfo(user)
    useUserStore().setLoginStatus(true)
    if (!routerInitialized) { initRouter(app); routerInitialized = true }
    bootstrap.authRequired = false
    bootstrap.ready = true
  } catch (error) {
    bootstrap.error = error instanceof Error ? error.message : '工作区启动失败'
    if (error instanceof ApiError && error.status === 401) bootstrap.authRequired = true
  } finally { bootstrap.loading = false }
}
const loginPath = window.location.hash.split('?')[0] === '#/auth/login' || window.location.pathname === '/auth/login'
if (loginPath || (isMockMode && getLoginScenario() !== 'success')) bootstrap.authRequired = true
else void retryBootstrap.run()
