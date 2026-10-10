<template>
  <div class="hx-page">
    <div class="hx-heading">
      <div><span class="hx-eyebrow">EXECUTION HEALTH</span><h1>执行监控</h1><p>按 API 生图与 CLI 图片修改分别查看当前队列、执行和异常。</p></div>
      <ElButton :loading="loading" @click="refresh">刷新状态</ElButton>
    </div>
    <ElAlert class="hx-admin-banner" title="交互方案预览 · 以下全部为模拟状态与模拟任务，未读取真实服务。" type="warning" :closable="false" show-icon />
    <div class="hx-admin-toolbar">
      <div class="hx-admin-toolbar-copy"><span class="hx-admin-kicker">PREVIEW CONTROLS</span><span>切换场景检查显示；刷新仅重载模拟快照。</span></div>
      <ElSelect v-model="scenario" aria-label="监控模拟场景" style="width: 180px" :disabled="loading">
        <ElOption v-for="item in scenarios" :key="item.value" :label="item.label" :value="item.value" />
      </ElSelect>
    </div>
    <p class="hx-muted" role="status">{{ loading ? '正在重载模拟快照…' : '模拟快照：2026-10-10 14:30:00（北京时间）；刷新不会改变服务心跳。' }}</p>
    <ElAlert v-if="scenario === 'unknown'" title="模拟未知：业务数据库采集失败且服务心跳过期，队列数量与服务健康均未知。单独心跳过期不会抹掉已采集的数据库数量。未知不表示空闲或零任务。" type="warning" :closable="false" />
    <ElAlert v-if="scenario === 'abnormal'" title="模拟异常：API 请求限流等待重试；CLI 有执行结果待核实，保留现场。" type="error" :closable="false" />
    <div class="hx-admin-kpis">
      <ElCard v-for="item in summary" :key="item.label" class="art-card hx-admin-kpi">
        <div><span>{{ item.label }}</span><strong>{{ item.value }}</strong><small>{{ item.note }}</small></div>
      </ElCard>
    </div>
    <div class="hx-stack">
      <ElCard v-for="channel in channels" :key="channel.name" class="art-card hx-section">
        <div class="hx-admin-section-head">
          <div><span class="hx-admin-kicker">{{ channel.code }}</span><h2>{{ channel.name }}</h2><p>{{ channel.description }}</p></div>
          <ElTag :type="scenario === 'unknown' ? 'warning' : scenario === 'abnormal' ? 'danger' : 'success'">模拟 · {{ stateLabel }}</ElTag>
        </div>
        <ElTable :data="channel.metrics" table-layout="auto" aria-label="渠道执行数量">
          <ElTableColumn prop="phase" label="阶段" min-width="120" />
          <ElTableColumn prop="tasks" label="关联任务（套）" min-width="135" />
          <ElTableColumn prop="images" label="涉及图片（张）" min-width="135" />
          <ElTableColumn prop="note" label="统计口径" min-width="240" />
        </ElTable>
        <p class="hx-muted">服务心跳（模拟）：{{ scenario === 'unknown' ? '2026-10-10 13:45:00 · 已过期' : '2026-10-10 14:29:55' }}（北京时间）</p>
        <p class="hx-footnote">{{ channel.capacity }}；同套任务可能跨阶段、跨渠道出现，各行套数不能直接相加。</p>
      </ElCard>
      <ElCard class="art-card hx-section">
        <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">QUEUE & INCIDENTS</span><h2>需要关注的任务</h2><p>点击任务打开本地 API 任务概览；不会跳转或请求生产任务。</p></div><ElTag type="info">模拟 · {{ incidents.length }} 条已知记录</ElTag></div>
        <ElTable :data="incidents" :empty-text="scenario === 'unknown' ? '当前异常列表未知，无法确认是否存在其他异常' : '此模拟场景暂无异常任务'">
          <ElTableColumn label="任务" min-width="185"><template #default="{ row }"><ElButton type="primary" text @click="selected = row">{{ row.name }}</ElButton></template></ElTableColumn>
          <ElTableColumn prop="channel" label="执行渠道" min-width="145" />
          <ElTableColumn prop="state" label="状态" min-width="115" />
          <ElTableColumn prop="issue" label="原因 / 建议" min-width="260" />
        </ElTable>
      </ElCard>
    </div>
    <ElDrawer :model-value="!!selected" title="API 任务概览 · 模拟" size="min(560px, 100vw)" @close="selected = null">
      <template v-if="selected">
        <ElAlert title="仅展示本地模拟任务，不触发重试、生成或采用。" type="warning" :closable="false" />
        <h2 class="hx-gap">{{ selected.name }}</h2><p class="hx-muted">{{ selected.id }} · 操作者：示例设计师</p>
        <ElDescriptions :column="1" border>
          <ElDescriptionsItem label="业务归属">API 换套图任务</ElDescriptionsItem>
          <ElDescriptionsItem label="当前执行">{{ selected.channel }} · {{ selected.state }}</ElDescriptionsItem>
          <ElDescriptionsItem label="任务图片">{{ selected.total }} 张；本次涉及 {{ selected.affected }} 张</ElDescriptionsItem>
          <ElDescriptionsItem label="异常说明">{{ selected.issue }}</ElDescriptionsItem>
          <ElDescriptionsItem label="任务创建">2026-10-10 14:00:00（北京时间）</ElDescriptionsItem>
          <ElDescriptionsItem label="Token / 费用">未提供回执</ElDescriptionsItem>
        </ElDescriptions>
        <p class="hx-muted">任务、图片和执行次数独立计数。CLI 修改产生候选版本，采用后才成为正式图片。</p>
      </template>
    </ElDrawer>
  </div>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { ElAlert, ElButton, ElCard, ElDescriptions, ElDescriptionsItem, ElDrawer, ElOption, ElSelect, ElTable, ElTableColumn, ElTag } from 'element-plus'

