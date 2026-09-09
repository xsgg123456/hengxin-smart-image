import App from './App.vue'
import { useUserStore } from './store/modules/user'
import { bootstrap, retryBootstrap } from './api/hengxin/bootstrap'
import { refreshWorkspace } from './views/hengxin/model'
import { fetchGetUserInfo } from './api/auth'
import { createApp } from 'vue'
import { initStore } from './store'                 // Store
import { initRouter } from './router'               // Router
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
setupGlobDirectives(app)
setupErrorHandle(app)

app.use(language)
app.mount('#app')

retryBootstrap.run = async () => {
  if (bootstrap.loading) return
  bootstrap.loading = true
  bootstrap.error = ''
  try {
    const user = await fetchGetUserInfo()
    await refreshWorkspace()
    useUserStore().setUserInfo(user)
    useUserStore().setLoginStatus(true)
    initRouter(app)
    bootstrap.ready = true
  } catch (error) {
    bootstrap.error = error instanceof Error ? error.message : '工作区启动失败'
  } finally { bootstrap.loading = false }
}
void retryBootstrap.run()
