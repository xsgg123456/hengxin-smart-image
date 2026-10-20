<template>
  <div class="retry-status">
    <ElButton v-if="item.retry?.canStop || pendingStop" size="small" text type="primary" :loading="operation.state.busy && pendingStop" :disabled="!canStop" @click="stop">{{ operation.state.busy && pendingStop ? '正在停止…' : pendingStop ? '重试停止' : accepted ? '已请求停止' : '停止自动重试' }}</ElButton>
  </div>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { apiImages } from '@/api/api-image-edits'
import type { ApiItem } from '@/types/api-image-edits'
import { itemCommand } from './item-command'
const props = defineProps<{ taskId: string; item: ApiItem; user: string; locked: boolean }>()
const emit = defineEmits<{ accepted: [] }>()
const accepted = ref(false)
const operation = computed(() => itemCommand(props.user, props.taskId, props.item.id))
const pendingStop = computed(() => operation.value.state.pending?.command.kind === 'stop')
const canStop = computed(() => !props.locked && !accepted.value && !operation.value.state.busy && (pendingStop.value || (!operation.value.state.pending && !!props.item.retry?.canStop)))
watch(() => [props.taskId, props.item.id, props.item.retry?.cycleId], () => { accepted.value = false })
async function stop() {
  if (!canStop.value) return
  const { taskId, item } = props
  if (await operation.value.submit({ kind: 'stop' }, (command, key) => {
    if (command.kind !== 'stop') throw new Error('请先确认此图片尚未完成的操作')
    return apiImages.stopItem(taskId, item.id, key)
  })) { accepted.value = true; emit('accepted') }
}
</script>
<style scoped>
.retry-status { overflow-wrap:anywhere; }
.retry-status .el-button { margin-top:8px; max-width:100%; }
</style>