type Scenario = 'normal' | 'abnormal' | 'unknown' | 'idle'
interface Incident { id: string; name: string; channel: string; state: string; issue: string; total: number; affected: number }
const scenario = ref<Scenario>('normal')
const loading = ref(false)
const selected = ref<Incident | null>(null)
let refreshTimer: ReturnType<typeof setTimeout> | undefined
const scenarios: { value: Scenario; label: string }[] = [
  { value: 'normal', label: '正常执行' }, { value: 'abnormal', label: '异常 / 等待重试' },
  { value: 'unknown', label: '数据源与心跳未知' }, { value: 'idle', label: '空闲' }
]
const stateLabel = computed(() => ({ normal: '正常执行', abnormal: '需要关注', unknown: '未知', idle: '空闲' })[scenario.value])
const count = (value: number) => scenario.value === 'unknown' ? '未知' : scenario.value === 'idle' ? 0 : value
const summary = computed(() => [
  { label: '总体状态', value: stateLabel.value, note: '模拟服务健康状态' },
  { label: '排队任务（去重）', value: count(4), note: '套 · 跨渠道按任务去重' },
  { label: '排队图片（去重）', value: count(21), note: '张 · 当前等待执行' },
  { label: '待核实图片', value: count(scenario.value === 'abnormal' ? 1 : 0), note: '张 · 不计入失败或成功' }
])
const channels = computed(() => [
  {
    name: 'API 生图', code: 'API GENERATION', description: '初始生成与 API 文字修改；图片级请求、退避和收图。',
    capacity: '只读配置示例：全站 5 套任务准入，每套最多 10 张图并行',
    metrics: [
      { phase: '排队', tasks: count(3), images: count(20), note: '等待任务准入的图片' },
      { phase: '运行', tasks: count(2), images: count(12), note: '图片请求正在执行' },
      { phase: '等待重试', tasks: count(scenario.value === 'abnormal' ? 1 : 0), images: count(scenario.value === 'abnormal' ? 2 : 0), note: '退避期间保留任务准入名额' },
      { phase: '收图', tasks: count(1), images: count(2), note: '结果已返回，正在校验入库' }
    ]
  },
  {
    name: 'CLI 图片修改', code: 'CLI IMAGE EDIT', description: 'API 成品上的多轮图片修改；执行轮次与候选版本分别记录。',
    capacity: '配置快照（2026-10-10 16:19 核查）：全站最多 5 个 CLI 图片修改轮次并发，同一图片会话串行；不等同 API 任务并发',
    metrics: [
      { phase: '排队', tasks: count(1), images: count(1), note: '等待 CLI 执行的修改轮次所关联图片' },
      { phase: '运行', tasks: count(scenario.value === 'abnormal' ? 0 : 1), images: count(scenario.value === 'abnormal' ? 0 : 1), note: 'CLI 轮次执行中的关联图片' },
      { phase: '等待重试', tasks: count(0), images: count(0), note: '仅统计确已进入重试等待的轮次' },
      { phase: '收图', tasks: count(0), images: count(0), note: '校验候选图片，不等同已采用' },
      { phase: '待核实', tasks: count(scenario.value === 'abnormal' ? 1 : 0), images: count(scenario.value === 'abnormal' ? 1 : 0), note: '终态未确认，保留现场不重复执行' }
    ]
  }
])
const incidents = computed<Incident[]>(() => scenario.value === 'abnormal' ? [
  { id: 'preview-api-1001', name: '手机主图换套 · 示例 A', channel: 'API 生图', state: '等待重试', issue: '请求限流；按冻结请求退避重试', total: 8, affected: 2 },
  { id: 'preview-api-1002', name: '手机详情换套 · 示例 B', channel: 'CLI 图片修改', state: '待核实', issue: '未收到明确终态；先核实原轮次结果', total: 12, affected: 1 }
] : [])
function refresh() {
  loading.value = true
  refreshTimer = setTimeout(() => { loading.value = false }, 650)
}
onBeforeUnmount(() => { if (refreshTimer) clearTimeout(refreshTimer) })
</script>
