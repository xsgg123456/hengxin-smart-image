<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">AUTOMATIC CLEANUP</span><h1>自动清理</h1><p>查看国内 CLI 会话的清理状态、到期计划和实际处理结果。</p></div><ElButton :loading="summaryLoading || recordsLoading" @click="refresh">刷新状态</ElButton></div>
    <div class="hx-detail-toolbar hx-gap"><span class="hx-footnote" role="status">数据更新时间：{{ time(summary?.checkedAt, '尚未读取') }} · 北京时间{{ summaryError && summary ? ' · 快照已过期' : '' }}</span><div><span class="hx-muted">每 15 秒刷新</span><ElSwitch v-model="auto" aria-label="自动刷新" /></div></div>
    <ElAlert v-if="summaryError" :title="`${summaryError}；当前服务与数量未知${summary ? '，下方保留上次快照（已过期）' : ''}。`" type="error" :closable="false" show-icon />
    <ElSkeleton v-if="summaryLoading && !summary" :rows="8" animated class="hx-gap" />
    <template v-else>
      <RetentionService :data="summary" :stale="!!summaryError && !!summary" :compact="compact" />
      <div class="hx-admin-kpis"><ElCard v-for="kpi in kpis" :key="kpi.label" class="art-card hx-admin-kpi"><div><span>{{ kpi.label }}</span><strong>{{ kpi.value }}</strong><small>{{ summaryError && summary ? '上次快照（已过期） · ' : '' }}{{ kpi.note }}</small></div></ElCard></div>
    </template>
    <ElCard class="art-card hx-section hx-admin-table-card">
      <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">CLEANUP ACTIVITY</span><h2>清理明细</h2><p>每一条记录对应一个会话的处理结果，失败与暂缓不计入成功数量。</p></div><ElButton @click="policyOpen = true">查看保留规则</ElButton></div>
      <ElTabs v-model="query.tab"><ElTabPane label="清理记录" name="history" /><ElTabPane label="待清理" name="pending" /></ElTabs>
      <div class="hx-admin-query-row hx-gap" style="margin-bottom:18px">
        <ElInput v-model="query.keyword" :maxlength="200" clearable placeholder="搜索任务名称或会话编号" aria-label="搜索任务" style="width:240px" />
        <ElSelect v-model="query.kind" aria-label="清理类型" placeholder="全部类型" style="width:140px"><ElOption label="全部类型" value="" /><ElOption v-for="(label,value) in kindLabels" :key="value" :label="label" :value="value" /></ElSelect>
        <ElSelect v-model="query.result" aria-label="处理结果" placeholder="全部结果" style="width:165px"><ElOption label="全部结果" value="" /><ElOption v-for="(label,value) in resultLabels" :key="value" :label="label" :value="value" /></ElSelect>
        <ElDatePicker v-model="dates" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" range-separator="至" :aria-label="query.tab === 'history' ? '处理日期范围' : '到期日期范围'" style="max-width:100%" />
        <ElButton @click="reset">重置</ElButton>
      </div>
      <ElAlert v-if="recordsError" :title="`${recordsError}${records ? '；下方为已过期的上次快照' : '；记录数量未知'}。`" type="error" :closable="false" show-icon />
      <ElSkeleton v-if="recordsLoading && !records" :rows="6" animated />
      <ElTable v-else :data="records?.items || []" :empty-text="recordsError ? '读取失败，请刷新重试' : '暂无符合条件的记录'" row-key="id">
        <ElTableColumn label="任务 / 会话" min-width="210"><template #default="{row}"><div class="hx-table-name"><div><strong>{{ row.taskName }}</strong><small>第 {{ row.imagePosition }} 张 · {{ row.resourceId }}{{ row.taskDeleted ? ' · 任务已删除' : '' }}</small></div></div></template></ElTableColumn>
        <ElTableColumn label="清理类型" width="100"><template #default="{row}">{{ kindLabels[row.kind as RetentionKind] }}</template></ElTableColumn>
        <ElTableColumn label="处理结果" width="140"><template #default="{row}"><ElTag :type="tagType(row.result)">{{ resultLabels[row.result as RetentionResult] }}</ElTag></template></ElTableColumn>
        <ElTableColumn :label="query.tab === 'history' ? '处理时间' : '到期时间'" min-width="170"><template #default="{row}">{{ time(query.tab === 'history' ? row.processedAt : row.dueAt) }}</template></ElTableColumn>
        <ElTableColumn :label="query.tab === 'history' ? '处理摘要' : '当前说明'" min-width="200"><template #default="{row}">{{ row.detail }}</template></ElTableColumn>
        <ElTableColumn label="操作" width="75" fixed="right"><template #default="{row}"><ElButton link type="primary" @click="openDetail(row)">详情</ElButton></template></ElTableColumn>
      </ElTable>
      <ElPagination v-if="records" v-model:current-page="query.page" v-model:page-size="query.pageSize" :total="records.total" :page-sizes="[20,50,100]" :layout="compact ? 'prev, pager, next' : 'total, sizes, prev, pager, next'" class="hx-gap" />
      <p class="hx-footnote">{{ records ? `共 ${records.total} 条${recordsError ? '（快照已过期）' : ''}` : '记录数量未知' }} · 时间均为北京时间 · {{ query.tab === 'history' ? '按处理日期筛选' : '按到期日期筛选' }} · 明细保留 {{ summary ? summary.policy.detailRetentionDays : '未知' }} 天，累计统计长期保留 · 统计起算：{{ time(summary?.statisticsSince, summary ? '尚无统计记录' : '未知') }}</p>
    </ElCard>
    <RetentionDetail :row="selected" :open="detailOpen" :loading="detailLoading" :error="detailError" @close="closeDetail" />
    <RetentionPolicy :open="policyOpen" :policy="summary?.policy" :stale="!!summaryError && !!summary" @close="policyOpen = false" />
  </div>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElAlert, ElButton, ElCard, ElDatePicker, ElInput, ElOption, ElPagination, ElSelect, ElSkeleton, ElSwitch, ElTable, ElTableColumn, ElTabs, ElTabPane, ElTag } from 'element-plus'
