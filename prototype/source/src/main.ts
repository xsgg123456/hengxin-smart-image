import App from './App.vue'
import { useUserStore } from './store/modules/user'
import { useWorktabStore } from './store/modules/worktab'
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
// Migrate only the replaced navigation tabs; preserve tasks and prototype data.
const worktabs = useWorktabStore()
worktabs.opened = worktabs.opened.filter(tab => !['/wallpaper/index', '/product/index', '/text/index'].includes(tab.path))
// Local interaction prototype only; no production authentication or API.
useUserStore().setLoginStatus(true)
initRouter(app)
setupGlobDirectives(app)
setupErrorHandle(app)

app.use(language)
app.mount('#app')
