<template>
  <ElDrawer :model-value="open" :title="task?.name || '任务详情'" size="82%" class="hx-detail" destroy-on-close :before-close="closeDrawer">
    <div v-loading="loading">
      <ElAlert v-if="error" :title="error" type="error" show-icon :closable="false"><ElButton text @click="load()">重试加载</ElButton></ElAlert>
      <ElEmpty v-if="!task && !loading" description="任务不可用，请重试或返回任务列表" />
      <template v-if="task && data">
        <div class="hx-detail-toolbar"><div><ElTag>{{ labels[task.mode] }}</ElTag><span class="hx-muted">{{ task.id }} · {{ formatTime(task.time) }}</span></div></div>
        <div class="hx-filter"><ElButton :disabled="!editable" @click="edit(null)">整套修改</ElButton><ElButton :disabled="!complete || busy" :loading="downloading" @click="download">{{ isMockMode ? '下载整套示例' : '下载整套' }}</ElButton><ElButton type="primary" :disabled="!complete || busy" :loading="archiving" @click="archive">{{ task.archived ? '再次归档当前整套' : '归档到成品库' }}</ElButton></div>
        <p class="hx-footnote">单张修改以正在查看的版本为基础；整套修改、下载和归档使用各位置当前版本。相同版本再次归档会返回已有成品。</p>
        <ElAlert v-if="archivedResult" :title="`已归档：${archivedResult.name}`" type="success" :closable="false" show-icon class="hx-gap"><ElButton text type="primary" :disabled="busy" @click="viewArchive">查看该成品</ElButton></ElAlert>
        <ElAlert v-if="isMockMode" title="交互演示：以下为示例图片，尚未调用真实 Skill。修改操作演示版本与状态变化。" type="info" show-icon :closable="false" />
        <ElAlert v-if="fixtureNotice(task)" :title="fixtureNotice(task)" type="warning" show-icon :closable="false" />
        <ElAlert v-if="data.executionControl.blockedReason" :title="data.executionControl.blockedReason" type="info" show-icon :closable="false" class="hx-gap" />
        <ElAlert v-if="revision.session.value.uncertain" title="上次修改的受理结果尚未确认，当前意见已保留。" type="warning" :closable="false" class="hx-gap"><ElButton :loading="submitting" @click="confirmPrevious">确认上次提交</ElButton></ElAlert>
        <ElAlert v-if="revision.session.value.accepted && !revision.session.value.settled" title="修改请求已受理，正在获取最新执行状态。" type="info" :closable="false" class="hx-gap" />
        <ElAlert v-if="actionError" :title="actionError" class="hx-gap" type="error" show-icon :closable="false" />
        <TaskTemplate :key="`template-${task.id}`" :task="task" />
        <TaskSources :key="`sources-${task.id}`" :sources="task.sources" />
        <ExecutionProgress :key="task.id" :task-id="task.id" :current-round-id="task.currentRoundId" :rounds="data.rounds" :active="visible" @detailed-failure="detailedFailure = $event" />
        <div class="hx-gap"><ElTag :type="failed ? 'danger' : 'info'">{{ task.state }}</ElTag><ElProgress v-if="task.progress !== null" :percentage="task.progress" :status="failed ? 'exception' : undefined" /><p v-if="task.error && !detailedFailure" class="hx-muted">{{ task.error }}</p>
          <p v-if="failed" class="hx-muted">执行未全部成功，已有成功结果和旧版本保留。重试沿用上一失败轮次的范围与意见。</p>
          <ElButton v-if="failed" type="primary" :loading="submitting" :disabled="!actions.canRetry || !lastFailed" @click="retry">重试失败范围</ElButton>
        </div>
        <div class="hx-result-grid"><ResultCard v-for="slot in data.slots" :key="`${task.id}-${slot.slot}`" :slot="slot" :state="task.state" :editable="editable" @edit="edit" /></div>
        <ElCollapse class="hx-gap"><ElCollapseItem :title="`执行与修改记录（${data.rounds.length}）`"><ElEmpty v-if="!data.rounds.length" description="暂无轮次记录" :image-size="60" /><div v-for="round in data.rounds" :key="round.id" class="hx-log"><strong>{{ round.target === null ? '整套' : `第 ${round.target + 1} 张` }} · {{ round.state }}</strong><p v-if="round.baseVersion">基于 V{{ round.baseVersion }} 修改</p><p>{{ round.note || '首次生成' }}</p><ElImage v-if="round.annotation" :src="round.annotation.url" :alt="`问题截图：${round.annotation.name}`" :preview-src-list="[round.annotation.url]" fit="contain" preview-teleported style="width: 80px; height: 80px" /><small>{{ formatTime(round.createdAt) }} · {{ round.operatorId }}</small><p v-if="round.error">{{ round.error }}</p></div></ElCollapseItem></ElCollapse>
      </template>
    </div>
  </ElDrawer>
  <ElDialog v-model="feedbackOpen" :title="target === null ? '整套修改意见' : `修改第 ${target + 1} 张图片`" width="560px" top="6vh" append-to-body destroy-on-close :close-on-click-modal="!submitting" :close-on-press-escape="!submitting" :show-close="!submitting" :before-close="closeFeedback">
    <div class="revision-fields">
    <p class="hx-muted">{{ target === null ? '本轮意见应用于整套图片。' : '仅修改这个位置的图片，其余图片保留。' }}</p>
    <template v-if="target !== null">
      <div class="revision-base"><ElImage v-if="base" :src="base.url" :alt="`修改基础 V${base.version}`" :preview-src-list="[base.url]" fit="contain" preview-teleported /><strong>{{ base ? `本次基于 V${base.version} 修改` : '尚无成品，本次基于原底图修改' }}</strong></div>
      <p id="revision-annotation-label">问题截图（可选，1 张）</p>
      <ImageUpload v-if="feedbackOpen && task" :key="`${identity()}-${task.id}-${revision.draftKey.value}`" v-model="annotations" :mode="task.mode" :disabled="submitting || revision.session.value.uncertain" :max-count="1" sortable hide-examples :button-label="annotations.length ? '替换问题截图' : '上传问题截图'" aria-labelledby="revision-annotation-label" @blocked="annotationBlocked = $event" />
      <p class="hx-footnote">可上传圈出问题的截图。圈线、箭头仅用于定位，不会作为成品内容。</p>
    </template>
    <label for="revision-note">修改意见</label><ElInput id="revision-note" v-model="feedback" :disabled="submitting" type="textarea" :rows="4" :placeholder="target === null ? '例如：整套图片的屏幕亮度调高，其他内容保持不变' : '例如：请将截图红圈中的镜头向右调整，其余内容保持不变'" maxlength="1000" show-word-limit />
    <ElAlert v-if="actionError" :title="actionError" type="error" :closable="false" />
    <ElButton v-if="revision.session.value.uncertain" :loading="submitting" @click="confirmPrevious">确认上次提交（保留当前意见）</ElButton>
    </div>
    <template #footer><ElButton :disabled="submitting" @click="feedbackOpen = false">取消</ElButton><ElButton type="primary" :disabled="!feedback.trim() || feedback.trim().length > 1000 || !editable || (target !== null && annotationBlocked)" :loading="submitting" @click="applyFeedback">提交修改</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, toRef, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { getService, isMockMode } from '@/api/hengxin/client'
