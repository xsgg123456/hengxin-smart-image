<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">EXECUTION INSIGHTS</span><h1>调用统计</h1><p>{{ personal ? '个人 · 设计师甲' : '全员' }}统计预览 · 北京时间自然日</p></div></div>
    <ElAlert class="hx-admin-banner" title="交互预览 · 全部为确定性模拟数据，不代表线上实时统计；Token 和费用未提供。" type="warning" :closable="false" show-icon />
    <div class="hx-admin-toolbar">
      <div class="hx-admin-toolbar-copy">预览场景</div>
      <div class="hx-admin-toolbar-actions">
        <ElSelect v-if="isManager" v-model="scope" aria-label="预览统计视角" style="width: 200px"><ElOption label="全员视角" value="all" /><ElOption label="个人视角 · 设计师甲" value="self" /></ElSelect>
        <ElSelect v-model="scenario" aria-label="统计预览场景" style="width: 160px"><ElOption v-for="(label, key) in scenarios" :key="key" :label="label" :value="key" /></ElSelect>
      </div>
    </div>
    <ElCard class="art-card hx-section hx-admin-query-card preview-main">
      <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">FILTERS</span><h2>统计范围</h2><p>任务按创建日、执行按开始日、候选按产出日、正式版本按发布日、采用按采用日计数。</p></div><ElTag type="info" effect="plain">模拟区间 10月1日—10日</ElTag></div>
      <div class="hx-admin-query-row">
        <ElDatePicker v-model="dates" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" aria-label="统计日期范围" />
        <ElSelect v-if="!personal" v-model="person" clearable placeholder="全部人员" aria-label="统计人员" style="width: 170px"><ElOption v-for="name in people" :key="name" :label="name" :value="name" /></ElSelect>
        <ElSelect v-model="kind" clearable placeholder="全部执行类型" aria-label="执行类型" style="width: 185px"><ElOption v-for="(label, key) in kindLabels" :key="key" :label="label" :value="key" /></ElSelect>
        <ElButton type="primary" @click="query">查询统计</ElButton><ElButton @click="reset">重置</ElButton>
      </div>
      <p class="hx-footnote">筛选即时生效；汇总覆盖全部筛选结果，不随分页变化。当前库存只随人员变化，不受历史日期及执行类型影响。</p>
      <ElSkeleton v-if="scenario === 'loading'" :rows="8" animated aria-label="正在读取统计数据" />
      <ElAlert v-else-if="scenario === 'error'" title="模拟读取失败：暂时无法取得统计摘要" type="error" :closable="false"><ElButton text type="primary" @click="scenario = 'normal'">重试加载</ElButton></ElAlert>
      <template v-else>
        <ElTabs v-model="tab">
          <ElTabPane label="业务成果" name="business" /><ElTabPane label="执行消耗" name="execution" />
        </ElTabs>
        <div class="hx-admin-kpis"><ElCard v-for="(card, index) in cards" :key="card.label" class="art-card hx-admin-kpi" :class="`hx-admin-kpi-${index}`"><div><span>{{ card.label }}</span><strong>{{ card.value }}</strong><small>{{ card.note }}</small></div></ElCard></div>
        <div v-if="tab === 'business'" class="hx-admin-summary"><div><span class="hx-admin-kicker">CURRENT INVENTORY</span><strong>当前库存 · 模拟快照 2026-10-10 18:00</strong></div><p>{{ inventory.length }} 套任务 · 原图总数 {{ inventoryImages }} · 当前成功结果 {{ inventoryImages }} · 失败 0 · 待处理 0</p><small>本快照模拟当前全部原图均有可用结果；历史修改失败不抹掉已有结果。历史生成版本与采用记录属于累计发生量，同一图片修改或重复采用可能产生多条记录，不能相加为库存。</small></div>
        <div v-else class="hx-admin-summary"><div><span class="hx-admin-kicker">SUCCESS & UNKNOWN</span><strong>成功率与待核实</strong></div><p>API 请求成功率 {{ requestRate }} · 当前图片交付成功率 {{ deliveryRate }}</p><p>API 已知成功 {{ summary.requestSuccess }} / 失败 {{ summary.requestFailed }} / 待核实 {{ summary.requestUnknown }} · 当前图片待核实 0（模拟快照）</p><small>API 成功率 = 成功请求 / 已知结果请求（含重试）；当前交付成功率 = 当前成功图片 / 当前成功与失败图片，仅按人员过滤，与历史执行筛选独立。CLI 候选成功不等于交付或采用。待核实不计分母。CLI 内部请求数未提供，不按轮次折算。</small></div>
        <p class="hx-footnote">{{ tab === 'business' ? '正式版本包含 API 自动发布及 CLI 手动采用后的发布；CLI 候选独立计数，采用只统计 CLI 手动采用。按执行类型筛选时，新建任务只归属于首次生成。' : '请求尝试包含首次请求与失败重试；CLI 轮次独立计数。Token 输入 / 输出：未提供；费用：未提供。' }}</p>
        <div class="hx-admin-table-head"><div><span class="hx-admin-kicker">DAILY BREAKDOWN</span><strong>人员每日明细</strong></div><span class="hx-muted">共 {{ rows.length }} 条</span></div>
        <ElTable :data="pageRows" class="hx-admin-table" empty-text="此范围暂无统计记录" style="width: 100%">
          <ElTableColumn prop="day" label="日期" min-width="120" /><ElTableColumn prop="user" label="实际操作者" min-width="120" />
          <template v-if="tab === 'business'"><ElTableColumn prop="created" label="新建任务" min-width="100" /><ElTableColumn prop="versions" label="正式版本" min-width="100" /><ElTableColumn prop="candidates" label="CLI 候选" min-width="100" /><ElTableColumn prop="adopted" label="手动采用" min-width="100" /></template>
          <template v-else><ElTableColumn prop="summary.requests" label="API 请求" min-width="100" /><ElTableColumn prop="summary.retries" label="其中重试" min-width="100" /><ElTableColumn prop="summary.cliRounds" label="CLI 轮次" min-width="100" /></template>
          <ElTableColumn label="操作" width="110" fixed="right"><template #default="{ row }"><ElButton text type="primary" @click="openDay(row)">展开明细</ElButton></template></ElTableColumn>
        </ElTable>
        <ElPagination v-if="rows.length" v-model:current-page="page" :page-size="8" :total="rows.length" layout="prev, pager, next" class="preview-pagination" aria-label="每日明细分页" />
      </template>
    </ElCard>
    <ElDrawer v-model="detailOpen" title="人员每日调用明细 · 模拟" size="min(1050px, 96vw)" destroy-on-close>
      <template v-if="selected">
        <div class="hx-drawer-intro"><span class="hx-admin-kicker">{{ selected.day }}</span><strong>{{ selected.user }}</strong><p>包含当日开始、产出或采用的执行；每项指标仅计其对应事件日期。</p></div>
        <ElTable :data="selected.details" empty-text="当日仅创建任务，尚无执行记录">
          <ElTableColumn label="关联任务" min-width="150"><template #default="{ row }"><ElButton text type="primary" @click="openTask(row.taskId)">{{ row.taskId }}</ElButton></template></ElTableColumn>
          <ElTableColumn label="执行类型" min-width="150"><template #default="{ row }">{{ kindLabels[row.kind as ExecutionKind] }}</template></ElTableColumn>
          <ElTableColumn prop="date" label="开始日期" min-width="120" /><ElTableColumn label="产出日期" min-width="120"><template #default="{ row }">{{ row.outputDate || '尚无产出' }}</template></ElTableColumn><ElTableColumn label="发布日期" min-width="120"><template #default="{ row }">{{ row.publishedDate || '尚未发布' }}</template></ElTableColumn><ElTableColumn label="采用日期" min-width="120"><template #default="{ row }">{{ row.kind === 'cli' ? row.adoptedDate || '尚未采用' : '不适用' }}</template></ElTableColumn>
          <ElTableColumn prop="requests" label="API 请求" width="100" /><ElTableColumn prop="retries" label="重试" width="80" /><ElTableColumn prop="cliRounds" label="CLI 轮次" width="100" />
          <ElTableColumn prop="versions" label="正式版本" width="100" /><ElTableColumn prop="candidates" label="CLI 候选" min-width="100" /><ElTableColumn prop="adopted" label="手动采用" width="100" />
          <ElTableColumn prop="unknown" label="待核实图片" width="110" />
        </ElTable>
        <p class="hx-footnote">以上数值为每条执行的完整记录，跨日事件不会全部计入当日汇总。每条 CLI 记录代表一轮图片修改对话。CLI 记录的 API 请求数 0 表示未记录 API 调用，其内部请求数未提供。</p>
      </template>
    </ElDrawer>
    <ElDrawer v-model="taskOpen" title="关联任务概览 · 本地模拟" size="min(640px, 96vw)" append-to-body destroy-on-close>
      <template v-if="task">
        <div class="hx-drawer-intro"><span class="hx-admin-kicker">{{ task.id }}</span><strong>{{ task.name }}</strong><p>全部为预览数据，无真实图片文件。</p></div>
        <ElDescriptions :column="1" border><ElDescriptionsItem label="所属人员">{{ task.owner }}</ElDescriptionsItem><ElDescriptionsItem label="创建日期">{{ task.created }}</ElDescriptionsItem><ElDescriptionsItem label="当前图片">{{ task.currentImages }} 张</ElDescriptionsItem><ElDescriptionsItem label="历史正式版本">{{ taskSummary.versions }}</ElDescriptionsItem><ElDescriptionsItem label="历史CLI候选">{{ taskSummary.candidates }}</ElDescriptionsItem><ElDescriptionsItem label="历史手动采用">{{ taskSummary.adopted }}</ElDescriptionsItem><ElDescriptionsItem label="API 请求 / 重试">{{ taskSummary.requests }} / {{ taskSummary.retries }}</ElDescriptionsItem><ElDescriptionsItem label="CLI 修改轮次">{{ taskSummary.cliRounds }}</ElDescriptionsItem><ElDescriptionsItem label="Token / 费用">未提供 / 未提供</ElDescriptionsItem></ElDescriptions>
        <p class="hx-footnote">任务概览展示该任务完整历史，不受外层日期和执行类型过滤。返回关闭此抽屉即可保留每日明细。</p>
      </template>
    </ElDrawer>
  </div>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElAlert, ElButton, ElCard, ElDatePicker, ElDescriptions, ElDescriptionsItem, ElDrawer, ElOption, ElPagination, ElSelect, ElSkeleton, ElTabPane, ElTable, ElTableColumn, ElTabs, ElTag } from 'element-plus'
