<template>
  <div class="hx-page auth-page">
    <div class="hx-heading"><div><span class="hx-eyebrow">CODEX ACCOUNT</span><h1>Codex 账号</h1><p>管理{{ businessNames[side] }}使用的账号，授权失效后可在这里重新登录。</p></div><ElButton :loading="busy || account?.checking" :disabled="!account || account.status === 'empty' || loginOpen || loading || !!error" @click="check">检测连接</ElButton></div>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon><ElButton text :loading="loading" :disabled="busy || loginOpen" @click="load">重新读取当前配置</ElButton></ElAlert>
    <ElCard v-if="!account && loading" class="art-card hx-section"><p role="status">正在读取账号配置…</p><ElSkeleton :rows="5" animated /></ElCard>
    <div v-if="account" class="hx-stack">
      <ElCard class="art-card hx-section hx-admin-settings-card">
        <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">{{ side === 'domestic' ? 'DOMESTIC BUSINESS' : 'OVERSEAS BUSINESS' }}</span><div class="auth-status-title"><h2>{{ businessNames[side] }}账号</h2><ElTag :type="statusTypes[account.status]">{{ statusNames[account.status] }}</ElTag></div><p>仅用于{{ side === 'domestic' ? '国内业务的 CLI 图片修改' : '海外业务的 AI 设计工作台' }}，与{{ other }}账号独立配置。</p></div><ElTag type="info">有管理权限可配置</ElTag></div>
        <ElAlert v-if="account.status === 'expired'" title="授权已失效，请使用原账号重新授权" description="授权恢复后可继续原会话。已失败的操作不会自动重跑，请返回任务重新发送。" type="error" :closable="false" show-icon />
        <ElAlert v-else-if="account.status === 'network'" title="暂时无法连接，尚不能确定授权是否失效" description="请先检查连接并重试，无需立即更换账号。当前账号配置仍保留。" type="warning" :closable="false" show-icon />
        <ElAlert v-else-if="account.status === 'unchecked'" title="当前账号尚未进行真实连接检测" description="请点击检测连接，确认授权是否可用。" type="info" :closable="false" show-icon />
        <ElAlert v-else-if="notice" :title="notice" type="success" :closable="false" show-icon />
        <ElEmpty v-if="account.status === 'empty'" description="当前业务尚未配置 Codex 账号" :image-size="80"><ElButton type="primary" :disabled="disabled" @click="start('connect')">登录并授权</ElButton><p class="hx-footnote">可与{{ other }}使用相同账号，也可以单独登录其他账号。</p></ElEmpty>
        <template v-else>
          <dl class="auth-details"><div><dt>当前账号</dt><dd>{{ account.email || '未提供邮箱' }}</dd></div><div><dt>工作区</dt><dd>{{ account.workspace || '未提供工作区标识' }}</dd></div><div><dt>最近检测 · 北京时间</dt><dd>{{ account.checked || '尚未检测' }}</dd></div><div><dt>最近更新 · 北京时间</dt><dd>{{ account.updated || '暂无记录' }}</dd></div></dl>
          <div class="auth-actions"><ElButton type="primary" :disabled="disabled" @click="start('renew')">重新授权</ElButton><ElButton :disabled="disabled" @click="start('replace')">更换账号</ElButton><span class="hx-footnote" style="margin:0">通过官方页面登录，无需填写账号密码或上传凭据文件。</span></div>
          <div class="auth-separator"><span class="hx-footnote" style="margin:0">移除后，当前业务需重新授权才能继续使用 Codex。任务与历史记录保留。</span><ElButton type="danger" plain :disabled="disabled" @click="removeOpen = true">移除配置</ElButton></div>
        </template>
      </ElCard>
      <ElCard class="art-card hx-section hx-admin-settings-card">
        <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">AUTHORIZATION HISTORY</span><h2>授权操作记录</h2><p>仅展示{{ businessNames[side] }}的操作记录，不展示授权凭据。</p></div></div>
        <ElTable :data="account.audit" empty-text="暂无授权操作记录"><ElTableColumn prop="time" label="操作时间（北京时间）" min-width="185" /><ElTableColumn prop="operator" label="操作者" min-width="150" /><ElTableColumn prop="action" label="操作" min-width="180" /><ElTableColumn prop="result" label="结果" min-width="120" /></ElTable>
      </ElCard>
    </div>
    <p class="auth-disclosure">重新授权建议使用原账号和原工作区；更换账号后，新任务使用新账号，旧会话能否续接需单独确认。</p>
    <AuthorizationDialog v-if="loginOpen && account" :side="side" :intent="intent" :current="account" :api="api" @close="closed" @activate="activated" @failure="$emit('failure', $event)" />
    <ElDialog v-model="removeOpen" title="移除当前业务账号配置？" width="min(520px, calc(100vw - 32px))" align-center :close-on-click-modal="false" :before-close="closeRemove">
      <p class="hx-muted">将移除{{ businessNames[side] }}的 {{ account?.email || '当前' }} 账号配置。任务与历史记录保留，后续使用 Codex 需重新授权。{{ other }}配置不受影响。</p>
      <ElAlert v-if="error" :title="error" type="error" :closable="false" />
      <template #footer><ElButton :disabled="busy" @click="removeOpen = false">取消</ElButton><ElButton type="danger" :loading="busy" :disabled="loading || !!error" @click="confirmRemove">确认移除</ElButton></template>
    </ElDialog>
  </div>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import AuthorizationDialog from './AuthorizationDialog.vue'
import { businessNames, createCodexAuthApi, statusNames, statusTypes, type Account, type Business, type CodexAuthApi, type Intent } from '../../api/codex-auth'
import { useAccount } from './use-account'
import './style.css'
const props = defineProps<{ side: Business; adapter?: CodexAuthApi }>()
const emit = defineEmits<{ failure: [reason: unknown] }>()
const api = props.adapter || createCodexAuthApi(props.side)
const { account, loading, busy, error, notice, load, mutate, enabled } = useAccount(api, reason => emit('failure', reason))
const other = computed(() => props.side === 'domestic' ? '海外业务' : '国内业务')
const loginOpen = ref(false), removeOpen = ref(false), intent = ref<Intent>('renew')
const disabled = computed(() => busy.value || loading.value || !!account.value?.checking || !!error.value || loginOpen.value)
function start(value: Intent) { if (!disabled.value) { intent.value = value; loginOpen.value = true; notice.value = '' } }
function check() { if (!disabled.value && account.value?.status !== 'empty') void mutate(api.check) }
function activated(result: Account, different: boolean) { enabled(result, different); loginOpen.value = false }
function closed() { loginOpen.value = false; void load() }
function closeRemove(done: () => void) { if (!busy.value) done() }
async function confirmRemove() { if (account.value && await mutate(() => api.remove(account.value!.revision), '已移除当前业务的账号配置')) removeOpen.value = false }
</script>
