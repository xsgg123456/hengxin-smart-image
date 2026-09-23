<template>
  <ElDrawer v-model="open" :title="task?.name || '换图详情'" size="min(1040px, 96vw)" destroy-on-close>
    <ElAlert v-if="error" :title="error" type="error" :closable="false"><ElButton @click="$emit('refresh')">重新加载</ElButton></ElAlert>
    <ElSkeleton v-else-if="loading && !task" :rows="8" animated />
    <div v-if="task" class="detail-content">
      <ElAlert v-if="actionError || downloadError" :title="actionError || downloadError" type="error" :closable="false" />
      <ElAlert v-if="task.error" :title="task.error" type="warning" :closable="false" />
      <ElAlert v-if="task.status === 'uncertain'" title="请求结果需核实，通道保持阻塞" description="旧请求可能仍在处理，不会自动重复生成。请联系超级管理员核实旧请求已停止后再恢复。" type="warning" show-icon :closable="false" />
      <div class="hx-detail-toolbar hx-gap"><div><ElTag :type="task.status === 'succeeded' ? 'success' : task.status === 'uncertain' || failed ? 'danger' : 'primary'">{{ taskLabels[task.status] }}</ElTag><span class="hx-muted">{{ task.id }}</span></div><div class="detail-actions">
        <ElButton type="primary" :loading="packing" :disabled="!canZip || packing" @click="downloadZip">{{ packing ? '打包中…' : '下载整套 ZIP' }}</ElButton>
        <ElButton :loading="loading" @click="$emit('refresh')">刷新详情</ElButton>
        <ElButton v-if="retryPending || (failed && !isTaskActive(task))" type="primary" :loading="busy" :disabled="busy || packing || hasItemOperation || (!retryPending && channelBlocked)" @click="$emit('retry', task.id)">{{ retryPending ? '确认原重试请求' : `仅重试失败的 ${failed} 张` }}</ElButton>
        <ElButton v-if="admin && task.status === 'uncertain'" type="warning" :loading="busy" @click="$emit('resolve', task.id)">核实已停止</ElButton>
      </div></div>
      <ElCard class="art-card" shadow="never">
        <div class="hx-row"><strong>{{ progressText }}</strong><span class="hx-muted">{{ success }} / {{ task.items.length }} 张成功</span></div>
        <ElProgress class="hx-gap" :percentage="Math.round((success + failed) / task.items.length * 100)" :stroke-width="7" :show-text="false" />
        <p class="hx-footnote">第 {{ task.batch.current }} / {{ task.batch.total }} 批 · {{ task.batch.running }} 张处理中 · 每批最多 10 张，整批结束后处理下一批。</p><p class="hx-footnote">操作人：{{ task.operator || '未记录' }} · {{ friendlyTime(task.created) }} · 成功结果保留，关闭详情不会中断处理。</p>
        <p class="hx-footnote">网络尝试 {{ task.metrics.requestCount }} 次 · 生成重试 {{ task.metrics.retryCount }} 次 · 总耗时 {{ seconds(task.metrics.elapsedSeconds) }} · 费用未提供</p>
      <p class="hx-footnote">排队 {{ seconds(task.metrics.queueSeconds) }} · 生成 {{ seconds(task.metrics.generationSeconds) }} · 收图重试不计入生成重试；返回尺寸以上游实际图片为准。</p>
      </ElCard>
      <SharedMaterial :picture="task.material" />
      <div class="result-grid hx-gap">
        <ElCard v-for="item in task.items" :key="item.id" class="art-card" shadow="never">
          <div class="hx-row"><strong>原图 {{ item.position }}</strong><ElTag :type="item.state === 'succeeded' ? 'success' : ['failed', 'uncertain'].includes(item.state) ? 'danger' : item.state === 'retry_wait' ? 'warning' : 'info'" size="small">{{ itemLabels[item.state] }}</ElTag></div>
          <ElButton text type="primary" @click="comparisonId = item.id; comparisonOpen = true">查看原图 / 对照成品</ElButton>
          <div class="result-picture hx-gap"><ApiResultPicture :item="item" :results="results" /></div>
          <p v-if="item.nextAttemptAt" class="hx-footnote">下次尝试：{{ friendlyTime(item.nextAttemptAt) }}</p><p v-if="item.error" class="item-error">{{ item.error }}</p>
          <div class="result-footer"><span>{{ item.result ? `当前 V${item.currentVersion} · 点击放大` : item.source?.name || '原图未记录' }}</span><ElButton v-if="item.result" text type="primary" :loading="downloading === item.result.fileId" :disabled="!!downloading" @click="download(item.result)">下载图片</ElButton></div>
          <p v-if="item.revision" class="hx-footnote">修改：{{ itemLabels[item.revision.state] }} · {{ item.revision.operator }} · 基于 V{{ item.revision.baseVersion }}<span v-if="item.state !== 'succeeded'"> · 旧结果保留</span></p>
          <p v-if="item.retries" class="hx-footnote">已自动重试 {{ item.retries }} / 3 次</p>
          <div class="card-actions">
            <ElButton v-if="item.result" size="small" :disabled="packing || busy || command(item).state.busy || (!!command(item).state.pending && command(item).state.pending?.command.kind !== 'revise') || (!command(item).state.pending && (item.state !== 'succeeded' || channelBlocked))" @click="revisionId = item.id; revisionOpen = true">{{ command(item).state.pending?.command.kind === 'revise' ? '确认原修改请求' : '修改这张' }}</ElButton>
            <ElButton v-if="item.result" text type="primary" @click="versionId = item.id; versionOpen = true">历史版本 · {{ item.versions.length }}</ElButton>
            <ElButton v-if="item.state === 'failed' || command(item).state.pending?.command.kind === 'retry'" size="small" type="primary" :loading="command(item).state.busy" :disabled="packing || busy || (!!command(item).state.pending && command(item).state.pending?.command.kind !== 'retry') || (!command(item).state.pending && channelBlocked)" @click="retryItem(item)">{{ command(item).state.pending ? '确认原重试请求' : '继续重试这张' }}</ElButton>
          </div>
          <p v-if="command(item).state.error" class="item-error">{{ command(item).state.error }}</p>
        </ElCard>
      </div>
      <ElCollapse class="hx-gap"><ElCollapseItem title="本次输入与提示词" name="input"><p class="prompt-text">{{ task.prompt }}</p><div class="input-grid"><div v-for="(picture, index) in inputs" :key="index"><PicturePreview v-if="picture?.url" :picture="picture" title="本次输入" /><p v-else>图片未记录</p><p>{{ index === inputs.length - 1 ? '共用素材' : `原图 ${index + 1}` }}</p></div></div></ElCollapseItem><ElCollapseItem title="处理记录" name="events"><ElEmpty v-if="!task.events.length" description="暂无处理记录" :image-size="60" /><div v-for="(event, index) in task.events" :key="index" class="hx-log">{{ event }}</div></ElCollapseItem></ElCollapse>
    </div>
    <SourceComparison v-if="comparison" v-model="comparisonOpen" :position="comparison.position" :source="comparison.source" :result="comparison.result" :version="comparison.currentVersion" />
    <RealRevisionDialog v-if="task && revisionId" v-model="revisionOpen" :task="task" :item-id="revisionId" :blocked="packing || busy" @accepted="emit('refresh')" />
    <RealVersionDialog v-if="task && versionId" v-model="versionOpen" :task="task" :item-id="versionId" :locked="packing || busy" @accepted="emit('refresh')" />
    <template #footer><ElButton @click="open = false">返回换图记录</ElButton></template>
  </ElDrawer>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { apiImages, errorText } from '@/api/api-image-edits'
