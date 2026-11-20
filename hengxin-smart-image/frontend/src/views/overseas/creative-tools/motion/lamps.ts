export type LampKind =
  | 'outon' | 'outonlife' | 'wayfair' | 'walmart'
  | 'custom-size' | 'white-background' | 'cutout'

type Box = [x: number, y: number, width: number, height: number]
type WallLight = [x: number, y: number, radiusX: number, radiusY: number, opacity: number]

interface Lamps {
  bounds: Box
  fabric: string
  timing: number
  walls?: WallLight[]
  clip?: string
}

// Paths follow the fabric and diffusers in each 500 × 278 photograph.
// Wall reflections have independent falloff and stop at the edges of the inset photographs.
const LAMPS: Record<LampKind, Lamps[]> = {
  outon: [
    { bounds: [24, 8, 69, 54], timing: 1,
      fabric: 'M34 14 Q58 7 82 14 L90.5 57 Q57 54 27 58 Z' },
    { bounds: [244, 28, 52, 71], timing: -1.16,
      fabric: 'M268 31 Q277 29 286 31 L290 47 Q277 46 264 48 Z',
      walls: [[276, 48, 35, 51, 0.45]] },
    { bounds: [400, 39, 40, 55], timing: 1.12,
      fabric: 'M416 44 Q422 42 430 44 L433 57 L413 57 Z',
      walls: [[423, 53, 22, 27, 0.48]], clip: 'M400 40 H439 V66 H400 Z M409 66 H439 V92 H409 Z' },
    { bounds: [272, 150, 64, 65], timing: 0.85,
      fabric: 'M292 160 Q299 158 304 160 L307 172 L289 172 Z',
      walls: [[299, 171, 31, 40, 0.56]], clip: 'M271 150 H336 V210 H306 V176 H272 Z' },
    { bounds: [407, 150, 42, 69], timing: -0.88,
      fabric: 'M423 165 Q429 163 434 165 L437 176 L421 176 Z',
      walls: [[429, 176, 25, 42, 0.56]] },
  ],
  outonlife: [
    { bounds: [23, 9, 76, 51], timing: 1,
      fabric: 'M25 16 L34 11 L97 13 L97 56 L35 56 L25 59 Z' },
    { bounds: [234, 28, 56, 50], timing: -1.16,
      fabric: 'M250 35 L278 36 L278 53 L250 53 Z',
      walls: [[262, 44, 33, 30, 0.65]] },
    { bounds: [363, 28, 80, 58], timing: 1.15,
      fabric: 'M383 36 L405 37 L405 53 L383 53 Z',
      walls: [[394, 45, 45, 37, 0.62]] },
    { bounds: [232, 151, 33, 50], timing: 0.87,
      fabric: 'M233 163 L256 163 L256 178 L233 178 Z',
      walls: [[244, 172, 30, 30, 0.54]], clip: 'M233 158 H261 V193 H233 Z' },
    { bounds: [435, 151, 35, 61], timing: -0.9,
      fabric: 'M442 160 L464 160 L464 175 L442 175 Z',
      walls: [[454, 171, 24, 32, 0.6]], clip: 'M437 151 H459 Q469 152 469 164 V212 H437 Z' },
  ],
  wayfair: [
    { bounds: [80, 62, 31, 40], timing: 1,
      fabric: 'M82.5 68 L87 65.5 L90.5 97.5 L86.5 99 Z M89.3 65 L105 64 L108.2 95.8 L92.4 97.1 Z' },
    { bounds: [249, 23, 63, 58], timing: -1.1,
      fabric: 'M282 31 L285 30 L283 53 L280 54 Z M287 30 L297.5 31.3 L295.8 54 L285 53.2 Z',
      walls: [[289, 43, 34, 39, 0.55]], clip: 'M252 35 Q256 24 271 23 L311 26 L307 79 L249 73 Z' },
    { bounds: [381, 35, 26, 34], timing: 1.15,
      fabric: 'M389.5 38.5 L402.2 40 L399.8 63 L387 61.5 Z' },
    { bounds: [299, 152, 42, 49], timing: 0.84,
      fabric: 'M322.8 164 L332 165.2 L330.3 182.8 L321.2 181.9 Z',
      walls: [[327, 176, 24, 24, 0.43]], clip: 'M302 154 L339 157 L334 200 L299 197 Z' },
    { bounds: [369, 151, 53, 57], timing: -0.9,
      fabric: 'M390.7 161.9 L399.3 162 L397.7 182.1 L389 181.5 Z M400.8 162.3 L404.9 163.8 L403.4 182.4 L399.3 182.6 Z',
      walls: [[395, 173, 27, 30, 0.50]], clip: 'M372 151 L421 157 L417 206 L368 202 Z' },
  ],
  walmart: [
    { bounds: [82, 61, 32, 25], timing: 1,
      fabric: 'M83 65 Q96 62 111 62 L112.3 82.5 Q99 84.5 84 84.6 Z' },
    { bounds: [241, 21, 106, 67], timing: -1.15,
      fabric: 'M257 24 L279 26 L277.6 41.4 L256 39.4 Z M291 35 L308 37 L306 53 L289 50 Z M316 39 L334 40 L332 56 L314 54 Z',
      walls: [[267, 37, 34, 48, 0.64]], clip: 'M244 43 Q245 26 260 22 L345 29 L338 86 L240 76 Z' },
    { bounds: [429, 35, 35, 74], timing: 1.12,
      fabric: 'M434 42 L450 43 Q461 46 463 63 L432 61 Z',
      walls: [[447, 56, 31, 43, 0.58]], clip: 'M431 36 Q461 39 464 61 L460 104 L429 100 Z' },
    { bounds: [289, 141, 55, 64], timing: 0.87,
      fabric: 'M301 146 L321 148 L319 161 L299 159 Z',
      walls: [[311, 155, 34, 47, 0.65]], clip: 'M293 141 L344 147 L335 205 L289 198 Z' },
    { bounds: [349, 148, 87, 72], timing: -0.9,
      fabric: 'M379 155 L400 157 L398 169 L377 167 Z',
      walls: [[389, 164, 43, 52, 0.64]], clip: 'M351 149 L435 159 L427 219 L343 210 Z' },
  ],
  'custom-size': [
    { bounds: [59, 145, 86, 55], timing: 1,
      fabric: 'M85 148 Q102 145 119 148 L143 197.7 Q104 199 62 197.8 Z' },
    { bounds: [311, 150, 104, 100], timing: -1.13,
      fabric: 'M345 163 Q357 161 367 163 L383 196 Q364 204 330 199 Z',
      walls: [[356, 192, 50, 54, 0.64]], clip: 'M312 156 Q316 150 326 150 H403 Q415 150 415 162 V250 H311 Z' },
  ],
  'white-background': [
    { bounds: [20, 57, 113, 97], timing: 1,
      fabric: 'M56 82 L78 67 L89 84 L65 99 Z',
      walls: [[69, 88, 64, 58, 0.66]], clip: 'M20 62 L124 57 L132 151 L26 155 Z' },
    { bounds: [276, 53, 92, 98], timing: -1.16,
      fabric: 'M332 68 Q348 64 363.5 69 L362.7 92.5 L330 90 Z',
      walls: [[346, 85, 64, 62, 0.67]], clip: 'M277 54 L368 60 L365 127 L332 151 L276 134 Z' },
    { bounds: [423, 69, 55, 47], timing: 1.18,
      fabric: 'M439 81 Q454 78 472 82 L471 106 L437 103 Z',
      walls: [[454, 94, 32, 23, 0.43]], clip: 'M426 69 L477 73 L474 115 L423 111 Z' },
    { bounds: [420, 116, 56, 50], timing: -0.92,
      fabric: 'M443 124 Q460 129 470.5 139 L460.4 158 L433.8 146.5 Z',
      walls: [[451, 143, 30, 25, 0.45]], clip: 'M424 117 L476 121 L472 165 L420 161 Z' },
    { bounds: [418, 166, 52, 46], timing: 0.84,
      fabric: 'M433 183 L460 170 L468.5 191 L443 205 Z',
      walls: [[451, 189, 30, 24, 0.43]], clip: 'M421 166 L470 170 L468 211 L417 207 Z' },
    { bounds: [414, 211, 54, 42], timing: -1.07,
      fabric: 'M431 224 Q445 231 462 222 L461 241 Q451 254 431 247 Z',
      walls: [[446, 236, 29, 22, 0.43]], clip: 'M417 211 L467 215 L464 241 Q462 253 447 252 L415 250 Z' },
  ],
  cutout: [
    { bounds: [76, 48, 82, 119], timing: 1,
      fabric: 'M104 66 L116 66 L116 81 L104 81 Z M124 88 L135 88 L135 105 L124 105 Z M112 107 L124 107 L124 122 L112 122 Z',
      walls: [[110, 78, 44, 41, 0.77], [128, 103, 34, 58, 0.60]] },
    { bounds: [346, 48, 81, 119], timing: -1,
      fabric: 'M372 67 L384 67 L384 82 L372 82 Z M393 89 L404 89 L404 106 L393 106 Z M381 108 L392 108 L392 123 L381 123 Z',
      walls: [[378, 79, 44, 41, 0.77], [397, 104, 34, 58, 0.60]] },
  ],
}

