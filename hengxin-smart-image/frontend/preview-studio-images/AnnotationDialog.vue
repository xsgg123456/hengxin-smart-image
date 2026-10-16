<template>
  <ElDialog class="studio-annotation-dialog" :model-value="!!asset" :title="`修改这张 · ${asset?.name || ''}`" width="min(1380px,96vw)" align-center append-to-body destroy-on-close :close-on-click-modal="false" :close-on-press-escape="!locked" :show-close="!locked" @update:model-value="!$event && $emit('close')">
    <DirectAnnotationEditor v-if="asset" ref="editor" :draft-key="`studio-preview-${epoch}-${asset.id}`" :load-original="load" :base-label="`当前图片：${asset.name}`" @preview-state="locked = $event" @submit="$emit('confirm', $event)" />
    <template #footer><span class="annotation-return-note">确认后回到输入区，由你补充并发送</span><ElButton :disabled="locked" @click="$emit('close')">取消</ElButton><ElButton type="primary" :disabled="locked" @click="editor?.preview()">确认标注</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import type { PreparedAnnotation } from '@/views/hengxin/components/annotation/AnnotationEditor.vue'
import DirectAnnotationEditor from './DirectAnnotationEditor.vue'
import type { Asset } from './state'
const props = defineProps<{ asset?: Asset; epoch: number }>()
defineEmits<{ close: []; confirm: [value: PreparedAnnotation] }>()
const editor = ref<InstanceType<typeof DirectAnnotationEditor>>(), locked = ref(false)
async function load() { const r = await fetch(props.asset!.url); if (!r.ok) throw new Error('原图加载失败'); return r.blob() }
</script>
