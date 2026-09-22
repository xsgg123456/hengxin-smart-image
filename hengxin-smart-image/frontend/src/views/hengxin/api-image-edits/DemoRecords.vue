<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">API IMAGE HISTORY</span><h1>换图记录</h1><p>每张原图的进度单独记录，成功结果随时查看。</p></div><ElButton type="primary" @click="router.push('/api-image-edits/create')"><ArtSvgIcon icon="ri:add-line" /> 新建换图</ElButton></div>
    <PreviewNotice />
    <div class="hx-stats"><ElCard v-for="stat in stats" :key="stat.label" class="art-card" shadow="never"><span>{{ stat.label }}</span><strong>{{ stat.count }}<small> {{ stat.unit }}</small></strong></ElCard></div>
    <ElCard class="art-card hx-section" shadow="never">
      <div class="hx-filter"><ElRadioGroup v-model="filter" aria-label="换图状态"><ElRadioButton v-for="label in ['全部', '处理中', '全部成功', '部分失败']" :key="label" :value="label">{{ label }}</ElRadioButton></ElRadioGroup><ElInput v-model="search" aria-label="搜索换图记录" placeholder="搜索任务名称或编号" class="hx-search" clearable /></div>
      <ArtTable :data="tasks" :columns="columns" :loading="false" height="auto" :show-table-header="false" :show-pagination="false" empty-height="300px" empty-text="暂无换图记录，点击右上角新建换图" row-key="id">
        <template #name="{ row }"><div class="hx-table-name"><img :src="row.items[0]?.source.url" alt="原图缩略图" /><div><strong>{{ row.name }}</strong><small>{{ row.id }}</small></div></div></template>
        <template #status="{ row }"><ElTag :type="taskState(row) === '全部成功' ? 'success' : taskState(row).includes('失败') ? 'danger' : 'primary'">{{ taskState(row) }}</ElTag></template>
        <template #progress="{ row }"><span>{{ row.items.filter((item: EditItem) => item.state === '成功').length }} / {{ row.items.length }} 张成功</span><p class="hx-footnote">{{ row.items.filter((item: EditItem) => item.state === '失败').length }} 张失败 · 串行处理</p></template>
        <template #action="{ row }"><ElButton text type="primary" @click="show(row.id)">查看详情</ElButton><ElButton text type="danger" :disabled="['排队中', '处理中'].includes(taskState(row))" @click="remove(row)">删除</ElButton></template>
      </ArtTable>
    </ElCard>
    <TaskDetail v-model="open" :task="selected" />
  </div>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import PreviewNotice from './PreviewNotice.vue'
import TaskDetail from './TaskDetail.vue'
import { preview, taskState, type EditItem, type EditTask } from './preview-state'
const router = useRouter(), route = useRoute()
const filter = ref('全部'), search = ref(''), selectedId = ref(''), open = ref(false)
const selected = computed(() => preview.tasks.find(task => task.id === selectedId.value))
const tasks = computed(() => preview.tasks.filter(task => (filter.value === '全部' || taskState(task) === filter.value || (filter.value === '处理中' && taskState(task) === '排队中')) && `${task.name} ${task.id}`.includes(search.value)))
const stats = computed(() => [
  { label: '全部换图任务', count: preview.tasks.length, unit: '套' },
  { label: '排队 / 处理中', count: preview.tasks.filter(task => ['排队中', '处理中'].includes(taskState(task))).length, unit: '套' },
  { label: '已成功图片', count: preview.tasks.reduce((sum, task) => sum + task.items.filter(item => item.state === '成功').length, 0), unit: '张' },
  { label: '失败待处理', count: preview.tasks.reduce((sum, task) => sum + task.items.filter(item => item.state === '失败').length, 0), unit: '张' }
])
const columns = [
  { prop: 'name', label: '任务', useSlot: true, minWidth: 260 },
  { prop: 'status', label: '状态', useSlot: true, width: 120 },
  { prop: 'progress', label: '图片进度', useSlot: true, minWidth: 165 },
  { prop: 'created', label: '创建时间', minWidth: 165 },
  { prop: 'action', label: '操作', useSlot: true, width: 175 }
]
function show(id: string) { selectedId.value = id; open.value = true }
watch(() => route.query.task, value => { if (typeof value === 'string') show(value) }, { immediate: true })
async function remove(task: EditTask) {
  try { await ElMessageBox.confirm('删除此演示记录及其中的示例结果？', '删除换图记录', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }) }
  catch { return }
  preview.tasks = preview.tasks.filter(item => item.id !== task.id)
}
</script>