function surface(width: number, height: number) {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas 2D unavailable')
  return ctx
}

function prepareExposure(photo: HTMLImageElement, group: Lamps) {
  const [x, y, width, height] = group.bounds
  const mask = surface(width, height)
  mask.translate(-x, -y)
  mask.save()
  if (group.clip) mask.clip(new Path2D(group.clip))
  for (const [cx, cy, rx, ry, opacity] of group.walls ?? []) {
    mask.save()
    mask.translate(cx, cy)
    mask.scale(rx, ry)
    const falloff = mask.createRadialGradient(0, 0, 0, 0, 0, 1)
    falloff.addColorStop(0, `rgba(255,255,255,${opacity})`)
    falloff.addColorStop(0.55, `rgba(255,255,255,${opacity * 0.42})`)
    falloff.addColorStop(1, 'transparent')
    mask.fillStyle = falloff
    mask.fillRect(-1, -1, 2, 2)
    mask.restore()
  }
  mask.restore()
  if (group.walls) {
    // Let wall light die out before a crop edge, including the narrow detail panels.
    mask.save()
    mask.globalCompositeOperation = 'destination-in'
    for (const gradient of [
      mask.createLinearGradient(x, y, x + width, y),
      mask.createLinearGradient(x, y, x, y + height),
    ]) {
      gradient.addColorStop(0, 'transparent')
      gradient.addColorStop(0.14, 'white')
      gradient.addColorStop(0.86, 'white')
      gradient.addColorStop(1, 'transparent')
      mask.fillStyle = gradient
      mask.fillRect(x, y, width, height)
    }
    mask.restore()
  }
  mask.filter = 'blur(0.5px)'
  mask.fillStyle = 'white'
  mask.fill(new Path2D(group.fabric))
  const coverage = mask.getImageData(0, 0, width, height).data

  const bright = surface(width, height)
  const dim = surface(width, height)
  bright.drawImage(photo, x, y, width, height, 0, 0, width, height)
  const warm = bright.getImageData(0, 0, width, height)
  const cool = dim.createImageData(width, height)
  for (let i = 0; i < coverage.length; i += 4) {
    const r = warm.data[i], g = warm.data[i + 1], b = warm.data[i + 2]
    // Tint the original pixels so linen grain, seams and printed details survive both exposures.
    cool.data[i] = r * 0.73
    cool.data[i + 1] = g * 0.75
    cool.data[i + 2] = b * 0.77
    warm.data[i] = r + (255 - r) * 0.72
    warm.data[i + 1] = g + (232 - g) * 0.54
    warm.data[i + 2] = b + (145 - b) * 0.60
    const reflectance = Math.min(1, (r * 0.30 + g * 0.59 + b * 0.11) / 95)
    warm.data[i + 3] = cool.data[i + 3] = coverage[i + 3] * reflectance
  }
  bright.putImageData(warm, 0, 0)
  dim.putImageData(cool, 0, 0)
  return { bright: bright.canvas, dim: dim.canvas, x, y, timing: group.timing }
}

export function prepareLamp(photo: HTMLImageElement, kind: LampKind) {
  const layers = LAMPS[kind].map(group => prepareExposure(photo, group))
  return (ctx: CanvasRenderingContext2D, phase: number): void => {
    if (phase <= 0 || phase >= 1) return
    const easing = Math.sin(Math.PI * phase) ** 2
    ctx.save()
    const opacity = ctx.globalAlpha
    for (const layer of layers) {
      const localPhase = phase + (Math.abs(layer.timing) - 1) * easing
      const exposure = Math.sin(localPhase * 2 * Math.PI) * Math.sign(layer.timing)
      ctx.globalAlpha = opacity * Math.abs(exposure)
      ctx.drawImage(exposure > 0 ? layer.bright : layer.dim, layer.x, layer.y)
    }
    ctx.restore()
  }
}
