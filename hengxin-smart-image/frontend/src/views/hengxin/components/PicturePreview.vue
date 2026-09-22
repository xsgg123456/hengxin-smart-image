<template>
  <ElImage ref="image" :key="`${picture.url}-${attempt}`" :src="picture.url" :alt="picture.name"
    fit="contain" :preview-src-list="group.map(p => p.url)" :initial-index="index"
    :infinite="false" show-progress preview-teleported class="hx-picture"
    tabindex="0" role="button" :aria-label="`放大查看 ${picture.name}`" @keydown.enter.prevent="image?.showPreview()" @keydown.space.prevent="image?.showPreview()">
    <template #placeholder><span class="hx-picture-state" role="status">图片加载中…</span></template>
    <template #error><span class="hx-picture-state">图片加载失败<ElButton text type="primary" @click.stop="attempt++">重新加载</ElButton></span></template>
    <template #progress="{ activeIndex, total }"><div class="hx-viewer-caption">{{ title || '图片预览' }} · {{ activeIndex + 1 }} / {{ total }}<br />{{ group[activeIndex]?.name }}<small>← → 切换图片 · 滚轮缩放 · Esc 关闭</small></div></template>
  </ElImage>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ImageInstance } from 'element-plus'
import type { Picture } from '@/types/hengxin'
const props = defineProps<{ picture: Picture; pictures?: readonly Picture[]; index?: number; title?: string }>()
const group = computed(() => props.pictures?.length ? props.pictures : [props.picture])
const index = computed(() => Math.max(0, Math.min(props.index ?? 0, group.value.length - 1)))
const attempt = ref(0), image = ref<ImageInstance>()
</script>
<style scoped>
.hx-picture { display:block; width:100%; height:100%; background:var(--art-gray-100); border-radius:8px; cursor:zoom-in; }
.hx-picture:has(:focus-visible) { outline:3px solid var(--el-color-primary); outline-offset:2px; }
.hx-picture-state { display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; color:var(--art-gray-600); font-size:12px; }
.hx-viewer-caption { color:white; text-align:center; font-size:14px; line-height:1.6; overflow-wrap:anywhere; max-width:70vw; }
.hx-viewer-caption small { display:block; color:#d5d9e2; font-size:12px; }
</style>
