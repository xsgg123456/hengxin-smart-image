<template>
  <div class="hx-page">
    <div class="hx-heading"><div><h1>{{ baseline ? (oldPage === 'usage' ? '调用统计' : '执行监控') : '调用与执行' }}</h1><p>{{ baseline ? '张帅 · 超级管理员' : '按人员查看使用情况，跟进每一次 Codex 执行。' }}</p></div></div>
    <template v-if="baseline"><ElRadioGroup v-model="oldPage" class="hx-gap"><ElRadioButton value="usage">调用统计</ElRadioButton><ElRadioButton value="monitor">执行监控</ElRadioButton></ElRadioGroup><OverseasLiveActivity :key="oldPage" :page="oldPage" :api="managementApi" all-members /></template>
    <template v-else>
      <ElCard class="art-card hx-section" shadow="never">
        <div class="execution-strip"><span>执行概况</span><ElButton v-for="s in liveStates" :key="s.key" :aria-label="`查看${s.label}记录`" :class="{ 'selected-state': status === s.key && view === 'jobs' }" text @click="showStatus(s.key)"><span class="status-dot" :class="s.key" />{{ s.label }} <strong>{{ scene === 'normal' ? jobs.filter(j => j.status === s.key).length : '—' }}</strong></ElButton><small>海外全员 · 全部时间，点击状态查看记录</small></div>
      </ElCard>
      <ElCard class="art-card hx-section hx-admin-table-card" shadow="never">
        <div class="activity-top"><ElRadioGroup v-model="view" aria-label="统计视图"><ElRadioButton value="people">按人员统计</ElRadioButton><ElRadioButton value="jobs">执行记录</ElRadioButton></ElRadioGroup><ElButton :loading="refreshing" @click="refresh">刷新数据</ElButton></div>
        <div class="light-filters">
          <label><span>执行操作者</span><ElSelect v-model="member" clearable filterable placeholder="全部人员" aria-label="执行操作者"><ElOption v-for="p in people" :key="p.id" :label="p.name" :value="p.id" /></ElSelect></label>
          <label class="date-filter"><span>统计时间</span><ElDatePicker v-model="dates" type="daterange" start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" range-separator="至" :clearable="true" :shortcuts="shortcuts" /></label>
          <label v-if="view === 'jobs'"><span>执行状态</span><ElSelect v-model="status" clearable placeholder="全部状态" aria-label="执行状态"><ElOption v-for="(label, key) in labels" :key="key" :label="label" :value="key" /></ElSelect></label>
          <label v-if="view === 'jobs'" class="keyword-filter"><span>任务</span><ElInput v-model="keyword" clearable placeholder="搜索任务名称或 ID" aria-label="搜索执行任务" /></label>
          <ElButton @click="reset">重置筛选</ElButton>
        </div>
        <p class="scope-line">{{ member ? people.find(p => p.id === member)?.name : '海外全员' }} · {{ dates?.length ? dates.join(' 至 ') : '全部时间' }}<span v-if="view === 'people'"> · 点击人员查看执行记录</span><ElButton v-if="view === 'jobs' && member" text type="primary" @click="view = 'people'">返回人员统计</ElButton></p>
        <ElAlert v-if="scene === 'error'" title="数据加载失败，请重试。已选择的筛选条件会保留。" type="error" :closable="false"><ElButton @click="$emit('retry')">重新加载</ElButton></ElAlert>
        <template v-else>
          <ArtTable v-if="view === 'people'" :data="visiblePeople" :columns="peopleColumns" :loading="loading" height="auto" :show-table-header="false" :show-pagination="false" empty-height="260px" empty-text="暂无匹配的调用记录，请调整人员或统计时间">
            <template #name="{ row }"><ElButton text type="primary" @click="showMember(row.id)">{{ row.name }}</ElButton></template>
            <template #last="{ row }">{{ formatBeijingTime(row.last) }}</template>
            <template #action="{ row }"><ElButton text type="primary" @click="showMember(row.id)">查看记录</ElButton></template>
          </ArtTable>
          <ArtTable v-else :data="visibleJobs" :columns="jobColumns" :loading="loading" height="auto" :show-table-header="false" :show-pagination="false" empty-height="260px" empty-text="暂无匹配的执行记录，请调整筛选条件">
            <template #status="{ row }"><ElTag :type="row.status === 'failed' ? 'danger' : row.status === 'succeeded' ? 'success' : 'primary'">{{ labels[row.status] }}</ElTag></template>
            <template #startedAt="{ row }">{{ formatBeijingTime(row.startedAt, '尚未开始') }}</template>
            <template #duration="{ row }">{{ duration(row) }}</template>
            <template #action="{ row }"><ElButton text type="primary" @click="selected = row">查看详情</ElButton></template>
          </ArtTable>
          <div class="light-pagination"><span>{{ view === 'people' ? `共 ${visiblePeople.length} 人 · 调用 ${sumCalls} 次 · 生成 ${sumImages} 张图片` : `共 ${filtered.length} 条记录 · 每页 20 条` }}</span><ElPagination v-if="view === 'jobs'" v-model:current-page="page" :page-size="20" :total="scene === 'normal' ? filtered.length : 0" layout="prev, pager, next" :disabled="loading" /></div>
          <p class="hx-footnote">按实际发起人统计；成功发起的一轮请求计一次，排队或失败也计入。</p>
        </template>
      </ElCard>
    </template>
    <ElDrawer :model-value="!!selected" title="执行详情" size="min(560px, 100vw)" @close="selected = null"><template v-if="selected"><h2 class="detail-title">{{ selected.taskName }}</h2><ElDescriptions :column="1" border><ElDescriptionsItem label="执行操作者">{{ selected.operatorName }}</ElDescriptionsItem><ElDescriptionsItem label="状态">{{ labels[selected.status] }}</ElDescriptionsItem><ElDescriptionsItem label="作业 ID">{{ selected.id }}</ElDescriptionsItem><ElDescriptionsItem label="开始时间">{{ formatBeijingTime(selected.startedAt, '尚未开始') }}</ElDescriptionsItem><ElDescriptionsItem label="结束时间">{{ formatBeijingTime(selected.completedAt, '尚未结束') }}</ElDescriptionsItem><ElDescriptionsItem label="耗时">{{ duration(selected) }}</ElDescriptionsItem><ElDescriptionsItem label="执行次数">{{ selected.executionCount }}</ElDescriptionsItem><ElDescriptionsItem label="生成图片">{{ selected.imageCount }}</ElDescriptionsItem></ElDescriptions><ElAlert v-if="selected.error" class="hx-gap" :title="selected.error" type="warning" :closable="false" /></template></ElDrawer>
  </div>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import OverseasLiveActivity from '@/views/overseas/admin/OverseasLiveActivity.vue'
