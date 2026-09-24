<template>
  <g
    v-for="(mark, index) in marks"
    :key="mark.id"
    :data-mark="mark.id"
    class="annotation-mark"
  >
    <path
      v-if="mark.kind === 'pen'"
      :d="markPath(mark)"
      fill="none"
      stroke="#d66a26"
      :stroke-width="style.stroke"
      stroke-linecap="round"
      stroke-linejoin="round"
      pointer-events="none"
    />
    <rect
      v-else
      :x="mark.x"
      :y="mark.y"
      :width="mark.width"
      :height="mark.height"
      :fill="selected === mark.id ? '#ed7c221c' : '#ed7c220b'"
      stroke="#d66a26"
      :stroke-width="style.stroke"
      pointer-events="none"
    />
    <g data-move :style="{ '--mark-cursor': editable ? 'move' : 'crosshair' }">
      <title>拖动编号移动标注；空白处可继续画新框</title>
      <circle
        :cx="badgePoint(mark, width, height).x"
        :cy="badgePoint(mark, width, height).y"
        :r="Math.max(style.radius, 11 / scale)"
        fill="#d66a26"
      />
      <text
        :x="badgePoint(mark, width, height).x"
        :y="badgePoint(mark, width, height).y"
        text-anchor="middle"
        dominant-baseline="central"
        fill="white"
        :font-size="Math.max(style.font, 12 / scale)"
        font-family="Arial"
        >{{ index + 1 }}</text
      >
    </g>
    <g v-if="selected === mark.id && mark.kind === 'rect' && editable">
      <rect
        v-for="handle in handles(mark)"
        :key="handle.name"
        :data-resize="handle.name"
        :x="handle.x - 10 / scale"
        :y="handle.y - 10 / scale"
        :width="20 / scale"
        :height="20 / scale"
        fill="transparent"
        :style="{ '--mark-cursor': `${handle.name}-resize` }"
      />
      <rect
        v-for="handle in handles(mark)"
        :key="`visible-${handle.name}`"
        :x="handle.x - 3.5 / scale"
        :y="handle.y - 3.5 / scale"
        :width="7 / scale"
        :height="7 / scale"
        fill="white"
        stroke="#d66a26"
        :stroke-width="1 / scale"
        pointer-events="none"
      />
    </g>
  </g>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import {
  badgePoint,
  markPath,
  markStyle,
  type AnnotationMark,
} from './annotation-model'
const props = defineProps<{
  marks: AnnotationMark[]
  selected: string
  width: number
  height: number
  scale: number
  editable: boolean
}>()
const style = computed(() => markStyle(props.width, props.height))
const handles = (m: AnnotationMark) => [
  { name: 'nw', x: m.x, y: m.y },
  { name: 'n', x: m.x + m.width / 2, y: m.y },
  { name: 'ne', x: m.x + m.width, y: m.y },
  { name: 'e', x: m.x + m.width, y: m.y + m.height / 2 },
  { name: 'se', x: m.x + m.width, y: m.y + m.height },
  { name: 's', x: m.x + m.width / 2, y: m.y + m.height },
  { name: 'sw', x: m.x, y: m.y + m.height },
  { name: 'w', x: m.x, y: m.y + m.height / 2 },
]
</script>
