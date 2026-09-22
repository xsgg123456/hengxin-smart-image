<template>
  <div ref="surface" class="image-upload" @dragover.prevent @drop.prevent="dropFiles">
    <ElUpload v-if="!compact" :key="uploadGeneration" ref="upload" :drag="!sortable" :multiple="maxCount !== 1" accept="image/png,image/jpeg,image/webp"
      :auto-upload="false" :show-file-list="false" :disabled="disabled || examplesLoading" :on-change="onChange">
      <ElButton v-if="sortable" :disabled="disabled || examplesLoading">{{ buttonLabel || '上传图片' }}</ElButton>
      <template v-else>
        <div class="hx-upload-icon"><ArtSvgIcon icon="ri:upload-cloud-2-line" /></div>
        <strong>点击上传，或将图片拖到这里</strong><p>{{ label || descriptions[mode] }}</p>
        <small>JPG / PNG / WebP · 单张不超过 10 MiB · 每组最多 {{ maxCount ?? 20 }} 张</small>
      </template>
    </ElUpload>
    <ElButton v-if="!compact && isMockMode && !hideExamples" text type="primary" :disabled="disabled" :loading="examplesLoading" @click="example">
      {{ exampleLabel || '使用示例素材' }}
    </ElButton>
    <p v-if="!compact" class="hx-footnote">{{ isDemoMode ? 'Demo 图片保存在本机浏览器；示例按钮会替换当前选择。' : isMockMode ? `模拟接收，仅本次页面有效。${hideExamples ? '' : '示例按钮将替换当前图片。'}` : '图片上传后保存在服务器；移除仅取消当前选择。' }}
      <template v-if="sortable">JPG / PNG / WebP · 单张不超过 10 MiB · 每组最多 {{ maxCount ?? 20 }} 张</template>
    </p>
    <div v-if="compact" class="compact-toolbar"><span>已添加 {{ entries.length }} 张</span><span>点击图片放大 · 拖入可继续添加</span></div>
    <input ref="compactInput" hidden type="file" :multiple="maxCount !== 1" accept="image/png,image/jpeg,image/webp" :disabled="disabled || examplesLoading" @change="pickFiles" />
    <div v-if="entries.length" :class="sortable ? 'hx-editor-pictures' : 'compact-grid'">
      <div v-for="(entry, index) in visibleEntries" :key="entry.id" :class="sortable ? 'picture-card' : 'compact-picture'">
        <PicturePreview :picture="entry" :pictures="entries" :index="index" title="本次上传图片" :style="sortable ? { width: '100%', height: '130px' } : { width: '100%', height: '104px' }" />
        <section class="picture-meta">
          <span :title="entry.name">{{ entry.name }}</span>
          <small :class="{ 'upload-error': entry.state === 'failed' }" role="status">
            {{ entry.state === 'checking' ? '校验中…' : entry.state === 'uploading' ? '接收中…' : entry.state === 'failed' ? entry.error : isMockMode ? '模拟已接收' : '已接收' }}
          </small>
        </section>
        <div class="picture-actions">
          <ElButton v-if="!isMockMode && entry.picture" text :loading="downloading.has(entry.id)" :aria-label="`下载图片 ${index + 1}`" @click="download(entry.id, entry.picture)">下载</ElButton>
          <ElButton v-if="sortable && maxCount !== 1" text :disabled="disabled || examplesLoading || index === 0" :aria-label="`前移图片 ${index + 1}`" @click="move(index, -1)">前移</ElButton>
          <ElButton v-if="sortable && maxCount !== 1" text :disabled="disabled || examplesLoading || index === entries.length - 1" :aria-label="`后移图片 ${index + 1}`" @click="move(index, 1)">后移</ElButton>
          <ElButton v-if="entry.state === 'failed'" text type="primary" :disabled="disabled || examplesLoading" :aria-label="`重试图片 ${index + 1}`" @click="retry(entry.id)">重试</ElButton>
          <button v-if="compact" class="compact-remove" type="button" :disabled="disabled" :aria-label="`移除图片 ${index + 1}`" @click="remove(entry.id)"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 4 8 8M12 4l-8 8" /></svg></button>
          <ElButton v-else text type="danger" :disabled="disabled" :aria-label="`移除图片 ${index + 1}`" @click="remove(entry.id)">移除</ElButton>
        </div>
      </div>
      <button v-if="compact" type="button" class="compact-add" :disabled="disabled || examplesLoading || entries.length >= (maxCount ?? 20)" @click="compactInput?.click()"><svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" stroke-width="1.5" /></svg><span>{{ entries.length >= (maxCount ?? 20) ? '已达数量上限' : '添加图片' }}</span></button>
    </div>
    <div v-if="compact" class="compact-footer"><span>JPG / PNG / WebP · 单张 ≤ 10 MiB · 最多 {{ maxCount ?? 20 }} 张</span><ElButton v-if="canCollapse" text type="primary" :aria-expanded="expanded" @click="expanded = !expanded">{{ expanded ? '收起' : `展开全部 · 共 ${entries.length} 张` }}</ElButton></div>
    <ElAlert v-if="error" :title="error" type="error" closable show-icon class="hx-gap" @close="error = ''" />
  </div>
