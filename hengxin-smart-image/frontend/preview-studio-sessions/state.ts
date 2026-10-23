import { computed, onUnmounted, ref } from 'vue'
import { makeTurn, materials } from '../preview-studio-process/fixtures'
import type { PreviewTurn } from '../preview-studio-process/fixtures'
import type { Asset } from '../preview-studio-images/state'

export interface Session {
  id: string; name: string; draft: string; skill: string; attachments: Asset[]
  turns: PreviewTurn[]; selected: string[]; unread: boolean; scroll: number
}
export interface Archived { asset: Asset; sessionId: string; sessionName: string; sku: string }
export const taskName = '直杆实木布罩灯-乡村风 整套 测试 新版V2'
export function useSessions() {
  let number = 3
  const make = (name: string): Session => ({ id: crypto.randomUUID(), name, draft: '', skill: '', attachments: [], turns: [], selected: [], unread: false, scroll: 0 })
  const sessions = ref<Session[]>([make('主图方案'), make('详情页方案'), make('风格探索')])
  sessions.value[0].turns = [makeTurn('initial-main')]
  sessions.value[2].turns = [makeTurn('initial-style', 'succeeded', '探索温暖乡村风的场景设计。')]
  const activeId = ref(sessions.value[0].id), completed = ref(false), archived = ref<Archived[]>([])
  const current = computed(() => sessions.value.find(s => s.id === activeId.value)!)
  const running = (s: Session) => s.turns.some(t => t.status === 'running')
  const runningCount = computed(() => sessions.value.filter(running).length)
  const selectedPictures = computed(() => current.value.turns.flatMap(t => t.pictures).filter(p => current.value.selected.includes(p.id)))
  const timers = new Map<string, ReturnType<typeof setInterval>>()
  function clear(id: string) { const timer = timers.get(id); if (timer) clearInterval(timer); timers.delete(id) }
  function switchTo(s: Session) { activeId.value = s.id; s.unread = false }
  function create() { if (sessions.value.length >= 10 || completed.value) return; const s = make(`会话 ${++number}`); sessions.value.push(s); switchTo(s) }
  function finish(s: Session, status: 'succeeded' | 'failed' | 'cancelled' = 'succeeded') {
    const turn = s.turns.find(t => t.status === 'running'); if (!turn) return
    clear(s.id); turn.status = status
    if (status === 'succeeded') Object.assign(turn, makeTurn(turn.id, status, turn.text))
    else turn.pictures = []
    s.unread = activeId.value !== s.id
  }
  function send() {
    const s = current.value
    if (completed.value || running(s) || (!s.draft.trim() && !s.attachments.length)) return
    const text = s.draft.trim() || '请根据本轮引用的资料制作图片。'
    const input = s.attachments.length ? `${text}\n\n本轮引用：${s.attachments.map(a => a.name).join('、')}` : text
    const turn = makeTurn(crypto.randomUUID(), 'running', input), entries = turn.entries
    turn.entries = []; turn.pictures = []; turn.reply = ''; s.turns.push(turn)
    s.draft = ''; s.attachments = []
    let index = 0
    timers.set(s.id, setInterval(() => {
      const live = s.turns[s.turns.length - 1]
      if (index < entries.length) live.entries.push(entries[index++]); else finish(s)
    }, 3500))
  }
  function remove(s: Session) {
    if (running(s) || completed.value) return
    clear(s.id); sessions.value = sessions.value.filter(row => row.id !== s.id)
    if (!sessions.value.length) { sessions.value.push(make(`会话 ${++number}`)) }
    if (activeId.value === s.id) switchTo(sessions.value[0])
  }
  function add(assets: Asset[]) {
    if (completed.value) return
    const s = current.value
    for (const a of assets) if (!s.attachments.some(v => v.id === a.id)) s.attachments.push(a)
  }
  function toggle(id: string) { const s = current.value; s.selected = s.selected.includes(id) ? s.selected.filter(v => v !== id) : [...s.selected, id] }
  function group(assets: Asset[]) { const s = current.value; const all = assets.every(a => s.selected.includes(a.id)); for (const a of assets) if (all || !s.selected.includes(a.id)) toggle(a.id) }
  function archive(sku: string) {
    if (completed.value) return
    for (const asset of selectedPictures.value) if (!archived.value.some(a => a.asset.id === asset.id)) archived.value.push({ asset, sessionId: current.value.id, sessionName: current.value.name, sku })
    current.value.selected = []
  }
  function previewCompleted() {
    for (const s of sessions.value) finish(s)
    if (!archived.value.length) {
      let source = sessions.value.find(s => s.turns.some(t => t.pictures.length))
      if (!source) { source = current.value; source.turns.push(makeTurn(crypto.randomUUID())) }
      const asset = source.turns.flatMap(t => t.pictures)[0]
      archived.value.push({ asset, sessionId: source.id, sessionName: source.name, sku: 'H-ZGD0008' })
    }
    completed.value = true
  }
  function label(s: Session) {
    if (running(s)) return '生成中'
    if (s.unread) return s.turns.at(-1)?.status === 'failed' ? '执行失败 · 未读' : '有新结果'
    return ({ failed: '执行失败', cancelled: '已停止', succeeded: '已完成', running: '生成中' } as const)[s.turns.at(-1)?.status || 'succeeded'] || '待开始'
  }
  onUnmounted(() => { for (const id of timers.keys()) clear(id) })
  return { sessions, current, activeId, completed, archived, running, runningCount, selectedPictures, switchTo, create, finish, send, remove, add, toggle, group, archive, previewCompleted, label, materials }
}
