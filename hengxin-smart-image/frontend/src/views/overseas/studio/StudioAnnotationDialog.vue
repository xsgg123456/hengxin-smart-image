<template>
  <ElDialog class="studio-annotation-dialog" :model-value="!!picture" :title="`修改这张 · ${picture.name}`" width="min(1380px,96vw)" align-center append-to-body destroy-on-close :close-on-click-modal="false" :close-on-press-escape="!locked && !submitting" :show-close="!locked && !submitting" @update:model-value="!$event && $emit('close')">
    <StudioAnnotationEditor ref="editor" :draft-key="editingKey" :load-original="load" :base-label="`当前图片：${picture.name}`" :submitting="submitting" @preview-state="locked = $event" @failure="$emit('failure', $event)" @submit="$emit('confirm', $event)" />
    <ElAlert v-if="error" :title="error" type="error" :closable="false" />
    <template #footer><span class="annotation-return-note">确认后回到输入区，由你补充并发送</span><ElButton :disabled="locked || submitting" @click="$emit('close')">取消</ElButton><ElButton type="primary" :disabled="locked || submitting" :loading="submitting" @click="editor?.preview()">确认标注</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import type { StudioPicture } from '@/api/overseas/studio'
import type { PreparedAnnotation } from '@/views/hengxin/components/annotation/AnnotationEditor.vue'
import { annotationDraft, forgetAnnotationDraft } from '@/views/hengxin/components/annotation/annotation-drafts'
import StudioAnnotationEditor from './StudioAnnotationEditor.vue'
import { loadStudioImage } from './studio-images'
const props = defineProps<{ picture: StudioPicture; draftKey: string; submitting: boolean; error: string }>()
defineEmits<{ close: []; confirm: [value: PreparedAnnotation]; failure: [reason: unknown] }>()
const editor = ref<InstanceType<typeof StudioAnnotationEditor>>(), locked = ref(false)
const editingKey = `${props.draftKey}:editing`, controller = new AbortController()
annotationDraft(editingKey).marks = JSON.parse(JSON.stringify(annotationDraft(props.draftKey).marks))
async function load() { return loadStudioImage(props.picture, AbortSignal.any([controller.signal, AbortSignal.timeout(120000)])) }
function commit() { annotationDraft(props.draftKey).marks = JSON.parse(JSON.stringify(annotationDraft(editingKey).marks)) }
onBeforeUnmount(() => { controller.abort(); forgetAnnotationDraft(editingKey) })
defineExpose({ commit })
</script>
