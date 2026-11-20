<template>
  <nav class="overseas-support-menu" aria-label="帮助与信息">
    <button type="button" title="意见反馈" :class="{ selected: open }" aria-label="意见反馈" @click="start">
      <ElIcon><ChatLineSquare /></ElIcon><span>意见反馈</span>
    </button>
    <button type="button" title="关于我们" :class="{ selected: route.path === '/overseas/about' && !open }" aria-label="关于我们" @click="about">
      <ElIcon><InfoFilled /></ElIcon><span>关于我们</span>
    </button>
  </nav>
  <ElDrawer v-model="open" title="意见反馈" size="min(450px, 100vw)" append-to-body
    :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy">
    <ElTabs v-model="tab">
      <ElTabPane label="提交反馈" name="create">
        <ElForm label-position="top" class="support-form" @submit.prevent="submit">
          <ElFormItem label="反馈页面"><span class="support-source">{{ feedbackSourceText(source, taskName, sku) }}
            <small v-if="pendingContext" role="status">正在读取任务信息…</small></span></ElFormItem>
          <ElFormItem label="问题描述" required :error="error">
            <ElInput v-model="description" aria-label="问题描述" type="textarea" :rows="5" maxlength="2000" show-word-limit :disabled="busy"
              placeholder="你进行了什么操作？页面出现了什么问题？" @input="error = ''" />
          </ElFormItem>
          <ElFormItem label="问题截图（选填）">
            <label v-if="!picture" class="support-upload"><ElIcon><Upload /></ElIcon> 添加截图
              <input type="file" accept="image/png,image/jpeg,image/webp" aria-label="添加截图" :disabled="busy" @change="attach">
            </label>
            <div v-else class="support-image"><img :src="url" alt="已选问题截图"><div>{{ picture.name }}
              <ElButton link type="danger" :disabled="busy" @click="clearPicture">移除</ElButton></div></div>
          </ElFormItem>
        </ElForm>
      </ElTabPane>
      <ElTabPane label="我的反馈" name="mine" :disabled="busy">
        <MyFeedback v-if="open && tab === 'mine'" :api="api" @failure="denied" />
      </ElTabPane>
    </ElTabs>
    <template #footer>
      <div v-if="tab === 'create'" class="support-footer"><ElButton :disabled="busy" @click="open = false">取消</ElButton>
        <ElButton type="primary" :loading="busy" :disabled="pendingContext" @click="submit">提交反馈</ElButton></div>
      <ElButton v-else @click="open = false">关闭</ElButton>
    </template>
  </ElDrawer>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ChatLineSquare, InfoFilled, Upload } from '@element-plus/icons-vue'
import { useSettingStore } from '@/store/modules/setting'
import { feedbackAccessDenied, feedbackError, feedbackSourceText, screenshotIssue, type FeedbackApi } from '@/api/overseas/feedback'
import MyFeedback from './MyFeedback.vue'

const props = defineProps<{ source: string; taskName?: string; sku?: string; pendingContext?: boolean; api: FeedbackApi }>()
const emit = defineEmits<{ submitted: []; failure: [reason: unknown] }>()
const route = useRoute(), router = useRouter(), settings = useSettingStore()
const tab = ref('create'), open = ref(false), busy = ref(false), error = ref('')
const description = ref(''), url = ref(''), picture = ref<File>()
let active = true
watch(() => route.query.feedback, value => {
  if (value === 'mine') { tab.value = 'mine'; open.value = true }
}, { immediate: true })

function closeMobileMenu() { if (window.innerWidth < 800) settings.setMenuOpen(false) }
function start() { closeMobileMenu(); tab.value = 'create'; open.value = true }
function about() { closeMobileMenu(); void router.push('/overseas/about') }
function clearPicture() {
  if (url.value) URL.revokeObjectURL(url.value)
  url.value = ''; picture.value = undefined
}
function clearDraft() { clearPicture(); description.value = ''; error.value = '' }
function denied(reason: unknown) { clearDraft(); open.value = false; emit('failure', reason) }
function attach(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]
  if (!file) return
  const issue = screenshotIssue(file)
  if (issue) { ElMessage.warning(issue); input.value = ''; return }
  clearPicture(); picture.value = file; url.value = URL.createObjectURL(file)
}
async function submit() {
  if (busy.value || props.pendingContext) return
  if (!description.value.trim()) { error.value = '请填写问题描述'; return }
  busy.value = true
  try {
    await props.api.create({ source: props.source, taskName: props.taskName, sku: props.sku }, description.value, picture.value)
    if (!active) return
    clearDraft(); emit('submitted'); tab.value = 'mine'; ElMessage.success('反馈已提交')
  } catch (reason) {
    if (!active) return
    if (feedbackAccessDenied(reason)) denied(reason)
    else ElMessage.error(feedbackError(reason))
  } finally { if (active) busy.value = false }
}
onBeforeUnmount(() => { active = false; clearPicture() })
</script>
<style>
.menu-left:has(.overseas-support-menu) > .el-scrollbar { max-height: calc(100% - 180px); }
.menu-left-close .overseas-support-menu button { justify-content: center; padding: 0; }
.menu-left-close .overseas-support-menu button span { display: none; }
</style>
<style scoped>
.overseas-support-menu { position: absolute; bottom: 10px; left: 8px; right: 8px; padding-top: 8px; border-top: 1px solid var(--el-border-color-lighter); display: grid; gap: 3px; }
.overseas-support-menu button { height: 42px; border: 0; border-radius: 6px; display: flex; align-items: center; gap: 10px; padding: 0 14px; background: transparent; color: var(--el-text-color-regular); font: inherit; font-size: 14px; cursor: pointer; }
.overseas-support-menu .el-icon { font-size: 17px; }
.overseas-support-menu button:hover { background: var(--el-fill-color-light); }
.overseas-support-menu button.selected { background: var(--el-color-primary-light-9); color: var(--el-color-primary); }
.support-form .el-form-item { margin-bottom: 24px; }
.support-source { color: var(--el-text-color-secondary); font-size: 13px; overflow-wrap: anywhere; }
.support-upload { position: relative; display: inline-flex; align-items: center; gap: 8px; padding: 4px 14px; border: 1px dashed var(--el-border-color); border-radius: 6px; cursor: pointer; }
.support-upload input { position: absolute; inset: 0; opacity: 0; width: 100%; cursor: pointer; }
.support-upload:focus-within { outline: 2px solid var(--el-color-primary); }
.support-image { min-width: 0; overflow-wrap: anywhere; }
.support-image img { display: block; max-width: 100%; max-height: 180px; object-fit: contain; }
.support-footer { display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
.support-footer button + button { margin-left: 0; }
</style>
