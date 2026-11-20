import { prepareFan } from './fans'
import { prepareLamp, type LampKind } from './lamps'
import { prepareMaterial } from './materials'
import { prepareSports } from './sports'

export type Scene = LampKind | 'home-depot' | 'replicate' | 'beleev' | 'remove-product' | 'edit-text' | 'mercado-libre' | 'recolor'
export type DrawScene = (ctx: CanvasRenderingContext2D, phase: number) => void
const prepared = new WeakMap<HTMLImageElement, DrawScene>()

export function getScene(photo: HTMLImageElement, scene: Scene): DrawScene {
  const cached = prepared.get(photo)
  if (cached) return cached
  let draw: DrawScene
  switch (scene) {
    case 'home-depot': case 'replicate':
      draw = prepareFan(photo, scene)
      break
    case 'beleev': case 'remove-product': case 'edit-text':
      draw = prepareSports(photo, scene)
      break
    case 'mercado-libre': case 'recolor':
      draw = prepareMaterial(photo, scene)
      break
    default:
      draw = prepareLamp(photo, scene)
  }
  prepared.set(photo, draw)
  return draw
}
