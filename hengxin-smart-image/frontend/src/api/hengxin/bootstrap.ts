import { reactive } from 'vue'
export const bootstrap = reactive({ ready: false, loading: false, error: '' })
export const retryBootstrap = { run: async () => {} }
