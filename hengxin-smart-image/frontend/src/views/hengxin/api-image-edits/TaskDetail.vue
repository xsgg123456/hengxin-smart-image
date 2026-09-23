<template>
  <ElDrawer v-model="open" :title="task?.name || '换图详情'" size="min(1040px, 96vw)" destroy-on-close>
    <div v-if="task" class="detail-content">
      <ElAlert title="交互演示：以下是示例结果，并非上传图片的实际生成效果。" type="info" show-icon :closable="false" />
      <div class="hx-detail-toolbar hx-gap"><div><ElTag :type="statusType">{{ state }}</ElTag><span class="hx-muted">{{ task.id }} · 操作人：{{ task.operator || '演示操作人' }}</span></div><div><ElButton v-if="failed && !active" @click="retryFailed(task)">重试失败项</ElButton><ElButton v-if="active" @click="preview.paused = !preview.paused">{{ preview.paused ? '继续演示' : '暂停演示' }}</ElButton><ElButton type="primary" :disabled="!canZip" :loading="packing" @click="downloadZip">{{ packing ? '正在打包' : '整套下载 ZIP' }}</ElButton></div></div>
      <ElAlert v-if="zipError" :title="zipError" type="error" :closable="false" class="hx-gap"><ElButton text type="primary" :loading="packing" :disabled="!canZip" @click="downloadZip">重试下载</ElButton></ElAlert>
      <ElCard class="art-card" shadow="never">
        <div class="hx-row"><strong>{{ progressText }}</strong><span class="hx-muted">{{ success }} / {{ task.items.length }} 张成功</span></div>
        <ElProgress class="hx-gap" :percentage="Math.round(settled / task.items.length * 100)" :stroke-width="7" :show-text="false" />
        <p class="hx-footnote">{{ active ? '每批最多 10 张同时处理，当前批完成后继续下一批。关闭详情不会中断演示。' : failed ? '成功结果已保留，失败项可继续重试。' : '全部示例结果已就绪，按原图顺序排列。' }}</p>
        <p class="hx-footnote">ZIP 使用每张图片选定的当前版本。{{ !canZip ? '全部图片与修改成功后可整套下载；修改期间保留旧结果。' : '历史版本可单独查看和下载。' }}</p>
      </ElCard>
      <SharedMaterial :picture="task.material" />
      <div class="result-grid hx-gap">
        <ElCard v-for="(item, index) in task.items" :key="index" class="art-card" shadow="never">
          <div class="hx-row"><strong>原图 {{ index + 1 }}</strong><ElTag :type="item.state === '成功' ? 'success' : item.state === '失败' ? 'danger' : item.state === '等待重试' ? 'warning' : 'info'" size="small">{{ item.state }}</ElTag></div>
          <p class="item-meta">第 {{ Math.floor(index / 10) + 1 }} 批 · 自动重试 {{ item.retries }}/3</p>
          <ElButton text type="primary" @click="comparisonIndex = index; comparisonOpen = true">查看原图 / 对照成品</ElButton>
          <div class="result-picture hx-gap">
            <PicturePreview v-if="item.result" :picture="item.result" :pictures="results" :index="results.findIndex(p => p.url === item.result?.url && p.name === item.result?.name)" title="模拟结果" />
            <div v-else class="result-placeholder"><ArtSvgIcon :icon="item.state === '失败' ? 'ri:error-warning-line' : item.state === '等待重试' ? 'ri:refresh-line' : 'ri:image-line'" /><strong>{{ item.state }}</strong><span>{{ item.state === '等待重试' ? `自动重试 ${item.retries}/3` : item.state === '失败' ? '3 次重试已用尽' : '结果将在这里显示' }}</span></div>
          </div>
          <div class="result-footer"><span>{{ item.result ? '示例结果 · 点击放大' : item.source?.name || '原图未记录' }}</span><div v-if="item.result"><ElButton text type="primary" :disabled="packing || !!(item.revision && item.revision.state !== '成功')" @click="edit(index)">修改</ElButton><ElButton text type="primary" @click="download(item.result)">下载</ElButton></div></div>
          <div v-if="item.result" class="version-entry"><ElTag size="small" type="info">当前 V{{ item.result.version || 1 }}</ElTag><ElButton text type="primary" @click="history(index)">历史版本（{{ item.versions?.length || 1 }}）</ElButton></div>
          <div v-if="item.revision" class="revision-status"><ElTag size="small" :type="item.revision.state === '失败' ? 'danger' : item.revision.state === '成功' ? 'success' : 'warning'">修改{{ item.revision.state }}</ElTag><span>重试 {{ item.revision.retries }}/3 · {{ item.revision.operator }}</span><ElButton v-if="item.revision.state === '失败'" text type="primary" @click="retryRevision(task, index)">重试修改</ElButton><small v-if="item.revision.state !== '成功'">当前仍展示上次成功结果</small></div>
        </ElCard>
      </div>
      <ElCollapse class="hx-gap">
        <ElCollapseItem title="本次输入与提示词" name="input"><p class="prompt-text">{{ task.prompt }}</p><div class="input-grid"><div v-for="(picture, index) in inputs" :key="index"><PicturePreview :picture="picture" :pictures="inputs" :index="index" title="本次输入" /><p>{{ index === inputs.length - 1 ? '共用素材' : `原图 ${index + 1}` }}</p></div></div></ElCollapseItem>
        <ElCollapseItem title="处理记录" name="events"><div v-for="(event, index) in task.events" :key="index" class="hx-log">{{ event }}</div></ElCollapseItem>
      </ElCollapse>
      <SourceComparison v-if="comparison" v-model="comparisonOpen" :position="comparisonIndex + 1" :source="comparison.source" :result="comparison.result" :version="comparison.result?.version" />
      <DemoRevisionDialog v-model="revisionOpen" :task="task" :index="revisionIndex" />
      <DemoVersionDialog v-model="historyOpen" :task="task" :index="historyIndex" :locked="packing" />
    </div>
    <template #footer><ElButton @click="open = false">返回换图记录</ElButton></template>
  </ElDrawer>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Picture } from '@/types/hengxin'
