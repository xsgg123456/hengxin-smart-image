<template>
  <ElCard class="art-card hx-section hx-gap plans-panel" shadow="never">
    <div class="hx-section-title"><h2>确认图片排版方案</h2><ElButton :loading="loading" :disabled="saving" @click="load()">刷新方案</ElButton></div>
    <p v-if="loading && !loaded" role="status">正在加载方案…</p>
    <ElAlert v-if="error" class="hx-gap" :title="error" type="warning" :closable="false" />
    <template v-if="loaded">
      <p v-if="!plans.length" class="hx-muted">暂无图片排版方案。</p>
      <ElSelect v-if="plans.length" v-model="selectedId" aria-label="方案版本" class="hx-gap" :disabled="saving || !!pending">
        <ElOption v-for="plan in plans" :key="plan.id" :value="plan.id" :label="`方案 v${plan.version} · ${planStatuses[plan.status]}${plan.id === latest?.id ? '（最新）' : '（历史只读）'}`" />
      </ElSelect>
      <template v-if="selected">
        <p class="hx-footnote">{{ selected.createdAt }} · {{ planStatuses[selected.status] }}</p>
        <ElAlert v-if="selected.feedback" title="本轮方案修改意见" :description="selected.feedback" type="info" :closable="false" />
        <ElAlert v-if="selected.status === 'uncertain'" title="分析结果尚未确认，请联系管理员核实，切勿重复提交。" type="warning" :closable="false" />
        <p v-if="selected.status === 'pending'" role="status">分析任务已提交，正在等待执行结果。排队与执行状态见下方执行记录。</p>
        <p v-if="['failed', 'cancelled'].includes(selected.status)" role="alert">本轮分析未完成，可核对资料与执行记录后重试。</p>
        <template v-if="selected.content">
          <ElTabs v-model="sku"><ElTabPane v-for="s in selected.content.skus" :key="s.code" :label="s.code" :name="s.code" /></ElTabs>
          <article v-for="(picture, i) in pictures" :key="i" class="plan-row">
            <span class="hx-number">{{ i + 1 }}</span><div><h3>{{ picture.title }}</h3><p>{{ picture.description }}</p><p>图片尺寸：{{ picture.width }} × {{ picture.height }} px</p><ElCollapse><ElCollapseItem title="完整生图提示词" :name="i"><p>{{ picture.prompt }}</p></ElCollapseItem></ElCollapse></div>
          </article>
          <p class="hx-footnote">当前 SKU {{ pictures.length }} 张；确认对方案内全部 {{ selected.content.skus.length }} 个 SKU 生效。</p>
        </template>
        <p v-if="selected.id !== latest?.id" class="hx-footnote">历史方案仅供查看，请切换最新版本处理。</p>
      </template>
      <template v-if="actionable">
        <ElInput v-model="feedback" aria-label="方案修改意见" type="textarea" :rows="3" maxlength="10000" :disabled="saving || !!pending" placeholder="不通过时请填写方案修改意见" />
        <div class="actions hx-gap">
          <ElButton v-if="canAnalyze" :loading="saving" :disabled="loading || !!pending || (latest?.status === 'ready' && !feedback.trim())" @click="submit('analysis')">{{ latest?.status === 'ready' ? '不通过，重新分析' : latest ? '重试分析' : '开始分析' }}</ElButton>
          <ElButton v-if="canConfirm" type="primary" :loading="saving" :disabled="loading || !!pending" @click="submit('confirm')">确认方案，开始生图</ElButton>
        </div>
      </template>
      <ElButton v-if="pending" class="hx-gap" :loading="saving" :disabled="!allowed" @click="send">核实并重试原请求</ElButton>
      <p v-if="!allowed" class="hx-footnote">当前为只读视角，方案处理需由负责设计或设计主管操作。</p>
    </template>
  </ElCard>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { createPlansApi, planStatuses, type Plan } from '@/api/overseas/plans'
