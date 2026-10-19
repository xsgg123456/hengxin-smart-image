<template>
  <ElDialog :model-value="open" title="归档所选图片" width="min(600px, 94vw)" append-to-body @close="$emit('close')">
    <p>将所选 <strong>{{ pictures.length }}</strong> 张图片归入以下产品；归档后仍可继续对话。</p>
    <ArchiveFields hide-sku />
    <label class="sku-label" for="archive-sku">SKU</label>
    <ElSelect id="archive-sku" v-model="sku" aria-label="选择所属 SKU" placeholder="选择所属 SKU" style="width:100%">
      <ElOption :label="product.sku" :value="product.sku" />
    </ElSelect>
    <div class="confirm-pictures"><AssetImage v-for="picture in pictures" :key="picture.id" :asset="picture" :group="pictures" title="待归档图片" /></div>
    <div class="confirm-audit"><span>归档人</span><strong>{{ previewActor }}</strong><ElTag size="small" type="info">当前登录用户 · 示例</ElTag></div>
    <p class="hx-footnote">归档时间在确认时自动记录。此预览仅模拟保存，刷新页面后重置。</p>
    <template #footer><ElButton @click="$emit('close')">取消</ElButton><ElButton type="primary" :disabled="!sku || !pictures.length" @click="$emit('confirm')">确认归档</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue'
import ArchiveFields from './ArchiveFields.vue'
import AssetImage from '../preview-studio-images/AssetImage.vue'
import { product, previewActor } from './archive-state'
import type { Asset } from '../preview-studio-images/state'
const props = defineProps<{ open: boolean; pictures: Asset[] }>()
defineEmits<{ close: []; confirm: [] }>()
const sku = ref('')
watch(() => props.open, value => { if (value) sku.value = '' })
</script>
<style scoped>
.sku-label { display: block; margin: 0 0 8px; color: #7b8aab; }
.confirm-pictures { display: flex; gap: 10px; flex-wrap: wrap; margin: 18px 0; }
.confirm-pictures :deep(.el-image) { width: 72px; height: 72px; border: 1px solid #dce3ef; border-radius: 6px; }
.confirm-audit { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin: 18px 0 10px; }
.confirm-audit > span:first-child { color: #7b8aab; }
</style>
