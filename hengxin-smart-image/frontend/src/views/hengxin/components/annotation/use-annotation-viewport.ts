import { computed, onBeforeUnmount, onMounted, ref, type Ref } from 'vue'
import { clamp, type Point } from './annotation-model'

export function useAnnotationViewport(
  props: { width: number; height: number },
  svg: Ref<SVGSVGElement | undefined>,
  locked: Ref<boolean>,
) {
  const zoom = ref(1),
    view = ref<Point>({ x: 0, y: 0 }),
    fitScale = ref(1)
  const scale = computed(() => fitScale.value * zoom.value)
  const maxZoom = computed(() => Math.max(8, 1 / fitScale.value))
  const viewBox = computed(
    () =>
      `${view.value.x} ${view.value.y} ${props.width / zoom.value} ${props.height / zoom.value}`,
  )
  function point(event: {
    clientX: number
    clientY: number
  }): Point | undefined {
    const matrix = svg.value?.getScreenCTM()
    return matrix
      ? new DOMPoint(event.clientX, event.clientY).matrixTransform(
          matrix.inverse(),
        )
      : undefined
  }
  function setView(next: Point) {
    view.value = {
      x:
        zoom.value < 1
          ? (props.width - props.width / zoom.value) / 2
          : clamp(next.x, 0, props.width - props.width / zoom.value),
      y:
        zoom.value < 1
          ? (props.height - props.height / zoom.value) / 2
          : clamp(next.y, 0, props.height - props.height / zoom.value),
    }
  }
  function setZoom(next: number, anchor?: Point) {
    if (locked.value) return
    const previous = zoom.value
    const at = anchor ?? {
      x: view.value.x + props.width / previous / 2,
      y: view.value.y + props.height / previous / 2,
    }
    zoom.value = clamp(next, Math.min(1, 1 / fitScale.value), maxZoom.value)
    setView({
      x: at.x - ((at.x - view.value.x) * previous) / zoom.value,
      y: at.y - ((at.y - view.value.y) * previous) / zoom.value,
    })
  }
  function fit() {
    if (!locked.value) {
      zoom.value = 1
      view.value = { x: 0, y: 0 }
    }
  }
  function actualSize() {
    setZoom(1 / fitScale.value)
  }
  function wheel(event: WheelEvent) {
    event.preventDefault()
    const delta =
      event.deltaY *
      (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? 300 : 1)
    setZoom(
      zoom.value * Math.exp(-clamp(delta, -300, 300) * 0.002),
      point(event),
    )
  }
  function panKey(event: KeyboardEvent) {
    if (locked.value) return
    const directions: Record<string, Point> = {
      ArrowLeft: { x: -1, y: 0 },
      ArrowRight: { x: 1, y: 0 },
      ArrowUp: { x: 0, y: -1 },
      ArrowDown: { x: 0, y: 1 },
    }
    const d = directions[event.key]
    if (!d) return
    event.preventDefault()
    setView({
      x: view.value.x + (d.x * 40) / scale.value,
      y: view.value.y + (d.y * 40) / scale.value,
    })
  }
  let observer: ResizeObserver | undefined
  onMounted(() => {
    observer = new ResizeObserver(([entry]) => {
      const box = entry?.contentRect
      if (box?.width && box.height)
        fitScale.value = Math.min(
          box.width / props.width,
          box.height / props.height,
        )
    })
    if (svg.value?.parentElement) observer.observe(svg.value.parentElement)
  })
  onBeforeUnmount(() => observer?.disconnect())
  return {
    zoom,
    view,
    scale,
    maxZoom,
    viewBox,
    point,
    setView,
    setZoom,
    fit,
    actualSize,
    wheel,
    panKey,
  }
}
