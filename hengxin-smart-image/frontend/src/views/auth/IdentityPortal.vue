<template>
  <div v-if="overseas && member && !busy" :key="member.id" :inert="checking" :aria-busy="checking">
    <OverseasPortal :member="member" @member="member = $event" @switch="switchBusiness" @logout="logout" @failure="businessFailure" />
  </div>
  <div v-else class="flex w-full h-screen overflow-auto">
    <LoginLeftView />
    <div class="relative flex-1">
      <AuthTopBar />
      <div class="auth-right-wrap"><div class="form">
        <h3 class="title brand-title">
          <img class="block dark:hidden" src="@imgs/brand/logo-horizontal.svg" alt="恒鑫智图 · 企业 AI 生图平台" />
          <img class="hidden dark:block" src="@imgs/brand/logo-horizontal-white.svg" alt="恒鑫智图 · 企业 AI 生图平台" />
        </h3>
        <p v-if="busy" role="status">正在验证企业身份与业务权限…</p>
        <ElAlert v-if="error" class="hx-gap" :title="error" type="warning" :closable="false" show-icon />
        <BusinessEntry v-if="name" :identity="access" :states="states" :busy="busy" @enter="enter" @apply="application($event, false)" @withdraw="application($event, true)" @retry="load" @logout="logout" />
        <template v-else-if="!busy">
          <p class="sub-title">使用企业钉钉身份登录工作区</p>
          <ElButton class="w-full hx-gap" type="primary" :disabled="!config?.configured" @click="authorize">钉钉登录</ElButton>
          <ElButton class="w-full hx-gap" @click="legacySession">已有国内会话，重新连接</ElButton>
        </template>
        <ElButton v-if="error || hasFailure" class="w-full hx-gap" :loading="busy" @click="load">重新连接</ElButton>
      </div></div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import LoginLeftView from '@/components/core/views/login/LoginLeftView.vue'
