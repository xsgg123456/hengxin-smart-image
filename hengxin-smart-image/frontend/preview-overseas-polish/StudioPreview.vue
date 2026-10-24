<template>
  <section ref="workspace" class="studio-page" :style="{ '--studio-height': workspaceHeight }">
    <div class="studio-steps" aria-label="工作流进度">
      <span :class="completed ? 'finished' : 'done'">{{ completed ? '✓' : '①' }} 运营提交图需</span><i></i>
      <span :class="completed ? 'finished' : 'done'">{{ completed ? '✓' : '②' }} 设计人工审核</span><i></i>
      <span :class="completed ? 'finished' : 'active'">{{ completed ? '✓' : '③' }} AI 设计工作台<small v-if="data?.reopened && !completed">继续设计</small></span><i></i>
      <span :class="{ finished: completed || data?.archiveId }">{{ completed ? '✓' : '④' }} 归档成品库<small v-if="data?.archiveId && !completed">已有归档</small></span>
      <ElTag v-if="completed" type="success" size="small">全部完成</ElTag>
    </div>
    <ElCard shadow="never" class="art-card studio-chat-card" :class="{ 'studio-expanded': expanded }" @keydown.esc="expanded = false">
      <div class="studio-chat-heading"><div class="session-heading"><strong>与 Codex 协作</strong><span v-if="runningCount" role="status">{{ runningCount }} 个会话处理中</span><ElTag v-if="completed" type="success" size="small">任务已完成</ElTag></div><div class="studio-actions">
        <ElButton size="small" @click="sessionsOpen = !sessionsOpen">会话 · {{ sessions.length }}/10</ElButton><ElButton size="small" @click="materialsOpen = !materialsOpen">任务素材 · {{ data?.materials.length || 0 }}</ElButton><ElButton size="small" :loading="loading" @click="refresh">刷新</ElButton>
        <ElButton size="small" :disabled="!data?.archiveId" @click="viewArchive">查看本任务成品</ElButton><ElButton v-if="completed" size="small" type="primary" :disabled="!canReopen" @click="reopenOpen = true">解冻工作台</ElButton><ElButton v-else size="small" :disabled="!canComplete" :title="runningCount ? '请等待或停止所有执行后完成任务' : '至少归档一张图片后可完成'" @click="completeOpen = true">完成任务</ElButton><ElButton size="small" @click="expanded = !expanded">{{ expanded ? '退出展开' : '展开工作台' }}</ElButton>
      </div></div>
      <div v-if="completed" class="session-completed-notice" role="status"><strong>任务已完成 · 所有会话只读</strong><span>可切换查看历史及归档成品。需要继续设计，请点击“解冻工作台”。</span></div>
      <ElAlert v-if="sessionError || preferenceNotice" :title="sessionError || preferenceNotice" type="warning" :closable="false" />
      <ElAlert v-if="sessionPending && !sessionBusy" title="会话操作结果尚未确认，请核实原请求。" type="warning" :closable="false"><ElButton :loading="sessionBusy" @click="retrySession">核实会话操作</ElButton></ElAlert>
      <ElAlert v-if="error || limitError" :title="limitError || error" type="error" :closable="false" />
      <ElAlert v-if="draftNotice && !skillError" :title="draftNotice" type="warning" :closable="false" />
      <ElAlert v-if="pending && !busy" title="上次操作的结果尚未确认。请使用相同请求重试，避免重复提交。" type="warning" :closable="false"><ElButton :loading="busy" :disabled="!task.capabilities.includes('task.design')" @click="retry">核实并重试上次操作</ElButton></ElAlert>
      <div class="studio-workspace"><StudioSessionList v-if="sessionsOpen" :sessions="sessions" :active-id="activeId" :disabled="!canManage" :can-create="canNewConversation" @select="s => selectSession(s.id)" @create="newConversation" @close="sessionsOpen = false" @action="sessionAction" /><section class="studio-conversation">
        <div class="session-current"><div><strong>{{ currentSession?.name || (sessions.length ? '加载会话…' : '暂无会话') }}</strong><small>{{ completed ? '只读会话 · 历史记录与文件保留' : currentSession?.deletionStatus ? currentSession.deletionError || '正在清理会话文件，请稍候' : data?.activeTurnId ? activeTurn?.status === 'collecting' ? '回复已结束 · 正在保存文件' : '执行中 · 切换会话不中断执行' : '独立上下文 · 独立工作文件' }}</small></div><div class="studio-actions"><ElButton size="small" :disabled="!currentSession || !!currentSession.deletionStatus || data?.conversationId !== activeId" @click="recoveryOpen = true">取回文件</ElButton><ElButton v-if="currentSession" text size="small" :disabled="!canManage || !!currentSession.deletionStatus" @click="sessionAction('rename', currentSession)">重命名</ElButton></div></div>
        <StudioTurns v-if="data?.conversationId === activeId" :key="activeId" :scroll-position="scrollPosition" @scroll-position="(position, id) => saveScroll(position, id || undefined)" :turns="data?.turns || []" :transcript="transcript" :conversation-id="data?.conversationId" :selected="selected" :disabled="locked" @failure="fail" @group="toggleGroup" @toggle="toggle" @modify="openAnnotation" />
        <div class="session-archive-bar"><span>{{ completed ? '成品已归入本任务，可通过右上角查看' : selected.length ? `已选当前会话 ${selected.length} 张图片` : '勾选当前会话图片，归档到本任务' }}</span><ElButton size="small" type="primary" :disabled="locked || !!data?.activeTurnId || !selected.length" @click="archiveOpen = true">归档所选图片（{{ selected.length }}）</ElButton></div>
        <div class="studio-composer" @dragover.prevent @drop.prevent="drop" @paste="paste">
          <p v-if="completed" class="studio-completion-note">任务已完成。需要继续修改时，点击右上方“解冻工作台”。</p>
          <p v-if="data && !data.archiveId" class="studio-completion-note">暂无可用归档成品，可能尚未归档或已删除；完成任务前请先归档图片。</p>
          <button class="studio-dropzone" :disabled="locked" :class="{ 'is-dragging': dragging }" @dragover.prevent.stop="dragging = true" @dragleave="dragging = false" @click="input?.click()">{{ uploading ? '正在上传…' : dragging ? '松开即可添加附件' : '拖拽图片或文件到这里，或点击上传' }} <small>仅加入当前会话 · 最多 100 个附件 · 单个最大 500 MB</small></button>
          <div v-if="ordinaryAttachments.length || revisions.length || plainReferences.length" class="composer-files">
            <StudioAttachments :assets="[...ordinaryAttachments, ...plainReferences]" title="本轮附件" compact removable :disabled="locked" @remove="removeAttachment" @failure="fail" />
            <StudioRevisionDraft v-for="revision in revisions" :key="revision.base.id" :revision="revision" :disabled="locked" @edit="openAnnotation(revision.base)" @remove="removeRevision(revision.base.id)" @failure="fail" />
          </div>
          <small v-if="revisionError" class="studio-revision-hint">{{ revisionError }}</small>
          <small v-if="skillError" class="studio-revision-hint" role="alert">{{ skillError }}</small>
          <ElInput v-model="text" type="textarea" :rows="2" resize="none" :disabled="locked" aria-label="设计要求" placeholder="描述设计要求，或继续提出修改意见…" @keydown="handleStudioSendKey($event, send)" />
          <div class="studio-compose-tools"><div class="studio-input-tools"><StudioSkillSelect v-model="skill" :skills="data?.skills || []" :disabled="locked" /></div><div class="polish-send-tools"><ExpandedComposer v-if="!baseline" :key="activeId" v-model="text" :disabled="locked" :session-name="currentSession?.name || '会话'" /><ElButton v-if="data?.activeTurnId" :loading="busy" :disabled="!editable || !!pending || uploading || activeTurn?.status === 'cancelling'" @click="stop">停止</ElButton><ElButton v-else type="primary" :loading="busy" :disabled="!canSend" @click="send">发送</ElButton></div></div>
          <p class="studio-compose-note">发送到：{{ currentSession?.name || '请先新建会话' }} · Enter 发送，Shift + Enter 换行 · 切换会话保留草稿</p>
          <input ref="input" hidden type="file" multiple @change="upload">
        </div>
      </section><StudioMaterials v-if="materialsOpen" :key="activeId" :assets="data?.materials || []" :disabled="locked" :removing="removingMaterials" @close="materialsOpen = false" @add="add" @remove="confirmRemoveMaterial" @remove-selected="confirmRemoveMaterials" @failure="fail" /></div>
    </ElCard>
    <StudioRecoveryDialog v-if="recoveryOpen && activeId && data?.conversationId === activeId" :key="`${task.id}:${activeId}`" :task-id="task.id" :conversation-id="activeId" :readonly="completed || !task.capabilities.includes('task.design') || !!currentSession?.deletionStatus" :busy="!!data?.activeTurnId || uploading" @close="recoveryOpen = false" @saved="refresh" @failure="fail" />
    <StudioAnnotationDialog v-if="editing && data" :key="editingKey" ref="annotationDialog" :picture="editing" :draft-key="editingKey" :submitting="uploading" :error="annotationError" @close="closeAnnotation" @confirm="applyAnnotation" @failure="fail" />
    <ElDialog v-model="archiveOpen" title="归档所选图片" width="min(600px,94vw)" append-to-body><p>归属任务：{{ task.name }} · 来源会话：{{ currentSession?.name }}。将当前会话所选 {{ selected.length }} 张图片归入指定 SKU，保留来源信息。</p><StudioArchiveFields :task="task" /><label for="studio-archive-sku">SKU</label><ElSelect id="studio-archive-sku" v-model="sku" style="width:100%;margin-top:8px" aria-label="归档所属 SKU" placeholder="选择所属 SKU"><ElOption v-for="item in task.skus" :key="item.code" :value="item.code" :label="item.code" /></ElSelect><template #footer><ElButton @click="archiveOpen = false">取消</ElButton><ElButton type="primary" :disabled="locked || !!data?.activeTurnId || !sku || !selected.length" :loading="busy" @click="doArchive">确认归档</ElButton></template></ElDialog>
    <ElDialog v-model="completeOpen" title="确认完成任务" width="min(480px,94vw)" append-to-body><p>完成后本任务所有会话将锁定，已归档成品和对话记录都会保留。</p><p>后续需要修改，可以解冻工作台，继续当前对话。</p><template #footer><ElButton @click="completeOpen = false">继续设计</ElButton><ElButton type="primary" :loading="busy" :disabled="!canComplete" @click="doComplete">确认完成</ElButton></template></ElDialog>
    <ElDialog v-model="reopenOpen" title="解冻工作台" width="min(480px,94vw)" append-to-body><p>解冻后任务回到第③步“AI 设计工作台”，恢复为设计中。</p><p>本任务全部 {{ sessions.length }} 个会话恢复编辑。原会话、上下文、草稿和已归档成品保留；不会自动开始生成，也不需要重新提交图需或审核。</p><template #footer><ElButton @click="reopenOpen = false">取消</ElButton><ElButton type="primary" :loading="busy" :disabled="!canReopen" @click="doReopen">确认解冻</ElButton></template></ElDialog>
    <OverseasArchiveDetail v-if="archiveId" :id="archiveId" :api="archivesApi" @close="closeArchive" @source="viewSource" @failure="archiveFailure" />
  </section>
