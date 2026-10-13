<template>
  <ElCard class="art-card" shadow="never">
    <ElImage v-if="url" :src="url" :alt="picture.name" :preview-src-list="[url]" preview-teleported fit="contain" class="archive-picture" @error="imageError = true"><template #error><span>图片无法显示，请下载原图查看</span></template></ElImage>
    <p v-else-if="loading" role="status">正在加载图片…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <ElButton v-if="error || imageError" text type="primary" :loading="loading" @click="load">重新加载图片</ElButton>
    <p>{{ picture.name }}</p><p class="hx-footnote">{{ picture.sku }} · {{ picture.width }} × {{ picture.height }}</p>
    <ElButton text type="primary" :disabled="!blob" @click="download">下载图片</ElButton>
  </ElCard>
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { IdentityError } from '@/api/identity/request'
import type { ArchivePicture, ArchivesApi } from '@/api/overseas/archives'
import { saveBlob } from '@/api/overseas/pictures'
import { archiveError } from '@/api/overseas/archives'
const props = defineProps<{ archiveId: string; picture: ArchivePicture; api: ArchivesApi }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const blob = ref<Blob>(), url = ref(''), error = ref(''), loading = ref(false), imageError = ref(false)
let active = true, controller: AbortController | undefined
function release() { if (url.value) URL.revokeObjectURL(url.value); url.value = ''; blob.value = undefined }
async function load() {
  if (loading.value) return
  controller = new AbortController(); loading.value = true; error.value = ''; imageError.value = false; release()
  try {
    const value = await props.api.content(props.archiveId, props.picture.id, controller.signal)
    if (!active) return
    if (value.type !== props.picture.contentType || value.size !== props.picture.sizeBytes) throw Error('图片文件与归档记录不一致，请刷新后重试')
    blob.value = value; url.value = URL.createObjectURL(value)
  } catch (reason) { if (active) { error.value = archiveError(reason); if (reason instanceof IdentityError && [401, 403].includes(reason.status)) emit('failure', reason) } }
  finally { if (active) loading.value = false }
}
function download() { if (blob.value) saveBlob(blob.value, props.picture.name) }
onMounted(load)
onUnmounted(() => { active = false; controller?.abort(); release() })
</script>
<style scoped>
.archive-picture { height: 210px; width: 100%; }
p { white-space: normal; overflow-wrap: anywhere; }
</style>
