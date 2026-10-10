<template>
  <ElDrawer :model-value="true" title="人员每日调用明细" size="min(1100px, 96vw)" destroy-on-close @close="$emit('close')">
    <div class="hx-drawer-intro"><span class="hx-admin-kicker">{{ row.date }}</span><strong>{{ row.userName }}</strong><p>仅展示各事件在北京时间当日发生的记录；当前页不影响外层汇总。</p></div>
    <ElSkeleton v-if="loading" :rows="6" animated aria-label="正在读取调用明细" />
    <ElAlert v-else-if="error" :title="error" type="error" :closable="false"><ElButton text type="primary" @click="load">重试加载</ElButton></ElAlert>
    <template v-else-if="report">
      <ElTable :data="report.events" empty-text="当日暂无事件明细">
        <ElTableColumn label="关联任务" min-width="190"><template #default="{ row: event }"><span v-if="event.taskDeleted">{{ event.taskName || event.taskId }} <ElTag type="info">已删除</ElTag></span><ElButton v-else text type="primary" @click="openTask(event.taskId)">{{ event.taskName || event.taskId }}</ElButton></template></ElTableColumn>
        <ElTableColumn label="事件 / 渠道" min-width="150"><template #default="{ row: event }">{{ usageCategoryLabels[event.category as UsageCategory] }}<div class="hx-muted">{{ event.channel === 'api' ? 'API' : event.channel === 'cli' ? 'CLI' : event.channel === 'business' ? '业务事件' : '历史渠道待核实' }}</div></template></ElTableColumn>
        <ElTableColumn label="操作类型" min-width="140"><template #default="{ row: event }">{{ kindLabels[event.kind] || event.kind || '历史类型待核实' }}</template></ElTableColumn>
        <ElTableColumn label="发生时间（北京）" min-width="180"><template #default="{ row: event }">{{ time(event.occurredAt) }}</template></ElTableColumn>
        <ElTableColumn label="结果" min-width="120"><template #default="{ row: event }">{{ stateLabels[event.state] || event.state }}</template></ElTableColumn>
        <ElTableColumn prop="quantity" label="事件数量" width="100" />
        <ElTableColumn label="请求重试" min-width="110"><template #default="{ row: event }">{{ event.category !== 'api_request' ? '不适用' : event.isRetry === null ? '待核实' : event.isRetry ? '是' : '否' }}</template></ElTableColumn>
        <ElTableColumn label="操作者归属" min-width="180"><template #default="{ row: event }">{{ event.operatorName || '未记录' }}<div><ElTag :type="event.attribution === 'verified' ? 'success' : 'warning'">{{ event.attribution === 'verified' ? '已核实' : '历史归属未核实' }}</ElTag></div></template></ElTableColumn>
      </ElTable>
      <ElPagination v-if="report.total" :current-page="page" :page-size="20" :total="report.total" layout="total, prev, pager, next" class="usage-pagination" aria-label="调用事件分页" @current-change="changePage" />
      <p class="hx-footnote">CLI 启动证据不足不计真实调用；候选、正式生成、手动采用和恢复为独立事件，不能相加为库存。正常澄清完成不等于产出图片。已删除任务保留历史，不跳转失效详情。Token 与费用未提供。</p>
    </template>
  </ElDrawer>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { getApiUsage } from '@/api/api-management-usage'
import { usageCategoryLabels } from '@/api/api-management-usage-validate'
import type { ApiUsageRow, UsageCategory } from '@/types/api-management-usage'
import { useAdminQuery } from './use-admin-query'
const props = defineProps<{ row: ApiUsageRow; category?: UsageCategory }>()
defineEmits<{ close: [] }>()
const page = ref(1), router = useRouter()
const { data: report, loading, error, load } = useAdminQuery(() => getApiUsage({ from: props.row.date, to: props.row.date, userId: props.row.userId || undefined, unassigned: props.row.userId === null ? true : undefined, category: props.category, page: page.value, pageSize: 20 }))
const kindLabels: Record<string, string> = { generation: '首次生成', text_edit: '文字修改', text_repair: '文案修复', image_edit: '图片修改', legacy_unknown: '历史类型待核实', initial: '首次生成', task_created: '创建任务', cli_submission: 'CLI 提交', adopt: '手动采用', restore: '恢复版本' }
const stateLabels: Record<string, string> = { succeeded: '成功', success: '成功', failed: '失败', running: '进行中', queued: '排队中', unknown: '待核实', unverified: '启动证据不足', candidate: '已产出候选', adopted: '已采用', published: '已发布', restored: '已恢复', submitted: '已提交', created: '已创建', waiting_user: '等待补充', cancelled: '已取消', completed: '已完成', stopped: '已停止', retryable: '失败（可重试）', uncertain: '结果待核实', channel: '渠道异常', permanent: '失败（不可重试）', rejected: '已拒绝' }
const time = (v: string) => new Date(v).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
function changePage(value: number) { page.value = value; void load() }
function openTask(task: string) { void router.push({ path: '/api-image-edits/records', query: { task } }) }
</script>
<style scoped>
.usage-pagination { margin-top: 18px; justify-content: flex-end; flex-wrap: wrap; }
.hx-footnote { line-height: 1.7; }
</style>

