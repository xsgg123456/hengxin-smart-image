type SportsKind = 'beleev' | 'remove-product' | 'edit-text'
type Frame = (ctx: CanvasRenderingContext2D, phase: number) => void

const turn = Math.PI * 2

function prepareScooter(photo: HTMLImageElement): Frame {
  // The contour stays in the mint margin around the original white sticker.
  // Its narrow section leaves the arrow beside the handle untouched.
  const contour = new Path2D(
    'M 50 35 L 121 35 L 122 69 L 102 71 L 102 181 L 133 193 ' +
      'L 133 235 L 94 246 L 59 246 L 50 223 L 2 216 L 2 191 ' +
      'L 61 191 L 78 183 L 79 70 L 50 66 Z'
  )
  const backing = document.createElement('canvas')
  backing.width = 136
  backing.height = 250
  const brush = backing.getContext('2d')
  if (!brush) return () => {}

  brush.drawImage(photo, 0, 0)
  const pixels = brush.getImageData(0, 0, backing.width, backing.height)
  for (let y = 0; y < backing.height; y++) {
    // Both samples come from clear background at the same height.
    const right = y > 72 && y < 180 ? 108 : 135
    const row = y * backing.width * 4
    for (let x = 1; x < right; x++) {
      for (let channel = 0; channel < 3; channel++) {
        const leftColor = pixels.data[row + channel]
        const rightColor = pixels.data[row + right * 4 + channel]
        pixels.data[row + x * 4 + channel] = leftColor + (rightColor - leftColor) * x / right
      }
    }
  }
  brush.putImageData(pixels, 0, 0)

  return (ctx, phase) => {
    const roll = (1 - Math.cos(phase * turn)) / 2
    if (roll < 0.00001) return
    ctx.save()
    ctx.clip(contour)
    ctx.drawImage(backing, 0, 0)
    ctx.restore()
    ctx.save()
    ctx.translate(74 + roll * 17, 235)
    ctx.rotate(Math.sin(phase * turn) * 0.009)
    ctx.translate(-74, -235)
    ctx.clip(contour)
    ctx.drawImage(photo, 0, 0)
    ctx.restore()
  }
}

function prepareSwings(photo: HTMLImageElement): Frame {
  return (ctx, phase) => {
    const sway = Math.sin(phase * turn) * 0.061
    if (Math.abs(sway) < 0.00001) return
    for (const offset of [0, 270]) {
      ctx.save()
      ctx.translate(offset, 32)
      ctx.beginPath()
      ctx.rect(31, 0, 168, 192)
      ctx.clip()
      ctx.fillStyle = 'white'
      ctx.fillRect(39, 0, 147, 190)
      // The ropes keep their top attachment points. Displacement increases
      // towards the board, which carries the child and the printed design.
      ctx.transform(1, 0, sway, Math.sqrt(1 - sway * sway), 0, 0)
      ctx.drawImage(photo, offset + 39, 32, 147, 190, 39, 0, 147, 190)
      ctx.restore()
    }
  }
}

function prepareSnow(): Frame {
  const flakes = Array.from({ length: 60 }, (_, i) => ({
    x: 21 + ((i * 113) % 241),
    y: 15 + ((i * 67) % 242),
    offset: (i * 0.61803398875) % 1,
    radius: 0.65 + ((i * 7) % 13) / 9,
    fall: 48 + ((i * 41) % 88)
  }))
  // Follow the photographed side of the comparison and its rounded corners.
  const scene = new Path2D('M 38 19 L 270 19 L 257 259 L 38 259 Q 20 259 20 241 L 20 37 Q 20 19 38 19 Z')
  return (ctx, phase) => {
    ctx.save()
    ctx.clip(scene)
    ctx.fillStyle = 'white'
    for (const flake of flakes) {
      const age = (phase + flake.offset) % 1
      const x = flake.x - age * 15 + 3 * Math.sin((age + flake.offset) * turn)
      const y = flake.y + (age - 0.5) * flake.fall
      ctx.globalAlpha = 0.83 * Math.sin(Math.PI * age) ** 2
      ctx.beginPath()
      ctx.ellipse(x, y, flake.radius * 0.8, flake.radius * 1.25, 0.24, 0, turn)
      ctx.fill()
    }
    ctx.restore()
  }
}

export function prepareSports(photo: HTMLImageElement, kind: SportsKind): Frame {
  if (kind === 'beleev') return prepareScooter(photo)
  if (kind === 'remove-product') return prepareSwings(photo)
  return prepareSnow()
}
