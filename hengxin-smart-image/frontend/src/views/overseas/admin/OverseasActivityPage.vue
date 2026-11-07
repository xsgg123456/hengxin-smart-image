<template>
  <div>
    <p class="hx-footnote">{{ allMembers ? '人员范围：海外全员' : '人员范围：当前角色可见任务' }} · 历史未记录操作者的作业仅在全部执行记录显示，不计入个人调用次数。</p>
    <ElCard class="art-card hx-section" shadow="never">
      <div class="execution-strip"><span>执行概况</span><ElButton v-for="item in liveStates" :key="item.key" :aria-label="`查看${item.label}记录`" text :class="{ selected: view === 'jobs' && status === item.key }" @click="showStatus(item.key)"><span class="status-dot" :class="item.key" />{{ item.label }} <strong>{{ totals?.[item.key] ?? '—' }}</strong></ElButton><small>{{ allMembers ? '海外全员' : '可见任务' }} · 全部时间，点击状态查看记录</small></div>
    </ElCard>
    <ElCard class="art-card hx-section hx-admin-table-card activity-card" shadow="never">
      <div class="activity-top"><ElRadioGroup v-model="view" aria-label="统计视图"><ElRadioButton value="people">按人员统计</ElRadioButton><ElRadioButton value="jobs">执行记录</ElRadioButton></ElRadioGroup><ElButton class="light-neutral" :loading="loading" @click="refresh">刷新数据</ElButton></div>
      <div class="activity-filters">
        <label><span>执行操作者</span><ElSelect v-model="member" clearable filterable placeholder="全部人员" aria-label="执行操作者" :loading="operatorsLoading"><ElOption v-for="person in operators" :key="person.id" :label="person.name" :value="person.id" /></ElSelect></label>
        <label class="date-filter"><span>统计时间</span><ElDatePicker v-model="dates" type="daterange" start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" range-separator="至" :shortcuts="shortcuts" /></label>
        <label v-if="view === 'jobs'"><span>执行状态</span><ElSelect v-model="status" clearable placeholder="全部状态" aria-label="执行状态"><ElOption v-for="(label, key) in statuses" :key="key" :label="label" :value="key" /></ElSelect></label>
        <label v-if="view === 'jobs'" class="keyword-filter"><span>任务</span><ElInput v-model="keyword" clearable placeholder="搜索任务名称或 ID" aria-label="搜索执行任务" /></label>
        <ElButton class="light-neutral" @click="reset">重置筛选</ElButton>
      </div>
      <div v-if="operatorsError" class="hx-gap"><ElAlert :title="operatorsError" type="error" :closable="false" /><ElButton :loading="operatorsLoading" @click="loadOperators">重试人员列表</ElButton></div>
      <p class="scope-line">{{ member ? operators.find(person => person.id === member)?.name || '已选执行操作者' : allMembers ? '海外全员' : '当前角色可见范围' }} · {{ dates?.length ? dates.join(' 至 ') : '全部时间' }}<span v-if="view === 'people'"> · 点击人员查看执行记录</span><ElButton v-if="view === 'jobs' && member" text type="primary" @click="view = 'people'">返回人员统计</ElButton></p>
      <ElAlert v-if="error" :title="error" type="error" :closable="false" class="hx-gap"><ElButton :loading="loading" @click="load">重新加载</ElButton></ElAlert>
      <template v-else>
        <ArtTable v-if="view === 'people'" :data="people" :columns="peopleColumns" :loading="loading" height="auto" :show-table-header="false" :show-pagination="false" empty-height="260px" empty-text="暂无匹配的调用记录，请调整人员或统计时间">
          <template #name="{ row }"><ElButton text type="primary" @click="showMember(row.id)">{{ row.name }}</ElButton></template><template #lastCall="{ row }">{{ formatBeijingTime(row.lastCall) }}</template><template #action="{ row }"><ElButton text type="primary" @click="showMember(row.id)">查看记录</ElButton></template>
        </ArtTable>
        <ArtTable v-else :data="jobs" :columns="jobColumns" :loading="loading" height="auto" :show-table-header="false" :show-pagination="false" empty-height="260px" empty-text="暂无匹配的执行记录，请调整筛选条件">
          <template #operatorName="{ row }">{{ row.operatorName || '未记录' }}</template><template #status="{ row }"><ElTag :type="row.status === 'failed' ? 'danger' : row.status === 'succeeded' ? 'success' : 'primary'">{{ statuses[row.status] || row.status }}</ElTag></template><template #startedAt="{ row }">{{ formatBeijingTime(row.startedAt, '尚未开始') }}</template><template #duration="{ row }">{{ duration(row) }}</template><template #action="{ row }"><ElButton text type="primary" @click="selected = row">查看详情</ElButton></template>
        </ArtTable>
        <div class="activity-pagination"><span>{{ view === 'people' ? `共 ${people.length} 人 · 调用 ${sumCalls} 次 · 生成 ${sumImages} 张图片` : `共 ${total} 条记录 · 每页 20 条` }}</span><ElPagination v-if="view === 'jobs'" :current-page="page" :page-size="20" :total="total" layout="prev, pager, next" :disabled="loading" @current-change="page = $event" /></div>
        <p class="hx-footnote">调用次数按用户成功发起的请求统计；排队、失败和发起后取消均计入，同一请求重复投递不重复计数。历史未记录或已删除的数据无法完整统计。</p>
      </template>
    </ElCard>
    <ElDrawer :model-value="!!selected" title="执行详情" size="min(560px, 100vw)" @close="selected = null"><template v-if="selected"><h2 class="detail-title">{{ selected.taskName }}</h2><ElDescriptions :column="1" border><ElDescriptionsItem label="执行操作者">{{ selected.operatorName || '未记录' }}</ElDescriptionsItem><ElDescriptionsItem label="状态">{{ statuses[selected.status] || selected.status }}</ElDescriptionsItem><ElDescriptionsItem label="作业 ID">{{ selected.id }}</ElDescriptionsItem><ElDescriptionsItem label="发起时间">{{ formatBeijingTime(selected.createdAt) }}</ElDescriptionsItem><ElDescriptionsItem label="开始时间">{{ formatBeijingTime(selected.startedAt, '尚未开始') }}</ElDescriptionsItem><ElDescriptionsItem label="结束时间">{{ formatBeijingTime(selected.completedAt, '尚未结束') }}</ElDescriptionsItem><ElDescriptionsItem label="耗时">{{ duration(selected) }}</ElDescriptionsItem><ElDescriptionsItem label="执行尝试次数">{{ selected.executionCount }}</ElDescriptionsItem><ElDescriptionsItem label="生成图片">{{ selected.imageCount }}</ElDescriptionsItem></ElDescriptions><ElAlert v-if="selected.error" class="hx-gap" :title="selected.error" type="warning" :closable="false" /></template></ElDrawer>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import { managementError, type Job, type ManagementApi, type ManagementQuery, type Operator, type PersonUsage, type Usage } from '@/api/overseas/management'
