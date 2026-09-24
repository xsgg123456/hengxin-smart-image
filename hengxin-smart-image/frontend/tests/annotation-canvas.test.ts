import assert from 'node:assert/strict'
import test from 'node:test'
import {
  appendPoint,
  badgePoint,
  cloneMarks,
  moveMark,
  rectangle,
  resizeMark,
  restoreGeometry,
  type AnnotationMark,
} from '../src/views/hengxin/components/annotation/annotation-model'
import {
  exportAnnotation,
  MAX_ANNOTATION_BYTES,
  validateAnnotationBlob,
} from '../src/views/hengxin/components/annotation/annotation-export'

const mark = (overrides: Partial<AnnotationMark> = {}): AnnotationMark => ({
  id: 'one',
  kind: 'rect',
  x: 20,
  y: 30,
  width: 50,
  height: 80,
  points: [],
  note: '原意见',
  ...overrides,
})

test('非方形原图反向框选与越界拖动使用原像素坐标', () => {
  assert.deepEqual(rectangle({ x: 700, y: 1300 }, { x: -200, y: 1600 }, 790, 1500), {
    x: 0,
    y: 1300,
    width: 700,
    height: 200,
  })
  assert.deepEqual(moveMark(mark(), 900, 1800, 790, 1500), mark({ x: 740, y: 1420 }))
  assert.deepEqual(moveMark(mark(), -900, -1800, 790, 1500), mark({ x: 0, y: 0 }))
  assert.deepEqual(resizeMark(mark(), 1000, 2000, 790, 1500), mark({ width: 770, height: 1470 }))
  assert.equal(resizeMark(mark(), -100, -100, 790, 1500).width, 4)
})

test('一笔圈注只更新一条标注，点与包围范围约束在原图内', () => {
  let pen = mark({
    kind: 'pen',
    x: 20,
    y: 30,
    width: 0,
    height: 0,
    points: [{ x: 20, y: 30 }],
  })
  pen = appendPoint(pen, { x: 30, y: 40 }, 790, 1500)
  pen = appendPoint(pen, { x: 900, y: -20 }, 790, 1500)
  assert.equal(pen.id, 'one')
  assert.deepEqual(pen.points, [
    { x: 20, y: 30 },
    { x: 30, y: 40 },
    { x: 790, y: 0 },
  ])
  assert.deepEqual([pen.x, pen.y, pen.width, pen.height], [20, 0, 770, 40])
  const moved = moveMark(pen, -300, 2000, 790, 1500)
  assert.deepEqual(moved.points, [
    { x: 0, y: 1490 },
    { x: 10, y: 1500 },
    { x: 770, y: 1460 },
  ])
})

test('撤销几何变动保留同 id 最新意见，删除后撤销恢复原意见和顺序', () => {
  const snapshot = [mark(), mark({ id: 'two', note: '第二处' })]
  const restored = restoreGeometry(snapshot, [mark({ x: 100, note: '刚更新的意见' })])
  assert.deepEqual(restored, [mark({ note: '刚更新的意见' }), snapshot[1]])
  assert.equal(restoreGeometry(snapshot, [mark({ note: '' })])[0].note, '')
  const copied = cloneMarks([mark({ points: [{ x: 5, y: 6 }] })])
  copied[0].points[0].x = 99
  assert.equal(snapshot[0].x, 20)
})

test('边缘圈注编号仍完整保留在图片内', () => {
  const badge = badgePoint(mark({ x: 789, y: 1499 }), 790, 1500)
  assert.ok(badge.x < 790 && badge.y < 1500)
})

test('原尺寸 PNG 大小限制拒绝超限与空结果', () => {
  assert.throws(() => validateAnnotationBlob(null), /合成标注图失败/)
  assert.throws(() => validateAnnotationBlob(new Blob([])), /合成标注图失败/)
  assert.throws(
    () => validateAnnotationBlob(new Blob([new Uint8Array(MAX_ANNOTATION_BYTES + 1)])),
    /未压缩或降采样/,
  )
  assert.doesNotThrow(() => validateAnnotationBlob(new Blob([new Uint8Array(MAX_ANNOTATION_BYTES)])))
})

test('导出按 naturalWidth/Height 完整绘图，矩形和画笔共用数组编号', async () => {
  const labels: string[] = [],
    calls: unknown[][] = []
  const context = {
    drawImage: (...args: unknown[]) => calls.push(args),
    strokeRect: () => {},
    beginPath: () => {},
    moveTo: () => {},
    lineTo: () => {},
    stroke: () => {},
    arc: () => {},
    fill: () => {},
    fillText: (label: string) => labels.push(label),
  }
  const canvas = {
    width: 0,
    height: 0,
    getContext: () => context,
    toBlob: (callback: (blob: Blob) => void) => callback(new Blob(['png'], { type: 'image/png' })),
  }
  const prior = Object.getOwnPropertyDescriptor(globalThis, 'document')
  Object.defineProperty(globalThis, 'document', {
    configurable: true,
    value: { createElement: () => canvas },
  })
  try {
    const image = {
      naturalWidth: 790,
      naturalHeight: 1500,
      width: 100,
      height: 100,
    } as HTMLImageElement
    const file = await exportAnnotation(image, [
      mark(),
      mark({
        id: 'two',
        kind: 'pen',
        points: [
          { x: 1, y: 2 },
          { x: 3, y: 4 },
        ],
      }),
    ])
    assert.deepEqual([canvas.width, canvas.height], [790, 1500])
    assert.deepEqual(calls[0], [image, 0, 0])
    assert.deepEqual(labels, ['1', '2'])
    assert.equal(file.type, 'image/png')
  } finally {
    if (prior) Object.defineProperty(globalThis, 'document', prior)
    else Reflect.deleteProperty(globalThis, 'document')
  }
})
