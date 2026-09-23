<template>
  <UploadInteraction :disabled="disabled || draft.locked()" @files="receiveFiles" @error="state.error = $event">
    <ElAlert title="前 N 张是原图，最后一张是共用素材" description="按原图顺序添加，再添加一张素材。可拖动排序，或点击“设为素材”。" type="info" show-icon :closable="false" />
    <ElUpload class="hx-gap" :class="{ compact: state.images.length }" drag multiple accept="image/jpeg,image/png,image/webp" :disabled="disabled || draft.locked()" :auto-upload="false" :show-file-list="false" :on-change="addFile">
      <div class="hx-upload-icon"><ArtSvgIcon icon="ri:upload-cloud-2-line" /></div><strong>拖入图片，或点击选择文件</strong><p>JPG / PNG / WebP · 每张不超过 10 MiB · 最多 20 张原图 + 1 张素材</p>
    </ElUpload>
    <div v-if="state.images.length" class="sequence-grid hx-gap">
      <div v-for="(picture, index) in state.images" :key="picture.id" class="sequence-card" :class="{ material: index === state.images.length - 1 }" :draggable="!disabled && !draft.locked()" @dragstart="dragIndex = index" @dragend="dragIndex = null" @dragover.prevent @drop.prevent="drop(index)">
        <div class="sequence-label"><ElTag :type="index === state.images.length - 1 ? 'warning' : 'info'" size="small">{{ index === state.images.length - 1 ? '共用素材 · 最后一张' : `原图 ${index + 1}` }}</ElTag><ArtSvgIcon icon="ri:draggable" /></div>
        <div class="sequence-picture"><PicturePreview :picture="picture" :pictures="state.images" :index="index" title="输入图片" /></div>
        <p :title="picture.name">{{ picture.name }}</p><ElTag size="small" :type="picture.state === 'failed' ? 'danger' : picture.state === 'ready' ? 'success' : 'info'">{{ uploadLabels[picture.state] }}</ElTag>
        <p v-if="picture.error" class="upload-error">{{ picture.error }}</p>
        <div class="sequence-actions"><ElButton size="small" :disabled="disabled || draft.locked() || index === 0" @click="draft.move(index, index - 1)">前移</ElButton><ElButton size="small" :disabled="disabled || draft.locked() || index === state.images.length - 1" @click="draft.move(index, index + 1)">后移</ElButton></div>
        <div class="sequence-actions"><ElButton text size="small" type="primary" :disabled="disabled || draft.locked() || index === state.images.length - 1" @click="draft.move(index, state.images.length - 1)">设为素材</ElButton><ElButton v-if="picture.state === 'failed'" text size="small" :disabled="disabled || draft.locked()" @click="draft.retry(picture)">重传</ElButton><ElButton text size="small" type="danger" :disabled="disabled || draft.locked() || ['uploading', 'removing'].includes(picture.state)" @click="draft.remove(picture)">移除</ElButton></div>
      </div>
    </div>
    <p class="hx-footnote">上传全部完成后才可提交。切换页面会保留本次草稿与上传状态。</p>
  </UploadInteraction>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import type { UploadFile } from 'element-plus'
import UploadInteraction from '../components/UploadInteraction.vue'
import PicturePreview from '../components/PicturePreview.vue'
import type { createDraft } from './real-draft'
const { draft, disabled } = defineProps<{ disabled: boolean; draft: ReturnType<typeof createDraft> }>()
const state = draft.state, dragIndex = ref<number | null>(null)
const uploadLabels = { uploading: '上传中', ready: '上传完成', failed: '上传失败', removing: '清理中' }
function receiveFiles(files: File[]) { if (!disabled && !draft.locked()) files.forEach(file => draft.add(file)) }
function addFile(file: UploadFile) { if (file.raw) receiveFiles([file.raw]) }
function drop(to: number) { if (!disabled && !draft.locked() && dragIndex.value !== null) draft.move(dragIndex.value, to); dragIndex.value = null }
</script>
<style scoped>
.sequence-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }
.compact :deep(.el-upload-dragger) { padding:12px; }
.compact .hx-upload-icon { display:none; }
.compact p { margin:4px 0 0; }
.sequence-card { padding:10px; border:1px solid var(--default-border); border-radius:10px; min-width:0; }
.sequence-card.material { border-color:var(--el-color-warning); background:var(--el-color-warning-light-9); }
.sequence-label,.sequence-actions { display:flex; align-items:center; justify-content:space-between; gap:4px; }
.sequence-label { margin-bottom:10px; color:var(--art-gray-500); }
.sequence-picture { height:135px; }
.sequence-card p { font-size:12px; margin:10px 0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.sequence-actions { margin-top:6px; flex-wrap:wrap; }
.sequence-actions .el-button { margin:0; }
@media(max-width:600px) { .sequence-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
</style>

<style scoped>.sequence-card .upload-error { white-space:normal; overflow-wrap:anywhere; color:var(--el-color-danger); }</style>
