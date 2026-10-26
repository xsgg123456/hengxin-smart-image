<template>
  <ElDialog :model-value="true" :title="title" class="auth-dialog" width="min(640px, calc(100vw - 32px))" align-center :close-on-click-modal="false" :before-close="close">
    <ElAlert :title="businessNames[side] + ' · ' + (intent === 'replace' ? '更换账号前，当前配置继续保留' : current.status !== 'empty' ? '请使用原账号和原工作区完成授权' : '请登录要用于当前业务的账号')" :description="current.status !== 'empty' ? '当前账号：' + (current.email || '未提供邮箱') + ' · ' + (current.workspace || '未提供工作区标识') : '授权通过后，还需要确认启用。'" type="info" :closable="false" show-icon />
    <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon><ElButton v-if="!authorization" text :disabled="busy" @click="start">重试获取授权码</ElButton><ElButton v-else text :loading="polling" :disabled="busy" @click="poll">重新读取授权状态</ElButton></ElAlert>
    <div v-if="step === 'starting'" class="auth-checking" role="status"><h3>正在获取授权码…</h3><p class="hx-muted">当前业务配置保持不变。</p><ElSkeleton :rows="2" animated /></div>
    <template v-else-if="step === 'waiting' || step === 'expired'">
      <h3>1. 打开官方授权页，输入授权码</h3>
      <p class="hx-muted auth-url">{{ authorization?.verificationUrl || '等待官方授权地址' }}</p>
      <div class="auth-code"><div><strong>{{ step === 'expired' || remaining === 0 ? '已过期' : authorization?.userCode }}</strong><br><small>仅用于本次官方设备授权</small></div><ElButton :disabled="step === 'expired' || remaining === 0 || !authorization?.userCode" @click="copy">{{ copied ? '已复制' : '复制授权码' }}</ElButton></div>
      <ElButton type="primary" plain :disabled="step === 'expired' || remaining === 0 || !officialUrl" @click="openOfficial">前往官方授权</ElButton>
      <h3>2. 完成登录后，系统检测新授权</h3>
      <p v-if="step === 'waiting' && remaining > 0" class="hx-muted" role="status">等待授权完成 · 剩余 {{ remaining }} 秒</p>
      <ElAlert v-else title="本次授权码已过期，当前账号配置未改变" description="重新获取授权码后再试。" type="warning" :closable="false" show-icon />
    </template>
    <div v-else-if="step === 'checking'" class="auth-checking" role="status"><h3>正在检测新授权…</h3><p class="hx-muted">核对账号、工作区与连接状态，当前配置暂不变更。</p><ElSkeleton :rows="2" animated /></div>
    <template v-else-if="step === 'failed'">
      <ElAlert title="暂时无法检测新授权" :description="authorization?.message || '连接异常，尚未启用新授权。原账号配置仍保留，可重试检测或取消。'" type="warning" :closable="false" show-icon />
      <ElButton v-if="!authorization?.candidateEmail" type="primary" :loading="busy" @click="restart">重新获取授权码</ElButton>
    </template>
    <template v-else-if="step === 'mismatch'">
      <ElAlert title="登录账号或工作区与原身份不一致，暂不启用" :description="authorization?.message || '恢复原会话请使用原账号和原工作区重新登录。如需更换账号，请取消后使用“更换账号”入口。'" type="warning" :closable="false" show-icon />
      <dl class="auth-details"><div><dt>原账号 / 工作区</dt><dd>{{ current.email || '未提供邮箱' }} / {{ current.workspace || '未提供工作区标识' }}</dd></div><div><dt>本次登录 / 工作区</dt><dd>{{ authorization?.candidateEmail || '未提供邮箱' }} / {{ authorization?.candidateWorkspace || '未提供工作区标识' }}</dd></div></dl>
    </template>
    <template v-else-if="step === 'verified'">
      <ElAlert title="新授权检测通过，等待确认启用" description="确认后仅更新当前业务的账号配置。" type="success" :closable="false" show-icon />
      <dl class="auth-details"><div><dt>本次授权账号</dt><dd>{{ authorization?.candidateEmail || '未提供邮箱' }}</dd></div><div><dt>工作区</dt><dd>{{ authorization?.candidateWorkspace || '未提供工作区标识' }}</dd></div><div><dt>连接检测</dt><dd>通过</dd></div><div><dt>生效范围</dt><dd>{{ businessNames[side] }}</dd></div></dl>
      <template v-if="authorization?.different"><ElAlert title="将更换为另一个账号或工作区" description="后续新任务使用新账号；旧会话不能保证直接续接，需要时恢复原账号。" type="warning" :closable="false" show-icon /><ElCheckbox v-model="acknowledged" :disabled="busy">我已了解更换账号对旧会话的影响</ElCheckbox></template>
      <p v-else class="hx-muted">{{ current.status !== 'empty' ? '账号和工作区一致，更新后可返回原会话继续使用。已失败的操作不会自动重跑。' : '启用后，当前业务即可使用此账号进行 Codex 调用。' }}</p>
    </template>
    <template #footer><div class="auth-dialog-footer"><span class="hx-footnote" style="margin:0">确认启用前，当前配置保持不变</span><div class="auth-actions"><ElButton :disabled="busy" @click="close">取消</ElButton><ElButton v-if="step === 'starting' || step === 'checking'" type="primary" loading>{{ step === 'starting' ? '正在获取' : '正在检测' }}</ElButton><ElButton v-else-if="step === 'expired' || step === 'mismatch' || (step === 'waiting' && remaining === 0)" type="primary" :loading="busy" @click="restart">重新获取授权码</ElButton><ElButton v-else-if="step === 'failed' && authorization?.candidateEmail" type="primary" :loading="busy" @click="retry">重试检测</ElButton><ElButton v-else-if="step === 'verified'" type="primary" :loading="busy" :disabled="authorization?.different && !acknowledged" @click="activate">{{ authorization?.different ? '确认更换并启用' : '确认启用' }}</ElButton></div></div></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { businessNames, officialAuthorizationUrl, type Account, type Business, type CodexAuthApi, type Intent } from '../../api/codex-auth'
import { useAuthorization } from './use-authorization'
const props = defineProps<{ side: Business; intent: Intent; current: Account; api: CodexAuthApi }>()
const emit = defineEmits<{ close: []; activate: [account: Account, different: boolean]; failure: [reason: unknown] }>()
const { authorization, step, remaining, busy, polling, error, acknowledged, start, poll, retry, activate, close } = useAuthorization(props.api, props.intent, props.current.revision, {
  close: () => emit('close'), activate: (account, different) => emit('activate', account, different), failure: reason => emit('failure', reason)
})
const copied = ref(false)
const title = computed(() => props.intent === 'replace' ? '更换 Codex 账号' : props.intent === 'connect' ? '登录并授权' : '重新授权')
const officialUrl = computed(() => officialAuthorizationUrl(authorization.value?.verificationUrl || ''))
function openOfficial() { if (officialUrl.value) window.open(officialUrl.value, '_blank', 'noopener,noreferrer') }
async function copy() { try { await navigator.clipboard.writeText(authorization.value?.userCode || ''); copied.value = true } catch { ElMessage.info('复制失败，请手动选择上方授权码复制') } }
function restart() { copied.value = false; void start() }
</script>

