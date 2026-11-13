<template>
  <section class="hx-page domestic-studio" :class="{ expanded }">
    <div class="hx-heading domestic-heading"><div><span class="hx-admin-kicker">AI IMAGE WORKSPACE</span><h1>{{ config.title }}</h1><p>{{ config.description }}</p></div><div><ElButton :icon="Reading" plain @click="tutorialOpen = true">使用教程</ElButton><ElButton :icon="Plus" :disabled="!canNewConversation" @click="createSession">新建会话</ElButton></div></div>
    <div class="domestic-card">
      <header class="domestic-toolbar"><div class="domestic-identity"><span class="domestic-ai"><ElIcon><MagicStick /></ElIcon></span><strong>AI 设计工作台</strong><small>{{ runningCount ? `${runningCount} 个会话处理中` : '准备就绪' }}</small></div><div class="domestic-tools"><ElButton size="small" :type="sessionsOpen ? 'primary' : 'default'" plain :icon="ChatDotRound" @click="sessionsOpen = !sessionsOpen">会话 · {{ sessions.length }}</ElButton><ElButton size="small" :type="materialsOpen ? 'primary' : 'default'" plain :icon="FolderOpened" @click="materialsOpen = !materialsOpen">素材</ElButton><ElButton size="small" :icon="FullScreen" @click="expanded = !expanded">{{ expanded ? '退出展开' : '展开' }}</ElButton></div></header>
      <ElAlert v-if="sessionError || preferenceNotice" :title="sessionError || preferenceNotice" type="warning" :closable="false" />
      <ElAlert v-if="sessionPending && !sessionBusy" title="会话操作结果尚未确认，请使用原请求重试。" type="warning" :closable="false"><ElButton @click="retrySession">核实会话操作</ElButton></ElAlert>
      <ElAlert v-if="error || limitError || skillError" :title="limitError || skillError || error" type="error" :closable="false" />
      <ElAlert v-if="pending && !busy" title="上次操作结果尚未确认，请使用原请求重试。" type="warning" :closable="false"><ElButton @click="retry">核实并重试</ElButton></ElAlert>
      <ElAlert v-if="activeTurn?.canRecover" :title="activeTurn.recoveryRequested ? '正在核实原执行并收取结果，不会重新生成。' : '本轮结果尚未收取完成，可核实原执行并重试收取。'" type="warning" :closable="false"><ElButton v-if="!activeTurn.recoveryRequested" :disabled="busy || uploading || !!pending" @click="recoverTurn">核实并收取结果</ElButton></ElAlert>
      <div class="studio-workspace">
        <StudioSessionList v-if="sessionsOpen && !mobile" :sessions="sessions" :active-id="activeId" :disabled="!canManage" :can-create="canNewConversation" domestic @select="chooseSession" @create="createSession" @close="sessionsOpen = false" @action="sessionAction" />
        <section class="studio-conversation">
          <header class="session-current"><div><strong>{{ currentSession?.name || '正在准备会话…' }}</strong><small>{{ currentSession?.deletionStatus ? currentSession.deletionError || '正在清理会话文件' : '独立会话 · 切换会保留附件和草稿' }}</small></div><div class="domestic-tools"><ElButton size="small" :disabled="!currentSession || !!currentSession.deletionStatus || data?.conversationId !== activeId" @click="recoveryOpen = true">取回文件</ElButton><template v-if="canArchiveWorkspace"><ElButton size="small" :disabled="!canArchive" @click="archiveOpen = true">归档到成品库</ElButton><ElButton size="small" text @click="router.push('/product-library')">查看成品库</ElButton></template></div></header>
          <StudioTurns v-if="data?.conversationId === activeId" :key="activeId" :turns="data.turns" :transcript="transcript" :conversation-id="activeId" :selected="selected" :disabled="locked" :scroll-position="scrollPosition" hide-empty-guide simple-pictures batch-annotation @scroll-position="(position, id) => saveScroll(position, id || undefined)" @failure="fail" @group="toggleGroup" @toggle="toggle" @modify="openAnnotation" @batch-modify="openBatchAnnotation" />
          <div v-else class="studio-messages" />
          <div class="studio-composer" @dragover.prevent @drop.prevent="drop" @paste="paste">
            <ElAlert v-if="draftNotice" :title="draftNotice" type="warning" :closable="false" />
            <div v-if="ordinaryAttachments.length || revisions.length || plainReferences.length" class="composer-files">
              <StudioAttachments :assets="[...ordinaryAttachments, ...plainReferences]" title="本轮附件" compact removable :disabled="locked" @remove="removeAttachment" @failure="fail" />
              <StudioRevisionDraft v-for="revision in revisions" :key="revision.base.id" :revision="revision" :disabled="locked" @edit="openAnnotation(revision.base)" @remove="removeRevision(revision.base.id)" @failure="fail" />
            </div>
            <small v-if="revisionError" class="studio-revision-hint">{{ revisionError }}</small>
            <ElInput v-model="text" type="textarea" :rows="3" resize="none" :disabled="locked" aria-label="设计要求" placeholder="描述你的要求，或继续提出修改意见…" @keydown="handleStudioSendKey($event, send)" />
            <div class="studio-compose-tools"><div><ElCheckbox v-if="boundSkill" v-model="useSkill" class="domestic-skill-choice" :disabled="locked" :title="boundSkill.description || '选中后仅本轮使用'">{{ boundSkill.displayName }}<span v-if="useSkill"> · 本轮使用</span></ElCheckbox><span v-else class="domestic-skill-empty">暂无可选 Skill</span><ElButton v-if="skill && skill !== boundSkill?.id" text :disabled="locked" @click="skill = ''">取消失效 Skill</ElButton><ElButton text :icon="Paperclip" :disabled="locked" @click="input?.click()">上传附件</ElButton><small>拖拽或粘贴图片到这里</small></div><div class="studio-send-tools"><StudioTextEditor v-model="text" :disabled="locked" :session-name="currentSession?.name || '会话'" domestic /><ElButton v-if="data?.activeTurnId" :loading="busy" :disabled="!editable || !!pending || uploading" @click="stop">停止</ElButton><ElButton v-else type="primary" :icon="Promotion" :loading="busy" :disabled="!canSend" @click="send">发送</ElButton></div></div>
            <input ref="input" hidden type="file" multiple @change="upload">
          </div>
          <p class="studio-compose-note">发送到：{{ currentSession?.name || '请先新建会话' }} · Enter 发送，Shift + Enter 换行</p>
        </section>
        <StudioMaterials v-if="materialsOpen" :key="activeId" :assets="data?.materials || []" :disabled="locked" domestic @close="materialsOpen = false" @add="add" @failure="fail" />
      </div>
    </div>
    <ElDrawer v-if="mobile" v-model="sessionsOpen" :with-header="false" title="会话列表" size="min(300px,90vw)" direction="ltr" class="domestic-session-drawer" append-to-body><StudioSessionList :sessions="sessions" :active-id="activeId" :disabled="!canManage" :can-create="canNewConversation" domestic @select="chooseSession" @create="createSession" @close="sessionsOpen = false" @action="sessionAction" /></ElDrawer>
    <ElDrawer v-model="tutorialOpen" :title="`${config.title} · 使用教程`" size="min(460px, 100vw)"><ElEmpty description="教程待补充" /></ElDrawer>
    <ArchiveDialog v-if="canArchiveWorkspace && currentSession" :key="activeId" v-model="archiveOpen" :workspace="config.key" :conversation="currentSession" :actor="actor" />
    <StudioRecoveryDialog v-if="recoveryOpen && activeId && data?.conversationId === activeId" :key="activeId" scope="domestic" :task-id="config.key" :conversation-id="activeId" :readonly="!editable" :busy="!!data?.activeTurnId || uploading" @close="recoveryOpen = false" @saved="refresh" @failure="fail" />
    <StudioEditDialog v-if="editing && data" :key="editingKey" :pictures="editing.pictures" :initial-id="editing.initialId" :batch="editing.batch" :has-confirmed="editing.pictures.some(p => revisions.some(r => r.base.id === p.id))" :key-for="draftKey" :submitting="uploading" :error="annotationError" @close="closeAnnotation" @confirm="applyAnnotation" />
  </section>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound, FolderOpened, FullScreen, MagicStick, Paperclip, Plus, Promotion, Reading } from '@element-plus/icons-vue'
