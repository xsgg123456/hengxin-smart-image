<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">YOUR CREATIVE PIPELINE</span><h1>任务中心</h1><p>查看全员任务，从提交到成品，每一套图片的进度都在这里。</p></div><ElButton type="primary" @click="router.push('/image-processing/wallpaper')"><ArtSvgIcon icon="ri:add-line" /> 新建套图任务</ElButton></div>
    <div class="hx-stats"><ElCard v-for="s in statCards" :key="s.label" class="art-card" shadow="never"><span>{{ s.label }}</span><strong>{{ s.count ?? '—' }}<small> {{ s.unit }}</small></strong></ElCard></div>
    <ElCard class="art-card hx-section" shadow="never">
      <div class="hx-filter">
        <ElRadioGroup v-model="state" aria-label="任务状态"><ElRadioButton value="all">全部任务</ElRadioButton><ElRadioButton value="排队中">排队中</ElRadioButton><ElRadioButton value="执行中">执行中</ElRadioButton><ElRadioButton value="待查看">待查看</ElRadioButton><ElRadioButton value="部分失败">部分失败</ElRadioButton><ElRadioButton value="失败">失败</ElRadioButton></ElRadioGroup>
        <ElSelect v-model="mode" class="hx-search" aria-label="处理类型"><ElOption value="all" label="全部类型" /><ElOption v-for="(label, key) in labels" :key="key" :value="key" :label="label" /></ElSelect>
        <ElInput v-model="search" clearable placeholder="搜索名称、编号或 SKU" aria-label="搜索任务" class="hx-search"><template #prefix><ArtSvgIcon icon="ri:search-line" /></template></ElInput>
      </div>
      <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon><ElButton text @click="load()">重试加载</ElButton></ElAlert>
      <ElAlert v-if="deleteError" :title="deleteError" type="error" :closable="false" show-icon />
      <ArtTable :data="tasks" :columns="columns" :loading="loading" height="auto" empty-height="340px" :show-table-header="false" row-key="id" empty-text="暂无匹配任务" :show-pagination="false">
        <template #name="{ row }"><div class="hx-table-name"><img v-if="row.images[0]" :src="row.images[0].url" alt="当前结果缩略图" /><div><strong>{{ row.name }}</strong><small>{{ row.id }}{{ row.sku ? ` · ${row.sku}` : '' }}</small></div></div></template>
        <template #mode="{ row }"><ElTag effect="plain">{{ labels[row.mode as Mode] }}</ElTag><ElTag v-if="row.executionSource === 'fixture'" type="warning" size="small">测试任务</ElTag></template>
        <template #state="{ row }"><ElTag :type="['失败', '部分失败'].includes(row.state) ? 'danger' : row.state === '待查看' ? 'success' : 'primary'">{{ row.state }}</ElTag></template>
        <template #progress="{ row }"><ElProgress v-if="row.progress !== null" :percentage="row.progress" :stroke-width="5" /><span v-else>{{ row.state }}</span><small class="hx-muted">{{ row.images.length }} 张已有结果{{ row.outputCount ? ` / ${row.outputCount} 张` : '' }}</small></template>
        <template #time="{ row }">{{ formatTime(row.time) }}</template>
        <template #action="{ row }"><ElButton text type="primary" @click="show(row)">查看详情</ElButton><ElButton text type="danger" :disabled="!!deleting" :loading="deleting === row.id" @click="remove(row)">删除</ElButton></template>
      </ArtTable>
      <ElPagination v-model:current-page="page" class="hx-gap" :page-size="pageSize" :total="total" layout="prev, pager, next, total" :disabled="loading || !!deleting" />
    </ElCard>
    <TaskDetail v-model="detailOpen" :task-id="currentId" :active="active" @changed="load(true)" />
  </div>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteTask } from '@/api/tasks'
import type { Task, Mode } from '@/types/hengxin'
import { labels } from '../model'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import TaskDetail from './TaskDetail.vue'
import { useTaskList } from './use-task-list'
const router = useRouter(), route = useRoute()
const { mode, search, state, tasks, stats, page, total, pageSize, loading, error, active, load } = useTaskList()
const detailOpen = ref(false), currentId = ref(''), deleting = ref(''), deleteError = ref('')
const statCards = computed(() => [{ label: '全部任务', count: stats.value?.total, unit: '个任务' }, { label: '处理中', count: stats.value?.processing, unit: '个任务' }, { label: '等待查看', count: stats.value?.ready, unit: '个任务' }, { label: '已归档成品', count: stats.value?.archived, unit: '套成品' }])
const columns = [{ prop: 'name', label: '任务名称', minWidth: 260, useSlot: true }, { prop: 'mode', label: '处理类型', width: 110, useSlot: true }, { prop: 'state', label: '状态', width: 110, useSlot: true }, { prop: 'progress', label: '生成进度', width: 160, useSlot: true }, { prop: 'time', label: '提交时间', minWidth: 160, useSlot: true }, { prop: 'action', label: '操作', width: 160, useSlot: true }]
function show(task: Task) { currentId.value = task.id; detailOpen.value = true }
watch(() => route.query.taskId ?? route.query.task, id => { if (typeof id === 'string') { currentId.value = id; detailOpen.value = true } }, { immediate: true })
function formatTime(value: string) { return new Date(value).toLocaleString('zh-CN', { hour12: false }) }
async function remove(task: Task) {
  if (deleting.value) return
  deleting.value = task.id
  try {
    try { await ElMessageBox.confirm(`确认删除“${task.name}”？运行中的任务将停止，已归档的图片保留。`, '删除任务', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }) } catch { return }
    await deleteTask(task.id)
    deleteError.value = ''; ElMessage.success('任务已删除')
    if (currentId.value === task.id) detailOpen.value = false
    await load()
  } catch (reason) { deleteError.value = reason instanceof Error ? reason.message : '删除失败，请点击删除重试' }
  finally { deleting.value = '' }
}
</script>
