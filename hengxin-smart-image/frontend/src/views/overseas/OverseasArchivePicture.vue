<template>
  <ElCard class="art-card" shadow="never">
    <ElImage v-if="url" :src="url" :alt="picture.name" fit="contain" class="archive-picture" role="button" tabindex="0" :aria-label="`预览 ${picture.name}`" @click="$emit('preview')" @keydown.enter.stop.prevent="$emit('preview')" @keydown.space.stop.prevent="$emit('preview')" @error="imageError"><template #error><span>图片无法显示，请下载原图查看</span></template></ElImage>
    <p v-else-if="loading" role="status">正在加载图片…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <ElButton v-if="error" text type="primary" :loading="loading" @click="load">重新加载图片</ElButton>
    <p>{{ picture.name }}</p><p class="hx-footnote">{{ picture.sku }} · {{ picture.width }} × {{ picture.height }}</p>
    <ElButton text type="primary" :disabled="!blob" @click="download">下载图片</ElButton>
  </ElCard>
</template>
<script setup lang="ts">
import type { ArchivePicture, ArchivesApi } from '@/api/overseas/archives'
import { saveBlob } from '@/api/overseas/pictures'
import { useArchiveImage } from './use-archive-image'
const props = defineProps<{ archiveId: string; picture: ArchivePicture; api: ArchivesApi }>()
const emit = defineEmits<{ failure: [reason: unknown]; preview: [] }>()
const { blob, url, error, loading, load, imageError } = useArchiveImage(props.api, () => props.archiveId, () => props.picture, reason => emit('failure', reason))
function download() { if (blob.value) saveBlob(blob.value, props.picture.name) }
</script>
<style scoped>
.archive-picture { height: 210px; width: 100%; cursor: zoom-in; }
p { white-space: normal; overflow-wrap: anywhere; }
</style>
