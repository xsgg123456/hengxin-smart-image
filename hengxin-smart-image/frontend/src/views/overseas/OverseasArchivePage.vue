<template>
  <div class="hx-heading"><div><h1>成品库</h1><p>搜索品名、品牌或 SKU，任一项匹配即可。</p></div><ElTag type="success">{{ total }} 套归档</ElTag></div>
  <ElCard class="art-card hx-section" shadow="never"><div class="hx-filter">
    <ElInput v-model="search" clearable class="hx-search" aria-label="搜索成品" placeholder="搜索品名、品牌、SKU" /><ElSelect v-model="archiver" clearable filterable aria-label="归档人筛选" placeholder="全部归档人" style="width:200px"><ElOption v-for="person in archivers" :key="person.id" :label="person.name" :value="person.id" /></ElSelect><ElButton class="light-neutral" @click="reset">重置筛选</ElButton><ElButton class="light-neutral" :loading="loading" @click="refresh">刷新成品</ElButton>
  </div><p v-if="archiver" class="hx-footnote hx-gap">显示 {{ archivers.find(person => person.id === archiver)?.name || '所选人员' }} 曾参与归档的成品，包含多人分批归档。</p><ElAlert v-if="archiversError" :title="archiversError" type="error" :closable="false"><ElButton @click="loadArchivers">重试人员列表</ElButton></ElAlert></ElCard>
  <p v-if="loading" role="status">正在加载成品…</p><ElAlert v-if="error" :title="error" type="error" :closable="false" />
  <ElEmpty v-if="!loading && !error && !items.length" description="暂无匹配成品；设计归档后的图片会显示在这里"><ElButton v-if="search || archiver" class="light-neutral" @click="reset">清空筛选</ElButton></ElEmpty>
  <div class="hx-library-grid hx-gap"><ElCard v-for="item in items" :key="item.id" class="art-card hx-library-card" shadow="never">
    <div class="archive-cover-layout"><OverseasArchiveCover v-if="!item.deletionStatus" :archive="item" :api="api" @preview="preview = item.id" @failure="fail" /><div v-else class="archive-unavailable">{{ item.deletionStatus === 'deleting' ? '正在删除…' : '删除未完成' }}</div>
      <div class="hx-library-info"><div class="archive-card-status"><ElTag :type="item.deletionStatus ? 'warning' : 'success'">{{ item.deletionStatus === 'deleting' ? '正在删除' : item.deletionStatus === 'delete_failed' ? '删除未完成' : '已归档' }}</ElTag></div>
        <OverseasArchiveFields :archive="item" compact />
        <p v-if="item.sourceDeleted || !item.taskId" class="hx-footnote">原任务已删除</p>
        <p class="hx-footnote">{{ item.pictureCount }} 张图片</p>
      </div>
    </div>
    <dl class="archive-card-audit">
      <div><dt>最近归档人</dt><dd>{{ item.latestArchive?.actorName || '历史记录未记录' }}</dd></div>
      <div><dt>归档时间</dt><dd>{{ item.latestArchive ? `${formatBeijingTime(item.latestArchive.at)}（北京时间）` : '历史记录未记录' }}</dd></div>
      <div v-if="archiver && item.latestArchive?.actorId !== archiver"><dt>筛选匹配</dt><dd>{{ archivers.find(person => person.id === archiver)?.name || '所选人员' }} 曾参与归档</dd></div>
    </dl>
    <div class="hx-row archive-card-actions"><ElButton text type="primary" :disabled="!!item.deletionStatus" @click="selected = item.id">查看成品</ElButton><ElButton class="light-neutral" :loading="downloading === item.id" :disabled="!!item.deletionStatus" @click="download(item)">下载整套成品</ElButton></div>
    <OverseasArchiveDelete v-if="canDelete" :archive="item" :api="api" :can-delete="canDelete" @changed="deletionChanged" @failure="fail" />
  </ElCard></div>
  <ElPagination v-if="!error && total" class="hx-gap" layout="prev, pager, next" :current-page="page" :page-size="20" :total="total" @current-change="page = $event" />
  <OverseasArchiveDetail v-if="selected" :id="selected" :api="api" @close="selected = ''" @source="router.push(`/overseas/tasks/${$event}`)" @failure="fail" />
  <OverseasArchiveViewer v-if="preview" :key="preview" :archive-id="preview" :api="api" :initial-index="0" @close="preview = ''" @failure="fail" />
</template>
<script setup lang="ts">
import { formatBeijingTime } from '@/utils/beijing-time'

