<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">API IMAGE HISTORY</span><h1>换图记录</h1><p>每张原图的进度单独记录，成功结果随时查看。</p></div><ElButton type="primary" @click="router.push('/api-image-edits/create')"><ArtSvgIcon icon="ri:add-line" /> 新建换图</ElButton></div>
    <ElTabs v-model="scope" class="scope-tabs" aria-label="任务查看范围"><ElTabPane label="我的任务" name="mine" /><ElTabPane label="全部任务" name="all" /></ElTabs>
    <ElAlert v-if="error" :title="error" type="error" :closable="false"><ElButton text @click="scene = 'normal'; refresh()">重新加载</ElButton></ElAlert>
    <div class="hx-stats"><ElCard v-for="stat in stats" :key="stat.label" class="art-card" shadow="never"><span>{{ stat.label }}</span><strong>{{ stat.count }}<small> {{ stat.unit }}</small></strong></ElCard></div>
    <ElCard class="art-card hx-section" shadow="never">
      <div class="hx-filter records-filter">
        <div v-if="scope === 'all'" class="filter-field"><span>创建人</span><ElSelect v-model="creator" aria-label="创建人" placeholder="全部人员" filterable clearable><ElOption label="全部人员" value="" /><ElOption v-for="person in people" :key="person.id" :label="person.name" :value="person.id" /></ElSelect></div>
        <div class="filter-field"><span>状态</span><ElSelect v-model="filter" aria-label="换图状态" placeholder="全部状态"><ElOption label="全部状态" value="" /><ElOption v-for="(label, value) in taskLabels" :key="value" :label="label" :value="value" /></ElSelect></div>
        <div class="filter-field"><span>创建时间</span><ElSelect v-model="period" aria-label="创建时间"><ElOption label="全部时间" value="all" /><ElOption label="今天" value="today" /><ElOption label="近 7 天" value="week" /><ElOption label="近 30 天" value="month" /><ElOption label="自定义" value="custom" /></ElSelect></div>
        <ElInput v-model="search" aria-label="搜索换图记录" maxlength="60" placeholder="搜索任务名称或编号" class="hx-search" clearable><template #prefix><ArtSvgIcon icon="ri:search-line" /></template></ElInput>
        <div class="filter-actions"><ElButton text @click="reset">重置</ElButton><ElButton :loading="loading" @click="refresh">刷新</ElButton></div>
      </div>
      <div v-if="period === 'custom'" class="date-range"><span>日期范围</span><ElDatePicker v-model="dates" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" range-separator="至" :default-value="[new Date(2026, 9, 1), new Date(2026, 9, 22)]" aria-label="自定义日期范围" /><small v-if="!dates">请选择起止日期，当前暂不限制时间</small></div>
      <div class="scope-summary"><span>当前查看：<strong>{{ scopeText }}</strong><span class="summary-count">共 {{ total }} 套任务</span></span><span>按创建时间倒序 · 统计包含全部筛选结果</span></div>
      <ArtTable :data="tasks" :columns="columns" :loading="loading" height="auto" :show-table-header="false" :show-pagination="false" empty-height="240px" :empty-text="hasFilters ? '没有匹配的记录，请调整筛选条件' : scope === 'mine' ? '你还没有创建换图任务' : '暂无换图记录'" row-key="id">
        <template #name="{ row }"><div class="hx-table-name"><div class="record-thumb"><PicturePreview v-if="row.cover?.url" :picture="row.cover" title="原图缩略图" /></div><div><strong>{{ row.name }}</strong><small>{{ row.id }}</small></div></div></template>
        <template #status="{ row }"><ElTag :type="row.status === 'succeeded' ? 'success' : ['failed', 'partial_failed'].includes(row.status) ? 'info' : 'primary'">{{ taskLabels[row.status as ApiTaskState] }}</ElTag></template>
        <template #progress="{ row }"><span>{{ row.counts.success }} / {{ row.counts.total }} 张已完成</span><p class="hx-footnote">{{ row.counts.failed }} 张未完成</p></template>
        <template #operator="{ row }"><span>{{ row.operator }}</span><small v-if="row.creatorId === 'me'" class="me-label">我</small></template>
        <template #created="{ row }"><span>{{ friendlyTime(row.created) }}</span></template>
        <template #action="{ row }"><ElButton text type="primary" @click="selected = row">查看详情</ElButton><ElTooltip :content="deleteBlockedReason(row) || '删除此示例任务'" placement="top"><span><ElButton text type="danger" :disabled="!canDeleteTask(row)" @click="remove(row)">删除</ElButton></span></ElTooltip></template>
      </ArtTable>
      <div v-if="!total && !loading" class="empty-actions"><ElButton v-if="hasFilters" @click="reset">清空筛选</ElButton><template v-else><ElButton type="primary" @click="router.push('/api-image-edits/create')">新建换图</ElButton><ElButton v-if="scope === 'mine'" @click="scene = 'normal'; scope = 'all'">查看全部任务</ElButton></template></div>
      <ElPagination v-if="total" v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[20, 50, 100]" :total="total" layout="total, sizes, prev, pager, next" class="hx-gap" />
    </ElCard>
    <div class="preview-tools"><span>仅预览 · 当前身份：张三 · 示例日期：2026-10-22</span><ElSelect v-model="scene" aria-label="预览场景" size="small"><ElOption label="正常列表" value="normal" /><ElOption label="空列表" value="empty" /><ElOption label="刷新失败" value="error" /></ElSelect></div>
    <PreviewDetail v-model="selected" />
  </div>
