<template><canvas ref="canvas" :aria-label="`第 ${page} 页缩略图`" /></template>
<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import type { PDFDocumentProxy, RenderTask } from 'pdfjs-dist'
const props = defineProps<{ document: PDFDocumentProxy; page: number }>()
const canvas = ref<HTMLCanvasElement>()
let generation = 0, render: RenderTask | undefined
async function draw() {
  const id = ++generation, prior = render; render = undefined; prior?.cancel()
  try {
    await prior?.promise.catch(() => undefined)
    const page = await props.document.getPage(props.page)
    if (id !== generation || !canvas.value) return
    const view = page.getViewport({ scale: 96 / page.getViewport({ scale: 1 }).width })
    const context = canvas.value.getContext('2d')
    if (!context) return
    canvas.value.width = view.width; canvas.value.height = view.height
    render = page.render({ canvas: canvas.value, canvasContext: context, viewport: view })
    await render.promise
  } catch { /* Full reader reports failures; a thumbnail must not block reading. */ }
}
onMounted(draw); watch(() => [props.document, props.page], draw)
onUnmounted(() => { ++generation; render?.cancel() })
</script>
<style scoped>canvas { display: block; width: 96px; max-height: 160px; object-fit: contain; margin: auto; background: white; }</style>