import { useWindowSize } from '@vueuse/core'
import { createStudioApi, type StudioPicture } from '@/api/shared/studio'
import { overseasImageCache } from '@/api/shared/image-cache'
import { useStudioSessions } from '@/views/shared/studio/use-studio-sessions'
import type { SessionView } from '@/views/shared/studio/studio-session-state'
import { handleStudioSendKey } from '@/views/shared/studio/studio-send-key'
import { draftFor, forgetDraft, type PreparedRevision } from '@/views/shared/studio/editing/state'
import { revisionAssetIds } from '@/views/shared/studio/studio-revisions'
import StudioSessionList from '@/views/shared/studio/StudioSessionList.vue'
import StudioTurns from '@/views/shared/studio/StudioTurns.vue'
import StudioMaterials from '@/views/shared/studio/StudioMaterials.vue'
import StudioAttachments from '@/views/shared/studio/StudioAttachments.vue'
import StudioTextEditor from '@/views/shared/studio/StudioTextEditor.vue'
import StudioRecoveryDialog from '@/views/shared/studio/StudioRecoveryDialog.vue'
import StudioRevisionDraft from '@/views/shared/studio/StudioRevisionDraft.vue'
import StudioEditDialog from '@/views/shared/studio/editing/EditorDialog.vue'
import type { domesticWorkspaces } from '@/api/hengxin/domestic-workspaces'
import ArchiveDialog from './ArchiveDialog.vue'

