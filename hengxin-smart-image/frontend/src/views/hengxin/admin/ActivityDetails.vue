<template>
  <ElDrawer :model-value="!!selected" title="执行详情" size="min(560px, 100vw)" @close="$emit('close-record')">
    <template v-if="selected"><h2 class="detail-title">{{ selected.task }} <ElTag v-if="selected.taskDeleted" type="info">已删除</ElTag></h2>
      <ElDescriptions :column="1" border>
        <ElDescriptionsItem label="执行 ID">{{ selected.id }}</ElDescriptionsItem><ElDescriptionsItem label="实际操作者">{{ selected.person }}</ElDescriptionsItem>
        <ElDescriptionsItem label="生成类型">{{ selected.kind ? kinds[selected.kind] : '历史类型未记录' }}</ElDescriptionsItem><ElDescriptionsItem label="状态">{{ statuses[selected.status] || selected.status }}</ElDescriptionsItem>
        <ElDescriptionsItem label="发起时间">{{ time(selected.createdAt) }}</ElDescriptionsItem><ElDescriptionsItem label="开始时间">{{ time(selected.startedAt) }}</ElDescriptionsItem><ElDescriptionsItem label="结束时间">{{ time(selected.finishedAt) }}</ElDescriptionsItem>
        <ElDescriptionsItem label="耗时">{{ selected.seconds === null ? '未记录 / 尚未结束' : `${Math.round(selected.seconds)} 秒` }}</ElDescriptionsItem><ElDescriptionsItem label="生成图片">{{ selected.images === null ? '未关联到此执行记录' : `${selected.images} 张` }}</ElDescriptionsItem>
        <ElDescriptionsItem v-if="selected.kind !== 'cli_edit'" label="是否重试">{{ selected.retry === null ? '未记录' : selected.retry ? '是（已包含在 API 请求数内）' : '否' }}</ElDescriptionsItem>
      </ElDescriptions><ElAlert v-if="selected.error" class="hx-gap" :title="selected.error" type="warning" :closable="false" />
      <p v-if="selected.images === null" class="hx-footnote">该请求与图片产出没有可靠关联，不能把请求成功次数当成生成图片数。</p>
    </template>
  </ElDrawer>
  <ElDrawer :model-value="serviceOpen" title="执行服务详情" size="min(620px, 100vw)" @close="$emit('close-service')">
    <p class="hx-footnote">服务状态来自心跳，不代表上游模型已验证可用。</p>
    <section v-for="channel in monitor?.channels || []" :key="channel.channel" class="service-detail">
      <div class="activity-top"><h2>{{ channel.channel === 'api' ? 'API 生图' : 'CLI 图片修改' }}</h2><ElTag :type="channel.state === 'available' ? 'success' : 'warning'">{{ states[channel.state] }}</ElTag></div>
      <ElAlert v-if="!channel.enabled" title="此执行渠道未启用。" type="warning" :closable="false" /><ElAlert v-if="channel.paused" :title="channel.pauseReason || 'API 通道暂停'" type="error" :closable="false" />
      <ElAlert v-if="channel.queueState === 'unknown'" title="队列采集失败，数量未知。" type="warning" :closable="false" />
      <p class="hx-footnote">{{ channel.channel === 'api' ? `任务准入 ${count(channel.concurrencyLimit)} 套 · 每批 ${count(channel.imagesPerBatch)} 张` : `最多并行 ${count(channel.concurrencyLimit)} 个修改轮次 · 同图会话串行` }}</p>
      <ElTable :data="channel.metrics"><ElTableColumn label="阶段"><template #default="{row}">{{ statuses[row.phase] || row.phase }}</template></ElTableColumn><ElTableColumn label="关联任务（套）"><template #default="{row}">{{ count(row.tasks) }}</template></ElTableColumn><ElTableColumn label="涉及图片（张）"><template #default="{row}">{{ count(row.images) }}</template></ElTableColumn><ElTableColumn v-if="channel.channel === 'cli'" label="修改轮次"><template #default="{row}">{{ count(row.turns) }}</template></ElTableColumn></ElTable>
      <p v-if="!channel.workers.length" class="hx-footnote">尚无有效心跳，无法确认节点是否在线。</p><p v-for="worker in channel.workers" :key="worker.id" class="hx-footnote">{{ worker.id }} · {{ time(worker.checkedAt) }} · {{ states[worker.state] }} · 容量 {{ count(worker.capacity) }}</p>
      <p class="hx-footnote">同套任务可能跨阶段出现，任务套数不能直接相加。</p>
    </section>
  </ElDrawer>
</template>
<script setup lang="ts">
import { formatBeijingTime } from '@/utils/beijing-time'
import { activityStatuses as statuses, generationKinds as kinds, type ActivityRecord } from '@/types/activity'
import type { ApiMonitorReport } from '@/types/execution-management'
defineProps<{ selected: ActivityRecord | null; serviceOpen: boolean; monitor?: ApiMonitorReport }>()
defineEmits<{ 'close-record': []; 'close-service': [] }>()
const time = (value: string | null) => value ? formatBeijingTime(value) : '未记录 / 尚未发生'
const count = (value: number | null) => value === null ? '未知' : value
const states = {available:'在线',unavailable:'不可用',unknown:'未知'}
</script>
