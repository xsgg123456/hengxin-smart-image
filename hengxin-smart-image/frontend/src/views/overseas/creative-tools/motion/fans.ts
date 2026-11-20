type Point = [number, number]
type Blade = { outline: Point[]; colour: [number, number, number] }
type Cover = {
  centre: Point
  bounds: [number, number, number, number]
  blades: Blade[]
  fixture: Path2D
}

// Each outline follows the same six points on a blade through five photographed
// positions. Interpolating them preserves the projected length and blade pitch.
const homeDepot: Cover = {
  centre: [101, 129],
  bounds: [35, 88, 135, 58],
  blades: [
    { outline: [[106,128],[150,132],[153,132.5],[151,134.5],[147,136.5],[106,132]], colour: [102,92,88] },
    { outline: [[105,131],[99,139],[97,141],[93,142],[90,142],[97,131]], colour: [110,93,78] },
    { outline: [[96,131],[42,134],[39,134],[39,132.5],[42,132],[95,129]], colour: [151,145,141] },
    { outline: [[96,129],[50,108],[47.5,106],[50,105.8],[59,106],[99,125]], colour: [128,119,114] },
    { outline: [[105,126],[157,108.4],[159.5,108],[163,111],[166.5,115],[108,131]], colour: [76,55,41] },
  ],
  fixture: new Path2D('M94.5 93 Q94 90 101.5 90 Q109 90 107 94 L104 99 L103 100 L103 116.6 Q108.5 120 108.5 124 L111 127 L109 129 Q114 129 115 132 L112.7 135 L109 137 Q100 141 92 137 L89 135 Q85 133 88 130 L92 129 L92.5 124 Q94 120 99.6 117 L100 100 Q96 98 94.5 93Z'),
}

const replicate: Cover = {
  centre: [329, 83],
  bounds: [212, 23, 246, 106],
  blades: [
    { outline: [[355,85],[448,96],[452,97],[452,98],[440,99],[355,87]], colour: [211,209,201] },
    { outline: [[334,85],[350,117],[352.5,123],[348,123.5],[337,122],[323,88]], colour: [194,189,181] },
    { outline: [[308,96],[255,114.8],[251,116],[247,115],[236,106],[304,86]], colour: [186,181,173] },
    { outline: [[302,83],[221,69.5],[217,68],[218,62],[231,52],[309,73]], colour: [181,173,163] },
    { outline: [[337,76],[389,47],[396,45],[410,45],[418.5,48],[347,81]], colour: [211,210,204] },
  ],
  fixture: new Path2D('M315 33 Q315 27 329 26.5 Q344 26 343.5 32 L341 39 Q340 44 332 46 L332 55.5 Q351 56 354 64 Q355 67 351 69 L338 76 L337 81 Q344 84 350.5 89 Q354 91 353 97 L351 99 Q349 110 346 114 Q339 120 329 119 Q318 119 313 114 Q309.5 105 308 98 Q305 98 305 94 Q305 88.5 318 84 L318 77 Q312 73 305 72 L304.5 66 Q304 58 327 55.5 L327 45 Q318 44 316 36Z'),
}

function polygon(points: Point[]) {
  const path = new Path2D()
  path.moveTo(...points[0])
  for (const point of points.slice(1)) path.lineTo(...point)
  path.closePath()
  return path
}

function surface(width: number, height: number) {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  return canvas.getContext('2d', { willReadFrequently: true })!
}

// Fill only the fixture and blade silhouettes. Nearest surrounding ceiling
// samples retain the original lighting without a rectangular retouched area.
function background(photo: HTMLImageElement, cover: Cover) {
  const [left, top, width, height] = cover.bounds
  const base = surface(width, height)
  base.drawImage(photo, -left, -top, 500, 278)
  const pixels = base.getImageData(0, 0, width, height)
  const mask = surface(width, height)
  mask.translate(-left, -top)
  mask.lineWidth = cover === replicate ? 10 : 5
  mask.lineJoin = 'round'
  const paths = cover.blades.map(blade => polygon([cover.centre, ...blade.outline]))
  paths.push(cover.fixture)
  // The dark blade brackets extend beyond the cylindrical motor.
  if (cover === replicate) paths.push(new Path2D('M293 79 L305 72 L358 73 L349 81 L370 86 L369 90 L349 88 L309 90 L294 92Z'))
  for (const path of paths) {
    mask.fill(path)
    mask.stroke(path)
  }
  const alpha = mask.getImageData(0, 0, width, height).data
  const directions: Point[] = [[1,0],[-1,0],[0,1],[0,-1]]
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const offset = (y * width + x) * 4
      if (!alpha[offset + 3]) continue
      const rgb = [0, 0, 0]
      let total = 0
      for (const [dx, dy] of directions) {
        let col = x, row = y, distance = 0
        do {
          col += dx
          row += dy
          distance++
        } while (col >= 0 && col < width && row >= 0 && row < height && alpha[(row * width + col) * 4 + 3])
        if (col < 0 || col >= width || row < 0 || row >= height) continue
        const weight = 1 / (distance * distance)
        const sample = (row * width + col) * 4
        for (let c = 0; c < 3; c++) rgb[c] += weight * pixels.data[sample + c]
        total += weight
      }
      if (total) for (let c = 0; c < 3; c++) pixels.data[offset + c] = rgb[c] / total
    }
  }
  base.putImageData(pixels, 0, 0)
  if (cover === replicate) {
    // Soften the reconstructed ceiling texture inside the mask only.
    const ceiling = surface(width, height)
    ceiling.filter = 'blur(2px)'
    ceiling.drawImage(base.canvas, 0, 0)
    ceiling.filter = 'none'
    ceiling.globalCompositeOperation = 'destination-in'
    ceiling.drawImage(mask.canvas, 0, 0)
    base.drawImage(ceiling.canvas, 0, 0)
  }
  return base.canvas
}

