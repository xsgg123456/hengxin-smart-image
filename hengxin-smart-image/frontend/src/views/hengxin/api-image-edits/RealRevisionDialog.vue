<template>
  <ElDialog v-model="open" :title="`修改第 ${item?.position || ''} 张图片 · ${cliMode ? imageEditor?.baseLabel || '图片修改' : `基于 V${baseVersion}`}`" width="min(1380px, 96vw)" align-center append-to-body destroy-on-close :close-on-click-modal="false" :close-on-press-escape="cliMode || !working" :show-close="cliMode || !working">
    <div class="revision-mode-row">
      <ElRadioGroup v-model="mode" aria-label="修改类型" :disabled="modeLocked"><ElRadioButton value="image_edit">图片修改</ElRadioButton><ElRadioButton value="text_edit">文字修改</ElRadioButton></ElRadioGroup>
      <span class="hx-footnote">{{ mode === 'image_edit' ? '本次只修改画面元素，不修改文字内容' : '本次只修改文字，不调整其他画面元素' }}</span>
      <ElButton text type="primary" :disabled="modeLocked" @click="fixedPromptOpen = true">查看固定提示词</ElButton>
    </div>
    <PendingRevision v-if="pending" :command="pending.command" />
    <ImageConversationEditor v-else-if="cliMode && open && item" :key="`${user}:${task.id}:${itemId}`" ref="imageEditor" :task="task" :item="item" :user="user" :blocked="blocked" @accepted="emit('accepted')" @preview-state="previewBusy = $event" @locked="imageLocked = $event" />
    <div v-else-if="open && source" class="revision-editor"><AnnotationEditor ref="editor" :draft-key="draftKey" :load-original="loadOriginal" :base-label="`本次基于 V${baseVersion} · ${modeLabel}`" :limit="4000" marking-optional require-text :preview-prompt="buildPrompt" :description="description" :disabled="working || !!pending || blocked || !!referenceError" @preview-state="previewBusy = $event" @submit="submit">
      <template #references="{ hasAnnotation, marks }"><RevisionReferences v-if="!referenceError" :references="references" :has-annotation="hasAnnotation" :marks="marks" /><ElAlert v-else :title="referenceError" type="error" :closable="false" /></template>
      <template #inputs="{ annotationUrl }"><RevisionReferences :references="references" :annotation-url="annotationUrl" confirmation /></template>
    </AnnotationEditor></div>
    <ElAlert v-else title="该版本的成品原始文件不可用，请重新读取任务详情。" type="error" :closable="false" />
    <ElAlert v-if="error" :title="error" type="error" :closable="false" />
    <template #footer><ElButton :disabled="!cliMode && working" @click="open = false">关闭</ElButton><template v-if="cliMode"><ElButton v-if="imageEditor?.canAdopt" :disabled="imageEditor?.busy" @click="imageEditor?.adopt()">采用此图</ElButton><ElButton v-if="imageEditor?.active && !imageEditor.pending" type="danger" plain :loading="imageEditor?.busy" @click="imageEditor?.stop()">停止本轮</ElButton><ElButton v-else type="primary" :loading="imageEditor?.busy" :disabled="!imageEditor || (imageEditor.locked && !imageEditor.pending) || blocked" @click="imageEditor?.preview()">{{ imageEditor?.pending ? '确认原修改请求' : '预览提交内容' }}</ElButton></template><ElButton v-else type="primary" :loading="working" :disabled="blocked || (!pending && (!source || !!referenceError))" @click="pending ? confirmPrevious() : editor?.preview()">{{ pending ? '确认原修改请求' : '预览提交内容' }}</ElButton></template>
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
import RevisionReferences from './RevisionReferences.vue'
import PendingRevision from './PendingRevision.vue'
import ImageConversationEditor from './ImageConversationEditor.vue'
import { revisionReferences } from './revision-references'
const open = defineModel<boolean>({ required: true })
const props = defineProps<{ task: ApiTask; itemId: string; blocked?: boolean }>()
const emit = defineEmits<{ accepted: [] }>()
const userStore = useUserStore(), user = computed(() => String(userStore.getUserInfo.userId))
const item = computed(() => props.task.items.find(i => i.id === props.itemId))
const operation = computed(() => itemCommand(user.value, props.task.id, props.itemId))
const pending = computed(() => operation.value.state.pending)
const uploading = ref(false), working = computed(() => uploading.value || operation.value.state.busy)
const editKind = ref<'image_edit' | 'text_edit'>('image_edit'), previewBusy = ref(false), fixedPromptOpen = ref(false)
const imageEditor = ref<InstanceType<typeof ImageConversationEditor>>(), imageLocked = ref(false)
const cliMode = computed(() => editKind.value === 'image_edit' && !pending.value)
const modeLocked = computed(() => working.value || (cliMode.value && imageLocked.value) || !!pending.value || !!props.blocked || previewBusy.value || fixedPromptOpen.value)
const mode = computed({ get: () => editKind.value, set: (value: 'image_edit' | 'text_edit') => { if (!modeLocked.value) editKind.value = value } })
const modeLabel = computed(() => mode.value === 'image_edit' ? '图片修改' : '文字修改')
const buildPrompt = computed(() => mode.value === 'image_edit' ? buildImageEditPrompt : buildTextEditPrompt)
const fixedPrompt = computed(() => mode.value === 'image_edit' ? IMAGE_EDIT_TEMPLATE : TEXT_EDIT_TEMPLATE)
const description = computed(() => mode.value === 'image_edit'
  ? '当前成品是唯一编辑底图，原图与素材仅参考指定修改；其余内容保持不变。标注仅用于定位，文字修改请切换模式。'
  : '只替换指定文字，保留字体样式与布局；仅修补文字所需的邻近背景。图片元素修改请切换模式，不能混合提交。')
