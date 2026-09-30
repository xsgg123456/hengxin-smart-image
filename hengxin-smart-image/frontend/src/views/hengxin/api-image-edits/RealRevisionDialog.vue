<template>
  <ElDialog v-model="open" :title="`修改第 ${item?.position || ''} 张图片 · 基于 V${baseVersion}`" width="min(1380px, 96vw)" align-center append-to-body destroy-on-close :close-on-click-modal="false" :close-on-press-escape="!working" :show-close="!working">
    <div class="revision-mode-row">
      <ElRadioGroup v-model="mode" aria-label="修改类型" :disabled="modeLocked"><ElRadioButton value="image_edit">图片修改</ElRadioButton><ElRadioButton value="text_edit">文字修改</ElRadioButton></ElRadioGroup>
      <span class="hx-footnote">{{ mode === 'image_edit' ? '本次只修改画面元素，不修改文字内容' : '本次只修改文字，不调整其他画面元素' }}</span>
      <ElButton text type="primary" :disabled="modeLocked" @click="fixedPromptOpen = true">查看固定提示词</ElButton>
    </div>
    <div v-if="open && source" class="revision-editor"><AnnotationEditor ref="editor" :draft-key="draftKey" :load-original="loadOriginal" :base-label="`本次基于 V${baseVersion} · ${modeLabel}`" :limit="4000" marking-optional require-text :preview-prompt="buildPrompt" :description="description" :disabled="working || !!pending || blocked" @preview-state="previewBusy = $event" @submit="submit" /></div>
    <ElAlert v-else title="该版本的成品原始文件不可用，请重新读取任务详情。" type="error" :closable="false" />
    <ElAlert v-if="error" :title="error" type="error" :closable="false" />
    <template #footer><ElButton :disabled="working" @click="open = false">关闭</ElButton><ElButton type="primary" :loading="working" :disabled="blocked || (!source && !pending)" @click="pending ? confirmPrevious() : editor?.preview()">{{ pending ? '确认原修改请求' : '预览提交内容' }}</ElButton></template>
  </ElDialog>
  <ElDialog v-model="fixedPromptOpen" :title="`${modeLabel} · 固定提示词`" width="min(760px, 94vw)" align-center append-to-body>
    <p class="hx-footnote">固定规则适用于不同图片；本次修改意见在提交时单独填入。需要图片和文字两类修改时，请分两次操作。</p>
    <pre class="fixed-prompt">{{ fixedPrompt }}</pre>
    <template #footer><ElButton @click="fixedPromptOpen = false">返回修改</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { useUserStore } from '@/store/modules/user'
import { apiImages, errorText } from '@/api/api-image-edits'
import type { ApiPicture, ApiTask } from '@/types/api-image-edits'
import AnnotationEditor, { type PreparedAnnotation } from '../components/annotation/AnnotationEditor.vue'
import { forgetAnnotationDraft } from '../components/annotation/annotation-drafts'
import { buildTextEditPrompt, TEXT_EDIT_TEMPLATE } from './text-edit-prompt'
import { buildImageEditPrompt, IMAGE_EDIT_TEMPLATE } from './image-edit-prompt'
import { itemCommand, type ItemCommand } from './item-command'
const open = defineModel<boolean>({ required: true })
const props = defineProps<{ task: ApiTask; itemId: string; blocked?: boolean }>()
const emit = defineEmits<{ accepted: [] }>()
const userStore = useUserStore(), user = computed(() => String(userStore.getUserInfo.userId))
const item = computed(() => props.task.items.find(i => i.id === props.itemId))
const operation = computed(() => itemCommand(user.value, props.task.id, props.itemId))
const pending = computed(() => operation.value.state.pending)
const uploading = ref(false), working = computed(() => uploading.value || operation.value.state.busy)
const editKind = ref<'image_edit' | 'text_edit'>('image_edit'), previewBusy = ref(false), fixedPromptOpen = ref(false)
const modeLocked = computed(() => working.value || !!pending.value || !!props.blocked || previewBusy.value || fixedPromptOpen.value)
const mode = computed({ get: () => editKind.value, set: (value: 'image_edit' | 'text_edit') => { if (!modeLocked.value) editKind.value = value } })
const modeLabel = computed(() => mode.value === 'image_edit' ? '图片修改' : '文字修改')
const buildPrompt = computed(() => mode.value === 'image_edit' ? buildImageEditPrompt : buildTextEditPrompt)
const fixedPrompt = computed(() => mode.value === 'image_edit' ? IMAGE_EDIT_TEMPLATE : TEXT_EDIT_TEMPLATE)
const description = computed(() => mode.value === 'image_edit'
  ? '按意见编辑指定元素或区域，保留文字及其他未指定内容；标注仅用于定位。文字修改请切换模式，不能混合提交。'
  : '只替换指定文字，保留字体样式与布局；仅修补文字所需的邻近背景。图片元素修改请切换模式，不能混合提交。')