import PicturePreview from '../components/PicturePreview.vue'
import SharedMaterial from './SharedMaterial.vue'
import SourceComparison from './SourceComparison.vue'
import { preview, taskState, retryFailed, retryRevision, batchInfo, type EditTask, type EditItem } from './preview-state'
import { downloadTaskZip } from './preview-download'
import DemoRevisionDialog from './DemoRevisionDialog.vue'
import DemoVersionDialog from './DemoVersionDialog.vue'
import { getVersions } from './preview-state'
const open = defineModel<boolean>({ required: true })
const props = defineProps<{ task?: EditTask }>()
const revisionOpen = ref(false), revisionIndex = ref(0), packing = ref(false), zipError = ref('')
const comparisonIndex = ref(0), comparisonOpen = ref(false)
const comparison = computed(() => props.task?.items[comparisonIndex.value])
const historyOpen = ref(false), historyIndex = ref(0)
watch(() => props.task?.id, () => { comparisonOpen.value = false; revisionOpen.value = false; historyOpen.value = false; zipError.value = '' })
watch(open, value => { if (!value) { comparisonOpen.value = false; revisionOpen.value = false; historyOpen.value = false } })
const state = computed(() => props.task ? taskState(props.task) : '')
const active = computed(() => ['处理中', '排队中'].includes(state.value))
const success = computed(() => props.task?.items.filter(item => item.state === '成功').length || 0)
const failed = computed(() => props.task?.items.filter(item => item.state === '失败' || item.revision?.state === '失败').length || 0)
const settled = computed(() => props.task?.items.filter(item => ['成功', '失败'].includes(item.state)).length || 0)
const canZip = computed(() => !!props.task?.items.length && props.task.items.every(item => item.state === '成功' && item.result && (!item.revision || item.revision.state === '成功')))
const statusType = computed(() => failed.value ? 'danger' : active.value ? 'primary' : 'success')
const results = computed(() => props.task?.items.flatMap(item => item.result ? [item.result] : []) || [])
const inputs = computed(() => props.task ? [...props.task.items.map(item => item.source), props.task.material] : [])
const progressText = computed(() => {
  if (preview.paused && active.value) return '演示已暂停'
  if (!props.task) return ''
  const batch = batchInfo(props.task)
  const revisions = props.task.items.filter(revisionActive).length
  return revisions ? `${revisions} 张正在修改 · 旧结果已保留` : `第 ${batch.current} / ${batch.total} 批 · ${batch.running} 张处理中`
})
function revisionActive(item: EditItem) { return !!item.revision && ['处理中', '等待重试'].includes(item.revision.state) }
function edit(index: number) { revisionIndex.value = index; revisionOpen.value = true }
function history(index: number) { if (!props.task) return; getVersions(props.task, index); historyIndex.value = index; historyOpen.value = true }
async function downloadZip() {
  if (!props.task || packing.value || !canZip.value) return
  packing.value = true; zipError.value = ''
  try { await downloadTaskZip(props.task) } catch (reason) { zipError.value = reason instanceof Error ? reason.message : '打包失败，请重试' } finally { packing.value = false }
}
function download(picture: Picture) {
  const link = document.createElement('a'); link.href = picture.url; link.download = picture.name; link.click()
}
</script>
<style scoped>
.detail-content { color:var(--art-gray-800); }
.hx-detail-toolbar, .hx-detail-toolbar > div { display:flex; align-items:center; flex-wrap:wrap; gap:8px; }
.hx-detail-toolbar { margin-bottom:16px; }
.hx-detail-toolbar .el-button + .el-button { margin-left:0; }
.item-meta { margin-top:8px; font-size:12px; color:var(--art-gray-600); }
.revision-status { display:flex; flex-wrap:wrap; align-items:center; gap:6px; font-size:12px; border-top:1px solid var(--art-gray-200); padding-top:10px; }
.revision-status small { width:100%; color:var(--art-gray-600); }
.version-entry { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:8px; }
.version-entry .el-button { padding:6px; }
.result-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }
.result-grid :deep(.el-card__body) { padding:14px; }
.result-picture { height:180px; }
.result-placeholder { display:flex; flex-direction:column; gap:10px; height:100%; align-items:center; justify-content:center; background:var(--art-gray-100); color:var(--art-gray-600); border-radius:8px; }
.result-placeholder .art-svg-icon { font-size:28px; }
.result-placeholder span { font-size:12px; }
.result-footer { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:12px; min-height:32px; }
.result-footer span { min-width:0; font-size:12px; color:var(--art-gray-600); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.result-footer > div { display:flex; flex:none; }
.result-footer .el-button { padding:6px; margin:0; }
.input-grid { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:12px; }
.input-grid .hx-picture { height:100px; }
.input-grid p { margin-top:6px; text-align:center; }
.prompt-text { white-space:pre-wrap; margin-bottom:16px; overflow-wrap:anywhere; }
@media(max-width:700px) { .result-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .input-grid { grid-template-columns:repeat(3,minmax(0,1fr)); } }
</style>
