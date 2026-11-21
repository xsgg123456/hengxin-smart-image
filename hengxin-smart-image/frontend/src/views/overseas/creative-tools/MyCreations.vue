<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { IdentityError } from '@/api/identity/request'
import { taskError, type TaskSummary, type TasksApi } from '@/api/overseas/tasks'

const props = defineProps<{ api: TasksApi; refresh: number }>()
const emit = defineEmits<{ close: []; open: [id: string]; failure: [reason: unknown] }>()
const search = ref(''), page = ref(1), total = ref(0), tasks = ref<TaskSummary[]>([])
const busy = ref(false), error = ref('')
const pageSize = 20
let generation = 0
let timer: ReturnType<typeof setTimeout> | undefined

async function load() {
  clearTimeout(timer)
  const current = ++generation
  busy.value = true
  error.value = ''
  tasks.value = []
  try {
    const result = await props.api.list({ search: search.value.trim(), scope: '', status: '', toolScope: 'mine', page: page.value, pageSize })
    if (current !== generation) return
    tasks.value = result.items
    total.value = result.total
    if (!result.items.length && page.value > 1) page.value = Math.max(1, Math.ceil(result.total / pageSize))
  } catch (reason) {
    if (current !== generation) return
    total.value = 0
    error.value = taskError(reason)
    if (reason instanceof IdentityError && [401, 403].includes(reason.status)) emit('failure', reason)
  } finally {
    if (current === generation) busy.value = false
  }
}
watch(search, () => {
  ++generation
  clearTimeout(timer)
  busy.value = true
  tasks.value = []
  error.value = ''
  if (page.value !== 1) page.value = 1
  else timer = setTimeout(load, 200)
})
watch([page, () => props.refresh], load, { immediate: true })
onUnmounted(() => { ++generation; clearTimeout(timer) })
</script>

<template>
  <ElDialog :model-value="true" title="我的创作" width="min(620px, calc(100vw - 32px))" align-center append-to-body @close="emit('close')">
    <ElInput v-model="search" maxlength="161" clearable :prefix-icon="Search" aria-label="搜索品名或 SKU" placeholder="搜索品名或 SKU" />
    <p v-if="busy" role="status" class="my-task-empty">正在加载创作…</p>
    <ElAlert v-else-if="error" :title="error" type="error" :closable="false"><ElButton @click="load">重试</ElButton></ElAlert>
    <ul v-else-if="tasks.length" class="my-task-list">
      <li v-for="task in tasks" :key="task.id">
        <button type="button" @click="emit('open', task.id)">
          <span class="my-task-info"><strong>{{ task.productName }}</strong><small>{{ task.skus.map(s => s.code).join('、') }} · {{ [task.platform || '其他平台', task.brand].filter(Boolean).join(' · ') }}</small></span>
          <span class="my-task-action">继续创作</span>
        </button>
      </li>
    </ul>
    <p v-else class="my-task-empty">{{ search.trim() ? '没有找到匹配的创作' : '暂无创作，从平台生图卡片开始创建。' }}</p>
    <ElPagination v-if="total > pageSize && !error" v-model:current-page="page" :disabled="busy" :page-size="pageSize" :total="total" layout="prev, pager, next" :pager-count="5" />
  </ElDialog>
</template>
<style scoped>
.my-task-list { list-style: none; margin: 14px 0 0; padding: 0; max-height: 52dvh; overflow: auto; }
.my-task-list li + li { border-top: 1px solid var(--el-border-color-lighter); }
.my-task-list button { display: flex; align-items: center; justify-content: space-between; gap: 12px; width: 100%; text-align: left; font: inherit; color: inherit; border: 0; cursor: pointer; background: transparent; padding: 12px 4px; }
.my-task-list button:hover { background: var(--el-fill-color-light); }
.my-task-info { display: grid; gap: 4px; min-width: 0; overflow-wrap: anywhere; }
.my-task-info small, .my-task-empty { color: var(--el-text-color-secondary); }
.my-task-empty { margin: 24px 0 8px; text-align: center; }
.my-task-action { flex: none; color: var(--el-color-primary); }
</style>
