<template>
  <ElCard class="art-card hx-section hx-admin-settings-card">
    <div class="hx-admin-section-head"><div><span class="hx-admin-kicker">SYSTEM SETTINGS</span><h2>海外业务配置</h2><p>暂停和并发影响后续领取；超时和默认 Skill 仅影响新作业，在途作业保持原快照。</p></div><ElButton :loading="loading" :disabled="saving" @click="load(true)">刷新配置</ElButton></div>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" class="hx-gap" />
    <ElForm v-if="form" label-position="top" :disabled="loading || saving" @submit.prevent="save">
      <ElFormItem label="暂停接纳执行"><ElSwitch v-model="form.paused" aria-label="暂停接纳执行" /></ElFormItem>
      <ElFormItem label="任务并发上限（1–5）"><ElInputNumber v-model="form.concurrency" aria-label="任务并发上限" :min="1" :max="5" :precision="0" /></ElFormItem>
      <ElFormItem label="新作业执行时限（秒，10–7200）"><ElInputNumber v-model="form.timeoutSeconds" aria-label="执行时限" :min="10" :max="7200" :precision="0" /></ElFormItem>
      <ElFormItem v-for="(label,stage) in stages" :key="stage" :label="label + '默认 Skill'"><ElSelect v-model="form.defaults[stage]" :aria-label="label + '默认 Skill'"><ElOption :value="BUILTIN_SKILL" label="内置协议 Skill" /><ElOption v-for="skill in skills" :key="skill.id" :value="skill.id" :label="skill.displayName" /><ElOption v-if="missing(stage)" :value="form.defaults[stage] || ''" label="当前绑定不可用，请重新选择" disabled /></ElSelect></ElFormItem>
      <ElFormItem label="自动清理"><ElTag type="info">关闭（只读）</ElTag></ElFormItem>
      <div class="hx-admin-toolbar-actions hx-gap"><ElButton :disabled="!saved" @click="restore">重置未保存修改</ElButton><ElButton type="primary" :loading="saving" :disabled="blocked" @click="save">保存配置</ElButton></div>
      <p class="hx-footnote" role="status">{{ dirty ? '有未保存修改' : '当前配置已保存' }} · 版本 {{ form.version }}</p>
    </ElForm>
    <ElEmpty v-else-if="!loading" description="配置暂不可用，请刷新重试" />
  </ElCard>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { IdentityError } from '@/api/identity/auth'
import { stages, managementError, type Stage, type ManagementApi, type Settings, type Skill } from '@/api/overseas/management'
const props = defineProps<{api: ManagementApi}>()
const emit = defineEmits<{failure: [reason: unknown]}>()
const BUILTIN_SKILL = '__builtin__'
type SettingsForm = Omit<Settings, 'defaults'> & { defaults: Record<Stage, string> }
const form = ref<SettingsForm>(), saved = ref<SettingsForm>(), skills = ref<Skill[]>([]), loading = ref(false), saving = ref(false), blocked = ref(false), error = ref('')
let active = true
const copy = (v: Settings | SettingsForm): SettingsForm => ({ ...v, defaults: { analysis: v.defaults.analysis ?? BUILTIN_SKILL, generation: v.defaults.generation ?? BUILTIN_SKILL, revision: v.defaults.revision ?? BUILTIN_SKILL } })
const toSettings = (v: SettingsForm): Settings => ({ ...v, defaults: { analysis: v.defaults.analysis === BUILTIN_SKILL ? null : v.defaults.analysis, generation: v.defaults.generation === BUILTIN_SKILL ? null : v.defaults.generation, revision: v.defaults.revision === BUILTIN_SKILL ? null : v.defaults.revision } })
const dirty = computed(() => JSON.stringify(form.value) !== JSON.stringify(saved.value))
const missing = (stage: Stage) => !!form.value?.defaults[stage] && form.value.defaults[stage] !== BUILTIN_SKILL && !skills.value.some(s => s.id === form.value?.defaults[stage])
function restore() { if (saved.value) form.value = copy(saved.value); error.value = ''; blocked.value = false }
function failure(reason: unknown) { if (reason instanceof IdentityError && [401,403].includes(reason.status)) { form.value = undefined; saved.value = undefined; skills.value = []; emit('failure',reason) } }
async function load(preserve = false) {
  if (loading.value) return
  loading.value = true
  try {
    const [value, list] = await Promise.all([props.api.settings(),props.api.skills()])
    if (!active) return
    saved.value = copy(value); skills.value = list.items
    if (!preserve || !form.value) form.value = copy(value)
    else form.value.version = value.version
    blocked.value = false
    if (preserve) error.value = '已刷新最新版本，草稿保留；请核对后再保存'
  } catch (reason) { if (active) { blocked.value = true; error.value = managementError(reason); failure(reason) } }
  finally { if (active) loading.value = false }
}
async function save() {
  if (!form.value || saving.value || blocked.value || loading.value) return
  const draft = toSettings(form.value)
  if (!Number.isInteger(draft.concurrency) || draft.concurrency < 1 || draft.concurrency > 5 || !Number.isInteger(draft.timeoutSeconds) || draft.timeoutSeconds < 10 || draft.timeoutSeconds > 7200 || (Object.keys(stages) as Stage[]).some(missing)) { error.value = '请检查并发、执行时限和默认 Skill'; return }
  saving.value = true; error.value = ''
  try { const result = await props.api.saveSettings(draft); if (active) { saved.value = copy(result); form.value = copy(result); ElMessage.success('配置已保存') } }
  catch (reason) {
    if (!active) return
    error.value = managementError(reason); failure(reason)
    if (reason instanceof IdentityError && (reason.status === 409 || reason.status === 0 || reason.status >= 500)) { blocked.value = true; await load(true); if (active && form.value) error.value = reason.status === 409 ? '配置已变化，已刷新版本并保留草稿；请核对后保存' : '写入结果未知，已刷新服务端配置；请核对草稿与最新配置后再保存' }
  } finally { if (active) saving.value = false }
}
onMounted(() => load())
onUnmounted(() => { active = false; form.value = undefined; saved.value = undefined; skills.value = [] })
</script>
