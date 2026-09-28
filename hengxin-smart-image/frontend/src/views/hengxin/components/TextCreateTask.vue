<template>
  <div class="hx-page">
    <div class="hx-heading"><div><h1>替换文字</h1><p>上传一张原图，填写文字修改要求；可框选或圈出需要修改的位置。</p></div><ElButton @click="router.push('/tasks/index')">查看任务</ElButton></div>
    <ElCard class="art-card hx-section" shadow="never">
      <ElForm label-position="top" :disabled="locked" class="task-fields">
        <ElFormItem label="任务名称" required><ElInput v-model="name" aria-label="任务名称" maxlength="60" show-word-limit placeholder="例如：商品标题文字替换" /></ElFormItem>
        <ElFormItem label="SKU（选填）"><ElInput v-model="sku" aria-label="SKU" maxlength="80" show-word-limit /></ElFormItem>
      </ElForm>
      <ImageUpload :key="draftKey" v-model="sources" mode="text" :max-count="1" :example-count="1" :disabled="locked" @blocked="uploadBlocked = $event" />
      <p class="hx-footnote">每次处理一张原图。更换图片请先移除当前图片，旧标注会清空。</p>
    </ElCard>
    <ElCard v-if="sources.length === 1" class="art-card hx-section hx-gap" shadow="never">
      <AnnotationEditor ref="editor" :draft-key="draftKey" :load-original="loadOriginal" source-label="上传图片" base-label="本次基于上传原图修改" confirm-label="确认提交生成任务" :limit="1000" require-text marking-optional :disabled="locked" @submit="prepareSubmit" />
    </ElCard>
    <ElAlert v-if="error || localError" :title="localError || error" type="error" :closable="false" class="hx-gap" />
    <ElAlert v-if="accepted" :title="`任务已受理：${accepted.taskId}`" type="success" :closable="false" class="hx-gap"><ElButton text @click="viewAccepted">查看已受理任务</ElButton><ElButton text @click="startNew">另建任务</ElButton></ElAlert>
    <ElAlert v-else-if="uncertain" title="上次提交结果尚未确认；输入已保留，请确认原请求以避免重复任务。" type="warning" :closable="false" class="hx-gap"><ElButton text :loading="submitting" @click="submit(true)">确认上次提交</ElButton></ElAlert>
    <div class="hx-gap"><ElButton type="primary" size="large" :loading="working" :disabled="locked || uploadBlocked || sources.length !== 1 || !name.trim()" @click="editor?.preview()">预览提交内容</ElButton><span class="hx-footnote"> 预计输出 1 张</span></div>
  </div>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { uploadFile } from '@/api/files'
import { isMockMode } from '@/api/hengxin/client'
import type { Picture } from '@/types/hengxin'
import { useCreateTask } from '../use-create-task'
import { requestDownload, readImage } from '../download-helpers'
import ImageUpload from './ImageUpload.vue'
import AnnotationEditor, { type PreparedAnnotation } from './annotation/AnnotationEditor.vue'
import { annotationDraft, annotationText } from './annotation/annotation-drafts'
const router = useRouter()
const { session, sources, name, sku, note, submitting, uploadBlocked, error, submit, accepted, uncertain, viewAccepted, startNew } = useCreateTask(ref('text'))
const draftKey = computed(() => session.value.draft.annotationKey)
const editor = ref<InstanceType<typeof AnnotationEditor>>()
const uploading = ref(false), localError = ref('')
const working = computed(() => submitting.value || uploading.value || session.value.submission.pending)
const locked = computed(() => working.value || uncertain.value || !!accepted.value)
let alive = true, cached: { file: File; picture: Picture } | undefined
watch(draftKey, () => { cached = undefined; localError.value = '' })
watch(() => {
  try { return annotationText(annotationDraft(draftKey.value), 1000, false) } catch { return '' }
}, value => { note.value = value }, { immediate: true, flush: 'sync' })
async function loadOriginal() {
  const source = sources.value[0]
  if (!source) throw new Error('请先上传原图')
  if (!isMockMode) return requestDownload(import.meta.env.VITE_API_URL || '/api/v1', [source.fileId])
  const image = await readImage(source.url)
  return new Blob([image.data], { type: image.mime })
}
async function prepareSubmit(value: PreparedAnnotation) {
  if (locked.value || uploadBlocked.value || sources.value.length !== 1) return
  const key = draftKey.value; uploading.value = true; localError.value = ''
  try {
    let picture: Picture | undefined
    if (value.file) {
      picture = cached?.file === value.file ? cached.picture : await uploadFile(value.file)
      if (!alive || key !== draftKey.value) return
      cached = { file: value.file, picture }
      if (!picture.fileId && !isMockMode) throw new Error('标注图上传未返回文件标识，请重试')
    }
    if (!alive || key !== draftKey.value) return
    note.value = value.text
    await submit(false, picture?.fileId ?? null)
  } catch (cause) {
    if (alive && key === draftKey.value) localError.value = cause instanceof Error ? cause.message : '标注图上传失败，请重试'
  } finally { if (alive) uploading.value = false }
}
onBeforeUnmount(() => { alive = false })
</script>
<style scoped>
.task-fields { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
@media(max-width:600px) { .task-fields { grid-template-columns:1fr; gap:0; } }
</style>
