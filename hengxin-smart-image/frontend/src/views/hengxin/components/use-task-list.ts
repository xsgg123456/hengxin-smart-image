import { onActivated, onBeforeUnmount, onDeactivated, ref, watch } from 'vue'
import { listTasks } from '@/api/tasks'
import type { Mode, Task, TaskPage, TaskQuery } from '@/types/hengxin'

export function useTaskList() {
  const mode = ref<Mode | 'all'>('all'), search = ref(''), state = ref<TaskQuery['state'] | 'all'>('all')
  const tasks = ref<Task[]>([]), stats = ref<TaskPage['stats']>(), page = ref(1), total = ref(0)
  const loading = ref(false), error = ref(''), active = ref(true), pageSize = 12
  let request = 0, timer: ReturnType<typeof setTimeout> | undefined
  function stop() { clearTimeout(timer); request++; loading.value = false }
  async function load(quiet = false) {
    if (!active.value) return
    clearTimeout(timer)
    const current = ++request
    loading.value = !quiet
    try {
      const result = await listTasks({ page: page.value, pageSize, search: search.value.trim(), mode: mode.value === 'all' ? undefined : mode.value, state: state.value === 'all' ? undefined : state.value })
      if (current !== request) return
      const lastPage = Math.max(1, Math.ceil(result.total / pageSize))
      if (page.value > lastPage) { page.value = lastPage; return }
      tasks.value = result.items; total.value = result.total; stats.value = result.stats; error.value = ''
    } catch (reason) {
      if (current === request) error.value = reason instanceof Error ? reason.message : '任务加载失败，请重试'
    } finally {
      if (current === request) {
        loading.value = false
        if (active.value) timer = setTimeout(() => { void load(true) }, 4000)
      }
    }
  }
  watch([mode, search, state], () => { page.value = 1 }, { flush: 'sync' })
  watch([mode, search, state, page], () => { void load() }, { immediate: true })
  onActivated(() => { active.value = true; void load() })
  onDeactivated(() => { active.value = false; stop() })
  onBeforeUnmount(() => { active.value = false; stop() })
  return { mode, search, state, tasks, stats, page, total, pageSize, loading, error, active, load }
}
