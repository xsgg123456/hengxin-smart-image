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
</template>
<script setup lang="ts">
import { formatBeijingTime } from '@/utils/beijing-time'
import { activityStatuses as statuses, generationKinds as kinds, type ActivityRecord } from '@/types/activity'
defineProps<{ selected: ActivityRecord | null }>()
defineEmits<{ 'close-record': [] }>()
const time = (value: string | null) => value ? formatBeijingTime(value) : '未记录 / 尚未发生'
</script>
