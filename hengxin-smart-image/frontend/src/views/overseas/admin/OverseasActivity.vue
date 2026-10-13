<template>
  <div>
    <div class="hx-admin-kpis">
      <ElCard
        v-for="item in cards"
        :key="item.label"
        class="art-card hx-admin-kpi"
        ><div>
          <span>{{ item.label }}</span
          ><strong>{{ item.value }}</strong
          ><small>{{ item.note }}</small>
        </div></ElCard
      >
    </div>
    <ElCard class="art-card hx-section hx-admin-table-card">
      <div class="hx-admin-section-head">
        <div>
          <span class="hx-admin-kicker">{{
            page === "usage" ? "WORKFLOW ACTIVITY" : "EXECUTION STATUS"
          }}</span>
          <h2>{{ page === "usage" ? "任务与流程记录" : "当前任务状态" }}</h2>
          <p>
            {{
              page === "usage"
                ? "流程记录不是模型调用回执，实际 API 请求、Token 和费用均未接入。删除任务会同步移除此处的预览记录。"
                : "来自本地任务的实时状态；未接入 Worker 心跳，不能据此判断真实服务是否在线。"
            }}
          </p>
        </div>
        <ElTag type="info">{{ rows.length }} 套任务</ElTag>
      </div>
      <div class="hx-filter">
        <ElInput
          v-model="search"
          class="hx-search"
          placeholder="搜索任务、品名或品牌"
          clearable
          aria-label="搜索海外管理任务"
        /><ElSelect
          v-model="status"
          clearable
          placeholder="全部状态"
          style="width: 160px"
          aria-label="任务状态"
          ><ElOption
            v-for="(label, key) in STATUS_LABELS"
            :key="key"
            :label="label"
            :value="key"
        /></ElSelect>
      </div>
      <ArtTable
        height="auto"
        empty-height="260px"
        :data="rows"
        :columns="columns"
        :show-table-header="false"
        :show-pagination="false"
        empty-text="暂无匹配的海外任务，请先由运营提交图需"
      >
        <template #status="{ row }"
          ><ElTag
            :type="
              row.status.endsWith('Failed')
                ? 'danger'
                : row.status === 'archived'
                  ? 'success'
                  : 'info'
            "
            >{{ STATUS_LABELS[row.status as Status] }}</ElTag
          ></template
        >
        <template #pictures="{ row }">{{
          ["review", "archived"].includes(row.status)
            ? row.pictures.length
            : "尚未生成"
        }}</template>
        <template #activity="{ row }">{{ row.events.length }}</template>
        <template #action="{ row }"
          ><ElButton type="primary" text @click="selectedId = row.id"
            >查看记录</ElButton
          ></template
        >
      </ArtTable>
      <p class="hx-footnote">
        {{
          page === "usage"
            ? "API 请求次数 / Token / 费用：未提供。图片数仅统计生成完成后的当前图片，不将排版方案占位图计为产出。"
            : "失败任务由设计在任务工作台重试；管理员在此只读观察执行状态。"
        }}
      </p>
    </ElCard>
    <ElDrawer
      :model-value="!!selected"
      title="海外任务执行记录"
      size="min(600px, 100vw)"
      @close="selectedId = ''"
    >
      <template v-if="selected"
        ><h2>{{ selected.name }}</h2>
        <p class="hx-muted">
          {{ selected.productName }} · {{ selected.brand }}
        </p>
        <ElDescriptions :column="1" border
          ><ElDescriptionsItem label="状态">{{
            STATUS_LABELS[selected.status]
          }}</ElDescriptionsItem
          ><ElDescriptionsItem label="SKU">{{
            selected.skus.map((s) => s.code).join("、")
          }}</ElDescriptionsItem
          ><ElDescriptionsItem label="创建时间">{{
            selected.createdAt
          }}</ElDescriptionsItem
          ><ElDescriptionsItem label="当前返工图片"
            >{{
              selected.pictures.filter((p) => p.reworking).length
            }}
            张</ElDescriptionsItem
          ><ElDescriptionsItem label="Token / 费用"
            >未提供</ElDescriptionsItem
          ></ElDescriptions
        >
        <ElTimeline v-if="selected.events.length" class="hx-gap"
          ><ElTimelineItem
            v-for="(event, i) in selected.events"
            :key="i"
            :timestamp="event.at"
            >{{ event.title }}</ElTimelineItem
          ></ElTimeline
        ><ElEmpty v-else description="暂无流程记录" />
      </template>
    </ElDrawer>
  </div>
</template>
<script setup lang="ts">
import { computed, ref } from "vue";
import {
  ElButton,
  ElCard,
  ElDescriptions,
  ElDescriptionsItem,
  ElDrawer,
  ElEmpty,
  ElInput,
  ElOption,
  ElSelect,
  ElTag,
  ElTimeline,
  ElTimelineItem,
} from "element-plus";
import ArtTable from "@/components/core/tables/art-table/index.vue";
import { overseasTasks } from "../preview-adapter";
import { STATUS_LABELS, type Status } from "../types";
import { taskSummary } from "./management-adapter";
const props = defineProps<{ page: "usage" | "monitor" }>();
const search = ref(""),
  status = ref(""),
  selectedId = ref("");
const rows = computed(() =>
  overseasTasks.filter(
    (t) =>
      (!status.value || t.status === status.value) &&
      `${t.name} ${t.productName} ${t.brand}`
        .toLowerCase()
        .includes(search.value.trim().toLowerCase()),
  ),
);
const summary = computed(() => taskSummary(rows.value));
const selected = computed(() =>
  overseasTasks.find((t) => t.id === selectedId.value),
);
const cards = computed(() =>
  props.page === "usage"
    ? [
        {
          label: "当前任务",
          value: summary.value.tasks,
          note: "套 · 当前筛选范围",
        },
        {
          label: "已生成图片",
          value: summary.value.pictures,
          note: "张 · 当前图片，含返工中图片",
        },
        {
          label: "整套已归档",
          value: summary.value.archived,
          note: "套 · 全部图片已通过",
        },
        {
          label: "流程记录",
          value: summary.value.events,
          note: "条 · 非 API 请求次数",
        },
      ]
    : [
        {
          label: "执行中任务",
          value: summary.value.running,
          note: "套 · 分析、生图或单图返工",
        },
        {
          label: "当前失败",
          value: summary.value.failed,
          note: "套 · 等待设计重试",
        },
        {
          label: "待设计处理",
          value: summary.value.pending,
          note: "套 · 方案或图片审核阶段",
        },
        {
          label: "返工中图片",
          value: summary.value.reworking,
          note: "张 · 当前单图返工",
        },
      ],
);
const columns = [
  { prop: "name", label: "任务名称", minWidth: 200 },
  { prop: "brand", label: "品牌", minWidth: 110 },
  { prop: "status", label: "状态", minWidth: 120, useSlot: true },
  { prop: "pictures", label: "当前图片", minWidth: 110, useSlot: true },
  { prop: "activity", label: "流程记录", width: 100, useSlot: true },
  { prop: "action", label: "操作", width: 110, useSlot: true },
];
</script>
