<template>
  <div class="flex w-full h-screen overflow-auto">
    <LoginLeftView />
    <div class="relative flex-1">
      <AuthTopBar />
      <div class="auth-right-wrap">
        <div class="form">
          <h3 class="title brand-title">
            <img
              class="block dark:hidden"
              src="@imgs/brand/logo-horizontal.svg"
              alt="恒鑫智图 · 企业 AI 生图平台"
            /><img
              class="hidden dark:block"
              src="@imgs/brand/logo-horizontal-white.svg"
              alt="恒鑫智图 · 企业 AI 生图平台"
            />
          </h3>
          <BusinessEntry
            v-if="previewSession.authenticated"
            :identity="previewSession"
            @enter="enter"
            @logout="logout"
          />
          <template v-else>
            <p class="sub-title">使用企业钉钉身份登录工作区</p>
            <ElTag class="hx-gap">电脑浏览器 · 网页授权</ElTag>
            <ElAlert
              class="hx-gap"
              :title="error || '登录后将验证企业成员资格与各业务权限。'"
              :type="error ? 'warning' : 'info'"
              :closable="false"
              show-icon
            />
            <ElButton
              class="hx-full hx-gap"
              type="primary"
              :loading="busy"
              @click="authorize"
              >钉钉登录</ElButton
            >
          </template>

        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import LoginLeftView from "@/components/core/views/login/LoginLeftView.vue";
import AuthTopBar from "@/components/core/views/login/AuthTopBar.vue";
import BusinessEntry from "@/views/auth/BusinessEntry.vue";
import {
  mayEnter,
  type AccessScenario,
  type Business,
  type OverseasRole,
} from "./access";
import { previewSession, authorizePreview, logoutPreview } from "./session";
const router = useRouter();
// 仅供本地浏览器验收的 URL 场景，不在登录产品界面展示测试配置。
const params = new URLSearchParams(window.location.search);
const scenario: AccessScenario = ['domestic', 'overseas', 'none'].includes(params.get('access') || '')
  ? params.get('access') as AccessScenario : 'both';
const role: OverseasRole = params.get('role') === 'designer' ? 'designer'
  : params.get('role') === 'operator' ? 'operator' : 'admin';
const result = params.get('authResult') || 'success';
const busy = ref(false), error = ref('');
async function authorize() {
  busy.value = true;
  error.value = "";
  await new Promise((resolve) => setTimeout(resolve, 400));
  busy.value = false;
  if (result !== "success") {
    error.value =
      result === "denied"
        ? "你已拒绝授权，请重新授权。"
        : "认证服务暂不可用，请稍后重试。";
    return;
  }
  authorizePreview(scenario, role);
  await router.replace("/business");
}
function enter(business: Business) {
  if (mayEnter(previewSession, business))
    void router.push(
      business === "overseas" ? "/overseas/create" : "/domestic",
    );
}
function logout() {
  logoutPreview();
  void router.replace("/auth/login");
}
</script>
<style scoped>
@import "../views/auth/login/style.css";
.auth-right-wrap {
  position: relative;
  inset: auto;
  min-height: 100vh;
  height: auto;
  overflow: visible;
  padding-block: 90px 32px;
}
.auth-right-wrap .form {
  height: auto;
  padding-block: 16px;
}
.brand-title img {
  width: 280px;
  max-width: 100%;
  height: auto;
}
</style>
