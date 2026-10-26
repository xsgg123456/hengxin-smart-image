<template>
  <div class="hx-page auth-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">CODEX ACCOUNT</span><h1>Codex 账号</h1><p>管理{{ businessNames[side] }}使用的账号，授权失效后可在这里重新登录。</p></div><ElButton :loading="checking" :disabled="!account.email || loginOpen" @click="check">检测连接</ElButton></div>
    <div class="hx-stack">
      <ElCard class="art-card hx-section hx-admin-settings-card">
        <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">{{ side === 'domestic' ? 'DOMESTIC BUSINESS' : 'OVERSEAS BUSINESS' }}</span><div class="auth-status-title"><h2>{{ businessNames[side] }}账号</h2><ElTag :type="statusTypes[account.status]">{{ statusNames[account.status] }}</ElTag></div><p>仅用于{{ side === 'domestic' ? '国内业务的 CLI 图片修改' : '海外业务的 AI 设计工作台' }}，与{{ other }}账号独立配置。</p></div><ElTag type="info">管理员可配置</ElTag></div>
        <ElAlert v-if="account.status === 'expired'" title="授权已失效，请使用原账号重新授权" description="授权恢复后可继续原会话。已失败的操作不会自动重跑，请返回任务重新发送。" type="error" :closable="false" show-icon />
        <ElAlert v-else-if="account.status === 'network'" title="暂时无法连接，尚不能确定授权是否失效" description="请先检查连接并重试，无需立即更换账号。当前账号配置仍保留。" type="warning" :closable="false" show-icon />
        <ElAlert v-else-if="notice" :title="notice" type="success" :closable="false" show-icon />
        <ElEmpty v-if="account.status === 'empty'" description="当前业务尚未配置 Codex 账号" :image-size="80"><ElButton type="primary" @click="start('connect')">登录并授权</ElButton><p class="hx-footnote">可与{{ other }}使用相同账号，也可以单独登录其他账号。</p></ElEmpty>
        <template v-else>
          <dl class="auth-details"><div><dt>当前账号</dt><dd>{{ account.email }}</dd></div><div><dt>工作区</dt><dd>{{ account.workspace }}</dd></div><div><dt>最近检测 · 北京时间</dt><dd>{{ account.checked || '尚未检测' }}</dd></div><div><dt>最近更新 · 北京时间</dt><dd>{{ account.updated }}</dd></div></dl>
          <div class="auth-actions"><ElButton type="primary" :disabled="checking" @click="start('renew')">重新授权</ElButton><ElButton :disabled="checking" @click="start('replace')">更换账号</ElButton><span class="hx-footnote" style="margin:0">通过官方页面登录，无需填写账号密码或上传凭据文件。</span></div>
          <div class="auth-separator"><span class="hx-footnote" style="margin:0">移除后，当前业务需重新授权才能继续使用 Codex。任务与历史记录保留。</span><ElButton type="danger" plain :disabled="checking" @click="removeOpen = true">移除配置</ElButton></div>
        </template>
      </ElCard>
      <ElCard class="art-card hx-section hx-admin-settings-card">
        <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">AUTHORIZATION HISTORY</span><h2>授权操作记录</h2><p>仅展示{{ businessNames[side] }}的操作记录，不展示授权凭据。</p></div></div>
        <ElTable :data="account.audit" empty-text="暂无授权操作记录"><ElTableColumn prop="time" label="操作时间（北京时间）" min-width="185" /><ElTableColumn prop="operator" label="操作者" min-width="150" /><ElTableColumn prop="action" label="操作" min-width="180" /><ElTableColumn prop="result" label="结果" min-width="120" /></ElTable>
      </ElCard>
    </div>
    <p class="auth-disclosure">重新授权建议使用原账号和原工作区；更换账号后，新任务使用新账号，旧会话能否续接需单独确认。</p>
    <AuthorizationDialog v-if="loginOpen" :side="side" :intent="intent" :current-email="account.email" @close="loginOpen = false" @activate="enabled" />
    <ElDialog v-model="removeOpen" title="移除当前业务账号配置？" width="min(520px, calc(100vw - 32px))" align-center>
      <p class="hx-muted">将移除{{ businessNames[side] }}的 {{ account.email }} 账号配置。任务与历史记录保留，后续使用 Codex 需重新授权。{{ other }}配置不受影响。</p>
      <template #footer><ElButton @click="removeOpen = false">取消</ElButton><ElButton type="danger" @click="confirmRemove">确认移除</ElButton></template>
    </ElDialog>
  </div>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AuthorizationDialog from './AuthorizationDialog.vue'
import { accounts, activate, audit, businessNames, now, remove, statusNames, statusTypes, type Business } from './model'
const props = defineProps<{side: Business}>()
const account = computed(() => accounts[props.side]), other = computed(() => props.side === 'domestic' ? '海外业务' : '国内业务')
const loginOpen = ref(false), removeOpen = ref(false), checking = ref(false), notice = ref('')
const intent = ref<'renew' | 'replace' | 'connect'>('renew')
let timer: ReturnType<typeof setTimeout> | undefined
function start(value: typeof intent.value) { intent.value = value; loginOpen.value = true; notice.value = '' }
function check() {
  if (checking.value || !account.value.email) return
  checking.value = true
  timer = setTimeout(() => {
    account.value.checked = now(); checking.value = false
    const good = account.value.status === 'ready'
    audit(props.side, '检测连接', good ? '可用' : account.value.status === 'network' ? '连接异常，授权状态未确认' : '授权已失效')
    if (good) { notice.value = '连接检测通过，当前账号可用。'; ElMessage.success('演示检测完成：连接正常') }
    else ElMessage.warning(account.value.status === 'network' ? '演示结果：网络异常，原配置保留' : '演示结果：授权已失效，请重新授权')
  }, 650)
}
function enabled(email: string) {
  const firstConnection = !account.value.email
  const changed = !firstConnection && account.value.email !== email
  activate(props.side, email); loginOpen.value = false
  notice.value = firstConnection ? '账号已启用，可用于当前业务的 Codex 调用。' : changed ? '新账号已启用。后续新任务使用新账号，旧会话续接需单独确认。' : '授权已更新，可以返回任务继续原会话；失败操作请重新发送。'
  ElMessage.success('预览配置已更新，仅在当前页面生效')
}
function confirmRemove() { remove(props.side); removeOpen.value = false; notice.value = ''; ElMessage.success('已移除当前业务的演示配置') }
onBeforeUnmount(() => { if (timer) clearTimeout(timer) })
</script>
