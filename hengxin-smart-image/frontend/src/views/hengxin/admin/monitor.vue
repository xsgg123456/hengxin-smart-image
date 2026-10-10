<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">EXECUTION HEALTH</span><h1>执行监控</h1><p>按 API 生图与 CLI 图片修改分别查看数据库队列和执行服务心跳。</p></div><ElButton :loading="loading" @click="load">刷新状态</ElButton></div>
    <ElAlert v-if="error" :title="error + '；已有快照可能过期，请重新读取。'" type="error" :closable="false" />
    <ElSkeleton v-if="loading && !data" :rows="8" animated />
    <ElEmpty v-else-if="!data && !error" description="暂无监控快照" />
    <template v-if="data">
      <p class="hx-muted" role="status">数据库快照：{{ time(data.checkedAt) }}（北京时间）。心跳未知不表示空闲，数据库计数不证明执行服务在线。</p>
      <div class="hx-admin-kpis"><ElCard v-for="item in data.channels" :key="item.channel" class="art-card hx-admin-kpi"><div><span>{{ names[item.channel] }}执行服务</span><strong>{{ error ? '快照过期' : states[item.state] }}</strong><small>独立 Worker 心跳；不代表上游模型已验证可用</small></div></ElCard></div>
      <div class="hx-stack">
        <ElCard v-for="item in data.channels" :key="item.channel" class="art-card hx-section">
          <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">{{ item.channel === 'api' ? 'API GENERATION' : 'CLI IMAGE EDIT' }}</span><h2>{{ names[item.channel] }}</h2><p>{{ item.channel === 'api' ? '图片级请求、等待重试与收图。' : '当前图片会话的最新轮次；候选和澄清回复不计入失败。' }}</p></div><ElTag :type="item.state === 'available' ? 'success' : 'warning'">服务：{{ error ? '快照过期' : states[item.state] }}</ElTag></div>
          <ElAlert v-if="!item.enabled" title="此执行渠道在部署配置中未启用。" type="warning" :closable="false" />
          <ElAlert v-if="item.paused" :title="item.pauseReason || 'API 通道暂停'" type="error" :closable="false" />
          <p v-if="item.channel === 'cli'" class="hx-muted">全局占用 {{ count(item.sharedActiveTurns) }} 个轮次，其中旧 CLI 任务占用 {{ count(item.otherActiveTurns) }} 个；下表只统计 API 图片修改业务。</p>
          <ElAlert v-if="item.queueState === 'unknown'" title="数据库队列采集失败，数量未知。" type="warning" :closable="false" />
          <ElTable :data="item.metrics" table-layout="auto"><ElTableColumn label="阶段" min-width="120"><template #default="{row}">{{ phases[row.phase] || row.phase }}</template></ElTableColumn><ElTableColumn label="关联任务（套）" min-width="135"><template #default="{row}">{{ count(row.tasks) }}</template></ElTableColumn><ElTableColumn label="涉及图片（张）" min-width="135"><template #default="{row}">{{ count(row.images) }}</template></ElTableColumn><ElTableColumn v-if="item.channel === 'cli'" label="修改轮次（次）" min-width="135"><template #default="{row}">{{ count(row.turns) }}</template></ElTableColumn></ElTable>
          <p v-if="!item.workers.length" class="hx-muted">尚无 Worker 心跳，无法从心跳判断执行节点是否在线。</p><p v-for="worker in item.workers" :key="worker.id" class="hx-muted">{{ worker.id }} · {{ time(worker.checkedAt) }}（北京时间） · {{ states[worker.state] }} · 采样容量 {{ count(worker.capacity) }}</p>
          <p class="hx-footnote">{{ item.channel === 'api' ? `当前配置：全站 ${count(item.concurrencyLimit)} 套任务准入，每套 ${count(item.imagesPerBatch)} 张 / 批` : `当前配置：全站最多 ${count(item.concurrencyLimit)} 个 CLI 执行轮次；同一图片会话串行` }}。</p>
          <p class="hx-footnote">同套任务可跨阶段、跨渠道出现，各行套数不能直接相加；当前运行数量不等于并发配置。最新失败与历史失败请求分别统计。</p>
        </ElCard>
        <ElCard class="art-card hx-section"><div class="hx-admin-section-head"><div><span class="hx-admin-kicker">QUEUE & INCIDENTS</span><h2>需要关注的任务</h2><p>打开对应 API 任务详情；已删除任务不进入当前队列。</p></div></div>
          <ElTable :data="data.incidents" :empty-text="data.channels.some(c => c.queueState === 'unknown') ? '采集不完整，关注任务未知' : '当前没有需要关注的任务'"><ElTableColumn label="任务" min-width="185"><template #default="{row}"><ElButton type="primary" text @click="router.push({path:'/api-image-edits/records',query:{task:row.taskId}})">{{ row.name }}</ElButton></template></ElTableColumn><ElTableColumn label="执行渠道" min-width="145"><template #default="{row}">{{ names[row.channel as 'api'|'cli'] }}</template></ElTableColumn><ElTableColumn label="状态" min-width="115"><template #default="{row}">{{ phases[row.phase] || row.phase }}</template></ElTableColumn><ElTableColumn prop="images" label="涉及图片（张）" min-width="135" /></ElTable>
          <p v-if="data.incidentsTruncated" class="hx-muted">仅展示前 100 条关注记录，队列数量包含全部记录。</p>
        </ElCard>
      </div>
    </template>
  </div>
</template>
<script setup lang="ts">
import { useRouter } from 'vue-router'
import { getApiMonitor } from '@/api/execution-management'
import { useAdminQuery } from './use-admin-query'
const router = useRouter()
const {data, loading, error, load} = useAdminQuery(getApiMonitor)
const names = {api:'API 生图',cli:'CLI 图片修改'}
const states = {available:'在线',unavailable:'不可用',unknown:'未知'}
const phases: Record<string,string> = {queued:'排队',running:'运行',retry_wait:'等待重试',collecting:'收图',cancelling:'取消中',uncertain:'待核实',failed:'当前失败'}
const count = (value: number|null) => value === null ? '未知' : value
const time = (value: string) => new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'})
</script>
