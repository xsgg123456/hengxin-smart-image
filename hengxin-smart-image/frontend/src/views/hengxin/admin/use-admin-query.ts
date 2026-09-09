import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { ApiError } from '@/api/hengxin/http'
export function useAdminQuery<T>(query: () => Promise<T>) {
  const data = shallowRef<T>(), loading = ref(false), error = ref('')
  let sequence = 0
  async function load() {
    const current = ++sequence; loading.value = true; error.value = ''
    try { const result = await query(); if (current === sequence) data.value = result }
    catch (reason) { if (current === sequence) { error.value = reason instanceof Error ? reason.message : '读取失败，请重试'; if (reason instanceof ApiError && [401, 403].includes(reason.status)) data.value = undefined } }
    finally { if (current === sequence) loading.value = false }
  }
  onMounted(load); onBeforeUnmount(() => { sequence++ })
  return { data, loading, error, load }
}
