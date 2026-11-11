<template>
  <section class="batch-board">
    <div class="board-toolbar">
      <ElButtonGroup><ElButton v-for="t in tools" :key="t.value" :type="tool === t.value ? 'primary' : 'default'" :disabled="disabled" @click="tool = t.value">{{ t.label }}</ElButton></ElButtonGroup>
      <div class="board-zoom"><ElButton :disabled="disabled || zoom <= minZoom" aria-label="缩小整组" @click="changeZoom(.8)">−</ElButton><span>{{ Math.round(zoom * 100) }}%</span><ElButton :disabled="disabled || zoom >= 4" aria-label="放大整组" @click="changeZoom(1.25)">＋</ElButton><ElButton :disabled="disabled" @click="fit">适应整组</ElButton></div>
    </div>
    <p class="board-help">{{ tool === 'pan' ? '拖动画布查看图片 · 滚轮缩放' : '点击选图 · 可直接在图上框选或圈注 · 双击图片进入精细标注' }}</p>
    <svg ref="svg" class="board-stage" :class="{ 'is-pan': tool === 'pan' }" :viewBox="`${camera.x} ${camera.y} ${1236 / zoom} ${720 / zoom}`" aria-label="整组图片画布" @wheel.prevent="wheel" @pointerdown="begin" @pointermove="move" @pointerup="finish" @pointercancel="cancel" @lostpointercapture="cancel" @dblclick="focusPicture">
      <g v-for="(p, i) in pictures" :key="p.id" :data-picture="p.id" tabindex="0" role="button" :aria-label="`选择图片 ${p.name}`" @keydown.enter.prevent="!disabled && $emit('select', p.id)">
        <rect :x="cell(i).x" :y="cell(i).y" width="384" height="332" rx="8" fill="var(--default-box-color)" :stroke="selected === p.id ? 'var(--el-color-primary)' : 'var(--el-border-color)'" :stroke-width="selected === p.id ? 2 : 1" />
        <foreignObject :x="cell(i).x + 14" :y="cell(i).y + 9" width="225" height="25"><div class="board-picture-name" :title="p.name">{{ p.name }}</div></foreignObject>
        <text :x="cell(i).x + 370" :y="cell(i).y + 26" text-anchor="end" font-size="12" :fill="draftFor(props.keyFor(p)).marks.length ? 'var(--el-color-primary)' : 'var(--el-text-color-secondary)'">{{ draftFor(props.keyFor(p)).marks.length ? `已标注 ${draftFor(props.keyFor(p)).marks.length}处` : '未标注 · 不带回' }}</text>
        <image :href="images[p.id]?.url" :x="placement(i).x" :y="placement(i).y" :width="size(i).width * placement(i).scale" :height="size(i).height * placement(i).scale" />
        <g :transform="`translate(${placement(i).x} ${placement(i).y}) scale(${placement(i).scale})`">
          <AnnotationMarks :marks="draftFor(props.keyFor(p)).marks" :selected="selected === p.id ? selectedMark : ''" :width="size(i).width" :height="size(i).height" :scale="placement(i).scale * zoom" :editable="false" />
        </g>
        <foreignObject v-if="!images[p.id]?.url" :x="cell(i).x + 20" :y="cell(i).y + 140" width="344" height="100"><div class="board-image-state" :class="{ 'has-error': images[p.id]?.error }">{{ images[p.id]?.error ? `${images[p.id].error} · 双击重试` : '正在读取图片…' }}</div></foreignObject>
      </g>
    </svg>
    <div class="board-bottom"><span>当前：{{ pictures.find(p => p.id === selected)?.name }} · {{ selectedDraft.marks.length }}处标注</span><div><ElButton size="small" :disabled="disabled || !selectedDraft.marks.length" @click="selectedDraft.marks.pop()">撤销上一处</ElButton><ElButton size="small" type="primary" plain :disabled="disabled" @click="$emit('focus', selected)">放大精细标注</ElButton></div></div>
  </section>
