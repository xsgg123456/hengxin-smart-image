<template>
  <ElDrawer :model-value="open" title="会话清理与数据保留" size="min(520px, 100vw)" @close="$emit('close')">
    <ElAlert v-if="stale" title="策略快照已过期，请刷新后核对当前生效配置。" type="warning" :closable="false" />
    <ElDescriptions v-if="policy" :column="1" border>
      <ElDescriptionsItem label="策略开关">{{ policy.enabled ? '已启用' : '未启用' }}</ElDescriptionsItem>
      <ElDescriptionsItem :label="`${policy.cacheIdleHours} 小时`">清理会话私有缓存与插件，保留聊天历史。</ElDescriptionsItem>
      <ElDescriptionsItem :label="`${policy.historyIdleHours} 小时`">清理会话执行目录、聊天、事件、提示词及无引用候选图与标注。</ElDescriptionsItem>
      <ElDescriptionsItem label="扫描间隔">{{ policy.scanIntervalSeconds }} 秒</ElDescriptionsItem>
      <ElDescriptionsItem label="单轮上限">{{ policy.batchSize }} 个会话及 {{ policy.batchSize }} 个对象回执</ElDescriptionsItem>
      <ElDescriptionsItem label="明细保留">{{ policy.detailRetentionDays }} 天；未完成记录继续保留，累计统计长期保存。</ElDescriptionsItem>
      <ElDescriptionsItem label="有效活动">提交、回复、重试、采用和执行结束会重新计时。</ElDescriptionsItem>
      <ElDescriptionsItem label="只读访问">查看、刷新和轮询不续期。</ElDescriptionsItem>
      <ElDescriptionsItem label="持续保留">正式成品、全部已采用版本、归档、原图、素材及用量汇总。</ElDescriptionsItem>
      <ElDescriptionsItem label="旧会话">已闲置超过 3 天的在下一轮开始清理，不额外给宽限。</ElDescriptionsItem>
    </ElDescriptions>
    <ElEmpty v-else description="尚未读取到实际策略，请刷新状态后重试" />
    <p class="hx-muted hx-gap">活动中的会话受保护；失败保留状态并自动重试。超过单轮上限的清理对象分批处理。</p>
  </ElDrawer>
</template>
<script setup lang="ts">
import { ElAlert, ElDescriptions, ElDescriptionsItem, ElDrawer, ElEmpty } from 'element-plus'
import type { RetentionSummary } from '@/types/retention'
defineProps<{ open: boolean; policy?: RetentionSummary['policy']; stale: boolean }>()
defineEmits<{ close: [] }>()
</script>
