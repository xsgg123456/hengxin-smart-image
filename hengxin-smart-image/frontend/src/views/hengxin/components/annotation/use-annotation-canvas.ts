import { computed, onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import {
  appendPoint,
  clamp,
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
  client: Point
}

export function useAnnotationCanvas(
  props: CanvasProps,
  marks: Ref<AnnotationMark[]>,
  select: (id: string) => void,
) {
  const svg = ref<SVGSVGElement>()
  const tool = ref<'rect' | 'pen'>('rect')
  const zoom = ref(1),
    view = ref<Point>({ x: 0, y: 0 })
  const selected = ref(props.selectedId || '')
  const history = ref<AnnotationMark[][]>([])
  const gesture = ref<Gesture>()
  const viewBox = computed(
    () => `${view.value.x} ${view.value.y} ${props.width / zoom.value} ${props.height / zoom.value}`,
  )
  const locked = computed(() => !!props.disabled || !!gesture.value)
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
      await ElMessageBox.confirm('清空所有标注和对应意见？可以通过撤销恢复。', '清空标注', {
        confirmButtonText: '清空',
        cancelButtonText: '取消',
        type: 'warning',
      })
    } catch {
      return
    }
    if (locked.value) return
    remember()
    marks.value = []
    choose('')
  }
  function setView(next: Point) {
    view.value = {
      x: clamp(next.x, 0, props.width - props.width / zoom.value),
      y: clamp(next.y, 0, props.height - props.height / zoom.value),
    }
  }
  function setZoom(next: number) {
    if (locked.value) return
    const previous = zoom.value
    zoom.value = clamp(next, 1, 4)
    setView({
      x: view.value.x + props.width / previous / 2 - props.width / zoom.value / 2,
      y: view.value.y + props.height / previous / 2 - props.height / zoom.value / 2,
    })
  }
  function fit() {
    if (!locked.value) {
      zoom.value = 1
      view.value = { x: 0, y: 0 }
    }
  }
  function point(event: PointerEvent): Point | undefined {
    const matrix = svg.value?.getScreenCTM()
    if (!matrix) return
    return new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse())
  }
  function begin(event: PointerEvent, pan = false) {
    if (props.disabled || gesture.value || event.button !== 0 || !svg.value) return
    const p = point(event)
    if (!p || (!pan && (p.x < 0 || p.y < 0 || p.x > props.width || p.y > props.height))) return
    const base: Gesture = {
      type: 'pan',
      pointerId: event.pointerId,
      start: p,
      snapshot: cloneMarks(marks.value),
      origin: { ...view.value },
      client: { x: event.clientX, y: event.clientY },
    }
    if (pan) {
      if (zoom.value === 1) return
    } else {
      const target = event.target instanceof Element ? event.target : null
      const id = target?.closest('[data-mark]')?.getAttribute('data-mark')
      const hit = marks.value.find((mark) => mark.id === id)
      if (hit && tool.value === 'rect') {
        base.type = target?.hasAttribute('data-resize') ? 'resize' : 'move'
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
    if (g.type === 'pen') next = appendPoint(current, p, props.width, props.height)
    if (g.type === 'move')
      next = {
        ...moveMark(original, dx, dy, props.width, props.height),
        note: current.note,
      }
    if (g.type === 'resize')
      next = {
        ...resizeMark(original, dx, dy, props.width, props.height),
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
    if (g.type !== 'pan') {
      if (cancelled || invalid) {
        marks.value = restoreGeometry(g.snapshot, marks.value)
        choose('')
      } else if (JSON.stringify(g.snapshot) !== JSON.stringify(marks.value)) remember(g.snapshot)
    }
    if (svg.value?.hasPointerCapture(g.pointerId)) svg.value.releasePointerCapture(g.pointerId)
  }
  function end(event: PointerEvent, cancel = false) {
    if (event.pointerId === gesture.value?.pointerId) finish(cancel)
  }
  function panKey(event: KeyboardEvent) {
    if (locked.value) return
    const directions: Record<string, Point> = {
      ArrowLeft: { x: -1, y: 0 },
      ArrowRight: { x: 1, y: 0 },
      ArrowUp: { x: 0, y: -1 },
      ArrowDown: { x: 0, y: 1 },
    }
    const direction = directions[event.key]
    if (!direction) return
    event.preventDefault()
    setView({
      x: view.value.x + (direction.x * 40) / zoom.value,
      y: view.value.y + (direction.y * 40) / zoom.value,
    })
  }
  const cancelGesture = () => finish(true)
  const onVisibility = () => {
    if (document.hidden) cancelGesture()
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
  onMounted(() => {
    window.addEventListener('blur', cancelGesture)
    document.addEventListener('visibilitychange', onVisibility)
  })
  onBeforeUnmount(() => {
    cancelGesture()
    window.removeEventListener('blur', cancelGesture)
    document.removeEventListener('visibilitychange', onVisibility)
  })
  return {
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
  }
}
