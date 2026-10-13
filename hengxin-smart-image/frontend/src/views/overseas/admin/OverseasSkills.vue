<template>
  <ElCard class="art-card hx-section hx-admin-table-card">
    <div class="hx-admin-section-head">
      <div>
        <span class="hx-admin-kicker">WORKFLOW SKILLS</span>
        <h2>海外 Skill 目录</h2>
        <p>
          本地指令配置预览；保存与启停不会调用
          AI，也不会改变当前模拟任务的固定执行逻辑。
        </p>
      </div>
      <ElButton type="primary" @click="edit()">添加 Skill</ElButton>
    </div>
    <div class="hx-filter">
      <ElInput
        v-model="search"
        class="hx-search"
        placeholder="搜索 Skill 名称"
        clearable
        aria-label="搜索 Skill"
      /><ElSelect
        v-model="stage"
        clearable
        placeholder="全部阶段"
        style="width: 160px"
        aria-label="Skill 阶段"
        ><ElOption
          v-for="(label, key) in stages"
          :key="key"
          :label="label"
          :value="key"
      /></ElSelect>
    </div>
    <ArtTable
      height="auto"
      empty-height="280px"
      :data="rows"
      :columns="columns"
      :show-table-header="false"
      :show-pagination="false"
      empty-text="暂无匹配的 Skill，可添加海外工作流指令"
    >
      <template #stage="{ row }">{{
        stages[row.stage as keyof typeof stages]
      }}</template
      ><template #enabled="{ row }"
        ><ElTag :type="row.enabled ? 'success' : 'info'">{{
          row.enabled ? "启用" : "停用"
        }}</ElTag></template
      >
      <template #action="{ row }"
        ><ElButton text type="primary" @click="edit(row)">编辑</ElButton
        ><ElButton text @click="toggle(row)">{{
          row.enabled ? "停用" : "启用"
        }}</ElButton
        ><ElButton text type="danger" @click="remove(row)"
          >删除</ElButton
        ></template
      >
    </ArtTable>
  </ElCard>
  <ElDialog
    v-model="open"
    :title="form.id ? '编辑海外 Skill' : '添加海外 Skill'"
    width="min(680px, 94vw)"
    :close-on-click-modal="false"
  >
    <ElForm label-position="top" @submit.prevent="save"
      ><ElFormItem label="Skill 名称" required
        ><ElInput
          v-model="form.name"
          aria-label="Skill 名称"
          maxlength="60" /></ElFormItem
      ><ElFormItem label="工作流阶段" required
        ><ElSelect v-model="form.stage" aria-label="工作流阶段"
          ><ElOption
            v-for="(label, key) in stages"
            :key="key"
            :label="label"
            :value="key" /></ElSelect></ElFormItem
      ><ElFormItem label="指令内容" required
        ><ElInput
          v-model="form.content"
          aria-label="指令内容"
          type="textarea"
          :rows="8"
          maxlength="8000"
          show-word-limit
          placeholder="输入此阶段应执行的要求" /></ElFormItem
      ><ElFormItem label="启用配置"
        ><ElSwitch v-model="form.enabled" aria-label="启用配置" /></ElFormItem
    ></ElForm>
    <ElAlert
      v-if="error"
      :title="error"
      type="error"
      :closable="false"
    /><template #footer
      ><ElButton @click="open = false">取消</ElButton
      ><ElButton type="primary" @click="save">保存 Skill</ElButton></template
    >
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import {
  ElAlert,
  ElButton,
  ElCard,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElSelect,
  ElSwitch,
  ElTag,
} from "element-plus";
import ArtTable from "@/components/core/tables/art-table/index.vue";
import {
  skills,
  stages,
  saveSkill,
  removeRecord,
  type Skill,
} from "./management-adapter";
const search = ref(""),
  stage = ref(""),
  open = ref(false),
  error = ref("");
const blank = (): Skill => ({
  id: "",
  name: "",
  stage: "analysis",
  content: "",
  enabled: true,
});
const form = reactive(blank());
const rows = computed(() =>
  skills.filter(
    (s) =>
      (!stage.value || s.stage === stage.value) &&
      s.name.toLowerCase().includes(search.value.trim().toLowerCase()),
  ),
);
function edit(skill?: Skill) {
  Object.assign(form, skill || blank());
  error.value = "";
  open.value = true;
}
function save() {
  try {
    saveSkill(form);
    open.value = false;
    ElMessage.success("Skill 已保存到本地预览");
  } catch (e) {
    error.value = e instanceof Error ? e.message : "保存失败";
  }
}
async function toggle(skill: Skill) {
  if (skill.enabled) {
    try {
      await ElMessageBox.confirm(
        `停用「${skill.name}」的本地配置？`,
        "停用 Skill",
        {
          type: "warning",
          confirmButtonText: "确认停用",
          cancelButtonText: "取消",
        },
      );
    } catch {
      return;
    }
  }
  saveSkill({ ...skill, enabled: !skill.enabled });
}
async function remove(skill: Skill) {
  try {
    await ElMessageBox.confirm(
      `删除「${skill.name}」及其本地指令内容？`,
      "删除 Skill",
      {
        type: "warning",
        confirmButtonText: "确认删除",
        cancelButtonText: "取消",
      },
    );
    removeRecord(skills, skill.id);
  } catch {
    /* 取消删除 */
  }
}
const columns = [
  { prop: "name", label: "Skill 名称", minWidth: 180 },
  { prop: "stage", label: "工作流阶段", minWidth: 130, useSlot: true },
  { prop: "enabled", label: "状态", width: 90, useSlot: true },
  { prop: "action", label: "操作", width: 220, useSlot: true },
];
</script>
