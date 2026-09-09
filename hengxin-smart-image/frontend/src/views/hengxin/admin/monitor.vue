<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">EXECUTION HEALTH</span><h1>执行监控</h1><p>查看当前服务状态与业务异常，空闲表示暂无执行，不代表离线。</p></div><ElButton :loading="loading" @click="load">刷新状态</ElButton></div>
    <AdminPreview />
    <ElAlert v-if="error" :title="error" type="error" :closable="false"><ElButton text @click="load">重试加载</ElButton></ElAlert>
    <template v-if="report">
      <div class="hx-stats hx-gap"><ElCard class="art-card"><span>总体服务</span><strong>{{ states[report.state] }}</strong></ElCard><ElCard class="art-card"><span>排队任务</span><strong>{{ report.queueSize }}</strong></ElCard><ElCard class="art-card"><span>正在执行</span><strong>{{ report.runningCount }}</strong></ElCard><ElCard class="art-card"><span>最后检查</span><strong style="font-size: 15px">{{ report.checkedAt ? time(report.checkedAt) : '未检查' }}</strong></ElCard></div>
      <ElAlert v-if="report.state === 'unknown'" title="健康检查已过期或尚未提供，当前状态未知。" type="warning" :closable="false" />
      <ElAlert v-if="report.state === 'unavailable'" :title="report.issue?.message || '执行服务暂不可用，请根据依赖状态处理异常。'" type="error" :closable="false" />
      <ElCard v-if="report.detail" class="art-card hx-section hx-gap"><h2>执行环境</h2><p class="hx-muted">CLI {{ report.detail.cliVersion || '未提供' }} · 配置{{ report.detail.configured === null ? '未知' : report.detail.configured ? '就绪' : '未就绪' }} · 临时空间 {{ report.detail.freeDiskBytes == null ? '未知' : `${(report.detail.freeDiskBytes / 1024 ** 3).toFixed(1)} GiB` }}</p><p class="hx-muted">最近结果：{{ report.detail.lastResult || '尚无记录' }}（历史结果不替代当前健康检查）</p>
        <ArtTable height="auto" empty-height="340px" :show-table-header="false" :data="report.detail.workers" :columns="workerColumns" :show-pagination="false" empty-text="暂无执行节点"><template #state="{ row }">{{ states[row.state as keyof typeof states] }}</template><template #checkedAt="{ row }">{{ time(row.checkedAt) }}</template></ArtTable>
        <div class="hx-source-list"><ElTag v-for="dependency in report.detail.dependencies" :key="dependency.name" :type="dependency.state === 'available' ? 'success' : dependency.state === 'unavailable' ? 'danger' : 'warning'">{{ dependency.name }} · {{ dependency.message }}</ElTag></div>
      </ElCard>
      <ElCard class="art-card hx-section hx-gap"><h2>队列与业务异常</h2><ArtTable height="auto" empty-height="340px" :show-table-header="false" :data="report.tasks" :columns="columns" :loading="loading" :show-pagination="false" empty-text="暂无排队、执行或异常任务"><template #name="{ row }"><ElButton type="primary" text @click="router.push({path:'/tasks/index', query:{taskId:row.taskId}})">{{ row.name }}</ElButton></template><template #sessionId="{ row }">{{ row.sessionId || '尚未创建' }}</template><template #elapsedSeconds="{ row }">{{ row.elapsedSeconds == null ? '未知' : `${row.elapsedSeconds} 秒` }}</template><template #error="{ row }">{{ row.error || '—' }}</template></ArtTable></ElCard>
    </template>
  </div>
</template>
<script setup lang="ts">
import { useRouter } from 'vue-router'
import { getMonitor } from '@/api/management'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import AdminPreview from './AdminPreview.vue'
import { useAdminQuery } from './use-admin-query'
const router = useRouter(), { data: report, loading, error, load } = useAdminQuery(getMonitor)
const states = { idle: '空闲', running: '执行中', unavailable: '不可用', unknown: '未知' }
const time = (value: string) => new Date(value).toLocaleString('zh-CN', { hour12: false })
const workerColumns = [{ prop: 'id', label: '节点' }, { prop: 'state', label: '状态', useSlot: true }, { prop: 'concurrency', label: '并发上限' }, { prop: 'checkedAt', label: '心跳 / 检查时间', minWidth: 170, useSlot: true }]
const columns = [{ prop: 'name', label: '任务', minWidth: 190, useSlot: true }, { prop: 'operatorName', label: '操作者', width: 120 }, { prop: 'state', label: '阶段', width: 100 }, { prop: 'sessionId', label: '会话标识', minWidth: 140, useSlot: true }, { prop: 'elapsedSeconds', label: '已运行', width: 110, useSlot: true }, { prop: 'error', label: '业务错误', minWidth: 160, useSlot: true }]
</script>