import { formatBeijingTime } from '@/utils/beijing-time'
import type { Job } from '@/api/overseas/management'
import { jobs, people, selectJobs, managementApi } from './data'
const props = defineProps<{ baseline: boolean; scene: string }>()
const emit = defineEmits<{ retry: [] }>()
const view = ref('people'), oldPage = ref<'usage' | 'monitor'>('usage'), member = ref(''), status = ref(''), keyword = ref(''), dates = ref<string[] | null>(null), page = ref(1), selected = ref<Job | null>(null), refreshing = ref(false)
const loading = computed(() => props.scene === 'loading' || refreshing.value)
const labels: Record<string, string> = { queued: '排队中', running: '执行中', uncertain: '待核实', succeeded: '成功', failed: '失败', cancelled: '已取消' }
const liveStates = [{ key: 'queued', label: '排队中' }, { key: 'running', label: '执行中' }, { key: 'failed', label: '失败' }, { key: 'uncertain', label: '待核实' }]
const shortcuts = [{ text: '最近 7 天', value: () => [new Date('2026-11-01T00:00:00+08:00'), new Date('2026-11-07T23:59:59+08:00')] }]
const scoped = computed(() => selectJobs({ memberId: member.value, from: dates.value?.[0] ? new Date(dates.value[0] + 'T00:00:00+08:00').toISOString() : '', to: dates.value?.[1] ? new Date(dates.value[1] + 'T23:59:59+08:00').toISOString() : '' }))
const filtered = computed(() => scoped.value.filter(j => (!status.value || j.status === status.value) && (!keyword.value.trim() || (j.taskName + j.taskId).toLowerCase().includes(keyword.value.trim().toLowerCase()))))
const visibleJobs = computed(() => props.scene === 'normal' ? filtered.value.slice((page.value - 1) * 20, page.value * 20) : [])
const visiblePeople = computed(() => props.scene !== 'normal' ? [] : people.map(p => { const rows = scoped.value.filter(j => j.operatorId === p.id); return { ...p, calls: rows.length, images: rows.reduce((n, j) => n + j.imageCount, 0), last: rows[0]?.createdAt, count: rows.length } }).filter(p => p.count).sort((a, b) => b.calls - a.calls))
const sumCalls = computed(() => visiblePeople.value.reduce((n, p) => n + p.calls, 0)), sumImages = computed(() => visiblePeople.value.reduce((n, p) => n + p.images, 0))
const peopleColumns = [{ prop: 'name', label: '用户', minWidth: 150, useSlot: true }, { prop: 'calls', label: '调用次数', minWidth: 120 }, { prop: 'images', label: '生成图片数', minWidth: 120 }, { prop: 'last', label: '最近调用时间', minWidth: 180, useSlot: true }, { prop: 'action', label: '操作', width: 120, useSlot: true }]
const jobColumns = [{ prop: 'taskName', label: '任务名称', minWidth: 240 }, { prop: 'operatorName', label: '执行操作者', minWidth: 120 }, { prop: 'status', label: '状态', minWidth: 100, useSlot: true }, { prop: 'startedAt', label: '开始时间', minWidth: 170, useSlot: true }, { prop: 'duration', label: '耗时', width: 100, useSlot: true }, { prop: 'action', label: '操作', width: 110, useSlot: true }]
function showMember(id: string) { member.value = id; view.value = 'jobs'; status.value = ''; keyword.value = ''; page.value = 1 }
function showStatus(value: string) { member.value = ''; dates.value = null; keyword.value = ''; status.value = value; view.value = 'jobs'; page.value = 1 }
function reset() { member.value = ''; dates.value = null; status.value = ''; keyword.value = ''; page.value = 1 }
function duration(job: Job) { return job.completedAt && job.startedAt ? `${Math.round((Date.parse(job.completedAt) - Date.parse(job.startedAt)) / 60000)} 分钟` : job.status === 'queued' ? '尚未开始' : job.status === 'uncertain' ? '待核实' : '进行中' }
async function refresh() { refreshing.value = true; await new Promise(resolve => setTimeout(resolve, 400)); refreshing.value = false; emit('retry') }
watch([member, dates, status, keyword, view], () => { page.value = 1 })
</script>