import { useUserStore } from '@/store/modules/user'
import { aggregate, buildUsage, kindLabels, people, percentage, previewTasks, usageEvents } from './usage-data'
import type { ExecutionKind, PreviewTask, UsageDailyRow } from './usage-data'
const store = useUserStore()
const isManager = computed(() => store.info.roles?.some(role => ['super_admin', 'design_manager'].includes(role)) ?? false)
const scope = ref('all'), personal = computed(() => !isManager.value || scope.value === 'self')
const scenarios = { normal: '正常数据', loading: '正在加载', empty: '空记录', error: '读取失败' }
const scenario = ref<keyof typeof scenarios>('normal'), tab = ref('business')
const dates = ref<string[] | null>(null), person = ref(''), kind = ref<ExecutionKind | ''>(''), page = ref(1)
const report = computed(() => buildUsage({ from: dates.value?.[0], to: dates.value?.[1], user: personal.value ? '设计师甲' : person.value, kind: kind.value }))
const empty = computed(() => scenario.value === 'empty')
const inventory = computed(() => empty.value ? [] : report.value.inventory)
const inventoryImages = computed(() => inventory.value.reduce((sum, t) => sum + t.currentImages, 0))
const rows = computed(() => empty.value ? [] : report.value.rows)
const pageRows = computed(() => rows.value.slice((page.value - 1) * 8, page.value * 8))
const summary = computed(() => empty.value ? aggregate([]) : report.value.summary)
const requestRate = computed(() => percentage(summary.value.requestSuccess, summary.value.requestSuccess + summary.value.requestFailed))
const deliveryRate = computed(() => percentage(inventoryImages.value, inventoryImages.value))
const cards = computed(() => tab.value === 'business' ? [
  { label: '新建任务', value: empty.value ? 0 : report.value.created, note: '所选期间 · 创建事件' },
  { label: '历史正式版本', value: empty.value ? 0 : report.value.versions, note: '所选期间 · 发布事件' },
  { label: 'CLI 候选版本', value: empty.value ? 0 : report.value.candidates, note: '所选期间 · 候选产出事件' },
  { label: '历史手动采用', value: empty.value ? 0 : report.value.adopted, note: '所选期间 · 采用事件' },
  { label: '当前图片库存', value: inventoryImages.value, note: '当前快照 · 仅按人员过滤' }
] : [
  { label: 'API 请求尝试', value: summary.value.requests, note: '含首次请求与重试' },
  { label: '其中失败重试', value: summary.value.retries, note: '包含在请求尝试内' },
  { label: 'CLI 修改轮次', value: summary.value.cliRounds, note: '不换算模型内部请求' },
  { label: '执行记录数', value: summary.value.executions, note: '首次、修改与 CLI 执行' }
])
const selected = ref<UsageDailyRow>(), detailOpen = ref(false), task = ref<PreviewTask>(), taskOpen = ref(false)
const taskSummary = computed(() => aggregate(usageEvents.filter(e => e.taskId === task.value?.id)))
watch([dates, person, kind, scope, scenario, personal], () => { page.value = 1; detailOpen.value = false; taskOpen.value = false })
function query() { scenario.value = 'normal'; page.value = 1 }
function reset() { dates.value = null; person.value = ''; kind.value = ''; query() }
function openDay(row: UsageDailyRow) { selected.value = row; detailOpen.value = true }
function openTask(id: string) { task.value = previewTasks.find(t => t.id === id && (!personal.value || t.owner === '设计师甲')); taskOpen.value = Boolean(task.value) }
</script>
<style scoped>
.preview-main { margin-top: 18px; }
.preview-pagination { margin-top: 18px; justify-content: flex-end; }
.hx-footnote { line-height: 1.7; }
@media (max-width: 600px) {
  .hx-admin-table-head { gap: 8px; flex-wrap: wrap; }
  .hx-admin-query-row > .el-button { margin-left: 0; }
}
</style>