import { formatBeijingTime } from '@/utils/beijing-time'
const props = defineProps<{ api: ManagementApi; allMembers?: boolean }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const view = ref('people'), member = ref(''), status = ref(''), keyword = ref(''), dates = ref<string[] | null>(null), page = ref(1)
const jobs = ref<Job[]>([]), people = ref<PersonUsage[]>([]), totals = ref<Usage | null>(null), total = ref(0), selected = ref<Job | null>(null)
const loading = ref(false), error = ref(''), operators = ref<Operator[]>([]), operatorsLoading = ref(false), operatorsError = ref('')
const statuses: Record<string,string> = { queued: '排队中', running: '执行中', collecting: '收集产物', cancelling: '取消中', uncertain: '待核实', succeeded: '成功', failed: '失败', cancelled: '已取消' }
const liveStates = [{ key: 'queued' as const, label: '排队中' }, { key: 'running' as const, label: '执行中' }, { key: 'failed' as const, label: '失败' }, { key: 'uncertain' as const, label: '待核实' }]
const shortcuts = [{ text: '最近 7 天', value: () => { const [y, m, d] = formatBeijingTime(new Date()).slice(0, 10).split('-').map(Number); const end = new Date(y, m - 1, d); const start = new Date(y, m - 1, d - 6); return [start, end] } }]
const peopleColumns = [{ prop: 'name', label: '用户', minWidth: 150, useSlot: true }, { prop: 'calls', label: '调用次数', minWidth: 120 }, { prop: 'images', label: '生成图片数', minWidth: 120 }, { prop: 'lastCall', label: '最近调用时间', minWidth: 180, useSlot: true }, { prop: 'action', label: '操作', width: 120, useSlot: true }]
const jobColumns = [{ prop: 'taskName', label: '任务名称', minWidth: 240 }, { prop: 'operatorName', label: '执行操作者', minWidth: 120, useSlot: true }, { prop: 'status', label: '状态', minWidth: 100, useSlot: true }, { prop: 'startedAt', label: '开始时间', minWidth: 170, useSlot: true }, { prop: 'duration', label: '耗时', width: 100, useSlot: true }, { prop: 'action', label: '操作', width: 110, useSlot: true }]
const sumCalls = computed(() => people.value.reduce((sum, person) => sum + person.calls, 0)), sumImages = computed(() => people.value.reduce((sum, person) => sum + person.images, 0))
let active = true, generation = 0, operatorGeneration = 0, timer: ReturnType<typeof setTimeout> | undefined
function baseQuery(): ManagementQuery { return { memberId: '', from: '', to: '', taskId: '', kind: '', status: '', page: 1, pageSize: 20 } }
function periodQuery(): ManagementQuery {
  const q = baseQuery(); q.memberId = member.value
  if (dates.value?.length === 2) {
    q.from = `${dates.value[0]}T00:00:00+08:00`
    q.before = new Date(Date.parse(`${dates.value[1]}T00:00:00+08:00`) + 86400000).toISOString()
  }
  return q
}
async function load() {
  const current = ++generation; loading.value = true; error.value = ''; jobs.value = []; people.value = []; total.value = 0; selected.value = null
  const period = periodQuery(), query = { ...period, page: page.value, search: keyword.value.trim(),
    ...(status.value === 'collecting' || status.value === 'cancelling' ? { status: status.value } : { statusGroup: status.value }) }
  try {
    const [summary, persons, records] = await Promise.all([props.api.usage(baseQuery()), props.api.people(period), props.api.jobs(query)])
    if (active && current === generation) { totals.value = summary; people.value = persons.items; jobs.value = records.items; total.value = records.total }
  } catch (reason) { if (active && current === generation) { totals.value = null; error.value = managementError(reason); emit('failure', reason) } }
  finally { if (active && current === generation) loading.value = false }
}
async function loadOperators() {
  const current = ++operatorGeneration; operatorsLoading.value = true; operatorsError.value = ''
  try { const value = await props.api.operators(); if (active && current === operatorGeneration) operators.value = value.items }
  catch (reason) { if (active && current === operatorGeneration) { operators.value = []; operatorsError.value = managementError(reason); emit('failure', reason) } }
  finally { if (active && current === operatorGeneration) operatorsLoading.value = false }
}
function filter() { if (page.value === 1) void load(); else page.value = 1 }
function showMember(id: string) { member.value = id; view.value = 'jobs'; status.value = ''; keyword.value = ''; page.value = 1 }
function showStatus(value: string) { member.value = ''; dates.value = null; keyword.value = ''; status.value = value; view.value = 'jobs'; page.value = 1 }
function reset() { member.value = ''; dates.value = null; status.value = ''; keyword.value = ''; page.value = 1 }
function refresh() { void loadOperators(); void load() }
function duration(job: Job) {
  if (job.completedAt && job.startedAt) return `${Math.max(0, Math.round((Date.parse(job.completedAt) - Date.parse(job.startedAt)) / 60000))} 分钟`
  if (['succeeded', 'failed', 'cancelled'].includes(job.status)) return job.startedAt ? '耗时未知' : '未执行'
  return job.status === 'queued' ? '尚未开始' : job.status === 'uncertain' ? '待核实' : '进行中'
}
watch([member, dates, status, view], filter)
watch(keyword, () => { ++generation; jobs.value = []; total.value = 0; clearTimeout(timer); timer = setTimeout(filter, 250) })
watch(page, load)
onMounted(() => { void load(); void loadOperators() })
onUnmounted(() => { active = false; ++generation; ++operatorGeneration; clearTimeout(timer); jobs.value = []; people.value = []; operators.value = []; totals.value = null; selected.value = null })
</script>
<style scoped>
.activity-card { margin-top: 18px; }
:deep(.light-neutral:not(:hover):not(:focus-visible)) { color: var(--el-text-color-regular); border-color: var(--el-border-color); }
.activity-top { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 22px; }
.execution-strip { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; font-size: 14px; }
.execution-strip > .el-button { margin: 0; padding: 8px 12px; }
.execution-strip :deep(.el-button:not(.selected):not(:hover):not(:focus-visible)) { color: var(--el-text-color-regular); }
.execution-strip strong { font-size: 18px; margin-left: 10px; font-variant-numeric: tabular-nums; }
.execution-strip small { margin-left: auto; color: var(--art-gray-600); font-size: 12px; }
.execution-strip .selected { background: var(--el-color-primary-light-9); color: var(--el-color-primary); }
.status-dot { width: 6px; height: 6px; border-radius: 50%; margin-right: 8px; background: var(--el-color-warning); }
.status-dot.running { background: var(--el-color-primary); }.status-dot.failed { background: var(--el-color-danger); }.status-dot.uncertain { background: var(--el-color-info); }
.activity-filters { display: flex; align-items: flex-end; gap: 14px; flex-wrap: wrap; }
.activity-filters > label { display: flex; flex-direction: column; gap: 8px; width: 190px; font-size: 13px; color: var(--art-gray-700); }
.activity-filters > label.date-filter { width: 300px; }.activity-filters > label.date-filter :deep(.el-date-editor) { width: 100%; max-width: 100%; }.activity-filters > label.keyword-filter { width: 250px; }
.scope-line { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12px; color: var(--art-gray-600); margin: 20px 0 8px; }
.activity-pagination { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; padding-top: 18px; font-size: 13px; color: var(--art-gray-600); }
.detail-title { font-size: 18px; margin-bottom: 24px; line-height: 1.7; overflow-wrap: anywhere; }
@media (max-width: 700px) { .activity-filters > label, .activity-filters > label.date-filter, .activity-filters > label.keyword-filter { width: 100%; }.execution-strip { gap: 8px; }.execution-strip small { margin-left: 0; width: 100%; }.activity-top { flex-wrap: wrap; } }
</style>
