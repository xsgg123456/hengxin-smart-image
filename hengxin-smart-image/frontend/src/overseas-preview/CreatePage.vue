<template><OverseasCreate v-model="draft" :allowed="role === 'operator'" preview @back="$emit('back')">
<template #example><ElButton text type="primary" :disabled="role !== 'operator'" @click="draft = exampleDraft()">填入示例</ElButton></template>
<template #after>      <ElCard class="art-card hx-section" shadow="never">
        <div class="hx-section-title">
          <h2><span class="hx-number">02</span>上传图需资料</h2>
          <ElTag>至少一份</ElTag>
        </div>
        <div class="form-grid">
          <div v-for="kind in kinds" :key="kind.key">
            <h3>{{ kind.label }}</h3>
            <ElUpload
              drag
              :auto-upload="false"
              :show-file-list="false"
              :disabled="role !== 'operator'"
              :accept="kind.accept"
              :on-change="(file) => pick(file, kind.key)"
              ><strong>点击选择或拖入文件</strong>
              <p>{{ kind.accept }} · 最大 20 MB</p></ElUpload
            >
            <p
              v-for="file in draft.files.filter((f) => f.kind === kind.key)"
              :key="file.name"
              class="file-row"
            >
              {{ file.name }}{{ file.sample ? "（示例）" : ""
              }}<ElButton
                text
                type="danger"
                :disabled="role !== 'operator'"
                @click="draft.files = draft.files.filter((f) => f !== file)"
                >移除</ElButton
              >
            </p>
            <ElButton
              text
              type="primary"
              :disabled="role !== 'operator'"
              @click="sample(kind.key)"
              >使用示例资料</ElButton
            >
          </div>
        </div>
        <p class="hx-footnote">
          本地预览仅记录文件名，不上传、不解析文件。示例资料及图片均不代表实际
          AI 结果。
        </p>
        <ElAlert
          title="提交前请核对"
          description="请确认品名、品牌、SKU 信息准确，已上传的资料能清楚说明图片需求。提交后将直接进入 AI 排版分析，由设计确认方案。"
          type="info"
          :closable="false"
        />
        <ElAlert
          v-if="error"
          :title="error"
          type="error"
          :closable="false"
          class="hx-gap"
        />
        <div class="actions hx-gap">
          <ElCheckbox v-model="fail" :disabled="role !== 'operator'"
            >演示分析失败</ElCheckbox
          ><ElButton
            :disabled="role !== 'operator'"
            @click="
              draft = emptyDraft();
              error = '';
            "
            >清空</ElButton
          ><ElButton
            type="primary"
            :disabled="role !== 'operator'"
            @click="submit"
            >确认并提交，开始分析</ElButton
          >
        </div>
      </ElCard></template></OverseasCreate></template>
<script setup lang="ts">
import { ref } from 'vue'
import type { UploadFile } from 'element-plus'
import type { Material, Role, Task } from '@/views/overseas/types'
import OverseasCreate from '@/views/overseas/OverseasCreate.vue'
import { createTask, validateMaterial } from '@/views/overseas/workflow'
import { emptyDraft, exampleDraft, overseasTasks, simulate } from '@/views/overseas/preview-adapter'
const props = defineProps<{ role: Role }>()
const emit = defineEmits<{ back: []; created: [task: Task] }>()
const draft = ref(emptyDraft()), error = ref(''), fail = ref(false)
const kinds: { key: Material["kind"]; label: string; accept: string }[] = [
  { key: "requirement", label: "图片需求文件", accept: ".pdf,.doc,.docx" },
  { key: "competitor", label: "竞品分析表格", accept: ".xlsx,.xls,.csv" },
];
function setFile(file: Material) {
  if (props.role !== "operator") return;
  validateMaterial(file);
  draft.value.files = [
    ...draft.value.files.filter((f) => f.kind !== file.kind),
    file,
  ];
}
function pick(file: UploadFile, kind: Material["kind"]) {
  try {
    setFile({ name: file.name, size: file.size ?? 0, kind, sample: false });
    error.value = "";
  } catch (e) {
    error.value = (e as Error).message;
  }
}
function sample(kind: Material["kind"]) {
  setFile({
    name: kind === "requirement" ? "图片需求示例.pdf" : "竞品分析示例.xlsx",
    size: 2048,
    kind,
    sample: true,
  });
}
function submit() {
  try {
    const task = createTask(draft.value, props.role, `OS-${Date.now()}`);
    overseasTasks.unshift(task);
    const stored = overseasTasks[0];
    simulate(stored, fail.value);
    emit("created", stored);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
</script>
<style scoped>
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.actions { display: flex; gap: 10px; justify-content: flex-end; flex-wrap: wrap; }
.file-row { overflow-wrap: anywhere; font-size: 13px; }
h3 { font-size: 14px; margin-bottom: 12px; }
@media (max-width: 600px) { .form-grid { grid-template-columns: 1fr; } .actions > .el-button { margin-left: 0; } }
</style>
