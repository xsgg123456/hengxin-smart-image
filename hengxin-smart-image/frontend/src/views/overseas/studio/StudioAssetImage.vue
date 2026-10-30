<template>
  <ElImage :key="thumbnailKey" :src="thumbnailUrl(asset)" :alt="asset.name" fit="contain" tabindex="0" role="button" :aria-label="`预览 ${asset.name}`" @click="open(index)" @keydown.enter.stop.prevent="open(index)" @keydown.space.stop.prevent="open(index)" @error="verifyThumbnail">
    <template #placeholder><span class="image-state">加载中…</span></template>
    <template #error><span class="image-state">缩略图暂不可用<br>点击查看原图<br><button type="button" :disabled="downloading" @click.stop="download(index)">下载原文件</button><small v-if="downloadError" role="alert">{{ downloadError }}</small></span></template>
  </ElImage>
  <ElImageViewer v-if="visible" :key="viewerKey" :url-list="urlList" :initial-index="current" :infinite="false" show-progress teleported :z-index="6000" @close="close" @switch="select" @error="imageError">
    <template #viewer-error><span class="image-state">图片无法预览，可下载原文件</span></template>
    <template #progress="{ activeIndex, total }"><div class="image-caption">{{ title }} · {{ activeIndex + 1 }} / {{ total }}<br>{{ images[activeIndex]?.name }} <button type="button" @click.stop="download(activeIndex)">下载原图</button><small>{{ downloadError || '← → 切换图片 · 滚轮缩放 · Esc 关闭' }}</small></div></template>
    <div v-if="error" class="image-cache-error" role="alert">{{ error }} <button type="button" @click.stop="retry">重新加载</button></div>
  </ElImageViewer>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { checkImage, imageUrl, thumbnailUrl, isImage, type StudioImage } from './studio-images'
import { useImageViewer } from './use-image-viewer'
import { downloadAttachment } from '@/api/overseas/attachment-download'
import { IdentityError } from '@/api/identity/request'
import { overseasImageCache } from '@/api/overseas/image-cache'
const props = defineProps<{ asset: StudioImage; group: StudioImage[]; title: string }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const downloadError = ref(''), downloading = ref(false), controller = new AbortController()
const images = computed(() => props.group.filter(isImage))
const index = computed(() => Math.max(0, images.value.findIndex(a => a.id === props.asset.id)))
const { visible, current, viewerKey, urlList, error, open, close, select, imageError, retry } = useImageViewer(images, reason => emit('failure', reason))
const thumbnailKey = ref(0)
let thumbnailAttempts = 0, thumbnailTimer: ReturnType<typeof setTimeout> | undefined, thumbnailEpoch = 0
watch(() => thumbnailUrl(props.asset), () => { ++thumbnailEpoch; thumbnailAttempts = 0; clearTimeout(thumbnailTimer); thumbnailTimer = undefined })
async function verifyThumbnail() {
  const epoch = thumbnailEpoch
  try { await checkImage(props.asset, AbortSignal.any([controller.signal, AbortSignal.timeout(10000)])) }
  catch (reason) {
    if (controller.signal.aborted || epoch !== thumbnailEpoch) return
    if (reason instanceof IdentityError && [401, 403, 404].includes(reason.status)) { emit('failure', reason); return }
  }
  if (controller.signal.aborted || epoch !== thumbnailEpoch || thumbnailAttempts >= 4 || thumbnailTimer) return
  // Small image workers can be busy on the first batch. Retry the same URL with a bounded stagger.
  thumbnailTimer = setTimeout(() => { thumbnailTimer = undefined; thumbnailKey.value++ }, 300 + (index.value % 8) * 80 + thumbnailAttempts++ * 450)
}
async function download(index: number) {
  if (downloading.value) return
  const asset = images.value[index]; if (!asset) return
  downloading.value = true; downloadError.value = ''
  try { await downloadAttachment(asset.url, asset.name, controller.signal) }
  catch (reason) { if (!controller.signal.aborted) {
    if (reason instanceof IdentityError && [401, 403, 404].includes(reason.status)) overseasImageCache.invalidate(imageUrl(asset))
    downloadError.value = reason instanceof Error ? reason.message : '下载失败，请重试'; emit('failure', reason)
  } }
  finally { downloading.value = false }
}
onUnmounted(() => { controller.abort(); clearTimeout(thumbnailTimer) })
</script>
<style scoped>
.image-cache-error { position: absolute; top: 70px; left: 50%; transform: translateX(-50%); padding: 12px; color: white; background: #333; border-radius: 4px; }
</style>
