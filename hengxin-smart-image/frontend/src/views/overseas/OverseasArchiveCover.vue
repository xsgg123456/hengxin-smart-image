<template>
  <div class="archive-cover">
    <button type="button" class="archive-cover-button" :aria-label="`预览 ${archive.productName}`" @click="$emit('preview')">
      <ElImage v-if="url && !error" :src="url" :alt="archive.productName" fit="contain" @error="imageError" />
      <span v-else>{{ error || metadataError ? '封面加载失败' : loading || metadataLoading ? '加载封面…' : '预览成品' }}</span>
      <span class="archive-cover-count">共 {{ archive.pictureCount }} 张</span>
    </button>
    <button v-if="error || metadataError" class="archive-cover-retry" type="button" @click="metadataError ? legacyCover() : load()">重试封面</button>
  </div>
</template>
<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { type Archive, type ArchivesApi } from '@/api/overseas/archives'
import { useArchiveImage } from './use-archive-image'
const props = defineProps<{ archive: Archive; api: ArchivesApi }>()
const emit = defineEmits<{ preview: []; failure: [reason: unknown] }>()
const picture = ref(props.archive.cover || undefined), metadataError = ref(false), metadataLoading = ref(false)
let alive = true
const { url, error, loading, load, imageError } = useArchiveImage(props.api, () => props.archive.id, () => picture.value, reason => emit('failure', reason))
// Pre-snapshot archives acquire their immutable first asset through the existing authorized detail path.
async function legacyCover() {
  metadataLoading.value = true; metadataError.value = false
  try { const detail = await props.api.get(props.archive.id); if (alive) picture.value = detail.pictures[0] }
  catch (reason) { if (alive) { metadataError.value = true; if (reason instanceof IdentityError && [401, 403].includes(reason.status)) emit('failure', reason) } }
  finally { if (alive) metadataLoading.value = false }
}
if (!picture.value) void legacyCover()
onUnmounted(() => { alive = false })
</script>
<style scoped>
.archive-cover { position: relative; flex: 0 0 120px; width: 120px; height: 120px; }
.archive-cover-button { position: relative; display: block; width: 100%; height: 100%; padding: 0; cursor: zoom-in; color: var(--art-gray-600); background: var(--art-gray-100); border: 1px solid var(--default-border); border-radius: 6px; overflow: hidden; }
.archive-cover-button .el-image { width: 100%; height: 100%; }
.archive-cover-count { position: absolute; bottom: 4px; right: 4px; background: #0009; color: white; border-radius: 4px; padding: 1px 6px; font-size: 11px; pointer-events: none; }
.archive-cover-retry { position: absolute; top: 4px; left: 4px; color: var(--el-color-primary); background: var(--el-bg-color); border: 1px solid var(--default-border); border-radius: 4px; cursor: pointer; }
@media (max-width: 600px) { .archive-cover { flex-basis: 96px; width: 96px; height: 96px; } }
</style>
