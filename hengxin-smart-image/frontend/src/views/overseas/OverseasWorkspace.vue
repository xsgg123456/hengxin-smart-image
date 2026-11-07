<template><div class="hx-page">      <div class="hx-heading">
        <div>
          <h1>工作流任务</h1>
          <p>从需求提交到成品归档，跟进每一套海外商品图片。</p>
        </div>
        <ElButton
          type="primary"
          v-if="allowed"
          @click="$emit('create')"
          >提交图需</ElButton
        >
      </div>
      <slot name="stats" />
      <ElCard class="art-card hx-section" shadow="never">
        <div class="hx-filter">
          <ElRadioGroup v-model="scope"
            ><ElRadioButton value="all">全部任务</ElRadioButton
            ><ElRadioButton value="mine">{{ preview ? '待我处理' : '与我相关' }}</ElRadioButton></ElRadioGroup
          ><ElSelect v-model="status" placeholder="全部状态" aria-label="状态筛选" style="width: 160px"
            ><ElOption label="全部状态" value="" /><ElOption
              v-for="(label, key) in (preview ? labels : taskGroups)"
              :key="key"
              :label="label"
              :value="key" /></ElSelect
          ><ElSelect v-if="!preview" v-model="designer" clearable filterable aria-label="设计负责人筛选" placeholder="全部设计负责人" style="width: 200px"><ElOption v-for="person in assignees" :key="person.id" :value="person.id" :label="person.name" /></ElSelect><ElInput
            v-model="query"
            class="hx-search"
            clearable
            aria-label="搜索任务"
            placeholder="搜索品名、品牌、SKU 或任务"
          /><ElButton :class="{ 'light-neutral': !preview }" @click="$emit('refresh')" :loading="busy">刷新任务</ElButton>
        </div>
        <slot name="feedback" />
        <ArtTable
          :data="tasks"
          :columns="columns"
          height="auto"
          empty-height="300px"
          :show-pagination="false"
          row-key="id"
          :empty-text="allowed ? '暂无匹配任务，请提交图需或清空筛选' : '暂无匹配任务，请清空筛选或联系提交人'"
        >
          <template #name="{ row }"
            ><div class="hx-table-name">
              <div>
                <strong>{{ row.name }}</strong
                ><small>{{ row.productName }} · {{ row.id }}</small>
              </div>
            </div></template
          >
          <template #status="{ row }"
            ><ElTag :type="preview ? 'primary' : taskStatusTone(row.status)">{{ preview ? labels[row.status as keyof typeof labels] : taskStatusLabel(row.status) }}</ElTag><p v-if="!preview && taskStatusNote(row.status)" class="task-status-note">{{ taskStatusNote(row.status) }}</p><p v-if="row.deletionError" class="task-deletion-error">{{ row.deletionError }}</p></template
          >
          <template #designer="{ row }">{{ row.designer?.name || '未指派' }}</template>
          <template #createdAt="{ row }">{{ formatBeijingTime(row.createdAt) }}</template>
          <template #action="{ row }"
            ><ElButton text type="primary" @click="$emit('open', row.id)">查看详情</ElButton
            ><slot name="action" :row="row" /></template
          >
        </ArtTable>
        <slot name="pagination" />
        <p class="hx-footnote">
          共 {{ total }} 个任务 · 提交人提交，设计审核图需、协作生图与归档
        </p>
      </ElCard>
</div></template>
<script setup lang="ts">
import { formatBeijingTime } from '@/utils/beijing-time'

import { computed } from 'vue'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import { taskStatuses, type TaskSummary } from '@/api/overseas/tasks'
import type { Task } from './types'
import { taskGroups, taskStatusLabel, taskStatusNote, taskStatusTone } from './task-status'
const props = withDefaults(defineProps<{ tasks: (TaskSummary | Task)[]; allowed: boolean; total: number; busy?: boolean; preview?: boolean; assignees?: { id: string; name: string }[] }>(), { assignees: () => [] })
const query = defineModel<string>('query', { required: true }), scope = defineModel<string>('scope', { required: true }), status = defineModel<string>('status', { required: true })
const designer = defineModel<string>('designer', { default: '' })
defineEmits<{ create: []; open: [id: string]; refresh: [] }>()
const labels = computed(() => Object.fromEntries(Object.entries(taskStatuses).filter(([key]) => key !== 'deleted' && (!props.preview || !['created', 'deleting', 'delete_failed'].includes(key)))))
const columns = [
  { prop: 'name', label: '任务 / 品名', minWidth: 240, useSlot: true },
  { prop: 'brand', label: '品牌', minWidth: 100 },
  { prop: 'platform', label: '平台', minWidth: 100 },
  ...(!props.preview ? [{ prop: 'designer', label: '设计负责人', minWidth: 120, useSlot: true }] : []),
  { prop: 'status', label: props.preview ? '当前节点' : '任务状态', minWidth: 160, useSlot: true },
  { prop: 'createdAt', label: '提交时间', minWidth: 170, useSlot: true },
  { prop: 'action', label: '操作', minWidth: 180, useSlot: true },
]
</script>
<style scoped>
:deep(.light-neutral:not(:hover):not(:focus-visible)) { color: var(--el-text-color-regular); border-color: var(--el-border-color); }
.task-deletion-error { font-size: 12px; color: var(--el-color-danger); white-space: normal; overflow-wrap: anywhere; margin-top: 6px; }
.task-status-note { margin-top: 6px; font-size: 12px; line-height: 1.6; color: var(--art-gray-600); white-space: normal; }
</style>
