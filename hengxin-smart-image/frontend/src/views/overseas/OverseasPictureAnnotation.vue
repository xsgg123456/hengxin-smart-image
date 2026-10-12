<template>
  <ElDialog
    class="overseas-annotation-dialog"
    :model-value="true"
    :title="`标注修改 · ${picture.sku} · ${picture.title} · v${baseVersion}`"
    width="min(1200px, 96vw)"
    append-to-body
    :close-on-click-modal="false"
    :before-close="close"
  >
    <div class="annotation-layout">
      <section>
        <AnnotationCanvas
          v-if="dimensions"
          v-model="marks"
          :image-url="picture.url!"
          :width="dimensions.width"
          :height="dimensions.height"
          :disabled="confirming || locked || conflict || !allowed"
        /><ElAlert v-else-if="loadError" :title="loadError" type="error"
          ><ElButton @click="load">重试加载图片</ElButton></ElAlert
        >
        <p v-else>正在读取原始图片…</p>
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
              :disabled="confirming || locked || conflict || !allowed"
              maxlength="1000" /></ElFormItem
          ><ElFormItem label="整体补充要求"
            ><ElInput
              v-model="general"
              aria-label="整体补充要求"
              type="textarea"
              :rows="3"
              maxlength="1000"
              :disabled="
                confirming || locked || !allowed
              " /></ElFormItem></ElForm
        ><ElAlert
          title="只修改这张图片"
          description="基于当前版本提交返工；标注不会进入成品，其他图片及审核状态保留。"
          type="info"
          :closable="false"
        /><ElAlert v-if="error || failure" :title="error || failure" type="error" :closable="false" />
      </aside>
    </div>
    <ElAlert v-if="conflict" title="底图已变化，意见已保留。请复制意见，关闭后基于最新版本重新标注。" type="warning" :closable="false" />
    <ElAlert
      v-if="confirming"
      title="确认本次单图修改"
      :description="summary"
      type="warning"
      :closable="false"
    />
    <template #footer
      ><ElButton :disabled="locked" @click="confirming ? (confirming = false) : $emit('close')">{{
        confirming ? "返回继续标注" : "取消"
      }}</ElButton
      ><ElButton v-if="retryable" type="primary" @click="$emit('retry')">核实并重试图片原请求</ElButton><ElButton
        type="primary"
        :disabled="!dimensions || !allowed || locked || conflict"
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
import type { Picture } from "@/api/overseas/pictures";
const props = defineProps<{ picture: Picture; allowed: boolean; locked: boolean; conflict: boolean; failure: string; retryable: boolean }>();
const emit = defineEmits<{
  close: [];
  retry: [];
  submit: [version: number, note: string, marks: AnnotationMark[]];
}>();
const baseVersion = props.picture.version;
function close(done: () => void) { if (!props.locked) { emit("close"); done() } }
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
    image.src = props.picture.url!;
    await image.decode();
    if (image.naturalWidth !== props.picture.width || image.naturalHeight !== props.picture.height) throw Error("原图尺寸不匹配");
    if (!disposed)
      dimensions.value = {
        width: image.naturalWidth,
        height: image.naturalHeight,
      };
  } catch {
    if (!disposed) loadError.value = "原始图片读取失败，请重试";
  }
}
function submit() {
  error.value = "";
  if (!props.allowed || props.locked || props.conflict) return;
  if (
    (!marks.value.length && !general.value.trim()) ||
    marks.value.some((m) => !m.note.trim())
  ) {
    error.value = "请填写每处标注意见，或提供整体修改要求";
    return;
  }
  if (marks.value.length > 100 || marks.value.some(m => m.points.length > 2000) || marks.value.reduce((n, m) => n + m.points.length, 0) > 10000) { error.value = "标注过多，请简化后重试"; return; }
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
