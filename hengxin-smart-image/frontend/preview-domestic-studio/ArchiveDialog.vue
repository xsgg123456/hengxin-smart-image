<template>
  <ElDialog v-model="open" title="归档到成品库" width="min(500px,94vw)" :close-on-click-modal="false" :before-close="beforeClose">
    <ElForm label-position="top" @submit.prevent="save">
      <ElFormItem label="产品名称" required :error="error"><ElInput v-model="name" aria-label="产品名称" maxlength="60" show-word-limit placeholder="输入产品名称" :disabled="saving" @keyup.enter="save" /></ElFormItem>
    </ElForm>
    <div class="archive-dialog-info"><p>来源：{{ config.title }} / {{ conversation.name }}</p><p>保存当前会话的归档副本，归档后可以继续设计。</p><p class="archive-preview-note">本地预览仅保存演示对话和已发送附件，暂无真实成品图片；刷新页面后清空。</p></div>
    <template #footer><ElButton :disabled="saving" @click="open = false">取消</ElButton><ElButton type="primary" :loading="saving" @click="save">保存归档</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { archiveConversation } from './archives'
import type { Conversation } from './state'
import type { WorkspaceConfig } from './workspaces'
const props = defineProps<{ config: WorkspaceConfig; conversation: Conversation }>()
const open = defineModel<boolean>({ required: true })
const name = ref(''), error = ref(''), saving = ref(false)
watch(name, () => { error.value = '' })
watch(open, value => { if (value) { name.value = ''; error.value = '' } })
function beforeClose(done: () => void) { if (!saving.value) done() }
async function save() {
  if (saving.value) return
  if (!name.value.trim() || name.value.trim().length > 60) { error.value = '请输入 1–60 个字的产品名称'; return }
  saving.value = true; error.value = ''
  try { await archiveConversation(props.config, props.conversation, name.value); open.value = false; ElMessage.success('已归档，可在「成品库」查看') }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '归档失败，请重试' }
  finally { saving.value = false }
}
</script>
