<template>
  <ElDrawer v-model="open" :title="task?.name || '任务详情'" size="82%" class="hx-detail" destroy-on-close :before-close="closeDrawer">
    <div v-loading="loading">
      <ElAlert v-if="error" :title="error" type="error" show-icon :closable="false"><ElButton text @click="load()">重试加载</ElButton></ElAlert>
      <ElEmpty v-if="!task && !loading" description="任务不可用，请重试或返回任务列表" />
      <template v-if="task && data">
        <div class="hx-detail-toolbar"><div><ElTag>{{ labels[task.mode] }}</ElTag><span class="hx-muted">{{ task.id }} · {{ formatTime(task.time) }}</span></div></div>
        <div class="hx-filter"><ElButton :disabled="!editable" @click="edit(null)">整套修改</ElButton><ElButton :disabled="!complete || busy" :loading="downloading" @click="download">{{ isMockMode ? '下载整套示例' : '下载整套' }}</ElButton><ElButton type="primary" :disabled="!complete || busy" :loading="archiving" @click="archive">{{ task.archived ? '再次归档当前整套' : '归档到成品库' }}</ElButton></div>
        <p class="hx-footnote">整套下载和归档使用每个位置的当前版本；历史版本选择仅用于查看和单张下载。相同版本再次归档会返回已有成品。</p>
        <ElAlert v-if="isMockMode" title="交互演示：以下为示例图片，尚未调用真实 Skill。修改操作演示版本与状态变化。" type="info" show-icon :closable="false" />
        <ElAlert v-if="actionError" :title="actionError" class="hx-gap" type="error" show-icon :closable="false" />
        <div class="hx-gap"><ElTag :type="failed ? 'danger' : 'info'">{{ task.state }}</ElTag><ElProgress v-if="task.progress !== null" :percentage="task.progress" :status="failed ? 'exception' : undefined" /><p v-if="task.error" class="hx-muted">{{ task.error }}</p>
          <p v-if="failed" class="hx-muted">执行未全部成功，已有成功结果和旧版本保留。重试沿用上一失败轮次的范围与意见。</p>
          <ElButton v-if="failed" type="primary" :loading="submitting" :disabled="busy || !lastFailed" @click="retry">重试失败范围</ElButton>
        </div>
        <div class="hx-result-grid"><ResultCard v-for="slot in data.slots" :key="`${task.id}-${slot.slot}`" :slot="slot" :state="task.state" :editable="editable" @edit="edit" /></div>
        <ElCollapse class="hx-gap"><ElCollapseItem :title="`执行与修改记录（${data.rounds.length}）`"><ElEmpty v-if="!data.rounds.length" description="暂无轮次记录" :image-size="60" /><div v-for="round in data.rounds" :key="round.id" class="hx-log"><strong>{{ round.target === null ? '整套' : `第 ${round.target + 1} 张` }} · {{ round.state }}</strong><p>{{ round.note || '首次生成' }}</p><small>{{ formatTime(round.createdAt) }} · {{ round.operatorId }}</small><p v-if="round.error">{{ round.error }}</p></div></ElCollapseItem></ElCollapse>
      </template>
    </div>
  </ElDrawer>
  <ElDialog v-model="feedbackOpen" :title="target === null ? '整套修改意见' : `修改第 ${target + 1} 张图片`" width="520px" append-to-body :close-on-click-modal="!submitting" :close-on-press-escape="!submitting" :show-close="!submitting" :before-close="closeFeedback">
    <p class="hx-muted">{{ target === null ? '本轮意见应用于整套图片。' : '仅重新生成这个位置的图片，其余图片保留。' }}</p><ElInput v-model="feedback" :disabled="submitting" type="textarea" :rows="5" placeholder="填写本轮修改意见" maxlength="1000" show-word-limit />
    <ElAlert v-if="actionError" :title="actionError" type="error" :closable="false" />
    <template #footer><ElButton :disabled="submitting" @click="feedbackOpen = false">取消</ElButton><ElButton type="primary" :disabled="!feedback.trim() || feedback.trim().length > 1000 || submitting" :loading="submitting" @click="applyFeedback">提交修改</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, ref, toRef, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { isMockMode } from '@/api/hengxin/client'
