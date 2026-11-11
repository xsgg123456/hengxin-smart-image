<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">EXECUTION INSIGHTS</span><h1>调用与执行</h1><p>查看人员使用情况，跟进当前执行进度。</p></div><ElButton :loading="loading" @click="refresh">刷新数据</ElButton></div>
    <ElCard class="art-card hx-section" shadow="never">
      <div class="execution-strip"><span>当前执行</span><ElButton v-for="item in liveStates" :key="item.key" :aria-label="`查看${item.label}记录`" text :class="{ selected: view === 'jobs' && status === item.key }" :disabled="loading || !!error" @click="showStatus(item.key)"><span class="status-dot" :class="item.key" />{{ item.label }}<strong>{{ loading || !!error ? '—' : countState(item.key) }}</strong></ElButton><small>全部人员 · 全部时间 · 条执行</small></div>
      <div class="service-strip"><span v-for="channel in ['api','cli']" :key="channel">{{ channel === 'api' ? 'API 生图' : 'CLI 修改' }} <ElTag size="small" :type="serviceState(channel) === 'available' ? 'success' : 'warning'">{{ serviceLabel(channel) }}</ElTag></span><small>{{ monitor ? `更新于 ${time(monitor.checkedAt)}（北京时间）` : '服务状态尚未获取' }}</small><ElButton text type="primary" :disabled="monitorLoading || !monitor" @click="serviceOpen = true">服务详情 ›</ElButton></div>
      <ElAlert v-if="monitorError" :title="monitorError" type="error" :closable="false" class="hx-gap"><ElButton text @click="loadMonitor">重试服务状态</ElButton></ElAlert>
      <ElAlert v-else-if="monitor?.channels.some(c => c.state !== 'available' || !c.enabled || c.paused || c.queueState === 'unknown')" title="执行服务状态需要关注，请查看服务详情。队列数量不能证明服务在线。" type="warning" :closable="false" class="hx-gap" />
    </ElCard>
    <ElCard class="art-card hx-section activity-card" shadow="never">
      <div class="activity-top"><ElRadioGroup v-model="view" aria-label="统计视图"><ElRadioButton value="people">按人员统计</ElRadioButton><ElRadioButton value="jobs">执行记录</ElRadioButton></ElRadioGroup><ElPopover placement="bottom-end" :width="320" trigger="click"><template #reference><ElButton text>统计说明 ⓘ</ElButton></template><p>生成图片＝首次生成＋修改生成，采用或恢复已有图片不重复计数。</p><p>API 请求包含重试；CLI 修改轮次只统计已证实启动的轮次，两者不相加为模型调用次数。</p><p>历史API请求与图片产出缺少可靠关联时显示“未关联”，人员图片汇总仍按真实产出统计。</p><p>日期按统计发生时间：API 请求、已启动 CLI 轮次按启动时间，未启动按发起时间；图片按产出时间。发起时间与开始时间在详情中分别展示。</p><p>当前执行按执行记录计数；执行中包含等待重试、收图、取消中。当前失败不等于历史失败请求总数。</p></ElPopover></div>
      <div class="activity-filters">
        <label><span>执行操作者</span><ElSelect v-model="person" clearable filterable placeholder="全部人员" aria-label="执行操作者"><ElOption v-for="item in users" :key="item.id" :label="item.name" :value="item.id" /></ElSelect></label>
        <label class="date-filter"><span>统计时间</span><ElDatePicker v-model="dates" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" :shortcuts="shortcuts" /></label>
        <label><span>生成类型</span><ElSelect v-model="kind" clearable placeholder="全部类型" aria-label="生成类型"><ElOption v-for="(label,key) in kinds" :key="key" :value="key" :label="label" /></ElSelect></label>
        <label v-if="view === 'jobs'"><span>执行状态</span><ElSelect v-model="status" @change="currentOnly = false" clearable placeholder="全部状态" aria-label="执行状态"><ElOption v-for="(label,key) in statusFilters" :key="key" :value="key" :label="label" /></ElSelect></label>
        <label v-if="view === 'jobs'" class="keyword-filter"><span>任务</span><ElInput v-model="keyword" clearable placeholder="搜索任务名称或执行 ID" aria-label="搜索任务" /></label>
        <ElButton @click="reset">重置筛选</ElButton>
      </div>
      <p class="scope-line">{{ scope }} · {{ kind ? kinds[kind] : '全部类型' }}<span v-if="view === 'jobs' && status"> · {{ statusFilters[status] || status }}</span><span v-if="view === 'jobs' && currentOnly"> · 当前状态</span><ElButton v-if="view === 'jobs' && person" text type="primary" @click="view = 'people'">返回人员统计</ElButton></p>
      <ElSkeleton v-if="loading" :rows="7" animated aria-label="正在读取数据" />
      <ElAlert v-else-if="error" :title="error" type="error" :closable="false"><ElButton text type="primary" @click="load">重新加载</ElButton></ElAlert>
      <template v-else-if="report">
        <div class="usage-summary"><span>生成图片 <strong>{{ sums.images ?? '未关联' }}</strong>{{ sums.images === null ? '' : ' 张' }}</span><span>API 请求 <strong>{{ sums.api }}</strong> 次</span><span>CLI 修改 <strong>{{ sums.cli }}</strong> 轮</span><small>当前{{ view === 'people' ? '人员' : '记录' }}筛选范围合计</small></div>
        <ElTable v-if="view === 'people'" :data="personRows" empty-text="暂无匹配的使用记录，请调整筛选条件" class="hx-admin-table">
          <ElTableColumn label="人员" min-width="150"><template #default="{row}"><ElButton text type="primary" @click="showPerson(row.id)">{{ row.name }}</ElButton></template></ElTableColumn>
          <ElTableColumn prop="images" label="生成图片（张）" min-width="145" /><ElTableColumn prop="api" label="API 请求（次）" min-width="145" /><ElTableColumn prop="cli" label="CLI 修改（轮）" min-width="145" />
          <ElTableColumn label="最近使用时间" min-width="185"><template #default="{row}">{{ time(row.latest) }}</template></ElTableColumn>
          <ElTableColumn label="操作" width="110" fixed="right"><template #default="{row}"><ElButton text type="primary" @click="showPerson(row.id)">查看记录</ElButton></template></ElTableColumn>
        </ElTable>
        <ElTable v-else :data="pageRows" empty-text="暂无匹配的执行记录，请调整筛选条件" class="hx-admin-table">
          <ElTableColumn label="任务名称" min-width="210"><template #default="{row}">{{ row.task }} <ElTag v-if="row.taskDeleted" size="small" type="info">已删除</ElTag></template></ElTableColumn><ElTableColumn prop="person" label="操作者" min-width="100" /><ElTableColumn label="类型" min-width="110"><template #default="{row}">{{ row.kind ? kinds[row.kind as Kind] : '历史类型未记录' }}</template></ElTableColumn>
          <ElTableColumn label="状态" min-width="110"><template #default="{row}"><ElTag :type="row.status === 'succeeded' ? 'success' : row.status === 'failed' ? 'danger' : row.status === 'uncertain' ? 'warning' : 'info'">{{ statuses[row.status] || row.status }}</ElTag></template></ElTableColumn>
          <ElTableColumn label="生成图片" min-width="100"><template #default="{row}">{{ row.images ?? '未关联' }}</template></ElTableColumn><ElTableColumn label="发起时间" min-width="185"><template #default="{row}">{{ time(row.createdAt) }}</template></ElTableColumn>
          <ElTableColumn label="耗时" min-width="95"><template #default="{row}">{{ duration(row) }}</template></ElTableColumn><ElTableColumn label="操作" width="110" fixed="right"><template #default="{row}"><ElButton text type="primary" @click="selected = row">查看详情</ElButton></template></ElTableColumn>
        </ElTable>
        <div class="activity-pagination"><span>{{ view === 'people' ? `共 ${personRows.length} 人 · 点击人员查看执行记录` : `共 ${report.total} 条记录 · 每页 20 条` }}</span><ElPagination v-if="view === 'jobs' && report.total" v-model:current-page="page" :total="report.total" :page-size="20" layout="prev, pager, next" aria-label="执行记录分页" /></div>
      </template>
    </ElCard>
    <ActivityDetails :selected="selected" :service-open="serviceOpen" :monitor="monitor" @close-record="selected = null" @close-service="serviceOpen = false" />
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { formatBeijingTime } from '@/utils/beijing-time'
import { activityStatuses as statuses, generationKinds as kinds, type GenerationKind as Kind, type ActivityRecord } from '@/types/activity'
import { useActivity } from './use-activity'
import ActivityDetails from './ActivityDetails.vue'
import './activity.css'
const { users,view,person,dates,kind,status,keyword,page,currentOnly,report,monitor,loading,monitorLoading,error,monitorError,selected,serviceOpen,scope,load,loadMonitor,reset,showPerson,showStatus,refresh } = useActivity()
const liveStates = [{ key:'queued', label:'排队中' },{ key:'running', label:'执行中' },{ key:'uncertain', label:'待核实' },{ key:'failed', label:'当前失败' }]
const statusFilters: Record<string,string> = {queued:'排队中',running:'执行中（含收图、重试、取消中）',uncertain:'待核实',failed:'失败',succeeded:'已完成',cancelled:'已取消',unknown:'历史状态未记录'}
const sums = computed(() => report.value?.summary || {images:null,api:0,cli:0})
const personRows = computed(() => report.value?.people || []), pageRows = computed(() => report.value?.records || [])
const time = (value: string | null) => value ? formatBeijingTime(value) : '未记录'
const duration = (row: ActivityRecord) => row.seconds !== null ? `${Math.round(row.seconds)} 秒` : row.status === 'queued' ? '未开始' : ['running','retry_wait','collecting','cancelling'].includes(row.status) ? '进行中' : '未记录'
const countState = (key: string) => report.value?.live[key as keyof NonNullable<typeof report.value>['live']] ?? '—'
const serviceState = (key: string) => monitor.value?.channels.find(c=>c.channel===key)?.state
const serviceLabel = (key: string) => monitorLoading.value ? '更新中' : !monitor.value ? '未获取' : ({available:'在线',unavailable:'不可用',unknown:'未知'}[serviceState(key) || 'unknown'])
const day = () => formatBeijingTime(new Date().toISOString()).slice(0,10)
const shortcuts = [{text:'今天',value:()=>[new Date(`${day()}T00:00:00+08:00`),new Date(`${day()}T00:00:00+08:00`)]},{text:'近7天',value:()=>[new Date(Date.parse(`${day()}T00:00:00+08:00`)-6*86400000),new Date(`${day()}T00:00:00+08:00`)]}]
</script>
