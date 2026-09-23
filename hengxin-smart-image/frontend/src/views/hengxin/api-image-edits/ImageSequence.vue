<template>
  <UploadInteraction @files="receiveFiles" @error="error = $event">
    <ElAlert title="前 N 张是原图，最后一张是共用素材" description="例如修改 5 张套图：依次放入 5 张原图，第 6 张放素材。可以拖动排序，或点击“设为素材”。" type="info" show-icon :closable="false" />
    <ElUpload class="hx-gap" :class="{ compact: images.length }" drag multiple accept="image/jpeg,image/png,image/webp" :auto-upload="false" :show-file-list="false" :on-change="addFile">
      <div class="hx-upload-icon"><ArtSvgIcon icon="ri:upload-cloud-2-line" /></div>
      <strong>拖入图片，或点击选择文件</strong><p>JPG / PNG / WebP · 每张不超过 10 MiB · 最多 20 张原图 + 1 张素材</p>
    </ElUpload>
    <ElAlert v-if="error" class="hx-gap" :title="error" type="error" :closable="false" />
    <div v-if="images.length" class="sequence-grid hx-gap">
      <div v-for="(picture, index) in images" :key="picture.url + index" class="sequence-card" :class="{ material: index === images.length - 1 }" draggable="true" @dragstart="dragIndex = index" @dragend="dragIndex = null" @dragover.prevent @drop.prevent="drop(index)">
        <div class="sequence-label"><ElTag :type="index === images.length - 1 ? 'warning' : 'info'" size="small">{{ index === images.length - 1 ? '共用素材 · 最后一张' : `原图 ${index + 1}` }}</ElTag><ArtSvgIcon icon="ri:draggable" /></div>
        <div class="sequence-picture"><PicturePreview :picture="picture" :pictures="images" :index="index" title="输入图片" /></div>
        <p :title="picture.name">{{ picture.name }}</p>
        <div class="sequence-actions"><ElButton size="small" :disabled="index === 0" :aria-label="`前移第 ${index + 1} 张`" @click="move(index, index - 1)">前移</ElButton><ElButton size="small" :disabled="index === images.length - 1" :aria-label="`后移第 ${index + 1} 张`" @click="move(index, index + 1)">后移</ElButton></div>
        <div class="sequence-actions"><ElButton text size="small" type="primary" :disabled="index === images.length - 1" @click="move(index, images.length - 1)">设为素材</ElButton><ElButton text size="small" type="danger" :aria-label="`移除第 ${index + 1} 张`" @click="images.splice(index, 1)">移除</ElButton></div>
      </div>
    </div>
    <p v-if="images.length" class="hx-footnote">{{ Math.max(0, images.length - 1) }} 张原图 + 1 张素材 · 提交前请核对最后一张。调整顺序后角色标签会同步更新。</p>
  </UploadInteraction>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import type { UploadFile } from 'element-plus'
import type { Picture } from '@/types/hengxin'
import PicturePreview from '../components/PicturePreview.vue'
import UploadInteraction from '../components/UploadInteraction.vue'
import { preview } from './preview-state'
const images = defineModel<Picture[]>({ required: true })
const error = ref(''), dragIndex = ref<number | null>(null)
function receiveFiles(files: File[]) {
  error.value = ''
  files.forEach(addRawFile)
}
function addFile(file: UploadFile) { if (file.raw) receiveFiles([file.raw]) }
function addRawFile(raw: File) {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(raw.type) || !raw.size || raw.size > 10 * 1024 * 1024) { error.value = '请选择不超过 10 MiB 的 JPG、PNG 或 WebP 图片。'; return }
  if (images.value.length >= 21) { error.value = '最多添加 21 张图片（20 张原图和 1 张素材）。'; return }
  const picture = { name: raw.name, url: URL.createObjectURL(raw) }
  // 先按选择顺序占位，再验证解码，避免异步读取打乱原图/素材顺序。
  images.value.push(picture)
  const image = new Image(); preview.pendingUploads++
  image.onload = () => { preview.pendingUploads-- }
  image.onerror = () => {
    preview.pendingUploads--
    // 路由切换后仍清理共享草稿，不能向已卸载组件回写失效的 model。
    preview.images = preview.images.filter(value => value.url !== picture.url)
    URL.revokeObjectURL(picture.url); error.value = `${raw.name} 无法读取，请重新选择图片。`
  }
  image.src = picture.url
}
function move(from: number, to: number) {
  if (to < 0 || to >= images.value.length) return
  const [picture] = images.value.splice(from, 1)
  if (picture) images.value.splice(to, 0, picture)
}
function drop(to: number) { if (dragIndex.value !== null) move(dragIndex.value, to); dragIndex.value = null }
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