const props = defineProps<{ config: typeof domesticWorkspaces[number]; actor: string }>()
const router = useRouter(), api = createStudioApi(fetch, 'domestic')
overseasImageCache.setIdentity(`domestic:${props.actor}`)
const failure = (reason: unknown) => { if (reason instanceof Error) ElMessage.error(reason.message) }
const { data, sessions, activeId, currentSession, runningCount, canManage, canNewConversation, newConversation,
  renameConversation, deleteConversation, selectSession, sessionBusy, sessionError, sessionPending, retrySession,
  preferenceNotice, scrollPosition, saveScroll, text, skill, skillError, attachments, references, revisions, revisionError, draftKey, confirmRevisions, removeRevision, selected, transcript, error, limitError,
  busy, uploading, pending, editable, activeTurn, locked, canSend, send, retry, stop, recoverTurn, refresh, add, receive, toggle, toggleGroup,
  fail, draftNotice } = useStudioSessions(() => ({ id: props.config.key, version: 1, capabilities: ['task.design'] }), failure, () => {}, api, props.actor, true)
const boundSkill = computed(() => data.value?.skills[0])
const useSkill = computed({ get: () => !!boundSkill.value && skill.value === boundSkill.value.id,
  set: (checked: boolean) => { skill.value = checked ? boundSkill.value?.id || '' : '' } })
const { width } = useWindowSize()
const mobile = computed(() => width.value < 800)
const sessionsOpen = ref(!mobile.value), materialsOpen = ref(false), expanded = ref(false), tutorialOpen = ref(false), archiveOpen = ref(false), recoveryOpen = ref(false)
const input = ref<HTMLInputElement>()
const canArchiveWorkspace = computed(() => ['camera', 'case'].includes(props.config.key))
const canArchive = computed(() => !!currentSession.value && !currentSession.value.deletionStatus && !data.value?.activeTurnId
  && !!data.value?.turns.some(turn => turn.reply?.trim()))
