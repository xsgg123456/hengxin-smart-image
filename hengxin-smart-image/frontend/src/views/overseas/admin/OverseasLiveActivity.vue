<template>
  <div>
    <div class="hx-admin-kpis"><ElCard v-for="item in cards" :key="item.label" class="art-card hx-admin-kpi"><div><span>{{ item.label }}</span><strong>{{ item.value }}</strong><small>当前可见筛选范围</small></div></ElCard></div>
    <ElCard class="art-card hx-section hx-admin-table-card">
      <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">EXECUTION STATUS</span><h2>{{ page === 'usage' ? '任务与执行统计' : '当前执行状态' }}</h2><p>按作业创建时间筛选；人工等待不占并发，待核实作业单列且占用槽位。</p></div><ElButton :loading="loading" @click="load">刷新统计</ElButton></div>
      <div class="hx-filter">
        <ElInput v-model="query.taskId" class="hx-search" aria-label="任务 ID" placeholder="任务 ID" clearable />
        <ElSelect v-model="query.kind" aria-label="执行类型" placeholder="全部类型" clearable style="width:160px"><ElOption v-for="(label,key) in kinds" :key="key" :value="key" :label="label" /></ElSelect>
        <ElSelect v-model="query.status" aria-label="执行状态" placeholder="全部状态" clearable style="width:160px"><ElOption v-for="(label,key) in statuses" :key="key" :value="key" :label="label" /></ElSelect>
        <ElDatePicker v-model="from" type="datetime" aria-label="开始时间" placeholder="开始时间" style="max-width:100%" />
        <ElDatePicker v-model="to" type="datetime" aria-label="结束时间" placeholder="结束时间" style="max-width:100%" />
        <ElButton type="primary" :disabled="loading" @click="filter">应用筛选</ElButton>
      </div>
      <ElAlert v-if="error" :title="error" type="error" :closable="false" class="hx-gap" />
      <ArtTable :data="rows" :columns="columns" :loading="loading" height="auto" empty-height="260px" :show-table-header="false" :show-pagination="false" empty-text="暂无符合条件的执行作业">
        <template #kind="{row}">{{ kinds[row.kind] || row.kind }}</template>
        <template #status="{row}"><ElTag>{{ statuses[row.status] || row.status }}</ElTag></template>
        <template #tokens="{row}">{{ row.inputTokens ?? '未提供' }} / {{ row.outputTokens ?? '未提供' }}</template>
        <template #action="{row}"><ElButton text type="primary" @click="selected = row">查看记录</ElButton></template>
      </ArtTable>
      <div class="hx-filter hx-gap"><span>共 {{ total }} 个作业</span><ElPagination :current-page="query.page" :page-size="query.pageSize" :total="total" layout="prev, pager, next" :disabled="loading" @current-change="changePage" /></div>
      <p class="hx-footnote">执行次数不等于模型 API 调用次数。费用：{{ usage?.cost ?? '未提供' }}；Token 缺失时显示未提供。</p>
    </ElCard>
    <ElDrawer :model-value="!!selected" title="海外执行记录" size="min(600px, 100vw)" @close="selected = null"><template v-if="selected"><h2>{{ selected.taskName }}</h2><ElDescriptions :column="1" border><ElDescriptionsItem label="作业 ID">{{ selected.id }}</ElDescriptionsItem><ElDescriptionsItem label="状态">{{ statuses[selected.status] || selected.status }}</ElDescriptionsItem><ElDescriptionsItem label="创建时间">{{ selected.createdAt }}</ElDescriptionsItem><ElDescriptionsItem label="开始时间">{{ selected.startedAt || '尚未开始' }}</ElDescriptionsItem><ElDescriptionsItem label="完成时间">{{ selected.completedAt || '尚未完成' }}</ElDescriptionsItem><ElDescriptionsItem label="执行次数">{{ selected.executionCount }}</ElDescriptionsItem><ElDescriptionsItem label="错误摘要">{{ selected.error || '无' }}</ElDescriptionsItem></ElDescriptions></template></ElDrawer>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElDescriptions, ElDescriptionsItem } from 'element-plus'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import { managementError, stages, type ManagementApi, type ManagementQuery, type Job, type Usage } from '@/api/overseas/management'
const props = defineProps<{ page: 'usage' | 'monitor'; api: ManagementApi }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const query = reactive<ManagementQuery>({ from: '', to: '', taskId: '', kind: '', status: '', page: 1, pageSize: 20 })
const from = ref<Date>(), to = ref<Date>(), rows = ref<Job[]>([]), selected = ref<Job | null>(null), usage = ref<Usage | null>(null), total = ref(0), loading = ref(false), error = ref('')
const kinds: Record<string,string> = { ...stages, reanalysis: '重新分析' }
const statuses: Record<string,string> = { queued: '排队中', running: '执行中', collecting: '收集产物', cancelling: '取消中', uncertain: '待核实', succeeded: '成功', failed: '失败', cancelled: '已取消' }
let active = true, generation = 0
const cards = computed(() => (props.page === 'usage' ? [['作业总数','jobs'],['生成图片','generationImages'],['返工图片','revisionImages'],['输入 Token','inputTokens'],['输出 Token','outputTokens'],['费用','cost']] : [['排队','queued'],['执行中','running'],['待核实（占槽）','uncertain'],['成功','succeeded'],['失败','failed'],['已取消','cancelled']]).map(([label,key]) => ({ label, value: usage.value?.[key as keyof Usage] ?? '未提供' })))
async function load() {
  const current = ++generation
  loading.value = true; error.value = ''; rows.value = []; usage.value = null; total.value = 0; selected.value = null
  query.from = from.value?.toISOString() || ''; query.to = to.value?.toISOString() || ''
  if (query.from && query.to && query.from > query.to) { error.value = '开始时间不能晚于结束时间'; loading.value = false; return }
  try { const [summary, jobs] = await Promise.all([props.api.usage({...query}), props.api.jobs({...query})]); if (active && current === generation) { usage.value = summary; rows.value = jobs.items; total.value = jobs.total } }
  catch (reason) { if (active && current === generation) { error.value = managementError(reason); emit('failure', reason) } }
  finally { if (active && current === generation) loading.value = false }
}
function filter() { query.page = 1; void load() }
function changePage(page: number) { query.page = page; void load() }
const columns = [{prop:'taskName',label:'任务名称',minWidth:180},{prop:'kind',label:'类型',minWidth:110,useSlot:true},{prop:'status',label:'状态',minWidth:100,useSlot:true},{prop:'executionCount',label:'执行次数',width:100},{prop:'imageCount',label:'图片数',width:90},{prop:'tokens',label:'输入 / 输出 Token',minWidth:170,useSlot:true},{prop:'action',label:'操作',width:110,useSlot:true}]
onMounted(load)
onUnmounted(() => { active = false; ++generation; rows.value = []; selected.value = null; usage.value = null })
</script>
