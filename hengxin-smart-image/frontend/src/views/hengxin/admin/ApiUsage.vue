<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">EXECUTION INSIGHTS</span><h1>调用统计</h1><p>{{ report ? (report.scope === 'all' ? '全员 · ' : '个人 · ') : '' }}API 业务统计 · 北京时间自然日</p></div></div>
    <ElCard class="art-card hx-section hx-admin-query-card">
      <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">FILTERS</span><h2>统计范围</h2><p>任务按创建日、请求按尝试开始日、CLI 按真实启动日、版本按发布日、采用按采用日统计。</p></div><ElTag type="info" effect="plain">北京时间 · 自然日</ElTag></div>
      <div class="hx-admin-query-row">
        <ElDatePicker v-model="dates" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" aria-label="统计日期范围" />
        <ElSelect v-if="allUsers" v-model="userId" clearable placeholder="全部人员" aria-label="统计人员" style="width: 180px"><ElOption v-for="user in report?.users || []" :key="user.id" :value="user.id" :label="user.name" /></ElSelect>
        <ElSelect v-model="category" clearable placeholder="全部事件类型" aria-label="统计事件类型" style="width: 190px"><ElOption v-for="(label, key) in usageCategoryLabels" :key="key" :value="key" :label="label" /></ElSelect>
        <ElButton type="primary" :loading="loading" @click="query">查询统计</ElButton><ElButton :disabled="loading" @click="reset">重置</ElButton>
      </div>
      <p class="hx-footnote">点击查询应用筛选；汇总覆盖全部筛选结果，不随分页变化。历史按实际操作者筛选；库存按任务创建人筛选。</p>
      <ElAlert v-if="inputError" :title="inputError" type="warning" :closable="false" />
      <ElSkeleton v-if="loading" :rows="8" animated aria-label="正在读取统计数据" />
      <ElAlert v-else-if="error" :title="error" type="error" :closable="false"><ElButton text type="primary" @click="load">重试加载</ElButton></ElAlert>
      <template v-else-if="report">
        <ElTabs v-model="tab"><ElTabPane label="业务成果" name="business" /><ElTabPane label="执行消耗" name="execution" /></ElTabs>
        <div class="hx-admin-kpis"><ElCard v-for="(card, index) in cards" :key="card.label" class="art-card hx-admin-kpi" :class="`hx-admin-kpi-${index}`"><div><span>{{ card.label }}</span><strong>{{ card.value }}</strong><small>{{ card.note }}</small></div></ElCard></div>
        <div v-if="tab === 'business'" class="hx-admin-summary"><div><span class="hx-admin-kicker">CURRENT INVENTORY</span><strong>当前库存 · 仅按创建人过滤，不受日期与事件类型影响</strong></div><p>{{ report.inventory.tasks }} 套任务 · 原图 {{ report.inventory.sourceImages }} 张 · 有正式结果 {{ report.inventory.withResultImages }} 张</p><p>最新处理成功 {{ report.inventory.succeededImages }} · 失败 {{ report.inventory.failedImages }} · 待处理 {{ report.inventory.pendingImages }} · 待核实 {{ report.inventory.uncertainImages }}</p><small>当前图片交付成功率 {{ percentage(report.inventory.deliverySuccessRate) }} = 最新处理成功 /（成功 + 失败）。待处理、待核实不入分母。最新修改失败仍可能保留旧正式结果。</small></div>
        <div v-else class="hx-admin-summary"><div><span class="hx-admin-kicker">SUCCESS & UNKNOWN</span><strong>历史请求成功率与当前交付分别统计</strong></div><p>API 请求成功率 {{ percentage(report.summary.requestSuccessRate) }} · 已知成功 {{ report.summary.apiSucceeded }} / 失败 {{ report.summary.apiFailed }} / 未知 {{ report.summary.apiUnknown }} / 在途 {{ report.summary.apiRunning }}</p><p>CLI 已证实启动 {{ report.summary.cliStarted }} · 启动证据不足 {{ report.summary.cliUnverified }} · 成功完成 {{ report.summary.cliSucceeded }} / 失败 {{ report.summary.cliFailed }} / 待核实 {{ report.summary.cliUnknown }}</p><small>API 成功率仅以已知成功和失败请求为分母；未知与在途不入分母。CLI 正常澄清文字完成不算生图失败；内部模型请求数未提供，不按轮次折算。</small></div>
        <p class="hx-footnote">正式生成版本 {{ report.summary.generatedVersions }} · 来源待核实版本 {{ report.summary.unverifiedVersions }}（不计生成或采用） · CLI 候选 {{ report.summary.cliCandidates }} · 手动采用 {{ report.summary.adoptions }} · 恢复版本 {{ report.summary.restores }}。候选不等于采用，恢复不增加生成或模型调用。</p>
        <p class="hx-footnote">历史归属未核实 {{ report.summary.unverifiedAttribution }} 条；重试属性未知 {{ report.summary.apiRetryUnknown }} 条。Token 输入 / 输出：未提供；费用：未提供。</p>
        <div class="hx-admin-table-head"><div><span class="hx-admin-kicker">DAILY BREAKDOWN</span><strong>人员每日明细</strong></div><span class="hx-muted">共 {{ report.rows.length }} 条汇总记录</span></div>
        <ElTable :data="pageRows" class="hx-admin-table" empty-text="此范围暂无统计记录" style="width: 100%">
          <ElTableColumn prop="date" label="日期" min-width="120" /><ElTableColumn prop="userName" label="实际操作者 / 历史登记人" min-width="170" />
          <template v-if="tab === 'business'"><ElTableColumn prop="summary.tasksCreated" label="新建任务" min-width="100" /><ElTableColumn prop="summary.generatedVersions" label="正式生成版本" min-width="120" /><ElTableColumn prop="summary.unverifiedVersions" label="来源待核实版本" min-width="140" /><ElTableColumn prop="summary.cliCandidates" label="CLI 候选" min-width="100" /><ElTableColumn prop="summary.adoptions" label="手动采用" min-width="100" /><ElTableColumn prop="summary.restores" label="恢复版本" min-width="100" /></template>
          <template v-else><ElTableColumn prop="summary.apiAttempts" label="API 请求" min-width="100" /><ElTableColumn prop="summary.apiRetries" label="其中重试" min-width="100" /><ElTableColumn prop="summary.cliSubmitted" label="CLI 提交" min-width="100" /><ElTableColumn prop="summary.cliStarted" label="CLI 真启动" min-width="110" /><ElTableColumn prop="summary.cliUnverified" label="启动证据不足" min-width="120" /></template>
          <ElTableColumn label="操作" width="110" fixed="right"><template #default="{ row }"><ElButton text type="primary" @click="openDay(row)">展开明细</ElButton></template></ElTableColumn>
        </ElTable>
        <ElPagination v-if="report.rows.length" v-model:current-page="page" :page-size="8" :total="report.rows.length" layout="prev, pager, next" class="usage-pagination" aria-label="每日明细分页" />
      </template>
    </ElCard>
    <ApiUsageDetail v-if="selected" :key="`${selected.date}-${selected.userId}-${applied.category}`" :row="selected" :category="applied.category" @close="selected = undefined" />
  </div>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { getApiUsage } from '@/api/api-management-usage'
