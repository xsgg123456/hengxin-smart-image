<template>
  <section class="batch-board">
    <div class="board-toolbar">
      <ElButtonGroup><ElButton v-for="t in tools" :key="t.value" :type="tool === t.value ? 'primary' : 'default'" :disabled="disabled" @click="tool = t.value">{{ t.label }}</ElButton></ElButtonGroup>
      <div class="board-zoom"><ElButton :disabled="disabled || zoom <= .5" aria-label="缩小整组" @click="changeZoom(.8)">−</ElButton><span>{{ Math.round(zoom * 100) }}%</span><ElButton :disabled="disabled || zoom >= 4" aria-label="放大整组" @click="changeZoom(1.25)">＋</ElButton><ElButton :disabled="disabled" @click="fit">适应整组</ElButton></div>
    </div>
    <p class="board-help">{{ tool === 'pan' ? '拖动画布查看图片 · 滚轮缩放' : '点击选图 · 可直接在图上框选或圈注 · 双击图片进入精细标注' }}</p>
    <svg ref="svg" class="board-stage" :class="{ 'is-pan': tool === 'pan' }" :viewBox="`${camera.x} ${camera.y} ${1236 / zoom} ${720 / zoom}`" aria-label="整组图片画布" @wheel.prevent="wheel" @pointerdown="begin" @pointermove="move" @pointerup="finish" @pointercancel="cancel" @lostpointercapture="cancel" @dblclick="focusPicture">
      <g v-for="(p, i) in pictures" :key="p.id" :data-picture="p.id" tabindex="0" role="button" :aria-label="`选择图片 ${p.name}`" @keydown.enter.prevent="$emit('select', p.id)">
        <rect :x="cell(i).x" :y="cell(i).y" width="384" height="332" rx="8" fill="var(--default-box-color)" :stroke="selected === p.id ? 'var(--el-color-primary)' : 'var(--el-border-color)'" :stroke-width="selected === p.id ? 2 : 1" />
        <text :x="cell(i).x + 14" :y="cell(i).y + 26" font-size="14" fill="var(--el-text-color-primary)">{{ p.name }}</text>
        <text :x="cell(i).x + 370" :y="cell(i).y + 26" text-anchor="end" font-size="12" :fill="draftFor(p.id).marks.length ? 'var(--el-color-primary)' : 'var(--el-text-color-secondary)'">{{ draftFor(p.id).marks.length ? `已标注 ${draftFor(p.id).marks.length}处` : '未标注 · 不带回' }}</text>
        <image :href="p.url" :x="placement(i).x" :y="placement(i).y" :width="p.width * placement(i).scale" :height="p.height * placement(i).scale" @error="failed[p.id] = true" @load="failed[p.id] = false" />
        <g :transform="`translate(${placement(i).x} ${placement(i).y}) scale(${placement(i).scale})`">
          <AnnotationMarks :marks="draftFor(p.id).marks" :selected="selected === p.id ? selectedMark : ''" :width="p.width" :height="p.height" :scale="placement(i).scale * zoom" :editable="false" />
        </g>
        <text v-if="failed[p.id]" :x="cell(i).x + 192" :y="cell(i).y + 180" text-anchor="middle" font-size="14" fill="var(--el-color-danger)">图片读取失败，请进入精细标注重试</text>
      </g>
    </svg>
    <div class="board-bottom"><span>当前：{{ pictures.find(p => p.id === selected)?.name }} · {{ draftFor(selected).marks.length }}处标注</span><div><ElButton size="small" :disabled="disabled || !draftFor(selected).marks.length" @click="draftFor(selected).marks.pop()">撤销上一处</ElButton><ElButton size="small" type="primary" plain :disabled="disabled" @click="$emit('focus', selected)">放大精细标注</ElButton></div></div>
  </section>
