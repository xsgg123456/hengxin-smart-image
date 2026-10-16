<template>
  <ElDialog :model-value="!!id" title="归档成品" width="min(1100px, 94vw)" append-to-body @close="$emit('close')">
    <p v-if="loading" role="status">正在加载归档成品…</p>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" />
    <ElButton :loading="loading" @click="load">刷新成品详情</ElButton>
    <template v-if="detail">
      <h2 class="hx-gap">{{ detail.productName }}</h2><p>{{ detail.brand }} · {{ detail.platform }} · {{ detail.skus.map(sku => sku.code).join(' · ') }}</p>
      <p class="hx-footnote">{{ detail.pictureCount }} 张图片 · 归档于 {{ formatBeijingTime(detail.createdAt) }}</p>
      <p v-if="detail.sourceDeleted || !detail.taskId" class="hx-gap">原任务已删除</p>
      <ElButton v-else text type="primary" @click="$emit('source', detail.taskId)">查看原任务</ElButton>
      <div class="archive-pictures hx-gap"><OverseasArchivePicture v-for="(picture, index) in detail.pictures" :key="detail.id + picture.id + revision" :archive-id="detail.id" :picture="picture" :api="api" @failure="failure" @preview="previewIndex = index" /></div>
    </template>
    <template #footer><ElButton @click="$emit('close')">关闭</ElButton></template>
  </ElDialog>
  <OverseasArchiveViewer v-if="detail && previewIndex !== null" :key="detail.id" :archive-id="detail.id" :api="api" :group="detail.pictures" :initial-index="previewIndex" @close="previewIndex = null" @failure="failure" />
</template>
<script setup lang="ts">
import { formatBeijingTime } from '@/utils/beijing-time'

import { onUnmounted, ref, watch } from 'vue'
import { IdentityError } from '@/api/identity/request'
import type { ArchiveDetail, ArchivesApi } from '@/api/overseas/archives'
import { archiveError } from '@/api/overseas/archives'
import OverseasArchivePicture from './OverseasArchivePicture.vue'
import OverseasArchiveViewer from './OverseasArchiveViewer.vue'
const props = defineProps<{ id: string; api: ArchivesApi }>()
const emit = defineEmits<{ close: []; source: [taskId: string]; failure: [reason: unknown] }>()
const detail = ref<ArchiveDetail>(), error = ref(''), loading = ref(false), revision = ref(0)
const previewIndex = ref<number | null>(null)
let epoch = 0, alive = true
function failure(reason: unknown) {
  error.value = archiveError(reason)
  if (reason instanceof IdentityError && [401, 403].includes(reason.status)) { ++epoch; detail.value = undefined; emit('failure', reason) }
}
async function load() {
  const id = props.id, current = ++epoch
  detail.value = undefined; previewIndex.value = null; error.value = ''; loading.value = false
  if (!id) return
  loading.value = true
  try { const value = await props.api.get(id); if (alive && current === epoch) { detail.value = value; revision.value++ } }
  catch (reason) { if (alive && current === epoch) failure(reason) }
  finally { if (current === epoch) loading.value = false }
}
watch(() => props.id, load, { immediate: true })
onUnmounted(() => { alive = false; ++epoch; detail.value = undefined })
</script>
<style scoped>
.archive-pictures { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(200px, 100%), 1fr)); gap: 16px; }
h2, p { overflow-wrap: anywhere; }
</style>
