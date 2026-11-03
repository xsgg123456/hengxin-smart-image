<template>
  <ElCard class="art-card hx-section" shadow="never">
    <div class="section-heading"><h2>图需资料</h2><ElTag type="info">至少提供一份</ElTag></div>
    <p class="hx-muted hx-gap">至少上传一份资料，每类支持多份，单份不超过 500 MB。PPT/PPTX 自动归入图片需求文件，其他需求附件归入竞品分析表格。</p>
    <ElAlert v-if="error" :title="error" type="error" :closable="false" class="hx-gap" />
    <div class="material-grid">
      <div v-for="kind in kinds" :key="kind.key" class="material-card" :data-kind="kind.key">
        <div class="section-heading"><h3>{{ kind.label }}</h3><ElTag v-if="group(kind.key).length" size="small" type="info">{{ group(kind.key).length }} 份</ElTag></div>
        <div v-for="file in group(kind.key)" :key="file.id" class="import-file" :data-file-id="file.id">
          <div class="file-details"><ElIcon class="file-symbol"><Document /></ElIcon><div><p class="file-name">{{ file.name }}</p><p class="hx-muted">{{ formatAttachmentSize(file.size) }} · {{ file.importId ? '需求附件' : '手动添加' }}</p></div></div>
          <template v-if="file.state === 'running' || file.state === 'queued'"><ElProgress :percentage="file.progress" /><p class="hx-muted" role="status">{{ file.state === 'queued' ? '等待后台导入…' : '正在后台导入…' }}</p></template>
          <div class="file-actions"><span :class="file.state === 'failed' ? 'file-failed' : 'file-ready'">{{ file.state === 'failed' ? file.error || '导入失败，请重试' : file.state === 'ready' ? '已就绪' : '' }}</span><div>
            <ElButton v-if="file.state === 'failed'" link type="primary" :disabled="disabled || changing" @click="action('retry', file)">重试</ElButton>
            <AttachmentDownload v-if="file.materialId" :url="`/api/overseas/v1/materials/${encodeURIComponent(file.materialId)}/content`" :name="file.name" @failure="$emit('failure', $event)" />
            <ElButton link type="danger" :disabled="disabled || changing" @click="action('remove', file)">{{ ['queued','running'].includes(file.state) ? '取消导入' : '移除' }}</ElButton>
          </div></div>
        </div>
        <div v-for="file in uploads.filter(f => f.kind === kind.key)" :key="file.id" class="import-file"><p class="file-name">{{ file.file.name }}</p><ElProgress :percentage="file.progress" /><p role="status">{{ file.progress === 100 ? '正在保存上传原件…' : '正在上传…' }}</p><ElButton text type="danger" @click="file.controller.abort()">取消上传</ElButton></div>
        <ElUpload drag multiple :auto-upload="false" :show-file-list="false" :disabled="disabled || changing" :data-material-kind="kind.key" :on-change="file => selected(file, kind.key)">
          <div class="upload-copy"><strong>{{ group(kind.key).length ? '继续添加文件' : `点击选择或拖入${kind.label}` }}</strong><span>支持多份 · 单份不超过 500 MB</span></div>
        </ElUpload>
      </div>
    </div>
    <p class="review-notice">提交后先由图需审核，审核通过后才能继续 AI 设计；资料不完整时退回提交人修改。</p>
  </ElCard>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { Document } from '@element-plus/icons-vue'
