import { createApp } from 'vue'
import { createPinia } from 'pinia'
import language from './locales'
import IdentityPortal from './views/auth/IdentityPortal.vue'
import { initializeTheme } from './hooks/core/useTheme'
import '@styles/core/tailwind.css'
import '@styles/index.scss'
import '@/views/hengxin/prototype.css'
const app = createApp(IdentityPortal)
app.use(createPinia()).use(language)
initializeTheme()
app.mount('#app')
