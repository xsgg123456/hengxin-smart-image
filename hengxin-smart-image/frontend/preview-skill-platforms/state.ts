import { reactive, ref } from 'vue'
import type { ManagedSkill } from '@/api/overseas/management'
import seed from './seed.json'
export interface PreviewSkill extends ManagedSkill { platforms: string[] }
export const platforms = [
  { value: 'Amazon', label: '亚马逊 / Amazon' }, { value: 'Wayfair', label: '威费尔 / Wayfair' },
  { value: 'Mercado Libre', label: '美客多 / Mercado Libre' }, { value: 'Walmart', label: '沃尔玛 / Walmart' },
  { value: 'The Home Depot', label: '家得宝 / The Home Depot' }, { value: 'Shopee', label: '虾皮 / Shopee' },
]
export const skills = reactive<PreviewSkill[]>(structuredClone(seed))
export const taskPlatform = ref('Amazon')
export const previewNotice = '独立交互预览 · 示例平台归属与开关 · 刷新重置 · 不连接生产服务'
