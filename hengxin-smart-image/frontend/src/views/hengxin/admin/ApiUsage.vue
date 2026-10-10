<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">EXECUTION INSIGHTS</span><h1>调用统计</h1><p>{{ report ? (report.scope === 'all' ? '全员 · ' : '个人 · ') : '' }}API 业务统计 · 北京时间自然日</p></div></div>
    <ElCard class="art-card hx-section hx-admin-query-card">
      <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">FILTERS</span><h2>统计范围</h2><p>累计统计每次成功生成的图片，首次生成与修改生成分别展示。</p></div><ElTag type="info" effect="plain">{{ applied.from ? `${applied.from} — ${applied.to}` : '全部时间' }}</ElTag></div>
      <div class="hx-admin-query-row">
        <ElDatePicker v-model="dates" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期（不限）" end-placeholder="结束日期（不限）" aria-label="统计日期范围" />
        <ElSelect v-if="allUsers" v-model="userId" clearable placeholder="全部人员" aria-label="统计人员" style="width: 180px"><ElOption v-for="user in report?.users || []" :key="user.id" :value="user.id" :label="user.name" /></ElSelect>
        <ElSelect v-model="generationType" clearable placeholder="全部生成类型" aria-label="生成类型" style="width: 190px"><ElOption v-for="(label, key) in generationLabels" :key="key" :value="key" :label="label" /></ElSelect>
        <ElButton type="primary" :loading="loading" @click="query">查询统计</ElButton><ElButton :disabled="loading" @click="reset">重置</ElButton>
      </div>
      <p class="hx-footnote">点击查询应用筛选；汇总覆盖全部筛选结果，不随分页变化。历史按实际操作者筛选。</p>
      <ElAlert v-if="inputError" :title="inputError" type="warning" :closable="false" />
      <ElSkeleton v-if="loading" :rows="8" animated aria-label="正在读取统计数据" />
      <ElAlert v-else-if="error" :title="error" type="error" :closable="false"><ElButton text type="primary" @click="load">重试加载</ElButton></ElAlert>
      <template v-else-if="report">
        <ElTabs v-model="tab"><ElTabPane label="业务成果" name="business" /><ElTabPane label="执行消耗" name="execution" /></ElTabs>
        <div class="hx-admin-kpis"><ElCard v-for="(card, index) in cards" :key="card.label" class="art-card hx-admin-kpi" :class="`hx-admin-kpi-${index}`"><div><span>{{ card.label }}</span><strong>{{ card.value }}</strong><small>{{ card.note }}</small></div></ElCard></div>
        <div v-if="tab === 'business'" class="hx-admin-summary"><div><span class="hx-admin-kicker">TOTAL OUTPUT</span><strong>首次生成 {{ report.summary.initialImages }} 张 + 修改生成 {{ report.summary.modifiedImages }} 张 = 累计 {{ report.summary.totalGeneratedImages }} 张</strong></div><p>修改生成包含 API 改图和 CLI 改图，每次成功产出新图均计入累计。</p><small>采用已有结果、恢复已有版本不重复增加；失败与上传素材不计入生成图片。</small></div>
        <div v-else class="hx-admin-summary"><div><span class="hx-admin-kicker">SUCCESS & UNKNOWN</span><strong>请求与生成图片分别统计</strong></div><p>API 请求成功率 {{ percentage(report.summary.requestSuccessRate) }} · 已知成功 {{ report.summary.apiSucceeded }} / 失败 {{ report.summary.apiFailed }} / 未知 {{ report.summary.apiUnknown }} / 在途 {{ report.summary.apiRunning }}</p><p>CLI 已证实启动 {{ report.summary.cliStarted }} · 启动证据不足 {{ report.summary.cliUnverified }} · 成功完成 {{ report.summary.cliSucceeded }} / 失败 {{ report.summary.cliFailed }} / 待核实 {{ report.summary.cliUnknown }}</p><small>API 成功率仅以已知成功和失败请求为分母；未知与在途不入分母。CLI 正常澄清文字完成不算生图失败；内部模型请求数未提供，不按轮次折算。</small></div>
        <p v-if="tab === 'execution'" class="hx-footnote">正式生成版本 {{ report.summary.generatedVersions }} · 来源待核实版本 {{ report.summary.unverifiedVersions }}（不计生成或采用） · CLI 候选 {{ report.summary.cliCandidates }} · 手动采用 {{ report.summary.adoptions }} · 恢复版本 {{ report.summary.restores }}。候选不等于采用，恢复不增加生成或模型调用。</p>
        <p v-if="tab === 'business'" class="hx-footnote">来源待核实版本 {{ report.summary.unverifiedVersions }}（来源待核实、未计入累计）。</p>
        <p class="hx-footnote">历史归属未核实 {{ report.summary.unverifiedAttribution }} 条；重试属性未知 {{ report.summary.apiRetryUnknown }} 条。Token 输入 / 输出：未提供；费用：未提供。</p>
        <div class="hx-admin-table-head"><div><span class="hx-admin-kicker">DAILY BREAKDOWN</span><strong>人员每日明细</strong></div><span class="hx-muted">共 {{ report.rows.length }} 条汇总记录</span></div>
        <ElTable :data="pageRows" class="hx-admin-table" empty-text="此范围暂无统计记录" style="width: 100%">
          <ElTableColumn prop="date" label="日期" min-width="120" /><ElTableColumn prop="userName" label="实际操作者 / 历史登记人" min-width="170" />
          <template v-if="tab === 'business'"><ElTableColumn prop="summary.initialImages" label="首次生成" min-width="110" /><ElTableColumn prop="summary.modifiedImages" label="修改生成" min-width="110" /><ElTableColumn prop="summary.totalGeneratedImages" label="合计生成" min-width="110" /></template>
          <template v-else><ElTableColumn prop="summary.apiAttempts" label="API 请求" min-width="100" /><ElTableColumn prop="summary.apiRetries" label="其中重试" min-width="100" /><ElTableColumn prop="summary.cliSubmitted" label="CLI 提交" min-width="100" /><ElTableColumn prop="summary.cliStarted" label="CLI 真启动" min-width="110" /><ElTableColumn prop="summary.cliUnverified" label="启动证据不足" min-width="120" /></template>
          <ElTableColumn label="操作" width="110" fixed="right"><template #default="{ row }"><ElButton text type="primary" @click="openDay(row)">查看明细</ElButton></template></ElTableColumn>
        </ElTable>
        <ElPagination v-if="report.rows.length" v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[20, 50, 100]" :total="report.rows.length" layout="total, sizes, prev, pager, next" @size-change="page = 1" class="usage-pagination" aria-label="每日明细分页" />
      </template>
    </ElCard>
    <ApiUsageDetail v-if="selected" :key="`${selected.date}-${selected.userId}-${applied.generationType}-${tab}`" :row="selected" :generation-type="applied.generationType" :outputs-only="tab === 'business'" @close="selected = undefined" />
  </div>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getApiUsage } from '@/api/api-management-usage'
