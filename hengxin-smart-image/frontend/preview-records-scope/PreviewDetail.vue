<template>
  <ElDrawer v-model="open" :title="modelValue?.name || '换图详情'" size="min(1040px, 96vw)" destroy-on-close>
    <template v-if="modelValue"><ElTag type="info">示例任务 · 仅预览</ElTag><p class="hx-muted hx-gap">创建人：{{ modelValue.operator }} · {{ friendlyTime(modelValue.created) }}</p>
      <ElCard class="art-card hx-gap" shadow="never"><div class="hx-row"><strong>{{ modelValue.counts.success }} / {{ modelValue.counts.total }} 张已完成</strong><ElTag>{{ taskLabels[modelValue.status] }}</ElTag></div><ElProgress class="hx-gap" :percentage="Math.round(modelValue.counts.success / modelValue.counts.total * 100)" :stroke-width="7" :show-text="false" /></ElCard>
      <div class="preview-pictures hx-gap"><ElCard v-for="index in modelValue.counts.total" :key="index" class="art-card" shadow="never"><strong>原图 {{ index }}</strong><div class="preview-picture hx-gap"><PicturePreview :picture="{ name: `示例图片 ${index}`, url: `/demo-images/sample-${(index - 1) % 4 + 1}.jpg` }" title="示例图片" /></div><p class="hx-footnote">图片仅用于交互预览，不代表真实生成结果</p></ElCard></div>
    </template>
    <template #footer><ElButton @click="open = false">返回换图记录</ElButton></template>
  </ElDrawer>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import PicturePreview from '@/views/hengxin/components/PicturePreview.vue'
import { formatBeijingTime as friendlyTime } from '@/utils/beijing-time'
import { taskLabels } from '@/types/api-image-edits'
import type { PreviewTask } from './state'
const props = defineProps<{ modelValue?: PreviewTask }>()
const emit = defineEmits<{ 'update:modelValue': [value: PreviewTask | undefined] }>()
const open = computed({ get: () => !!props.modelValue, set: value => { if (!value) emit('update:modelValue', undefined) } })
</script>
<style scoped>
.preview-pictures { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:18px; }
.preview-picture { height:230px; }
@media(max-width:640px) { .preview-pictures { grid-template-columns:1fr; } }
</style>
