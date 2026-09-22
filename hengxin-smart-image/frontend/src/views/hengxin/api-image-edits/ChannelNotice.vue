<template>
  <ElAlert v-if="error" :title="error" type="error" :closable="false" class="channel-notice"><ElButton text @click="$emit('refresh')">重新检查</ElButton></ElAlert>
  <ElAlert v-else-if="loading" title="正在检查 API 换套图状态…" type="info" :closable="false" class="channel-notice" />
  <ElAlert v-else-if="!status?.enabled" title="API 换套图尚未启用" description="请联系管理员完成服务端配置并启用独立 API 通道。" type="warning" show-icon :closable="false" class="channel-notice" />
  <ElAlert v-else-if="status.paused" title="API 通道已暂停" type="warning" show-icon :closable="false" class="channel-notice"><p>{{ status.reason || '请联系管理员检查服务配置或核实未确认的请求。' }}</p><ElButton v-if="admin" :loading="busy" @click="$emit('resume')">配置已修复，恢复通道</ElButton></ElAlert>
</template>
<script setup lang="ts">
import type { ApiChannel } from '@/types/api-image-edits'
defineProps<{ status?: ApiChannel; error: string; loading: boolean; admin: boolean; busy: boolean }>()
defineEmits<{ refresh: []; resume: [] }>()
</script>
<style scoped>.channel-notice { margin-bottom:20px; }.channel-notice p { overflow-wrap:anywhere; }</style>
