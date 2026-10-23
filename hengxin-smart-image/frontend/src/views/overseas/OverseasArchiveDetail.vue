<template>
  <ElDialog :model-value="!!id" title="归档成品" width="min(1100px, 94vw)" append-to-body @close="$emit('close')">
    <p v-if="loading" role="status">正在加载归档成品…</p>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" />
    <ElButton :loading="loading" @click="load">刷新成品详情</ElButton>
    <template v-if="detail">
      <OverseasArchiveFields :archive="detail" />
      <p class="hx-footnote">{{ detail.pictureCount }} 张图片</p>
      <dl class="archive-detail-audit">
        <div><dt>归档人</dt><dd>{{ detail.latestArchive?.actorName || '历史记录未记录' }}</dd></div>
        <div><dt>归档时间</dt><dd>{{ detail.latestArchive ? `${formatBeijingTime(detail.latestArchive.at)}（北京时间）` : '历史记录未记录' }}</dd></div>
      </dl>
      <details class="archive-history hx-gap">
        <summary>归档操作历史（{{ detail.archiveHistory?.length || 0 }} 次已记录）</summary>
        <p v-if="detail.historyIncomplete !== false" class="hx-footnote">历史记录未记录：早期归档操作者或涉及图片无法核实。</p>
        <ol v-if="detail.archiveHistory?.length">
          <li v-for="event in detail.archiveHistory" :key="event.id">
            <p>{{ event.actorName }} · {{ formatBeijingTime(event.at) }}（北京时间）</p>
            <p class="hx-footnote">本次归档 {{ event.pictures.length }} 张图片</p>
            <ul><li v-for="picture in event.pictures" :key="picture.id">{{ picture.name }} · SKU：{{ picture.sku }}</li></ul>
          </li>
        </ol>
      </details>
      <p v-if="detail.sourceDeleted || !detail.taskId" class="hx-gap">原任务已删除</p>
      <ElButton v-else text type="primary" @click="$emit('source', detail.taskId)">查看原任务</ElButton>
      <ElSelect v-model="sourceFilter" aria-label="筛选来源会话" class="hx-gap"><ElOption label="全部会话" value="" /><ElOption v-for="source in archiveSources" :key="source.id" :label="source.name" :value="source.id" /></ElSelect>
      <div class="archive-pictures hx-gap"><div v-for="picture in filteredPictures" :key="detail.id + picture.id + revision"><OverseasArchivePicture :archive-id="detail.id" :picture="picture" :api="api" @failure="failure" @preview="previewIndex = detail.pictures.findIndex(p => p.id === picture.id)" /><p class="hx-footnote">来源会话：{{ picture.sourceConversationName || '历史会话未记录' }}</p></div></div>
    </template>
    <template #footer><ElButton @click="$emit('close')">关闭</ElButton></template>
  </ElDialog>
  <OverseasArchiveViewer v-if="detail && previewIndex !== null" :key="detail.id" :archive-id="detail.id" :api="api" :group="detail.pictures" :initial-index="previewIndex" @close="previewIndex = null" @failure="failure" />
</template>
<script setup lang="ts">
import { formatBeijingTime } from '@/utils/beijing-time'

import { computed, onUnmounted, ref, watch } from 'vue'
import { IdentityError } from '@/api/identity/request'
import type { ArchiveDetail, ArchivesApi } from '@/api/overseas/archives'
import { archiveError } from '@/api/overseas/archives'
import OverseasArchiveFields from './OverseasArchiveFields.vue'
import OverseasArchivePicture from './OverseasArchivePicture.vue'
import OverseasArchiveViewer from './OverseasArchiveViewer.vue'
const props = defineProps<{ id: string; api: ArchivesApi }>()
const emit = defineEmits<{ close: []; source: [taskId: string]; failure: [reason: unknown] }>()
const detail = ref<ArchiveDetail>(), error = ref(''), loading = ref(false), revision = ref(0)
const previewIndex = ref<number | null>(null), sourceFilter = ref('')
const archiveSources = computed(() => [...new Map((detail.value?.pictures || []).map(p => [p.sourceConversationId || 'legacy', { id: p.sourceConversationId || 'legacy', name: p.sourceConversationName || '历史会话未记录' }])).values()])
const filteredPictures = computed(() => (detail.value?.pictures || []).filter(p => !sourceFilter.value || (p.sourceConversationId || 'legacy') === sourceFilter.value))
let epoch = 0, alive = true
function failure(reason: unknown) {
  error.value = reason instanceof IdentityError && reason.status === 409 ? '成品正在删除或暂不可用，请刷新成品详情。' : archiveError(reason)
  if (reason instanceof IdentityError && [401, 403].includes(reason.status)) { ++epoch; detail.value = undefined; emit('failure', reason) }
}
async function load() {
  const id = props.id, current = ++epoch
  detail.value = undefined; previewIndex.value = null; sourceFilter.value = ''; error.value = ''; loading.value = false
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
.archive-history { overflow-wrap: anywhere; }
.archive-history summary { cursor: pointer; }
.archive-history ol, .archive-history ul { padding-left: 22px; }
.archive-detail-audit { border-top: 1px solid var(--el-border-color-lighter); margin: 16px 0 0; padding-top: 12px; font-size: 13px; }
.archive-detail-audit > div { display: flex; gap: 16px; margin: 6px 0; line-height: 1.6; }
.archive-detail-audit dt { width: 56px; flex-shrink: 0; color: var(--el-text-color-secondary); }
.archive-detail-audit dd { margin: 0; overflow-wrap: anywhere; }
h2, p { overflow-wrap: anywhere; }
</style>