import { createRequestKeys, taskError, type TaskDetail } from '@/api/overseas/tasks'
const props = defineProps<{ task: TaskDetail; refresh: number }>()
const emit = defineEmits<{ failure: [reason: unknown]; changed: [task: TaskDetail]; refresh: [] }>()
const api = createPlansApi(), keys = createRequestKeys(), plans = ref<Plan[]>([]), selectedId = ref(''), sku = ref(''), feedback = ref(''), error = ref('')
const loading = ref(false), loaded = ref(false), saving = ref(false), taskVersion = ref(0)
const pending = ref<{ kind: 'analysis' | 'confirm'; taskId: string; planId: string; version: number; feedback: string; key: string }>()
let epoch = 0, alive = true
const latest = computed(() => plans.value[0]), selected = computed(() => plans.value.find(p => p.id === selectedId.value))
const pictures = computed(() => selected.value?.content?.skus.find(s => s.code === sku.value)?.pictures || [])
const allowed = computed(() => props.task.capabilities.includes('task.design'))
const current = computed(() => !selected.value || selected.value.id === latest.value?.id)
const canAnalyze = computed(() => ['submitted', 'analysisFailed', 'plan'].includes(props.task.status) && (!latest.value || ['ready', 'failed', 'cancelled'].includes(latest.value.status)))
const canConfirm = computed(() => props.task.status === 'plan' && latest.value?.status === 'ready')
const actionable = computed(() => allowed.value && current.value && loaded.value && (canAnalyze.value || canConfirm.value))
function fail(reason: unknown) {
  error.value = taskError(reason)
  if (reason instanceof IdentityError && [401, 403, 404].includes(reason.status)) { ++epoch; plans.value = []; loaded.value = false; feedback.value = ''; pending.value = undefined; emit('failure', reason) }
}
async function load(preserveError = false) {
  const id = props.task.id, request = ++epoch; loading.value = true; if (!preserveError) error.value = ''
  try {
    const value = await api.list(id)
    if (!alive || request !== epoch) return
    const wasLatest = !selectedId.value || selectedId.value === latest.value?.id
    plans.value = value.items; taskVersion.value = value.taskVersion; loaded.value = true
    if (wasLatest || !plans.value.some(p => p.id === selectedId.value)) selectedId.value = latest.value?.id || ''
  } catch (reason) { if (alive && request === epoch) { loaded.value = false; plans.value = []; fail(reason) } }
  finally { if (request === epoch) loading.value = false }
}
function submit(kind: 'analysis' | 'confirm') {
  if (!actionable.value || loading.value || saving.value || pending.value || (kind === 'analysis' && (!canAnalyze.value || (latest.value?.status === 'ready' && !feedback.value.trim()))) || (kind === 'confirm' && !canConfirm.value)) return
  const body = { kind, taskId: props.task.id, planId: latest.value?.id || '', version: taskVersion.value, feedback: feedback.value.trim() }
  pending.value = { ...body, key: keys.for(body) }; void send()
}
async function send() {
  const request = pending.value, currentEpoch = epoch
  if (!request || saving.value || !allowed.value) return
  saving.value = true; error.value = ''
  try {
    const value = request.kind === 'analysis' ? await api.analyze(request.taskId, request.version, request.feedback, request.key) : await api.confirm(request.taskId, request.planId, request.version, request.key)
    if (!alive || currentEpoch !== epoch) return
    pending.value = undefined; keys.clear(); feedback.value = ''; emit('changed', value); await load()
  } catch (reason) {
    if (!alive || currentEpoch !== epoch) return
    if (reason instanceof IdentityError && reason.status > 0 && reason.status < 500) {
      pending.value = undefined
      if (reason.status === 409) { await load(); emit('refresh') }
      fail(reason)
    } else error.value = '请求结果尚未确认，请核实并重试原请求；意见已保留。'
  } finally { saving.value = false }
}
watch(() => props.task.id, () => { ++epoch; plans.value = []; loaded.value = false; selectedId.value = ''; feedback.value = ''; pending.value = undefined; keys.clear(); void load() }, { immediate: true })
watch([() => props.task.version, () => props.refresh], () => { if (!saving.value) void load(true) })
watch(allowed, value => { if (!value) { ++epoch; pending.value = undefined; feedback.value = ''; keys.clear(); void load() } })
watch(selected, value => { if (!value?.content?.skus.some(s => s.code === sku.value)) sku.value = value?.content?.skus[0]?.code || '' })
onUnmounted(() => { alive = false; ++epoch; plans.value = []; feedback.value = ''; pending.value = undefined })
</script>
<style scoped>
.plans-panel { min-width: 0; overflow-wrap: anywhere; }
.hx-section-title, .actions { display: flex; flex-wrap: wrap; gap: 8px; }
.actions { justify-content: flex-end; }
.plan-row { display: flex; align-items: flex-start; gap: 14px; border-bottom: 1px solid var(--el-border-color-lighter); padding: 18px 0; }
.plan-row > div { min-width: 0; flex: 1; }
.plan-row p { font-size: 13px; line-height: 1.8; white-space: pre-wrap; overflow-wrap: anywhere; }
h2 { font-size: 16px; } h3 { font-size: 14px; }
</style>
