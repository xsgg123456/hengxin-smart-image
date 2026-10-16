<template>
  <ElImage ref="image" :src="asset.url" :alt="asset.name" fit="contain" :preview-src-list="images.map(a => a.url)" :initial-index="index" :infinite="false" show-progress preview-teleported :z-index="6000" tabindex="0" role="button" :aria-label="`预览 ${asset.name}`" @keydown.enter.stop.prevent="image?.showPreview()" @keydown.space.stop.prevent="image?.showPreview()">
    <template #placeholder><span class="image-state">加载中…</span></template>
    <template #error><span class="image-state">图片无法读取</span></template>
    <template #progress="{ activeIndex, total }"><div class="image-caption">{{ title }} · {{ activeIndex + 1 }} / {{ total }}<br>{{ images[activeIndex]?.name }} <a :href="images[activeIndex]?.url" :download="images[activeIndex]?.name" @click.stop>下载原图</a><small>← → 切换图片 · 滚轮缩放 · Esc 关闭</small></div></template>
  </ElImage>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ImageInstance } from 'element-plus'
import type { Asset } from './state'
const props = defineProps<{ asset: Asset; group: Asset[]; title: string }>()
const image = ref<ImageInstance>()
const images = computed(() => props.group.filter(a => a.image))
const index = computed(() => Math.max(0, images.value.findIndex(a => a.id === props.asset.id)))
</script>
