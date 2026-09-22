<template>
  <div class="api-result-picture">
    <PicturePreview v-if="item.result" :picture="item.result" :pictures="results" :index="results.findIndex(p => p.fileId === item.result?.fileId)" title="换图结果" />
    <GenerationPlaceholder v-if="pending" :class="{ 'revision-progress': !!item.result }"
      :running="moving" :motion="moving" :compact="!!item.result" :index="item.position - 1"
      :label="label" :status-text="label" :description="description" />
    <div v-else-if="!item.result" class="result-placeholder" role="status">
      <ArtSvgIcon icon="ri:error-warning-line" /><strong>{{ itemLabels[item.state] }}</strong><span>请查看下方处理提示</span>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { itemLabels, type ApiItem, type ApiPicture } from '@/types/api-image-edits'
import GenerationPlaceholder from '../components/GenerationPlaceholder.vue'
import PicturePreview from '../components/PicturePreview.vue'
const props = defineProps<{ item: ApiItem; results: ApiPicture[] }>()
const pending = computed(() => ['queued', 'running', 'retry_wait', 'collecting'].includes(props.item.state))
const waiting = computed(() => props.item.state === 'retry_wait' || (props.item.state === 'collecting' && !!props.item.nextAttemptAt))
const moving = computed(() => ['running', 'collecting'].includes(props.item.state) && !waiting.value)
const label = computed(() => waiting.value ? (props.item.state === 'collecting' ? '等待重新收图' : '等待自动重试')
  : props.item.state === 'running' ? '正在生成画面' : props.item.state === 'collecting' ? '正在收取结果' : '等待开始处理')
const description = computed(() => props.item.result ? '当前结果保留 · 新版本就绪后显示'
  : waiting.value ? '稍后自动继续，无需重复提交' : props.item.state === 'collecting' ? '下载并保存已生成的图片'
    : props.item.state === 'queued' ? '轮到这张后自动开始' : '结果就绪后将在这里呈现')
</script>
<style scoped>
.api-result-picture { position:relative; height:100%; min-width:0; }
.api-result-picture > .generation-canvas { height:100%; aspect-ratio:auto; }
.api-result-picture > .revision-progress { position:absolute; bottom:0; left:0; right:0; height:auto; pointer-events:none; }
.result-placeholder { display:flex; flex-direction:column; gap:10px; height:100%; align-items:center; justify-content:center; background:var(--art-gray-100); color:var(--art-gray-600); border-radius:8px; }
.result-placeholder .art-svg-icon { font-size:28px; }
.result-placeholder span { font-size:12px; }
</style>