import { usageCategoryLabels } from '@/api/api-management-usage-validate'
import type { ApiUsageQuery, ApiUsageRow, UsageCategory } from '@/types/api-management-usage'
import { useUserStore } from '@/store/modules/user'
import { useAdminQuery } from './use-admin-query'
import ApiUsageDetail from './ApiUsageDetail.vue'
const dates = ref<string[] | null>(null), userId = ref(''), category = ref<UsageCategory | ''>(''), inputError = ref('')
const applied = ref<ApiUsageQuery>({}), page = ref(1), tab = ref('business'), selected = ref<ApiUsageRow>()
const allUsers = computed(() => useUserStore().info.roles?.some(role => ['super_admin', 'design_manager'].includes(role)))
const { data: report, loading, error, load } = useAdminQuery(() => getApiUsage({ ...applied.value, page: 1, pageSize: 1 }))
const pageRows = computed(() => report.value?.rows.slice((page.value - 1) * 8, page.value * 8) || [])
const percentage = (v: number | null) => v === null ? '无已知结果' : `${(v * 100).toFixed(1)}%`
const cards = computed(() => {
  const s = report.value?.summary, inventory = report.value?.inventory
  if (!s || !inventory) return []
  return tab.value === 'business' ? [
    { label: '新建任务', value: s.tasksCreated, note: '所选期间 · 创建事件' },
    { label: '正式生成版本', value: s.generatedVersions, note: '所选期间 · 发布事件' },
    { label: '手动采用记录', value: s.adoptions, note: '不含 API 自动发布' },
    { label: '当前原图库存', value: inventory.sourceImages, note: '当前快照 · 仅按创建人过滤' }
  ] : [
    { label: 'API 请求尝试', value: s.apiAttempts, note: '含首次请求与失败重试' },
    { label: '其中已知重试', value: s.apiRetries, note: '已包含在请求尝试内' },
    { label: 'CLI 真实启动', value: s.cliStarted, note: '不换算内部模型请求' },
    { label: 'CLI 提交轮次', value: s.cliSubmitted, note: '提交不等于启动' }
  ]
})
function query() {
  inputError.value = ''
  if (dates.value?.length === 2 && dates.value[0]! > dates.value[1]!) { inputError.value = '开始日期不能晚于结束日期'; return }
  applied.value = { from: dates.value?.[0], to: dates.value?.[1], userId: allUsers.value ? userId.value || undefined : undefined, category: category.value || undefined }
  page.value = 1; selected.value = undefined; void load()
}
function reset() { dates.value = null; userId.value = ''; category.value = ''; query() }
function openDay(row: ApiUsageRow) { selected.value = row }
</script>
<style scoped>
.usage-pagination { margin-top: 18px; justify-content: flex-end; }
.hx-footnote { line-height: 1.7; }
@media (max-width: 600px) { .hx-admin-table-head { gap: 8px; flex-wrap: wrap; } .hx-admin-query-row > .el-button { margin-left: 0; } }
</style>

