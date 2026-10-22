<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">API IMAGE HISTORY</span><h1>换图记录</h1><p>每张原图的进度单独记录，成功结果随时查看。</p></div><ElButton type="primary" @click="router.push('/api-image-edits/create')"><ArtSvgIcon icon="ri:add-line" /> 新建换图</ElButton></div>
    <ElTabs v-model="scope" class="scope-tabs" aria-label="任务查看范围"><ElTabPane label="我的任务" name="mine" /><ElTabPane label="全部任务" name="all" /></ElTabs>
    <ChannelNotice :status="status" :error="channelError" :loading="channelLoading" :admin="isAdmin" :busy="channelBusy" @refresh="loadChannel" @resume="resume" />
    <ElAlert v-if="error || actionError" :title="error || actionError" type="error" :closable="false"><ElButton text @click="refresh()">重新加载</ElButton></ElAlert>
    <div class="hx-stats"><ElCard v-for="stat in statCards" :key="stat.label" class="art-card" shadow="never"><span>{{ stat.label }}</span><strong>{{ stat.count }}<small> {{ stat.unit }}</small></strong></ElCard></div>
    <ElCard class="art-card hx-section" shadow="never">
      <div class="hx-filter records-filter">
        <div v-if="scope === 'all'" class="filter-field"><span>创建人</span><ElSelect v-model="creatorId" aria-label="创建人" placeholder="全部人员" filterable clearable :loading="creatorsLoading"><ElOption label="全部人员" value="" /><ElOption v-for="person in creators" :key="person.id" :label="person.id === userId ? `${person.name}（我）` : person.name" :value="person.id" /></ElSelect></div>
        <div class="filter-field"><span>状态</span><ElSelect v-model="filter" aria-label="换图状态" placeholder="全部状态"><ElOption label="全部状态" value="" /><ElOption v-for="(label, value) in taskLabels" :key="value" :label="label" :value="value" /></ElSelect></div>
        <div class="filter-field"><span>创建时间</span><ElSelect v-model="period" aria-label="创建时间"><ElOption label="全部时间" value="all" /><ElOption label="今天" value="today" /><ElOption label="近 7 天" value="week" /><ElOption label="近 30 天" value="month" /><ElOption label="自定义" value="custom" /></ElSelect></div>
        <ElInput v-model="search" aria-label="搜索换图记录" maxlength="60" placeholder="搜索任务名称或编号" class="hx-search" clearable><template #prefix><ArtSvgIcon icon="ri:search-line" /></template></ElInput>
        <div class="filter-actions"><ElButton text @click="resetFilters">重置</ElButton><ElButton :loading="loading" @click="refresh()">刷新</ElButton></div>
      </div>
      <ElAlert v-if="scope === 'all' && creatorsError" :title="creatorsError" type="error" :closable="false"><ElButton text @click="loadCreators">重新加载创建人</ElButton></ElAlert>
      <div v-if="period === 'custom'" class="date-range"><span>日期范围</span><ElDatePicker v-model="dates" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" range-separator="至"  aria-label="自定义日期范围" /><small v-if="!dates">请选择起止日期，当前暂不限制时间</small></div>
      <div class="scope-summary"><span>当前查看：<strong>{{ scopeText }}</strong><span class="summary-count">{{ stats ? `共 ${total} 套任务` : loading ? '正在加载…' : '任务数量暂不可用' }}</span></span><span>按创建时间倒序 · 统计包含全部筛选结果</span></div>
      <ArtTable :data="tasks" :columns="columns" :loading="loading" height="auto" :show-table-header="false" :show-pagination="false" empty-height="300px" :empty-text="error ? '列表加载失败，请重试' : hasFilters ? '没有匹配的记录，请调整筛选条件' : scope === 'mine' ? '你还没有创建换图任务' : '暂无换图记录'" row-key="id">
        <template #name="{ row }"><div class="hx-table-name"><div class="record-thumb"><PicturePreview v-if="row.cover?.url" :picture="row.cover" title="原图缩略图" /></div><div><strong>{{ row.name }}</strong><small>{{ row.id }}</small></div></div></template>
        <template #status="{ row }"><ElTag :type="row.status === 'succeeded' ? 'success' : ['failed', 'partial_failed'].includes(row.status) ? 'info' : 'primary'">{{ taskLabels[row.status as ApiTaskState] }}</ElTag><CliActivityTag :state="row.cliActivity" /></template>
        <template #progress="{ row }"><span>{{ row.counts.success }} / {{ row.counts.total }} 张已完成</span><p class="hx-footnote">{{ row.counts.failed }} 张未完成</p></template>
        <template #operator="{ row }"><span>{{ row.operator || '未记录' }}</span><small v-if="row.creatorId === userId" class="me-label">我</small></template>
        <template #created="{ row }"><span>{{ friendlyTime(row.created) }}</span></template>
        <template #action="{ row }"><ElButton text type="primary" :disabled="row.deletionState === 'deleting'" @click="show(row.id)">查看详情</ElButton><ElTooltip :content="deleteBlockedReason(row) || row.deletionError || '永久删除任务及关联资料'" placement="top"><span><ElButton text type="danger" :disabled="busy || !canDeleteTask(row)" @click="remove(row)">{{ row.deletionState === 'deleting' ? '删除中…' : row.deletionState === 'failed' ? '重试删除' : '删除' }}</ElButton></span></ElTooltip><p v-if="row.deletionState === 'failed'" class="hx-footnote deletion-error">删除未完成，请重试</p></template>
      </ArtTable>
      <div v-if="!total && !loading && !error" class="empty-actions"><ElButton v-if="hasFilters" @click="resetFilters">清空筛选</ElButton><template v-else><ElButton type="primary" @click="router.push('/api-image-edits/create')">新建换图</ElButton><ElButton v-if="scope === 'mine'" @click="scope = 'all'">查看全部任务</ElButton></template></div>
      <ElPagination v-if="total" v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[20, 50, 100]" :total="total" layout="total, sizes, prev, pager, next" class="hx-gap" />
    </ElCard>
    <RealTaskDetail v-model="open" :task="selected" :loading="detailLoading" :error="detailError" :action-error="actionError" :busy="busy" :retry-pending="retryPending" :channel-blocked="blocked" :channel="status" @refresh="loadDetail()" @retry="retry" />
  </div>
