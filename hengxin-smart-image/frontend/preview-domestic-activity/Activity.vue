<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">EXECUTION INSIGHTS</span><h1>调用与执行</h1><p>查看人员使用情况，跟进当前执行进度。</p></div><ElButton :loading="busy" @click="refresh">刷新数据</ElButton></div>
    <ElCard class="art-card hx-section" shadow="never">
      <div class="execution-strip"><span>当前执行</span><ElButton v-for="item in liveStates" :key="item.key" :aria-label="`查看${item.label}记录`" text :class="{ selected: view === 'jobs' && status === item.key }" :disabled="busy || scene === 'error'" @click="showStatus(item.key)"><span class="status-dot" :class="item.key" />{{ item.label }}<strong>{{ busy || scene === 'error' ? '—' : countState(item.key) }}</strong></ElButton><small>全部人员 · 全部时间 · 条执行</small></div>
      <div class="service-strip"><span>API 生图 <ElTag size="small" :type="scene === 'degraded' || scene === 'error' || busy ? 'warning' : 'success'">{{ scene === 'degraded' ? '未知' : scene === 'error' ? '未获取' : busy ? '更新中' : '在线' }}</ElTag></span><span>CLI 修改 <ElTag size="small" :type="scene === 'degraded' || scene === 'error' || busy ? 'warning' : 'success'">{{ scene === 'degraded' ? '不可用' : scene === 'error' ? '未获取' : busy ? '更新中' : '在线' }}</ElTag></span><small>更新于 {{ updatedAt }}（北京时间）</small><ElButton text type="primary" :disabled="busy || scene === 'error'" @click="serviceOpen = true">服务详情 ›</ElButton></div>
      <ElAlert v-if="scene === 'degraded'" title="API 服务心跳未知，CLI 服务不可用。队列数量不能证明服务在线，请查看服务详情。" type="warning" :closable="false" class="hx-gap" />
    </ElCard>
    <ElCard class="art-card hx-section activity-card" shadow="never">
      <div class="activity-top"><ElRadioGroup v-model="view" aria-label="统计视图"><ElRadioButton value="people">按人员统计</ElRadioButton><ElRadioButton value="jobs">执行记录</ElRadioButton></ElRadioGroup><ElPopover placement="bottom-end" :width="320" trigger="click"><template #reference><ElButton text>统计说明 ⓘ</ElButton></template><p>生成图片＝首次生成＋修改生成，采用或恢复已有图片不重复计数。</p><p>API 请求包含重试；CLI 修改轮次只统计已证实启动的轮次，两者不相加为模型调用次数。</p><p>当前执行按执行记录计数；执行中包含等待重试、收图、取消中。当前失败不等于历史失败请求总数。</p></ElPopover></div>
      <div class="activity-filters">
        <label><span>执行操作者</span><ElSelect v-model="person" clearable filterable placeholder="全部人员" aria-label="执行操作者"><ElOption v-for="item in people" :key="item.id" :label="item.name" :value="item.id" /></ElSelect></label>
        <label class="date-filter"><span>统计时间</span><ElDatePicker v-model="dates" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" :shortcuts="shortcuts" /></label>
        <label><span>生成类型</span><ElSelect v-model="kind" clearable placeholder="全部类型" aria-label="生成类型"><ElOption v-for="(label,key) in kinds" :key="key" :value="key" :label="label" /></ElSelect></label>
        <label v-if="view === 'jobs'"><span>执行状态</span><ElSelect v-model="status" clearable placeholder="全部状态" aria-label="执行状态"><ElOption v-for="(label,key) in statusFilters" :key="key" :value="key" :label="label" /></ElSelect></label>
        <label v-if="view === 'jobs'" class="keyword-filter"><span>任务</span><ElInput v-model="keyword" clearable placeholder="搜索任务名称或执行 ID" aria-label="搜索任务" /></label>
        <ElButton @click="reset">重置筛选</ElButton>
      </div>
      <p class="scope-line">{{ person ? people.find(p => p.id === person)?.name : '国内全员' }} · {{ dates?.length ? dates.join(' 至 ') : '全部时间' }} · {{ kind ? kinds[kind] : '全部类型' }}<span v-if="view === 'jobs' && status"> · {{ statusFilters[status] }}</span><ElButton v-if="view === 'jobs' && person" text type="primary" @click="view = 'people'">返回人员统计</ElButton></p>
      <ElSkeleton v-if="busy" :rows="7" animated aria-label="正在读取数据" />
      <ElAlert v-else-if="scene === 'error'" title="数据加载失败，请重试。当前数量未知。" type="error" :closable="false"><ElButton text type="primary" @click="refresh">重新加载</ElButton></ElAlert>
      <template v-else>
        <div class="usage-summary"><span>生成图片 <strong>{{ sums.images }}</strong> 张</span><span>API 请求 <strong>{{ sums.api }}</strong> 次</span><span>CLI 修改 <strong>{{ sums.cli }}</strong> 轮</span><small>当前{{ view === 'people' ? '人员' : '记录' }}筛选范围合计</small></div>
        <ElTable v-if="view === 'people'" :data="personRows" empty-text="暂无匹配的使用记录，请调整筛选条件" class="hx-admin-table">
          <ElTableColumn label="人员" min-width="150"><template #default="{row}"><ElButton text type="primary" @click="showPerson(row.id)">{{ row.name }}</ElButton></template></ElTableColumn>
          <ElTableColumn prop="images" label="生成图片（张）" min-width="145" /><ElTableColumn prop="api" label="API 请求（次）" min-width="145" /><ElTableColumn prop="cli" label="CLI 修改（轮）" min-width="145" />
          <ElTableColumn label="最近使用时间" min-width="185"><template #default="{row}">{{ time(row.latest) }}</template></ElTableColumn>
          <ElTableColumn label="操作" width="110" fixed="right"><template #default="{row}"><ElButton text type="primary" @click="showPerson(row.id)">查看记录</ElButton></template></ElTableColumn>
        </ElTable>
        <ElTable v-else :data="pageRows" empty-text="暂无匹配的执行记录，请调整筛选条件" class="hx-admin-table">
          <ElTableColumn prop="task" label="任务名称" min-width="210" /><ElTableColumn prop="person" label="操作者" min-width="100" /><ElTableColumn label="类型" min-width="110"><template #default="{row}">{{ kinds[row.kind as Kind] }}</template></ElTableColumn>
          <ElTableColumn label="状态" min-width="110"><template #default="{row}"><ElTag :type="row.status === 'succeeded' ? 'success' : row.status === 'failed' ? 'danger' : row.status === 'uncertain' ? 'warning' : 'info'">{{ statuses[row.status as Status] }}</ElTag></template></ElTableColumn>
          <ElTableColumn prop="images" label="生成图片" min-width="100" /><ElTableColumn label="发起时间" min-width="185"><template #default="{row}">{{ time(row.createdAt) }}</template></ElTableColumn>
          <ElTableColumn label="耗时" min-width="95"><template #default="{row}">{{ duration(row) }}</template></ElTableColumn><ElTableColumn label="操作" width="110" fixed="right"><template #default="{row}"><ElButton text type="primary" @click="selected = row">查看详情</ElButton></template></ElTableColumn>
        </ElTable>
        <div class="activity-pagination"><span>{{ view === 'people' ? `共 ${personRows.length} 人 · 点击人员查看执行记录` : `共 ${filtered.length} 条记录 · 每页 20 条` }}</span><ElPagination v-if="view === 'jobs' && filtered.length" v-model:current-page="page" :total="filtered.length" :page-size="20" layout="prev, pager, next" aria-label="执行记录分页" /></div>
      </template>
    </ElCard>
    <Details :selected="selected" :service-open="serviceOpen" :rows="source" :unavailable="scene === 'degraded'" @close-record="selected = null" @close-service="serviceOpen = false" />
  </div>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { formatBeijingTime } from '@/utils/beijing-time'
