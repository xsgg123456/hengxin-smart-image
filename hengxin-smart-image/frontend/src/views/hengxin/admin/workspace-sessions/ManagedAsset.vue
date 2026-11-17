<template>
  <div class="wm-managed-asset" :class="result && image ? 'studio-picture' : ['studio-image-file', { 'is-image': image }]" :title="asset.name">
    <StudioAssetImage v-if="image" ref="preview" :asset="asset" :group="group" :title="title" :access="managedImageAccess" @failure="$emit('failure', $event)" />
    <span v-else class="studio-doc-icon">文件</span>
    <div class="studio-image-file-meta"><span :title="asset.name">{{ asset.name }}</span></div>
    <div v-if="result || !image" class="wm-asset-actions">
      <ElButton v-if="image" text type="primary" @click="preview?.open()">预览</ElButton>
      <ElButton text type="primary" :loading="busy" @click="download">下载</ElButton>
      <small v-if="'sizeBytes' in asset">{{ formatAttachmentSize(asset.sizeBytes) }}</small>
      <small v-if="error" role="alert" class="wm-error">{{ error }}</small>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import StudioAssetImage from '@/views/shared/studio/StudioAssetImage.vue'
import { isImage, type StudioImage } from '@/views/shared/studio/studio-images'
import { downloadManagedAsset, managedImageAccess } from './managed-image-access'
import { formatAttachmentSize } from '@/utils/attachment-size'
const props = defineProps<{ asset: StudioImage; group: StudioImage[]; title: string; result?: boolean }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const preview = ref<InstanceType<typeof StudioAssetImage>>(), busy = ref(false), error = ref('')
const controller = new AbortController(), image = computed(() => isImage(props.asset))
async function download() {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { await downloadManagedAsset(props.asset, controller.signal) }
  catch (reason) { if (!controller.signal.aborted) { error.value = reason instanceof Error ? reason.message : '下载失败，请重试'; emit('failure', reason) } }
  finally { busy.value = false }
}
onUnmounted(() => controller.abort())
</script>
