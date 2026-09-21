<template>
  <ElCard class="hx-gap hx-task-template" shadow="never">
    <template #header><strong>任务绑定</strong></template>
    <div class="hx-binding-summary" role="group" aria-label="任务绑定摘要">
      <div class="hx-binding-item">
        <span class="hx-binding-label">模板</span>
        <strong class="hx-binding-name">{{ templateName }}</strong>
        <ElTag v-if="showTemplateVersion" type="info">
          {{ templateVersionLabel }}
        </ElTag>
      </div>
      <div class="hx-binding-item">
        <span class="hx-binding-label">Skill</span>
        <strong class="hx-binding-name">{{ skillName || "未记录" }}</strong>
      </div>
    </div>
    <p class="hx-footnote">
      以上绑定来自任务提交时的快照，后续模板或 Skill
      更新不影响此任务。
    </p>
    <ElCollapse v-model="technicalDetailsOpen" class="hx-binding-details">
      <ElCollapseItem name="technical">
        <template #title>技术详情</template>
        <dl class="hx-technical-details" aria-label="任务绑定技术详情">
          <div>
            <dt>Skill 快照 ID</dt>
            <dd>
              <span
                class="hx-truncated-value"
                :title="skillId || '未记录'"
                :aria-label="skillId || '未记录'"
              >
                {{ shortSkillId }}
              </span>
              <ElButton
                v-if="skillId"
                class="hx-copy-button"
                text
                type="primary"
                size="small"
                @click="copyValue(skillId, 'Skill 快照 ID')"
              >
                复制
              </ElButton>
            </dd>
          </div>
          <div>
            <dt>内容校验和</dt>
            <dd>
              <span
                class="hx-truncated-value"
                :title="skillChecksum || '未记录'"
                :aria-label="skillChecksum || '未记录'"
              >
                {{ shortSkillChecksum }}
              </span>
              <ElButton
                v-if="skillChecksum"
                class="hx-copy-button"
                text
                type="primary"
                size="small"
                @click="copyValue(skillChecksum, '内容校验和')"
              >
                复制
              </ElButton>
            </dd>
          </div>
        </dl>
        <p class="hx-footnote">
          长值已缩略显示，悬停可查看完整值，也可复制后用于排查。
        </p>
      </ElCollapseItem>
    </ElCollapse>
  </ElCard>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";

import type { Task } from "@/types/hengxin";

const props = defineProps<{ task: Task }>();
const technicalDetailsOpen = ref<string[]>([]);

const templateName = computed(() => {
  const name =
    props.task.templateSnapshot?.name?.trim() || props.task.template.trim();
  return name || (props.task.mode === "text" ? "未使用模板" : "未保留模板信息");
});

const templateVersion = computed(() => {
  const value =
    props.task.templateSnapshot?.version ?? props.task.templateVersion;
  return typeof value === "number" && Number.isInteger(value) && value > 0
    ? value
    : null;
});

const showTemplateVersion = computed(
  () =>
    props.task.mode !== "text" ||
    Boolean(props.task.templateSnapshot) ||
    templateVersion.value !== null,
);
const templateVersionLabel = computed(() =>
  templateVersion.value === null ? "版本未记录" : `v${templateVersion.value}`,
);
const skillName = computed(() => props.task.skillSnapshot?.name?.trim() || "");
const skillId = computed(
  () =>
    props.task.skillSnapshot?.id?.trim() || props.task.skillVersionId.trim(),
);
const skillChecksum = computed(
  () => props.task.skillSnapshot?.checksum?.trim() || "",
);
const shortSkillId = computed(() => shorten(skillId.value, 8, 5));
const shortSkillChecksum = computed(() => shorten(skillChecksum.value, 12, 8));

function shorten(value: string, prefix: number, suffix: number) {
  if (!value) return "未记录";
  if (value.length <= prefix + suffix + 1) return value;
  return `${value.slice(0, prefix)}…${value.slice(-suffix)}`;
}

async function copyValue(value: string, label: string) {
  try {
    await navigator.clipboard.writeText(value);
    ElMessage.success(`${label}已复制`);
  } catch {
    ElMessage.error(`${label}复制失败，请手动复制`);
  }
}
</script>

<style scoped>
.hx-task-template {
  min-width: 0;
}

.hx-task-template .hx-footnote {
  margin: 10px 0 0;
}

.hx-binding-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 24px;
}

.hx-binding-item {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
}

.hx-binding-label {
  flex: none;
  color: var(--hx-muted, #64748b);
  font-size: 12px;
}

.hx-binding-name {
  min-width: 0;
  overflow-wrap: anywhere;
}

.hx-binding-details {
  margin-top: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
  border-bottom: 0;
}

.hx-technical-details {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 24px;
  margin: 0;
}

.hx-technical-details > div {
  min-width: 0;
}

.hx-technical-details dt {
  color: var(--hx-muted, #64748b);
  font-size: 12px;
}

.hx-technical-details dd {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
  margin: 4px 0 0;
}

.hx-truncated-value {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}

.hx-copy-button {
  flex: none;
}

@media (max-width: 640px) {
  .hx-binding-summary,
  .hx-technical-details {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
