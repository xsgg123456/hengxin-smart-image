<template>
  <div class="hx-page">
    <div class="hx-heading">
      <div>
        <span class="hx-eyebrow">OVERSEAS MANAGEMENT</span>
        <h1>{{ titles[page] }}</h1>
        <p>{{ descriptions[page] }}</p>
      </div>
    </div>
    <ElAlert
      class="hx-admin-banner"
      title="海外独立管理预览 · 数据仅保存在本次浏览器内存，刷新或退出后重置；未连接生产服务。"
      type="warning"
      :closable="false"
      show-icon
    />
    <OverseasActivity
      v-if="page === 'usage' || page === 'monitor'"
      :key="page"
      :page="page"
    />
    <OverseasMembers v-else-if="page === 'users'" :adapter="previewMembers" />
    <OverseasSkills v-else-if="page === 'skills'" />
    <OverseasSettings v-else />
  </div>
</template>
<script setup lang="ts">
import { ElAlert } from "element-plus";
import type { ManagementPage } from "./management-adapter";
import OverseasActivity from "./OverseasActivity.vue";
import OverseasMembers from "./OverseasMembers.vue";
import { previewMembers } from './members-preview';
import OverseasSkills from "./OverseasSkills.vue";
import OverseasSettings from "./OverseasSettings.vue";
defineProps<{ page: ManagementPage }>();
const titles = {
  usage: "调用统计",
  monitor: "执行监控",
  users: "用户与角色",
  skills: "Skill 管理",
  settings: "系统配置",
};
const descriptions = {
  usage: "查看当前海外任务与流程记录，统计随本地操作实时更新。",
  monitor: "查看海外分析、生图及单图返工的当前执行状态。",
  users: "独立维护海外成员目录与角色配置。",
  skills: "查看海外已安装 Skill 的名称与描述。",
  settings: "编辑海外业务配置草案，保存后可在本次预览中重新读取。",
};
</script>
