import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import Fixture from './fixture.vue'
createApp(Fixture).use(ElementPlus).mount('#app')
