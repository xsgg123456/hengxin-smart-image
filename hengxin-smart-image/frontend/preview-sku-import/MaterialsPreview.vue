<template>
  <ElCard class="art-card hx-section" shadow="never">
    <div class="section-heading"><h2>图需资料</h2><ElTag type="info">至少提供一份</ElTag></div>
    <p class="hx-muted hx-gap">至少上传一份资料，每类支持多份，单份不超过 500 MB。PPT/PPTX 自动归入图片需求文件，其他附件归入竞品分析表格。</p>
    <div class="material-grid">
      <div v-for="kind in kinds" :key="kind.key" class="material-card" :data-kind="kind.key">
        <div class="section-heading"><h3>{{ kind.label }}</h3><ElTag v-if="group(kind.key).length" size="small" type="info">{{ group(kind.key).length }} 份</ElTag></div>
        <div v-for="file in group(kind.key)" :key="file.id" class="import-file" :data-file-id="file.id">
          <div class="file-details"><ElIcon class="file-symbol"><Document /></ElIcon><div><p class="file-name">{{ file.filename }}</p><p class="hx-muted">{{ formatAttachmentSize(file.size) }} · {{ file.local ? '手动添加' : '需求附件' }}</p></div></div>
          <template v-if="file.state === 'importing'"><ElProgress :percentage="file.progress" /><p class="hx-muted" role="status">正在导入…</p></template>
          <div v-else class="file-actions">
            <span :class="file.state === 'failed' ? 'file-failed' : 'file-ready'">{{ file.state === 'failed' ? '导入失败，请重试' : '已就绪' }}</span>
            <div><ElButton v-if="file.state === 'failed'" link type="primary" :disabled="disabled" @click="$emit('retry', file)">重试</ElButton><ElButton v-else link type="primary" @click="$emit('download', file)">下载</ElButton><ElButton link type="danger" :disabled="disabled" @click="$emit('remove', file)">移除</ElButton></div>
          </div>
        </div>
        <ElUpload drag multiple :auto-upload="false" :show-file-list="false" :disabled="disabled" :on-change="file => selected(file, kind.key)">
          <div class="upload-copy"><strong>{{ group(kind.key).length ? '继续添加文件' : `点击选择或拖入${kind.label}` }}</strong><span>支持多份 · 单份不超过 500 MB</span></div>
        </ElUpload>
      </div>
    </div>
    <p class="review-notice">提交后先由图需审核，审核通过后才能继续 AI 设计；资料不完整时退回提交人修改。</p>
  </ElCard>
</template>
<script setup lang="ts">
import { Document } from '@element-plus/icons-vue'
import type { UploadFile } from 'element-plus'
import { formatAttachmentSize } from '@/api/overseas/attachment-download'
import type { PreviewFile } from './fixtures'
const props = defineProps<{ files: PreviewFile[]; disabled?: boolean }>()
const emit = defineEmits<{ add: [file: File, kind: PreviewFile['kind']]; retry: [file: PreviewFile]; remove: [file: PreviewFile]; download: [file: PreviewFile] }>()
const kinds = [{ key: 'requirement', label: '图片需求文件' }, { key: 'competitor', label: '竞品分析表格' }] as const
const group = (kind: PreviewFile['kind']) => props.files.filter(f => f.kind === kind)
function selected(file: UploadFile, kind: PreviewFile['kind']) { if (file.raw) emit('add', file.raw, kind) }
</script>
<style scoped>
h2,h3{font-size:14px}p{overflow-wrap:anywhere;white-space:pre-wrap}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}
.material-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;margin-top:20px}.material-card{border:1px solid #e4e7ed;border-radius:10px;padding:18px;min-width:0}.material-card :deep(.el-upload){display:block;width:100%}.material-card :deep(.el-upload-dragger){width:100%;padding:28px 12px;background:#fafbff;margin-top:12px}.upload-copy{display:flex;flex-direction:column;gap:14px;font-size:13px;color:#687891;white-space:normal}.upload-copy strong{font-weight:500}.upload-copy span{font-size:12px;color:#8b98aa}.review-notice{margin-top:20px;padding:16px;border-radius:8px;background:#f4f7ff;color:#7789a8;font-size:13px;line-height:1.8}
.import-file{margin-top:14px;padding:14px 0;border-bottom:1px solid var(--el-border-color-lighter)}.file-details{display:flex;gap:10px;align-items:flex-start}.file-details>div{min-width:0}.file-symbol{color:var(--el-color-primary);margin-top:3px;flex-shrink:0}.file-name{font-size:13px;line-height:1.6}.file-details .hx-muted{font-size:12px;margin-top:4px}.file-actions{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:10px;font-size:12px}.file-ready{color:var(--el-color-success)}.file-failed{color:var(--el-color-danger)}.el-progress{margin-top:12px}
@media(max-width:800px){.material-grid{grid-template-columns:1fr}}
</style>
