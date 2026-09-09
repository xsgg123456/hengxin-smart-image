import { reactive } from 'vue'
export const bootstrap = reactive({ ready: false, loading: false, error: '', authRequired: false })
export const retryBootstrap = { run: async () => {} }
