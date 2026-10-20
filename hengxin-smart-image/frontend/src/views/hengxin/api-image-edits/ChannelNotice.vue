<template>
  <ElAlert v-if="error" :title="error" type="error" :closable="false" class="channel-notice"><ElButton text @click="$emit('refresh')">重新检查</ElButton></ElAlert>
  <ElAlert v-else-if="loading" title="正在检查 API 换套图状态…" type="info" :closable="false" class="channel-notice" />
  <ElAlert v-else-if="!status?.enabled" title="服务暂不可用，请稍后再试。" type="warning" show-icon :closable="false" class="channel-notice" />
  <ElAlert v-else-if="status.paused" title="服务暂不可用，请稍后再试。" type="warning" show-icon :closable="false" class="channel-notice"><ElButton v-if="admin" :loading="busy" @click="$emit('resume')">恢复服务</ElButton></ElAlert>
  <ElAlert v-else-if="retryMessage" :title="retryMessage" type="warning" show-icon :closable="false" class="channel-notice" />
</template>
<script setup lang="ts">
import type { ApiChannel } from '@/types/api-image-edits'
import { computed } from 'vue'
import { channelRetryText } from './retry-status'
const props = defineProps<{ status?: ApiChannel; error: string; loading: boolean; admin: boolean; busy: boolean }>()
const retryMessage = computed(() => channelRetryText(props.status))
defineEmits<{ refresh: []; resume: [] }>()
</script>
<style scoped>.channel-notice { margin-bottom:20px; }.channel-notice p { overflow-wrap:anywhere; }</style>
