<template>
  <ElCard class="art-card hx-section" shadow="never">
    <div class="section-heading"><h2>图需资料</h2><ElTag v-if="editable" type="info">至少提供一份</ElTag></div>
    <p v-if="editable" class="hx-muted hx-gap">至少一份解析成功的资料，每类一份，每份不超过 20 MiB。PDF 须包含可抽取文字；DOC 请另存为 DOCX 或 PDF。</p>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" class="hx-gap" />
    <div class="material-grid"><div v-for="kind in kinds" :key="kind.key" class="material-card">
      <h3>{{ kind.label }}</h3>
      <template v-if="file(kind.key)">
        <p class="file-name">{{ file(kind.key)?.name }} · {{ file(kind.key)?.status === 'ready' ? '解析成功' : '解析失败' }} · 第 {{ file(kind.key)?.version }} 版</p>
        <p v-if="file(kind.key)?.error" role="alert">{{ file(kind.key)?.error }}</p>
        <ElButton :disabled="locked" @click="preview = true">预览资料</ElButton>
        <ElButton v-if="editable && replaceable && file(kind.key)?.taskId" text type="danger" :disabled="locked" @click="detach(file(kind.key)!)">更换资料</ElButton>
        <template v-if="editable && !file(kind.key)?.taskId">
          <ElButton v-if="file(kind.key)?.status === 'failed'" :disabled="locked" @click="retry(file(kind.key)!)">重试解析</ElButton>
          <div class="hx-gap"><ElButton type="danger" text :disabled="locked" @click="remove(file(kind.key)!)">移除资料</ElButton></div>
        </template>
      </template>
      <ElUpload v-else-if="editable" drag :key="`${kind.key}-${inputKey}`" :auto-upload="false" :show-file-list="false" :accept="kind.accept" :disabled="locked" :on-change="selected => upload(selected, kind.key)">
        <div class="upload-copy"><strong>点击选择或拖入{{ kind.label }}</strong><span>{{ kind.accept }} · 单份不超过 20 MiB</span></div>
      </ElUpload>
      <p v-else class="hx-muted">未提供{{ kind.label }}</p>
      <template v-if="uploading === kind.key">
        <ElProgress :percentage="progress" />
        <p role="status">{{ progress === 100 ? '上传完成，正在解析…' : '正在上传…' }}</p>
        <ElButton @click="cancel">取消上传</ElButton>
      </template>
    </div></div>
    <p v-if="editable" class="review-notice">提交后先由设计人工审核，通过后才进入 AI 分析；资料不完整时退回运营修改。</p>
    <OverseasMaterialPreview v-model="preview" :files="files" :api="api" @failure="failed" />
  </ElCard>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElMessageBox, type UploadFile } from 'element-plus'
import { IdentityError } from '@/api/identity/request'
import { materialError, validateFile, type Material, type MaterialKind, type MaterialsApi } from '@/api/overseas/materials'
import OverseasMaterialPreview from './OverseasMaterialPreview.vue'
const files = defineModel<Material[]>({ required: true })
const props = defineProps<{ api: MaterialsApi; editable: boolean; disabled?: boolean; replaceable?: boolean }>()
const emit = defineEmits<{ busy: [value: boolean]; failure: [reason: unknown] }>()
const kinds = [{ key: 'requirement', label: '图片需求文件', accept: '.pdf,.docx' }, { key: 'competitor', label: '竞品分析表格', accept: '.xls,.xlsx,.csv' }] as const
const busy = ref(false), progress = ref(0), uploading = ref<MaterialKind>(), error = ref(''), preview = ref(false), inputKey = ref(0)
const locked = computed(() => busy.value || props.disabled), file = (kind: MaterialKind) => files.value.find(f => f.kind === kind)
let generation = 0, controller: AbortController | undefined
watch(busy, value => emit('busy', value), { flush: 'sync' })
function cancel() { ++generation; controller?.abort(); controller = undefined; busy.value = false; uploading.value = undefined; progress.value = 0; inputKey.value++ }
function failed(reason: unknown) {
  error.value = materialError(reason)
  if (reason instanceof IdentityError && reason.status === 409) files.value = []
  if (reason instanceof IdentityError && [401, 403, 404].includes(reason.status)) { files.value = []; preview.value = false; emit('failure', reason) }
}
async function upload(selected: UploadFile, kind: MaterialKind) {
  if (locked.value || !props.editable || !selected.raw || file(kind)) return
  try { validateFile(selected.raw, kind) } catch (reason) { failed(reason); inputKey.value++; return }
  const current = ++generation; controller = new AbortController(); error.value = ''; busy.value = true; uploading.value = kind; progress.value = 0
  try { const result = await props.api.upload(selected.raw, kind, value => { if (current === generation) progress.value = value }, controller.signal); if (current === generation) files.value = [...files.value, result] }
  catch (reason) { if (current === generation) failed(reason) }
  finally { if (current === generation) { busy.value = false; uploading.value = undefined; inputKey.value++ } }
}
async function retry(material: Material) {
  if (locked.value || !props.editable || material.taskId) return
  const current = ++generation; busy.value = true; error.value = ''
  try { const value = await props.api.retry(material.id); if (current === generation) files.value = files.value.map(f => f.id === value.id ? value : f) }
  catch (reason) { if (current === generation) failed(reason) }
  finally { if (current === generation) busy.value = false }
}
async function remove(material: Material) {
  if (locked.value || !props.editable || material.taskId) return
  const current = ++generation; busy.value = true; error.value = ''
  try {
    await ElMessageBox.confirm('移除后将无法再次读取该原件，确定移除？', '移除资料', { type: 'warning', confirmButtonText: '确认移除', cancelButtonText: '取消' })
    if (current !== generation || !props.editable) return
    await props.api.remove(material.id)
    if (current === generation) files.value = files.value.filter(f => f.id !== material.id)
  } catch (reason) { if (current === generation && reason !== 'cancel' && reason !== 'close') failed(reason) }
  finally { if (current === generation) busy.value = false }
}
function detach(material: Material) {
  if (!props.editable || !props.replaceable || locked.value) return
  files.value = files.value.filter(file => file.id !== material.id)
}
watch(() => props.editable, () => { cancel(); preview.value = false })
onUnmounted(cancel)
</script>
<style scoped>
h2 { font-size: 16px; }
h3 { font-size: 14px; margin-bottom: 12px; }
p { overflow-wrap: anywhere; white-space: pre-wrap; }
.file-name { margin-bottom: 12px; }
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.material-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; margin-top: 20px; }
.material-card { border: 1px solid #e4e7ed; border-radius: 10px; padding: 18px; min-width: 0; }
.material-card :deep(.el-upload) { display: block; width: 100%; }.material-card :deep(.el-upload-dragger) { width: 100%; padding: 28px 12px; background: #fafbff; }
.upload-copy { display: flex; flex-direction: column; gap: 14px; font-size: 13px; color: #687891; white-space: normal; }.upload-copy strong { font-weight: 500; }.upload-copy span { font-size: 12px; color: #8b98aa; }
.review-notice { margin-top: 20px; padding: 16px; border-radius: 8px; background: #f4f7ff; color: #7789a8; font-size: 13px; line-height: 1.8; }
@media(max-width: 800px) { .material-grid { grid-template-columns: 1fr; } }
</style>
