<template>
  <ElDrawer :model-value="open" title="清理详情" size="min(560px, 100vw)" @close="$emit('close')">
    <ElSkeleton v-if="loading" :rows="8" animated />
    <ElAlert v-else-if="error" :title="error" type="error" :closable="false" show-icon />
    <template v-else-if="row">
      <div class="hx-drawer-intro"><span class="hx-admin-kicker">CLEANUP RECEIPT</span><strong>{{ row.taskName }}</strong><p>第 {{ row.imagePosition }} 张图片 · {{ row.resourceId }}</p></div>
      <ElTag :type="tagType(row.result)">{{ resultLabels[row.result] }}</ElTag>
      <p class="hx-muted hx-gap">{{ row.detail }}</p>
      <ElDescriptions :column="1" border class="hx-gap">
        <ElDescriptionsItem label="清理类型">{{ kindLabels[row.kind] }}</ElDescriptionsItem>
        <ElDescriptionsItem label="最后有效活动">{{ time(row.lastActivityAt) }}</ElDescriptionsItem>
        <ElDescriptionsItem label="到期时间">{{ time(row.dueAt) }}</ElDescriptionsItem>
        <ElDescriptionsItem label="本次处理时间">{{ time(row.processedAt, '尚未处理') }}</ElDescriptionsItem>
        <ElDescriptionsItem label="下次尝试">{{ time(row.nextAttemptAt, '暂无计划') }}</ElDescriptionsItem>
        <ElDescriptionsItem label="已清理对话">{{ row.turnsRemoved }} 轮</ElDescriptionsItem>
        <ElDescriptionsItem label="已回收候选文件">{{ row.objectsRemoved }} 个</ElDescriptionsItem>
        <ElDescriptionsItem label="待回收文件">{{ row.objectsPending }} 个</ElDescriptionsItem>
        <ElDescriptionsItem label="原任务">{{ row.taskDeleted ? '任务已删除，清理摘要保留' : '任务仍保留' }}</ElDescriptionsItem>
      </ElDescriptions>
      <h3 class="hx-gap">仍然保留</h3><p class="hx-muted">正式成品、全部已采用版本、归档、原图、素材，以及调用量和 Token 汇总。</p>
      <ElAlert v-if="row.kind === 'history' && ['complete','objects_pending'].includes(row.result)" title="旧会话历史不能恢复；后续修改可基于正式图片明确开启新会话。" type="info" :closable="false" />
      <p class="hx-footnote">时间均为北京时间。这里只保留清理摘要，不保存已删除的聊天或提示词正文。</p>
    </template>
  </ElDrawer>
</template>
<script setup lang="ts">
import { ElDrawer, ElTag, ElDescriptions, ElDescriptionsItem, ElAlert, ElSkeleton } from 'element-plus'
import { formatBeijingTime as time } from '@/utils/beijing-time'
import { tagType, resultLabels, kindLabels } from './retention-presenter'
import type { RetentionRow } from '@/types/retention'
defineProps<{ row?: RetentionRow; open: boolean; loading: boolean; error: string }>()
defineEmits<{ close: [] }>()
</script>
