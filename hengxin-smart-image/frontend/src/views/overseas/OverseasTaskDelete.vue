<template>
  <span class="task-delete">
    <ElButton v-if="canDelete" text type="danger" :loading="sending || opening" :disabled="currentStatus === 'deleting' || currentStatus === 'deleted'" @click="openDialog">{{ currentStatus === 'deleting' ? '正在删除' : currentStatus === 'delete_failed' ? '重试删除' : '删除' }}</ElButton>
    <span v-if="error && !open && error !== task.deletionError" class="task-delete-error" role="alert">{{ error }}</span>
    <ElDialog v-model="open" title="永久删除任务" width="min(560px, 94vw)" append-to-body :close-on-click-modal="false" :close-on-press-escape="!sending" :show-close="!sending">
      <p class="task-delete-name">任务：{{ snapshot?.name }}</p>
      <ElAlert title="任务资料、对话、未归档图片及本任务的 CLI 临时数据将永久删除，已归档成品保留。" type="warning" :closable="false" />
      <ElForm label-position="top" class="hx-gap" @submit.prevent="remove"><ElFormItem label="输入完整任务名称以确认删除"><ElInput v-model="confirmationName" aria-label="确认删除任务名称" :disabled="sending" autocomplete="off" /></ElFormItem></ElForm>
      <ElAlert v-if="error" :title="error" type="error" :closable="false" />
      <template #footer><ElButton :disabled="sending" @click="open = false">取消</ElButton><ElButton type="danger" :loading="sending" :disabled="!confirmed" @click="remove">确认永久删除</ElButton></template>
    </ElDialog>
  </span>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { taskError, type TaskDeletion, type TaskSummary, type TasksApi } from '@/api/overseas/tasks'
const props = defineProps<{ task: TaskSummary; api: Pick<TasksApi, 'get' | 'remove' | 'deletion'> }>()
const emit = defineEmits<{ changed: [value: TaskDeletion]; failure: [reason: unknown] }>()
const open = ref(false), opening = ref(false), sending = ref(false), confirmationName = ref(''), error = ref(''), snapshot = ref<TaskSummary>()
const state = ref<TaskDeletion>()
const currentStatus = computed(() => state.value?.status || props.task.deletionStatus || props.task.status)
const canDelete = computed(() => props.task.capabilities.includes('task.delete'))
const confirmed = computed(() => !!snapshot.value?.capabilities.includes('task.delete') && confirmationName.value === snapshot.value.name && canDelete.value && !sending.value && currentStatus.value !== 'deleting')
let alive = true, timer: ReturnType<typeof setTimeout> | undefined
function fail(reason: unknown) {
  error.value = taskError(reason)
  if (reason instanceof IdentityError && [401, 403].includes(reason.status)) { open.value = false; clearTimeout(timer); emit('failure', reason); return true }
  return false
}
function schedule() { clearTimeout(timer); if (alive && currentStatus.value === 'deleting') timer = setTimeout(() => { void poll() }, 2000) }
function apply(value: TaskDeletion) {
  if (!alive) return
  state.value = value; error.value = value.error || (value.status === 'delete_failed' ? '删除未完成，请重试。已归档成品保留。' : '')
  if (value.status !== 'delete_failed') open.value = false
  emit('changed', value); schedule()
}
async function poll() {
  try { const value = await props.api.deletion(props.task.id); if (alive) apply(value) }
  catch (reason) { if (alive && !fail(reason)) schedule() }
}
async function openDialog() {
  if (!canDelete.value || sending.value || opening.value || currentStatus.value === 'deleting') return
  opening.value = true; error.value = ''; confirmationName.value = ''
  try {
    const value = await props.api.get(props.task.id)
    if (!alive) return
    if (!value.capabilities.includes('task.delete')) { fail(new IdentityError(403, '删除权限已变化，请刷新。')); return }
    snapshot.value = value
    if (value.deletionStatus === 'deleting' || value.status === 'deleting') { apply({ taskId: value.id, status: 'deleting', error: value.deletionError || null }); return }
    state.value = undefined; open.value = true
  } catch (reason) { if (alive) fail(reason) }
  finally { if (alive) opening.value = false }
}
async function remove() {
  if (!confirmed.value || !snapshot.value) return
  const task = snapshot.value; sending.value = true; error.value = ''
  try { const value = await props.api.remove(task.id, task.version, confirmationName.value); if (alive) apply(value) }
  catch (reason) {
    if (!alive || fail(reason)) return
    if (reason instanceof IdentityError && reason.status === 409) {
      try {
        const latest = await props.api.get(task.id)
        if (alive) {
          snapshot.value = latest
          if (latest.name !== task.name) confirmationName.value = ''
          if (latest.status === 'deleting') apply({ taskId: task.id, status: 'deleting', error: latest.deletionError || null })
        }
      } catch (refreshError) { if (alive) fail(refreshError) }
    }
    // 网络中断不等于删除失败；只读核实实际状态，不重新发起删除。
    if (reason instanceof IdentityError && (reason.status === 0 || reason.status >= 500)) {
      try { const value = await props.api.deletion(task.id); if (alive) apply(value) }
      catch (verificationError) { if (alive && verificationError instanceof IdentityError && [401, 403].includes(verificationError.status)) fail(verificationError) }
    }
  } finally { if (alive) sending.value = false }
}
watch(() => [props.task.deletionStatus, props.task.status], () => { if (!state.value) schedule() }, { immediate: true })
onUnmounted(() => { alive = false; clearTimeout(timer); snapshot.value = undefined })
</script>
<style scoped>
.task-delete { display: inline-flex; flex-wrap: wrap; align-items: center; vertical-align: middle; }
.task-delete-error { display: block; width: 100%; max-width: 250px; color: var(--el-color-danger); white-space: normal; overflow-wrap: anywhere; font-size: 12px; }
.task-delete-name { overflow-wrap: anywhere; margin-bottom: 16px; }
</style>