import { filterRecords, groupStatus, kinds, people, records, scene, statuses, summary, type Kind, type RecordItem, type Status } from './data'
import Details from './Details.vue'
const view = ref('people'), person = ref(''), dates = ref<string[] | null>(null), kind = ref<Kind | ''>(''), status = ref(''), keyword = ref(''), page = ref(1)
const selected = ref<RecordItem | null>(null), serviceOpen = ref(false), refreshing = ref(false), updatedAt = ref('2026-11-11 17:00:00')
const statusFilters: Record<string,string> = { queued: '排队中', running: '执行中（含收图、重试、取消中）', uncertain: '待核实', failed: '失败', succeeded: '已完成', cancelled: '已取消' }
const liveStates = [{ key: 'queued', label: '排队中' }, { key: 'running', label: '执行中' }, { key: 'uncertain', label: '待核实' }, { key: 'failed', label: '当前失败' }]
const shortcuts = [{ text: '示例今日', value: () => [new Date('2026-11-11T00:00:00+08:00'), new Date('2026-11-11T00:00:00+08:00')] }, { text: '示例近 7 天', value: () => [new Date('2026-11-05T00:00:00+08:00'), new Date('2026-11-11T00:00:00+08:00')] }]
const busy = computed(() => refreshing.value || scene.value === 'loading')
const source = computed(() => scene.value === 'empty' ? [] : records)
const baseRows = computed(() => filterRecords(source.value, person.value, dates.value, kind.value))
const filtered = computed(() => baseRows.value.filter(row => (!status.value || groupStatus(row) === status.value) && (!keyword.value.trim() || `${row.task} ${row.id}`.toLowerCase().includes(keyword.value.trim().toLowerCase()))))
const pageRows = computed(() => filtered.value.slice((page.value - 1) * 20, page.value * 20))
const personRows = computed(() => people.map(p => { const rows = baseRows.value.filter(row => row.personId === p.id); return { ...p, ...summary(rows), latest: rows[0]?.createdAt || '', count: rows.length } }).filter(p => p.count))
const sums = computed(() => summary(view.value === 'people' ? baseRows.value : filtered.value))
const time = (value: string) => formatBeijingTime(value)
const duration = (row: RecordItem) => row.seconds !== null ? `${row.seconds} 秒` : !row.startedAt ? '未开始' : row.status === 'uncertain' ? '待核实' : '进行中'
function countState(key: string) { return source.value.filter(row => groupStatus(row) === key).length }
function reset() { person.value = ''; dates.value = null; kind.value = ''; status.value = ''; keyword.value = ''; page.value = 1 }
function showPerson(id: string) { person.value = id; status.value = ''; keyword.value = ''; view.value = 'jobs' }
function showStatus(key: string) { reset(); status.value = key; view.value = 'jobs' }
let timer: ReturnType<typeof setTimeout> | undefined
function refresh() { clearTimeout(timer); refreshing.value = true; timer = setTimeout(() => { if (scene.value === 'error' || scene.value === 'loading') scene.value = 'normal'; updatedAt.value = time(new Date().toISOString()); refreshing.value = false }, 500) }
watch([person, dates, kind, status, keyword, view, scene], () => { page.value = 1; selected.value = null; serviceOpen.value = false })
onUnmounted(() => clearTimeout(timer))
</script>
