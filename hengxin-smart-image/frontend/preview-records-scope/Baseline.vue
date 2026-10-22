<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">API IMAGE HISTORY</span><h1>换图记录</h1><p>每张原图的进度单独记录，成功结果随时查看。</p></div><ElButton type="primary" @click="router.push('/api-image-edits/create')"><ArtSvgIcon icon="ri:add-line" /> 新建换图</ElButton></div>
    <ElAlert v-if="error || actionError" :title="error || actionError" type="error" :closable="false"><ElButton text @click="refresh()">重新加载</ElButton></ElAlert>
    <div class="hx-stats"><ElCard v-for="stat in stats" :key="stat.label" class="art-card" shadow="never"><span>{{ stat.label }}</span><strong>{{ stat.count }}<small> {{ stat.unit }}</small></strong></ElCard></div>
    <ElCard class="art-card hx-section" shadow="never">
      <div class="hx-filter"><ElSelect v-model="filter" aria-label="换图状态" style="width:160px"><ElOption label="全部状态" value="" /><ElOption v-for="(label, value) in taskLabels" :key="value" :label="label" :value="value" /></ElSelect><ElInput v-model="search" aria-label="搜索换图记录" maxlength="60" placeholder="搜索任务名称或编号" class="hx-search" clearable /><ElButton :loading="loading" @click="refresh()">刷新</ElButton></div>
      <ArtTable :data="tasks" :columns="columns" :loading="loading" height="auto" :show-table-header="false" :show-pagination="false" empty-height="300px" :empty-text="error ? '列表加载失败，请重试' : '暂无换图记录'" row-key="id">
        <template #name="{ row }"><div class="hx-table-name"><div class="record-thumb"><PicturePreview v-if="row.cover?.url" :picture="row.cover" title="原图缩略图" /></div><div><strong>{{ row.name }}</strong><small>{{ row.id }}</small></div></div></template>
        <template #status="{ row }"><ElTag :type="row.status === 'succeeded' ? 'success' : ['failed', 'partial_failed'].includes(row.status) ? 'info' : 'primary'">{{ taskLabels[row.status as ApiTaskState] }}</ElTag><CliActivityTag :state="row.cliActivity" /></template>
        <template #progress="{ row }"><span>{{ row.counts.success }} / {{ row.counts.total }} 张已完成</span><p class="hx-footnote">{{ row.counts.failed }} 张未完成</p></template>
        <template #operator="{ row }"><span>{{ row.operator || '未记录' }}</span></template>
        <template #created="{ row }"><span>{{ friendlyTime(row.created) }}</span></template>
        <template #action="{ row }"><ElButton text type="primary" :disabled="row.deletionState === 'deleting'" @click="show(row.id)">查看详情</ElButton><ElTooltip :content="deleteBlockedReason(row) || row.deletionError || '永久删除任务及关联资料'" placement="top"><span><ElButton text type="danger" :disabled="busy || !canDeleteTask(row)" @click="remove()">{{ row.deletionState === 'deleting' ? '删除中…' : row.deletionState === 'failed' ? '重试删除' : '删除' }}</ElButton></span></ElTooltip><p v-if="row.deletionState === 'failed'" class="hx-footnote deletion-error">删除未完成，请重试</p></template>
      </ArtTable>
      <ElPagination v-if="total" v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[20, 50, 100]" :total="total" layout="total, sizes, prev, pager, next" class="hx-gap" />
    </ElCard>
    <PreviewDetail v-model="selected" />
  </div>
</template><script setup lang="ts">
// 基准模板和样式取自正式 RealRecords.vue，仅数据与动作替换为隔离示例。
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { taskLabels, isApiTaskPending, canDeleteTask, deleteBlockedReason, type ApiTaskState } from '@/types/api-image-edits'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import CliActivityTag from '@/views/hengxin/api-image-edits/CliActivityTag.vue'
import PicturePreview from '@/views/hengxin/components/PicturePreview.vue'
import { formatBeijingTime as friendlyTime } from '@/utils/beijing-time'
import PreviewDetail from './PreviewDetail.vue'
import { usePreviewRecords } from './state'
const router = useRouter()
const { tasks, total, page, pageSize, search, filter, selected, loading, error, refresh } = usePreviewRecords('all')
const actionError = '', busy = false
const stats = computed(() => [
  { label: '当前筛选任务', count: total.value, unit: '套' },
  { label: '本页排队 / 处理中', count: tasks.value.filter(isApiTaskPending).length, unit: '套' },
  { label: '本页成功图片', count: tasks.value.reduce((n, t) => n + t.counts.success, 0), unit: '张' },
  { label: '本页未完成图片', count: tasks.value.reduce((n, t) => n + t.counts.failed, 0), unit: '张' }
])
const columns = [{ prop: 'name', label: '任务', useSlot: true, minWidth: 260 }, { prop: 'status', label: '状态', useSlot: true, width: 120 }, { prop: 'progress', label: '图片进度', useSlot: true, minWidth: 165 }, { prop: 'operator', label: '操作人', useSlot: true, width: 115 }, { prop: 'created', label: '创建时间', useSlot: true, minWidth: 120 }, { prop: 'action', label: '操作', useSlot: true, width: 175 }]
function show(id: string) { selected.value = tasks.value.find(t => t.id === id) }
function remove() { ElMessage.info('基准页面仅供视觉对照，请在新版预览体验示例删除。') }
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
</style>
