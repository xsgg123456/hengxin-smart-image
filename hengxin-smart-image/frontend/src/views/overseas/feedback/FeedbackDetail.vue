<template>
  <ElDrawer :model-value="true" title="反馈详情" size="min(500px, 100vw)" append-to-body :close-on-click-modal="!saving"
    :close-on-press-escape="!saving" :show-close="!saving" @close="emit('close')">
    <ElAlert v-if="problem" type="error" :closable="false" :title="problem" />
    <div v-loading="loading" class="feedback-details">
      <template v-if="record">
        <div class="feedback-metadata"><span>{{ record.submitter_name }}</span><span>{{ formatBeijingTime(record.created_at) }}</span></div>
        <p class="feedback-source">反馈页面 · {{ feedbackSourceText(record.source, record.task_name, record.sku) }}</p>
        <h3 class="feedback-heading">问题描述</h3><p class="feedback-description">{{ record.question }}</p>
        <template v-if="record.screenshot_url">
          <h3 class="feedback-heading">问题截图</h3>
          <ElImage v-if="imageUrl" class="feedback-picture" :src="imageUrl" fit="contain" :preview-src-list="[imageUrl]" preview-teleported alt="用户提交的问题截图" />
          <ElButton v-else-if="imageError" link type="primary" @click="loadImage">截图读取失败，点击重试</ElButton>
          <span v-else class="feedback-source">正在加载截图…</span>
        </template>
        <ElDivider />
        <ElForm label-position="top" :disabled="saving || conflict || loading">
          <ElFormItem label="处理状态"><ElRadioGroup v-model="status" aria-label="处理状态">
            <ElRadioButton v-for="(label, key) in feedbackStatuses" :key="key" :value="key">{{ label }}</ElRadioButton>
          </ElRadioGroup></ElFormItem>
          <ElFormItem label="回复提交人" :required="status === 'resolved'" :error="replyError">
            <ElInput v-model="reply" aria-label="回复提交人" type="textarea" :rows="3" maxlength="4000" show-word-limit
              placeholder="告诉提交人处理进展或解决方法" @input="replyError = ''" />
          </ElFormItem>
          <ElFormItem label="内部备注（仅管理员可见）">
            <ElInput v-model="note" aria-label="内部备注" type="textarea" :rows="2" maxlength="4000" placeholder="记录内部排查细节" />
          </ElFormItem>
        </ElForm>
        <small v-if="record.version > 1" class="feedback-source">最近处理于 {{ formatBeijingTime(record.updated_at) }}</small>
      </template>
    </div>
    <template #footer>
      <ElButton :disabled="saving" @click="emit('close')">关闭</ElButton>
      <ElButton v-if="conflict || !record" type="primary" :loading="loading" @click="load">刷新最新记录</ElButton>
      <ElButton v-else type="primary" :loading="saving" :disabled="loading" @click="save">保存处理</ElButton>
    </template>
  </ElDrawer>
</template>
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { IdentityError } from '@/api/identity/request'
import { feedbackAccessDenied, feedbackError, feedbackSourceText, feedbackStatuses, type FeedbackApi, type FeedbackStatus, type ManagedFeedback } from '@/api/overseas/feedback'
import { formatBeijingTime } from '@/utils/beijing-time'

const props = defineProps<{ api: FeedbackApi; id: string }>()
const emit = defineEmits<{ close: []; saved: []; failure: [reason: unknown] }>()
const record = ref<ManagedFeedback>(), status = ref<FeedbackStatus>('pending'), reply = ref(''), note = ref('')
const saving = ref(false), loading = ref(false), problem = ref(''), replyError = ref(''), conflict = ref(false)
const imageUrl = ref(''), imageError = ref(false)
let active = true, imageVersion = 0
function releaseImage() {
  ++imageVersion
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
  imageUrl.value = ''; imageError.value = false
}
async function loadImage() {
  releaseImage()
  const request = imageVersion
  try {
    const blob = await props.api.screenshot(props.id, true)
    if (active && request === imageVersion) imageUrl.value = URL.createObjectURL(blob)
  } catch (reason) {
    if (!active || request !== imageVersion) return
    imageError.value = true
    if (feedbackAccessDenied(reason)) emit('failure', reason)
  }
}
async function load() {
  if (loading.value || saving.value) return
  loading.value = true; problem.value = ''; replyError.value = ''
  try {
    const latest = await props.api.detail(props.id)
    if (!active) return
    record.value = latest; status.value = latest.status; reply.value = latest.public_reply; note.value = latest.internal_note
    conflict.value = false
    if (latest.screenshot_url && !imageUrl.value) void loadImage()
  } catch (reason) {
    if (!active) return
    problem.value = feedbackError(reason)
    if (feedbackAccessDenied(reason)) emit('failure', reason)
  } finally { if (active) loading.value = false }
}
async function save() {
  if (!record.value || saving.value || loading.value || conflict.value) return
  if (status.value === 'resolved' && !reply.value.trim()) { replyError.value = '请填写给提交人的处理结果'; return }
  saving.value = true; problem.value = ''; replyError.value = ''
  try {
    await props.api.save(props.id, { version: record.value.version, status: status.value, public_reply: reply.value.trim(), internal_note: note.value.trim() })
    if (active) { ElMessage.success('处理记录已保存'); emit('saved') }
  } catch (reason) {
    if (!active) return
    conflict.value = reason instanceof IdentityError && reason.status === 409
    problem.value = feedbackError(reason)
    if (feedbackAccessDenied(reason)) emit('failure', reason)
  } finally { if (active) saving.value = false }
}
onMounted(load)
onBeforeUnmount(() => { active = false; releaseImage() })
</script>
<style scoped>
.feedback-details { min-height: 64px; }
.feedback-metadata { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; font-size: 13px; color: var(--el-text-color-regular); }
.feedback-source { color: var(--el-text-color-secondary); font-size: 13px; margin-top: 8px; overflow-wrap: anywhere; }
.feedback-heading { font-size: 14px; font-weight: 600; margin: 22px 0 10px; }
.feedback-description { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.7; }
.feedback-picture { max-width: 100%; max-height: 200px; border: 1px solid var(--el-border-color-light); border-radius: 8px; }
.feedback-picture :deep(img) { max-height: 190px; }
</style>
