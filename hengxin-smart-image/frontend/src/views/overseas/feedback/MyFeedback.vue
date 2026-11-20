<template>
  <div v-loading="loading" class="personal-feedback">
    <ElAlert v-if="error" :title="error" type="error" :closable="false"><ElButton link @click="load">重新加载</ElButton></ElAlert>
    <ElEmpty v-else-if="!loading && !items.length" description="你还没有提交过反馈" />
    <article v-for="item in items" :key="item.id" class="personal-item">
      <header><span>{{ formatBeijingTime(item.created_at) }}</span>
        <ElTag size="small" :type="item.status === 'pending' ? 'warning' : item.status === 'processing' ? 'primary' : 'success'">{{ feedbackStatuses[item.status] }}</ElTag>
      </header>
      <p class="personal-question">{{ item.question }}</p>
      <p class="personal-source">{{ feedbackSourceText(item.source, item.task_name, item.sku) }}</p>
      <div v-if="item.public_reply" class="personal-reply"><strong>管理员回复</strong><p>{{ item.public_reply }}</p></div>
      <p v-else class="personal-wait">暂无管理员回复</p>
    </article>
    <ElPagination v-if="total > pageSize" :current-page="page" :total="total" :page-size="pageSize" :pager-count="5"
      layout="prev, pager, next" @current-change="pageChanged" />
  </div>
</template>
<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { feedbackAccessDenied, feedbackError, feedbackSourceText, feedbackStatuses, type Feedback, type FeedbackApi } from '@/api/overseas/feedback'
import { formatBeijingTime } from '@/utils/beijing-time'
const props = defineProps<{ api: FeedbackApi }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const items = ref<Feedback[]>([]), loading = ref(false), error = ref('')
const page = ref(1), total = ref(0), pageSize = 20
let generation = 0
async function load() {
  const epoch = ++generation
  loading.value = true; error.value = ''; items.value = []
  try {
    const result = await props.api.mine((page.value - 1) * pageSize, pageSize)
    if (epoch === generation) { items.value = result.items; total.value = result.total }
  } catch (reason) {
    if (epoch !== generation) return
    total.value = 0; error.value = feedbackError(reason)
    if (feedbackAccessDenied(reason)) emit('failure', reason)
  } finally { if (epoch === generation) loading.value = false }
}
function pageChanged(value: number) { page.value = value; void load() }
onMounted(() => { void load(); window.addEventListener('focus', load) })
onBeforeUnmount(() => { ++generation; window.removeEventListener('focus', load) })
</script>
<style scoped>
.personal-feedback { min-height: 80px; }
.personal-item { padding: 18px 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.personal-item:first-child { padding-top: 4px; }
.personal-item header { display: flex; justify-content: space-between; gap: 8px; align-items: center; color: var(--el-text-color-secondary); font-size: 12px; }
.personal-question, .personal-reply p { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.65; }
.personal-question { margin: 10px 0 4px; color: var(--el-text-color-primary); font-size: 15px; }
.personal-source, .personal-wait { font-size: 12px; color: var(--el-text-color-secondary); overflow-wrap: anywhere; }
.personal-wait { margin: 10px 0 0; }
.personal-reply { margin-top: 12px; padding: 10px 14px; background: var(--el-fill-color-light); border-radius: 7px; font-size: 13px; }
.personal-reply strong { font-size: 12px; font-weight: 600; }
.personal-reply p { margin: 4px 0 0; }
</style>
