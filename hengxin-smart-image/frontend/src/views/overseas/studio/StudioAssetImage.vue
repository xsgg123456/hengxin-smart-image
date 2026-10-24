<template>
  <ElImage ref="image" :src="imageUrl(asset)" :alt="asset.name" fit="contain" :preview-src-list="images.map(imageUrl)" :initial-index="index" :infinite="false" show-progress preview-teleported :z-index="6000" tabindex="0" role="button" :aria-label="`预览 ${asset.name}`" @keydown.enter.stop.prevent="image?.showPreview()" @keydown.space.stop.prevent="image?.showPreview()" @error="verify(index)" @show="verify(index)" @switch="verify">
    <template #placeholder><span class="image-state">加载中…</span></template>
    <template #error><span class="image-state">图片无法预览<br><button type="button" :disabled="downloading" @click.stop="download(index)">下载原文件</button><small v-if="downloadError" role="alert">{{ downloadError }}</small></span></template>
    <template #viewer-error><span class="image-state">图片无法预览，可下载原文件</span></template>
    <template #progress="{ activeIndex, total }"><div class="image-caption">{{ title }} · {{ activeIndex + 1 }} / {{ total }}<br>{{ images[activeIndex]?.name }} <button type="button" @click.stop="download(activeIndex)">下载原图</button><small>{{ downloadError || '← → 切换图片 · 滚轮缩放 · Esc 关闭' }}</small></div></template>
  </ElImage>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import type { ImageInstance } from 'element-plus'
import { checkImage, imageUrl, isImage, type StudioImage } from './studio-images'
import { downloadAttachment } from '@/api/overseas/attachment-download'
const props = defineProps<{ asset: StudioImage; group: StudioImage[]; title: string }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const image = ref<ImageInstance>(), downloadError = ref(''), downloading = ref(false), controller = new AbortController()
const images = computed(() => props.group.filter(isImage))
const index = computed(() => Math.max(0, images.value.findIndex(a => a.id === props.asset.id)))
async function verify(index: number) {
  const asset = images.value[index]; if (!asset) return false
  try { await checkImage(asset, AbortSignal.any([controller.signal, AbortSignal.timeout(10000)])); downloadError.value = ''; return true }
  catch (reason) { if (!controller.signal.aborted) { downloadError.value = reason instanceof Error ? reason.message : '图片无法读取'; emit('failure', reason) }; return false }
}
async function download(index: number) {
  if (downloading.value) return
  const asset = images.value[index]; if (!asset) return
  downloading.value = true; downloadError.value = ''
  try { await downloadAttachment(asset.url, asset.name, controller.signal) }
  catch (reason) { if (!controller.signal.aborted) { downloadError.value = reason instanceof Error ? reason.message : '下载失败，请重试'; emit('failure', reason) } }
  finally { downloading.value = false }
}
onUnmounted(() => controller.abort())
</script>
