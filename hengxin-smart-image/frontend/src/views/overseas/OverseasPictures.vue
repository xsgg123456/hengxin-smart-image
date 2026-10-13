<template>
  <div class="hx-result-grid">
    <ElCard v-for="picture in pictures" :key="picture.id" shadow="never"
      ><ElImage
        :src="picture.url"
        :alt="picture.title"
        fit="contain"
        :preview-src-list="pictures.map((p) => p.url)"
        :initial-index="pictures.indexOf(picture)"
        preview-teleported
      />
      <div class="hx-result-meta">
        <strong>{{ picture.title }} · v{{ picture.version }}</strong>
      </div>
      <ElTag :type="picture.approved ? 'success' : 'info'">{{
        picture.reworking
          ? "模拟返工中"
          : picture.approved
            ? "已通过"
            : "待审核"
      }}</ElTag>
      <div v-if="task.status === 'review'" class="picture-actions">
        <ElButton
          text
          type="primary"
          :disabled="role !== 'designer' || picture.reworking"
          @click="$emit('approve', picture.id)"
          >{{ picture.approved ? "撤回通过" : "审核通过" }}</ElButton
        ><ElButton
          text
          :disabled="role !== 'designer' || picture.reworking"
          @click="$emit('edit', picture)"
          >标注修改</ElButton
        >
      </div>
      <details v-if="picture.history.length">
        <summary>返工记录</summary>
        <p v-for="(h, i) in picture.history" :key="i" class="hx-footnote">
          v{{ h.version }} → v{{ h.version + 1 }}：{{ h.note }}
          {{ h.marks.map((m) => m.note).join("；") }}
        </p>
      </details></ElCard
    >
  </div>
  <div v-if="task.status === 'review'" class="actions hx-gap">
    <ElButton
      type="primary"
      :disabled="
        role !== 'designer' ||
        approved !== task.pictures.length ||
        task.pictures.some((p) => p.reworking)
      "
      @click="$emit('archive')"
      >整套归档到成品库</ElButton
    >
  </div>
</template>
<script setup lang="ts">
import type { Picture, Role, Task } from "./types";
defineProps<{
  task: Task;
  role: Role;
  pictures: Picture[];
  approved: number;
}>();
defineEmits<{ approve: [id: string]; edit: [picture: Picture]; archive: [] }>();
</script>
<style scoped>
.hx-result-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.picture-actions,
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.picture-actions .el-button {
  margin-left: 0;
}
.actions {
  justify-content: flex-end;
}
@media (max-width: 600px) {
  .hx-result-grid {
    grid-template-columns: 1fr;
  }
}
</style>
