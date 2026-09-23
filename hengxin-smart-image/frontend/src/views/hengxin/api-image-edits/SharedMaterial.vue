<template>
  <ElCard class="art-card hx-gap" shadow="never">
    <div class="material-reference">
      <PicturePreview v-if="picture?.url" :picture="picture" title="本次共用素材" />
      <div><strong>本次共用素材</strong><p>{{ picture?.name || '素材未记录' }}</p>
        <p class="hx-footnote">{{ picture?.url ? '用于这套图片的共同参考 · 点击图片放大查看' : '历史记录中没有可查看的共用素材' }}</p></div>
    </div>
  </ElCard>
</template>
<script setup lang="ts">
import type { Picture } from '@/types/hengxin'
import PicturePreview from '../components/PicturePreview.vue'
defineProps<{ picture?: Picture | null }>()
</script>
<style scoped>
.material-reference { display:flex; align-items:center; gap:16px; }
.material-reference > .hx-picture { width:72px; height:72px; flex:none; }
.material-reference > div { min-width:0; overflow-wrap:anywhere; }
.material-reference p { margin-top:6px; }
</style>
