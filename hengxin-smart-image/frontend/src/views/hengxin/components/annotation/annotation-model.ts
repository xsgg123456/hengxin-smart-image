export type Point = { x: number; y: number }
export type AnnotationMark = {
  id: string
  kind: 'rect' | 'pen'
  x: number
  y: number
  width: number
  height: number
  points: Point[]
  note: string
}
export const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(value, max))
export const boundPoint = (p: Point, width: number, height: number): Point => ({
  x: clamp(p.x, 0, width),
  y: clamp(p.y, 0, height),
})
export const cloneMarks = (marks: AnnotationMark[]) =>
  marks.map((mark) => ({
    ...mark,
    points: mark.points.map((point) => ({ ...point })),
  }))
export function restoreGeometry(snapshot: AnnotationMark[], current: AnnotationMark[]) {
  const notes = new Map(current.map((mark) => [mark.id, mark.note]))
  return cloneMarks(snapshot).map((mark) => ({
    ...mark,
    note: notes.get(mark.id) ?? mark.note,
  }))
}
export function rectangle(start: Point, end: Point, width: number, height: number) {
  const a = boundPoint(start, width, height),
    b = boundPoint(end, width, height)
  return {
    x: Math.min(a.x, b.x),
    y: Math.min(a.y, b.y),
    width: Math.abs(a.x - b.x),
    height: Math.abs(a.y - b.y),
  }
}
export function moveMark(
  mark: AnnotationMark,
  dx: number,
  dy: number,
  width: number,
  height: number,
): AnnotationMark {
  const x = clamp(mark.x + dx, 0, width - mark.width),
    y = clamp(mark.y + dy, 0, height - mark.height)
  return {
    ...mark,
    x,
    y,
    points: mark.points.map((p) => ({
      x: p.x + x - mark.x,
      y: p.y + y - mark.y,
    })),
  }
}
export function resizeMark(
  mark: AnnotationMark,
  dx: number,
  dy: number,
  width: number,
  height: number,
): AnnotationMark {
  return {
    ...mark,
    width: clamp(mark.width + dx, Math.min(4, width - mark.x), width - mark.x),
    height: clamp(mark.height + dy, Math.min(4, height - mark.y), height - mark.y),
  }
}
export function appendPoint(
  mark: AnnotationMark,
  point: Point,
  width: number,
  height: number,
): AnnotationMark {
  const next = boundPoint(point, width, height),
    previous = mark.points.at(-1)
  if (previous && Math.hypot(next.x - previous.x, next.y - previous.y) < 1) return mark
  const x = Math.min(mark.x, next.x),
    y = Math.min(mark.y, next.y)
  return {
    ...mark,
    x,
    y,
    width: Math.max(mark.x + mark.width, next.x) - x,
    height: Math.max(mark.y + mark.height, next.y) - y,
    points: [...mark.points, next],
  }
}
// Same geometry and numbering is used on screen and in the original-resolution PNG.
export function markStyle(width: number, height: number) {
  const unit = Math.max(0.25, Math.min(width, height) / 800)
  return {
    stroke: 3 * unit,
    radius: 12 * unit,
    offset: 13 * unit,
    font: 15 * unit,
  }
}
export function badgePoint(mark: AnnotationMark, width: number, height: number): Point {
  const { radius, offset } = markStyle(width, height)
  return {
    x: clamp(mark.x + offset, radius, width - radius),
    y: clamp(mark.y + offset, radius, height - radius),
  }
}
export const markPath = (mark: AnnotationMark) =>
  mark.points.map((p, i) => `${i ? 'L' : 'M'} ${p.x} ${p.y}`).join(' ')