import AuthTopBar from '@/components/core/views/login/AuthTopBar.vue'
import BusinessEntry from './BusinessEntry.vue'
import OverseasPortal from '@/views/overseas/OverseasPortal.vue'
import { identityApi, IdentityError, type IdentityConfig, type AccessResult, type Member } from '@/api/identity/auth'
import { requestContainerAuthCode } from '@/api/hengxin/container-auth'
import type { Business } from '@/api/identity/access'
import { createOverseasRevalidator } from '@/api/identity/revalidate'
const callbackError = new URLSearchParams(window.location.hash.split('?')[1] || '').get('auth')
const busy = ref(false), error = ref(''), name = ref('')
const identitySession = ref('')
const checking = ref(false)
const config = ref<IdentityConfig>(), member = ref<Member>()
const states = ref<Partial<Record<Business, AccessResult>>>({})
const overseas = ref(window.location.hash.startsWith('#/overseas'))
const access = computed(() => ({ authenticated: !!name.value, domestic: !busy.value && states.value.domestic?.state === 'allowed', overseas: !busy.value && states.value.overseas?.state === 'allowed' }))
const hasFailure = computed(() => Object.values(states.value).some(v => v.state === 'error'))
function businessFailure(reason: unknown) {
  revalidator.invalidate()
  ++generation; member.value = undefined; states.value = {}; busy.value = false
  error.value = reason instanceof Error ? reason.message : '业务连接失败，请重新连接'
  if (reason instanceof IdentityError && reason.status === 401) { name.value = ''; overseas.value = false }
}
let generation = 0
const revalidator = createOverseasRevalidator({
  identity: () => identityApi.me(), member: () => identityApi.overseasMe(),
  accept(current, identityName) { member.value = current; name.value = identityName; identitySession.value = current.identitySessionId },
  reject: businessFailure,
  pending(value) {
    checking.value = value
    // Element弹层teleport到body，必须连同页面一起阻止核验期间的交互。
    document.body.inert = value
  }
})
async function load() {
  revalidator.invalidate()
  const epoch = ++generation
  overseas.value = window.location.hash.startsWith('#/overseas')
  busy.value = true; error.value = ''; name.value = ''; states.value = {}; member.value = undefined
  try {
    try { config.value = await identityApi.config() }
    catch (reason) {
      if (epoch !== generation) return
      if (reason instanceof IdentityError && reason.status === 404) { legacySession(); return }
      throw reason
    }
    if (epoch !== generation) return
    const identity = await identityApi.me()
    if (epoch !== generation) return
    name.value = identity.name
    identitySession.value = identity.sessionId
    const [domestic, foreign] = await Promise.all([identityApi.access('domestic', identity.sessionId), identityApi.access('overseas', identity.sessionId)])
    if (epoch !== generation) return
    const verified = await identityApi.me()
    if (epoch !== generation) return
    if (verified.sessionId !== identity.sessionId || [domestic, foreign].some(result => result.state === 'allowed' && result.member.identitySessionId !== identity.sessionId)) throw new IdentityError(401, '企业身份已变化，请重新选择业务')
    states.value = { domestic, overseas: foreign }
    if (overseas.value && foreign.state === 'allowed') {
      let current: Member
      try { current = await identityApi.overseasMe() }
      catch (reason) {
        if (!(reason instanceof IdentityError) || reason.status !== 401) throw reason
        if (epoch !== generation) return
        current = await identityApi.session('overseas', identity.sessionId)
      }
      if (epoch !== generation) return
      const latest = await identityApi.me()
      if (current.identitySessionId !== identity.sessionId || latest.sessionId !== identity.sessionId) throw new IdentityError(401, '企业身份已变化，请重新选择业务')
      if (epoch === generation) member.value = current
    }
    else overseas.value = false
  } catch (reason) {
    if (epoch !== generation) return
    error.value = !config.value?.configured && config.value ? '钉钉认证尚未配置，请联系管理员' : reason instanceof Error ? reason.message : '服务暂不可用，请重试'
    if (reason instanceof IdentityError && reason.status === 401) { if (callbackError === 'provider_error') error.value = '钉钉授权失败，请重新授权'; name.value = ''; overseas.value = false; states.value = {} }
  } finally { if (epoch === generation) busy.value = false }
}
function legacySession() { window.location.assign('/?workspace=domestic#/api-image-edits/create') }
async function authorize() {
  if (!config.value?.configured) return
  if (!/DingTalk/i.test(navigator.userAgent)) { window.location.assign('/api/identity/v1/dingtalk/authorize'); return }
  const epoch = ++generation
  busy.value = true; error.value = ''
  try {
    const code = await requestContainerAuthCode({ ...config.value, callbackPath: '' })
    if (epoch !== generation) return
    await identityApi.container(code)
    if (epoch !== generation) return
    await load()
  } catch (reason) { if (epoch === generation) error.value = reason instanceof Error ? reason.message : '授权失败，请重试' }
  finally { if (epoch === generation) busy.value = false }
}
async function enter(business: Business) {
  if (busy.value || !access.value[business]) return
  const epoch = ++generation
  busy.value = true; error.value = ''
  try {
    const current = await identityApi.session(business, identitySession.value)
    if (epoch !== generation) return
    const latest = await identityApi.me()
    if (epoch !== generation) return
    if (current.identitySessionId !== identitySession.value || latest.sessionId !== identitySession.value) throw new IdentityError(401, '企业身份已变化，请重新选择业务')
    if (business === 'domestic') { legacySession(); return }
    member.value = current; overseas.value = true; window.location.hash = '/overseas/tasks'
  }
  catch (reason) { if (epoch === generation) businessFailure(reason) }
  finally { if (epoch === generation) busy.value = false }
}
async function application(business: Business, withdraw: boolean) {
  if (busy.value) return
  const state = states.value[business]?.state
  if (withdraw ? state !== 'pending' : !['unregistered', 'rejected', 'legacy_unconfirmed'].includes(state || '')) return
  const label = business === 'domestic' ? '国内' : '海外'
  const epoch = ++generation
  busy.value = true; error.value = ''
  try {
    try { await ElMessageBox.confirm(withdraw ? `确认撤回${label}业务加入申请？` : `确认向${label}业务管理员申请加入？姓名来自当前企业身份，审批通过后才可进入。`, withdraw ? `撤回${label}申请` : `申请${label}权限`, { confirmButtonText: withdraw ? '确认撤回' : '确认申请', cancelButtonText: '取消', type: 'warning' }) } catch { return }
    if (epoch !== generation) return
    const latest = await identityApi.me()
    if (epoch !== generation) return
    if (latest.sessionId !== identitySession.value) throw new IdentityError(401, '企业身份已变化，请重新登录')
    await (withdraw ? identityApi.withdraw(business, identitySession.value) : identityApi.apply(business, identitySession.value))
    if (epoch !== generation) return
    ElMessage.success(withdraw ? `${label}申请已撤回` : `${label}申请已提交`)
    await load()
  } catch (reason) { if (epoch === generation) { if (reason instanceof IdentityError && reason.status === 401) businessFailure(reason); else error.value = reason instanceof Error ? reason.message : '申请操作失败，请重试' } }
  finally { if (epoch === generation) busy.value = false }
}
function switchBusiness() { revalidator.invalidate(); overseas.value = false; member.value = undefined; window.location.hash = '/auth/business'; void load() }
async function logout() {
  revalidator.invalidate()
  const epoch = ++generation
  busy.value = true; error.value = ''; member.value = undefined; overseas.value = false; states.value = {}
  try { await identityApi.logout(); if (epoch !== generation) return; try { localStorage.setItem('hengxin:logout', crypto.randomUUID()) } catch { /* 服务端已撤销 */ }; name.value = ''; states.value = {}; window.location.hash = '/auth/business' }
  catch (reason) { if (epoch === generation) error.value = reason instanceof Error ? reason.message : '退出失败，请重试' }
  finally { if (epoch === generation) busy.value = false }
}
function navigated() {
  const foreign = window.location.hash.startsWith('#/overseas')
  if (foreign !== overseas.value) { overseas.value = foreign; void load() }
}
function changed(event: StorageEvent) { if (event.key === 'hengxin:logout') void load() }
function resume() {
  if (document.visibilityState !== 'visible' || busy.value) return
  if (overseas.value && member.value) void revalidator.run()
  else void load()
}
onMounted(() => { void load(); window.addEventListener('focus', resume); window.addEventListener('storage', changed); window.addEventListener('hashchange', navigated); document.addEventListener('visibilitychange', resume) })
onUnmounted(() => { revalidator.invalidate(); ++generation; ElMessageBox.close(); window.removeEventListener('focus', resume); window.removeEventListener('storage', changed); window.removeEventListener('hashchange', navigated); document.removeEventListener('visibilitychange', resume) })
</script>
<style scoped>
@import './login/style.css';
.auth-right-wrap { position: relative; inset: auto; min-height: 100vh; height: auto; overflow: visible; padding-block: 90px 32px; }
.auth-right-wrap .form { height: auto; padding-block: 16px; }
.brand-title img { width: 280px; max-width: 100%; height: auto; }
.el-button + .el-button { margin-left: 0; }
</style>
