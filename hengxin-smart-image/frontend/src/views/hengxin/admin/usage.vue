<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">EXECUTION INSIGHTS</span><h1>调用统计</h1><p>{{ report?.scope === 'all' ? '全员' : '个人' }}执行记录 · 按上海时间自然日统计，不等同模型内部请求数。</p></div></div>
    <AdminPreview />
    <ElCard class="art-card hx-section">
      <div class="hx-filter">
        <ElDatePicker v-model="dates" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" aria-label="统计日期范围" style="max-width: 340px" />
        <ElSelect v-if="allUsers" v-model="userId" clearable placeholder="全部人员" aria-label="统计人员" style="width: 180px"><ElOption v-for="user in report?.users || []" :key="user.id" :value="user.id" :label="user.name" /></ElSelect>
        <ElSelect v-model="mode" clearable placeholder="全部类型" aria-label="统计类型" style="width: 150px"><ElOption v-for="(label,key) in labels" :key="key" :value="key" :label="label" /></ElSelect>
        <ElButton type="primary" :loading="loading" @click="load">查询统计</ElButton>
      </div>
      <ElAlert v-if="error" :title="error" type="error" :closable="false"><ElButton text @click="load">重试加载</ElButton></ElAlert>
      <template v-if="report">
        <div class="hx-stats"><ElCard v-for="card in cards" :key="card.label" class="art-card"><span>{{ card.label }}</span><strong>{{ card.value }}</strong></ElCard></div>
        <p class="hx-muted">首次 {{ report.summary.initial }} / 单张返工 {{ report.summary.single }} / 整套返工 {{ report.summary.whole }}；成功 {{ report.summary.success }} / 部分失败 {{ report.summary.partial }} / 失败 {{ report.summary.failed }} / 超时 {{ report.summary.timeout }} / 进行中 {{ report.summary.running }}。</p>
        <p class="hx-muted">平均排队 {{ seconds(report.summary.averageQueueSeconds) }} · 平均执行 {{ seconds(report.summary.averageDurationSeconds) }} · 输入 Token {{ report.summary.inputTokens ?? '未提供' }} · 输出 Token {{ report.summary.outputTokens ?? '未提供' }}</p>
        <p class="hx-footnote">成功率 = 成功 / 已结束执行，部分失败计入分母；未结束不计入。成功产出包含返工新版本。缺失 usage 不视为零，不估算费用或额度。</p>
        <ArtTable height="auto" empty-height="340px" :show-table-header="false" :data="report.rows" :loading="loading" :columns="columns" :show-pagination="false" empty-text="此范围暂无执行记录">
          <template #attempts="{ row }">{{ row.summary.attempts }}</template><template #outputs="{ row }">{{ row.summary.outputImages }}</template>
          <template #action="{ row }"><ElButton text type="primary" @click="selected = row; detailOpen = true">展开明细</ElButton></template>
        </ArtTable>
      </template>
    </ElCard>
    <ElDrawer v-model="detailOpen" title="调用明细" size="82%" destroy-on-close><template v-if="selected"><p>{{ selected.date }} · {{ selected.userName }} · 按实际操作者归属</p><ArtTable height="auto" empty-height="340px" :show-table-header="false" :data="selected.details" :columns="detailColumns" :show-pagination="false" empty-text="暂无执行明细">
      <template #taskName="{ row }"><ElButton text type="primary" @click="openTask(row.taskId)">{{ row.taskName }}</ElButton></template>
      <template #kind="{ row }">{{ kinds[row.kind as keyof typeof kinds] }}</template><template #state="{ row }">{{ states[row.state as keyof typeof states] }}</template>
      <template #usage="{ row }">{{ row.usage ? `${row.usage.inputTokens} / ${row.usage.outputTokens}` : '未提供' }}</template>
      <template #time="{ row }">{{ time(row.startedAt) }}</template>
    </ArtTable></template></ElDrawer>
  </div>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store/modules/user'
import { getUsage } from '@/api/management'
import type { Mode } from '@/types/hengxin'
import type { UsageRow } from '@/types/management'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import { labels } from '../model'
import AdminPreview from './AdminPreview.vue'
import { useAdminQuery } from './use-admin-query'
const dates = ref<string[] | null>(null), userId = ref(''), mode = ref<Mode | ''>('')
const allUsers = computed(() => useUserStore().info.roles?.some(role => ['super_admin','design_manager'].includes(role)))
const { data: report, loading, error, load } = useAdminQuery(() => getUsage({ from: dates.value?.[0], to: dates.value?.[1], userId: allUsers.value ? userId.value || undefined : undefined, mode: mode.value || undefined }))
const selected = ref<UsageRow>(), detailOpen = ref(false), router = useRouter()
const cards = computed(() => [{ label: '新建任务', value: report.value?.summary.tasks }, { label: '实际执行次数', value: report.value?.summary.attempts }, { label: '成功率', value: report.value?.summary.successRate == null ? '无数据' : `${(report.value.summary.successRate * 100).toFixed(1)}%` }, { label: '成功产出图片', value: report.value?.summary.outputImages }])
const columns = [{ prop: 'date', label: '日期', minWidth: 140 }, { prop: 'userName', label: '实际操作者', minWidth: 150 }, { prop: 'attempts', label: '执行次数', useSlot: true }, { prop: 'outputs', label: '成功图片', useSlot: true }, { prop: 'action', label: '操作', useSlot: true }]
const detailColumns = [{ prop: 'taskName', label: '关联任务', minWidth: 200, useSlot: true }, { prop: 'kind', label: '执行类型', width: 110, useSlot: true }, { prop: 'state', label: '结果', width: 100, useSlot: true }, { prop: 'time', label: '开始时间', minWidth: 180, useSlot: true }, { prop: 'usage', label: 'Token 输入 / 输出', minWidth: 150, useSlot: true }]
const kinds = { initial: '首次生成', single: '单张返工', whole: '整套返工' }, states = { running: '进行中', success: '成功', partial: '部分失败', failed: '失败', timeout: '超时' }
const seconds = (value: number | null) => value == null ? '无数据' : `${value.toFixed(1)} 秒`
const time = (value: string) => new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
function openTask(taskId: string) { detailOpen.value = false; void router.push({ path: '/tasks/index', query: { taskId } }) }
</script>
