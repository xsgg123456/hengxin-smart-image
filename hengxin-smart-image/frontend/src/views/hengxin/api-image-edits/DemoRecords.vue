<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">API IMAGE HISTORY</span><h1>换图记录</h1><p>每张原图的进度单独记录，成功结果随时查看。</p></div><ElButton type="primary" @click="router.push('/api-image-edits/create')"><ArtSvgIcon icon="ri:add-line" /> 新建换图</ElButton></div>
    <PreviewNotice />
    <div class="demo-scenes"><ElTag type="info">仅演示</ElTag><span>打开示例：</span><ElButton size="small" @click="run('retry')">11 张分批并行</ElButton><ElButton size="small" @click="run('success')">全部成功</ElButton><ElButton size="small" @click="run('partial')">重试耗尽</ElButton><ElButton size="small" @click="versionExample">三版对比与恢复</ElButton><small>示例记录可重复创建，进度自动更新</small></div>
    <div class="hx-stats"><ElCard v-for="stat in stats" :key="stat.label" class="art-card" shadow="never"><span>{{ stat.label }}</span><strong>{{ stat.count }}<small> {{ stat.unit }}</small></strong></ElCard></div>
    <ElCard class="art-card hx-section" shadow="never">
      <div class="hx-filter"><ElSelect v-model="filter" aria-label="换图状态" style="width:160px"><ElOption v-for="label in ['全部', '处理中', '全部成功', '部分失败', '全部失败']" :key="label" :label="label === '全部' ? '全部状态' : label" :value="label" /></ElSelect><ElInput v-model="search" aria-label="搜索换图记录" maxlength="60" placeholder="搜索任务名称或编号" class="hx-search" clearable /><ElButton :loading="refreshing" @click="refresh">刷新</ElButton></div>
      <ArtTable :data="tasks" :columns="columns" :loading="false" :cell-style="{ padding: '5px 0' }" height="auto" :show-table-header="false" :show-pagination="false" empty-height="300px" :empty-text="search || filter !== '全部' ? '没有匹配的记录，请调整筛选或搜索内容' : '暂无换图记录，点击右上角新建换图'" row-key="id">
        <template #name="{ row }"><div class="hx-table-name demo-task-name"><div class="demo-thumb"><PicturePreview v-if="row.items[0]" :picture="row.items[0].result || row.items[0].source" title="套图预览" /></div><div><strong>{{ row.name }}</strong><small>{{ row.id }}</small></div></div></template>
        <template #status="{ row }"><ElTag :type="taskState(row) === '全部成功' ? 'success' : taskState(row).includes('失败') ? 'danger' : 'primary'">{{ taskState(row) }}</ElTag></template>
        <template #progress="{ row }"><span>{{ row.items.filter((item: EditItem) => item.state === '成功').length }} / {{ row.items.length }} 张已出图</span><p class="hx-footnote">{{ revisionSummary(row) || `第 ${batchInfo(row).current}/${batchInfo(row).total} 批 · ${batchInfo(row).running} 张处理中` }}</p></template>
        <template #operator="{ row }"><span class="demo-operator">{{ row.operator || '演示操作人' }}</span></template>
        <template #created="{ row }"><span :title="row.created">{{ friendlyTime(row.created) }}</span></template>
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
import PicturePreview from '../components/PicturePreview.vue'
import { preview, taskState, ensureExamples, startScenario, startVersionExample, batchInfo, type Scenario, type EditItem, type EditTask } from './preview-state'
ensureExamples()
const router = useRouter(), route = useRoute()
const filter = ref('全部'), search = ref(''), selectedId = ref(''), open = ref(false)
const refreshing = ref(false)
const selected = computed(() => preview.tasks.find(task => task.id === selectedId.value))
const tasks = computed(() => preview.tasks.filter(task => (filter.value === '全部' || taskState(task) === filter.value || (filter.value === '处理中' && taskState(task) === '排队中')) && `${task.name} ${task.id}`.toLowerCase().includes(search.value.trim().toLowerCase())))
const stats = computed(() => [
  { label: '全部换图任务', count: preview.tasks.length, unit: '套' },
  { label: '排队 / 处理中', count: preview.tasks.filter(task => ['排队中', '处理中'].includes(taskState(task))).length, unit: '套' },
  { label: '已成功图片', count: preview.tasks.reduce((sum, task) => sum + task.items.filter(item => item.state === '成功').length, 0), unit: '张' },
  { label: '失败待处理', count: preview.tasks.reduce((sum, task) => sum + task.items.filter(item => item.state === '失败' || item.revision?.state === '失败').length, 0), unit: '张' }
])
const columns = [
  { prop: 'name', label: '任务', useSlot: true, minWidth: 235 },
  { prop: 'status', label: '状态', useSlot: true, width: 100 },
  { prop: 'progress', label: '图片进度', useSlot: true, minWidth: 150 },
  { prop: 'operator', label: '操作人', useSlot: true, width: 115 },
  { prop: 'created', label: '创建时间', useSlot: true, minWidth: 120 },
  { prop: 'action', label: '操作', useSlot: true, width: 150 }
]
function revisionSummary(task: EditTask) { const count = task.items.filter(item => item.revision && ['处理中', '等待重试'].includes(item.revision.state)).length; const failed = task.items.filter(item => item.revision?.state === '失败').length; return count ? `${count} 张修改中 · 旧图保留` : failed ? `${failed} 张修改失败 · 旧图保留` : '' }
function versionExample() { filter.value = '全部'; search.value = ''; show(startVersionExample()) }
function run(scenario: Scenario) { filter.value = '全部'; search.value = ''; show(startScenario(scenario)) }
async function refresh() { if (refreshing.value) return; refreshing.value = true; await new Promise(resolve => setTimeout(resolve, 350)); refreshing.value = false }
function friendlyTime(value: string) { const date = new Date(value); if (Number.isNaN(date.getTime())) return value; const time = date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }); return date.toDateString() === new Date().toDateString() ? `今天 ${time}` : `${date.getMonth() + 1}月${date.getDate()}日 ${time}` }
function show(id: string) { selectedId.value = id; open.value = true }
watch(() => route.query.task, value => { if (typeof value === 'string') show(value) }, { immediate: true })
async function remove(task: EditTask) {
  try { await ElMessageBox.confirm('删除此演示记录及其中的示例结果？', '删除换图记录', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }) }
  catch { return }
  preview.tasks = preview.tasks.filter(item => item.id !== task.id)
}
</script>
<style scoped>
.demo-scenes { display:flex; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:18px; color:var(--art-gray-600); }
.demo-scenes .el-button + .el-button { margin-left:0; }
.demo-scenes small { margin-left:auto; }
.demo-thumb { width:52px; height:52px; flex:none; }
.demo-operator { white-space:nowrap; }
.demo-task-name { min-width:0; gap:10px; }
.demo-task-name > div:last-child { min-width:0; }
.demo-task-name strong, .demo-task-name small { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
:deep(.el-table .el-table__cell) { padding:9px 0; }
.hx-footnote { margin:4px 0 0; line-height:1.4; }
.hx-filter { flex-wrap:wrap; }
</style>
