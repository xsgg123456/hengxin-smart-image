import { onActivated, onBeforeUnmount, onDeactivated, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { listTasks } from '@/api/tasks'
import { taskPollDelay } from '../task-state'
import type { Task, TaskPage } from '@/types/hengxin'
import { useListLocation } from '../list-location'

export function useTaskList() {
  const location = useListLocation(useRouter(), '/tasks/index', 'task')
  const { mode, search, state, scope, page } = location
  const tasks = ref<Task[]>([]), stats = ref<TaskPage['stats']>(), total = ref(0)
  const loading = ref(false), error = ref(''), active = ref(true), pageSize = 12
  let request = 0, timer: ReturnType<typeof setTimeout> | undefined
  function stop() { clearTimeout(timer); request++; loading.value = false }
  async function load(quiet = false) {
    if (!active.value) return
    clearTimeout(timer)
    const current = ++request
    loading.value = !quiet
    try {
      const result = await listTasks({ page: page.value, pageSize, scope: scope.value, search: search.value.trim(), mode: mode.value === 'all' ? undefined : mode.value, state: state.value === 'all' ? undefined : state.value })
      if (current !== request) return
      const lastPage = Math.max(1, Math.ceil(result.total / pageSize))
      if (page.value > lastPage) { page.value = lastPage; return }
      tasks.value = result.items; total.value = result.total; stats.value = result.stats; error.value = ''
    } catch (reason) {
      if (current === request) error.value = reason instanceof Error ? reason.message : '任务加载失败，请重试'
    } finally {
      if (current === request) {
        loading.value = false
        if (active.value) timer = setTimeout(() => { void load(true) }, taskPollDelay(tasks.value))
      }
    }
  }
  watch([mode, search, state, scope, page], () => { void load() }, { immediate: true })
  onActivated(() => { active.value = true; void load() })
  onDeactivated(() => { active.value = false; stop() })
  onBeforeUnmount(() => { active.value = false; stop() })
  return { ...location, tasks, stats, total, pageSize, loading, error, active, load }
}
