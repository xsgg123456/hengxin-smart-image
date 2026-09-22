<template>
  <ElDrawer v-model="open" :title="task?.name || '换图详情'" size="min(1040px, 96vw)" destroy-on-close>
    <div v-if="task" class="detail-content">
      <ElAlert title="交互演示：以下是示例结果，并非上传图片的实际生成效果。" type="info" show-icon :closable="false" />
      <div class="hx-detail-toolbar hx-gap"><div><ElTag :type="statusType">{{ state }}</ElTag><span class="hx-muted">{{ task.id }}</span></div><div><ElButton v-if="failed && !active" type="primary" @click="retryFailed(task)">仅重试失败的 {{ failed }} 张</ElButton><ElButton v-if="active" @click="preview.paused = !preview.paused">{{ preview.paused ? '继续演示' : '暂停演示' }}</ElButton></div></div>
      <ElCard class="art-card" shadow="never">
        <div class="hx-row"><strong>{{ progressText }}</strong><span class="hx-muted">{{ success }} / {{ task.items.length }} 张成功</span></div>
        <ElProgress class="hx-gap" :percentage="Math.round(settled / task.items.length * 100)" :stroke-width="7" :show-text="false" />
        <p class="hx-footnote">{{ active ? '当前图片处理结束后，才会处理下一张。关闭详情不会中断本页演示。' : failed ? '成功结果已保留，可以单独下载；失败项可以重新处理。' : '全部示例结果已就绪，按原图顺序排列。' }}</p>
      </ElCard>
      <div class="result-grid hx-gap">
        <ElCard v-for="(item, index) in task.items" :key="index" class="art-card" shadow="never">
          <div class="hx-row"><strong>原图 {{ index + 1 }}</strong><ElTag :type="item.state === '成功' ? 'success' : item.state === '失败' ? 'danger' : item.state === '等待重试' ? 'warning' : 'info'" size="small">{{ item.state }}</ElTag></div>
          <div class="result-picture hx-gap">
            <PicturePreview v-if="item.result" :picture="item.result" :pictures="results" :index="results.findIndex(p => p.url === item.result?.url && p.name === item.result?.name)" title="模拟结果" />
            <div v-else class="result-placeholder"><ArtSvgIcon :icon="item.state === '失败' ? 'ri:error-warning-line' : item.state === '等待重试' ? 'ri:refresh-line' : 'ri:image-line'" /><strong>{{ item.state }}</strong><span>{{ item.state === '等待重试' ? `自动重试 ${item.retries}/3` : item.state === '失败' ? '3 次重试已用尽' : '结果将在这里显示' }}</span></div>
          </div>
          <div class="result-footer"><span>{{ item.result ? '示例结果 · 点击放大' : item.source.name }}</span><ElButton v-if="item.result" text type="primary" @click="download(item.result)">下载示例</ElButton></div>
        </ElCard>
      </div>
      <ElCollapse class="hx-gap">
        <ElCollapseItem title="本次输入与提示词" name="input"><p class="prompt-text">{{ task.prompt }}</p><div class="input-grid"><div v-for="(picture, index) in inputs" :key="index"><PicturePreview :picture="picture" :pictures="inputs" :index="index" title="本次输入" /><p>{{ index === inputs.length - 1 ? '共用素材' : `原图 ${index + 1}` }}</p></div></div></ElCollapseItem>
        <ElCollapseItem title="处理记录" name="events"><div v-for="(event, index) in task.events" :key="index" class="hx-log">{{ event }}</div></ElCollapseItem>
      </ElCollapse>
    </div>
    <template #footer><ElButton @click="open = false">返回换图记录</ElButton></template>
  </ElDrawer>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import type { Picture } from '@/types/hengxin'
import PicturePreview from '../components/PicturePreview.vue'
import { preview, taskState, retryFailed, type EditTask } from './preview-state'
const open = defineModel<boolean>({ required: true })
const props = defineProps<{ task?: EditTask }>()
const state = computed(() => props.task ? taskState(props.task) : '')
const active = computed(() => ['处理中', '排队中'].includes(state.value))
const success = computed(() => props.task?.items.filter(item => item.state === '成功').length || 0)
const failed = computed(() => props.task?.items.filter(item => item.state === '失败').length || 0)
const settled = computed(() => success.value + failed.value)
const statusType = computed(() => failed.value ? 'danger' : active.value ? 'primary' : 'success')
const results = computed(() => props.task?.items.flatMap(item => item.result ? [item.result] : []) || [])
const inputs = computed(() => props.task ? [...props.task.items.map(item => item.source), props.task.material] : [])
const progressText = computed(() => {
  const index = props.task?.items.findIndex(item => ['处理中', '等待重试'].includes(item.state)) ?? -1
  const item = props.task?.items[index]
  if (preview.paused && active.value) return '演示已暂停'
  if (item?.state === '等待重试') return `第 ${index + 1} 张暂时失败，等待第 ${item.retries}/3 次重试`
  return index >= 0 ? `正在处理第 ${index + 1} 张` : state.value
})
function download(picture: Picture) {
  const link = document.createElement('a'); link.href = picture.url; link.download = picture.name; link.click()
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
