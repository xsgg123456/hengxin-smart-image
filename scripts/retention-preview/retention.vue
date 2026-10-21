<template>
  <div class="hx-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">AUTOMATIC CLEANUP</span><h1>自动清理</h1><p>查看国内 CLI 会话的清理状态、到期计划和实际处理结果。</p></div><ElButton :loading="loading" @click="refresh">刷新状态</ElButton></div>
    <div class="hx-admin-toolbar">
      <div class="hx-admin-toolbar-copy"><ElTag type="warning" effect="plain">交互预览</ElTag><span>全部为模拟数据，不执行真实清理</span></div>
      <div class="hx-admin-toolbar-actions"><span class="hx-muted">预览场景</span><ElSelect v-model="scenario" aria-label="预览场景" style="width:170px"><ElOption v-for="s in scenarios" :key="s.value" :label="s.label" :value="s.value" /></ElSelect></div>
    </div>
    <div class="hx-detail-toolbar hx-gap"><span class="hx-footnote" role="status">数据更新时间：{{ updated }} · 北京时间 · 模拟快照</span><div><span class="hx-muted">每 15 秒刷新</span><ElSwitch v-model="auto" aria-label="自动刷新" /></div></div>
    <ElAlert v-if="scenario === 'unknown'" title="数据读取失败，无法确认服务与清理数量。请稍后刷新。" type="error" :closable="false" show-icon />
    <ElSkeleton v-if="loading || scenario === 'loading'" :rows="12" animated class="hx-gap" />
    <template v-else>
      <ElCard class="art-card hx-section">
        <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">SERVICE STATUS</span><h2>清理服务</h2><p>闲置 24 小时清缓存 · 连续闲置 3 天清历史 · 每小时扫描，单轮最多 25 个会话</p></div><ElTag :type="statusType" effect="light">{{ serviceState }}</ElTag></div>
        <ElAlert v-if="scenario === 'offline'" title="超过 2 分钟未收到心跳，请检查清理服务。下方为最后一次已知清理记录。" type="warning" :closable="false" show-icon class="hx-gap" />
        <ElAlert v-if="scenario === 'error'" title="服务在线，但有 1 个会话清理失败，将自动重试。" type="warning" :closable="false" show-icon />
        <ElDescriptions :column="compact ? 1 : 3" class="hx-gap">
          <ElDescriptionsItem label="策略开关">已启用</ElDescriptionsItem>
          <ElDescriptionsItem label="最近心跳">{{ unknown ? '未知' : scenario === 'offline' ? '14:42:00（已超时）' : '14:49:50' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="本轮状态">{{ unknown ? '未知' : scenario === 'scanning' ? '扫描中 · 尚未结束' : '扫描已结束' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="最近扫描开始">{{ unknown ? '未知' : '今天 14:48:30' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="最近扫描结束">{{ unknown ? '未知' : scenario === 'scanning' ? '—' : '今天 14:48:42' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="下次预计扫描">{{ unknown || scenario === 'offline' ? '待确认' : scenario === 'scanning' ? '本轮结束后约 1 小时' : '今天 15:48:42' }}</ElDescriptionsItem>
        </ElDescriptions>
        <p class="hx-footnote">查看与刷新不会续期；正在执行或状态待核实的会话暂缓清理。已超过 3 天的旧会话直接进入下一轮扫描，不再增加宽限期。</p>
      </ElCard>
      <div class="hx-admin-kpis">
        <ElCard v-for="kpi in kpis" :key="kpi.label" class="art-card hx-admin-kpi"><div><span>{{ kpi.label }}</span><strong>{{ kpi.value }}</strong><small>{{ kpi.note }}</small></div></ElCard>
      </div>
      <ElCard class="art-card hx-section hx-admin-table-card">
        <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">CLEANUP ACTIVITY</span><h2>清理明细</h2><p>每一条记录对应一个会话的处理结果，失败与暂缓不计入成功数量。</p></div><ElButton @click="policy = true">查看保留规则</ElButton></div>
        <ElTabs v-model="tab"><ElTabPane label="清理记录" name="history" /><ElTabPane :label="`待清理${unknown ? '' : `（${waiting.length}）`}`" name="pending" /></ElTabs>
        <div class="hx-admin-query-row hx-gap" style="margin-bottom:18px">
          <ElInput v-model="keyword" clearable placeholder="搜索任务名称或会话编号" aria-label="搜索任务" style="width:240px" />
          <ElSelect v-model="kind" aria-label="清理类型" placeholder="全部类型" style="width:140px"><ElOption label="全部类型" value="" /><ElOption label="缓存" value="缓存" /><ElOption label="会话历史" value="会话历史" /></ElSelect>
          <ElSelect v-model="result" aria-label="处理结果" placeholder="全部结果" style="width:165px"><ElOption label="全部结果" value="" /><ElOption v-for="s in resultOptions" :key="s" :label="s" :value="s" /></ElSelect>
          <ElDatePicker v-model="dates" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" range-separator="至" aria-label="时间范围" style="max-width:100%" />
          <ElButton @click="reset">重置</ElButton>
        </div>
        <ElTable :data="filtered" :empty-text="unknown ? '读取失败，记录数量未知' : '暂无符合条件的记录'" row-key="id">
          <ElTableColumn label="任务 / 会话" min-width="210"><template #default="{row}"><div class="hx-table-name"><div><strong>{{ row.task }}</strong><small>第 {{ row.image }} 张 · {{ row.id }}{{ row.deleted ? ' · 任务已删除' : '' }}</small></div></div></template></ElTableColumn>
          <ElTableColumn prop="kind" label="清理类型" width="100" />
          <ElTableColumn label="处理结果" width="130"><template #default="{row}"><ElTag :type="tagType(row.result)">{{ row.result }}</ElTag></template></ElTableColumn>
          <ElTableColumn :label="tab === 'history' ? '处理时间' : '到期时间'" min-width="165"><template #default="{row}">{{ tab === 'history' ? row.time : row.due }}</template></ElTableColumn>
          <ElTableColumn :label="tab === 'history' ? '处理摘要' : '当前说明'" min-width="200"><template #default="{row}"><span>{{ row.detail }}</span></template></ElTableColumn>
          <ElTableColumn label="操作" width="75" fixed="right"><template #default="{row}"><ElButton link type="primary" @click="selected = row">详情</ElButton></template></ElTableColumn>
        </ElTable>
        <p class="hx-footnote">{{ unknown ? '记录数量未知' : `共 ${filtered.length} 条` }} · 时间均为北京时间 · 明细保留 90 天，累计统计长期保留 · 统计起算：2026-10-20（模拟）</p>
      </ElCard>
    </template>
    <RetentionDetail :row="selected" @close="selected = null" />
    <ElDrawer v-model="policy" title="会话清理与数据保留" size="min(520px, 100vw)">
      <ElDescriptions :column="1" border><ElDescriptionsItem label="24 小时">清理会话私有缓存与插件，保留聊天历史。</ElDescriptionsItem><ElDescriptionsItem label="72 小时">清理会话执行目录、聊天、事件、提示词及无引用候选图与标注。</ElDescriptionsItem><ElDescriptionsItem label="有效活动">提交、回复、重试、采用和执行结束会重新计时。</ElDescriptionsItem><ElDescriptionsItem label="只读访问">查看、刷新和轮询不续期。</ElDescriptionsItem><ElDescriptionsItem label="持续保留">正式成品、版本、归档、原图、素材及用量汇总。</ElDescriptionsItem><ElDescriptionsItem label="旧会话">已闲置超过 3 天的在下一轮开始清理，不额外给宽限。</ElDescriptionsItem></ElDescriptions>
      <p class="hx-muted hx-gap">活动中的会话受保护；失败保留状态并自动重试。超过单轮 25 个的清理对象分批处理。</p>
    </ElDrawer>
  </div>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElAlert, ElButton, ElCard, ElDatePicker, ElDescriptions, ElDescriptionsItem, ElDrawer, ElInput, ElOption, ElSelect, ElSkeleton, ElSwitch, ElTable, ElTableColumn, ElTabs, ElTabPane, ElTag } from 'element-plus'
import RetentionDetail from './RetentionDetail.vue'
import { failure, pending, records, scenarios, tagType, type CleanupRow, type Scenario } from './retention-data'
const scenario = ref<Scenario>('normal'), loading = ref(false), auto = ref(true), policy = ref(false)
const selected = ref<CleanupRow|null>(null), tab = ref('history'), keyword = ref(''), kind = ref(''), result = ref('')
const dates = ref<[string,string]|null>(null), updated = ref('2026-10-21 14:50:00'), compact = ref(window.innerWidth < 1000)
const unknown = computed(() => scenario.value === 'unknown')
const history = computed(() => unknown.value || scenario.value === 'empty' ? [] : scenario.value === 'error' ? [failure,...records] : records)
const waiting = computed(() => unknown.value || scenario.value === 'empty' ? [] : scenario.value === 'error' ? [failure,records[2],...pending] : [records[2],...pending])
const resultOptions = computed(() => [...new Set((tab.value === 'history' ? history.value : waiting.value).map(row => row.result))])
const filtered = computed(() => (tab.value === 'history' ? history.value : waiting.value).filter(row =>
  (!keyword.value || `${row.task} ${row.id}`.toLowerCase().includes(keyword.value.trim().toLowerCase())) &&
  (!kind.value || row.kind === kind.value) && (!result.value || row.result === result.value) &&
  (!dates.value || ((tab.value === 'history' ? row.time : row.due).slice(0,10) >= dates.value[0] && (tab.value === 'history' ? row.time : row.due).slice(0,10) <= dates.value[1]))))
const serviceState = computed(() => ({normal:'在线 · 等待下轮扫描',scanning:'在线 · 正在扫描',error:'在线 · 有清理异常',offline:'心跳超时',unknown:'状态未知',empty:'在线 · 暂无到期会话',loading:'读取中'})[scenario.value])
const statusType = computed(() => unknown.value ? 'info' : ['error','offline'].includes(scenario.value) ? 'warning' : 'success')
const kpis = computed(() => [
  {label:'今日缓存清理成功',value:unknown.value?'未知':scenario.value==='empty'?0:2,note:`累计 ${unknown.value?'未知':scenario.value==='empty'?0:2} 次`},
  {label:'今日历史清理成功',value:unknown.value?'未知':scenario.value==='empty'?0:1,note:`累计 ${unknown.value?'未知':scenario.value==='empty'?0:2} 次 · 文件回收中不计入`},
  {label:'失败待重试',value:unknown.value?'未知':scenario.value==='error'?1:0,note:scenario.value==='error'?'预计今天 15:48 再试':'当前待重试会话数'},
  {label:'已到期待处理',value:unknown.value?'未知':scenario.value==='empty'?0:scenario.value==='error'?3:2,note:unknown.value?'到期会话状态待确认':scenario.value==='empty'?'暂无到期会话':'含 1 个受保护会话、1 个文件回收中'}
])
let timer: ReturnType<typeof setInterval> | undefined, delay: ReturnType<typeof setTimeout> | undefined
function reset() { keyword.value=''; kind.value=''; result.value=''; dates.value=null }
function refresh() {
  if (loading.value || scenario.value === 'loading') return
  loading.value=true
  delay=setTimeout(() => { loading.value=false; updated.value=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',dateStyle:'short',timeStyle:'medium'}).format(new Date()) },450)
}
function resize() { compact.value=window.innerWidth<1000 }
watch(tab, reset)
watch(scenario, () => { clearTimeout(delay); loading.value=false; reset(); selected.value=null })
onMounted(() => { window.addEventListener('resize',resize); timer=setInterval(() => { if(auto.value && !document.hidden) refresh() },15000) })
onBeforeUnmount(() => { clearInterval(timer); clearTimeout(delay); window.removeEventListener('resize',resize) })
</script>
