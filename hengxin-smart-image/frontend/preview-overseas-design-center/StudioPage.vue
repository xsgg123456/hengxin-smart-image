<template>
  <section ref="page" class="center-studio" aria-label="AI 设计工作台">
    <header class="center-studio-heading">
      <button class="center-studio-back" type="button" @click="emit('back')">
        <ElIcon><ArrowLeft /></ElIcon> 返回设计任务中心
      </button>
      <div>
        <p>AI 设计工作台</p>
        <h1>{{ task.title }}</h1>
        <div class="center-studio-meta"><b>{{ task.sku }}</b><span v-if="task.designType === 'custom'">自定义生图</span><template v-else><span>{{ task.brand }}</span><span>{{ task.platform }}</span></template></div>
      </div>
    </header>
    <OverseasStudio :key="task.id" actor-id="design-center-preview" :task="detail" @failure="showFailure" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onScopeDispose, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import OverseasStudio from '@/views/overseas/studio/OverseasStudio.vue'
import { overseasImageCache } from '@/api/overseas/image-cache'
import { installStudioPreview, studioTask, type StudioEntry } from './studio-local'

const props = defineProps<{ task: StudioEntry }>()
const emit = defineEmits<{ back: [] }>()
const detail = computed(() => studioTask(props.task))
const page = ref<HTMLElement>()

let restore: (() => void) | undefined
watch(() => props.task.id, () => {
  restore?.()
  restore = installStudioPreview(props.task)
}, { immediate: true, flush: 'sync' })
onMounted(() => {
  overseasImageCache.setIdentity('design-center-preview')
  if (window.matchMedia('(max-width: 1150px)').matches) {
    page.value?.querySelector<HTMLButtonElement>('.session-list-title button')?.click()
    page.value?.querySelector<HTMLButtonElement>('.studio-materials-title button')?.click()
  }
})
onScopeDispose(() => restore?.())
function showFailure(reason: unknown) {
  ElMessage.warning(reason instanceof Error ? reason.message : '此操作在本地预览中不可用')
}
</script>

<style scoped>
.center-studio{min-width:0;padding:22px clamp(14px,2.2vw,36px) 0;color:var(--el-text-color-primary);--default-box-color:var(--el-bg-color);--default-border:var(--el-border-color-lighter);--art-gray-500:var(--el-text-color-secondary);--art-gray-600:var(--el-text-color-regular);--art-gray-700:var(--el-text-color-regular);--art-gray-800:var(--el-text-color-primary)}
.center-studio-heading{display:flex;flex-direction:column;align-items:flex-start;gap:16px;margin-bottom:16px}
.center-studio-heading p{font-size:12px;color:var(--el-text-color-secondary);margin:0 0 4px}
.center-studio-heading h1{font-size:clamp(20px,2vw,28px);font-weight:650;line-height:1.3;margin:0}
.center-studio-back{display:inline-flex;align-items:center;gap:4px;padding:0;border:0;background:transparent;color:var(--el-color-primary);font:inherit;font-size:13px;cursor:pointer}
.center-studio-meta{display:flex;align-items:center;flex-wrap:wrap;gap:10px;font-size:12px;color:var(--el-text-color-secondary);margin-top:7px}
.center-studio-meta b{font-weight:550;color:var(--el-text-color-regular)}
.center-studio-meta span{padding-left:10px;border-left:1px solid var(--el-border-color)}
.center-studio :deep(.studio-steps){display:none}
.center-studio :deep([data-material-id^="task:metadata-"] .attachment-download){display:none}
.center-studio :deep([data-material-id^="task:metadata-"] .material-info small){font-size:0}
.center-studio :deep([data-material-id^="task:metadata-"] .material-info small::after){content:"资料名已保留";font-size:11px}
@media(max-width:760px){
  .center-studio{padding:12px 8px 0}
  .center-studio-heading{gap:8px;margin-bottom:10px}
  .center-studio :deep(.studio-chat-card:not(.studio-expanded)>.el-card__body){height:auto;min-height:76dvh}
  .center-studio :deep(.studio-conversation){min-width:0}
  .center-studio :deep(.studio-messages){min-height:200px;max-height:42dvh}
  .center-studio :deep(.studio-compose-tools){flex-wrap:wrap}
}
</style>
