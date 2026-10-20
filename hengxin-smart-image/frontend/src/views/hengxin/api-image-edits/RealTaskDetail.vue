<template>
  <ElDrawer v-model="open" :title="task?.name || '换图详情'" size="min(1040px, 96vw)" destroy-on-close>
    <ElAlert v-if="error" :title="error" type="error" :closable="false"><ElButton @click="$emit('refresh')">重新加载</ElButton></ElAlert>
    <ElSkeleton v-else-if="loading && !task" :rows="8" animated />
    <div v-if="task" class="detail-content">
      <ElAlert v-if="actionError || downloadError" :title="actionError || downloadError" type="error" :closable="false" />
      <ElAlert v-if="task.deletionState && task.deletionState !== 'idle'" :title="task.deletionState === 'deleting' ? '正在永久删除任务及关联资料' : '删除未完成，请返回列表重试删除'" type="warning" :closable="false" />
      <div class="hx-detail-toolbar hx-gap"><div><ElTag :type="task.status === 'succeeded' ? 'success' : failed && !isTaskActive(task) ? 'info' : 'primary'">{{ taskLabels[task.status] }}</ElTag><span class="hx-muted">{{ task.id }}</span></div><div class="detail-actions">
        <ElButton type="primary" :loading="packing" :disabled="!canZip || packing" @click="downloadZip">{{ packing ? '打包中…' : '下载整套 ZIP' }}</ElButton>
        <ElButton :loading="loading" @click="$emit('refresh')">刷新详情</ElButton>
        <ElButton v-if="retryPending || (failed > 0 && !isTaskActive(task))" type="primary" :loading="busy" :disabled="deleting || busy || packing || hasItemOperation || (!retryPending && channelBlocked)" @click="$emit('retry', task.id)">{{ failed ? `重试未完成的 ${failed} 张` : '重试' }}</ElButton>
      </div></div>
      <ElCard class="art-card" shadow="never">
        <div class="hx-row"><strong>{{ progressText }}</strong></div>
        <ElProgress class="hx-gap" :percentage="task.items.length ? Math.round(success / task.items.length * 100) : 0" :stroke-width="7" :show-text="false" />
        <p class="hx-footnote">操作人：{{ task.operator || '未记录' }} · {{ friendlyTime(task.created) }}</p>
      </ElCard>
      <SharedMaterial :picture="task.material" />
      <div class="result-grid hx-gap">
        <ElCard v-for="item in task.items" :key="item.id" class="art-card" shadow="never">
          <div class="hx-row"><strong>原图 {{ item.position }}</strong><ElTag :type="item.state === 'succeeded' ? 'success' : item.state === 'failed' ? 'info' : item.state === 'retry_wait' ? 'warning' : 'info'" size="small">{{ itemStatusText(item) }}</ElTag><CliActivityTag :state="item.cliActivity" /></div>
          <ElButton text type="primary" @click="comparisonId = item.id; comparisonOpen = true">查看原图 / 对照成品</ElButton>
          <div class="result-picture hx-gap"><ApiResultPicture :item="item" :results="results" /></div>
          <ItemRetryStatus :task-id="task.id" :item="item" :user="user" :locked="deleting || packing || busy" @accepted="emit('refresh')" />
          <div class="result-footer"><span>{{ item.result ? `当前 V${item.currentVersion} · 点击放大` : item.source?.name || '原图未记录' }}</span><ElButton v-if="item.result" text type="primary" :loading="downloading === item.result.fileId" :disabled="!!downloading" @click="download(item.result)">下载图片</ElButton></div>
          <p v-if="item.revision" class="hx-footnote">{{ operationLabel(item.revision.kind) }} · {{ item.revision.operator }} · 基于 V{{ item.revision.baseVersion }}<span v-if="item.state !== 'succeeded'"> · 旧结果保留</span></p>
          <div class="card-actions">
            <ElButton v-if="item.result" size="small" :disabled="!canRevise(item, false)" @click="revisionId = item.id; revisionOpen = true">{{ pendingRevision(item, false) ? '确认原修改请求' : '修改图片' }}</ElButton>
            <ElButton v-if="item.result" size="small" :loading="command(item).state.busy && pendingRevision(item, true)" :disabled="!canRevise(item, true)" @click="repairText(item)">{{ pendingRevision(item, true) ? '确认原修复请求' : '修复文案' }}</ElButton>
            <ElButton v-if="item.result" text type="primary" @click="versionId = item.id; versionOpen = true">历史版本 · {{ item.versions.length }}</ElButton>
            <ElButton v-if="item.state === 'failed' || command(item).state.pending?.command.kind === 'retry'" size="small" type="primary" :loading="command(item).state.busy" :disabled="!canRetry(item)" @click="retryItem(item)">重试这张</ElButton>
          </div>
          <p v-if="command(item).state.error" class="item-error">{{ command(item).state.error }}</p>
        </ElCard>
      </div>
      <ElCollapse v-model="expandedSections" class="hx-gap"><ElCollapseItem title="本次输入与提示词" name="input"><p class="prompt-text">{{ task.prompt }}</p><div v-if="expandedSections.includes('input')" class="input-grid"><div v-for="(picture, index) in inputs" :key="index"><PicturePreview v-if="picture?.url" :picture="picture" title="本次输入" /><p v-else>图片未记录</p><p>{{ index === inputs.length - 1 ? '共用素材' : `原图 ${index + 1}` }}</p></div></div></ElCollapseItem></ElCollapse>
    </div>
    <SourceComparison v-if="comparison" v-model="comparisonOpen" :position="comparison.position" :source="comparison.source" :result="comparison.result" :version="comparison.currentVersion" />
    <RealRevisionDialog v-if="task && revisionId" v-model="revisionOpen" :task="task" :item-id="revisionId" :blocked="packing || busy || deleting" @accepted="emit('refresh')" />
    <RealVersionDialog v-if="task && versionId" v-model="versionOpen" :task="task" :item-id="versionId" :locked="packing || busy || deleting" @accepted="emit('refresh')" />
    <template #footer><ElButton @click="open = false">返回换图记录</ElButton></template>
  </ElDrawer>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { apiImages } from '@/api/api-image-edits'
