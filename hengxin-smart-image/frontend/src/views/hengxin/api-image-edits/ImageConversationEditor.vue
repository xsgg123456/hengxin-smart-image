<template>
  <div class="image-conversation">
    <div class="conversation-status" role="status"><span>{{ status }}</span><ElButton v-if="loadError" text @click="refresh">重新读取</ElButton></div>
    <p v-if="latest?.messages.length" class="latest-reply" role="status">{{ latest.messages.at(-1) }}</p>
    <ImageConversationHistory :conversation="conversation" :versions="item.versions" :connection="connection" :disabled="locked" @select-version="selectVersion" @select-turn="selectTurn" />
    <div v-if="source" class="revision-editor"><AnnotationEditor ref="editor" :draft-key="draftKey" :load-original="loadOriginal" :base-label="baseLabel" :limit="4000" marking-optional require-text :preview-prompt="buildImageEditPrompt" :disabled="locked || !!referenceError" description="当前底图是唯一编辑基础，原图与素材仅参考指定修改；其余内容保持不变。候选可继续修改，采用后才更新成品。" @preview-state="$emit('previewState', $event)" @submit="submit">
      <template #references="{ hasAnnotation, marks }"><RevisionReferences v-if="!referenceError" :references="references" :has-annotation="hasAnnotation" :marks="marks" /><ElAlert v-else :title="referenceError" type="error" :closable="false" /></template>
      <template #inputs="{ annotationUrl }"><RevisionReferences :references="references" :annotation-url="annotationUrl" confirmation /></template>
    </AnnotationEditor></div>
    <ElAlert v-else-if="!loading" title="底图原始文件不可用，请重新读取任务详情。" type="error" :closable="false" />
    <ElAlert v-if="error" :title="error" type="error" :closable="false" />
  </div>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { apiImages, errorText } from '@/api/api-image-edits'
