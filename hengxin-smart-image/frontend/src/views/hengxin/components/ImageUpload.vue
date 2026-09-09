<template>
  <div class="image-upload">
    <ElUpload :key="uploadGeneration" ref="upload" :drag="!sortable" multiple accept="image/png,image/jpeg,image/webp"
      :auto-upload="false" :show-file-list="false" :disabled="disabled || examplesLoading" :on-change="onChange">
      <ElButton v-if="sortable" :disabled="disabled || examplesLoading">上传图片</ElButton>
      <template v-else>
        <div class="hx-upload-icon"><ArtSvgIcon icon="ri:upload-cloud-2-line" /></div>
        <strong>点击上传，或将图片拖到这里</strong><p>{{ label || descriptions[mode] }}</p>
        <small>JPG / PNG / WebP · 单张不超过 10 MiB · 每组最多 20 张</small>
      </template>
    </ElUpload>
    <ElButton v-if="isMockMode" text type="primary" :disabled="disabled" :loading="examplesLoading" @click="example">
      {{ exampleLabel || '使用示例素材' }}
    </ElButton>
    <p class="hx-footnote">{{ isMockMode ? '模拟接收，仅本次页面有效。示例按钮将替换当前图片。' : '图片上传后保存在服务器；移除仅取消当前选择。' }}
      <template v-if="sortable">JPG / PNG / WebP · 单张不超过 10 MiB · 每组最多 20 张</template>
    </p>
    <div v-if="entries.length" :class="sortable ? 'hx-editor-pictures' : 'hx-source-list'">
      <div v-for="(entry, index) in entries" :key="entry.id" :class="sortable ? 'picture-card' : 'hx-source'">
        <ElImage :src="entry.url" :alt="entry.name" fit="cover" :preview-src-list="entries.map(e => e.url)"
          :initial-index="index" preview-teleported :style="sortable ? { width: '100%', height: '90px' } : { width: '44px', height: '48px', flexShrink: 0 }" />
        <section class="picture-meta">
          <span :title="entry.name">{{ entry.name }}</span>
          <small :class="{ 'upload-error': entry.state === 'failed' }" role="status">
            {{ entry.state === 'checking' ? '校验中…' : entry.state === 'uploading' ? '接收中…' : entry.state === 'failed' ? entry.error : isMockMode ? '模拟已接收' : '已接收' }}
          </small>
        </section>
        <div class="picture-actions">
          <ElButton v-if="!isMockMode && entry.picture" text :loading="downloading.has(entry.id)" :aria-label="`下载图片 ${index + 1}`" @click="download(entry.id, entry.picture)">下载</ElButton>
          <ElButton v-if="sortable" text :disabled="disabled || examplesLoading || index === 0" :aria-label="`前移图片 ${index + 1}`" @click="move(index, -1)">前移</ElButton>
          <ElButton v-if="sortable" text :disabled="disabled || examplesLoading || index === entries.length - 1" :aria-label="`后移图片 ${index + 1}`" @click="move(index, 1)">后移</ElButton>
          <ElButton v-if="entry.state === 'failed'" text type="primary" :disabled="disabled || examplesLoading" :aria-label="`重试图片 ${index + 1}`" @click="retry(entry.id)">重试</ElButton>
          <ElButton text type="danger" :disabled="disabled" :aria-label="`移除图片 ${index + 1}`" @click="remove(entry.id)">移除</ElButton>
        </div>
      </div>
    </div>
    <ElAlert v-if="error" :title="error" type="error" closable show-icon class="hx-gap" @close="error = ''" />
  </div>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue'
import type { UploadFile, UploadInstance } from 'element-plus'
import type { Mode, Picture } from '@/types/hengxin'
import { isMockMode } from '@/api/hengxin/client'
import { useImageUpload } from '../use-image-upload'
import { downloadPicture } from '../download'

const props = defineProps<{ mode: Mode; disabled?: boolean; label?: string; sortable?: boolean; exampleCount?: number; exampleLabel?: string }>()
const model = defineModel<Picture[]>({ required: true })
const emit = defineEmits<{ blocked: [value: boolean]; example: [] }>()
const upload = ref<UploadInstance>()
const uploadGeneration = ref(0)
const descriptions = { wallpaper: '上传希望放入手机屏幕的新壁纸', product: '上传希望替换到模板中的商品图片', text: '上传需要替换文字的商品图片' }
const { entries, error, blocked, examplesLoading, add, remove, move, retry, useExamples } = useImageUpload(model, props)
watch(blocked, value => emit('blocked', value), { immediate: true, flush: 'sync' })
const downloading = ref(new Set<number>())
async function download(id: number, picture: Picture) {
  if (downloading.value.has(id)) return
  downloading.value.add(id)
  try { await downloadPicture(picture) }
  finally { downloading.value.delete(id) }
}
let pendingCallbacks = 0
async function onChange(file: UploadFile) {
  if (!file.raw) return
  pendingCallbacks++
  try { await add(file.raw) }
  finally {
    pendingCallbacks--
    if (!pendingCallbacks) { upload.value?.clearFiles(); uploadGeneration.value++ }
  }
}
async function example() { if (await useExamples()) emit('example') }
</script>
<style scoped>
.image-upload { width: 100%; min-width: 0; }
.picture-card { min-width: 0; }
.picture-meta { min-width: 0; max-width: 220px; }
.picture-meta span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
.picture-meta small { display: block; font-size: 11px; color: var(--art-gray-600); overflow-wrap: anywhere; }
.picture-meta .upload-error { color: var(--el-color-danger); }
.picture-actions { display: flex; flex-wrap: wrap; gap: 2px; }
.picture-actions .el-button + .el-button { margin-left: 0; }
.hx-source { flex-wrap: wrap; }
</style>
