<template>
  <ElDrawer v-model="open" :title="task?.name || '换图详情'" size="min(1040px, 96vw)" destroy-on-close>
    <ElAlert v-if="error" :title="error" type="error" :closable="false"><ElButton @click="$emit('refresh')">重新加载</ElButton></ElAlert>
    <ElSkeleton v-else-if="loading && !task" :rows="8" animated />
    <div v-if="task" class="detail-content">
      <ElAlert v-if="actionError || downloadError" :title="actionError || downloadError" type="error" :closable="false" />
      <ElAlert v-if="task.error" :title="task.error" type="warning" :closable="false" />
      <ElAlert v-if="task.status === 'uncertain'" title="请求结果需核实，通道保持阻塞" description="旧请求可能仍在处理，不会自动重复生成。请联系超级管理员核实旧请求已停止后再恢复。" type="warning" show-icon :closable="false" />
      <div class="hx-detail-toolbar hx-gap"><div><ElTag :type="task.status === 'succeeded' ? 'success' : task.status === 'uncertain' || failed ? 'danger' : 'primary'">{{ taskLabels[task.status] }}</ElTag><span class="hx-muted">{{ task.id }}</span></div><div class="detail-actions">
        <ElButton :loading="loading" @click="$emit('refresh')">刷新详情</ElButton>
        <ElButton v-if="retryPending || (failed && !isTaskActive(task))" type="primary" :loading="busy" :disabled="busy || (!retryPending && channelBlocked)" @click="$emit('retry', task.id)">{{ retryPending ? '确认原重试请求' : `仅重试失败的 ${failed} 张` }}</ElButton>
        <ElButton v-if="admin && task.status === 'uncertain'" type="warning" :loading="busy" @click="$emit('resolve', task.id)">核实已停止</ElButton>
      </div></div>
      <ElCard class="art-card" shadow="never">
        <div class="hx-row"><strong>{{ progressText }}</strong><span class="hx-muted">{{ success }} / {{ task.items.length }} 张成功</span></div>
        <ElProgress class="hx-gap" :percentage="Math.round((success + failed) / task.items.length * 100)" :stroke-width="7" :show-text="false" />
        <p class="hx-footnote">成功结果保留，按原图顺序展示。关闭详情不会中断处理。</p>
        <p class="hx-footnote">网络尝试 {{ task.metrics.requestCount }} 次 · 生成重试 {{ task.metrics.retryCount }} 次 · 总耗时 {{ seconds(task.metrics.elapsedSeconds) }} · 费用未提供</p>
      <p class="hx-footnote">排队 {{ seconds(task.metrics.queueSeconds) }} · 生成 {{ seconds(task.metrics.generationSeconds) }} · 收图重试不计入生成重试；返回尺寸以上游实际图片为准。</p>
      </ElCard>
      <div class="result-grid hx-gap">
        <ElCard v-for="item in task.items" :key="item.id" class="art-card" shadow="never">
          <div class="hx-row"><strong>原图 {{ item.position }}</strong><ElTag :type="item.state === 'succeeded' ? 'success' : ['failed', 'uncertain'].includes(item.state) ? 'danger' : item.state === 'retry_wait' ? 'warning' : 'info'" size="small">{{ itemLabels[item.state] }}</ElTag></div>
          <div class="result-picture hx-gap"><PicturePreview v-if="item.result" :picture="item.result" :pictures="results" :index="results.findIndex(p => p.fileId === item.result?.fileId)" title="换图结果" /><div v-else class="result-placeholder"><ArtSvgIcon :icon="['failed', 'uncertain'].includes(item.state) ? 'ri:error-warning-line' : item.state === 'retry_wait' ? 'ri:refresh-line' : 'ri:image-line'" /><strong>{{ itemLabels[item.state] }}</strong><span>{{ item.state === 'retry_wait' ? '等待下一次尝试' : '结果将在这里显示' }}</span></div></div>
          <p v-if="item.nextAttemptAt" class="hx-footnote">下次尝试：{{ item.nextAttemptAt }}</p><p v-if="item.error" class="item-error">{{ item.error }}</p>
          <div class="result-footer"><span>{{ item.result ? '生成结果 · 点击放大' : item.source.name }}</span><ElButton v-if="item.result" text type="primary" :loading="downloading === item.result.fileId" :disabled="!!downloading" @click="download(item.result)">下载图片</ElButton></div>
        </ElCard>
      </div>
      <ElCollapse class="hx-gap"><ElCollapseItem title="本次输入与提示词" name="input"><p class="prompt-text">{{ task.prompt }}</p><div class="input-grid"><div v-for="(picture, index) in inputs" :key="index"><PicturePreview :picture="picture" :pictures="inputs" :index="index" title="本次输入" /><p>{{ index === inputs.length - 1 ? '共用素材' : `原图 ${index + 1}` }}</p></div></div></ElCollapseItem><ElCollapseItem title="处理记录" name="events"><ElEmpty v-if="!task.events.length" description="暂无处理记录" :image-size="60" /><div v-for="(event, index) in task.events" :key="index" class="hx-log">{{ event }}</div></ElCollapseItem></ElCollapse>
    </div>
    <template #footer><ElButton @click="open = false">返回换图记录</ElButton></template>
  </ElDrawer>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { apiImages, errorText } from '@/api/api-image-edits'
import { taskLabels, itemLabels, isTaskActive, type ApiPicture, type ApiTask } from '@/types/api-image-edits'
import PicturePreview from '../components/PicturePreview.vue'
const open = defineModel<boolean>({ required: true })
const props = defineProps<{ task?: ApiTask; loading: boolean; error: string; actionError: string; busy: boolean; admin: boolean; retryPending: boolean; channelBlocked: boolean }>()
defineEmits<{ refresh: []; retry: [id: string]; resolve: [id: string] }>()
const success = computed(() => props.task?.items.filter(i => i.state === 'succeeded').length || 0), failed = computed(() => props.task?.items.filter(i => i.state === 'failed').length || 0)
const results = computed(() => props.task?.items.flatMap(i => i.result ? [i.result] : []) || [])
const inputs = computed(() => props.task ? [...props.task.items.map(i => i.source), props.task.material] : [])
const progressText = computed(() => { const item = props.task?.items.find(i => ['running', 'retry_wait', 'collecting'].includes(i.state)); return item ? `原图 ${item.position}：${itemLabels[item.state]}` : props.task ? taskLabels[props.task.status] : '' })
const seconds = (value: number | null | undefined) => typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(1)} 秒` : '未提供'
const downloading = ref(''), downloadError = ref('')
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