</template>
<script setup lang="ts">
import { randomUUID } from '../../../../utils/browser-crypto'
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import type { StudioPicture } from '@/api/overseas/studio'
import AnnotationMarks from '@/views/hengxin/components/annotation/AnnotationMarks.vue'
import { appendPoint, boundPoint, cloneMarks, moveMark, type AnnotationMark, type Point } from '@/views/hengxin/components/annotation/annotation-model'
import { draftFor } from './state'
import { useBoardImages } from './use-board-images'
import { boardLayout } from './board-layout'
const props = defineProps<{ pictures: StudioPicture[]; selected: string; selectedMark: string; disabled: boolean; keyFor: (p: StudioPicture) => string }>()
const emit = defineEmits<{ select: [id: string]; focus: [id: string]; mark: [id: string] }>()
const tools = [{ value: 'select', label: '选择图片' }, { value: 'rect', label: '框选问题' }, { value: 'pen', label: '画笔圈注' }, { value: 'pan', label: '拖动画布' }]
const tool = ref('select'), zoom = ref(1), camera = reactive({ x: -12, y: -12 }), svg = ref<SVGSVGElement>()
const images = useBoardImages(() => props.pictures)
const selectedDraft = computed(() => draftFor(props.keyFor(props.pictures.find(p => p.id === props.selected)!)))
const layout = computed(() => boardLayout(props.pictures.length))
const fitZoom = computed(() => layout.value.fitZoom)
const minZoom = computed(() => Math.min(.5, fitZoom.value / 2))
const size = (i: number) => images[props.pictures[i].id] || { width: props.pictures[i].width || 1, height: props.pictures[i].height || 1 }
const cell = (i: number) => ({ x: i % layout.value.columns * 408, y: Math.floor(i / layout.value.columns) * 356 })
function placement(i: number) { const c = cell(i), p = size(i), scale = Math.min(356 / p.width, 274 / p.height); return { x: c.x + (384 - p.width * scale) / 2, y: c.y + 44, scale } }
function point(e: PointerEvent | WheelEvent): Point { const s = svg.value!, ctm = s.getScreenCTM()!; return new DOMPoint(e.clientX, e.clientY).matrixTransform(ctm.inverse()) }
function changeZoom(factor: number, pivot?: Point) { if (props.disabled || gesture) return; const before = zoom.value, next = Math.min(4, Math.max(minZoom.value, before * factor)); const p = pivot || { x: camera.x + 618 / before, y: camera.y + 360 / before }; camera.x = p.x - (p.x - camera.x) * before / next; camera.y = p.y - (p.y - camera.y) * before / next; zoom.value = next }
function wheel(e: WheelEvent) { changeZoom(e.deltaY < 0 ? 1.1 : 1 / 1.1, point(e)) }
function fit() { if (props.disabled || gesture) return; zoom.value = fitZoom.value; camera.x = -12; camera.y = -12 }
type Gesture = { pointer: number; start: Point; camera: Point; index: number; mark?: AnnotationMark; original?: AnnotationMark }
let gesture: Gesture | undefined
function targetPicture(e: MouseEvent | PointerEvent) { return (e.target as Element).closest('[data-picture]')?.getAttribute('data-picture') }
function begin(e: PointerEvent) {
  if (props.disabled || ![0, 1].includes(e.button) || gesture) return
  const start = point(e), id = targetPicture(e), index = props.pictures.findIndex(p => p.id === id)
  if (tool.value === 'pan' || e.button === 1) gesture = { pointer: e.pointerId, start, camera: { ...camera }, index: -1 }
  else if (index >= 0) {
    emit('select', id!)
    const existing = (e.target as Element).closest('[data-mark]')?.getAttribute('data-mark')
    if (existing && tool.value === 'select') {
      emit('mark', existing)
      const mark = draftFor(props.keyFor(props.pictures[index])).marks.find(m => m.id === existing)!, place = placement(index)
      gesture = { pointer: e.pointerId, start: { x: (start.x - place.x) / place.scale, y: (start.y - place.y) / place.scale }, camera: { ...camera }, index, mark, original: cloneMarks([mark])[0] }
      e.preventDefault(); svg.value?.setPointerCapture(e.pointerId); return
    }
    if (tool.value === 'select' || !images[id!]?.url) return
    const p = props.pictures[index], dimensions = size(index), place = placement(index), local = { x: (start.x - place.x) / place.scale, y: (start.y - place.y) / place.scale }
    if (local.x < 0 || local.y < 0 || local.x > dimensions.width || local.y > dimensions.height) return
    const mark: AnnotationMark = { id: randomUUID(), kind: tool.value === 'pen' ? 'pen' : 'rect', x: local.x, y: local.y, width: 0, height: 0, points: [local], note: '' }
    const draft = draftFor(props.keyFor(p)); draft.marks.push(mark)
    gesture = { pointer: e.pointerId, start: local, camera: { ...camera }, index, mark: draft.marks[draft.marks.length - 1] }; emit('mark', mark.id)
  }
  if (gesture) { e.preventDefault(); svg.value?.setPointerCapture(e.pointerId) }
}
function move(e: PointerEvent) {
  const g = gesture; if (!g || g.pointer !== e.pointerId) return
  const current = point(e)
  if (g.index < 0) { camera.x -= current.x - g.start.x; camera.y -= current.y - g.start.y; return }
  const p = size(g.index), place = placement(g.index), local = boundPoint({ x: (current.x - place.x) / place.scale, y: (current.y - place.y) / place.scale }, p.width, p.height), m = g.mark!
  if (g.original) Object.assign(m, moveMark(g.original, local.x - g.start.x, local.y - g.start.y, p.width, p.height))
  else if (m.kind === 'pen') Object.assign(m, appendPoint(m, local, p.width, p.height))
  else { m.x = Math.min(g.start.x, local.x); m.y = Math.min(g.start.y, local.y); m.width = Math.abs(local.x - g.start.x); m.height = Math.abs(local.y - g.start.y) }
}
function finish(e: PointerEvent) {
  const g = gesture; if (!g || g.pointer !== e.pointerId) return
  if (g.mark && (g.mark.kind === 'rect' ? g.mark.width < 8 || g.mark.height < 8 : g.mark.points.length < 3)) removeGestureMark(g)
  gesture = undefined; if (svg.value?.hasPointerCapture(e.pointerId)) svg.value.releasePointerCapture(e.pointerId)
}
function removeGestureMark(g: Gesture) { if (g.original && g.mark) Object.assign(g.mark, g.original); else if (g.mark) { const draft = draftFor(props.keyFor(props.pictures[g.index])); draft.marks = draft.marks.filter(m => m.id !== g.mark!.id) } }
function cancel() { if (gesture) removeGestureMark(gesture); gesture = undefined }
function focusPicture(e: MouseEvent) { const id = targetPicture(e); if (id && !props.disabled) emit('focus', id) }
watch(() => props.pictures.length, fit, { immediate: true })
watch(() => props.disabled, value => { if (value) cancel() })
onBeforeUnmount(cancel)
</script>
