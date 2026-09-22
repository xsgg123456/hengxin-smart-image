<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">FINISHED & COLLECTED</span><h1>成品库</h1><p>满意的作品，值得好好保存。随时查找、预览与下载。</p></div><ElTag effect="plain" size="large">{{ total }} 套匹配成品</ElTag></div>
    <ElCard class="art-card hx-section" shadow="never">
      <div class="hx-filter">
        <ElRadioGroup v-model="mode" aria-label="成品类型"><ElRadioButton value="all">全部成品</ElRadioButton><ElRadioButton v-for="(label, key) in labels" :key="key" :value="key">{{ label }}</ElRadioButton></ElRadioGroup>
        <ElInput v-model="search" placeholder="搜索成品名称" aria-label="搜索成品名称" clearable class="hx-search" />
      </div>
      <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon><ElButton text type="primary" :disabled="loading" @click="load">重试加载</ElButton></ElAlert>
      <div v-loading="loading" :aria-busy="loading">
        <div class="hx-library-grid">
          <ElCard v-for="a in archives" :key="a.id" class="art-card hx-library-card" shadow="never">
            <PictureMosaic :pictures="a.images" :title="a.name" />
            <div class="hx-library-info">
              <ElTag size="small" type="success">已归档</ElTag><h3>{{ a.name }}</h3><p>{{ labels[a.mode] }} · {{ a.images.length }} 张图片</p><p>{{ formatTime(a.time) }}</p>
              <div class="hx-row"><ElButton type="primary" plain :disabled="loading || !!deleting" @click="open(a.id)">查看成品</ElButton><ElButton text :disabled="loading || !!deleting || !!downloading || !a.images.length" :loading="downloading === a.id" @click="downloadArchive(a)">{{ isMockMode ? '下载整套示例' : '下载整套' }}</ElButton></div>
              <div class="hx-gap"><ElButton text type="danger" :disabled="loading || !!deleting || !!downloading" :loading="deleting === a.id" @click="remove(a)">删除成品</ElButton></div>
            </div>
          </ElCard>
        </div>
        <ElEmpty v-if="!archives.length" :description="loading ? '正在加载成品…' : error ? '成品加载失败，请重试' : '暂无匹配成品，可清除筛选或归档任务结果'"><template v-if="!loading && !error"><ElButton v-if="mode !== 'all' || search" @click="clearFilters">清除筛选</ElButton><ElButton @click="router.push('/tasks/index')">前往任务中心</ElButton></template></ElEmpty>
      </div>
      <ElPagination v-model:current-page="page" class="hx-gap" :page-size="pageSize" :total="total" layout="prev, pager, next, total" :disabled="loading || !!deleting" />
    </ElCard>
    <ElDialog :model-value="detailOpen" :title="preview?.name || '成品详情'" width="80%" :before-close="closePreview">
      <div v-loading="detailLoading" :aria-busy="detailLoading">
        <ElAlert v-if="detailError" :title="detailError" type="error" :closable="false" show-icon><ElButton text type="primary" :disabled="detailLoading" @click="loadDetail">重试详情</ElButton></ElAlert>
        <template v-if="preview">
          <p class="hx-muted">归档图片 · 后续修改不会覆盖此版本</p>
          <ElButton v-if="preview.taskId" text type="primary" :loading="sourceLoading" @click="viewSource">查看来源任务</ElButton>
          <p v-else class="hx-muted">此成品未记录来源任务，归档图片仍可查看和下载。</p>
          <ElAlert v-if="sourceError" :title="sourceError" type="warning" :closable="false" show-icon class="hx-gap" />
          <div class="hx-result-grid"><ElCard v-for="(p, i) in preview.images" :key="i" class="art-card" shadow="never">
            <PicturePreview :picture="p" :pictures="preview.images" :index="i" title="归档快照" />
            <div class="hx-result-meta"><strong>{{ p.name }}</strong><ElTag size="small">v{{ p.version || 1 }}</ElTag></div>
            <ElButton text type="primary" :disabled="!!downloading" :loading="downloading === `${preview.id}:${i}`" @click="downloadOne(p, `${preview.id}:${i}`)">{{ isMockMode ? '下载示例' : '下载图片' }}</ElButton>
          </ElCard></div>
          <ElEmpty v-if="!preview.images.length" description="此归档暂无可下载图片" />
        </template>
        <p v-else-if="detailLoading" class="hx-muted">正在加载归档快照…</p>
      </div>
    </ElDialog>
  </div>