import type { ApiItem, ApiPicture, ApiTask } from '@/types/api-image-edits'
import { editTurnLabels } from '@/types/api-image-conversation'
import AnnotationEditor, { type PreparedAnnotation } from '../components/annotation/AnnotationEditor.vue'
import RevisionReferences from './RevisionReferences.vue'
import ImageConversationHistory from './ImageConversationHistory.vue'
import { revisionReferences } from './revision-references'
import { buildImageEditPrompt } from './image-edit-prompt'
import { useImageConversation } from './use-image-conversation'
const props = defineProps<{ task: ApiTask; item: ApiItem; user: string; blocked?: boolean }>()
const emit = defineEmits<{ accepted: []; previewState: [value: boolean]; locked: [value: boolean] }>()
const { conversation, loading, error: loadError, connection, command, active, refresh, send, stop: stopTurn } = useImageConversation(props.user, props.task.id, props.item.id)
const source = shallowRef<ApiPicture>(), baseVersion = ref(props.item.currentVersion || 0), baseTurnId = ref(''), selected = ref(false)
const editor = ref<InstanceType<typeof AnnotationEditor>>(), uploading = ref(false), stopping = ref(false), localError = ref('')
const busy = computed(() => uploading.value || command.state.busy || stopping.value)
const pending = computed(() => command.state.pending)
const locked = computed(() => busy.value || loading.value || !!pending.value || !!active.value || !!props.blocked || !conversation.value)
const latest = computed(() => conversation.value?.turns.at(-1))
const candidate = computed(() => conversation.value?.turns.find(turn => turn.id === baseTurnId.value))
const canAdopt = computed(() => !!candidate.value?.candidate && candidate.value.status !== 'adopted' && !locked.value)
const baseLabel = computed(() => baseTurnId.value ? `基于第 ${(conversation.value?.turns.findIndex(t => t.id === baseTurnId.value) ?? 0) + 1} 轮候选 · 图片修改` : `基于 V${baseVersion.value} · 图片修改`)
const status = computed(() => loading.value ? '正在恢复修改会话…' : active.value ? `后台${editTurnLabels[active.value.status]} · 本轮编辑暂不可用，关闭窗口后仍继续` : latest.value ? editTurnLabels[latest.value.status] : '填写意见，开始本图的第一轮修改')
const error = computed(() => localError.value || command.state.error || loadError.value)
const replyAnchor = computed(() => [...(conversation.value?.turns || [])].reverse().find(turn => turn.status === 'waiting_user')?.id || '')
const draftKey = computed(() => JSON.stringify(['api-cli', props.user, props.task.id, props.item.id, baseTurnId.value || baseVersion.value, source.value?.fileId, replyAnchor.value]))
const referenceState = computed(() => { try { return { inputs: revisionReferences('image_edit', source.value, props.item.source, props.task.material), error: '' } } catch (e) { return { inputs: [], error: errorText(e) } } })
const references = computed(() => referenceState.value.inputs), referenceError = computed(() => referenceState.value.error)
let alive = true, generation = 0, seenCandidate = ''
watch(() => busy.value || !!pending.value || !!active.value, value => emit('locked', value), { immediate: true })
watch(draftKey, () => { generation++; localError.value = '' })
function selectVersion(number: number) {
  if (locked.value) return
  const version = props.item.versions.find(v => v.number === number)
  if (version) { selected.value = true; baseTurnId.value = ''; baseVersion.value = number; source.value = { ...version.picture } }
}
function selectTurn(id: string) {
  if (locked.value) return
  const turn = conversation.value?.turns.find(t => t.id === id)
  if (turn?.candidate) { selected.value = true; baseTurnId.value = id; source.value = { ...turn.candidate } }
}
watch(conversation, value => {
  if (!value) return
  const newest = [...value.turns].reverse().find(t => t.candidate)
  const last = value.turns.at(-1)
  if (!source.value && last?.basePicture && !last.candidate) {
    seenCandidate = newest?.id || ''; baseTurnId.value = last.baseTurnId || ''; baseVersion.value = last.baseVersion || baseVersion.value; source.value = { ...last.basePicture }
  } else if (newest?.candidate && newest.id !== seenCandidate) {
    seenCandidate = newest.id; baseTurnId.value = newest.id; source.value = { ...newest.candidate }; selected.value = false
  } else if (!source.value && !selected.value) {
    const version = props.item.versions.find(v => v.number === value.currentVersion)
    if (version) { baseVersion.value = version.number; source.value = { ...version.picture } }
  }
}, { immediate: true })
function loadOriginal() { return source.value ? apiImages.download(source.value.fileId) : Promise.reject(new Error('底图文件缺失')) }
async function submit(value: PreparedAnnotation) {
  if (locked.value || referenceError.value) return
  const token = generation, input = { ...(baseTurnId.value ? { baseTurnId: baseTurnId.value } : { baseVersion: baseVersion.value }), text: value.text, prompt: buildImageEditPrompt(value.text) }
  uploading.value = true; localError.value = ''
  let annotation: ApiPicture | undefined, submitted = false
  try {
    if (value.file) annotation = await apiImages.upload(value.file)
    if (!alive || token !== generation || props.blocked) return
    submitted = true
    await send({ kind: 'submit', input: { ...input, ...(annotation ? { annotationFileId: annotation.fileId } : {}) } })
  } catch (e) { if (alive) localError.value = errorText(e) }
  finally {
    if (annotation && !submitted) void apiImages.deleteFile(annotation.fileId).catch(() => {})
    uploading.value = false
  }
}
async function confirmPrevious() {
  if (!pending.value || busy.value) return
  const adopted = pending.value.action.kind === 'adopt'
  if (await send(pending.value.action) && adopted) emit('accepted')
}
async function adopt() {
  if (!canAdopt.value || !conversation.value?.currentVersion) return
  if (await send({ kind: 'adopt', turnId: baseTurnId.value, expectedVersion: conversation.value.currentVersion })) emit('accepted')
}
async function stop() { if (busy.value) return; stopping.value = true; try { await stopTurn() } finally { stopping.value = false } }
function preview() { if (pending.value) void confirmPrevious(); else editor.value?.preview() }
onBeforeUnmount(() => { alive = false; generation++; emit('locked', false) })
defineExpose({ preview, adopt, stop, active, busy, locked, canAdopt, pending, baseLabel })
</script>
<style scoped>
.conversation-status { font-size:13px; color:var(--el-text-color-secondary); line-height:1.8; }
.latest-reply { white-space:pre-wrap; overflow-wrap:anywhere; max-height:110px; overflow:auto; margin:8px 0; }
</style>

