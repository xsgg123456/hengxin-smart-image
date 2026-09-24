<template>
  <section class="annotation-canvas" aria-label="图片标注区">
    <div class="annotation-toolbar">
      <el-button-group>
        <el-button :type="tool === 'rect' ? 'primary' : 'default'" :disabled="locked" @click="tool = 'rect'"
          >框选问题</el-button
        >
        <el-button :type="tool === 'pen' ? 'primary' : 'default'" :disabled="locked" @click="tool = 'pen'"
          >画笔圈注</el-button
        >
      </el-button-group>
      <div class="annotation-zoom">
        <el-button aria-label="缩小" :disabled="locked || zoom <= 1" @click="setZoom(zoom - 0.25)"
          >−</el-button
        >
        <span>{{ Math.round(zoom * 100) }}%</span>
        <el-button aria-label="放大" :disabled="locked || zoom >= 4" @click="setZoom(zoom + 0.25)"
          >＋</el-button
        >
        <el-button :disabled="locked" @click="fit">适应窗口</el-button>
      </div>
    </div>
    <p class="annotation-help" aria-live="polite">
      {{
        panning
          ? '正在移动图片 · 松开后直接继续标注'
          : `当前：${tool === 'pen' ? '画笔圈注' : '框选'} · 放大后按住右上角手柄移动图片`
      }}
    </p>
    <div class="annotation-stage" :class="{ panning }">
      <svg
        ref="svg"
        :viewBox="viewBox"
        aria-label="当前成品与问题标注"
        role="img"
        @pointerdown="begin($event)"
        @pointermove="move"
        @pointerup="end($event)"
        @pointercancel="end($event, true)"
        @lostpointercapture="end($event, true)"
      >
        <image :href="imageUrl" :width="width" :height="height" />
        <g v-for="(mark, index) in marks" :key="mark.id" :data-mark="mark.id" class="annotation-mark">
          <path
            v-if="mark.kind === 'pen'"
            :d="markPath(mark)"
            fill="none"
            stroke="#d66a26"
            :stroke-width="style.stroke"
            stroke-linecap="round"
            stroke-linejoin="round"
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
          />
          <circle
            :cx="badgePoint(mark, width, height).x"
            :cy="badgePoint(mark, width, height).y"
            :r="style.radius"
            fill="#d66a26"
          />
          <text
            :x="badgePoint(mark, width, height).x"
            :y="badgePoint(mark, width, height).y"
            text-anchor="middle"
            dominant-baseline="central"
            fill="white"
            :font-size="style.font"
            font-family="Arial"
          >
            {{ index + 1 }}
          </text>
          <rect
            v-if="selected === mark.id && mark.kind === 'rect' && !disabled"
            data-resize
            :x="mark.x + mark.width - style.radius / 2"
            :y="mark.y + mark.height - style.radius / 2"
            :width="style.radius"
            :height="style.radius"
            fill="white"
            stroke="#d66a26"
            :stroke-width="style.stroke / 2"
            class="resize-handle"
          />
        </g>
      </svg>
      <button
        type="button"
        class="annotation-pan"
        :class="{ dragging: panning }"
        :disabled="disabled || zoom === 1"
        aria-label="按住拖动图片"
        title="按住并拖动可移动图片；聚焦后也可用方向键移动"
        @pointerdown.stop="begin($event, true)"
        @keydown="panKey"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.6"
          aria-hidden="true"
        >
          <path
            d="M8 12V5a1.5 1.5 0 0 1 3 0v6-8a1.5 1.5 0 0 1 3 0v8-6a1.5 1.5 0 0 1 3 0v7-3a1.5 1.5 0 0 1 3 0v6c0 5-3 7-7 7-3 0-4-1-6-4l-3-5a1.5 1.5 0 0 1 2-2l2 2Z"
          />
        </svg>
        <span>拖动图片</span
        ><small>{{ zoom === 1 ? '先放大图片' : panning ? '松开继续标注' : '按住这里拖动' }}</small>
      </button>
      <span v-if="!marks.length" class="annotation-hint">{{
        tool === 'pen' ? '按住鼠标自由圈注，松开完成一笔' : '在图片上按住并拖动，框出需要修改的位置'
      }}</span>
    </div>
    <div class="annotation-bottom">
      <span>已标注 {{ marks.length }} 处 · 原图 {{ width }} × {{ height }}</span>
      <div>
        <el-button size="small" :disabled="locked || !history.length" @click="undo">撤销</el-button>
        <el-button size="small" :disabled="locked || !selected" @click="remove()">删除选中</el-button>
        <el-button size="small" :disabled="locked || !marks.length" @click="clear">清空标注</el-button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { badgePoint, markPath, markStyle, type AnnotationMark } from './annotation-model'
import { useAnnotationCanvas } from './use-annotation-canvas'
const props = defineProps<{
  imageUrl: string
  width: number
  height: number
  disabled?: boolean
  selectedId?: string
}>()
const marks = defineModel<AnnotationMark[]>({ default: () => [] })
const emit = defineEmits<{ select: [id: string] }>()
const {
  svg,
  tool,
  zoom,
  selected,
  history,
  locked,
  panning,
  viewBox,
  undo,
  remove,
  clear,
  setZoom,
  fit,
  begin,
  move,
  end,
  panKey,
} = useAnnotationCanvas(props, marks, (id) => emit('select', id))
const style = computed(() => markStyle(props.width, props.height))
defineExpose({ remove, undo })
</script>

<style scoped>
.annotation-canvas {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 420px;
  height: 100%;
}
.annotation-toolbar,
.annotation-zoom,
.annotation-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.annotation-toolbar {
  flex-wrap: wrap;
}
.annotation-zoom {
  font-size: 12px;
}
.annotation-zoom .el-button + .el-button {
  margin-left: 0;
}
.annotation-help {
  margin: 12px 0;
  padding: 8px 12px;
  border-radius: 5px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-size: 12px;
}
.annotation-stage {
  position: relative;
  flex: 1;
  min-height: 320px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-light);
  cursor: crosshair;
  touch-action: none;
}
.annotation-stage > svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  user-select: none;
  touch-action: none;
}
.annotation-mark {
  cursor: move;
}
.resize-handle {
  cursor: nwse-resize;
}
.annotation-pan {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  color: var(--el-color-primary);
  background: var(--el-bg-color);
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: 5px;
  box-shadow: 0 2px 10px #22335a12;
  cursor: grab;
  touch-action: none;
  user-select: none;
}
.annotation-pan small {
  color: var(--el-text-color-secondary);
  font-size: 11px;
}
.annotation-pan:disabled {
  color: var(--el-text-color-secondary);
  cursor: default;
  border-color: var(--el-border-color);
}
.annotation-pan.dragging,
.panning {
  cursor: grabbing;
}
.annotation-pan:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
}
.annotation-hint {
  position: absolute;
  bottom: 12px;
  left: 50%;
  max-width: 95%;
  padding: 7px 12px;
  font-size: 12px;
  text-align: center;
  color: var(--el-text-color-secondary);
  background: var(--el-bg-color);
  border-radius: 20px;
  transform: translateX(-50%);
  pointer-events: none;
}
.annotation-bottom {
  margin-top: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
