<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">API IMAGE HISTORY</span><h1>换图记录</h1><p>每张原图的进度单独记录，成功结果随时查看。</p></div><ElButton type="primary" @click="router.push('/api-image-edits/create')"><ArtSvgIcon icon="ri:add-line" /> 新建换图</ElButton></div>
    <ChannelNotice :status="status" :error="channelError" :loading="channelLoading" :admin="isAdmin" :busy="channelBusy" @refresh="loadChannel" @resume="resume" />
    <ElAlert v-if="error || actionError" :title="error || actionError" type="error" :closable="false"><ElButton text @click="refresh()">重新加载</ElButton></ElAlert>
    <div class="hx-stats"><ElCard v-for="stat in stats" :key="stat.label" class="art-card" shadow="never"><span>{{ stat.label }}</span><strong>{{ stat.count }}<small> {{ stat.unit }}</small></strong></ElCard></div>
    <ElCard class="art-card hx-section" shadow="never">
      <div class="hx-filter"><ElSelect v-model="filter" aria-label="换图状态" style="width:160px"><ElOption label="全部状态" value="" /><ElOption v-for="(label, value) in taskLabels" :key="value" :label="label" :value="value" /></ElSelect><ElInput v-model="search" aria-label="搜索换图记录" maxlength="60" placeholder="搜索任务名称或编号" class="hx-search" clearable /><ElButton :loading="loading" @click="refresh()">刷新</ElButton></div>
      <ArtTable :data="tasks" :columns="columns" :loading="loading" height="auto" :show-table-header="false" :show-pagination="false" empty-height="300px" :empty-text="error ? '列表加载失败，请重试' : '暂无换图记录'" row-key="id">
        <template #name="{ row }"><div class="hx-table-name"><div class="record-thumb"><PicturePreview v-if="row.items[0]?.source?.url" :picture="row.items[0].source" title="原图缩略图" /></div><div><strong>{{ row.name }}</strong><small>{{ row.id }}</small></div></div></template>
        <template #status="{ row }"><ElTag :type="row.status === 'succeeded' ? 'success' : ['failed', 'partial_failed', 'uncertain'].includes(row.status) ? 'danger' : 'primary'">{{ taskLabels[row.status as ApiTaskState] }}</ElTag></template>
        <template #progress="{ row }"><span>{{ row.items.filter((item: ApiItem) => item.state === 'succeeded').length }} / {{ row.items.length }} 张成功</span><p class="hx-footnote">{{ row.items.filter((item: ApiItem) => item.state === 'failed').length }} 张失败 · 第 {{ row.batch.current }}/{{ row.batch.total }} 批</p></template>
        <template #operator="{ row }"><span>{{ row.operator || '未记录' }}</span></template>
        <template #created="{ row }"><span>{{ friendlyTime(row.created) }}</span></template>
        <template #action="{ row }"><ElButton text type="primary" @click="show(row.id)">查看详情</ElButton><ElButton text type="danger" :disabled="busy || isTaskActive(row)" @click="remove(row)">删除</ElButton></template>
      </ArtTable>
      <ElPagination v-if="total" v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" class="hx-gap" />
    </ElCard>
    <RealTaskDetail v-model="open" :task="selected" :loading="detailLoading" :error="detailError" :action-error="actionError" :busy="busy" :admin="isAdmin" :retry-pending="retryPending" :channel-blocked="blocked" @refresh="loadDetail()" @retry="retry" @resolve="resolve" />
  </div>
</template>
<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { apiImages } from '@/api/api-image-edits'
import { taskLabels, isTaskActive, type ApiTask, type ApiItem, type ApiTaskState } from '@/types/api-image-edits'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import ChannelNotice from './ChannelNotice.vue'
import RealTaskDetail from './RealTaskDetail.vue'
import PicturePreview from '../components/PicturePreview.vue'
import { friendlyTime } from './item-command'
import { useChannel } from './use-channel'
import { useRecords } from './use-records'
const router = useRouter(), route = useRoute()
const { status, error: channelError, loading: channelLoading, busy: channelBusy, isAdmin, blocked, load: loadChannel, resume } = useChannel()
const { tasks, total, page, search, filter, selectedId, selected, loading, detailLoading, error, detailError, actionError, busy, retryPending, loadDetail, refresh, action, retry } = useRecords()
const open = computed({ get: () => !!selectedId.value, set: value => { if (!value) void router.replace({ query: { ...route.query, task: undefined } }) } })
watch(() => route.query.task, id => { selectedId.value = typeof id === 'string' ? id : '' }, { immediate: true })
const stats = computed(() => [
  { label: '当前筛选任务', count: total.value, unit: '套' },
  { label: '本页排队 / 处理中', count: tasks.value.filter(t => ['queued', 'running'].includes(t.status)).length, unit: '套' },
  { label: '本页成功图片', count: tasks.value.reduce((n, t) => n + t.items.filter(i => i.state === 'succeeded').length, 0), unit: '张' },
  { label: '本页失败 / 需核实', count: tasks.value.reduce((n, t) => n + t.items.filter(i => ['failed', 'uncertain'].includes(i.state)).length, 0), unit: '张' }
])
const columns = [{ prop: 'name', label: '任务', useSlot: true, minWidth: 260 }, { prop: 'status', label: '状态', useSlot: true, width: 120 }, { prop: 'progress', label: '图片进度', useSlot: true, minWidth: 165 }, { prop: 'operator', label: '操作人', useSlot: true, width: 115 }, { prop: 'created', label: '创建时间', useSlot: true, minWidth: 120 }, { prop: 'action', label: '操作', useSlot: true, width: 175 }]
function show(id: string) { void router.replace({ query: { ...route.query, task: id } }) }
async function remove(task: ApiTask) {
  try { await ElMessageBox.confirm('删除此换图记录？删除后将无法从记录中查看结果。', '删除换图记录', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }) } catch { return }
  await action(async () => { await apiImages.remove(task.id); if (selectedId.value === task.id) open.value = false })
}
async function resolve(id: string) {
  try { await ElMessageBox.confirm('请先在服务端确认旧请求已停止，且不会继续返回结果。确认后将该项标为失败，再由你手动重试。', '核实不确定请求', { type: 'warning', confirmButtonText: '已核实停止', cancelButtonText: '取消' }) } catch { return }
  await action(() => apiImages.resolve(id)); await loadChannel()
}
</script>

<style scoped>
.record-thumb { width:52px; height:52px; flex:none; }
.hx-table-name { min-width:0; gap:10px; }
.hx-table-name > div:last-child { min-width:0; }
.hx-table-name strong, .hx-table-name small { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
:deep(.el-table .el-table__cell) { padding:9px 0; }
.hx-footnote { margin:4px 0 0; line-height:1.4; }
.hx-filter { flex-wrap:wrap; }
</style>
