<template>
  <div class="hx-picture-set">
    <div class="hx-picture-mosaic"><div v-for="(picture, index) in pictures.slice(0, 4)" :key="index" class="hx-picture-cell"><PicturePreview :picture="picture" :pictures="pictures" :index="index" :title="title" /><span v-if="index === 3 && pictures.length > 4" class="hx-picture-more" role="status">+{{ pictures.length - 4 }}</span></div></div>
    <div class="hx-picture-count">{{ pictures.length }} 张图片 <span>点击缩略图放大 · 可左右查看全部</span></div>
  </div>
</template>
<script setup lang="ts">
import type { Picture } from '@/types/hengxin'
import PicturePreview from './PicturePreview.vue'
defineProps<{ pictures: readonly Picture[]; title?: string }>()
</script>
<style scoped>
.hx-picture-set { min-width:0; background:var(--art-gray-100); padding:10px; }
.hx-picture-mosaic { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; }
.hx-picture-cell { position:relative; min-width:0; aspect-ratio:1; }
.hx-picture-cell>.hx-picture { aspect-ratio:1; height:auto; min-width:0; }
.hx-picture-more { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; border-radius:8px; background:rgba(20, 28, 42, .58); color:#fff; font-size:20px; font-weight:600; pointer-events:none; }
.hx-picture-count { display:flex; justify-content:space-between; flex-wrap:wrap; gap:4px; font-size:12px; line-height:1.6; padding-top:8px; color:var(--art-gray-700); }
.hx-picture-count span { color:var(--art-gray-600); font-size:11px; }
</style>
