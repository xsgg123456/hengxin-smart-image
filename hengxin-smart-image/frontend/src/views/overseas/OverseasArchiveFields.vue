<template>
  <dl class="archive-fields" :class="{ compact }">
    <div class="product-name"><dt>品名</dt><dd>{{ archive.productName }}</dd></div>
    <div><dt>品牌</dt><dd>{{ archive.brand }}</dd></div>
    <div><dt>平台</dt><dd>{{ archive.platform }}</dd></div>
    <div><dt>SKU</dt><dd>{{ archive.skus.map(sku => sku.code).join(' · ') }}</dd></div>
  </dl>
</template>
<script setup lang="ts">
import type { Archive } from '@/api/overseas/archives'
defineProps<{ archive: Archive; compact?: boolean }>()
</script>
<style scoped>
.archive-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 24px; margin: 16px 0; font-size: 14px; }
.archive-fields > div { display: flex; gap: 16px; min-width: 0; line-height: 1.6; }
.archive-fields dt { width: 42px; flex-shrink: 0; color: var(--art-text-gray-600); }
.archive-fields dd { margin: 0; overflow-wrap: anywhere; color: var(--art-text-gray-900); }
.product-name { grid-column: 1 / -1; }
.product-name dd { font-weight: 600; }
.compact { grid-template-columns: 1fr; gap: 7px; margin: 10px 0; }
@media (max-width: 600px) { .archive-fields { grid-template-columns: 1fr; } }
</style>
