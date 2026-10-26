<template>
  <ElDialog :model-value="true" :title="title" class="auth-dialog" width="min(640px, calc(100vw - 32px))" align-center :close-on-click-modal="false" @close="$emit('close')">
    <ElAlert :title="businessNames[side] + ' · ' + (intent === 'replace' ? '更换账号前，当前配置继续保留' : currentEmail ? '请使用原账号和原工作区完成授权' : '请登录要用于当前业务的账号')" :description="currentEmail ? '当前账号：' + currentEmail + ' · 个人工作区' : '授权通过后，还需要确认启用。'" type="info" :closable="false" show-icon />
    <template v-if="step === 'waiting' || step === 'expired'">
      <h3>1. 打开官方授权页，输入授权码</h3>
      <p class="hx-muted">auth.openai.com/codex/device</p>
      <div class="auth-code"><div><strong>{{ step === 'expired' ? '已过期' : 'DEMO-ONLY' }}</strong><br><small>示例授权码 · 不能用于真实登录</small></div><ElButton :disabled="step === 'expired'" @click="copy">{{ copied ? '已复制' : '复制授权码' }}</ElButton></div>
      <ElButton type="primary" plain :disabled="step === 'expired'" @click="guide = !guide">{{ guide ? '收起授权说明' : '前往官方授权（演示）' }}</ElButton>
      <p v-if="guide" class="hx-muted hx-gap">正式使用时将在新窗口打开 OpenAI 官方登录页，输入上方授权码并确认授权后，返回此处。本预览不打开真实登录页，请使用下方按钮演示授权完成。</p>
      <h3>2. 完成登录后，系统检测新授权</h3>
      <p v-if="step === 'waiting'" class="hx-muted" role="status">等待授权完成 · 剩余 {{ remaining }} 秒</p>
      <ElAlert v-else title="本次授权码已过期，当前账号配置未改变" description="重新获取授权码后再试。" type="warning" :closable="false" show-icon />
      <div class="auth-demo-controls" v-if="step === 'waiting'"><label for="auth-outcome">以下仅用于交互演示 · 模拟授权结果</label><ElSelect id="auth-outcome" v-model="outcome" aria-label="模拟授权结果"><ElOption value="same" :label="currentEmail ? '原账号授权成功' : '新账号授权成功'" /><ElOption value="different" label="登录了另一个账号" /><ElOption value="timeout" label="授权码过期" /><ElOption value="network" label="检测连接失败" /></ElSelect></div>
    </template>
    <div v-else-if="step === 'checking'" class="auth-checking" role="status"><h3>正在检测新授权…</h3><p class="hx-muted">核对账号、工作区与连接状态，当前配置暂不变更。</p><ElSkeleton :rows="2" animated /></div>
    <template v-else-if="step === 'failed'">
      <ElAlert title="暂时无法检测新授权" description="连接异常，尚未启用新授权。原账号配置仍保留，可重试检测或取消。" type="warning" :closable="false" show-icon />
      <div class="auth-demo-controls"><ElCheckbox v-model="networkRecovered">演示网络已恢复</ElCheckbox></div>
    </template>
    <template v-else-if="step === 'mismatch'">
      <ElAlert title="登录账号与原账号不一致，暂不启用" description="恢复原会话请使用原账号重新登录。如需更换账号，请取消后使用“更换账号”入口。" type="warning" :closable="false" show-icon />
      <dl class="auth-details"><div><dt>原账号</dt><dd>{{ currentEmail }}</dd></div><div><dt>本次登录</dt><dd>{{ candidate }}</dd></div></dl>
    </template>
    <template v-else>
      <ElAlert title="新授权检测通过，等待确认启用" description="确认后仅更新当前业务的账号配置。" type="success" :closable="false" show-icon />
      <dl class="auth-details"><div><dt>本次授权账号</dt><dd>{{ candidate }}</dd></div><div><dt>工作区</dt><dd>个人工作区</dd></div><div><dt>连接检测</dt><dd>通过</dd></div><div><dt>生效范围</dt><dd>{{ businessNames[side] }}</dd></div></dl>
      <template v-if="isDifferent"><ElAlert title="将更换为另一个账号" description="后续新任务使用新账号；旧会话不能保证直接续接，需要时恢复原账号。" type="warning" :closable="false" show-icon /><ElCheckbox v-model="acknowledged">我已了解更换账号对旧会话的影响</ElCheckbox></template>
      <p v-else class="hx-muted">{{ currentEmail ? '账号和工作区一致，更新后可返回原会话继续使用。已失败的操作不会自动重跑。' : '启用后，当前业务即可使用此账号进行 Codex 调用。' }}</p>
    </template>
    <template #footer><div class="auth-dialog-footer"><span class="hx-footnote" style="margin:0">仅为交互演示，不提交真实授权</span><div class="auth-actions"><ElButton @click="$emit('close')">取消</ElButton><ElButton v-if="step === 'waiting'" type="primary" @click="simulate">模拟已完成授权</ElButton><ElButton v-else-if="step === 'checking'" type="primary" loading>正在检测</ElButton><ElButton v-else-if="step === 'expired' || step === 'mismatch'" type="primary" @click="restart">重新获取授权码</ElButton><ElButton v-else-if="step === 'failed'" type="primary" @click="retry">重试检测</ElButton><ElButton v-else type="primary" :disabled="isDifferent && !acknowledged" @click="$emit('activate', candidate)">{{ isDifferent ? '确认更换并启用' : '确认启用' }}</ElButton></div></div></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { businessNames, sampleEmails, type Business } from './model'
const props = defineProps<{ side: Business; intent: 'renew' | 'replace' | 'connect'; currentEmail: string }>()
defineEmits<{close: []; activate: [email: string]}>()
type Step = 'waiting' | 'checking' | 'expired' | 'failed' | 'mismatch' | 'verified'
const step = ref<Step>('waiting'), outcome = ref('same'), remaining = ref(180), guide = ref(false), copied = ref(false)
const candidate = ref(''), acknowledged = ref(false), networkRecovered = ref(false)
const title = computed(() => props.intent === 'replace' ? '更换 Codex 账号' : props.intent === 'connect' ? '登录并授权' : '重新授权')
const isDifferent = computed(() => !!props.currentEmail && candidate.value !== props.currentEmail)
let timeout: ReturnType<typeof setTimeout> | undefined
const clock = setInterval(() => { if (step.value === 'waiting' && --remaining.value <= 0) step.value = 'expired' }, 1000)
function restart() { step.value = 'waiting'; remaining.value = 180; outcome.value = 'same'; copied.value = false; acknowledged.value = false; networkRecovered.value = false }
async function copy() { try { await navigator.clipboard.writeText('DEMO-ONLY'); copied.value = true } catch { ElMessage.info('请手动复制示例码 DEMO-ONLY') } }
function inspect(fail: boolean) {
  step.value = 'checking'
  timeout = setTimeout(() => {
    step.value = fail ? 'failed' : isDifferent.value && props.intent !== 'replace' ? 'mismatch' : 'verified'
  }, 900)
}
function simulate() {
  if (outcome.value === 'timeout') { step.value = 'expired'; return }
  candidate.value = outcome.value === 'different' ? 'new-account@example.com' : props.currentEmail || sampleEmails[props.side]
  inspect(outcome.value === 'network')
}
function retry() { inspect(!networkRecovered.value) }
onBeforeUnmount(() => { clearInterval(clock); if (timeout) clearTimeout(timeout) })
</script>
