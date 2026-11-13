<template>
  <ElDialog v-model="open" title="归档到成品库" width="min(500px,94vw)" :close-on-click-modal="false" :before-close="beforeClose">
    <ElForm label-position="top" @submit.prevent="save"><ElFormItem label="产品名称" required :error="error"><ElInput v-model="name" aria-label="产品名称" maxlength="60" show-word-limit placeholder="输入产品名称" :disabled="saving || !!pending" @keyup.enter="save" /></ElFormItem></ElForm>
    <div class="archive-dialog-info"><p>来源：{{ conversation.name }}</p><p>保存当前会话的归档副本，归档后可以继续设计。</p><p v-if="pending">上次归档的结果尚未确认，将使用原请求核实。</p></div>
    <template #footer><ElButton :disabled="saving" @click="open = false">取消</ElButton><ElButton type="primary" :loading="saving" @click="save">{{ pending ? '核实并继续归档' : '保存归档' }}</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { randomUUID } from '@/utils/browser-crypto'
import { IdentityError } from '@/api/identity/request'
import { createDomesticArchivesApi } from '@/api/hengxin/domestic-archives'
import type { WorkspaceKey } from '@/api/hengxin/domestic-studio-skills'
import type { StudioConversation } from '@/api/shared/studio'
const props = defineProps<{ workspace: WorkspaceKey; conversation: StudioConversation; actor: string }>()
const open = defineModel<boolean>({ required: true })
const api = createDomesticArchivesApi(), name = ref(''), error = ref(''), saving = ref(false)
type Pending = { key: string; productName: string; conversationId: string }
const pending = ref<Pending>()
const storageKey = () => `hx-domestic-archive:${JSON.stringify([props.actor, props.workspace, props.conversation.id])}`
function stored() {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(storageKey()) || 'null')
    if (value && typeof value === 'object' && 'key' in value && 'productName' in value && 'conversationId' in value
      && typeof value.key === 'string' && typeof value.productName === 'string' && value.conversationId === props.conversation.id)
      return value as Pending
  } catch { /* Same-page state remains available if browser storage is unavailable. */ }
}
watch(open, value => { if (value) { pending.value = stored() || pending.value; name.value = pending.value?.productName || ''; error.value = '' } })
function beforeClose(done: () => void) { if (!saving.value) done() }
function clearPending() { pending.value = undefined; try { sessionStorage.removeItem(storageKey()) } catch { /* Same-page state was cleared. */ } }
async function save() {
  if (saving.value) return
  if (!name.value.trim() || name.value.trim().length > 60) { error.value = '请输入 1–60 个字的产品名称'; return }
  const request = pending.value || { key: randomUUID(), productName: name.value.trim(), conversationId: props.conversation.id }
  pending.value = request
  try { sessionStorage.setItem(storageKey(), JSON.stringify(request)) } catch { /* Keep the exact request for this page. */ }
  saving.value = true; error.value = ''
  try { await api.create(props.workspace, request.conversationId, request.productName, request.key); clearPending(); open.value = false; ElMessage.success('已归档，可在「成品库」查看') }
  catch (reason) {
    if (reason instanceof IdentityError && reason.status >= 400 && reason.status < 500 && reason.status !== 408) clearPending()
    error.value = reason instanceof IdentityError && typeof reason.detail === 'string' ? reason.detail : reason instanceof Error ? reason.message : '归档失败，请重试'
  } finally { saving.value = false }
}
</script>
<style scoped>.archive-dialog-info { font-size:13px; line-height:1.8; }.archive-dialog-info p { margin:8px 0; }</style>
