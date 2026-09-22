import { computed, onBeforeUnmount, ref } from 'vue'
import { apiImages, errorText } from '@/api/api-image-edits'
import { useUserStore } from '@/store/modules/user'
import type { ApiChannel } from '@/types/api-image-edits'
export function useChannel() {
  const status = ref<ApiChannel>(), error = ref(''), loading = ref(true), busy = ref(false)
  const isAdmin = computed(() => useUserStore().getUserInfo.roles?.includes('super_admin') || false)
  const blocked = computed(() => loading.value || !!error.value || !status.value?.enabled || !!status.value?.paused)
  let alive = true, serial = 0, timer: ReturnType<typeof setTimeout> | undefined
  async function load() {
    const version = ++serial
    try { const value = await apiImages.status(); if (alive && version === serial) { status.value = value; error.value = '' } }
    catch (e) { if (alive && version === serial) error.value = errorText(e) }
    finally { if (alive && version === serial) { loading.value = false; clearTimeout(timer); timer = setTimeout(load, 5000) } }
  }
  async function resume() {
    if (busy.value) return
    busy.value = true; error.value = ''
    try { await apiImages.resume(); await load() } catch (e) { error.value = errorText(e) }
    finally { busy.value = false }
  }
  void load()
  onBeforeUnmount(() => { alive = false; clearTimeout(timer) })
  return { status, error, loading, busy, isAdmin, blocked, load, resume }
}
