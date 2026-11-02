<template>
  <ElButton size="small" :disabled="!pictures.length" :loading="downloading" @click="download">下载所选图片（{{ pictures.length }}）</ElButton>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import type { StudioPicture } from '@/api/overseas/studio'
import { prepareStudioDownload } from '@/api/overseas/studio-download'
import { saveBlob } from '@/api/overseas/pictures'
const props = defineProps<{ pictures: StudioPicture[] }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const downloading = ref(false)
const controller = new AbortController()
onBeforeUnmount(() => controller.abort())
async function download() {
  if (downloading.value || !props.pictures.length) return
  downloading.value = true
  try {
    const blob = await prepareStudioDownload([...props.pictures], controller.signal)
    if (!controller.signal.aborted) saveBlob(blob, '工作台图片.zip')
  } catch (reason) { if (!controller.signal.aborted) emit('failure', reason) }
  finally { downloading.value = false }
}
</script>
