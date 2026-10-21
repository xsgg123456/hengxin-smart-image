<template>
  <ElDrawer :model-value="!!row" title="清理详情" size="min(560px, 100vw)" @close="$emit('close')">
    <template v-if="row">
      <div class="hx-drawer-intro"><span class="hx-admin-kicker">CLEANUP RECEIPT</span><strong>{{ row.task }}</strong><p>第 {{ row.image }} 张图片 · {{ row.id }} · 模拟记录</p></div>
      <ElTag :type="tagType(row.result)">{{ row.result }}</ElTag>
      <p class="hx-muted hx-gap">{{ row.detail }}</p>
      <ElDescriptions :column="1" border class="hx-gap">
        <ElDescriptionsItem label="清理类型">{{ row.kind }}</ElDescriptionsItem>
        <ElDescriptionsItem label="最后有效活动">{{ row.activity }}</ElDescriptionsItem>
        <ElDescriptionsItem label="到期时间">{{ row.due }}</ElDescriptionsItem>
        <ElDescriptionsItem label="本次处理时间">{{ row.time }}</ElDescriptionsItem>
        <ElDescriptionsItem label="已清理对话">{{ row.turns }} 轮</ElDescriptionsItem>
        <ElDescriptionsItem label="已回收候选文件">{{ row.files }} 个</ElDescriptionsItem>
        <ElDescriptionsItem label="原任务">{{ row.deleted ? '任务已删除，清理摘要保留' : '任务仍保留' }}</ElDescriptionsItem>
      </ElDescriptions>
      <h3 class="hx-gap">仍然保留</h3><p class="hx-muted">正式成品、已采用版本、归档、原图、素材，以及调用量和 Token 汇总。</p>
      <ElAlert v-if="row.kind === '会话历史' && ['全部完成','文件回收中'].includes(row.result)" title="旧会话历史不能恢复；后续修改可基于正式图片明确开启新会话。" type="info" :closable="false" />
      <p class="hx-footnote">时间均为北京时间。这里只保留清理摘要，不保存已删除的聊天或提示词正文。</p>
    </template>
  </ElDrawer>
</template>
<script setup lang="ts">
import { ElDrawer, ElTag, ElDescriptions, ElDescriptionsItem, ElAlert } from 'element-plus'
import { tagType, type CleanupRow } from './retention-data'
defineProps<{row: CleanupRow | null}>()
defineEmits<{close: []}>()
</script>
