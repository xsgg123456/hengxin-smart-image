import { computed, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import { getTask } from '@/api/tasks'
import type { TaskDetailData } from '@/types/hengxin'

export function useTaskDetail(taskId: Ref<string>, visible: Ref<boolean>) {
  const data = ref<TaskDetailData>(), loading = ref(false), error = ref('')
  let request = 0, timer: ReturnType<typeof setTimeout> | undefined
  async function load(quiet = false) {
    if (!visible.value || !taskId.value) return
    clearTimeout(timer)
    const current = ++request
    loading.value = !quiet
    try {
      const result = await getTask(taskId.value)
      if (current !== request) return
      data.value = result; error.value = ''
    } catch (reason) {
      if (current !== request) return
      error.value = reason instanceof Error ? reason.message : '详情加载失败，请重试'
      if (reason && typeof reason === 'object' && (('status' in reason && reason.status === 404) || ('code' in reason && reason.code === 'NOT_FOUND'))) data.value = undefined
    } finally {
      if (current === request) {
        loading.value = false
        if (visible.value) timer = setTimeout(() => { void load(true) }, 3000)
      }
    }
  }
  watch([taskId, visible], ([id, shown], previous) => {
    clearTimeout(timer); request++; loading.value = false
    if (id !== previous?.[0]) { data.value = undefined; error.value = '' }
    if (shown) void load()
  }, { immediate: true })
  onBeforeUnmount(() => { clearTimeout(timer); request++ })
  const task = computed(() => data.value?.task)
  const complete = computed(() => !error.value && !!data.value && task.value?.state === '待查看' && data.value.slots.length > 0 && data.value.slots.every(slot => slot.currentVersionId && slot.versions.some(v => v.id === slot.currentVersionId)))
  return { data, task, loading, error, complete, load }
}
