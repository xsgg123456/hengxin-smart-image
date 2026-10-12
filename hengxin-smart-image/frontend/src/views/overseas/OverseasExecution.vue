<template>
  <ElCard class="art-card hx-section hx-gap execution-panel" shadow="never">
    <div class="hx-heading"><h2>执行状态</h2><ElButton :loading="busy" :disabled="stopping" @click="refresh">刷新执行状态</ElButton></div>
    <p v-if="busy && !loaded" role="status">正在读取执行状态…</p>
    <ElAlert v-if="error" :title="error" type="warning" :closable="false" class="hx-gap" />
    <p v-if="loaded && !jobs.length" class="hx-muted">暂无执行记录，尚未开始分析或生成。</p>
    <div v-for="job in jobs" :key="job.id" class="hx-gap">
      <h3>{{ executionKinds[job.kind] }} <ElTag>{{ executionStatuses[job.status] }}</ElTag></h3>
      <p class="hx-muted">创建时间：{{ job.createdAt }}</p>
      <p v-if="job.error" role="alert">{{ job.error }}</p>
      <p v-if="job.status === 'uncertain'" role="alert">执行结果尚未确认，请联系管理员核实，切勿重复执行。</p>
      <div v-if="canCancel && ['queued', 'running', 'collecting'].includes(job.status)" class="hx-gap"><ElButton type="danger" text :disabled="busy || stopping || !!error" @click="cancel(job)">停止执行</ElButton></div>
    </div>
    <ElCollapse v-if="events.length" class="hx-gap"><ElCollapseItem title="执行记录" name="events"><p v-for="event in events" :key="event.id">{{ event.createdAt }} · {{ event.message }}</p></ElCollapseItem></ElCollapse>
  </ElCard>
</template>
<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import { IdentityError } from '@/api/identity/request'
import { createExecutionApi, executionError, executionKinds, executionStatuses, type ExecutionEvent, type ExecutionJob } from '@/api/overseas/execution'
const props = defineProps<{ taskId: string; canCancel: boolean }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const api = createExecutionApi(), jobs = ref<ExecutionJob[]>([]), events = ref<ExecutionEvent[]>([])
const error = ref(''), busy = ref(false), loaded = ref(false), stopping = ref(false)
let epoch = 0, cursor = 0, alive = true, blocked = false, confirming = false, timer: ReturnType<typeof setTimeout> | undefined, controller: AbortController | undefined
function closeConfirmation() { if (confirming) { confirming = false; ElMessageBox.close() } }
function stop() { ++epoch; clearTimeout(timer); controller?.abort(); busy.value = false }
function failed(reason: unknown) {
  error.value = executionError(reason)
  if (reason instanceof IdentityError && [401, 403, 404].includes(reason.status)) {
    blocked = true; stop(); jobs.value = []; events.value = []; cursor = 0; loaded.value = false; emit('failure', reason)
  }
}
async function poll() {
  if (!alive || blocked || busy.value || stopping.value) return
  const current = epoch; busy.value = true; controller = new AbortController()
  try {
    const batch = await api.events(props.taskId, cursor, controller.signal)
    const next = await api.jobs(props.taskId, controller.signal)
    if (current !== epoch) return
    jobs.value = next; events.value = [...events.value, ...batch.items]; cursor = batch.cursor; loaded.value = true; error.value = ''
  } catch (reason) { if (current === epoch) failed(reason) }
  finally { if (current === epoch) { busy.value = false; timer = setTimeout(poll, 2000) } }
}
function refresh() { if (blocked || stopping.value) return; stop(); void poll() }
async function cancel(job: ExecutionJob) {
  if (!props.canCancel || stopping.value) return
  stop(); const current = epoch; stopping.value = true
  try {
    confirming = true
    await ElMessageBox.confirm('确定停止这次执行？停止请求提交后，需要等待执行结束确认。', '停止执行', { type: 'warning', confirmButtonText: '确认停止', cancelButtonText: '继续执行' })
    confirming = false
    if (!alive || current !== epoch || !props.canCancel) return
    const value = await api.cancel(job.id, job.version)
    if (current === epoch) jobs.value = jobs.value.map(item => item.id === value.id ? value : item)
  } catch (reason) {
    if (current === epoch && reason !== 'cancel' && reason !== 'close') {
      failed(reason)
      if (reason instanceof IdentityError && reason.status === 0) error.value = '停止请求结果尚未确认，正在核实最新状态，请勿重复提交。'
    }
  } finally {
    confirming = false
    if (current === epoch) {
      stopping.value = false
      const message = error.value
      await poll()
      if (current === epoch && !error.value && message) error.value = message
    }
  }
}
watch(() => props.taskId, () => { stop(); closeConfirmation(); stopping.value = false; blocked = false; cursor = 0; jobs.value = []; events.value = []; error.value = ''; loaded.value = false; void poll() }, { immediate: true })
watch(() => props.canCancel, allowed => { if (!allowed && stopping.value) { stop(); closeConfirmation(); stopping.value = false; void poll() } })
onUnmounted(() => { alive = false; stop(); closeConfirmation(); jobs.value = []; events.value = [] })
</script>
<style scoped>
.hx-heading { flex-wrap: wrap; gap: 12px; }
.execution-panel { min-width: 0; overflow-wrap: anywhere; }
</style>
