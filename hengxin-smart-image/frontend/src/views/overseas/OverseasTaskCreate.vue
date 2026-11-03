<template>
  <div class="draft-status" aria-live="polite"><span>{{ status }}</span><ElButton v-if="state.error && !state.conflict" link type="primary" :disabled="state.saving" @click="retrySave">重试保存</ElButton><ElButton type="danger" text :disabled="locked || state.saving || uploadBusy || source.querying.value" @click="clearDraft">清空草稿</ElButton></div>
  <ElAlert v-if="state.localError" :title="state.localError" type="warning" :closable="false" />
  <ElAlert v-if="state.error" :title="state.error" type="error" :closable="false" />
  <div v-if="state.conflict" class="conflict-actions"><p>本地内容已保留，选择恢复方式前不会写入服务器。</p><ElButton :disabled="state.loading" @click="resolve(false)">使用服务器草稿</ElButton><ElButton type="primary" :disabled="state.loading" @click="resolve(true)">用本地字段恢复</ElButton></div>
  <ElAlert v-if="interrupted.length" type="warning" :closable="false" :title="`上次上传尚未确认完成，请核对已保存附件，缺失文件需要重新选择：${interrupted.join('、')}`" />
  <ElAlert v-if="state.submission" title="上次提交结果尚未确认，字段已保留。请重试提交以确认原任务，不会重复创建。" type="warning" :closable="false" />
  <OverseasCreate v-model="draft" :allowed="allowed" :busy="locked" @back="$emit('back')">
    <template #sku>
      <div class="sku-section-title"><h2>商品 SKU</h2></div>
      <ElFormItem label="商品 SKU" required><div class="sku-lookup-row"><ElInput v-model="draft.skus[0].code" aria-label="商品 SKU" maxlength="80" placeholder="输入 SKU，获取对应需求" :disabled="source.applying.value || uploadBusy" @keyup.enter="query" /><ElButton type="primary" plain :loading="source.querying.value || source.applying.value" :disabled="locked || uploadBusy || !draft.skus[0].code.trim()" @click="query">{{ source.querying.value ? '正在查询' : source.applying.value ? '正在导入' : '获取需求' }}</ElButton></div></ElFormItem>
      <div v-if="source.notice.value" class="lookup-notice" aria-live="polite"><ElAlert :title="source.notice.value" :type="source.noticeType.value" :closable="false" show-icon /><ul v-if="source.warnings.value.length"><li v-for="warning in source.warnings.value" :key="warning">{{ warning }}</li></ul></div>
      <ElAlert v-if="source.sourceMismatch.value" class="lookup-notice" title="当前资料来自其他 SKU，提交前请重新获取需求，或清空草稿后手动填写。" type="warning" :closable="false" show-icon />
    </template>
    <template #designer><ElFormItem label="负责设计" required><DesignerPicker v-model="draft.designerId" :api="api" :selected="source.designer.value || state.server?.matchedDesigner" :disabled="locked" @failure="$emit('failure', $event)" /></ElFormItem></template>
    <template #after>
      <DraftMaterialsPanel v-if="state.server && state.initialized" :key="state.server.id" :draft="state.server" :api="materialsApi" :disabled="locked || source.querying.value || source.confirming.value" :change="changeAttachment" :refresh="controller.refresh" @busy="uploadBusy = $event" @pending="controller.uploads" @failure="$emit('failure', $event)" />
      <ElAlert v-if="error" :title="error" type="error" :closable="false" />
      <div class="draft-submit"><ElButton type="primary" :loading="submitting" :disabled="!canSubmit" @click="submit">{{ state.submission ? '重试提交并确认结果' : '提交图需' }}</ElButton><span v-if="failedImports" class="submit-hint">请先重试或移除导入失败的附件。</span><span v-else-if="importing" class="hx-muted">附件正在后台导入，完成后可提交。</span></div>
    </template>
  </OverseasCreate>
  <RequirementPicker v-model="source.choosing.value" v-model:selected="source.selected.value" :items="source.matches.value" :sku="draft.skus[0].code" :busy="source.applying.value" @confirm="source.apply" />
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import { IdentityError } from '@/api/identity/request'
import { cleanDraft, emptyTaskDraft, taskError, validateNewDraft, type TasksApi } from '@/api/overseas/tasks'
import { readyMaterialIds, type MaterialsApi } from '@/api/overseas/materials'
import { createDraftsApi, type DraftsApi, type DraftFields } from '@/api/overseas/requirement-drafts'
import { browserDraftStorage, sameFields, type DraftStorage } from './requirement-draft-storage'
import { createDraftController } from './requirement-draft-controller'
import { useRequirementSource } from './use-requirement-source'
import OverseasCreate from './OverseasCreate.vue'
import DesignerPicker from './DesignerPicker.vue'
import DraftMaterialsPanel from './DraftMaterialsPanel.vue'
import RequirementPicker from './RequirementPicker.vue'
const props = defineProps<{ actorId: string; api: TasksApi; materialsApi: MaterialsApi; allowed: boolean; draftsApi?: DraftsApi }>()
const emit = defineEmits<{ back: []; created: [id: string]; failure: [reason: unknown] }>()
const draftsApi = props.draftsApi || createDraftsApi()
let storage: DraftStorage
try { storage = browserDraftStorage(props.actorId) } catch { storage = { read: () => { throw Error('本地存储不可用') }, write: () => { throw Error('本地存储不可用') }, clear: () => {} } }
const controller = createDraftController(draftsApi, storage, reason => emit('failure', reason)), state = controller.state
const draft = ref<DraftFields>(emptyTaskDraft()), submitting = ref(false), clearing = ref(false), uploadBusy = ref(false), error = ref(''), interrupted = ref<string[]>([])
const source = useRequirementSource(draft, controller, draftsApi, reason => emit('failure', reason), () => uploadBusy.value)
let synchronizing = false, active = true
watch(() => state.fields, value => { if (!sameFields(value, draft.value)) { synchronizing = true; draft.value = JSON.parse(JSON.stringify(value)); synchronizing = false } }, { deep: true, flush: 'sync' })
watch(draft, value => { if (!synchronizing) controller.edit(value) }, { deep: true, flush: 'sync' })
const locked = computed(() => !props.allowed || !state.initialized || state.loading || state.conflict || submitting.value || clearing.value || !!state.submission || source.applying.value || source.confirming.value)
const importing = computed(() => state.server?.imports.some(i => ['queued', 'running'].includes(i.state)))
const failedImports = computed(() => state.server?.imports.some(i => i.state === 'failed'))
const status = computed(() => state.loading ? '正在恢复个人草稿…' : state.conflict ? '草稿版本冲突' : state.error ? '草稿保存失败' : state.saving || state.dirty ? '正在保存草稿…' : state.initialized ? '草稿已保存' : '草稿未恢复')
const canSubmit = computed(() => {
  if (!props.allowed || !state.initialized || state.loading || state.conflict || submitting.value || uploadBusy.value || source.querying.value || source.applying.value || source.confirming.value) return false
  if (state.submission) return true
  if (importing.value || failedImports.value || source.sourceMismatch.value) return false
  try { validateNewDraft(draft.value); readyMaterialIds(state.server?.materials || []); return true } catch { return false }
})
function query() { if (!locked.value && !uploadBusy.value) void source.query() }
async function retrySave() { try { if (!state.initialized) await controller.initialize(); else await controller.flush() } catch { /* 状态含明确失败 */ } }
async function resolve(local: boolean) {
  try {
    await ElMessageBox.confirm(local ? '将当前本地字段恢复到最新服务器版本；服务器附件保持。确认前请核对当前表单内容。' : '将使用服务器草稿替换当前页面字段。', '选择草稿恢复方式', { type: 'warning', confirmButtonText: '确认恢复', cancelButtonText: '取消' })
    await controller.resolve(local)
  } catch (reason) { if (reason !== 'cancel' && reason !== 'close') error.value = taskError(reason) }
}
async function changeAttachment(operation: 'retry' | 'cancel' | 'remove', id: string) {
  return controller.mutate(() => operation === 'retry' ? draftsApi.retry(id) : operation === 'cancel' ? draftsApi.cancel(id) : draftsApi.removeMaterial(id))
}
async function clearDraft() {
  if (locked.value || uploadBusy.value || source.querying.value) return
  try {
    await ElMessageBox.confirm('清空全部已填信息和附件，并取消后台导入？此操作只影响你的新建草稿。', '清空草稿', { type: 'warning', confirmButtonText: '确认清空', cancelButtonText: '取消' })
    clearing.value = true
    await controller.mutate(server => draftsApi.clear(server.version), true)
    interrupted.value = []; controller.uploads([]); source.notice.value = ''; source.warnings.value = []; source.designer.value = null
  } catch (reason) { if (reason !== 'cancel' && reason !== 'close') error.value = taskError(reason) }
  finally { clearing.value = false }
}
async function submit() {
  if (!canSubmit.value) return
  submitting.value = true; error.value = ''
  try {
    if (!state.submission) {
      validateNewDraft(draft.value); await controller.flush()
      const server = state.server!
      if (server.source && server.source.sku !== draft.value.skus[0].code.trim()) throw Error('SKU 与附件来源不一致，请重新获取需求')
      if (server.imports.some(i => !['ready', 'cancelled'].includes(i.state))) throw Error('请等待附件导入完成，或处理失败附件')
      const body = cleanDraft({ ...draft.value, materialIds: readyMaterialIds(server.materials), draftId: server.id, draftVersion: server.version })
      controller.submission(body, server.submitKey)
    }
    const pending = state.submission!, result = await props.api.create(pending.body, pending.key)
    if (!active) return
    controller.completed(); emit('created', result.id)
  } catch (reason) {
    if (!active) return
    error.value = taskError(reason)
    // Network errors have unknown outcomes; preserve the exact request and key.
    if (reason instanceof IdentityError && reason.status >= 400 && reason.status < 500) { controller.clearSubmission(); if (reason.status === 409) await controller.refresh(); if ([401,403].includes(reason.status)) emit('failure', reason) }
  } finally { if (active) submitting.value = false }
}
void controller.initialize().then(() => { if (!active) return; interrupted.value = [...state.pendingUploads]; if (state.recoveredTaskId) emit('created', state.recoveredTaskId) })
const poll = setInterval(() => { if (!locked.value && !state.saving) void controller.refresh() }, 2000)
onUnmounted(() => { active = false; clearInterval(poll); controller.dispose() })
</script>
<style scoped>
.draft-status,.conflict-actions,.draft-submit{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:16px;font-size:13px}.draft-status{color:var(--el-text-color-secondary)}.conflict-actions{padding:12px}.sku-section-title{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}.sku-section-title h2{font-size:16px;font-weight:600}.sku-lookup-row{display:flex;gap:12px;width:100%;align-items:center}.sku-lookup-row .el-input{min-width:0}.sku-lookup-row .el-button{flex-shrink:0}.lookup-notice{margin-bottom:20px}.lookup-notice ul{padding:10px 16px 0;color:var(--el-color-warning-dark-2);font-size:13px;line-height:1.9}.lookup-notice :deep(.el-alert__title){line-height:1.7;overflow-wrap:anywhere}.submit-hint{color:var(--el-color-danger);font-size:13px}
@media(max-width:800px){.sku-lookup-row{align-items:stretch;flex-wrap:wrap}.sku-lookup-row .el-input{flex-basis:100%}.sku-lookup-row .el-button{margin-left:0}}
</style>
