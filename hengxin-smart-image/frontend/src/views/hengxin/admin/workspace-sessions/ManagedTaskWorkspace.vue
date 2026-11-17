<template>
  <div class="wm-page">
    <div class="wm-sync"><span :class="{ stale: !!error }">{{ error ? '会话同步已中断' : autoSync ? '会话自动同步' : '会话自动同步已暂停' }}<small>最后同步：{{ formatBeijingTime(lastSuccess, '尚未同步') }}（北京时间）</small></span><ElButton :loading="loading" @click="refresh">刷新会话</ElButton></div>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" />
    <SessionDetail v-if="sessionDetail && !denied" :key="selectedId" :detail="sessionDetail" :transcript="transcript" task-context @select="choose" @failure="handleFailure" />
    <ElSkeleton v-else-if="loading && detail.sessions.length" :rows="5" animated />
    <div v-else class="tc-card tc-empty"><strong>{{ detail.sessions.length ? '会话内容暂不可用' : '该任务尚未创建方案会话' }}</strong><p>{{ detail.sessions.length ? '请刷新会话后重试。' : '成员创建方案后，可在这里查看。' }}</p><span>管理员只读查看 · 无法代发消息或修改用户内容</span></div>
  </div>
</template>
<script setup lang="ts">
import { watch } from 'vue'
import type { ManagedTaskDetail } from '@/api/hengxin/domestic-tasks'
import { IdentityError } from '@/api/identity/request'
import { formatBeijingTime } from '@/utils/beijing-time'
import SessionDetail from './SessionDetail.vue'
import { useMonitor } from './use-monitor'
const props = defineProps<{ detail: ManagedTaskDetail; autoSync: boolean; initialSession?: string }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const { detail: sessionDetail, transcript, selectedId, autoSync, loading, denied, error, lastSuccess, refresh, select, failure } = useMonitor(undefined, false)
function choose(id: string) { if (props.detail.sessions.some(item => item.id === id)) select(id) }
function handleFailure(reason: unknown) { failure(reason); emit('failure', reason) }
watch(() => props.autoSync, value => { autoSync.value = value }, { immediate: true })
watch(() => props.detail.sessions, sessions => { if (!sessions.some(item => item.id === selectedId.value)) select(sessions.find(item => item.id === props.initialSession)?.id || sessions[0]?.id || '') }, { immediate: true })
watch(denied, value => { if (value) emit('failure', new IdentityError(403, '会话查看权限已失效')) })
</script>
