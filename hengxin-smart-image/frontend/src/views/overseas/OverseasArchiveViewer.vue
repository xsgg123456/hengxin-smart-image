<template>
  <ElImageViewer :url-list="urls" :initial-index="initialIndex" :infinite="false" show-progress teleported :z-index="6000" @close="$emit('close')" @switch="activeIndex = $event" @error="url && imageError()">
    <template #progress><div class="image-caption">归档成品 · {{ activeIndex + 1 }} / {{ pictures.length || '…' }}<br>{{ pictures[activeIndex]?.name }}<small>← → 切换图片 · 滚轮缩放 · Esc 关闭</small></div></template>
    <div v-if="loading || metadataLoading || error || metadataError" class="archive-viewer-state" role="status">
      <span>{{ error || metadataError || '正在加载原图…' }}</span>
      <ElButton v-if="error || metadataError" type="primary" @click="metadataError ? loadMetadata() : load()">重新加载图片</ElButton>
    </div>
  </ElImageViewer>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { ElImageViewer } from 'element-plus'
import { IdentityError } from '@/api/identity/request'
import { archiveError, type ArchivePicture, type ArchivesApi } from '@/api/overseas/archives'
import { useArchiveImage } from './use-archive-image'
const props = defineProps<{ archiveId: string; api: ArchivesApi; initialIndex: number; group?: ArchivePicture[] }>()
const emit = defineEmits<{ close: []; failure: [reason: unknown] }>()
const pictures = ref<ArchivePicture[]>(props.group || []), activeIndex = ref(props.initialIndex), metadataLoading = ref(false), metadataError = ref('')
let alive = true
const { url, error, loading, load, imageError } = useArchiveImage(props.api, () => props.archiveId, () => pictures.value[activeIndex.value], reason => emit('failure', reason))
// Only the active original is fetched; Element Plus owns navigation, transform reset and focus restoration.
const blank = 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs='
const urls = computed(() => pictures.value.length ? pictures.value.map((_, index) => index === activeIndex.value && url.value ? url.value : blank) : [blank])
async function loadMetadata() {
  metadataLoading.value = true; metadataError.value = ''
  try { const detail = await props.api.get(props.archiveId); if (alive) pictures.value = detail.pictures }
  catch (reason) { if (alive) { metadataError.value = archiveError(reason); if (reason instanceof IdentityError && [401, 403].includes(reason.status)) emit('failure', reason) } }
  finally { if (alive) metadataLoading.value = false }
}
if (!props.group) void loadMetadata()
onUnmounted(() => { alive = false; pictures.value = [] })
</script>
<style scoped>
.image-caption { color: white; text-align: center; line-height: 1.6; max-width: 75vw; overflow-wrap: anywhere; }
.image-caption small { display: block; color: #d5d9e2; font-size: 12px; }
.archive-viewer-state { position: absolute; inset: 40% 12% auto; display: flex; flex-direction: column; align-items: center; gap: 12px; color: white; text-align: center; overflow-wrap: anywhere; }
</style>