const baseVersion = ref(0), source = shallowRef<ApiPicture>(), localError = ref('')
const editor = ref<InstanceType<typeof AnnotationEditor>>()
const error = computed(() => localError.value || operation.value.state.error)
const draftKey = computed(() => JSON.stringify(['api', user.value, props.task.id, props.itemId, baseVersion.value, source.value?.fileId, mode.value]))
let generation = 0, alive = true
let cached: { file: File; picture: ApiPicture; operation: ReturnType<typeof itemCommand> } | undefined
watch([open, () => props.itemId, () => props.task.id, user], () => {
  generation++; clearUnusedUpload(); localError.value = ''; fixedPromptOpen.value = false; previewBusy.value = false
  if (!open.value) return
  const command = pending.value?.command
  editKind.value = command?.kind === 'revise' && command.input.kind !== 'image_edit' ? 'text_edit' : 'image_edit'
  baseVersion.value = command?.kind === 'revise' ? command.input.baseVersion : item.value?.currentVersion || 0
  const picture = item.value?.versions.find(v => v.number === baseVersion.value)?.picture
  source.value = picture ? { ...picture } : undefined
}, { immediate: true, flush: 'sync' })
watch(editKind, () => { generation++; clearUnusedUpload(); localError.value = '' }, { flush: 'sync' })
function clearUnusedUpload() {
  const saved = cached; cached = undefined
  // Uncertain requests own their frozen attachment until acceptance is resolved.
  if (saved && !saved.operation.state.pending && !saved.operation.state.busy) void apiImages.deleteFile(saved.picture.fileId).catch(() => {})
}
function loadOriginal() {
  if (!source.value?.fileId) return Promise.reject(new Error('成品原始文件标识缺失'))
  return apiImages.download(source.value.fileId)
}
async function send(command: ItemCommand) {
  const op = operation.value, taskId = props.task.id, itemId = props.itemId, key = draftKey.value, token = generation
  const accepted = await op.submit(command, (frozen, idempotencyKey) => {
    if (frozen.kind !== 'revise') throw new Error('请先确认该图片尚未完成的操作')
    return apiImages.revise(taskId, itemId, frozen.input, idempotencyKey)
  })
  if (accepted) forgetAnnotationDraft(key)
  if (accepted && alive && token === generation) { cached = undefined; open.value = false; emit('accepted') }
}
async function confirmPrevious() { if (!working.value && !props.blocked && pending.value) await send(pending.value.command) }
async function submit(value: PreparedAnnotation) {
  if (working.value || props.blocked || pending.value) return
  if (item.value?.currentVersion !== baseVersion.value) { localError.value = '当前版本已更新，请关闭后重新打开修改。'; return }
  const token = generation, kind = mode.value, version = baseVersion.value, prompt = buildPrompt.value(value.text)
  uploading.value = true; localError.value = ''
  try {
    let annotation: ApiPicture | undefined
    if (value.file) {
      annotation = cached?.file === value.file ? cached.picture : await apiImages.upload(value.file)
      cached = { file: value.file, picture: annotation, operation: operation.value }
    }
    if (!alive || generation !== token || !open.value || props.blocked) {
      if (annotation) await apiImages.deleteFile(annotation.fileId)
      return
    }
    if (item.value?.currentVersion !== baseVersion.value) throw new Error('当前版本已更新，请关闭后重新打开修改。')
    await send({ kind: 'revise', input: { baseVersion: version, kind, text: value.text, prompt, annotationFileId: annotation?.fileId }, annotation })
  } catch (error) { if (token === generation) localError.value = errorText(error) }
  finally { uploading.value = false }
}
onBeforeUnmount(() => { alive = false; generation++; clearUnusedUpload() })
</script>
<style scoped>
.revision-mode-row { display:flex; flex-wrap:wrap; align-items:center; gap:12px; margin-bottom:16px; }
.fixed-prompt { white-space:pre-wrap; overflow-wrap:anywhere; max-height:60dvh; overflow:auto; font:inherit; line-height:1.7; }
.revision-editor :deep(.annotation-editor) { height:min(65dvh,720px); }
@media(max-width:900px) { .revision-editor :deep(.annotation-editor) { height:calc(100dvh - 290px); min-height:450px; } }
@media(max-width:480px) {
  .revision-editor :deep(.annotation-editor) { grid-template-rows:minmax(260px,1fr) 110px; }
  .revision-editor :deep(.annotation-zoom .el-button) { padding-left:10px; padding-right:10px; }
  .revision-editor :deep(.annotation-pan small) { display:none; }
}
</style>
