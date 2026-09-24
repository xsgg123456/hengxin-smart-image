<template>
  <div class="material-pictures">
    <article v-for="(item, index) in items" :key="`${item.role}-${index}`" class="material-picture">
      <strong
        >{{ item.label }}<span v-if="item.version"> · V{{ item.version }}</span></strong
      >
      <div v-if="item.picture" class="material-preview">
        <PicturePreview :picture="item.picture" :title="item.label" />
      </div>
      <p v-else class="material-missing">{{ item.reason || '本轮图片记录缺失' }}</p>
      <p v-if="item.picture" class="hx-footnote">{{ item.picture.name }}</p>
      <p v-if="item.picture && item.reason" class="hx-footnote">{{ item.reason }}</p>
    </article>
  </div>
</template>
<script setup lang="ts">
import type { RoundMaterialImage } from '@/api/hengxin/round-materials'
import PicturePreview from './PicturePreview.vue'
defineProps<{ items: RoundMaterialImage[] }>()
</script>
<style scoped>
.material-pictures {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}
.material-picture {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}
.material-picture strong {
  display: block;
  margin-bottom: 10px;
  font-weight: 500;
  overflow-wrap: anywhere;
}
.material-preview {
  height: 180px;
}
.material-missing {
  min-height: 70px;
  display: flex;
  align-items: center;
  color: var(--el-text-color-secondary);
}
.hx-footnote {
  overflow-wrap: anywhere;
  margin-bottom: 0;
}
@media (max-width: 600px) {
  .material-pictures {
    grid-template-columns: 1fr;
  }
}
</style>
