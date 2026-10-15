<template>
  <div class="hx-heading">
    <div>
      <h1>成品库</h1>
      <p>搜索品名、品牌或 SKU，任一项匹配即可。</p>
    </div>
    <ElTag type="success">{{ rows.length }} 个 SKU 已归档</ElTag>
  </div>
  <ElCard class="art-card hx-section" shadow="never"
    ><div class="hx-filter">
      <ElInput
        v-model="query"
        clearable
        class="hx-search"
        placeholder="搜索品名、品牌、SKU"
        aria-label="搜索成品"
      /><ElButton
        @click="
          query = '';
        "
        >重置筛选</ElButton
      >
    </div></ElCard
  >
  <ElEmpty
    v-if="!filtered.length"
    description="暂无匹配成品；全部图片通过后由设计整套归档"
  />
  <div class="hx-library-grid hx-gap">
    <ElCard
      v-for="row in filtered"
      :key="`${row.task.id}-${row.sku.code}`"
      class="art-card hx-library-card"
      shadow="never"
      ><div class="hx-library-mosaic">
        <ElImage
          v-for="p in row.pictures.slice(0, 4)"
          :key="p.id"
          :src="p.url"
          :alt="p.title"
          fit="contain"
          :preview-src-list="row.pictures.map((p) => p.url)"
          :initial-index="row.pictures.indexOf(p)"
          preview-teleported
        />
      </div>
      <div class="hx-library-info">
        <div class="hx-row">
          <ElTag>{{ row.task.brand }}</ElTag
          ><ElTag type="success">全部通过</ElTag>
        </div>
        <h3>{{ row.task.productName }}</h3>
        <p>{{ row.sku.code }}</p>
        <div class="hx-row">
          <span class="hx-footnote"
            >{{ row.pictures.length }} 张示例图片 ·
            {{ row.task.platform }}</span
          ><ElButton text type="primary" @click="$emit('open', row.task)"
            >查看成品</ElButton
          >
        </div>
        <ElDivider /><ElButton
          v-if="role === 'designer'"
          text
          type="danger"
          @click="remove(row.task)"
          >移除整套归档</ElButton
        >
      </div></ElCard
    >
  </div>
</template>
<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { Role, Task } from "./types";
import { overseasTasks } from "./preview-adapter";
import { removeArchive } from "./workflow";
const props = defineProps<{ role: Role }>();
defineEmits<{ open: [task: Task] }>();
const query = ref("");
const rows = computed(() =>
  overseasTasks
    .filter((t) => t.status === "archived")
    .flatMap((task) =>
      task.skus.map((sku) => ({
        task,
        sku,
        pictures: task.pictures.filter((p) => p.sku === sku.code),
      })),
    ),
);
const filtered = computed(() =>
  rows.value.filter(
    (r) =>
      [r.task.productName, r.task.brand, r.sku.code]
        .some(value => value.toLowerCase().includes(query.value.trim().toLowerCase())),
  ),
);
async function remove(task: Task) {
  try {
    await ElMessageBox.confirm(
      `移除「${task.productName}」全部 ${task.skus.length} 个 SKU 的归档？原任务、图片及审核状态保留，可重新归档。`,
      "移除整套归档",
      {
        type: "warning",
        confirmButtonText: "移除整套归档",
        cancelButtonText: "取消",
      },
    );
    removeArchive(task, props.role);
  } catch (e) {
    if (e instanceof Error) ElMessage.error(e.message);
  }
}
</script>
<style scoped>
.hx-filter > .hx-search {
  width: 320px;
  max-width: 100%;
}
.hx-library-mosaic .el-image {
  height: 106px;
  min-width: 0;
}
.hx-library-info {
  overflow-wrap: anywhere;
}
@media (max-width: 600px) {
  .hx-filter > .hx-search {
    width: 100%;
    max-width: none;
  }
}
</style>
