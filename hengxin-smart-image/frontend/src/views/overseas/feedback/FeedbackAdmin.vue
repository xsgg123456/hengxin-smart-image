<template>
  <section class="dc-page hx-page">
    <header class="dc-title"><h1>反馈管理</h1><p>查看用户反馈的问题、来源页面和截图，记录处理进展。</p></header>
    <ElCard class="art-card feedback-card" shadow="never">
      <div class="feedback-filter">
        <ElRadioGroup v-model="filter" aria-label="反馈状态筛选" @change="filterChanged">
          <ElRadioButton value="">全部 {{ counts.pending + counts.processing + counts.resolved }}</ElRadioButton>
          <ElRadioButton v-for="(label, key) in feedbackStatuses" :key="key" :value="key">{{ label }} {{ counts[key] }}</ElRadioButton>
        </ElRadioGroup>
        <ElButton :loading="loading" @click="load">刷新</ElButton>
      </div>
      <ElAlert v-if="error" type="error" :closable="false" :title="error" />
      <ElTable v-loading="loading" :data="rows" row-key="id" empty-text="暂无此状态的反馈">
        <ElTableColumn prop="question" label="问题描述" min-width="235" />
        <ElTableColumn label="反馈页面" min-width="155"><template #default="{ row }">{{ feedbackSourceText(row.source, row.task_name, row.sku) }}</template></ElTableColumn>
        <ElTableColumn prop="submitter_name" label="提交人" width="100" />
        <ElTableColumn label="提交时间" width="164"><template #default="{ row }">{{ formatBeijingTime(row.created_at) }}</template></ElTableColumn>
        <ElTableColumn label="状态" width="95"><template #default="{ row }">
          <ElTag :type="row.status === 'pending' ? 'warning' : row.status === 'processing' ? 'primary' : 'success'">{{ feedbackStatuses[row.status as FeedbackStatus] }}</ElTag>
        </template></ElTableColumn>
        <ElTableColumn fixed="right" label="操作" width="95"><template #default="{ row }">
          <ElButton type="primary" link @click="selectedId = row.id">{{ row.status === 'resolved' ? '查看详情' : '查看处理' }}</ElButton>
        </template></ElTableColumn>
      </ElTable>
      <ElPagination v-if="total > pageSize" :current-page="page" :total="total" :page-size="pageSize" :pager-count="5"
        layout="prev, pager, next" class="hx-gap" @current-change="pageChanged" />
    </ElCard>
    <FeedbackDetail v-if="selectedId" :key="selectedId" :id="selectedId" :api="api"
      @close="selectedId = ''" @saved="saved" @failure="denied" />
  </section>
</template>
<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { feedbackAccessDenied, feedbackError, feedbackSourceText, feedbackStatuses, type FeedbackApi, type FeedbackStatus, type ManagedFeedback } from '@/api/overseas/feedback'
import { formatBeijingTime } from '@/utils/beijing-time'
import FeedbackDetail from './FeedbackDetail.vue'
const props = defineProps<{ api: FeedbackApi; refresh?: number }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const rows = ref<ManagedFeedback[]>([]), filter = ref<FeedbackStatus | ''>(''), selectedId = ref('')
const counts = ref({ pending: 0, processing: 0, resolved: 0 })
const loading = ref(false), error = ref(''), page = ref(1), total = ref(0), pageSize = 20
let generation = 0
function denied(reason: unknown) {
  ++generation; selectedId.value = ''; rows.value = []; total.value = 0; counts.value = { pending: 0, processing: 0, resolved: 0 }
  loading.value = false; error.value = feedbackError(reason); emit('failure', reason)
}
async function load() {
  const epoch = ++generation
  loading.value = true; error.value = ''; rows.value = []
  try {
    const result = await props.api.list(filter.value, (page.value - 1) * pageSize, pageSize)
    if (epoch !== generation) return
    const lastPage = Math.max(1, Math.ceil(result.total / pageSize))
    if (page.value > lastPage) { page.value = lastPage; await load(); return }
    rows.value = result.items; counts.value = result.counts; total.value = result.total
  } catch (reason) {
    if (epoch !== generation) return
    if (feedbackAccessDenied(reason)) { denied(reason); return }
    counts.value = { pending: 0, processing: 0, resolved: 0 }; total.value = 0; error.value = feedbackError(reason)
  } finally { if (epoch === generation) loading.value = false }
}
function pageChanged(value: number) { page.value = value; void load() }
function filterChanged() { pageChanged(1) }
function saved() { selectedId.value = ''; void load() }
watch(() => props.refresh, load)
onMounted(() => { void load(); window.addEventListener('focus', load) })
onBeforeUnmount(() => { ++generation; window.removeEventListener('focus', load) })
</script>
<style scoped>
.feedback-card { margin-top: 24px; }
.feedback-filter { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }
.feedback-filter :deep(.el-radio-group) { flex-wrap: wrap; }
@media (max-width: 600px) {
  .feedback-filter :deep(.el-radio-button__inner) { padding: 7px; }
}
</style>
