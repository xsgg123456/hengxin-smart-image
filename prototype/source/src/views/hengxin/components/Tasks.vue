<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">YOUR CREATIVE PIPELINE</span><h1>任务中心</h1><p>从提交到成品，每一套图片的进度都在这里。</p></div><ElButton type="primary" @click="router.push('/wallpaper/index')"><ArtSvgIcon icon="ri:add-line" /> 新建套图任务</ElButton></div>
    <div class="hx-stats"><ElCard v-for="s in stats" :key="s.label" class="art-card" shadow="never"><span>{{ s.label }}</span><strong>{{ s.count }}<small> 个任务</small></strong></ElCard></div>
    <ElCard class="art-card hx-section" shadow="never"><div class="hx-filter"><ElRadioGroup v-model="status"><ElRadioButton value="全部">全部任务</ElRadioButton><ElRadioButton value="处理中">处理中</ElRadioButton><ElRadioButton value="待查看">待查看</ElRadioButton><ElRadioButton value="失败">异常</ElRadioButton></ElRadioGroup><ElInput v-model="search" clearable placeholder="搜索任务名称或编号" class="hx-search"><template #prefix><ArtSvgIcon icon="ri:search-line" /></template></ElInput></div>
      <ArtTable :data="filtered" :columns="columns" row-key="id" empty-text="没有找到任务，试试其他筛选条件" :show-pagination="false">
        <template #name="{ row }"><div class="hx-table-name"><img :src="row.images[0]?.url" alt="任务缩略图" /><div><strong>{{ row.name }}</strong><small>{{ row.id }}</small></div></div></template>
        <template #mode="{ row }"><ElTag effect="plain">{{ labels[row.mode as Mode] }}</ElTag></template>
        <template #state="{ row }"><ElTag :type="row.state === '失败' ? 'danger' : row.state === '待查看' ? 'success' : 'primary'">{{ row.state }}</ElTag></template>
        <template #progress="{ row }"><ElProgress :percentage="row.progress" :stroke-width="5" /><small class="hx-muted">{{ row.images.length }} 张图片</small></template>
        <template #action="{ row }"><ElButton text type="primary" @click="show(row)">{{ row.state === '待查看' ? '查看结果' : row.state === '失败' ? '查看异常' : '查看进度' }}</ElButton></template>
      </ArtTable>
      <p class="hx-footnote">共 {{ filtered.length }} 个任务 · 当前为本地交互演示数据</p>
    </ElCard>
    <TaskDetail v-model="detailOpen" :task="current" />
  </div>
</template>
<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { db, labels, type Task, type Mode } from '../model'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import TaskDetail from './TaskDetail.vue'
const router = useRouter(), route = useRoute(), search = ref(''), status = ref('全部'), detailOpen = ref(false), current = ref<Task>()
const filtered = computed(() => db.tasks.filter(t => (status.value === '全部' || (status.value === '处理中' ? ['排队中', '执行中'].includes(t.state) : t.state === status.value)) && `${t.name}${t.id}`.toLowerCase().includes(search.value.toLowerCase())))
const stats = computed(() => [{ label: '全部任务', count: db.tasks.length }, { label: '处理中', count: db.tasks.filter(t => ['排队中', '执行中'].includes(t.state)).length }, { label: '等待查看', count: db.tasks.filter(t => t.state === '待查看').length }, { label: '已归档成品', count: db.archives.length }])
const columns = [{ prop: 'name', label: '任务名称', minWidth: 260, useSlot: true }, { prop: 'mode', label: '处理类型', width: 110, useSlot: true }, { prop: 'state', label: '状态', width: 100, useSlot: true }, { prop: 'progress', label: '生成进度', width: 150, useSlot: true }, { prop: 'time', label: '提交时间', minWidth: 130 }, { prop: 'action', label: '操作', width: 110, useSlot: true }]
function show(task: Task) { current.value = task; detailOpen.value = true }
onMounted(() => { const task = db.tasks.find(t => t.id === route.query.task); if (task) show(task) })
</script>
