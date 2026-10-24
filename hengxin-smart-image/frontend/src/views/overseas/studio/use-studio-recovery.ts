import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { createStudioOutputsApi, recoveryError, type RecoverableFile, type RecoveryResult } from '@/api/overseas/studio-outputs'
import { IdentityError } from '@/api/identity/request'

interface Context { taskId: string; conversationId: string; readonly: boolean; busy: boolean }
export function useStudioRecovery(context: () => Context, saved: () => void, failure: (reason: unknown) => void, api = createStudioOutputsApi()) {
  const items = ref<RecoverableFile[]>([]), selected = ref<string[]>([]), loading = ref(false), saving = ref(false)
  const serverBusy = ref(false), error = ref(''), result = ref<RecoveryResult>(), loaded = ref(false)
  let controller: AbortController | undefined
  const blocked = computed(() => context().readonly || context().busy || serverBusy.value || loading.value || saving.value)
  const canSave = computed(() => !blocked.value && selected.value.length > 0 && selected.value.length <= 100)
  function report(reason: unknown) {
    error.value = recoveryError(reason)
    if (reason instanceof IdentityError && [401, 403].includes(reason.status)) failure(reason)
  }
  async function load() {
    if (saving.value) return
    controller?.abort()
    const current = new AbortController(); controller = current
    const target = context(); loading.value = true; error.value = ''; loaded.value = false
    try {
      const response = await api.list(target.taskId, target.conversationId, current.signal)
      if (controller !== current || current.signal.aborted) return
      items.value = response.items; serverBusy.value = response.busy; loaded.value = true
      selected.value = selected.value.filter(id => response.items.some(item => item.id === id))
    } catch (reason) { if (controller === current && !current.signal.aborted) report(reason) }
    finally { if (controller === current) loading.value = false }
  }
  async function recover() {
    if (!canSave.value) return
    const files = items.value.filter(item => selected.value.includes(item.id)).map(({ id, version }) => ({ id, version }))
    if (!files.length) return
    controller?.abort()
    const current = new AbortController(); controller = current
    const target = context(); saving.value = true; error.value = ''; result.value = undefined
    try {
      const response = await api.recover(target.taskId, target.conversationId, files, current.signal)
      if (controller !== current || current.signal.aborted) return
      result.value = response
      // Keep unsuccessful selections for a deliberate retry, including a timed-out request.
      const failed = new Set(response.errors.map(item => item.id))
      selected.value = selected.value.filter(id => failed.has(id))
      if (response.saved.length) saved()
    } catch (reason) { if (controller === current && !current.signal.aborted) report(reason) }
    finally {
      if (controller === current) {
        saving.value = false
        if (result.value?.saved.length) void load()
      }
    }
  }
  function toggle(id: string, checked: boolean) {
    if (blocked.value) return
    if (!checked) selected.value = selected.value.filter(value => value !== id)
    else if (selected.value.length < 100 && !selected.value.includes(id)) selected.value.push(id)
  }
  watch(() => [context().taskId, context().conversationId], () => {
    controller?.abort(); controller = undefined; saving.value = false; items.value = []; selected.value = []; result.value = undefined
    serverBusy.value = false; void load()
  }, { immediate: true })
  watch(() => context().busy, (busy, previous) => { if (previous && !busy && !saving.value) void load() })
  onBeforeUnmount(() => { controller?.abort(); controller = undefined })
  return { items, selected, loading, saving, serverBusy, error, result, loaded, blocked, canSave, load, recover, toggle }
}