</template>
<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import ArtSvgIcon from '@/components/core/base/art-svg-icon/index.vue'
import PicturePreview from '@/views/hengxin/components/PicturePreview.vue'
import { taskLabels, canDeleteTask, deleteBlockedReason, type ApiTaskState } from '@/types/api-image-edits'
import { formatBeijingTime as friendlyTime } from '@/utils/beijing-time'
import { people, usePreviewRecords, type PreviewTask } from './state'
import PreviewDetail from './PreviewDetail.vue'
const router = useRouter()
const { records, scope, creator, filter, search, period, dates, page, pageSize, loading, error, selected, scene, total, tasks, stats, scopeText, hasFilters, refresh, reset } = usePreviewRecords()
const columns = [{ prop: 'name', label: '任务', useSlot: true, minWidth: 260 }, { prop: 'status', label: '状态', useSlot: true, width: 120 }, { prop: 'progress', label: '图片进度', useSlot: true, minWidth: 165 }, { prop: 'operator', label: '创建人', useSlot: true, width: 115 }, { prop: 'created', label: '创建时间', useSlot: true, minWidth: 160 }, { prop: 'action', label: '操作', useSlot: true, width: 175 }]
async function remove(task: PreviewTask) {
  if (!canDeleteTask(task)) return
  try { await ElMessageBox.confirm(`删除示例任务“${task.name}”？仅影响当前预览，刷新页面即可恢复。`, '删除换图任务', { type: 'warning', confirmButtonText: '删除示例', cancelButtonText: '取消' }) } catch { return }
  records.value = records.value.filter(t => t.id !== task.id)
  ElMessage.success('已删除示例任务')
}
</script>
<style scoped>
.record-thumb { width:52px; height:52px; flex:none; }
.hx-table-name { min-width:0; gap:10px; }
.hx-table-name > div:last-child { min-width:0; }
.hx-table-name strong, .hx-table-name small { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
:deep(.el-table .el-table__cell) { padding:9px 0; }
.hx-footnote { margin:4px 0 0; line-height:1.4; }
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
.preview-tools { display:flex; align-items:center; justify-content:flex-end; gap:12px; flex-wrap:wrap; font-size:11px; color:var(--art-gray-600); margin-top:18px; }
.preview-tools .el-select { width:126px; }
@media(max-width:1100px) { .records-filter .hx-search { max-width:none; flex:1; min-width:190px; } }
@media(max-width:640px) { .filter-field { width:100%; justify-content:space-between; } .filter-field .el-select { width:calc(100% - 72px); } .hx-stats { grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; } .hx-stats :deep(.el-card__body) { padding:16px; } .scope-summary { line-height:1.8; } :deep(.el-pagination) { flex-wrap:wrap; row-gap:10px; } .hx-heading { gap:10px; } .hx-heading > .el-button { padding:10px; } }
</style>
