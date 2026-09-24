<template>
  <ElDialog v-model="open" :title="`修改第 ${slot + 1} 张图片 · 基于 V${base.version}`" width="min(1380px, 96vw)" align-center append-to-body destroy-on-close :close-on-click-modal="false" :close-on-press-escape="!working" :show-close="!working">
    <AnnotationEditor v-if="open" ref="editor" :draft-key="draftKey" :load-original="loadOriginal" :base-label="`本次基于 V${base.version} 修改`" :limit="1000" require-text :disabled="working || uncertain || !editable" @submit="submit" />
    <ElAlert v-if="error || localError" :title="localError || error" type="error" :closable="false" />
    <template #footer><ElButton :disabled="working" @click="open = false">取消</ElButton><ElButton type="primary" :loading="working" :disabled="!uncertain && !editable" @click="uncertain ? emit('confirmPrevious') : editor?.preview()">{{ uncertain ? '确认上次提交' : '预览提交内容' }}</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { uploadFile } from '@/api/files'
import { isMockMode } from '@/api/hengxin/client'
import type { Picture, ResultVersion } from '@/types/hengxin'
import { requestDownload, readImage } from '../../download-helpers'
import AnnotationEditor, { type PreparedAnnotation } from './AnnotationEditor.vue'
const open = defineModel<boolean>({ required: true })
const props = defineProps<{ identity?: string; taskId: string; slot: number; base: ResultVersion; pending: boolean; uncertain: boolean; editable: boolean; error: string }>()
const emit = defineEmits<{ submit: [input: { note: string; annotationFileId: string | null }]; confirmPrevious: []; preparing: [value: boolean] }>()
const draftKey = computed(() => JSON.stringify(['cli', props.identity, props.taskId, props.slot, props.base.id]))
const editor = ref<InstanceType<typeof AnnotationEditor>>(), uploading = ref(false), localError = ref('')
const working = computed(() => props.pending || uploading.value)
let alive = true, cached: { file: File; picture: Picture } | undefined
async function loadOriginal() {
  if (!isMockMode) return requestDownload(import.meta.env.VITE_API_URL || '/api/v1', [props.base.fileId])
  const image = await readImage(props.base.url)
  return new Blob([image.data], { type: image.mime })
}
async function submit(value: PreparedAnnotation) {
  if (working.value || props.uncertain || !props.editable) return
  const key = draftKey.value; uploading.value = true; emit('preparing', true); localError.value = ''
  try {
    let picture: Picture | undefined
    if (value.file) { picture = cached?.file === value.file ? cached.picture : await uploadFile(value.file); cached = { file: value.file, picture } }
    if (!alive || key !== draftKey.value || !open.value) return
    if (value.file && !picture?.fileId && !isMockMode) throw new Error('标注图上传未返回文件标识，请重试')
    uploading.value = false; emit('preparing', false)
    emit('submit', { note: value.text, annotationFileId: picture?.fileId ?? null })
  } catch (error) { if (alive && key === draftKey.value) localError.value = error instanceof Error ? error.message : '标注上传失败' }
  finally { uploading.value = false; emit('preparing', false) }
}
onBeforeUnmount(() => { alive = false })
</script>