const baseVersion = ref(0), source = shallowRef<ApiPicture>(), localError = ref('')
const referenceState = computed(() => {
  try { return { inputs: revisionReferences(mode.value, source.value, item.value?.source, props.task.material), error: '' } }
  catch (error) { return { inputs: [], error: errorText(error) } }
})
const references = computed(() => referenceState.value.inputs), referenceError = computed(() => referenceState.value.error)
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
watch(editKind, value => {
  generation++; clearUnusedUpload(); localError.value = ''
  if (value === 'text_edit' && !pending.value) {
    baseVersion.value = item.value?.currentVersion || 0
    const picture = item.value?.versions.find(v => v.number === baseVersion.value)?.picture
    source.value = picture ? { ...picture } : undefined
  }
}, { flush: 'sync' })
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
  if (working.value || props.blocked || pending.value || referenceError.value) return
  if (item.value?.currentVersion !== baseVersion.value) { localError.value = '当前版本已更新，请关闭后重新打开修改。'; return }
  const token = generation, kind = mode.value, version = baseVersion.value, prompt = buildPrompt.value(value.text)
  const frozenReferences = references.value.map(input => ({ ...input, picture: { ...input.picture } }))
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
    await send({ kind: 'revise', input: { baseVersion: version, kind, text: value.text, prompt, annotationFileId: annotation?.fileId }, annotation, references: frozenReferences })
  } catch (error) { if (token === generation) localError.value = errorText(error) }
  finally { uploading.value = false }
}
onBeforeUnmount(() => { alive = false; generation++; clearUnusedUpload() })
</script>
<style scoped>
.revision-mode-row { display:flex; flex-wrap:wrap; align-items:center; gap:12px; margin-bottom:16px; }
.fixed-prompt { white-space:pre-wrap; overflow-wrap:anywhere; max-height:60dvh; overflow:auto; font:inherit; line-height:1.7; }
:deep(.revision-editor .annotation-editor) { height:min(65dvh,720px); }
@media(max-width:900px) {
  :deep(.revision-editor .annotation-editor) { height:calc(100dvh - 290px); min-height:600px; grid-template-rows:minmax(470px,1fr) 110px; }
  .revision-editor :deep(.annotation-pan small) { display:none; }
  .revision-editor :deep(.annotation-help) { height:36px; padding:4px 8px; font-size:11px; }
}
@media(max-width:480px) {
  .revision-editor :deep(.annotation-zoom .el-button) { padding-left:10px; padding-right:10px; }
  .revision-editor :deep(.annotation-pan small) { display:none; }
}
</style>
