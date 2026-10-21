<template>
  <ElCard class="art-card hx-section">
    <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">SERVICE STATUS</span><h2>清理服务</h2><p v-if="data">闲置 {{ data.policy.cacheIdleHours }} 小时清缓存 · 连续闲置 {{ data.policy.historyIdleHours / 24 }} 天清历史 · 每 {{ data.policy.scanIntervalSeconds / 60 }} 分钟扫描，单轮最多 {{ data.policy.batchSize }} 个会话</p><p v-else>正在获取实际清理策略与服务状态。</p></div><ElTag :type="!stale && state === 'online' ? 'success' : 'warning'" effect="light">{{ stale ? '快照过期 · 当前状态未知' : stateLabels[state] }}</ElTag></div>
    <ElAlert v-if="state === 'offline' && !stale" title="超过 2 分钟未收到心跳，请检查清理服务。下方为最后一次已知清理记录。" type="warning" :closable="false" show-icon class="hx-gap" />
    <ElAlert v-if="state === 'unknown' && !stale" title="尚不能确认清理服务状态；未知不表示在线或没有待清理会话。" type="warning" :closable="false" show-icon />
    <ElDescriptions :column="compact ? 1 : 3" class="hx-gap">
      <ElDescriptionsItem label="策略开关">{{ data ? data.policy.enabled ? '已启用' : '未启用' : '未知' }}</ElDescriptionsItem>
      <ElDescriptionsItem label="最近心跳">{{ time(data?.service.heartbeatAt, '未知') }}</ElDescriptionsItem>
      <ElDescriptionsItem label="本轮状态">{{ data ? scanLabels[data.service.scanState] : '未知' }}</ElDescriptionsItem>
      <ElDescriptionsItem label="最近扫描开始">{{ time(data?.service.lastStartedAt, '未知') }}</ElDescriptionsItem>
      <ElDescriptionsItem label="最近扫描结束">{{ time(data?.service.lastFinishedAt, data ? '尚无结束记录' : '未知') }}</ElDescriptionsItem>
      <ElDescriptionsItem label="下次预计扫描">{{ time(data?.service.nextScanAt, '待确认') }}</ElDescriptionsItem>
    </ElDescriptions>
    <p class="hx-footnote">查看与刷新不会续期；正在执行或状态待核实的会话暂缓清理。已超过 3 天的旧会话直接进入下一轮扫描，不再增加宽限期。</p>
  </ElCard>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { ElAlert, ElCard, ElDescriptions, ElDescriptionsItem, ElTag } from 'element-plus'
import { formatBeijingTime as time } from '@/utils/beijing-time'
import type { RetentionSummary } from '@/types/retention'
const props = defineProps<{ data?: RetentionSummary; stale: boolean; compact: boolean }>()
const state = computed(() => props.data?.service.state || 'unknown')
const stateLabels = { online: '服务在线', offline: '心跳超时', unknown: '状态未知', disabled: '策略未启用' }
const scanLabels = { running: '扫描中 · 尚未结束', completed: '扫描已结束', failed: '扫描失败', unknown: '未知' }
</script>