</template>
<script setup lang="ts">
import { previewApi, sampleText } from './preview-api'
import ExpandedComposer from './ExpandedComposer.vue'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createArchivesApi } from '@/api/overseas/archives'
import { IdentityError } from '@/api/identity/request'
import OverseasArchiveDetail from '@/views/overseas/OverseasArchiveDetail.vue'
import type { TaskDetail } from '@/api/overseas/tasks'
import StudioTurns from '@/views/overseas/studio/StudioTurns.vue'
import StudioRecoveryDialog from '@/views/overseas/studio/StudioRecoveryDialog.vue'
import StudioArchiveFields from '@/views/overseas/studio/StudioArchiveFields.vue'
import { handleStudioSendKey } from '@/views/overseas/studio/studio-send-key'
import type { Asset, StudioPicture } from '@/api/overseas/studio'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { PreparedAnnotation } from '@/views/hengxin/components/annotation/AnnotationEditor.vue'
import { forgetAnnotationDraft } from '@/views/hengxin/components/annotation/annotation-drafts'
import StudioAttachments from '@/views/overseas/studio/StudioAttachments.vue'
import StudioRevisionDraft from '@/views/overseas/studio/StudioRevisionDraft.vue'
import StudioAnnotationDialog from '@/views/overseas/studio/StudioAnnotationDialog.vue'
import StudioMaterials from '@/views/overseas/studio/StudioMaterials.vue'
import StudioSkillSelect from '@/views/overseas/studio/StudioSkillSelect.vue'
import { useStudioSessions } from '@/views/overseas/studio/use-studio-sessions'
import StudioSessionList from '@/views/overseas/studio/StudioSessionList.vue'
import type { SessionView } from '@/views/overseas/studio/studio-session-state'
import '@/views/overseas/studio/studio-sessions.css'
import '@/views/overseas/studio/studio.css'
const props = defineProps<{ actorId: string; task: TaskDetail; baseline?: boolean }>()
const emit = defineEmits<{ failure: [reason: unknown]; changed: [] }>()
const { data, text, skill, attachments, references, revisions, revisionError, skillError, draftKey, confirmRevision, removeRevision, selected, transcript, error, limitError, busy, uploading, loading, pending, editable, activeTurn, locked, canSend, canNewConversation, canComplete, canReopen, refresh, send, newConversation, retry, archive, complete, reopen, stop, add, receive, toggle, toggleGroup, fail, removeMaterial, removeMaterials, removingMaterials, materialNotice, draftNotice, sessions, activeId, currentSession, runningCount, canManage, sessionBusy, sessionError, sessionPending, retrySession, preferenceNotice, selectSession, renameConversation, deleteConversation, saveScroll, scrollPosition } = useStudioSessions(() => props.task, reason => emit('failure', reason), () => emit('changed'), previewApi, props.actorId)
const seeded = new Set<string>()
watch(data, value => { if (value?.conversationId && !seeded.has(value.conversationId)) { seeded.add(value.conversationId); text.value = sampleText } })
const completed = computed(() => data.value?.completed ?? props.task.status === 'completed')
watch(materialNotice, value => { if (value) ElMessage.info(value) })
async function confirmRemoveMaterial(asset: Asset) {
  if (locked.value) return
  try { await ElMessageBox.confirm('仅从任务素材列表移除，不影响历史消息和已发送文件。', `移除 ${asset.name}`, { confirmButtonText: '移除', cancelButtonText: '取消', type: 'warning' }) } catch { return }
  if (await removeMaterial(asset.id)) ElMessage.success('已从列表移除，历史消息和待发送附件保留')
}
async function confirmRemoveMaterials(ids: string[]) {
  if (locked.value || !ids.length) return
  try { await ElMessageBox.confirm(`将从任务素材列表移除这 ${ids.length} 项，历史消息、已发送文件和输入区已引用的附件保留。`, '移除所选素材', { confirmButtonText: '确认移除', cancelButtonText: '取消', type: 'warning' }) } catch { return }
  const result = await removeMaterials(ids)
  if (!result) return
  if (result.remaining) ElMessage.warning(`已移除 ${result.removed} 项，${result.remaining} 项未完成，请检查后重试`)
  else ElMessage.success(`已从列表移除 ${result.removed} 项，历史消息和待发送附件保留`)
}
const editing = ref<StudioPicture>(), editingKey = ref(''), annotationDialog = ref<InstanceType<typeof StudioAnnotationDialog>>(), annotationError = ref('')
const ordinaryAttachments = computed(() => attachments.value.filter(a => !revisions.value.some(r => r.annotation?.id === a.id)))
const plainReferences = computed(() => references.value.filter(p => !revisions.value.some(r => r.base.id === p.id)))
function removeAttachment(id: string) { if (!locked.value) { attachments.value = attachments.value.filter(a => a.id !== id); references.value = references.value.filter(p => p.id !== id) } }
function openAnnotation(picture: StudioPicture) { if (!locked.value) { annotationError.value = ''; editingKey.value = draftKey(picture); editing.value = picture } }
function closeAnnotation() { if (editing.value && !revisions.value.some(r => r.base.id === editing.value!.id)) forgetAnnotationDraft(editingKey.value); editing.value = undefined; annotationError.value = '' }
async function applyAnnotation(value: PreparedAnnotation) {
  if (!editing.value) return
  annotationError.value = ''
  if (await confirmRevision(editing.value, value)) { annotationDialog.value?.commit(); editing.value = undefined }
  else annotationError.value = error.value || '标注未保存，请重试'
}
watch(data, value => { if (!value) closeAnnotation() })
watch(activeId, () => { recoveryOpen.value = false; closeAnnotation(); archiveOpen.value = false; sku.value = '' })
const recoveryOpen = ref(false)
const sessionsOpen = ref(true), expanded = ref(false), materialsOpen = ref(true), dragging = ref(false), input = ref<HTMLInputElement>(), archiveOpen = ref(false), completeOpen = ref(false), reopenOpen = ref(false), sku = ref('')
watch(() => data.value?.completed, value => { if (value) completeOpen.value = false; else if (value === false) reopenOpen.value = false })
const workspace = ref<HTMLElement>(), workspaceHeight = ref('calc(100dvh - 230px)')
let resizeObserver: ResizeObserver | undefined
function fitWorkspace() {
  if (expanded.value) return
  const card = workspace.value?.querySelector('.studio-chat-card')
  if (card) workspaceHeight.value = `${Math.max(300, window.innerHeight - card.getBoundingClientRect().top - 14)}px`
}
onMounted(() => { resizeObserver = new ResizeObserver(fitWorkspace); if (workspace.value?.parentElement) resizeObserver.observe(workspace.value.parentElement); window.addEventListener('resize', fitWorkspace); fitWorkspace() })
watch(expanded, () => { void nextTick(fitWorkspace) })
const route = useRoute(), router = useRouter(), archivesApi = createArchivesApi()
const archiveId = computed(() => typeof route.query.archive === 'string' ? route.query.archive : '')
function viewArchive() { if (data.value?.archiveId) { expanded.value = false; void router.push({ query: { ...route.query, archive: data.value.archiveId } }) } }
function closeArchive() { const query = { ...route.query }; delete query.archive; void router.replace({ query }) }
function viewSource(id: string) { if (id === props.task.id) closeArchive(); else void router.push(`/overseas/tasks/${encodeURIComponent(id)}`) }
function archiveFailure(reason: unknown) { if (reason instanceof IdentityError && [401, 403].includes(reason.status)) emit('failure', reason) }
function drop(event: DragEvent) { dragging.value = false; const id = event.dataTransfer?.getData('application/x-studio-material'); if (id) add([id]); else void receive(Array.from(event.dataTransfer?.files || [])) }
function paste(event: ClipboardEvent) { const files = Array.from(event.clipboardData?.files || []); if (files.length) { event.preventDefault(); void receive(files) } }
function upload(event: Event) { const target = event.target as HTMLInputElement; void receive(Array.from(target.files || [])); target.value = '' }
async function doArchive() { if (await archive(sku.value)) archiveOpen.value = false }
async function sessionAction(command: string, session: SessionView) {
  if (!canManage.value) return
  try {
    if (command === 'rename') {
      const { value } = await ElMessageBox.prompt('名称只用于区分会话，不影响上下文。', '重命名会话', { inputValue: session.name, inputValidator: v => !!v?.trim() && v.trim().length <= 30 || '请输入 1–30 个字', confirmButtonText: '保存', cancelButtonText: '取消' })
      await renameConversation(session, value)
    } else {
      if (session.activeTurnId || session.deletionStatus === 'deleting') return
      await ElMessageBox.confirm(`删除「${session.name}」及其历史、工作文件和未归档图片，已归档成品保留。清理完成后释放会话名额。`, '删除会话', { type: 'warning', confirmButtonText: session.deletionStatus === 'delete_failed' ? '重试删除' : '确认删除', cancelButtonText: '取消' })
      await deleteConversation(session)
    }
  } catch { /* User cancelled the confirmation. */ }
}
async function doComplete() { const success = await complete(); completeOpen.value = false; if (success) ElMessage.success('任务已完成，归档成品和对话记录已保留') }
async function doReopen() { const success = await reopen(); reopenOpen.value = false; if (success) ElMessage.success('已解冻，继续使用原来的对话') }
onUnmounted(() => { closeAnnotation(); resizeObserver?.disconnect(); window.removeEventListener('resize', fitWorkspace) })
</script>