</template>
<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { taskLabels, canDeleteTask, deleteBlockedReason, type ApiTaskSummary, type ApiTaskState } from '@/types/api-image-edits'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import CliActivityTag from './CliActivityTag.vue'
import ChannelNotice from './ChannelNotice.vue'
import RealTaskDetail from './RealTaskDetail.vue'
import PicturePreview from '../components/PicturePreview.vue'
import { friendlyTime } from './item-command'
import { useChannel } from './use-channel'
import { useRecords } from './use-records'
const router = useRouter(), route = useRoute()
const { status, error: channelError, loading: channelLoading, busy: channelBusy, isAdmin, blocked, load: loadChannel, resume } = useChannel()
const { tasks, total, page, pageSize, search, filter, scope, creatorId, period, dates, stats, creators, creatorsLoading, creatorsError, hasFilters, loadCreators, resetFilters, userId, selectedId, selected, loading, detailLoading, error, detailError, actionError, busy, retryPending, loadDetail, refresh, retry, removeTask, deletedId, deletedName } = useRecords()
const open = computed({ get: () => !!selectedId.value, set: value => { if (!value) void router.replace({ query: { ...route.query, task: undefined } }) } })
watch(() => route.query.task, id => { selectedId.value = typeof id === 'string' ? id : '' }, { immediate: true })
watch(deletedId, id => { ElMessage.success(`“${deletedName.value}”已永久删除`); if (route.query.task === id) open.value = false })
const scopeText = computed(() => scope.value === 'mine' ? '我的任务' : creatorId.value ? `${creators.value.find(p => p.id === creatorId.value)?.name || '所选创建人'}的任务` : '全部人员的任务')
const statCards = computed(() => [
  { label: '当前筛选任务', count: stats.value?.tasks ?? '—', unit: '套' },
  { label: '排队 / 处理中', count: stats.value?.pendingTasks ?? '—', unit: '套' },
  { label: '成功图片', count: stats.value?.successImages ?? '—', unit: '张' },
  { label: '未完成图片', count: stats.value?.failedImages ?? '—', unit: '张' }
])
const columns = [{ prop: 'name', label: '任务', useSlot: true, minWidth: 260 }, { prop: 'status', label: '状态', useSlot: true, width: 120 }, { prop: 'progress', label: '图片进度', useSlot: true, minWidth: 165 }, { prop: 'operator', label: '创建人', useSlot: true, width: 115 }, { prop: 'created', label: '创建时间', useSlot: true, minWidth: 160 }, { prop: 'action', label: '操作', useSlot: true, width: 175 }]
function show(id: string) { void router.replace({ query: { ...route.query, task: id } }) }
async function remove(task: ApiTaskSummary) {
  if (!canDeleteTask(task) || busy.value) return
  try { await ElMessageBox.confirm(`永久删除“${task.name}”？永久删除任务及其关联图片、历史版本、Codex CLI会话和工作资料，无法恢复。`, '永久删除换图任务', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }) } catch { return }
  await removeTask(task)
}
</script>

