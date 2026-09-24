import { badgePoint, markStyle, type AnnotationMark } from './annotation-model'

export const MAX_ANNOTATION_BYTES = 10 * 1024 * 1024
export function validateAnnotationBlob(blob: Blob | null): asserts blob is Blob {
  if (!blob || !blob.size) throw new Error('合成标注图失败，请重试。')
  if (blob.size > MAX_ANNOTATION_BYTES)
    throw new Error('原尺寸标注 PNG 超过 10 MiB，无法提交；图片未压缩或降采样。请使用符合限制的已有标注图。')
}
export async function exportAnnotation(image: HTMLImageElement, marks: AnnotationMark[]): Promise<File> {
  const width = image.naturalWidth,
    height = image.naturalHeight
  if (!width || !height) throw new Error('原始图片尚未加载，无法合成标注。')
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('浏览器无法创建原尺寸标注画布。')
  ctx.drawImage(image, 0, 0)
  const style = markStyle(width, height)
  for (const [index, mark] of marks.entries()) {
    ctx.strokeStyle = '#d66a26'
    ctx.lineWidth = style.stroke
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    if (mark.kind === 'pen') {
      ctx.beginPath()
      mark.points.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)))
      ctx.stroke()
    } else ctx.strokeRect(mark.x, mark.y, mark.width, mark.height)
    const badge = badgePoint(mark, width, height)
    ctx.fillStyle = '#d66a26'
    ctx.beginPath()
    ctx.arc(badge.x, badge.y, style.radius, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = '#fff'
    ctx.font = `${style.font}px Arial`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(String(index + 1), badge.x, badge.y)
  }
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'))
  validateAnnotationBlob(blob)
  return new File([blob], '问题标注.png', { type: 'image/png' })
}
