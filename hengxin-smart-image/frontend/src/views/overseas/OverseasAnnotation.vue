<template>
  <ElDialog
    class="overseas-annotation-dialog"
    :model-value="true"
    :title="`标注修改 · ${picture.sku} · ${picture.title} · v${baseVersion}`"
    width="min(1200px, 96vw)"
    append-to-body
    :close-on-click-modal="false"
    @close="$emit('close')"
  >
    <div class="annotation-layout">
      <section>
        <AnnotationCanvas
          v-if="dimensions"
          v-model="marks"
          :image-url="picture.url"
          :width="dimensions.width"
          :height="dimensions.height"
          :disabled="confirming || role !== 'designer'"
        /><ElAlert v-else-if="loadError" :title="loadError" type="error"
          ><ElButton @click="load">重试加载图片</ElButton></ElAlert
        >
        <p v-else>正在读取示例图片…</p>
      </section>
      <aside>
        <h3>问题位置与修改意见</h3>
        <ElEmpty
          v-if="!marks.length"
          description="框选或圈注问题，也可直接填写整体修改要求"
          :image-size="60"
        /><ElForm label-position="top"
          ><ElFormItem
            v-for="(mark, i) in marks"
            :key="mark.id"
            :label="`标注 ${i + 1} 修改意见`"
            ><ElInput
              v-model="mark.note"
              type="textarea"
              :rows="2"
              :disabled="confirming || role !== 'designer'"
              maxlength="1000" /></ElFormItem
          ><ElFormItem label="整体补充要求"
            ><ElInput
              v-model="general"
              aria-label="整体补充要求"
              type="textarea"
              :rows="3"
              maxlength="1000"
              :disabled="
                confirming || role !== 'designer'
              " /></ElFormItem></ElForm
        ><ElAlert
          title="只修改这张图片"
          description="基于当前版本模拟返工；标注不会进入成品，其他图片及审核状态保留。"
          type="info"
          :closable="false"
        /><ElAlert v-if="error" :title="error" type="error" :closable="false" />
      </aside>
    </div>
    <ElAlert
      v-if="confirming"
      title="确认本次单图修改"
      :description="summary"
      type="warning"
      :closable="false"
    />
    <template #footer
      ><ElButton @click="confirming ? (confirming = false) : $emit('close')">{{
        confirming ? "返回继续标注" : "取消"
      }}</ElButton
      ><ElButton
        type="primary"
        :disabled="!dimensions || role !== 'designer'"
        @click="submit"
        >{{ confirming ? "确认提交修改" : "预览并提交修改" }}</ElButton
      ></template
    >
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import AnnotationCanvas from "../hengxin/components/annotation/AnnotationCanvas.vue";
import type { AnnotationMark } from "../hengxin/components/annotation/annotation-model";
import type { Picture, Role } from "./types";
const props = defineProps<{ picture: Picture; role: Role }>();
const emit = defineEmits<{
  close: [];
  submit: [version: number, note: string, marks: AnnotationMark[]];
}>();
const baseVersion = props.picture.version;
const marks = ref<AnnotationMark[]>([]),
  general = ref(""),
  error = ref(""),
  confirming = ref(false),
  loadError = ref("");
const dimensions = ref<{ width: number; height: number }>();
const summary = computed(() =>
  [...marks.value.map((m, i) => `标注 ${i + 1}：${m.note}`), general.value]
    .filter(Boolean)
    .join("；"),
);
let disposed = false;
async function load() {
  loadError.value = "";
  try {
    const image = new Image();
    image.src = props.picture.url;
    await image.decode();
    if (!disposed)
      dimensions.value = {
        width: image.naturalWidth,
        height: image.naturalHeight,
      };
  } catch {
    if (!disposed) loadError.value = "示例图片读取失败，请重试";
  }
}
function submit() {
  error.value = "";
  if (props.role !== "designer") return;
  if (
    (!marks.value.length && !general.value.trim()) ||
    marks.value.some((m) => !m.note.trim())
  ) {
    error.value = "请填写每处标注意见，或提供整体修改要求";
    return;
  }
  if (!confirming.value) {
    confirming.value = true;
    return;
  }
  emit("submit", baseVersion, general.value, marks.value);
}
onMounted(load);
onBeforeUnmount(() => {
  disposed = true;
});
</script>
<style scoped>
.annotation-layout {
  display: grid;
  grid-template-columns: minmax(0, 2.65fr) minmax(260px, 1fr);
  gap: 24px;
  height: min(70dvh, 760px);
  min-height: 450px;
}
.annotation-layout section {
  min-width: 0;
  min-height: 0;
}
.annotation-layout aside {
  overflow: auto;
  min-width: 0;
  padding-right: 5px;
}
.annotation-layout h3 {
  margin-bottom: 20px;
  font-size: 14px;
}
@media (max-width: 900px) {
  .annotation-layout {
    grid-template-columns: 1fr;
    grid-template-rows: 360px 260px;
    height: auto;
    min-height: 0;
    gap: 12px;
  }
}
</style>
<style>
.overseas-annotation-dialog { display: flex; flex-direction: column; margin: 3dvh auto !important; max-height: 94dvh; }
.overseas-annotation-dialog .el-dialog__body { min-height: 0; overflow: auto; }
.overseas-annotation-dialog .el-dialog__footer { flex-shrink: 0; }
</style>
