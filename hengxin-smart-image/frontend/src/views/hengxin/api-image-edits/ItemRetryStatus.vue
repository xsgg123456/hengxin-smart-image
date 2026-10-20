<template>
  <div class="retry-status">
    <p v-if="item.retry" class="hx-footnote">本轮 {{ item.retry.attempts }}/{{ item.retry.maxAttempts }} 次</p>
    <p v-else-if="item.retries" class="hx-footnote">历史记录：已自动重试 {{ item.retries }} 次</p>
    <p v-if="message" class="hx-footnote">{{ message }}</p>
    <p v-if="item.retry?.reason && item.state !== 'succeeded'" class="hx-footnote">{{ item.retry.reason }}</p>
    <p v-if="item.retry?.deadlineAt && !['succeeded', 'failed'].includes(item.state)" class="hx-footnote">本轮发送截止：{{ friendlyTime(item.retry.deadlineAt) }}</p>
    <ElButton v-if="item.retry?.canStop || pendingStop" size="small" type="warning" plain :loading="operation.state.busy && pendingStop" :disabled="!canStop" @click="stop">{{ operation.state.busy && pendingStop ? '正在停止…' : pendingStop ? '确认原停止请求' : accepted ? '已请求停止' : '停止重试' }}</ElButton>
  </div>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { apiImages } from '@/api/api-image-edits'
import type { ApiItem } from '@/types/api-image-edits'
import { itemCommand, friendlyTime } from './item-command'
import { itemRetryText } from './retry-status'
import { useRetryClock } from './use-retry-clock'
const props = defineProps<{ taskId: string; item: ApiItem; user: string; locked: boolean }>()
const emit = defineEmits<{ accepted: [] }>()
const now = useRetryClock(), accepted = ref(false)
const operation = computed(() => itemCommand(props.user, props.taskId, props.item.id))
const pendingStop = computed(() => operation.value.state.pending?.command.kind === 'stop')
const canStop = computed(() => !props.locked && !accepted.value && !operation.value.state.busy && (pendingStop.value || (!operation.value.state.pending && !!props.item.retry?.canStop)))
const message = computed(() => itemRetryText(props.item, now.value))
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
