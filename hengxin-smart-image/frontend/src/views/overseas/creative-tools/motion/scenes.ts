import { prepareFan } from './fans'
import { prepareLamp, type LampKind } from './lamps'
import { prepareMaterial } from './materials'
import { removalFrame } from './removal-frame'
import { prepareSports } from './sports'

export type Scene = LampKind | 'home-depot' | 'replicate' | 'beleev' | 'remove-product' | 'edit-text' | 'mercado-libre' | 'recolor'
export type DrawScene = (ctx: CanvasRenderingContext2D, phase: number) => void
type DrawFrame = (ctx: CanvasRenderingContext2D, elapsedMs: number) => void
const prepared = new WeakMap<HTMLImageElement, DrawFrame>()

export function getScene(photo: HTMLImageElement, scene: Scene): DrawFrame {
  const cached = prepared.get(photo)
  if (cached) return cached
  if (scene === 'replicate' || scene === 'edit-text' || scene === 'recolor') {
    const draw = removalFrame(photo, scene)
    prepared.set(photo, draw)
    return draw
  }
  let draw: DrawScene
  switch (scene) {
    case 'home-depot':
      draw = prepareFan(photo, scene)
      break
    case 'beleev': case 'remove-product':
      draw = prepareSports(photo, scene)
      break
    case 'mercado-libre':
      draw = prepareMaterial(photo, scene)
      break
    default:
      draw = prepareLamp(photo, scene)
  }
  const loop: DrawFrame = (ctx, elapsedMs) => draw(ctx, (elapsedMs % 3000) / 3000)
  prepared.set(photo, loop)
  return loop
}
