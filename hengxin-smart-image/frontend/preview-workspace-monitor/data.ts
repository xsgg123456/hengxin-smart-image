import { ref } from 'vue'
import { domesticWorkspaces } from '@/api/hengxin/domestic-workspaces'
export { domesticWorkspaces }
export type State = 'running' | 'queued' | 'succeeded' | 'failed' | 'empty'
export type Session = { id: string; person: string; workspace: string; name: string; status: State; time: string; turns: number; images: number; prompt: string; skill: string }
export const labels: Record<State, string> = { running: '执行中', queued: '排队中', succeeded: '已完成', failed: '失败', empty: '空会话' }
export const tagType = (status: State) => ({ running: 'primary', queued: 'warning', succeeded: 'success', failed: 'danger', empty: 'info' } as const)[status]
export const workspaceName = (key: string) => domesticWorkspaces.find(w => w.key === key)?.title || key
export const sessions = ref<Session[]>([
  { id: 'demo-camera-01', person: '陈晓（演示）', workspace: 'camera', name: '相机手柄 · 新品主图与卖点图', status: 'running', time: '10:42', turns: 2, images: 0, skill: '相机配件新品套图生成', prompt: '请根据上传的产品资料和参考图，制作相机手柄新品主图。保持产品结构和颜色准确，背景简洁，突出握持体验。' },
  { id: 'demo-case-01', person: '林悦（演示）', workspace: 'case', name: '磁吸手机壳 · 秋季新品套图', status: 'running', time: '10:40', turns: 2, images: 0, skill: '手机壳新品图片生成', prompt: '根据手机壳实拍和图需，制作新品套图。重点展示磁吸、镜头保护和材质细节，保持配色一致。' },
  { id: 'demo-product-01', person: '周宁（演示）', workspace: 'product', name: '白色手机壳 · 替换电商原图', status: 'queued', time: '10:38', turns: 1, images: 0, skill: '国内通用型产品替换', prompt: '把原图中的产品替换为素材中的白色款，保留原来的背景、文案和构图。' },
  { id: 'demo-phone-01', person: '陈晓（演示）', workspace: 'phone', name: '手机屏幕 · 蓝色壁纸替换', status: 'succeeded', time: '10:31', turns: 2, images: 2, skill: '未选择 Skill', prompt: '将这组手机屏幕换成参考图的蓝色壁纸，保留手机、透视、反光和屏幕外的全部内容。' },
  { id: 'demo-scene-01', person: '许言（演示）', workspace: 'scene', name: '产品场景图 · 尺寸调整', status: 'failed', time: '10:24', turns: 1, images: 0, skill: '通用型替换产品与模特', prompt: '保留产品，把背景换成明亮的室内场景，并调整为 1500 × 1500 像素。' },
  { id: 'demo-product-02', person: '林悦（演示）', workspace: 'product', name: '产品替换 · 第一版确认', status: 'succeeded', time: '10:15', turns: 2, images: 2, skill: '国内通用型产品替换', prompt: '按照第二张素材替换主图产品，原有文字、尺寸和位置保持一致。' },
  { id: 'demo-camera-02', person: '许言（演示）', workspace: 'camera', name: '相机配件 · 待提交需求', status: 'empty', time: '09:58', turns: 0, images: 0, skill: '未选择 Skill', prompt: '' },
  { id: 'demo-case-02', person: '周宁（演示）', workspace: 'case', name: '透明手机壳 · 细节展示', status: 'succeeded', time: '09:46', turns: 2, images: 2, skill: '手机壳新品图片生成', prompt: '根据参考图制作透明手机壳细节展示，突出镜头保护和边框材质。' },
])
export const scene = ref<'normal' | 'offline' | 'empty' | 'denied'>('normal')
export const progress = ref<Record<string, number>>({})
export const autoSync = ref(true)
export const synchronizedAt = ref('刚刚')
export function sync() {
  if (scene.value === 'offline' || scene.value === 'denied') return
  synchronizedAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
}
export function simulate(id: string) { progress.value[id] = Math.min((progress.value[id] || 0) + 1, 3); sync() }
