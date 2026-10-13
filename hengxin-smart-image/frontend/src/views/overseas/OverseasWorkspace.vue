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
          ><ElSelect v-model="status" aria-label="状态筛选" style="width: 160px"
            ><ElOption label="全部状态" value="" /><ElOption
              v-for="(label, key) in labels"
              :key="key"
              :label="label"
              :value="key" /></ElSelect
          ><ElInput
            v-model="query"
            class="hx-search"
            clearable
            aria-label="搜索任务"
            placeholder="搜索品名、品牌、SKU 或任务"
          /><ElButton @click="$emit('refresh')" :loading="busy">刷新任务</ElButton>
        </div>
        <slot name="feedback" />
        <ArtTable
          :data="tasks"
          :columns="columns"
          height="auto"
          empty-height="300px"
          :show-pagination="false"
          row-key="id"
          :empty-text="allowed ? '暂无匹配任务，请提交图需或清空筛选' : '暂无匹配任务，请清空筛选或联系运营'"
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
            ><ElTag>{{ labels[row.status as keyof typeof labels] }}</ElTag></template
          >
          <template #action="{ row }"
            ><ElButton text type="primary" @click="$emit('open', row.id)">查看详情</ElButton
            ><slot name="action" :row="row" /></template
          >
        </ArtTable>
        <slot name="pagination" />
        <p class="hx-footnote">
          共 {{ total }} 个任务 · 运营提交，设计审核图需、协作生图与归档
        </p>
      </ElCard>
</div></template>
<script setup lang="ts">
import { computed } from 'vue'
import ArtTable from '@/components/core/tables/art-table/index.vue'
import { taskStatuses, type TaskSummary } from '@/api/overseas/tasks'
import type { Task } from './types'
const props = defineProps<{ tasks: (TaskSummary | Task)[]; allowed: boolean; total: number; busy?: boolean; preview?: boolean }>()
const query = defineModel<string>('query', { required: true }), scope = defineModel<string>('scope', { required: true }), status = defineModel<string>('status', { required: true })
defineEmits<{ create: []; open: [id: string]; refresh: [] }>()
const labels = computed(() => props.preview ? Object.fromEntries(Object.entries(taskStatuses).filter(([key]) => key !== 'created')) : taskStatuses)
const columns = [
  { prop: 'name', label: '任务 / 品名', minWidth: 240, useSlot: true },
  { prop: 'brand', label: '品牌', minWidth: 100 },
  { prop: 'platform', label: '平台', minWidth: 100 },
  { prop: 'status', label: '当前节点', minWidth: 120, useSlot: true },
  { prop: 'createdAt', label: '提交时间', minWidth: 170 },
  { prop: 'action', label: '操作', minWidth: 100, useSlot: true },
]
</script>
