import App from './App.vue'
import { useUserStore } from './store/modules/user'
import { bootstrapUser } from './api/hengxin/bootstrap-user'
import { bootstrap, retryBootstrap } from './api/hengxin/bootstrap'
import { refreshWorkspace } from './views/hengxin/model'
import { fetchGetUserInfo } from './api/auth'
import { createApp } from 'vue'
import { initStore } from './store'                 // Store
import { initRouter, router } from './router'               // Router
import { useWorktabStore } from './store/modules/worktab'
import { resetRouterState, resetRouteInitState } from './router/guards/beforeEach'
import { isMockMode } from './api/hengxin/client'
import { getLoginScenario } from './api/hengxin/session'
import { ApiError } from './api/hengxin/http'
import { identity } from './api/hengxin/identity'
import { installIdentityLifecycle } from './api/hengxin/identity-lifecycle'
import { createBootstrapRunner } from './api/hengxin/bootstrap-runner'
import { installImageIdentity } from './api/hengxin/image-identity'
import { restoreIdentityRoutes } from './api/hengxin/identity-routing'
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
let routesNeedRefresh = false
function lockContent() {
  bootstrap.locked = true
  document.documentElement.dataset.identityLocked = 'true'
}
function clearIdentity() {
  routesNeedRefresh = true
  lockContent()
  bootstrap.ready = false
  bootstrap.loading = false
  useUserStore().setLoginStatus(false)
  useUserStore().info = {}
  useUserStore().accessToken = ''
  useUserStore().refreshToken = ''
  useUserStore().setLockStatus(false)
  useUserStore().setLockPassword('')
  useUserStore().setSearchHistory([])
  useWorktabStore().opened = []
  useWorktabStore().current = {}
  useWorktabStore().keepAliveExclude = []
  resetRouterState(0)
}
identity.subscribe(reason => {
  if (reason === 'suspended') {
    lockContent()
    if (!bootstrap.ready && routerInitialized) {
      routesNeedRefresh = true
      resetRouteInitState()
    }
    return
  }
  clearIdentity()
  bootstrap.authRequired = reason === 'invalid'
  if (reason === 'invalid') bootstrap.error = '会话已过期或账号无权访问，请重新登录'
})
window.addEventListener('hengxin:unauthorized', () => identity.invalidate(identity.epoch))
window.addEventListener('hengxin:identity-changed', () => {
  identity.advance('changed')
  void retryBootstrap.run()
})
identity.configureProbe(fetchGetUserInfo)
retryBootstrap.run = createBootstrapRunner({
  start() { lockContent(); bootstrap.loading = true; bootstrap.error = '' },
  async load() {
    const user = await fetchGetUserInfo()
    if (isMockMode) await refreshWorkspace()
    return user
  },
  async accept(user) {
    const epoch = identity.epoch
    const old = useUserStore().info
    if (old.userId && (old.userId !== user.userId || JSON.stringify(old.roles) !== JSON.stringify(user.roles))) {
      identity.advance('changed')
      void retryBootstrap.run()
      return
    }
    useUserStore().setUserInfo(user)
    useUserStore().setLoginStatus(true)
    bootstrapUser.offer(user)
    try {
    if (!routerInitialized) {
      initRouter(app)
      routerInitialized = true
      await router.isReady()
      identity.assert(epoch)
    }
    if (routesNeedRefresh) {
      await restoreIdentityRoutes(router, epoch)
      routesNeedRefresh = false
    }
    } finally { bootstrapUser.clear() }
    identity.assert(epoch)
    bootstrap.authRequired = false
    bootstrap.ready = true
    bootstrap.generation = identity.epoch
    bootstrap.locked = document.visibilityState === 'hidden'
    if (!bootstrap.locked) delete document.documentElement.dataset.identityLocked
  },
  fail(error) {
    bootstrap.error = error instanceof Error ? error.message : '工作区启动失败'
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      identity.invalidate(identity.epoch)
    }
  },
  finish() { bootstrap.loading = false }
})
installIdentityLifecycle({ window, document, lock: lockContent, resume: () => retryBootstrap.run() })
installImageIdentity(document)
const loginPath = window.location.hash.split('?')[0] === '#/auth/login' || window.location.pathname === '/auth/login'
if (loginPath || (isMockMode && getLoginScenario() !== 'success')) bootstrap.authRequired = true
else void retryBootstrap.run()
