<template>
  <dl class="studio-archive-fields">
    <div class="product-name"><dt>品名</dt><dd>{{ task.productName }}</dd></div>
    <div><dt>品牌</dt><dd>{{ task.brand }}</dd></div>
    <div><dt>平台</dt><dd>{{ task.platform }}</dd></div>
  </dl>
</template>
<script setup lang="ts">
import type { TaskDetail } from '@/api/overseas/tasks'
defineProps<{ task: Pick<TaskDetail, 'productName' | 'brand' | 'platform'> }>()
</script>
<style scoped>
.studio-archive-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 24px; margin: 16px 0; font-size: 14px; }
.studio-archive-fields > div { display: flex; gap: 16px; min-width: 0; line-height: 1.6; }
.studio-archive-fields dt { width: 42px; flex-shrink: 0; color: var(--art-text-gray-600); }
.studio-archive-fields dd { margin: 0; overflow-wrap: anywhere; color: var(--art-text-gray-900); }
.product-name { grid-column: 1 / -1; }
.product-name dd { font-weight: 600; }
@media (max-width: 600px) { .studio-archive-fields { grid-template-columns: 1fr; } }
</style>
