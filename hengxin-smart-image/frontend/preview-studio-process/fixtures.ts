import type { StudioTranscript } from '@/api/overseas/studio'
import type { Asset } from '../preview-studio-images/state'

export type PreviewStatus = 'running' | 'succeeded' | 'failed' | 'cancelled'
export interface PreviewTurn {
  id: string
  text: string
  status: PreviewStatus
  entries: StudioTranscript[]
  reply: string
  pictures: Asset[]
}
const samples = Array.from({ length: 8 }, (_, i) => new URL(`../preview-ai-studio/assets/sample-${i + 1}.jpg`, import.meta.url).href)
export const materials: Asset[] = [
  { id: 'brief', name: '图需说明（示例）.txt', url: new URL('../preview-ai-studio/assets/task-brief.txt', import.meta.url).href, image: false, caption: '图需资料 · 示例文件' },
  ...samples.slice(0, 7).map((url, i) => ({ id: `reference-${i}`, name: `产品参考-${i + 1}.jpg`, url, image: true, caption: '任务素材 · 灯具样图' })),
]
const process: [StudioTranscript['kind'], string][] = [
  ['message', '我会按「amazon-new-product-image-set」技能先阅读产品资料、竞品分析和已归档的 OUTON 品牌参考，整理这款乡村风灯具的产品特点与设计要求，再据此进入制作。'],
  ['tool', '已读取产品资料和本轮引用的参考图片。'],
  ['tool', '已读取品牌参考，核对构图和文字风格。'],
  ['tool', '已整理产品结构、材质与主要卖点。'],
  ['message', '产品资料已确认：胡桃木色实木灯杆、米黄色亚麻灯罩。接下来会突出木纹、柔和布罩和温暖的家居氛围，并保持产品结构一致。'],
  ['tool', '已整理白底主图与乡村风场景图的制作方向。'],
  ['tool', '已检查灯杆比例、灯罩颜色和画面留白。'],
  ['message', '参考图和设计方向已整理完毕，正在准备本轮交付说明和图片。'],
]
export function makeTurn(id: string, status: PreviewStatus = 'succeeded', text = '请结合产品资料和参考图片，制作这款乡村风落地灯的白底主图和场景图。'): PreviewTurn {
  return {
    id, text, status,
    entries: process.map(([kind, content], i) => ({ id: i + 1, turnId: id, itemId: `${id}-${i}`, kind, text: content, state: 'completed', createdAt: '2026-10-19' })),
    reply: '已整理好这款落地灯的设计方向，本轮交付如下：\n\n- **产品展示图**：展示灯具整体轮廓和温暖的家居氛围。\n- **场景展示图**：展示不同环境中的灯光效果。',
    pictures: samples.slice(0, 2).map((url, i) => ({ id: `${id}-image-${i}`, name: ['产品展示图.jpg', '场景图.jpg'][i], url, image: true, caption: '交互示例图片' })),
  }
}