import { computed, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { IdentityError } from '@/api/identity/request'
import { saveBlob } from '@/api/overseas/pictures'
import { createArchivesApi, type Archive, type ArchiveDeletion, type Archiver } from '@/api/overseas/archives'
import OverseasArchiveDelete from './OverseasArchiveDelete.vue'
import OverseasArchiveFields from './OverseasArchiveFields.vue'
import OverseasArchiveDetail from './OverseasArchiveDetail.vue'
import OverseasArchiveCover from './OverseasArchiveCover.vue'
import OverseasArchiveViewer from './OverseasArchiveViewer.vue'
import { archiveError, clearArchiveImages } from '@/api/overseas/archives'
const props = defineProps<{ refresh: number; capabilities?: string[] }>(), emit = defineEmits<{ failure: [reason: unknown] }>()
const router = useRouter(), api = createArchivesApi(), items = ref<Archive[]>([]), total = ref(0), page = ref(1), search = ref(''), error = ref(''), loading = ref(false), downloading = ref(''), selected = ref('')
const archiver = ref(''), archivers = ref<Archiver[]>([]), archiversError = ref('')
const preview = ref(''), canDelete = computed(() => props.capabilities?.includes('task.delete') === true)
function deletionChanged(value: ArchiveDeletion) {
  clearArchiveImages(value.archiveId)
  if (selected.value === value.archiveId) selected.value = ''
  if (preview.value === value.archiveId) preview.value = ''
  if (value.status === 'deleted') { void load(); void loadArchivers(); return }
  const item = items.value.find(item => item.id === value.archiveId)
  if (item) { item.deletionStatus = value.status; item.deletionError = value.error }
}
let epoch = 0, alive = true, timer: ReturnType<typeof setTimeout> | undefined
function fail(reason: unknown) { error.value = archiveError(reason); if (reason instanceof IdentityError && [401, 403].includes(reason.status)) { ++epoch; ++archiversEpoch; archiver.value = ''; archivers.value = []; selected.value = ''; preview.value = ''; items.value = []; total.value = 0; loading.value = false; emit('failure', reason) } }
async function load() {
  const current = ++epoch; loading.value = true; error.value = ''; items.value = []; total.value = 0
  try { const result = await api.list({ search: search.value.trim(), archiverId: archiver.value, page: page.value, pageSize: 20 }); if (alive && current === epoch) { items.value = result.items; total.value = result.total; if (!items.value.length && page.value > 1) page.value = Math.max(1, Math.ceil(total.value / 20)) } }
  catch (reason) { if (alive && current === epoch) fail(reason) }
  finally { if (current === epoch) loading.value = false }
}
async function download(item: Archive) { if (downloading.value || item.deletionStatus) return; downloading.value = item.id; const current = epoch; try { const blob = await api.download(item.id); if (alive && current === epoch && !item.deletionStatus) saveBlob(blob, `${item.productName}.zip`) } catch (reason) { if (alive && current === epoch) fail(reason) } finally { downloading.value = '' } }
let archiversEpoch = 0
async function loadArchivers() {
  const current = ++archiversEpoch; archiversError.value = ''
  try { const value = await api.operators(); if (alive && current === archiversEpoch) { archivers.value = value.items; if (archiver.value && !value.items.some(person => person.id === archiver.value)) archiver.value = '' } }
  catch (reason) { if (alive && current === archiversEpoch) { archivers.value = []; archiversError.value = archiveError(reason); if (reason instanceof IdentityError && [401, 403].includes(reason.status)) fail(reason) } }
}
function refresh() { void loadArchivers(); void load() }
function reset() { if (search.value || archiver.value) { search.value = ''; archiver.value = '' } else if (page.value !== 1) page.value = 1; else void load() }
watch([search, archiver], () => { selected.value = ''; preview.value = ''; ++epoch; loading.value = true; error.value = ''; items.value = []; total.value = 0; clearTimeout(timer); timer = setTimeout(() => { if (page.value === 1) void load(); else page.value = 1 }, 250) })
watch([page, () => props.refresh], () => { selected.value = ''; preview.value = ''; void load() }, { immediate: true })
watch(() => props.refresh, () => { archivers.value = []; void loadArchivers() }, { immediate: true })
onUnmounted(() => { alive = false; ++epoch; ++archiversEpoch; clearTimeout(timer); items.value = []; archivers.value = [] })
</script>
<style scoped>
.hx-filter > .el-input { width: 255px; max-width: 100%; }
:deep(.light-neutral:not(:hover):not(:focus-visible)) { color: var(--el-text-color-regular); border-color: var(--el-border-color); }
.hx-library-grid { grid-template-columns: repeat(auto-fill, minmax(min(420px, 100%), 1fr)); }
.hx-library-card :deep(.el-card__body) { padding: 18px; }
.archive-cover-layout { display: flex; align-items: center; gap: 18px; }
.hx-library-info { overflow-wrap: anywhere; min-width: 0; flex: 1; padding: 0; }
.hx-library-info h3 { margin: 10px 0 6px; line-height: 1.5; }
.hx-library-info p { margin: 6px 0; }
.archive-card-status { display: flex; justify-content: flex-end; }
.archive-card-audit { border-top: 1px solid var(--el-border-color-lighter); margin: 16px 0 0; padding-top: 12px; font-size: 13px; }
.archive-card-audit > div { display: flex; gap: 16px; margin: 6px 0; line-height: 1.6; }
.archive-card-audit dt { width: 70px; flex-shrink: 0; color: var(--el-text-color-secondary); }
.archive-card-audit dd { margin: 0; overflow-wrap: anywhere; }
.archive-unavailable { flex: 0 0 96px; color: var(--el-text-color-secondary); }
.archive-card-actions { margin-top: 14px; }
@media (max-width: 600px) { .hx-filter > .el-input { width: 100%; max-width: none; } .archive-cover-layout { gap: 12px; } }
</style>
