<template>
  <div class="hx-page hx-tasks-page">
    <div class="hx-heading"><div><h1>任务中心</h1><p>查看全员任务，从提交到成品，每一套图片的进度都在这里。</p></div><ElDropdown trigger="click" @command="create"><ElButton type="primary"><ArtSvgIcon icon="ri:add-line" /> 新建任务 <ArtSvgIcon icon="ri:arrow-down-s-line" /></ElButton><template #dropdown><ElDropdownMenu><ElDropdownItem v-for="(label, key) in labels" :key="key" :command="key">{{ label }}</ElDropdownItem></ElDropdownMenu></template></ElDropdown></div>
    <div class="task-overview">
      <ElRadioGroup v-model="scope" aria-label="任务范围"><ElRadioButton value="all">全员任务</ElRadioButton><ElRadioButton value="mine">我的任务</ElRadioButton></ElRadioGroup>
      <dl class="task-statistics" :aria-label="scope === 'mine' ? '我创建的任务统计' : '全员任务统计'"><div v-for="s in statCards" :key="s.label" :title="`${s.label}：${s.count ?? '—'} ${s.unit}`"><dt>{{ s.label }}</dt><dd>{{ loading ? '…' : s.count ?? '—' }}</dd></div></dl>
    </div>
    <ElCard class="art-card hx-section" shadow="never">
      <div class="hx-filter task-filters">
        <ElRadioGroup v-model="state" aria-label="任务状态"><ElRadioButton value="all">全部状态</ElRadioButton><ElRadioButton value="排队中">排队中</ElRadioButton><ElRadioButton value="执行中">执行中</ElRadioButton><ElRadioButton value="待查看">待查看</ElRadioButton><ElRadioButton value="部分失败">部分失败</ElRadioButton><ElRadioButton value="失败">失败</ElRadioButton></ElRadioGroup>
        <div class="task-search-controls">
        <ElSelect v-model="mode" class="hx-search" aria-label="处理类型"><ElOption value="all" label="全部类型" /><ElOption v-for="(label, key) in labels" :key="key" :value="key" :label="label" /></ElSelect>
        <ElInput v-model="search" clearable placeholder="搜索名称、编号或 SKU" aria-label="搜索任务" class="hx-search"><template #prefix><ArtSvgIcon icon="ri:search-line" /></template></ElInput>
        </div>
      </div>
      <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon><ElButton text @click="load()">重试加载</ElButton></ElAlert>
      <ElAlert v-if="deleteError" :title="deleteError" type="error" :closable="false" show-icon />
      <ArtTable :cell-style="{ padding: '4px 0' }" :header-cell-style="{ padding: '8px 0' }" :data="tasks" :columns="columns" :loading="loading" height="auto" empty-height="340px" :show-table-header="false" row-key="id" empty-text="暂无匹配任务" :show-pagination="false">
        <template #name="{ row }"><div class="hx-table-name task-name">
          <PicturePreview v-if="row.images[0]" class="task-picture" :picture="row.images[0]" :pictures="row.images" :title="`${row.name} · 当前结果`" /><span v-else class="task-picture task-picture-empty" aria-hidden="true"><ArtSvgIcon icon="ri:image-line" /></span>
          <div class="task-identity"><button class="task-title" type="button" :title="row.name" @click="show(row)">{{ row.name }}</button>
            <div class="task-meta"><small class="task-owner" :title="`创建人：${row.ownerName || row.ownerId}${row.sku ? ` · SKU：${row.sku}` : ''}`">{{ row.ownerName || row.ownerId }}{{ row.sku ? ` · SKU：${row.sku}` : '' }}</small>
            <div class="task-id"><small :title="row.id">{{ row.id }}</small><ElButton text size="small" :aria-label="`复制任务编号 ${row.id}`" @click="copyId(row.id)"><ArtSvgIcon icon="ri:file-copy-line" /></ElButton></div></div>
          </div></div></template>
        <template #mode="{ row }"><ElTag effect="plain">{{ labels[row.mode as Mode] }}</ElTag><ElTag v-if="row.executionSource === 'fixture'" type="warning" size="small">测试任务</ElTag></template>
        <template #state="{ row }"><ElTag :type="['失败', '部分失败'].includes(row.state) ? 'danger' : row.state === '待查看' ? 'success' : 'primary'">{{ row.state }}</ElTag></template>
        <template #progress="{ row }"><span v-if="['部分失败', '失败'].includes(row.state)">本轮未全部成功</span><ElProgress v-else-if="row.progress !== null" :percentage="row.progress" :stroke-width="5" /><span v-else>{{ row.state }}</span><small class="task-result-count hx-muted">{{ row.images.length }} 张可查看{{ row.outputCount ? ` / ${row.outputCount} 张` : '' }}{{ ['部分失败', '失败'].includes(row.state) ? '（含保留版本）' : '' }}</small></template>
        <template #time="{ row }">{{ formatTime(row.time) }}</template>
        <template #action="{ row }"><div class="task-actions"><ElButton text type="primary" @click="show(row)">查看详情</ElButton><ElButton text type="danger" :disabled="!!deleting" :loading="deleting === row.id" @click="remove(row)">删除</ElButton></div></template>
      </ArtTable>
      <ElPagination v-model:current-page="page" class="hx-gap" :page-size="pageSize" :total="total" layout="prev, pager, next, total" :disabled="loading || !!deleting" />
    </ElCard>
    <TaskDetail v-model="detailOpen" :task-id="currentId" :active="active" @changed="syncChanged" />
  </div>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteTask } from '@/api/tasks'
