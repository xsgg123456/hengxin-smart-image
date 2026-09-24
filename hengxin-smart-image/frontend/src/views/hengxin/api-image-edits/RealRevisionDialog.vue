<template>
  <ElDialog v-model="open" :title="`修改第 ${item?.position || ''} 张图片 · 基于 V${baseVersion}`" width="min(1380px, 96vw)" align-center append-to-body destroy-on-close :close-on-click-modal="false" :close-on-press-escape="!working" :show-close="!working">
    <AnnotationEditor v-if="open && source" ref="editor" :draft-key="draftKey" :load-original="loadOriginal" :base-label="`本次基于 V${baseVersion} 修改`" :limit="4000" :disabled="working || !!pending || blocked" @submit="submit" />
    <ElAlert v-else title="该版本的成品原始文件不可用，请重新读取任务详情。" type="error" :closable="false" />
    <ElAlert v-if="error" :title="error" type="error" :closable="false" />
    <template #footer><ElButton :disabled="working" @click="open = false">关闭</ElButton><ElButton type="primary" :loading="working" :disabled="blocked || (!source && !pending)" @click="pending ? confirmPrevious() : editor?.preview()">{{ pending ? '确认原修改请求' : '预览提交内容' }}</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { useUserStore } from '@/store/modules/user'
import { apiImages, errorText } from '@/api/api-image-edits'
import type { ApiPicture, ApiTask } from '@/types/api-image-edits'
import AnnotationEditor, { type PreparedAnnotation } from '../components/annotation/AnnotationEditor.vue'
import { forgetAnnotationDraft } from '../components/annotation/annotation-drafts'
import { itemCommand, type ItemCommand } from './item-command'
const open = defineModel<boolean>({ required: true })
const props = defineProps<{ task: ApiTask; itemId: string; blocked?: boolean }>()
const emit = defineEmits<{ accepted: [] }>()
const userStore = useUserStore(), user = computed(() => String(userStore.getUserInfo.userId))
const item = computed(() => props.task.items.find(i => i.id === props.itemId))
const operation = computed(() => itemCommand(user.value, props.task.id, props.itemId))
const pending = computed(() => operation.value.state.pending)
const uploading = ref(false), working = computed(() => uploading.value || operation.value.state.busy)
const baseVersion = ref(0), source = shallowRef<ApiPicture>(), localError = ref('')
const editor = ref<InstanceType<typeof AnnotationEditor>>()
const error = computed(() => localError.value || operation.value.state.error)
const draftKey = computed(() => JSON.stringify(['api', user.value, props.task.id, props.itemId, baseVersion.value, source.value?.fileId]))
let generation = 0, alive = true
let cached: { file: File; picture: ApiPicture; operation: ReturnType<typeof itemCommand> } | undefined
watch([open, () => props.itemId, () => props.task.id, user], () => {
  generation++; clearUnusedUpload(); localError.value = ''
  if (!open.value) return
  const command = pending.value?.command
  baseVersion.value = command?.kind === 'revise' ? command.input.baseVersion : item.value?.currentVersion || 0
  const picture = item.value?.versions.find(v => v.number === baseVersion.value)?.picture
  source.value = picture ? { ...picture } : undefined
}, { immediate: true, flush: 'sync' })
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
  const token = generation; uploading.value = true; localError.value = ''
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
    await send({ kind: 'revise', input: { baseVersion: baseVersion.value, text: value.text, annotationFileId: annotation?.fileId }, annotation })
  } catch (error) { if (token === generation) localError.value = errorText(error) }
  finally { uploading.value = false }
}
onBeforeUnmount(() => { alive = false; generation++; clearUnusedUpload() })
</script>