const editing = ref<{ pictures: StudioPicture[]; initialId: string; batch: boolean }>(), editingKey = ref(''), annotationError = ref('')
const visitedDrafts = new Set<string>()
const ordinaryAttachments = computed(() => { const ids = new Set(revisions.value.flatMap(revisionAssetIds)); return attachments.value.filter(item => !ids.has(item.id)) })
const plainReferences = computed(() => references.value.filter(item => !revisions.value.some(revision => revision.base.id === item.id)))
function removeAttachment(id: string) { if (!locked.value) { attachments.value = attachments.value.filter(item => item.id !== id); references.value = references.value.filter(item => item.id !== id) } }
function openEditor(pictures: StudioPicture[], batch: boolean) {
  if (locked.value || !pictures.length) return
  for (const picture of pictures) {
    const key = draftKey(picture); visitedDrafts.add(key)
    draftFor(key, revisions.value.find(revision => revision.base.id === picture.id)?.referenceImages)
  }
  annotationError.value = ''; editingKey.value = `${draftKey(pictures[0])}:${batch}`
  editing.value = { pictures, initialId: pictures[0].id, batch }
}
function openAnnotation(picture: StudioPicture) { openEditor([picture], false) }
function openBatchAnnotation(pictures: StudioPicture[]) { openEditor(pictures, true) }
function closeAnnotation() { editing.value = undefined; annotationError.value = '' }
async function applyAnnotation(items: PreparedRevision[], groupIds?: string[]) {
  if (!editing.value) return
  const owner = editing.value
  annotationError.value = ''
  const saved = await confirmRevisions(items, groupIds)
  if (editing.value !== owner) return
  if (saved) { closeAnnotation(); ElMessage.success(items.length ? `已带回${items.length}张图片，补充后点击发送` : '已移除本组待发送修改') }
  else annotationError.value = error.value || '修改材料未保存，请重试'
}
async function chooseSession(session: SessionView) { await selectSession(session.id); if (mobile.value) sessionsOpen.value = false }
async function createSession() { await newConversation(); if (mobile.value) sessionsOpen.value = false }
function upload(event: Event) { const target = event.target as HTMLInputElement; void receive(Array.from(target.files || [])); target.value = '' }
function drop(event: DragEvent) { const id = event.dataTransfer?.getData('application/x-studio-material'); if (id) add([id]); else void receive(Array.from(event.dataTransfer?.files || [])) }
function paste(event: ClipboardEvent) { const files = Array.from(event.clipboardData?.files || []); if (files.length) { event.preventDefault(); void receive(files) } }
async function sessionAction(command: string, session: SessionView) {
  if (!canManage.value) return
  try {
    if (command === 'rename') {
      const { value } = await ElMessageBox.prompt('名称只用于区分会话。', '重命名会话', { inputValue: session.name, inputValidator: value => !!value?.trim() && value.trim().length <= 30 || '请输入 1–30 个字', confirmButtonText: '保存', cancelButtonText: '取消' })
      await renameConversation(session, value)
    } else if (command === 'delete' && !session.activeTurnId && session.deletionStatus !== 'deleting') {
      await ElMessageBox.confirm(`删除「${session.name}」及其对话和文件？已归档成品保留。`, '删除会话', { type: 'warning', confirmButtonText: session.deletionStatus === 'delete_failed' ? '重试删除' : '确认删除', cancelButtonText: '取消' })
      await deleteConversation(session)
    }
  } catch { /* The confirmation was cancelled. */ }
}
watch(mobile, value => { sessionsOpen.value = !value })
watch(() => props.config.key, () => { sessionsOpen.value = !mobile.value; materialsOpen.value = false })
watch(data, value => { if (!value) closeAnnotation() })
watch(activeId, () => { archiveOpen.value = false; recoveryOpen.value = false; closeAnnotation() })
onUnmounted(() => { closeAnnotation(); visitedDrafts.forEach(forgetDraft); overseasImageCache.clear() })
</script>
<style src="@/views/shared/studio/studio.css"></style>
<style src="@/views/shared/studio/studio-sessions.css"></style>
<style src="./workspace.css"></style>
