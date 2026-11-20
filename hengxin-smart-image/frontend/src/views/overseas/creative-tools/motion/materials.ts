// The ring and the model roof are sampled in their original 500 × 278 photographs.
// Only the selected material changes colour; shadows, outlines and text stay put.
type Region = [left: number, top: number, width: number, height: number]

function sample(photo: HTMLImageElement, [x, y, w, h]: Region) {
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d', { willReadFrequently: true })!
  ctx.drawImage(photo, x, y, w, h, 0, 0, w, h)
  return ctx
}

function clamp(value: number) { return Math.max(0, Math.min(1, value)) }

function prepareRing(photo: HTMLImageElement) {
  const regions: Region[] = [[66, 82, 90, 89], [243, 54, 49, 63], [234, 158, 48, 62], [379, 164, 54, 65]]
  // Ellipse axes follow the different camera angles in the four product photos.
  const ellipses = [[110,126,36,36,0], [268,85,20,26,.19], [259,188,20,26,.29], [405,195,19,26,.4]]
  const strips = regions.map((region, i) => {
    const ctx = sample(photo, region)
    const pixels = ctx.getImageData(0, 0, region[2], region[3])
    const [cx, cy, rx, ry, tilt] = ellipses[i]
    for (let y = 0; y < region[3]; y++) for (let x = 0; x < region[2]; x++) {
      const dx = x + region[0] - cx, dy = y + region[1] - cy
      const radius = Math.hypot((dx + tilt * dy) / rx, dy / ry)
      const k = 4 * (y * region[2] + x)
      const rgb = pixels.data.subarray(k, k + 3)
      const chroma = Math.max(...rgb) - Math.min(...rgb)
      pixels.data[k+3] = 255 * clamp((.23 - Math.abs(1 - radius)) * 10) * clamp((chroma - 8) / 45)
    }
    ctx.putImageData(pixels, 0, 0)
    // Pre-render the illuminated strip hues once; each frame crossfades tiny sprites.
    return Array.from({ length: 8 }, (_, step) => {
      const layer = ctx.canvas.cloneNode(false) as HTMLCanvasElement
      const tint = layer.getContext('2d')!
      tint.filter = `hue-rotate(${step * 45}deg) saturate(1.35) brightness(1.08)`
      tint.drawImage(ctx.canvas, 0, 0)
      return layer
    })
  })
  return (ctx: CanvasRenderingContext2D, phase: number) => {
    const step = phase * 8
    for (let i = 0; i < strips.length; i++) {
      const [x,y] = regions[i]
      ctx.drawImage(strips[i][Math.floor(step) % 8], x, y)
      ctx.globalAlpha = step % 1
      ctx.drawImage(strips[i][(Math.floor(step) + 1) % 8], x, y)
      ctx.globalAlpha = 1
    }
  }
}

function prepareRoof(photo: HTMLImageElement) {
  const region: Region = [182, 22, 142, 117]
  const roof = sample(photo, region)
  const data = roof.getImageData(0, 0, region[2], region[3])
  const pixels = data.data
  // Refinish only the photographed roof tiles. Copper highlights and dark seams
  // retain their luminance while the surface gradually takes on a green patina.
  for (let i = 0; i < pixels.length; i += 4) {
    const [r,g,b] = pixels.subarray(i, i + 3)
    const amount = clamp((r - g - 12) / 48) * clamp((r - b - 20) / 38)
    const light = .299 * r + .587 * g + .114 * b
    pixels[i] = light * .53
    pixels[i+1] = light * 1.23
    pixels[i+2] = light * 1.07
    pixels[i+3] = 255 * amount
  }
  roof.putImageData(data, 0, 0)
  const outline = new Path2D('M185 105 L219 26 L230 25 L237 34 L271 39 L320 124 L305 131 L245 108 L228 69 L211 102 Z')
  return (ctx: CanvasRenderingContext2D, phase: number) => {
    ctx.save()
    ctx.clip(outline)
    ctx.globalAlpha = (1 - Math.cos(phase * 2 * Math.PI)) / 2
    ctx.drawImage(roof.canvas, region[0], region[1])
    ctx.restore()
  }
}

export function prepareMaterial(photo: HTMLImageElement, kind: 'mercado-libre' | 'recolor') {
  return kind === 'mercado-libre' ? prepareRing(photo) : prepareRoof(photo)
}