import { useUserStore } from '@/store/modules/user'
import { useRevisionSession } from '../revision-session'
import { archiveTask } from '@/api/archives'
import { submitArchive } from '../archive-requests'
import type { ResultVersion, RevisionInput } from '@/types/hengxin'
import { labels } from '../model'
import { downloadSet } from '../download'
import { useTaskDetail } from './use-task-detail'
import { fixtureNotice, taskActions } from '../task-state'
import ResultCard from './ResultCard.vue'
import ImageUpload from './ImageUpload.vue'
import TaskSources from './TaskSources.vue'
import TaskTemplate from './TaskTemplate.vue'
import ExecutionProgress from './ExecutionProgress.vue'
const detailedFailure = ref(false)
const router = useRouter()
const archivedResult = ref<{ id: string; name: string }>()
const open = defineModel<boolean>({ default: false })
const props = defineProps<{ taskId: string; active?: boolean }>()
const emit = defineEmits<{ changed: [] }>()
const visible = computed(() => open.value && props.active !== false)
const { data, task, complete, loading, error, load } = useTaskDetail(toRef(props, 'taskId'), visible)
const user = useUserStore()
const identity = () => user.isLogin && user.info.userId != null ? String(user.info.userId) : undefined
const revision = useRevisionSession(identity, () => props.taskId, async (input, key) => {
  const owner = identity(), service = await getService()
  if (!owner || owner !== identity()) throw new Error('登录身份已变化，请重新确认提交')
  return service.revise(input, key)
})
const { target, base, annotations, note: feedback } = revision
const annotationBlocked = ref(false)
const feedbackOpen = ref(false), archiving = ref(false), downloading = ref(false)
const actionError = computed({ get: () => revision.session.value.error, set: value => { revision.session.value.error = value } })
const submitting = computed(() => revision.session.value.pending)
let alive = true
onBeforeUnmount(() => { alive = false })
watch(data, value => { if (value) revision.observe(value) })
const busy = computed(() => submitting.value || archiving.value || downloading.value)
const failed = computed(() => !!task.value && ['失败', '部分失败'].includes(task.value.state))
const actions = computed(() => taskActions(data.value, busy.value || revision.blocked.value, error.value))
const editable = computed(() => actions.value.canRevise)
const lastFailed = computed(() => data.value?.rounds.find(r => r.id === task.value?.currentRoundId && ['失败', '部分失败'].includes(r.state)))
watch([() => props.taskId, identity], () => { feedbackOpen.value = false; archivedResult.value = undefined })
watch(visible, shown => { if (!shown && !submitting.value) feedbackOpen.value = false })
function formatTime(value: string) { return new Date(value).toLocaleString('zh-CN', { hour12: false }) }
function closeDrawer(done: () => void) { if (!busy.value) { feedbackOpen.value = false; open.value = false; done() } }
function closeFeedback(done: () => void) { if (!submitting.value) done() }
function edit(slot: number | null, version?: ResultVersion) {
  if (!editable.value || !revision.begin()) return
  target.value = slot; base.value = version ?? null; annotationBlocked.value = false; feedbackOpen.value = true
}
async function revise(input?: RevisionInput) {
  if (input && (input.retry ? !actions.value.canRetry : !actions.value.canRevise)) return
  const owner = identity(), id = props.taskId
  try {
    const accepted = await (input ? revision.submit(input) : revision.resolvePrevious())
    if (!alive || props.taskId !== id || identity() !== owner) return
    if (task.value?.id === id) { task.value.state = accepted.state; task.value.progress = null; task.value.currentRoundId = accepted.roundId }
    feedbackOpen.value = false; ElMessage.success('修改请求已受理，正在排队'); emit('changed')
    await load(true)
  } catch { /* 提交错误保留在原身份、原任务；详情错误由 load 单独显示。 */ }
}
function confirmPrevious() { if (!submitting.value) void revise() }
function applyFeedback() {
  if (!feedback.value.trim() || feedback.value.trim().length > 1000 || !task.value || (target.value !== null && annotationBlocked.value)) return
  void revise({ taskId: task.value.id, target: target.value, note: feedback.value.trim(),
    ...(target.value !== null ? { baseVersionId: base.value?.id ?? null, annotationFileId: annotations.value[0]?.fileId ?? null } : {}) })
}
function retry() {
  if (!task.value || !lastFailed.value || !actions.value.canRetry || !revision.begin()) return
  void revise({ taskId: task.value.id, target: lastFailed.value.target, note: lastFailed.value.note,
    retry: true, sourceRoundId: lastFailed.value.id })
}
async function archive() {
  if (!task.value || !data.value || !complete.value || busy.value) return
  const id = task.value.id, owner = identity()
  if (!owner) return
  const versionIds = data.value.slots.flatMap(slot => slot.currentVersionId ? [slot.currentVersionId] : [])
  archiving.value = true; actionError.value = ''
  try { const result = await submitArchive(owner, id, versionIds, archiveTask); if (!alive || props.taskId !== id || identity() !== owner) return; archivedResult.value = { id: result.id, name: result.name }; ElMessage.success(`已归档：${result.name}（相同版本会返回已有成品）`); emit('changed'); await load(true) }
  catch (reason) { if (props.taskId === id) actionError.value = reason instanceof Error ? reason.message : '归档失败，请重试' }
  finally { archiving.value = false }
}
function viewArchive() {
  if (archivedResult.value && !busy.value) void router.push({ path: '/archive/index', query: { archive: archivedResult.value.id } })
}
async function download() {
  if (!data.value || !task.value || !complete.value || busy.value) return
  downloading.value = true
  const pictures = data.value.slots.flatMap(slot => slot.versions.filter(v => v.id === slot.currentVersionId))
  try { await downloadSet(pictures, task.value.name) } finally { downloading.value = false }
}
</script>
<style scoped>
.revision-fields { max-height: 66vh; overflow-y: auto; padding-right: 8px; }
.revision-base { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.revision-base .el-image { width: 72px; height: 72px; flex-shrink: 0; }
.revision-fields label { display: block; margin: 12px 0 8px; }
</style>
