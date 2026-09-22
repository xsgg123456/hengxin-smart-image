<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">EXECUTION HEALTH</span><h1>执行监控</h1><p>查看当前服务状态与业务异常，空闲表示暂无执行，不代表离线。</p></div><ElButton :loading="loading" @click="load">刷新状态</ElButton></div>
    <AdminPreview />
    <ElAlert v-if="error" :title="error" type="error" :closable="false"><ElButton text :disabled="loading" @click="load">重试加载</ElButton></ElAlert>
    <ElCard v-if="loading && !report" class="art-card hx-section"><p role="status">正在读取执行状态…</p><ElSkeleton :rows="5" animated /></ElCard>
    <ElEmpty v-else-if="!report && !error" description="暂无监控报告" />
    <template v-if="report">
      <ElAlert v-if="error" title="刷新失败，以下为上次读取的报告，不代表当前状态。" type="warning" :closable="false" />
      <p v-else-if="loading" class="hx-muted" role="status">正在刷新，以下为上次读取的报告…</p>
      <div class="hx-admin-kpis hx-gap"><ElCard class="art-card hx-admin-kpi hx-health-kpi"><div><span>总体服务</span><strong>{{ states[report.state] }}</strong><small>当前健康状态</small></div><ArtSvgIcon icon="ri:heart-pulse-line" /></ElCard><ElCard class="art-card hx-admin-kpi"><div><span>排队任务</span><strong>{{ monitorCount(report.queueSize) }}</strong><small>等待执行</small></div><ArtSvgIcon icon="ri:time-line" /></ElCard><ElCard class="art-card hx-admin-kpi"><div><span>正在执行</span><strong>{{ monitorCount(report.runningCount) }}</strong><small>占用执行节点</small></div><ArtSvgIcon icon="ri:loader-4-line" /></ElCard><ElCard class="art-card hx-admin-kpi"><div><span>最后检查</span><strong class="hx-admin-kpi-time">{{ report.checkedAt ? time(report.checkedAt) : '未检查' }}</strong><small>心跳时间</small></div><ArtSvgIcon icon="ri:refresh-line" /></ElCard></div>
      <ElAlert v-if="report.state === 'unknown'" :title="report.issue?.message || '健康检查已过期或尚未提供，当前状态未知。'" type="warning" :closable="false" />
      <ElAlert v-if="report.state === 'unavailable'" :title="report.issue?.message || '执行服务暂不可用，请根据依赖状态处理异常。'" type="error" :closable="false" />
      <ElCard v-if="report.detail" class="art-card hx-section hx-gap"><div class="hx-admin-section-head"><div><span class="hx-admin-kicker">RUNTIME</span><h2>执行环境</h2><p>依赖状态和 Worker 心跳只用于判断当前可执行性。</p></div><ElTag :type="report.detail.configured ? 'success' : 'warning'">{{ report.detail.configured ? '环境就绪' : '状态待确认' }}</ElTag></div><p class="hx-muted">CLI {{ report.detail.cliVersion || '未提供' }} · 配置{{ report.detail.configured === null ? '未知' : report.detail.configured ? '就绪' : '未就绪' }} · 临时空间 {{ report.detail.freeDiskBytes == null ? '未知' : `${(report.detail.freeDiskBytes / 1024 ** 3).toFixed(1)} GiB` }}</p><p class="hx-muted">最近结果：{{ report.detail.lastResult || '尚无记录' }}（历史结果不替代当前健康检查）</p>
        <ArtTable height="auto" empty-height="340px" :show-table-header="false" :data="report.detail.workers" :columns="workerColumns" :show-pagination="false" empty-text="暂无执行节点"><template #state="{ row }">{{ states[row.state as keyof typeof states] }}</template><template #checkedAt="{ row }">{{ time(row.checkedAt) }}</template></ArtTable>
        <div class="hx-source-list"><ElTag v-for="dependency in report.detail.dependencies" :key="dependency.name" :type="dependency.state === 'available' ? 'success' : dependency.state === 'unavailable' ? 'danger' : 'warning'">{{ dependency.name }} · {{ dependency.message }}</ElTag></div>
      </ElCard>
      <ElCard class="art-card hx-section hx-gap"><div class="hx-admin-section-head"><div><span class="hx-admin-kicker">QUEUE & INCIDENTS</span><h2>队列与业务异常</h2><p>{{ coverage?.summary }}</p></div><ElTag type="info" effect="plain">{{ report.tasks.length }} 条</ElTag></div><ElAlert v-if="coverage?.truncated" title="非运行任务已截断：运行中及待核实任务全部显示，排队、失败、部分失败任务仅显示最近 100 条。更多任务请前往任务中心查看。" type="info" :closable="false" /><ArtTable height="auto" empty-height="340px" :show-table-header="false" :data="report.tasks" :columns="columns" :loading="loading" :show-pagination="false" :empty-text="coverage?.emptyText"><template #name="{ row }"><ElButton type="primary" text @click="router.push({path:'/tasks/index', query:{taskId:row.taskId}})">{{ row.name }}</ElButton></template><template #sessionId="{ row }">{{ row.sessionId || '未提供' }}</template><template #elapsedSeconds="{ row }">{{ elapsedTime(row.elapsedSeconds) }}</template><template #error="{ row }">{{ row.error || '—' }}</template></ArtTable></ElCard>
    </template>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { getMonitor } from '@/api/management'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import AdminPreview from './AdminPreview.vue'
import { useAdminQuery } from './use-admin-query'
import { elapsedTime, monitorCount, monitorCoverage } from './monitor-presentation'
const router = useRouter(), { data: report, loading, error, load } = useAdminQuery(getMonitor)
const coverage = computed(() => report.value ? monitorCoverage(report.value) : undefined)
const states = { idle: '空闲', running: '执行中', unavailable: '不可用', unknown: '未知' }
const time = (value: string) => new Date(value).toLocaleString('zh-CN', { hour12: false })
const workerColumns = [{ prop: 'id', label: '节点' }, { prop: 'state', label: '状态', useSlot: true }, { prop: 'concurrency', label: '并发上限' }, { prop: 'checkedAt', label: '心跳 / 检查时间', minWidth: 170, useSlot: true }]
const columns = computed(() => [{ prop: 'name', label: '任务', minWidth: 190, useSlot: true }, { prop: 'operatorName', label: '操作者', width: 120 }, { prop: 'state', label: '阶段', width: 100 }, ...(report.value?.detail ? [{ prop: 'sessionId', label: '会话标识', minWidth: 140, useSlot: true }] : []), { prop: 'elapsedSeconds', label: '已运行', width: 110, useSlot: true }, { prop: 'error', label: '业务错误', minWidth: 160, useSlot: true }])
</script>