import { submitRevision } from '@/api/revisions'
import { archiveTask } from '@/api/archives'
import type { RevisionInput } from '@/types/hengxin'
import { labels } from '../model'
import { downloadSet } from '../download'
import { useTaskDetail } from './use-task-detail'
import ResultCard from './ResultCard.vue'
const open = defineModel<boolean>({ default: false })
const props = defineProps<{ taskId: string; active?: boolean }>()
const emit = defineEmits<{ changed: [] }>()
const visible = computed(() => open.value && props.active !== false)
const { data, task, complete, loading, error, load } = useTaskDetail(toRef(props, 'taskId'), visible)
const feedbackOpen = ref(false), target = ref<number | null>(null), feedback = ref(''), actionError = ref('')
const submitting = ref(false), archiving = ref(false), downloading = ref(false)
const busy = computed(() => submitting.value || archiving.value || downloading.value)
const failed = computed(() => !!task.value && ['失败', '部分失败'].includes(task.value.state))
const editable = computed(() => task.value?.state === '待查看' && !busy.value && !error.value)
const lastFailed = computed(() => data.value?.rounds.find(r => r.id === task.value?.currentRoundId && ['失败', '部分失败'].includes(r.state)))
watch(() => props.taskId, () => { feedbackOpen.value = false; feedback.value = ''; actionError.value = '' })
watch(visible, shown => { if (!shown && !submitting.value) feedbackOpen.value = false })
function formatTime(value: string) { return new Date(value).toLocaleString('zh-CN', { hour12: false }) }
function closeDrawer(done: () => void) { if (!busy.value) { feedbackOpen.value = false; done() } }
function closeFeedback(done: () => void) { if (!submitting.value) done() }
function edit(slot: number | null) { if (!editable.value) return; target.value = slot; feedback.value = ''; actionError.value = ''; feedbackOpen.value = true }
async function revise(input: RevisionInput) {
  if (busy.value) return
  submitting.value = true; actionError.value = ''
  try {
    const accepted = await submitRevision(input)
    if (props.taskId !== input.taskId) return
    if (task.value?.id === input.taskId) { task.value.state = accepted.state; task.value.progress = null; task.value.currentRoundId = accepted.roundId }
    feedbackOpen.value = false; ElMessage.success('修改请求已受理，正在排队'); emit('changed')
    await load(true)
  } catch (reason) { if (props.taskId === input.taskId) actionError.value = reason instanceof Error ? reason.message : '提交失败，请重试' }
  finally { submitting.value = false }
}
function applyFeedback() {
  if (!feedback.value.trim() || feedback.value.trim().length > 1000 || !task.value) return
  void revise({ taskId: task.value.id, target: target.value, note: feedback.value.trim() })
}
function retry() {
  if (!task.value || !lastFailed.value) return
  void revise({ taskId: task.value.id, target: lastFailed.value.target, note: lastFailed.value.note, retry: true })
}
async function archive() {
  if (!task.value || !complete.value || busy.value) return
  const id = task.value.id
  archiving.value = true; actionError.value = ''
  try { const result = await archiveTask(id); if (props.taskId !== id) return; ElMessage.success(`已归档：${result.name}（相同版本会返回已有成品）`); emit('changed'); await load(true) }
  catch (reason) { if (props.taskId === id) actionError.value = reason instanceof Error ? reason.message : '归档失败，请重试' }
  finally { archiving.value = false }
}
async function download() {
  if (!data.value || !task.value || !complete.value || busy.value) return
  downloading.value = true
  const pictures = data.value.slots.flatMap(slot => slot.versions.filter(v => v.id === slot.currentVersionId))
  try { await downloadSet(pictures, task.value.name) } finally { downloading.value = false }
}
</script>
