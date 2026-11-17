import { computed, reactive, ref, watch } from 'vue'
export type Message = { id: string; role: 'user' | 'assistant'; text: string; time: string; skill?: string; files?: string[] }
export type Session = { id: string; name: string; draft: string; skill: boolean; files: string[]; messages: Message[] }
export type Task = { id: string; name: string; workspace: string; owner: string; completed: boolean; updated: string; sessions: Session[]; active: string }
export const uid = () => crypto.randomUUID()
export const stamp = () => new Date().toLocaleString('sv-SE', { timeZone: 'Asia/Shanghai' }).slice(0, 16)
export const makeSession = (name: string): Session => ({ id: uid(), name, draft: '', skill: false, files: [], messages: [] })
function seed(): Task[] {
  const make = (name: string, workspace: string, owner: string, names: string[], completed = false): Task => {
    const sessions = names.map(makeSession)
    if (sessions[0]) sessions[0].messages = [
      { id: uid(), role: 'user', text: '这套新品图先做一版简约风格，突出产品细节。保留产品真实比例，使用浅色背景。', time: '2026-11-17 09:32' },
      { id: uid(), role: 'assistant', text: '可以。这个方案以浅色背景和产品细节为主。请继续补充实拍素材与图需，我会在当前方案会话中继续处理。\n\n这是用于体验流程的示例对话，不代表真实生成结果。', time: '2026-11-17 09:33' },
    ]
    return { id: uid(), name, workspace, owner, completed, updated: '2026-11-17 09:33', sessions, active: sessions[0]?.id || '' }
  }
  return [make('iPhone 17 透明手机壳新品主图', 'case', '我', ['方案一 · 简约白底', '方案二 · 户外场景', '方案三 · 节日氛围']), make('运动相机保护套 · 京东新品图', 'camera', '我', ['方案一 · 产品细节', '方案二 · 运动场景']), make('磁吸支架主图产品替换', 'product', '我', ['方案一 · 保留原构图'], true), make('冬季新品场景设计', 'scene', '示例成员 A', ['方案一 · 室内暖光', '方案二 · 户外雪景']), make('手机屏幕壁纸替换', 'phone', '示例成员 B', ['方案一 · 蓝色壁纸'])]
}
const key = 'hx-isolated-task-preview-v1'
let initial = seed()
try { const saved = JSON.parse(localStorage.getItem(key) || 'null'); if (Array.isArray(saved) && saved.every(t => t.id && Array.isArray(t.sessions))) initial = saved } catch { /* keep demo */ }
export const tasks = reactive<Task[]>(initial)
export const previewRole = ref<'designer' | 'operator' | 'super_admin'>('designer')
try { const savedRole = sessionStorage.getItem('hx-task-preview-role'); if (savedRole === 'super_admin' || savedRole === 'operator') previewRole.value = savedRole } catch { /* preview default */ }
export const admin = computed(() => previewRole.value === 'super_admin')
watch(previewRole, value => { try { sessionStorage.setItem('hx-task-preview-role', value) } catch { /* current page remains usable */ } })
export const storageNotice = ref('')
watch(tasks, () => { try { localStorage.setItem(key, JSON.stringify(tasks)); storageNotice.value = '' } catch { storageNotice.value = '浏览器未能保存预览数据，请保持页面打开。' } }, { deep: true, immediate: true })
export function reset() { tasks.splice(0, tasks.length, ...seed()) }
