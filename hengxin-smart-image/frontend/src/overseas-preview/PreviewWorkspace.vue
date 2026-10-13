<template>
  <div class="hx-page">
    <OverseasCreate
      v-if="page === 'create'"
      :role="role"
      @back="navigate('tasks')"
      @created="open"
    />
    <OverseasDetail
      v-else-if="selected && page === 'tasks'"
      :task="selected"
      :role="role"
      @back="selectedId = ''"
      @archived="navigate('archive')"
    />
    <OverseasArchive v-else-if="page === 'archive'" :role="role" @open="open" />
    <OverseasWorkspace v-else v-model:query="query" v-model:scope="scope" v-model:status="status" :tasks="filtered" :allowed="role === 'operator'" :total="filtered.length" preview @create="navigate('create')" @open="open(overseasTasks.find(t => t.id === $event)!)">
      <template #stats><div class="hx-stats"><ElCard v-for="item in stats" :key="item.label" class="art-card" shadow="never"><span>{{ item.label }}</span><strong>{{ item.count }}</strong></ElCard></div></template>
      <template #action="{ row }"><ElButton v-if="role === 'operator'" text type="danger" @click="remove(overseasTasks.find(t => t.id === row.id)!)">删除</ElButton></template>
    </OverseasWorkspace>
  </div>
</template>
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import ArtTable from "@/components/core/tables/art-table/index.vue";
import OverseasCreate from "@/overseas-preview/CreatePage.vue";
import OverseasWorkspace from "@/views/overseas/OverseasWorkspace.vue";
import OverseasDetail from "@/views/overseas/OverseasDetail.vue";
import OverseasArchive from "@/views/overseas/OverseasArchive.vue";
import {
  overseasTasks,
  selectedOverseasTaskId as selectedId,
} from "@/views/overseas/preview-adapter";
import { canDelete } from "@/views/overseas/workflow";
import { STATUS_LABELS } from "@/views/overseas/types";
import type { Page, Role, Status, Task } from "@/views/overseas/types";
const props = defineProps<{ page: Page; role: Role }>();
const emit = defineEmits<{ navigate: [page: Page] }>();
const query = ref(""),
  status = ref(""),
  scope = ref("all");
const selected = computed(() =>
  overseasTasks.find((t) => t.id === selectedId.value),
);
watch(
  () => props.page,
  (page) => {
    if (page !== "tasks") selectedId.value = "";
  },
);
function navigate(page: Page) {
  selectedId.value = "";
  emit("navigate", page);
}
function open(task: Task) {
  selectedId.value = task.id;
  emit("navigate", "tasks");
}
const filtered = computed(() =>
  overseasTasks.filter(
    (t) =>
      (!status.value || t.status === status.value) &&
      (scope.value === "all" ||
        (props.role === "designer" &&
          ["plan", "review", "analysisFailed", "generationFailed"].includes(
            t.status,
          ))) &&
      [
        t.name,
        t.productName,
        t.brand,
        t.id,
        ...t.skus.map((s) => s.code),
      ]
        .join(" ")
        .toLowerCase()
        .includes(query.value.trim().toLowerCase()),
  ),
);
const stats = computed(() => [
  { label: "全部任务", count: overseasTasks.length },
  {
    label: "设计待审",
    count: overseasTasks.filter((t) => ["plan", "review"].includes(t.status))
      .length,
  },
  {
    label: "AI 处理中",
    count: overseasTasks.filter((t) =>
      ["analyzing", "generating"].includes(t.status),
    ).length,
  },
  {
    label: "已归档",
    count: overseasTasks.filter((t) => t.status === "archived").length,
  },
]);
async function remove(task: Task) {
  try {
    canDelete(task, props.role);
    await ElMessageBox.confirm(
      `删除「${task.name}」及本次预览中的流转记录？`,
      "删除任务",
      {
        type: "warning",
        confirmButtonText: "删除任务",
        cancelButtonText: "取消",
      },
    );
    canDelete(task, props.role);
    const index = overseasTasks.indexOf(task);
    if (index >= 0) overseasTasks.splice(index, 1);
  } catch (e) {
    if (e instanceof Error) ElMessage.error(e.message);
  }
}
</script>