<style scoped>
.deletion-error { color:var(--el-color-danger); }
.record-thumb { width:52px; height:52px; flex:none; }
.hx-table-name { min-width:0; gap:10px; }
.hx-table-name > div:last-child { min-width:0; }
.hx-table-name strong, .hx-table-name small { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
:deep(.el-table .el-table__cell) { padding:9px 0; }
.hx-footnote { margin:4px 0 0; line-height:1.4; }
.hx-filter { flex-wrap:wrap; }
.scope-tabs { margin:-8px 0 20px; }
.scope-tabs :deep(.el-tabs__header) { margin:0; }
.scope-tabs :deep(.el-tabs__item) { height:44px; font-size:15px; }
.scope-tabs :deep(.el-tabs__content) { display:none; }
.records-filter { justify-content:flex-start; gap:16px; margin-bottom:18px; }
.filter-field { display:flex; align-items:center; gap:10px; color:var(--art-gray-600); font-size:13px; }
.filter-field > span { white-space:nowrap; }
.filter-field .el-select { width:150px; }
.filter-actions { margin-left:auto; display:flex; gap:10px; }
.filter-actions .el-button { margin:0; }
.scope-summary { display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; font-size:12px; color:var(--art-gray-600); margin:0 0 18px; }
.scope-summary strong { font-weight:500; color:var(--el-color-primary); }
.summary-count { margin-left:14px; }
.me-label { margin-left:6px; font-size:11px; color:var(--el-color-primary); }
.date-range { display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin:0 0 18px; color:var(--art-gray-600); font-size:13px; }
.date-range :deep(.el-date-editor) { max-width:340px; }
.empty-actions { text-align:center; margin:0 0 24px; }
@media(max-width:1100px) { .records-filter .hx-search { max-width:none; flex:1; min-width:190px; } }
@media(max-width:640px) { .filter-field { width:100%; justify-content:space-between; } .filter-field .el-select { width:calc(100% - 72px); } .hx-stats { grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; } .hx-stats :deep(.el-card__body) { padding:16px; } .scope-summary { line-height:1.8; } :deep(.el-pagination) { flex-wrap:wrap; row-gap:10px; } .hx-heading { gap:10px; } .hx-heading > .el-button { padding:10px; } }
</style>
