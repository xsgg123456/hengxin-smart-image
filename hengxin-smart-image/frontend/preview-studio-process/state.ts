import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { makeTurn, type PreviewStatus } from './fixtures'
import type { Asset } from '../preview-studio-images/state'

export function useProcessPreview() {
  let serial = 0
  const turns = ref([makeTurn(`turn-${serial++}`)])
  const selected = ref<string[]>([]), archived = ref<string[]>([]), text = ref('')
  const chat = ref<HTMLElement>(), pending = ref<Asset[]>([])
  const running = computed(() => turns.value.some(t => t.status === 'running'))
  const timers: ReturnType<typeof setTimeout>[] = []
  function clearTimers() { for (const timer of timers) clearTimeout(timer); timers.length = 0 }
  function scroll(bottom = false) { void nextTick(() => chat.value?.scrollTo({ top: bottom ? chat.value.scrollHeight : 0 })) }
  function show(status: PreviewStatus, multiple = false) {
    clearTimers(); selected.value = []; pending.value = []
    turns.value = multiple ? [makeTurn(`turn-${serial++}`), makeTurn(`turn-${serial++}`, 'succeeded', '场景图请再突出灯罩的亚麻纹理，保持灯杆比例不变。')] : [makeTurn(`turn-${serial++}`, status)]
    if (multiple) turns.value[1].reply = '已按你的要求整理了第二轮示例：加强灯罩的亚麻纹理表现，保持灯杆比例和整体构图。下方图片用于演示本轮产物的位置。'
    scroll(status === 'succeeded' && !multiple)
  }
  function play(append = false) {
    clearTimers()
    if (!append) show('running')
    else {
      if (running.value) return
      turns.value.push(makeTurn(`turn-${serial++}`, 'running', text.value.trim() || '请继续细化灯罩纹理，保持产品比例不变。'))
      text.value = ''; pending.value = []
    }
    const turn = turns.value[turns.value.length - 1], all = [...turn.entries]
    if (append) turn.reply = '已收到本轮修改要求。这里演示完成后自动收起过程，保留最终回复和本轮图片的位置。预览使用现有样图，不会实际生成或修改图片。'
    turn.entries = all.slice(0, 2)
    scroll(append)
    timers.push(setTimeout(() => { turn.entries = all.slice(0, 5) }, 2500))
    timers.push(setTimeout(() => { turn.entries = all }, 5000))
    timers.push(setTimeout(() => { turn.status = 'succeeded'; scroll(append) }, 8000))
  }
  function finish() { clearTimers(); const turn = turns.value.at(-1); if (turn?.status === 'running') turn.status = 'succeeded' }
  function stop() { clearTimers(); const turn = turns.value.at(-1); if (turn?.status === 'running') turn.status = 'cancelled' }
  function toggle(id: string) { selected.value = selected.value.includes(id) ? selected.value.filter(x => x !== id) : [...selected.value, id] }
  function group(assets: Asset[]) { const ids = assets.map(a => a.id); selected.value = ids.every(id => selected.value.includes(id)) ? selected.value.filter(id => !ids.includes(id)) : [...new Set([...selected.value, ...ids])] }
  function explain() { ElMessage.info('当前为过程折叠交互预览，示例数据仅保存在本页。') }
  function add(assets: Asset[]) { pending.value = [...new Map([...pending.value, ...assets].map(a => [a.id, a])).values()] }
  function modify(asset: Asset) { text.value = `请修改 ${asset.name}：`; void nextTick(() => document.querySelector<HTMLTextAreaElement>('.studio-composer textarea')?.focus()) }
  onBeforeUnmount(clearTimers)
  onMounted(() => scroll(true))
  return { turns, selected, archived, text, chat, pending, running, show, play, finish, stop, toggle, group, explain, add, modify }
}
