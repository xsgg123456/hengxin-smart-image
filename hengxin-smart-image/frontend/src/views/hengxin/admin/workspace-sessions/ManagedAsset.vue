<template>
  <div class="wm-managed-asset">
    <ElImage v-if="isImage" :src="thumbnail" :alt="asset.name" fit="contain" tabindex="0" role="button" :aria-label="`预览 ${asset.name}`" @click="preview" @keydown.enter.prevent="preview">
      <template #placeholder><span class="image-state">加载中…</span></template>
      <template #error><button class="image-state" @click.stop="preview">图片暂不可用 · 点击重试</button></template>
    </ElImage>
    <span v-else class="studio-doc-icon">文件</span>
    <div><strong>{{ asset.name }}</strong><small v-if="'sizeBytes' in asset">{{ formatAttachmentSize(asset.sizeBytes) }}</small>
      <ElButton v-if="isImage" text type="primary" :loading="busy" @click="preview">预览</ElButton><ElButton text type="primary" :loading="busy" @click="download">下载</ElButton>
      <small v-if="error" role="alert" class="wm-error">{{ error }}</small>
    </div>
    <ElImageViewer v-if="visible && original" :url-list="[original]" teleported @close="visible = false" />
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { Asset, StudioPicture } from '@/api/shared/studio'
import type { StudioOutput } from '@/api/shared/studio-outputs'
import { readManagedAsset } from '@/api/hengxin/workspace-sessions'
import { formatAttachmentSize } from '@/utils/attachment-size'
const props = defineProps<{ asset: Asset | StudioPicture | StudioOutput }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const thumbnail = ref(''), original = ref(''), visible = ref(false), busy = ref(false), error = ref('')
const controller = new AbortController(), urls = new Set<string>()
const isImage = computed(() => 'width' in props.asset || ('contentType' in props.asset && ['image/jpeg', 'image/png', 'image/webp'].includes(props.asset.contentType)))
function blobUrl(blob: Blob) { const url = URL.createObjectURL(blob); urls.add(url); return url }
function failed(reason: unknown) { if (!controller.signal.aborted) { error.value = reason instanceof Error ? reason.message : '文件加载失败'; emit('failure', reason) } }
async function loadOriginal() {
  const blob = await readManagedAsset(props.asset.url, controller.signal)
  controller.signal.throwIfAborted()
  if (original.value) { URL.revokeObjectURL(original.value); urls.delete(original.value) }
  original.value = blobUrl(blob)
  return original.value
}
async function preview() {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { await loadOriginal(); visible.value = true } catch (reason) { failed(reason) } finally { busy.value = false }
}
async function download() {
  if (busy.value) return
  busy.value = true; error.value = ''
  try {
    const url = await loadOriginal(), link = document.createElement('a')
    link.href = url; link.download = props.asset.name; document.body.appendChild(link)
    try { link.click() } finally { link.remove() }
  } catch (reason) { failed(reason) } finally { busy.value = false }
}
onMounted(async () => {
  if (!isImage.value) return
  try { const blob = await readManagedAsset(props.asset.url, controller.signal, fetch, true); controller.signal.throwIfAborted(); thumbnail.value = blobUrl(blob) }
  catch (reason) { failed(reason) }
})
onUnmounted(() => { controller.abort(); for (const url of urls) URL.revokeObjectURL(url); urls.clear() })
</script>