</template>
<script setup lang="ts">
import PicturePreview from './PicturePreview.vue'
import { computed, ref, watch } from 'vue'
import { useElementSize } from '@vueuse/core'
import type { UploadFile, UploadInstance } from 'element-plus'
import type { Mode, Picture } from '@/types/hengxin'
import { isMockMode, isDemoMode } from '@/api/hengxin/client'
import { useImageUpload } from '../use-image-upload'
import { downloadPicture } from '../download'

const props = defineProps<{ mode: Mode; disabled?: boolean; label?: string; sortable?: boolean; exampleCount?: number; exampleLabel?: string; maxCount?: number; buttonLabel?: string; hideExamples?: boolean }>()
const model = defineModel<Picture[]>({ required: true })
const emit = defineEmits<{ blocked: [value: boolean]; example: [] }>()
const upload = ref<UploadInstance>()
const uploadGeneration = ref(0)
const descriptions = { wallpaper: '上传希望放入手机屏幕的新壁纸', product: '上传希望替换到模板中的商品图片', text: '上传需要替换文字的商品图片' }
const { entries, error, blocked, examplesLoading, add, remove, move, retry, useExamples } = useImageUpload(model, props)
const surface = ref<HTMLElement>(), compactInput = ref<HTMLInputElement>()
const { width } = useElementSize(surface)
const compact = computed(() => !props.sortable && entries.value.length > 0)
const expanded = ref(false)
const limit = computed(() => Math.max(1, Math.floor((width.value + 12) / 116) * 2 - 1))
const canCollapse = computed(() => compact.value && entries.value.length > limit.value && entries.value.every(entry => entry.state === 'ready'))
const visibleEntries = computed(() => canCollapse.value && !expanded.value ? entries.value.slice(0, limit.value) : entries.value)
watch(compact, () => { expanded.value = false })
async function pickFiles(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  await Promise.all(files.map(add))
}
async function dropFiles(event: DragEvent) {
  if (event.target instanceof Element && event.target.closest('.el-upload')) return
  if (!compact.value || props.disabled || examplesLoading.value) return
  await Promise.all(Array.from(event.dataTransfer?.files ?? []).map(add))
}
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
.compact-toolbar, .compact-footer { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px; font-size:12px; color:var(--art-gray-600); }
.compact-toolbar { margin-bottom:12px; }
.compact-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(min(104px,100%),104px)); gap:12px; }
.compact-picture { position:relative; min-width:0; }
.compact-picture .picture-meta { margin-top:6px; }
.compact-picture .compact-remove { position:absolute; top:4px; right:4px; display:grid; place-items:center; width:24px; height:24px; padding:0; border:0; border-radius:50%; background:var(--el-bg-color); color:var(--el-text-color-primary); cursor:pointer; }
.compact-remove svg { width:16px; height:16px; fill:none; stroke:currentColor; stroke-width:1.5; }
.compact-remove:hover { color:var(--el-color-danger); }
.compact-remove:focus-visible { outline:2px solid var(--el-color-primary); outline-offset:2px; }
.compact-remove:disabled { cursor:not-allowed; opacity:.5; }
.compact-add { height:104px; display:flex; flex-direction:column; gap:8px; align-items:center; justify-content:center; background:var(--el-fill-color-light); border:1px dashed var(--el-border-color); border-radius:8px; color:var(--el-color-primary); cursor:pointer; font:inherit; font-size:12px; }
.compact-add:focus-visible { outline:2px solid var(--el-color-primary); outline-offset:2px; }
.compact-add:disabled { cursor:not-allowed; color:var(--el-text-color-disabled); }
.compact-footer { margin-top:10px; }
.picture-card { min-width: 0; }
.picture-meta { min-width: 0; max-width: 220px; }
.picture-meta span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
.picture-meta small { display: block; font-size: 11px; color: var(--art-gray-600); overflow-wrap: anywhere; }
.picture-meta .upload-error { color: var(--el-color-danger); }
.picture-actions { display: flex; flex-wrap: wrap; gap: 2px; }
.picture-actions .el-button + .el-button { margin-left: 0; }
.hx-source { flex-wrap: wrap; }
</style>
