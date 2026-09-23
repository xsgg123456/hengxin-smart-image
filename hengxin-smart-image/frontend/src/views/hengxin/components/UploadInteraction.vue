<template>
  <div ref="surface" class="upload-interaction" :class="{ 'is-dragging': dragging }" tabindex="0" role="group" aria-label="图片上传区，聚焦后可按 Ctrl+V 粘贴图片"
    @pointerdown="focusSurface" @paste="paste" @dragenter.capture="dragEnter" @dragover.capture="dragOver" @dragleave.capture="dragLeave" @drop.capture="drop" @dragend="dragging = false">
    <slot />
    <div class="upload-paste-toolbar"><ElButton size="small" :disabled="disabled" :loading="reading" @click="pasteButton">粘贴图片</ElButton><span>点击上传区后 Ctrl+V · 支持拖入本地图片</span></div>
  </div>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { clipboardFiles, clipboardHint, isTextInput, readClipboardImages } from './upload-interaction'
const props = defineProps<{ disabled?: boolean }>()
const emit = defineEmits<{ files: [files: File[]]; error: [message: string] }>()
const surface = ref<HTMLElement>(), dragging = ref(false), reading = ref(false)
let alive = true
let generation = 0
watch(() => props.disabled, () => { generation++; dragging.value = false }, { flush: 'sync' })
onBeforeUnmount(() => { alive = false })
function focusSurface(event: PointerEvent) {
  if (isTextInput(event.target)) return
  if (event.target instanceof Element && event.target.closest('button, a, [role="button"]')) return
  surface.value?.focus({ preventScroll: true })
}
function paste(event: ClipboardEvent) {
  if (props.disabled || isTextInput(event.target) || !surface.value?.contains(document.activeElement)) return
  const files = clipboardFiles(event.clipboardData)
  if (!files.length) return
  event.preventDefault(); event.stopPropagation(); emit('files', files)
}
function hasFiles(event: DragEvent) { return Array.from(event.dataTransfer?.types ?? []).includes('Files') }
function dragEnter(event: DragEvent) { if (hasFiles(event) && !props.disabled) { event.preventDefault(); dragging.value = true } }
function dragOver(event: DragEvent) { if (hasFiles(event)) { event.preventDefault(); event.stopPropagation(); if (event.dataTransfer) event.dataTransfer.dropEffect = props.disabled ? 'none' : 'copy'; dragging.value = !props.disabled } }
function dragLeave(event: DragEvent) { if (!(event.relatedTarget instanceof Node) || !surface.value?.contains(event.relatedTarget)) dragging.value = false }
function drop(event: DragEvent) {
  dragging.value = false
  if (!hasFiles(event)) return
  event.preventDefault(); event.stopPropagation()
  if (!props.disabled) { surface.value?.focus({ preventScroll: true }); emit('files', Array.from(event.dataTransfer?.files ?? [])) }
}
async function pasteButton() {
  if (props.disabled || reading.value) return
  const token = generation
  surface.value?.focus({ preventScroll: true }); reading.value = true
  try {
    if (!navigator.clipboard?.read) throw new Error('unavailable')
    const files = await readClipboardImages(navigator.clipboard)
    if (!alive || props.disabled || token !== generation) return
    if (files.length) emit('files', files)
    else emit('error', '剪贴板中没有图片，请先复制图片，或点击选择文件。')
  } catch { if (alive && !props.disabled && token === generation) emit('error', clipboardHint) }
  finally { reading.value = false }
}
</script>
<style scoped>
.upload-interaction { width:100%; min-width:0; border-radius:8px; outline:2px solid transparent; outline-offset:3px; transition:outline-color .15s, background-color .15s; }
.upload-interaction:focus-visible,.upload-interaction.is-dragging { outline-color:var(--el-color-primary); }
.upload-interaction.is-dragging { background:var(--el-color-primary-light-9); }
.upload-paste-toolbar { display:flex; align-items:center; flex-wrap:wrap; gap:8px; margin-top:10px; }
.upload-paste-toolbar span { font-size:12px; color:var(--art-gray-600); }
</style>