function colour(rgb: number[], offset: number) {
  return `rgb(${rgb.map(channel => Math.round(channel + offset)).join(',')})`
}

export function prepareFan(photo: HTMLImageElement, kind: 'home-depot' | 'replicate') {
  const cover = kind === 'home-depot' ? homeDepot : replicate
  const plate = background(photo, cover)
  const [left, top, width, height] = cover.bounds
  const hardware = surface(width, height)
  hardware.translate(-left, -top)
  hardware.clip(cover.fixture)
  hardware.drawImage(photo, 0, 0, 500, 278)
  const turn = Math.PI * 2
  return (ctx: CanvasRenderingContext2D, phase: number) => {
    ctx.drawImage(plate, left, top)
    for (let blade = 0; blade < 5; blade++) {
      // Five-point periodic interpolation exactly reproduces each measured pose.
      const weights = cover.blades.map((_, index) => {
        const angle = turn * (phase + (blade - index) / 5)
        return (1 + 2 * Math.cos(angle) + 2 * Math.cos(2 * angle)) / 5
      })
      const interpolate = (value: (pose: Blade) => number) =>
        cover.blades.reduce((sum, pose, index) => sum + weights[index] * value(pose), 0)
      const outline = cover.blades[0].outline.map((_, index): Point => [
        interpolate(pose => pose.outline[index][0]), interpolate(pose => pose.outline[index][1]),
      ])
      if (kind === 'home-depot') {
        const extent = Math.max(67, ...outline.map(point => Math.abs(point[0] - cover.centre[0])))
        for (const point of outline) point[0] = cover.centre[0] + (point[0] - cover.centre[0]) * 67 / extent
      }
      const rgb = [0, 1, 2].map(channel => interpolate(pose => pose.colour[channel]))
      // Shade across the chord, even as the blade turns nearly edge-on.
      const dx = outline[2][0] - cover.centre[0], dy = outline[2][1] - cover.centre[1]
      const length = Math.hypot(dx, dy) || 1
      const nx = -dy / length, ny = dx / length
      const chord = Math.max(1, (outline[4][0] - outline[1][0]) * nx + (outline[4][1] - outline[1][1]) * ny)
      const gradient = ctx.createLinearGradient(...outline[1], outline[1][0] + nx * chord, outline[1][1] + ny * chord)
      gradient.addColorStop(0, colour(rgb, -12))
      gradient.addColorStop(0.14, colour(rgb, 2))
      gradient.addColorStop(0.86, colour(rgb, 0))
      gradient.addColorStop(1, colour(rgb, -7))
      ctx.fillStyle = gradient
      const bladePath = new Path2D()
      bladePath.moveTo(...outline[0])
      bladePath.lineTo(...outline[1])
      bladePath.bezierCurveTo(...outline[2], ...outline[3], ...outline[4])
      bladePath.lineTo(...outline[5])
      bladePath.closePath()
      ctx.fill(bladePath)
      ctx.strokeStyle = colour(rgb, -25)
      ctx.lineWidth = 0.45
      ctx.stroke(bladePath)
      // The black mounting arms connect the moving blades to the fixed motor.
      ctx.fillStyle = kind === 'replicate' ? '#201e1a' : '#312b26'
      const arm = new Path2D()
      const rootX = (outline[0][0] + outline[5][0]) / 2
      const rootY = (outline[0][1] + outline[5][1]) / 2
      arm.moveTo(cover.centre[0], cover.centre[1] - 2)
      arm.quadraticCurveTo(rootX - 4 * nx, rootY - 4 * ny, ...outline[0])
      arm.quadraticCurveTo(rootX + 2 * dx / length, rootY + 2 * dy / length, ...outline[5])
      arm.quadraticCurveTo(rootX - 2 * nx, rootY - 2 * ny, cover.centre[0], cover.centre[1] + 2)
      arm.closePath()
      ctx.fill(arm)
    }
    ctx.drawImage(hardware.canvas, left, top)
  }
}
