import { computed, ref, watch, type Ref } from 'vue'
import { useAnnotationShortcuts } from './use-annotation-shortcuts'
import { useAnnotationViewport } from './use-annotation-viewport'
import { ElMessageBox } from 'element-plus'
import {
  appendPoint,
  cloneMarks,
  moveMark,
  rectangle,
  resizeMark,
  restoreGeometry,
  type AnnotationMark,
  type Point,
} from './annotation-model'
type CanvasProps = {
  imageUrl: string
  width: number
  height: number
  disabled?: boolean
  selectedId?: string
}
type Gesture = {
  type: 'pan' | 'rect' | 'pen' | 'move' | 'resize'
  pointerId: number
  start: Point
  mark?: AnnotationMark
  snapshot: AnnotationMark[]
  origin: Point
  handle?: string
  client: Point
}
export function useAnnotationCanvas(
  props: CanvasProps,
  marks: Ref<AnnotationMark[]>,
  select: (id: string) => void,
) {
  const svg = ref<SVGSVGElement>()
  const tool = ref<'rect' | 'pen'>('rect')
  const { space, cancelGesture } = useAnnotationShortcuts(
    () => !!props.disabled,
    () => finish(true),
  )
  const selected = ref(props.selectedId || '')
  const history = ref<AnnotationMark[][]>([])
  const gesture = ref<Gesture>()
  const locked = computed(() => !!props.disabled || !!gesture.value)
  const viewport = useAnnotationViewport(props, svg, locked)
  const { zoom, view, point, setView, fit } = viewport
  const panning = computed(() => gesture.value?.type === 'pan')
  function choose(id: string) {
    selected.value = id
    select(id)
  }
  watch(
    () => props.selectedId,
    (id) => {
      selected.value = id || ''
    },
  )
  function remember(snapshot = marks.value) {
    history.value.push(cloneMarks(snapshot))
    if (history.value.length > 50) history.value.shift()
  }
  function undo() {
    if (locked.value) return
    const snapshot = history.value.pop()
    if (snapshot) {
      marks.value = restoreGeometry(snapshot, marks.value)
      choose('')
    }
  }
  function remove(id = selected.value) {
    if (locked.value || !marks.value.some((mark) => mark.id === id)) return
    remember()
    marks.value = marks.value.filter((mark) => mark.id !== id)
    choose('')
  }
  async function clear() {
    if (locked.value || !marks.value.length) return
    try {
      await ElMessageBox.confirm(
        '清空所有标注和对应意见？可以通过撤销恢复。',
        '清空标注',
        {
          confirmButtonText: '清空',
          cancelButtonText: '取消',
          type: 'warning',
        },
      )
    } catch {
      return
    }
    if (locked.value) return
    remember()
    marks.value = []
    choose('')
  }
  function begin(event: PointerEvent, pan = false) {
    if (
      props.disabled ||
      gesture.value ||
      ![0, 1].includes(event.button) ||
      !svg.value
    )
      return
    pan = pan || event.button === 1 || space.value
    const p = point(event)
    if (
      !p ||
      (!pan && (p.x < 0 || p.y < 0 || p.x > props.width || p.y > props.height))
    )
      return
    const base: Gesture = {
      type: 'pan',
      pointerId: event.pointerId,
      start: p,
      snapshot: cloneMarks(marks.value),
      origin: { ...view.value },
      client: { x: event.clientX, y: event.clientY },
    }
    if (pan) {
      if (zoom.value <= 1) return
    } else {
      const target = event.target instanceof Element ? event.target : null
      const id = target?.closest('[data-mark]')?.getAttribute('data-mark')
      const hit = marks.value.find((mark) => mark.id === id)
      if (
        hit &&
        tool.value === 'rect' &&
        (target?.closest('[data-move]') || target?.hasAttribute('data-resize'))
      ) {
        base.type = target?.hasAttribute('data-resize') ? 'resize' : 'move'
        base.handle = target?.getAttribute('data-resize') || undefined
        base.mark = cloneMarks([hit])[0]
        choose(hit.id)
      } else {
        const mark: AnnotationMark = {
          id: crypto.randomUUID(),
          kind: tool.value,
          x: p.x,
          y: p.y,
          width: 0,
          height: 0,
          points: tool.value === 'pen' ? [{ x: p.x, y: p.y }] : [],
          note: '',
        }
        base.type = tool.value
        base.mark = mark
        marks.value = [...marks.value, mark]
        choose(mark.id)
      }
    }
    gesture.value = base
    svg.value.setPointerCapture(event.pointerId)
    event.preventDefault()
  }
  function move(event: PointerEvent) {
    const g = gesture.value
    if (!g || event.pointerId !== g.pointerId) return
    if (g.type === 'pan') {
      const matrix = svg.value?.getScreenCTM()
      if (matrix)
        setView({
          x: g.origin.x - (event.clientX - g.client.x) / matrix.a,
          y: g.origin.y - (event.clientY - g.client.y) / matrix.d,
        })
      return
    }
    const p = point(event),
      original = g.mark
    if (!p || !original) return
    const current = marks.value.find((mark) => mark.id === original.id)
    if (!current) return
    const dx = p.x - g.start.x,
      dy = p.y - g.start.y
    let next = current
    if (g.type === 'rect')
      next = {
        ...current,
        ...rectangle(g.start, p, props.width, props.height),
      }
    if (g.type === 'pen') {
      for (const sample of [...(event.getCoalescedEvents?.() ?? []), event]) {
        const sampled = point(sample)
        if (sampled)
          next = appendPoint(
            next,
            sampled,
            props.width,
            props.height,
            event.type === 'pointerup',
          )
      }
    }
    if (g.type === 'move')
      next = {
        ...moveMark(original, dx, dy, props.width, props.height),
        note: current.note,
      }
    if (g.type === 'resize')
      next = {
        ...resizeMark(original, dx, dy, props.width, props.height, g.handle),
        note: current.note,
      }
    marks.value = marks.value.map((mark) => (mark.id === next.id ? next : mark))
  }
  function finish(cancelled = false) {
    const g = gesture.value
    if (!g) return
    gesture.value = undefined
    const mark = marks.value.find((item) => item.id === g.mark?.id)
    const invalid =
      (g.type === 'rect' && (!mark || mark.width < 4 || mark.height < 4)) ||
      (g.type === 'pen' && (!mark || mark.points.length < 2))
    if (g.type === 'pan' && cancelled) setView(g.origin)
    if (g.type !== 'pan') {
      if (cancelled || invalid) {
        marks.value = restoreGeometry(g.snapshot, marks.value)
        choose('')
      } else if (JSON.stringify(g.snapshot) !== JSON.stringify(marks.value))
        remember(g.snapshot)
    }
    if (svg.value?.hasPointerCapture(g.pointerId))
      svg.value.releasePointerCapture(g.pointerId)
  }
  function end(event: PointerEvent, cancel = false) {
    if (event.pointerId !== gesture.value?.pointerId) return
    if (!cancel) move(event)
    finish(cancel)
  }
  watch(
    () => props.disabled,
    (value) => {
      if (value) cancelGesture()
    },
  )
  watch(
    () => props.imageUrl,
    () => {
      cancelGesture()
      history.value = []
      fit()
      choose('')
    },
  )
  return {
    svg,
    tool,
    ...viewport,
    space,
    selected,
    history,
    locked,
    panning,
    undo,
    remove,
    clear,
    fit,
    begin,
    move,
    end,
  }
}