</template>
<script setup lang="ts">
import PicturePreview from './PicturePreview.vue'
import PictureMosaic from './PictureMosaic.vue'
import { ref, watch, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listArchives, getArchive, deleteArchive } from '@/api/archives'
import { getTask } from '@/api/tasks'
import { isMockMode } from '@/api/hengxin/client'
import type { Archive, Picture } from '@/types/hengxin'
import { labels } from '../model'
import { downloadSet, downloadPicture } from '../download'
import { useListLocation } from '../list-location'
const router = useRouter()
const { mode, search, page, detailId: previewId, detailOpen, openDetail, closeDetail, clearFilters } = useListLocation(router, '/archive/index', 'archive')
const archives = ref<Archive[]>([]), total = ref(0), pageSize = 12
const loading = ref(false), error = ref(''), deleting = ref(''), downloading = ref('')
const preview = ref<Archive>(), detailLoading = ref(false), detailError = ref('')
const sourceLoading = ref(false), sourceError = ref('')
let request = 0, detailRequest = 0, sourceRequest = 0
function message(reason: unknown, fallback: string) { return reason instanceof Error ? reason.message : fallback }
async function load() {
  const current = ++request
  loading.value = true; error.value = ''
  try {
    const result = await listArchives({ page: page.value, pageSize, search: search.value.trim(), mode: mode.value === 'all' ? undefined : mode.value })
    if (current !== request) return
    const last = Math.max(1, Math.ceil(result.total / pageSize))
    if (page.value > last) { page.value = last; return }
    archives.value = result.items; total.value = result.total
  } catch (reason) {
    if (current === request) error.value = message(reason, '成品加载失败，请重试')
  } finally { if (current === request) loading.value = false }
}
watch([mode, search, page], load, { immediate: true })
onBeforeUnmount(() => { request++; detailRequest++; sourceRequest++ })
watch(previewId, () => {
  preview.value = undefined; detailError.value = ''; detailLoading.value = false; detailRequest++
  sourceError.value = ''; sourceLoading.value = false; sourceRequest++
  if (previewId.value) void loadDetail()
}, { immediate: true })
function open(id: string) { void openDetail(id) }
function closePreview(done: () => void) { void closeDetail(); done() }
async function loadDetail() {
  const current = ++detailRequest, id = previewId.value
  if (!id) return
  detailLoading.value = true; detailError.value = ''
  try { const result = await getArchive(id); if (current === detailRequest) preview.value = result }
  catch (reason) { if (current === detailRequest) detailError.value = message(reason, '详情加载失败，请重试') }
  finally { if (current === detailRequest) detailLoading.value = false }
}
async function viewSource() {
  const taskId = preview.value?.taskId, archiveId = previewId.value
  if (!taskId || sourceLoading.value) return
  const current = ++sourceRequest
  sourceLoading.value = true; sourceError.value = ''
  try {
    await getTask(taskId)
    if (current === sourceRequest && previewId.value === archiveId) await router.push({ path: '/tasks/index', query: { task: taskId } })
  } catch (reason) {
    if (current === sourceRequest) sourceError.value = `来源任务暂不可访问：${message(reason, '请稍后重试')}。归档图片仍可查看和下载。`
  } finally { if (current === sourceRequest) sourceLoading.value = false }
}
async function downloadArchive(a: Archive) {
  if (downloading.value) return
  downloading.value = a.id
  try { await downloadSet(a.images, a.name) } finally { downloading.value = '' }
}
async function downloadOne(p: Picture, key: string) {
  if (downloading.value) return
  downloading.value = key
  try { await downloadPicture(p) } finally { downloading.value = '' }
}
function formatTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}
async function remove(a: Archive) {
  if (deleting.value) return
  deleting.value = a.id
  try {
    try { await ElMessageBox.confirm(`删除“${a.name}”？对应任务结果保留。`, '删除成品', { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }) }
    catch { return }
    await deleteArchive(a.id)
    if (previewId.value === a.id) await closeDetail()
    ElMessage.success('成品已删除')
    await load()
  } catch (reason) { ElMessage.error(message(reason, '删除失败，请重试')) }
  finally { deleting.value = '' }
}
</script>
