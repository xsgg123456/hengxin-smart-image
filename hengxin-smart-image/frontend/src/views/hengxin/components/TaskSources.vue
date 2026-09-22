<template>
  <ElCard class="hx-gap hx-task-sources" shadow="never">
    <template #header><strong>原提交素材 · {{ sources.length }} 张</strong></template>
    <p class="hx-footnote">本次提交的替换素材，返工继续使用；点击缩略图查看原图。</p>
    <ElEmpty v-if="!sources.length" description="此任务未保留提交素材" :image-size="40" />
    <div v-else class="hx-source-grid" role="region" aria-label="原提交素材列表" tabindex="0">
      <figure v-for="(source, index) in sources" :key="`${source.fileId ?? index}-${source.url}`" class="hx-source-item">
        <PicturePreview :picture="source" :pictures="sources" :index="index" title="原提交素材" />
        <figcaption :title="source.name">{{ source.name }}</figcaption>
      </figure>
    </div>
  </ElCard>
</template>
<script setup lang="ts">
import PicturePreview from './PicturePreview.vue'
import type { Picture } from '@/types/hengxin'
defineProps<{ sources: readonly Picture[] }>()
</script>
<style scoped>
.hx-task-sources { min-width: 0; }
.hx-task-sources .hx-footnote { margin: 0 0 10px; }
.hx-source-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(112px, 100%), 1fr)); gap: 12px; max-height: 240px; overflow: auto; }
.hx-source-item { min-width: 0; margin: 0; }
.hx-source-item .el-image { display: block; width: 100%; height: 80px; border-radius: 7px; background: var(--art-gray-100); }
.hx-source-placeholder { display: flex; align-items: center; justify-content: center; height: 100%; color: var(--art-gray-600); font-size: 12px; }
.hx-source-item figcaption { margin-top: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
</style>