import type { Task, Mode } from '@/types/hengxin'
import { labels } from '../model'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import TaskDetail from './TaskDetail.vue'
import PicturePreview from './PicturePreview.vue'
import { useTaskList } from './use-task-list'
const router = useRouter()
const { mode, search, state, scope, tasks, stats, page, total, pageSize, loading, error, active, load,
  detailOpen, detailId: currentId, openDetail, closeDetail } = useTaskList()
const deleting = ref(''), deleteError = ref('')
const statCards = computed(() => [{ label: '全部任务', count: stats.value?.total, unit: '个任务' }, { label: '处理中', count: stats.value?.processing, unit: '个任务' }, { label: '等待查看', count: stats.value?.ready, unit: '个任务' }, { label: '已归档成品', count: stats.value?.archived, unit: '套成品' }])
const columns = [{ prop: 'name', label: '任务 / 创建人', minWidth: 270, useSlot: true }, { prop: 'mode', label: '处理类型', width: 96, useSlot: true }, { prop: 'state', label: '状态', width: 90, useSlot: true }, { prop: 'progress', label: '生成进度', width: 150, useSlot: true }, { prop: 'time', label: '提交时间', minWidth: 148, useSlot: true }, { prop: 'action', label: '操作', width: 144, useSlot: true }]
async function copyId(id: string) {
  try { await navigator.clipboard.writeText(id); ElMessage.success('任务编号已复制') }
  catch { await ElMessageBox.alert(id, '任务编号（请手动复制）', { confirmButtonText: '关闭' }).catch(() => {}) }
}
function show(task: Task) { void openDetail(task.id) }
function syncChanged(update?: { taskId: string; state: Task['state']; progress: number | null; currentRoundId: string }) {
  if (!update) { void load(true); return }
  const row = tasks.value.find(item => item.id === update.taskId)
  if (row) {
    row.state = update.state
    row.progress = update.progress
    row.currentRoundId = update.currentRoundId
  }
  // 后台执行通常还未完成，避免立即读取旧列表把刚刚显示的受理状态覆盖掉。
  window.setTimeout(() => { void load(true) }, 3500)
}
function create(mode: Mode) {
  void router.push({ path: `/image-processing/${mode}`, query: { newTask: crypto.randomUUID() } })
}
function formatTime(value: string) { return new Date(value).toLocaleString('zh-CN', { hour12: false }) }
async function remove(task: Task) {
  if (deleting.value) return
  deleting.value = task.id
  try {
    try { await ElMessageBox.confirm(`确认删除“${task.name}”？运行中的任务将停止，已归档的图片保留。`, '删除任务', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }) } catch { return }
    await deleteTask(task.id)
    deleteError.value = ''; ElMessage.success('任务已删除')
    if (currentId.value === task.id) await closeDetail()
    await load()
  } catch (reason) { deleteError.value = reason instanceof Error ? reason.message : '删除失败，请点击删除重试' }
  finally { deleting.value = '' }
}
</script>
<style scoped>
 .hx-tasks-page { padding-top:8px; }
.hx-heading { margin-bottom:12px; }
.hx-heading h1 { font-size:22px; margin:0 0 4px; }
.hx-heading p { margin:0; }
.task-overview { display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; margin-bottom:12px; }
.task-statistics { display:flex; align-items:center; gap:24px; flex-wrap:wrap; margin:0; }
.task-statistics>div { display:flex; align-items:baseline; gap:8px; }
.task-statistics dt { font-size:12px; color:var(--art-gray-600); }
.task-statistics dd { margin:0; font-size:20px; font-weight:600; font-variant-numeric:tabular-nums; color:var(--art-gray-800); }
.hx-section :deep(.el-card__body) { padding:16px; }
.task-filters { margin-bottom:12px; gap:12px; }
.task-meta { display:flex; align-items:center; gap:12px; min-width:0; }
.task-owner { max-width:48%; flex-shrink:0; }
.task-id { min-width:0; flex:1; }
.task-actions { display:flex; align-items:center; gap:4px; white-space:nowrap; }
.task-actions .el-button { margin-left:0; padding:8px; }
.hx-tasks-page :deep(.el-table__cell) { padding:6px 0; }
.hx-tasks-page :deep(.el-table .cell) { line-height:20px; }
.task-name { padding:2px 0; gap:10px; }
.hx-section>.hx-gap { margin-top:12px; }
@media(max-width:900px) { .task-statistics { gap:12px 20px; } .task-overview { align-items:flex-start; gap:8px; } }

.task-search-controls { display:flex; gap:12px; flex:1; min-width:300px; justify-content:flex-end; }
.task-search-controls .el-select { max-width:160px; }
.task-name { min-width:0; }
.task-picture { width:44px; height:44px; flex:0 0 44px; }
.task-picture-empty { display:flex; align-items:center; justify-content:center; border-radius:8px; background:var(--art-gray-100); color:var(--art-gray-500); }
.task-identity { flex:1; min-width:0; }
.task-title { display:block; max-width:100%; border:0; background:none; padding:0; color:var(--el-text-color-primary); font:inherit; font-weight:500; text-align:left; cursor:pointer; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.task-title:hover { color:var(--el-color-primary); }
.task-title:focus-visible { outline:2px solid var(--el-color-primary); outline-offset:2px; }
.task-id { display:flex; align-items:center; gap:4px; }
.task-id small,.task-owner { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; display:block; }
.task-id small { min-width:0; }
.task-id .el-button { flex-shrink:0; padding:3px; width:24px; height:24px; min-height:24px; }
.task-result-count { display:block; font-size:12px; }
@media(max-width:1350px) { .task-filters { align-items:stretch; gap:12px; } .task-filters>.el-radio-group { width:100%; } .task-search-controls { justify-content:flex-start; width:100%; } .task-search-controls .el-input { max-width:340px; } }
</style>
