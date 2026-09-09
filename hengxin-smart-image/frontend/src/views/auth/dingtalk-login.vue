<template>
  <div class="flex w-full h-screen overflow-auto">
    <LoginLeftView />
    <div class="relative flex-1">
      <AuthTopBar />
      <div class="auth-right-wrap">
        <div class="form">
          <h3 class="title">恒信 AI 换套图</h3>
          <p class="sub-title">使用企业钉钉身份登录工作区</p>
          <ElTag class="hx-gap">{{ container ? '钉钉电脑端 · 容器免登' : '电脑浏览器 · 网页授权' }}</ElTag>
          <ElAlert class="hx-gap" :title="message" :type="state === 'success' ? 'info' : state === 'authorizing' ? 'info' : 'warning'" :closable="false" show-icon />
          <p class="hx-gap" v-if="state === 'authorizing'" role="status">正在验证企业身份…</p>
          <ElButton class="w-full hx-gap" type="primary" :loading="busy" @click="authorize">
            {{ state === 'success' ? (container ? '钉钉免登' : '钉钉登录') : '重新授权' }}
          </ElButton>
          <ElButton v-if="!isMockMode" class="w-full hx-gap" :loading="bootstrap.loading" @click="reconnect">已有会话，重新连接</ElButton>
          <template v-if="isMockMode">
            <ElDivider>模拟登录预览</ElDivider>
            <ElForm label-position="top">
              <ElFormItem label="预览角色">
                <ElSelect v-model="role" aria-label="预览角色">
                  <ElOption v-for="item in previewRoles" :key="item.value" :label="item.label" :value="item.value" />
                </ElSelect>
              </ElFormItem>
              <ElFormItem label="登录场景">
                <ElSelect v-model="state" aria-label="登录场景" @change="changeScenario">
                  <ElOption v-for="item in loginScenarios" :key="item" :label="labels[item]" :value="item" />
                </ElSelect>
              </ElFormItem>
              <ElFormItem label="入口预览">
                <ElRadioGroup v-model="container"><ElRadioButton :value="false">浏览器</ElRadioButton><ElRadioButton :value="true">钉钉容器</ElRadioButton></ElRadioGroup>
              </ElFormItem>
            </ElForm>
            <p class="sub-title">仅演示前端状态；未连接钉钉 SDK，不代表真实认证或容器兼容验收。</p>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { isMockMode } from '@/api/hengxin/client'
import { bootstrap, retryBootstrap } from '@/api/hengxin/bootstrap'
import { router } from '@/router'
import { getLoginScenario, getPreviewUser, loginScenarios, previewRoles, safeReturnPath, type LoginScenario } from '@/api/hengxin/session'

const state = ref<LoginScenario>(isMockMode ? getLoginScenario() : 'success')
const role = ref(isMockMode ? getPreviewUser().role ?? 'operator' : 'operator')
const container = ref(/DingTalk/i.test(navigator.userAgent))
const busy = ref(false)
const labels: Record<LoginScenario, string> = {
  success: '正常登录', authorizing: '授权中', denied: '拒绝授权', expired: '会话过期',
  pending: '待管理员授权', disabled: '账号已禁用', 'enterprise-mismatch': '企业不匹配', unavailable: '认证服务不可用'
}
const descriptions: Record<LoginScenario, string> = {
  success: '登录后将验证企业成员资格与系统角色。', authorizing: '正在等待钉钉授权结果，可重新发起授权。',
  denied: '你已拒绝授权，请重新授权后进入工作区。', expired: '会话已过期，请重新登录。',
  pending: '企业身份已验证，等待超级管理员分配角色。', disabled: '账号已禁用，请联系超级管理员。',
  'enterprise-mismatch': '当前账号不属于目标企业，请切换企业账号后重试。', unavailable: '认证服务暂不可用，请稍后重试。'
}
const message = computed(() => bootstrap.error || descriptions[state.value])
function changeScenario() { bootstrap.error = '' }
function destination() {
  const hashQuery = window.location.hash.split('?')[1] ?? ''
  return safeReturnPath(new URLSearchParams(hashQuery).get('redirect') ?? new URLSearchParams(window.location.search).get('redirect') ?? window.location.hash.slice(1))
}
function enterWorkspace() {
  const url = new URL(window.location.href)
  url.pathname = '/'
  url.searchParams.delete('auth')
  url.searchParams.delete('redirect')
  if (isMockMode) url.searchParams.set('role', role.value)
  url.hash = destination()
  window.location.replace(url.href)
}
async function authorize() {
  bootstrap.error = ''
  if (!isMockMode) {
    state.value = 'unavailable'
    bootstrap.error = '钉钉认证服务尚未接入，请联系管理员；真实授权将在后端接入阶段启用。'
    return
  }
  const result = state.value
  busy.value = true
  state.value = 'authorizing'
  await new Promise(resolve => setTimeout(resolve, 450))
  busy.value = false
  state.value = result
  if (result === 'success' || result === 'expired') enterWorkspace()
}
async function reconnect() {
  await retryBootstrap.run()
  // 会话重连保留当前应用内存中的未确认请求；整页跳转会丢失原幂等键。
  if (bootstrap.ready) await router.replace(destination())
}
</script>
<style scoped>
@import './login/style.css';
.auth-right-wrap { position: relative; inset: auto; min-height: 100vh; height: auto; overflow: visible; padding-block: 90px 32px; }
.auth-right-wrap .form { height: auto; padding-block: 16px; }
.el-button + .el-button { margin-left: 0; }
</style>