import { taskLabels, itemLabels, isTaskActive, type ApiPicture, type ApiTask, type ApiItem } from '@/types/api-image-edits'
import PicturePreview from '../components/PicturePreview.vue'
import SharedMaterial from './SharedMaterial.vue'
import SourceComparison from './SourceComparison.vue'
import ApiResultPicture from './ApiResultPicture.vue'
import RealRevisionDialog from './RealRevisionDialog.vue'
import RealVersionDialog from './RealVersionDialog.vue'
import { useUserStore } from '@/store/modules/user'
import { itemCommand, friendlyTime, saveBlob } from './item-command'
const open = defineModel<boolean>({ required: true })
const props = defineProps<{ task?: ApiTask; loading: boolean; error: string; actionError: string; busy: boolean; admin: boolean; retryPending: boolean; channelBlocked: boolean }>()
const emit = defineEmits<{ refresh: []; retry: [id: string]; resolve: [id: string] }>()
const success = computed(() => props.task?.items.filter(i => i.state === 'succeeded').length || 0), failed = computed(() => props.task?.items.filter(i => i.state === 'failed').length || 0)
const results = computed(() => props.task?.items.flatMap(i => i.result ? [i.result] : []) || [])
const inputs = computed(() => props.task ? [...props.task.items.map(i => i.source), props.task.material] : [])
const progressText = computed(() => { const item = props.task?.items.find(i => ['running', 'retry_wait', 'collecting'].includes(i.state)); return item ? `原图 ${item.position}：${itemLabels[item.state]}` : props.task ? taskLabels[props.task.status] : '' })
const seconds = (value: number | null | undefined) => typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(1)} 秒` : '未提供'
const downloading = ref(''), downloadError = ref(''), packing = ref(false)
const revisionId = ref(''), versionId = ref(''), revisionOpen = ref(false), versionOpen = ref(false)
const comparisonId = ref(''), comparisonOpen = ref(false)
const comparison = computed(() => props.task?.items.find(item => item.id === comparisonId.value))
const user = String(useUserStore().getUserInfo.userId)
const command = (item: ApiItem) => itemCommand(user, props.task!.id, item.id)
const hasItemOperation = computed(() => props.task?.items.some(i => command(i).state.busy || command(i).state.pending) || false)
const canZip = computed(() => !!props.task && !props.busy && !hasItemOperation.value && props.task.items.every(i => i.state === 'succeeded' && i.result))
watch(() => props.task?.id, () => { comparisonOpen.value = false; revisionOpen.value = false; versionOpen.value = false; revisionId.value = ''; versionId.value = '' })
watch(open, value => { if (!value) { comparisonOpen.value = false; revisionOpen.value = false; versionOpen.value = false } })
async function retryItem(item: ApiItem) {
  if (!props.task || packing.value || props.busy || (props.channelBlocked && !command(item).state.pending)) return
  const taskId = props.task.id
  if (await command(item).submit({ kind: 'retry' }, (action, key) => {
    if (action.kind !== 'retry') throw new Error('请先确认此图片尚未完成的操作')
    return apiImages.retryItem(taskId, item.id, key)
  })) emit('refresh')
}
async function downloadZip() {
  if (!canZip.value || packing.value || !props.task) return
  const task = props.task; packing.value = true; downloadError.value = ''
  try { saveBlob(await apiImages.zip(task.id), task.name + '.zip') }
  catch (e) { downloadError.value = errorText(e) }
  finally { packing.value = false }
}
async function download(picture: ApiPicture) {
  if (downloading.value) return
  downloading.value = picture.fileId; downloadError.value = ''
  try {
    const blob = await apiImages.download(picture.fileId), url = URL.createObjectURL(blob), link = document.createElement('a')
    link.href = url; link.download = picture.name; document.body.append(link); link.click(); link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 2000)
  } catch (e) { downloadError.value = errorText(e) }
  finally { downloading.value = '' }
}
</script>
<style scoped>
.card-actions { display:flex; flex-wrap:wrap; gap:8px; margin-top:8px; }.card-actions .el-button { margin:0; }
.detail-content { color:var(--art-gray-800); }
.result-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }
.result-grid :deep(.el-card__body) { padding:14px; }
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
</style>

<style scoped>.detail-actions { display:flex; flex-wrap:wrap; gap:8px; }.detail-actions .el-button { margin:0; }.item-error { margin-top:10px; font-size:12px; color:var(--el-color-danger); overflow-wrap:anywhere; }.hx-log { overflow-wrap:anywhere; }</style>
