<template>
  <ElCard class="art-card hx-section hx-admin-settings-card">
    <div class="hx-admin-section-head">
      <div>
        <span class="hx-admin-kicker">SYSTEM SETTINGS</span>
        <h2>海外业务配置草案</h2>
        <p>
          仅保存表单配置，尚未接入调度、清理或真实服务。初始值为预览示例，不代表已确认的生产限制。
        </p>
      </div>
      <ElTag type="info">本地预览</ElTag>
    </div>
    <ElForm label-position="top" @submit.prevent="save">
      <ElFormItem label="系统名称" required
        ><ElInput v-model="form.name" aria-label="系统名称" maxlength="40"
      /></ElFormItem>
      <ElFormItem label="任务并发上限（套，1–20）" required
        ><ElInputNumber
          v-model="form.concurrency"
          aria-label="任务并发上限"
          :min="1"
          :max="20"
          :precision="0"
      /></ElFormItem>
      <ElFormItem label="执行时限（秒，30–3600）" required
        ><ElInputNumber
          v-model="form.timeout"
          aria-label="执行时限"
          :min="30"
          :max="3600"
          :precision="0"
      /></ElFormItem>
      <ElFormItem label="过程数据保留（天，1–365）" required
        ><ElInputNumber
          v-model="form.retention"
          aria-label="过程数据保留"
          :min="1"
          :max="365"
          :precision="0"
      /></ElFormItem>
      <ElAlert
        v-if="error"
        class="hx-gap"
        :title="error"
        type="error"
        :closable="false"
      />
      <div class="hx-admin-toolbar-actions hx-gap">
        <ElButton @click="restore">重置未保存修改</ElButton
        ><ElButton type="primary" @click="save">保存本地配置</ElButton>
      </div>
    </ElForm>
    <p class="hx-footnote" role="status">
      {{
        dirty ? "有未保存修改" : "当前表单与本地已保存配置一致"
      }}。重置将恢复上一次保存值；刷新或退出后恢复初始示例值。
    </p>
  </ElCard>
</template>
<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import {
  ElAlert,
  ElButton,
  ElCard,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElTag,
} from "element-plus";
import { settings, saveSettings } from "./management-adapter";
const form = reactive({ ...settings }),
  error = ref("");
const dirty = computed(() => JSON.stringify(form) !== JSON.stringify(settings));
function restore() {
  Object.assign(form, settings);
  error.value = "";
}
function save() {
  try {
    saveSettings(form);
    restore();
    ElMessage.success("配置已保存到本地预览");
  } catch (e) {
    error.value = e instanceof Error ? e.message : "保存失败";
  }
}
</script>