import { formatBeijingTime as time } from '@/utils/beijing-time'
import { retentionApi } from '@/api/retention'
import type { RetentionKind, RetentionResult } from '@/types/retention'
import { useRetention } from './use-retention'
import { count, kindLabels, resultLabels, tagType } from './retention-presenter'
import RetentionDetail from './RetentionDetail.vue'
import RetentionService from './RetentionService.vue'
import RetentionPolicy from './RetentionPolicy.vue'
const { summary, records, selected, summaryError, recordsError, detailError, summaryLoading, recordsLoading, detailLoading, detailOpen, auto, query, dates, refresh, openDetail, closeDetail, reset } = useRetention(retentionApi)
const policyOpen = ref(false), compact = ref(window.innerWidth < 1000)
const kpis = computed(() => {
  const c = summary.value?.counts
  return [
    { label: '今日缓存清理成功', value: count(c?.cacheToday), note: `累计 ${count(c?.cacheTotal)} 次` },
    { label: '今日历史清理成功', value: count(c?.historyToday), note: `累计 ${count(c?.historyTotal)} 次 · 文件回收中不计入` },
    { label: '失败待重试', value: count(c?.retry), note: '当前待重试会话数' },
    { label: '已到期待处理', value: count(c?.overdue), note: `受保护会话 ${count(c?.protected)} 个 · 文件回收中 ${count(c?.objectsPending)} 个` }
  ]
})
function resize() { compact.value = window.innerWidth < 1000 }
onMounted(() => window.addEventListener('resize', resize))
onBeforeUnmount(() => window.removeEventListener('resize', resize))
</script>
