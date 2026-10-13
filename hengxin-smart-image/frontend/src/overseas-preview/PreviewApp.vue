<template>
  <ElConfigProvider :locale="zh" :z-index="3000">
    <PreviewLogin
      v-if="
        !previewSession.authenticated ||
        route.path === '/business' ||
        route.path === '/auth/login'
      "
    />
    <OverseasShell v-else>
      <template #account><ElTag class="business-label">海外业务</ElTag><ElButton text @click="switchBusiness">切换业务</ElButton><ElButton text @click="logout">退出登录</ElButton></template>
          <div class="preview-toolbar">
            <span class="hx-muted">前端预览 · 模拟数据，刷新重置</span>
            <ElRadioGroup
              :model-value="previewSession.overseasRole"
              size="small"
              aria-label="体验角色"
              @change="changeRole"
              ><ElRadioButton value="admin">管理员</ElRadioButton
              ><ElRadioButton value="operator">运营</ElRadioButton
              ><ElRadioButton value="designer"
                >设计</ElRadioButton
              ></ElRadioGroup
            >
          </div>
          <ArtPageContent />
    </OverseasShell>
  </ElConfigProvider>
</template>
<script setup lang="ts">
import { useRoute, useRouter } from "vue-router";
import { ElMessageBox } from "element-plus";
import zh from "element-plus/es/locale/lang/zh-cn";
import ArtPageContent from "@/components/core/layouts/art-page-content/index.vue";
import { useWorktabStore } from "@/store/modules/worktab";
import PreviewLogin from "./PreviewLogin.vue";
import OverseasShell from "@/views/overseas/OverseasShell.vue";
import { previewSession, logoutPreview } from "./session";
const router = useRouter(),
  route = useRoute();
function clearTabs() {
  const tabs = useWorktabStore();
  tabs.opened = [];
  tabs.current = {};
  tabs.keepAliveExclude = [];
}
function switchBusiness() {
  clearTabs();
  void router.push("/business");
}
async function logout() {
  try {
    await ElMessageBox.confirm(
      "退出后本次预览状态将清空，是否继续？",
      "退出预览",
      { type: "warning" },
    );
  } catch {
    return;
  }
  logoutPreview();
  clearTabs();
  window.location.replace(`${window.location.pathname}#/auth/login`);
}
function changeRole(role: string | number | boolean | undefined) {
  if (role === "operator" || role === "designer" || role === "admin")
    {
      previewSession.overseasRole = role;
      clearTabs();
      if (role !== "admin" && route.path.startsWith("/overseas/management/"))
        void router.replace("/overseas/tasks");
    }
}
</script>
<style lang="scss" scoped>
.preview-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin: 0 28px 8px;
}
.business-label {
  margin-left: 8px;
}
@media (max-width: 640px) {
  .business-label {
    display: none;
  }
  .preview-toolbar {
    margin: 12px 16px;
  }
}
</style>