</template>
<script setup lang="ts">
import { reactive, ref } from 'vue'
import type { StudioPicture } from '@/api/overseas/studio'
import AnnotationMarks from '@/views/hengxin/components/annotation/AnnotationMarks.vue'
import { appendPoint, boundPoint, cloneMarks, moveMark, type AnnotationMark, type Point } from '@/views/hengxin/components/annotation/annotation-model'
import { draftFor } from './state'
const props = defineProps<{ pictures: StudioPicture[]; selected: string; selectedMark: string; disabled: boolean }>()
const emit = defineEmits<{ select: [id: string]; focus: [id: string]; mark: [id: string] }>()
const tools = [{ value: 'select', label: '选择图片' }, { value: 'rect', label: '框选问题' }, { value: 'pen', label: '画笔圈注' }, { value: 'pan', label: '拖动画布' }]
const tool = ref('select'), zoom = ref(1), camera = reactive({ x: -12, y: -12 }), svg = ref<SVGSVGElement>(), failed = reactive<Record<string, boolean>>({})
const cell = (i: number) => ({ x: i % 3 * 408, y: Math.floor(i / 3) * 356 })
function placement(i: number) { const c = cell(i), p = props.pictures[i], scale = Math.min(356 / p.width, 274 / p.height); return { x: c.x + (384 - p.width * scale) / 2, y: c.y + 44, scale } }
function point(e: PointerEvent | WheelEvent): Point { const s = svg.value!, ctm = s.getScreenCTM()!; return new DOMPoint(e.clientX, e.clientY).matrixTransform(ctm.inverse()) }
function changeZoom(factor: number, pivot?: Point) { if (props.disabled || gesture) return; const before = zoom.value, next = Math.min(4, Math.max(.5, before * factor)); const p = pivot || { x: camera.x + 618 / before, y: camera.y + 360 / before }; camera.x = p.x - (p.x - camera.x) * before / next; camera.y = p.y - (p.y - camera.y) * before / next; zoom.value = next }
function wheel(e: WheelEvent) { changeZoom(e.deltaY < 0 ? 1.1 : 1 / 1.1, point(e)) }
function fit() { zoom.value = 1; camera.x = -12; camera.y = -12 }
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
    if (existing) {
      emit('mark', existing)
      const mark = draftFor(id!).marks.find(m => m.id === existing)!, place = placement(index)
      gesture = { pointer: e.pointerId, start: { x: (start.x - place.x) / place.scale, y: (start.y - place.y) / place.scale }, camera: { ...camera }, index, mark, original: cloneMarks([mark])[0] }
      e.preventDefault(); svg.value?.setPointerCapture(e.pointerId); return
    }
    if (tool.value === 'select') return
    const p = props.pictures[index], place = placement(index), local = { x: (start.x - place.x) / place.scale, y: (start.y - place.y) / place.scale }
    if (local.x < 0 || local.y < 0 || local.x > p.width || local.y > p.height) return
    const mark: AnnotationMark = { id: crypto.randomUUID(), kind: tool.value === 'pen' ? 'pen' : 'rect', x: local.x, y: local.y, width: 0, height: 0, points: [local], note: '' }
    const draft = draftFor(p.id); draft.marks.push(mark)
    gesture = { pointer: e.pointerId, start: local, camera: { ...camera }, index, mark: draft.marks[draft.marks.length - 1] }; emit('mark', mark.id)
  }
  if (gesture) { e.preventDefault(); svg.value?.setPointerCapture(e.pointerId) }
}
function move(e: PointerEvent) {
  const g = gesture; if (!g || g.pointer !== e.pointerId) return
  const current = point(e)
  if (g.index < 0) { camera.x -= current.x - g.start.x; camera.y -= current.y - g.start.y; return }
  const p = props.pictures[g.index], place = placement(g.index), local = boundPoint({ x: (current.x - place.x) / place.scale, y: (current.y - place.y) / place.scale }, p.width, p.height), m = g.mark!
  if (g.original) Object.assign(m, moveMark(g.original, local.x - g.start.x, local.y - g.start.y, p.width, p.height))
  else if (m.kind === 'pen') Object.assign(m, appendPoint(m, local, p.width, p.height))
  else { m.x = Math.min(g.start.x, local.x); m.y = Math.min(g.start.y, local.y); m.width = Math.abs(local.x - g.start.x); m.height = Math.abs(local.y - g.start.y) }
}
function finish(e: PointerEvent) {
  const g = gesture; if (!g || g.pointer !== e.pointerId) return
  if (g.mark && (g.mark.kind === 'rect' ? g.mark.width < 8 || g.mark.height < 8 : g.mark.points.length < 3)) removeGestureMark(g)
  gesture = undefined; if (svg.value?.hasPointerCapture(e.pointerId)) svg.value.releasePointerCapture(e.pointerId)
}
function removeGestureMark(g: Gesture) { if (g.original && g.mark) Object.assign(g.mark, g.original); else if (g.mark) { const draft = draftFor(props.pictures[g.index].id); draft.marks = draft.marks.filter(m => m.id !== g.mark!.id) } }
function cancel() { if (gesture) removeGestureMark(gesture); gesture = undefined }
function focusPicture(e: MouseEvent) { const id = targetPicture(e); if (id && !props.disabled) emit('focus', id) }
</script>