import { ElMessageBox, type UploadFile } from 'element-plus'
import { materialError, validateFile, type MaterialKind, type MaterialsApi } from '@/api/overseas/materials'
import { IdentityError } from '@/api/identity/request'
import type { RequirementDraft } from '@/api/overseas/requirement-drafts'
import { formatAttachmentSize } from '@/api/overseas/attachment-download'
import AttachmentDownload from './AttachmentDownload.vue'
const props = defineProps<{ draft: RequirementDraft; api: MaterialsApi; disabled: boolean; change: (operation: 'retry' | 'cancel' | 'remove', id: string) => Promise<unknown>; refresh: () => Promise<unknown> }>()
const emit = defineEmits<{ busy: [value: boolean]; pending: [names: string[]]; failure: [reason: unknown] }>()
const kinds = [{ key: 'requirement', label: '图片需求文件' }, { key: 'competitor', label: '竞品分析表格' }] as const
const error = ref(''), changing = ref(false), uploads = ref<{ id: string; file: File; kind: MaterialKind; progress: number; controller: AbortController }[]>([])
let active = true
const files = computed(() => {
  const imports = props.draft.imports.filter(i => i.state !== 'cancelled')
  return [...imports.map(i => ({ id: i.id, importId: i.id, materialId: i.materialId, name: i.filename, size: i.size, kind: i.kind, state: i.state as string, progress: i.progress, error: i.error })),
    ...props.draft.materials.filter(m => !imports.some(i => i.materialId === m.id)).map(m => ({ id: m.id, importId: '', materialId: m.id, name: m.name, size: m.sizeBytes, kind: m.kind, state: 'ready', progress: 100, error: null }))]
})
const group = (kind: MaterialKind) => files.value.filter(f => f.kind === kind)
watch(() => uploads.value.map(f => f.file.name), names => { emit('busy', !!names.length); emit('pending', names) }, { flush: 'sync' })
function failed(reason: unknown) { error.value = materialError(reason); if (reason instanceof IdentityError && [401, 403].includes(reason.status)) emit('failure', reason) }
async function selected(value: UploadFile, kind: MaterialKind) {
  if (!value.raw || props.disabled || changing.value) return
  try { validateFile(value.raw, kind); if (files.value.length + uploads.value.length >= 100) throw Error('单次最多 100 份资料，请先移除多余附件') } catch (reason) { failed(reason); return }
  const upload = { id: crypto.randomUUID(), file: value.raw, kind, progress: 0, controller: new AbortController() }
  uploads.value.push(upload); error.value = ''
  try {
    await props.api.upload(value.raw, kind, n => { const row = uploads.value.find(f => f.id === upload.id); if (row) row.progress = n }, upload.controller.signal, props.draft.id)
    if (active) await props.refresh()
  } catch (reason) { if (active) failed(reason) }
  finally { if (active) uploads.value = uploads.value.filter(f => f.id !== upload.id) }
}
async function action(operation: 'retry' | 'remove', file: typeof files.value[number]) {
  if (props.disabled || changing.value) return
  changing.value = true; error.value = ''
  try {
    if (operation === 'remove') await ElMessageBox.confirm(`移除「${file.name}」？只移除当前草稿的附件。`, '移除附件', { type: 'warning', confirmButtonText: '确认移除', cancelButtonText: '取消' })
    if (!active || props.disabled) return
    await props.change(operation === 'retry' ? 'retry' : file.importId ? 'cancel' : 'remove', file.importId || file.materialId!)
  } catch (reason) { if (reason !== 'cancel' && reason !== 'close' && active) failed(reason) }
  finally { changing.value = false }
}
onUnmounted(() => { active = false; for (const file of uploads.value) file.controller.abort(); emit('busy', false) })
</script>
<style scoped>
h2,h3{font-size:14px}p{overflow-wrap:anywhere;white-space:pre-wrap}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}
.material-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;margin-top:20px}.material-card{border:1px solid #e4e7ed;border-radius:10px;padding:18px;min-width:0}.material-card :deep(.el-upload){display:block;width:100%}.material-card :deep(.el-upload-dragger){width:100%;padding:28px 12px;background:#fafbff;margin-top:12px}.upload-copy{display:flex;flex-direction:column;gap:14px;font-size:13px;color:#687891;white-space:normal}.upload-copy strong{font-weight:500}.upload-copy span{font-size:12px;color:#8b98aa}.review-notice{margin-top:20px;padding:16px;border-radius:8px;background:#f4f7ff;color:#7789a8;font-size:13px;line-height:1.8}
.import-file{margin-top:14px;padding:14px 0;border-bottom:1px solid var(--el-border-color-lighter)}.file-details{display:flex;gap:10px;align-items:flex-start}.file-details>div{min-width:0}.file-symbol{color:var(--el-color-primary);margin-top:3px;flex-shrink:0}.file-name{font-size:13px;line-height:1.6}.file-details .hx-muted{font-size:12px;margin-top:4px}.file-actions{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:10px;font-size:12px;flex-wrap:wrap}.file-actions>div{display:flex;flex-wrap:wrap;align-items:center;gap:8px}.file-ready{color:var(--el-color-success)}.file-failed{color:var(--el-color-danger);overflow-wrap:anywhere}.el-progress{margin-top:12px}
@media(max-width:800px){.material-grid{grid-template-columns:1fr}}
</style>
