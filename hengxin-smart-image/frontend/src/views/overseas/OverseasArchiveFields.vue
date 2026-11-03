<template>
  <dl class="archive-fields" :class="{ compact }">
    <template v-if="compact">
      <div class="product-name"><dt>品名</dt><dd>{{ archive.productName || '未设置' }}</dd></div>
      <div><dt>品牌</dt><dd>{{ archive.brand || '未设置' }}</dd></div>
      <div><dt>平台</dt><dd>{{ archive.platform || '未设置' }}</dd></div>
      <div><dt>SKU</dt><dd>{{ skuText }}</dd></div>
    </template>
    <template v-else>
      <div><dt>SKU</dt><dd>{{ skuText }}</dd></div>
      <div><dt>目标平台</dt><dd>{{ archive.platform || '未设置' }}</dd></div>
      <div><dt>品牌</dt><dd>{{ archive.brand || '未设置' }}</dd></div>
      <div><dt>任务名称</dt><dd>{{ archive.taskName || '未设置' }}</dd></div>
      <div><dt>品名</dt><dd>{{ archive.productName || '未设置' }}</dd></div>
      <div><dt>语言</dt><dd>{{ languageLabel(archive.language) }}</dd></div>
    </template>
  </dl>
</template>
<script setup lang="ts">
import type { Archive } from '@/api/overseas/archives'
import { computed } from 'vue'
import { languageLabel } from './languages'
const props = defineProps<{ archive: Pick<Archive, 'productName' | 'brand' | 'platform' | 'taskName' | 'language' | 'skus'>; compact?: boolean }>()
const skuText = computed(() => props.archive.skus.map(sku => sku.code).filter(Boolean).join(' · ') || '未设置')
</script>
<style scoped>
.archive-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 24px; margin: 16px 0; font-size: 14px; }
.archive-fields > div { display: flex; gap: 16px; min-width: 0; line-height: 1.6; }
.archive-fields dt { width: 56px; flex-shrink: 0; color: var(--art-text-gray-600); }
.archive-fields dd { margin: 0; overflow-wrap: anywhere; color: var(--art-text-gray-900); }
.product-name { grid-column: 1 / -1; }
.product-name dd { font-weight: 600; }
.compact { grid-template-columns: 1fr; gap: 7px; margin: 10px 0; }
.compact dt { width: 42px; }
@media (max-width: 600px) { .archive-fields { grid-template-columns: 1fr; } }
</style>
