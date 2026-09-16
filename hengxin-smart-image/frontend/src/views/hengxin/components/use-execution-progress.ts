import { onScopeDispose, ref, watch } from 'vue'
import { getExecution } from '@/api/hengxin/execution'
import { createExecutionPoller, type ExecutionContext, type ExecutionState } from './execution-poller'

export function useExecutionProgress(context: () => ExecutionContext) {
  const state = ref<ExecutionState>({ loading: false, error: '' }), now = ref(Date.now())
  const poller = createExecutionPoller(getExecution, value => { state.value = value })
  let timer: ReturnType<typeof setInterval> | undefined
  watch(context, value => {
    clearInterval(timer); now.value = Date.now(); poller.setContext(value)
    if (value.active && !value.mock && value.identity) timer = setInterval(() => { now.value = Date.now() }, 1000)
  }, { immediate: true, flush: 'sync' })
  onScopeDispose(() => { clearInterval(timer); poller.dispose() })
  return { state, now, retry: poller.retry }
}
