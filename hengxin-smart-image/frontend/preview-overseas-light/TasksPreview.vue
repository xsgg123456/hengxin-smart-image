<template>
  <template v-if="selected">
    <div class="hx-page"><div class="hx-heading"><div><h1>任务详情</h1><p>{{ selected.name }}</p></div><ElButton @click="selected = null">返回任务列表</ElButton></div><ElCard class="art-card hx-section"><ElDescriptions :column="1" border><ElDescriptionsItem label="任务名称">{{ selected.name }}</ElDescriptionsItem><ElDescriptionsItem label="设计负责人">{{ selected.designer.name }}</ElDescriptionsItem><ElDescriptionsItem label="提交人">{{ selected.createdBy.name }}</ElDescriptionsItem><ElDescriptionsItem label="平台">{{ selected.platform }}</ElDescriptionsItem><ElDescriptionsItem :label="baseline ? '当前节点' : '任务状态'">{{ baseline ? taskStatuses[selected.status] : taskStatusLabel(selected.status) }}<p v-if="!baseline && taskStatusNote(selected.status)" class="hx-footnote">{{ taskStatusNote(selected.status) }}</p></ElDescriptionsItem></ElDescriptions><p class="hx-footnote hx-gap">本次预览展示任务列表交互；返回后保留原筛选条件和页码。</p></ElCard></div>
  </template>
  <component v-else :is="baseline ? OverseasWorkspace : WorkspacePreview" v-model:query="search" v-model:scope="scope" v-model:status="status" :tasks="rows" :allowed="true" :total="filtered.length" :busy="loading" @open="open" @create="explain" @refresh="refresh">
    <template #designer-filter><ElSelect v-model="designer" clearable filterable placeholder="全部设计负责人" aria-label="设计负责人筛选" style="width:200px"><ElOption v-for="person in people" :key="person.id" :label="person.name" :value="person.id" /></ElSelect></template>
    <template #feedback><ElAlert v-if="scene === 'error'" title="任务加载失败，筛选条件已保留。" type="error" :closable="false"><ElButton @click="$emit('retry')">重新加载</ElButton></ElAlert><p v-if="loading" role="status">正在加载任务…</p><div v-if="!baseline" class="task-page-top"><span>共 {{ filtered.length }} 个任务 · 每页 20 条</span><ElPagination v-model:current-page="page" :page-size="20" :total="filtered.length" layout="prev, pager, next" :disabled="loading" /></div></template>
    <template #action><ElButton text type="danger" @click="explain">删除</ElButton></template>
    <template #pagination><div class="light-pagination"><span v-if="!baseline">{{ filtered.length ? `${(page - 1) * 20 + 1}–${Math.min(page * 20, filtered.length)}` : '0' }} / {{ filtered.length }} 条</span><ElPagination v-model:current-page="page" :page-size="20" :total="filtered.length" layout="prev, pager, next" :disabled="loading" /></div></template>
  </component>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import OverseasWorkspace from '@/views/overseas/OverseasWorkspace.vue'
import WorkspacePreview from './WorkspacePreview.vue'
import { taskStatuses, type TaskSummary } from '@/api/overseas/tasks'
import { tasks, people } from './data'
import { taskGroup, taskStatusLabel, taskStatusNote } from './task-status'
const props = defineProps<{ baseline: boolean; scene: string }>(), emit = defineEmits<{ retry: [] }>()
const search = ref(''), scope = ref('all'), status = ref(''), designer = ref(''), page = ref(1), refreshing = ref(false), selected = ref<TaskSummary | null>(null)
const loading = computed(() => props.scene === 'loading' || refreshing.value)
const filtered = computed(() => props.scene !== 'normal' ? [] : tasks.filter(t =>
  (scope.value === 'all' || t.createdBy.id === 'zhang' || t.designer.id === 'zhang') && (!status.value || (props.baseline ? t.status === status.value : taskGroup(t.status) === status.value))
  && (props.baseline || !designer.value || t.designer.id === designer.value)
  && (!search.value.trim() || [t.name, t.productName, t.brand, t.id, ...t.skus.map(s => s.code)].join(' ').toLowerCase().includes(search.value.trim().toLowerCase()))))
const rows = computed(() => filtered.value.slice((page.value - 1) * 20, page.value * 20))
watch([search, scope, status, designer, () => props.baseline, () => props.scene], () => { page.value = 1 })
watch(() => props.baseline, () => { status.value = ''; page.value = 1 })
function open(id: string) { selected.value = tasks.find(t => t.id === id) || null }
function explain() { ElMessage.info('当前为列表交互预览；创建和删除不会修改真实任务。') }
async function refresh() { refreshing.value = true; await new Promise(resolve => setTimeout(resolve, 400)); refreshing.value = false; emit('retry') }
</script>

