<template>
  <div class="pdf-reader">
    <div class="pdf-tools"><ElButton :disabled="page <= 1 || busy" @click="page--">上一页</ElButton><span>{{ page }} / {{ pages || '—' }}</span><ElButton :disabled="page >= pages || busy" @click="page++">下一页</ElButton>
      <ElButton :disabled="zoom <= .5 || busy" aria-label="缩小" @click="zoom -= .25">−</ElButton><span>{{ Math.round(zoom * 100) }}%</span><ElButton :disabled="zoom >= 2 || busy" aria-label="放大" @click="zoom += .25">＋</ElButton><ElButton :disabled="busy" @click="zoom = 1">适合宽度</ElButton><span>PDF 原件</span>
    </div>
    <p v-if="busy" role="status">正在读取 PDF…</p>
    <ElAlert v-if="error" :title="error" type="warning" :closable="false" />
    <div class="pdf-layout"><aside v-if="documentRef" class="pdf-thumbnails" aria-label="PDF 页缩略图"><button v-for="number in thumbnailPages" :key="number" :class="{ selected: page === number }" :aria-label="`跳转第 ${number} 页`" :aria-current="page === number ? 'page' : undefined" @click="page = number"><MaterialPdfThumbnail :document="documentRef" :page="number" /><span>第 {{ number }} 页</span></button><p v-if="pages > 8">按上方翻页切换下一组</p></aside><div ref="viewport" class="pdf-paper" tabindex="0" aria-label="PDF 页面，可滚动阅读"><canvas v-show="!error" ref="canvas" :aria-label="`PDF 第 ${page} 页`" /></div></div>
  </div>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, shallowRef, watch, nextTick } from 'vue'
import type { PDFDocumentLoadingTask, PDFDocumentProxy, RenderTask } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { IdentityError } from '@/api/identity/request'
import { materialError, type Material, type MaterialsApi } from '@/api/overseas/materials'
import MaterialPdfThumbnail from './MaterialPdfThumbnail.vue'
const props = defineProps<{ file: Material; api: MaterialsApi }>()
declare const __PDF_ASSET_BASE__: string
const emit = defineEmits<{ failure: [reason: unknown] }>()
const canvas = ref<HTMLCanvasElement>(), viewport = ref<HTMLElement>(), page = ref(1), pages = ref(0), zoom = ref(1), busy = ref(false), error = ref('')
const documentRef = shallowRef<PDFDocumentProxy>()
const thumbnailPages = computed(() => { const start = Math.floor((page.value - 1) / 8) * 8 + 1; return Array.from({ length: Math.min(8, pages.value - start + 1) }, (_, i) => start + i) })
let generation = 0, rendering = 0, controller: AbortController | undefined, document: PDFDocumentProxy | undefined, loading: PDFDocumentLoadingTask | undefined, render: RenderTask | undefined
function clear() { ++generation; ++rendering; controller?.abort(); render?.cancel(); render = undefined; void loading?.destroy(); loading = undefined; document = undefined; documentRef.value = undefined; pages.value = 0 }
async function draw() {
  if (!document || !canvas.value || !viewport.value) return
  const id = ++rendering, current = generation, doc = document
  const prior = render; render = undefined; prior?.cancel(); busy.value = true
  try {
    await prior?.promise.catch(() => undefined)
    const pdfPage = await doc.getPage(page.value)
    if (id !== rendering || current !== generation || !canvas.value || !viewport.value) return
    const original = pdfPage.getViewport({ scale: 1 })
    const scale = Math.min(Math.max(200, viewport.value.clientWidth - 48) / original.width, 1.5) * zoom.value
    const view = pdfPage.getViewport({ scale }), context = canvas.value.getContext('2d')
    if (!context) throw Error('浏览器无法绘制 PDF，请下载原文件查看')
    const ratio = Math.min(window.devicePixelRatio || 1, 2, 4096 / Math.max(view.width, view.height))
    canvas.value.width = Math.ceil(view.width * ratio); canvas.value.height = Math.ceil(view.height * ratio)
    canvas.value.style.width = `${view.width}px`; canvas.value.style.height = `${view.height}px`
    render = pdfPage.render({ canvas: canvas.value, canvasContext: context, viewport: view, transform: [ratio, 0, 0, ratio, 0, 0] })
    await render.promise
  } catch (reason) { if (id === rendering && current === generation) error.value = `${materialError(reason)}；可下载原件查看` }
  finally { if (id === rendering && current === generation) busy.value = false }
}
async function load() {
  clear(); const current = generation; controller = new AbortController(); busy.value = true; error.value = ''; page.value = 1; zoom.value = 1
  try {
    const blob = await props.api.content(props.file.id, false, controller.signal), bytes = await blob.arrayBuffer()
    const pdf = await import('pdfjs-dist')
    if (current !== generation) return
    pdf.GlobalWorkerOptions.workerSrc = workerUrl
    const task = pdf.getDocument({ data: bytes, useSystemFonts: true, cMapUrl: __PDF_ASSET_BASE__ + 'cmaps/', cMapPacked: true, standardFontDataUrl: __PDF_ASSET_BASE__ + 'standard_fonts/', wasmUrl: __PDF_ASSET_BASE__ + 'wasm/' })
    loading = task
    const value = await task.promise
    if (current !== generation) { await task.destroy(); return }
    document = value; documentRef.value = value; pages.value = value.numPages; await nextTick(); await draw()
  } catch (reason) {
    if (current !== generation) return
    error.value = `${materialError(reason)}；可下载原文件或查看解析文本`
    if (reason instanceof IdentityError && [401, 403, 404].includes(reason.status)) emit('failure', reason)
  } finally { if (current === generation) busy.value = false }
}
watch(() => props.file.id, load, { immediate: true }); watch([page, zoom], draw); onUnmounted(clear)
</script>
<style scoped>
.pdf-tools { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; padding: 12px; background: #f6f8fc; color: #7b899d; font-size: 12px; }.pdf-tools .el-button { margin: 0; }
.pdf-paper { overflow: auto; background: #edf0f5; padding: 24px; max-height: min(650px, 55vh); min-height: 240px; }canvas { display: block; margin: 0 auto; background: white; box-shadow: 0 3px 14px #23345418; }
.pdf-layout { display: grid; grid-template-columns: 128px minmax(0, 1fr); }.pdf-thumbnails { background: #f4f6fa; padding: 10px; overflow: auto; max-height: min(650px, 55vh); }.pdf-thumbnails button { display: block; width: 100%; padding: 5px; margin-bottom: 10px; border: 2px solid transparent; border-radius: 5px; background: white; cursor: pointer; }.pdf-thumbnails button.selected { border-color: var(--el-color-primary); }.pdf-thumbnails span,.pdf-thumbnails p { display: block; font-size: 11px; margin-top: 5px; color: #718099; }@media(max-width: 600px) { .pdf-layout { grid-template-columns: 1fr; }.pdf-thumbnails { display: none; } }
</style>
