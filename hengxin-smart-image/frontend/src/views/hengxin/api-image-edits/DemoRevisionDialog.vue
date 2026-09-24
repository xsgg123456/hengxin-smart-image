<template>
  <ElDialog v-model="open" title="修改这张结果 · 本地演示" width="min(1380px, 96vw)" align-center append-to-body destroy-on-close :close-on-click-modal="false" :show-close="!busy">
    <AnnotationEditor v-if="open && item?.result" ref="editor" :draft-key="draftKey" :load-original="loadOriginal" :base-label="`本次基于 V${item.result.version || 1} 修改`" :limit="4000" :disabled="busy" @submit="submit" />
    <ElSelect v-model="scenario" aria-label="模拟修改结果" :disabled="busy"><ElOption label="修改成功" value="success" /><ElOption label="重试耗尽后失败" value="partial" /></ElSelect>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" />
    <template #footer><ElButton :disabled="busy" @click="open = false">取消</ElButton><ElButton type="primary" :loading="busy" @click="editor?.preview()">预览提交内容</ElButton></template>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import AnnotationEditor, { type PreparedAnnotation } from '../components/annotation/AnnotationEditor.vue'
import { forgetAnnotationDraft } from '../components/annotation/annotation-drafts'
import { readImage } from '../download-helpers'
import { requestRevision, type EditTask, type Scenario } from './preview-state'
const open = defineModel<boolean>({ required: true })
const props = defineProps<{ task: EditTask; index: number }>()
const item = computed(() => props.task.items[props.index])
const draftKey = computed(() => JSON.stringify(['api-demo', props.task.id, props.index, item.value?.result?.version || 1]))
const editor = ref<InstanceType<typeof AnnotationEditor>>(), scenario = ref<Scenario>('success'), error = ref(''), busy = ref(false)
async function loadOriginal() {
  if (!item.value?.result) throw new Error('没有成品原图')
  const image = await readImage(item.value.result.url)
  return new Blob([image.data], { type: image.mime })
}
async function submit(value: PreparedAnnotation) {
  if (busy.value) return
  busy.value = true; error.value = ''; const key = draftKey.value
  try {
    const file = value.file
    const url = file ? await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = reject; reader.readAsDataURL(file) }) : undefined
    requestRevision(props.task, props.index, value.text, file && url ? { name: file.name, url } : undefined, scenario.value)
    forgetAnnotationDraft(key); open.value = false
  } catch (reason) { error.value = reason instanceof Error ? reason.message : '提交失败，请重试' }
  finally { busy.value = false }
}
</script>
