import { reactive } from 'vue'
export const bootstrap = reactive({ ready: false, locked: true, generation: 0, loading: false, error: '', authRequired: false })
export const retryBootstrap = { run: async () => {} }
