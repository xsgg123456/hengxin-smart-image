import { ref } from 'vue'
import { makeTurn } from './fixtures'
import type { Asset } from '../preview-studio-images/state'

export const product = { name: '直杆实木布罩灯-乡村风', brand: 'OUTON', platform: 'Amazon', sku: 'H-ZGD0008' }
export const previewActor = '李娜'
export interface ArchiveEvent { id: number; actor: string; time: string; pictures: Asset[] }
export function useArchivePreview() {
  const pictures = ref<Asset[]>(makeTurn('turn-0').pictures)
  const events = ref<ArchiveEvent[]>([{ id: 1, actor: '张帅', time: '2026-10-16T10:46:34+08:00', pictures: [...pictures.value] }])
  function save(assets: Asset[]) {
    pictures.value = [...new Map([...pictures.value, ...assets].map(asset => [asset.id, asset])).values()]
    events.value.unshift({ id: events.value.length + 1, actor: previewActor, time: new Date().toISOString(), pictures: [...assets] })
  }
  return { pictures, events, save }
}