import { taskLabels, operationLabel, isTaskActive, type ApiPicture, type ApiTask, type ApiItem, type ApiChannel } from '@/types/api-image-edits'
import ItemRetryStatus from './ItemRetryStatus.vue'
import { taskProgressText, itemStatusText } from './retry-status'
import CliActivityTag from './CliActivityTag.vue'
import PicturePreview from '../components/PicturePreview.vue'
import SharedMaterial from './SharedMaterial.vue'
import SourceComparison from './SourceComparison.vue'
import ApiResultPicture from './ApiResultPicture.vue'
import RealRevisionDialog from './RealRevisionDialog.vue'
import RealVersionDialog from './RealVersionDialog.vue'
import { useUserStore } from '@/store/modules/user'
import { itemCommand, friendlyTime, saveBlob } from './item-command'
import { identity } from '@/api/hengxin/identity'
const open = defineModel<boolean>({ required: true })
const props = defineProps<{ task?: ApiTask; loading: boolean; error: string; actionError: string; busy: boolean; retryPending: boolean; channelBlocked: boolean; channel?: ApiChannel }>()
const emit = defineEmits<{ refresh: []; retry: [id: string] }>()
const success = computed(() => props.task?.items.filter(i => i.state === 'succeeded').length || 0), failed = computed(() => props.task?.items.filter(i => i.state === 'failed').length || 0)
const results = computed(() => props.task?.items.flatMap(i => i.result ? [i.result] : []) || [])
const inputs = computed(() => props.task ? [...props.task.items.map(i => i.source), props.task.material] : [])
const progressText = computed(() => props.task ? taskProgressText(props.task, props.channel) : '')
const expandedSections = ref<string[]>([])
const downloading = ref(''), downloadError = ref(''), packing = ref(false)
const revisionId = ref(''), versionId = ref(''), revisionOpen = ref(false), versionOpen = ref(false)
const comparisonId = ref(''), comparisonOpen = ref(false)
const comparison = computed(() => props.task?.items.find(item => item.id === comparisonId.value))
const user = String(useUserStore().getUserInfo.userId)
const command = (item: ApiItem) => itemCommand(user, props.task!.id, item.id)
const hasItemOperation = computed(() => props.task?.items.some(i => command(i).state.busy || command(i).state.pending) || false)
const deleting = computed(() => !!props.task?.deletionState && props.task.deletionState !== 'idle')
const canZip = computed(() => !deleting.value && !!props.task && !props.busy && !hasItemOperation.value && props.task.items.every(i => i.state === 'succeeded' && i.result))
watch(() => props.task?.id, () => { expandedSections.value = []; comparisonOpen.value = false; revisionOpen.value = false; versionOpen.value = false; revisionId.value = ''; versionId.value = ''; downloadError.value = '' })
watch(open, value => { if (!value) { comparisonOpen.value = false; revisionOpen.value = false; versionOpen.value = false } })
function pendingRevision(item: ApiItem, repair: boolean) {
  const pending = command(item).state.pending?.command
  return pending?.kind === 'revise' && (pending.input.kind === 'text_repair') === repair
}
function canRevise(item: ApiItem, repair: boolean) {
  const state = command(item).state
  return !deleting.value && !packing.value && !props.busy && !state.busy && !!item.result && (state.pending ? pendingRevision(item, repair) : item.state === 'succeeded' && !props.channelBlocked)
}
async function repairText(item: ApiItem) {
  if (!props.task || !canRevise(item, true) || !item.currentVersion) return
  const taskId = props.task.id
  if (await command(item).submit({ kind: 'revise', input: { baseVersion: item.currentVersion, kind: 'text_repair', text: '' } }, (action, key) => {
    if (action.kind !== 'revise' || action.input.kind !== 'text_repair') throw new Error('请先确认此图片尚未完成的操作')
    return apiImages.revise(taskId, item.id, action.input, key)
  })) emit('refresh')
}
function canRetry(item: ApiItem) {
  const state = command(item).state
  return !deleting.value && !packing.value && !props.busy && !props.retryPending && !state.busy &&
    (state.pending ? state.pending.command.kind === 'retry' : item.state === 'failed' && !props.channelBlocked)
}
async function retryItem(item: ApiItem) {
  if (!props.task || !canRetry(item)) return
  const taskId = props.task.id
  if (await command(item).submit({ kind: 'retry' }, (action, key) => {
    if (action.kind !== 'retry') throw new Error('请先确认此图片尚未完成的操作')
    return apiImages.retryItem(taskId, item.id, key)
  })) emit('refresh')
}
async function downloadZip() {
  const epoch = identity.epoch
  if (!canZip.value || packing.value || !props.task) return
  const task = props.task; packing.value = true; downloadError.value = ''
  try { const blob = await apiImages.zip(task.id); identity.assert(epoch); saveBlob(blob, task.name + '.zip') }
  catch (e) { if (identity.current(epoch)) downloadError.value = '下载失败，请点击下载重试。' }
  finally { packing.value = false }
}
async function download(picture: ApiPicture) {
  const epoch = identity.epoch
  if (downloading.value) return
  downloading.value = picture.fileId; downloadError.value = ''
  try {
    const blob = await apiImages.download(picture.fileId)
    identity.assert(epoch)
    const url = URL.createObjectURL(blob), link = document.createElement('a')
    link.href = url; link.download = picture.name; document.body.append(link); link.click(); link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 2000)
  } catch (e) { if (identity.current(epoch)) downloadError.value = '下载失败，请点击下载重试。' }
  finally { downloading.value = '' }
}
</script>
<style scoped>
.card-actions { display:flex; flex-wrap:wrap; gap:8px; margin-top:8px; }.card-actions .el-button { margin:0; }
.detail-content { color:var(--art-gray-800); }
.result-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }
.result-grid :deep(.el-card__body) { padding:14px; }
.result-grid .hx-row { flex-wrap:wrap; gap:4px; }
.result-picture { height:180px; }
.result-placeholder { display:flex; flex-direction:column; gap:10px; height:100%; align-items:center; justify-content:center; background:var(--art-gray-100); color:var(--art-gray-600); border-radius:8px; }
.result-placeholder .art-svg-icon { font-size:28px; }
.result-placeholder span { font-size:12px; }
.result-footer { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:12px; min-height:32px; }
.result-footer span { min-width:0; font-size:12px; color:var(--art-gray-600); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.input-grid { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:12px; }
.input-grid .hx-picture { height:100px; }
.input-grid p { margin-top:6px; text-align:center; }
.prompt-text { white-space:pre-wrap; margin-bottom:16px; overflow-wrap:anywhere; }
@media(max-width:700px) { .result-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .input-grid { grid-template-columns:repeat(3,minmax(0,1fr)); } }
@media(max-width:480px) { .result-grid { grid-template-columns:1fr; } }
</style>

<style scoped>.detail-actions { display:flex; flex-wrap:wrap; gap:8px; }.detail-actions .el-button { margin:0; }.item-error { margin-top:10px; font-size:12px; color:var(--el-color-danger); overflow-wrap:anywhere; }.hx-log { overflow-wrap:anywhere; }</style>
