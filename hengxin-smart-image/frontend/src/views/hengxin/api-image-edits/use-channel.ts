import { computed, onBeforeUnmount, ref } from 'vue'
import { apiImages, errorText } from '@/api/api-image-edits'
import { useUserStore } from '@/store/modules/user'
import type { ApiChannel } from '@/types/api-image-edits'
import { identity } from '@/api/hengxin/identity'
export function useChannel() {
  const status = ref<ApiChannel>(), error = ref(''), loading = ref(true), busy = ref(false)
  const isAdmin = computed(() => useUserStore().getUserInfo.roles?.includes('super_admin') || false)
  const blocked = computed(() => loading.value || !!error.value || !status.value?.enabled || !!status.value?.paused)
  let alive = true, serial = 0, timer: ReturnType<typeof setTimeout> | undefined
  async function load() {
    if (!alive || document.hidden) return
    const version = ++serial
    try { const value = await apiImages.status(); if (alive && version === serial) { status.value = value; error.value = '' } }
    catch (e) { if (alive && version === serial) error.value = errorText(e) }
    finally { if (alive && version === serial) { loading.value = false; clearTimeout(timer); if (!document.hidden) timer = setTimeout(load, 10000) } }
  }
  async function resume() {
    if (busy.value) return
    busy.value = true; error.value = ''
    try { await apiImages.resume(); await load() } catch (e) { error.value = errorText(e) }
    finally { busy.value = false }
  }
  void load()
  async function visibilityChanged() {
    clearTimeout(timer); serial++
    if (document.hidden || !alive) return
    const epoch = identity.epoch
    await identity.verify(epoch, true)
    if (alive && identity.current(epoch) && !document.hidden) void load()
  }
  document.addEventListener('visibilitychange', visibilityChanged)
  onBeforeUnmount(() => { alive = false; clearTimeout(timer); document.removeEventListener('visibilitychange', visibilityChanged) })
  return { status, error, loading, busy, isAdmin, blocked, load, resume }
}
