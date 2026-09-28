<template>
  <ElDialog v-model="open" :title="`原图与成品对照 · 第 ${position} 张`" width="min(1040px, 94vw)" align-center append-to-body destroy-on-close>
    <div class="comparison-grid">
      <section><p>原始图片</p><PicturePreview v-if="source?.url" :picture="source" title="任务原始图片" />
        <ElEmpty v-else description="历史记录中没有可查看的原始图片" :image-size="70" />
        <small>{{ source?.name || '原图未记录' }}</small></section>
      <section><p>当前成品 <ElTag v-if="result" size="small">V{{ version || 1 }}</ElTag></p>
        <PicturePreview v-if="result?.url" :picture="result" title="当前成品" />
        <ElEmpty v-else description="暂无可查看的成品" :image-size="70" /><small>点击任一图片可放大查看</small></section>
    </div>
    <template #footer><ElButton @click="open = false">关闭对照</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import type { Picture } from '@/types/hengxin'
import PicturePreview from '../components/PicturePreview.vue'
const open = defineModel<boolean>({ required: true })
defineProps<{ position: number; source?: Picture | null; result?: Picture | null; version?: number | null }>()
</script>
<style scoped>
.comparison-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:20px; max-height:64dvh; overflow-y:auto; }
.comparison-grid section { min-width:0; }
.comparison-grid p { display:flex; align-items:center; gap:8px; margin-bottom:12px; }
.comparison-grid .hx-picture { height:min(52dvh, 480px); }
.comparison-grid small { display:block; margin-top:8px; color:var(--art-gray-600); overflow-wrap:anywhere; }
@media(max-width:700px) { .comparison-grid { grid-template-columns:1fr; } .comparison-grid .hx-picture { height:34dvh; } }
</style>