import { generationLabels } from '@/api/api-management-usage-validate'
import type { ApiUsageQuery, ApiUsageRow, GenerationType } from '@/types/api-management-usage'
import { useUserStore } from '@/store/modules/user'
import { useAdminQuery } from './use-admin-query'
import ApiUsageDetail from './ApiUsageDetail.vue'
const dates = ref<string[] | null>(null), userId = ref(''), generationType = ref<GenerationType | ''>(''), inputError = ref('')
const applied = ref<ApiUsageQuery>({}), page = ref(1), pageSize = ref(20), tab = ref('business'), selected = ref<ApiUsageRow>()
const allUsers = computed(() => useUserStore().info.roles?.some(role => ['super_admin', 'design_manager'].includes(role)))
const { data: report, loading, error, load } = useAdminQuery(() => getApiUsage({ ...applied.value, outputsOnly: tab.value === 'business', page: 1, pageSize: 1 }))
const pageRows = computed(() => report.value?.rows.slice((page.value - 1) * pageSize.value, page.value * pageSize.value) || [])
const percentage = (v: number | null) => v === null ? '无已知结果' : `${(v * 100).toFixed(1)}%`
const cards = computed(() => {
  const s = report.value?.summary
  if (!s) return []
  return tab.value === 'business' ? [
    { label: '累计生成图片', value: s.totalGeneratedImages, note: '首次生成 + 修改生成 · 张' },
    { label: '首次生成图片', value: s.initialImages, note: '首次成功产出 · 张' },
    { label: '修改生成图片', value: s.modifiedImages, note: 'API 与 CLI 修改成功产出 · 张' },
    { label: '生成任务数', value: s.generatedTasks, note: '当前范围有成功产出的任务 · 套' }
  ] : [
    { label: 'API 请求', value: s.apiAttempts, note: '包含首次请求与重试 · 次' },
    { label: '其中重试', value: s.apiRetries, note: '已包含在请求内 · 次' },
    { label: 'API 失败', value: s.apiFailed, note: '失败请求不计生成图片 · 次' },
    { label: 'CLI 修改轮次', value: s.cliStarted, note: '已证实启动 · 不折算内部模型请求 · 轮' }
  ]
})
function query() {
  inputError.value = ''
  if (dates.value?.length === 2 && dates.value[0]! > dates.value[1]!) { inputError.value = '开始日期不能晚于结束日期'; return }
  applied.value = { from: dates.value?.[0], to: dates.value?.[1], userId: allUsers.value ? userId.value || undefined : undefined, generationType: generationType.value || undefined }
  page.value = 1; selected.value = undefined; void load()
}
function reset() { dates.value = null; userId.value = ''; generationType.value = ''; query() }
watch(tab, () => { page.value = 1; selected.value = undefined; void load() })
function openDay(row: ApiUsageRow) { selected.value = row }
</script>
<style scoped>
.usage-pagination { margin-top: 18px; justify-content: flex-end; flex-wrap: wrap; gap: 8px; }
.hx-footnote { line-height: 1.7; }
@media (max-width: 600px) { .hx-admin-table-head { gap: 8px; flex-wrap: wrap; } .hx-admin-query-row > .el-button { margin-left: 0; } }
</style>

