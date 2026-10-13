import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
export const skills = ['Amazon · OUTON · 灯具主图', 'Amazon · OUTON · 灯具 A+', 'Amazon · OUTONLIFE · 家居主图', 'Amazon · OUTONLIFE · 家居 A+', 'Amazon · BELEEV · 户外主图', 'Amazon · BELEEV · 户外 A+', 'Wayfair · OUTON · 主图与 A+', 'Walmart · 新品套图', '多平台 · 产品替换']
export const samples = [1, 2, 3, 4, 5, 6, 7, 8].map(i => new URL(`./assets/sample-${i}.jpg`, import.meta.url).href)
export function imageNumber(url: string) { return samples.findIndex(sample => new URL(sample).pathname === new URL(url).pathname) + 1 }
export const taskMaterials = [
  { key: 'brief', name: '图需说明（示例）.txt', image: false, url: new URL('./assets/task-brief.txt', import.meta.url).href },
  ...samples.slice(0, 3).map((url, i) => ({ key: `reference-${i}`, name: `参考图片 ${i + 1}（示例）.jpg`, image: true, url }))
]
export type Attachment = { id: number; name: string; url: string; image: boolean }
export type Message = { id: number; role: 'user' | 'assistant'; text: string; skill?: string; files?: Attachment[]; pictures?: string[] }
export function useStudio() {
  const text = ref(''), skill = ref(skills[0]), busy = ref(false), messages = ref<Message[]>([])
  const attachments = ref<Attachment[]>([]), selected = ref<string[]>([]), archived = ref<string[]>([])
  const chat = ref<HTMLElement>()
  const reference = ref(''), archiveOpen = ref(false), materialsOpen = ref(true)
  const allFiles = computed(() => messages.value.flatMap(m => m.files || []))
  const canSend = computed(() => !busy.value && (!!text.value.trim() || attachments.value.length > 0))
  const urls = new Set<string>()
  let serial = 0, timer: ReturnType<typeof setTimeout> | undefined
  function batchPictures() { return samples.map(source => { const url = new URL(source); url.searchParams.set('batch', String(++serial)); return url.href }) }
  function scroll() { void nextTick(() => chat.value?.scrollTo({ top: chat.value.scrollHeight, behavior: 'smooth' })) }
  function receive(files: File[]) {
    for (const file of files) {
      const isImage = /\.(png|jpe?g|webp)$/i.test(file.name) && /^image\/(png|jpeg|webp)$/.test(file.type)
      if (!isImage && !/\.(pdf|pptx?|docx?|xlsx?|csv|txt)$/i.test(file.name)) { ElMessage.warning(`${file.name}：请使用 JPG、PNG、WebP 或常见文档`); continue }
      if (!file.size || file.size > 20 * 1024 * 1024) { ElMessage.warning(`${file.name}：文件不能为空，最大 20 MB`); continue }
      const url = URL.createObjectURL(file); urls.add(url)
      attachments.value.push({ id: ++serial, name: file.name, url, image: isImage })
    }
  }
  function addMaterials(keys: string[]) {
    for (const item of taskMaterials.filter(item => keys.includes(item.key))) {
      if (!attachments.value.some(file => file.url === item.url)) attachments.value.push({ id: ++serial, name: item.name, image: item.image, url: item.url })
    }
  }
  function upload(event: Event) { const input = event.target as HTMLInputElement; receive(Array.from(input.files || [])); input.value = '' }
  function paste(event: ClipboardEvent) { if (event.clipboardData?.files.length) { event.preventDefault(); receive(Array.from(event.clipboardData.files)) } }
  function removeAttachment(id: number) { const file = attachments.value.find(f => f.id === id); if (file) { URL.revokeObjectURL(file.url); urls.delete(file.url) }; attachments.value = attachments.value.filter(f => f.id !== id) }
  function send() {
    if (!canSend.value) return
    const prompt = text.value.trim()
    messages.value.push({ id: ++serial, role: 'user', text: `${reference.value ? `针对图片 ${imageNumber(reference.value)}：` : ''}${prompt || '请查看这些附件。'}`, skill: skill.value || undefined, files: [...attachments.value] })
    text.value = ''; attachments.value = []; reference.value = ''; busy.value = true; scroll()
    timer = setTimeout(() => {
      messages.value.push({ id: ++serial, role: 'assistant', text: '模拟回复：这里会展示 Codex 的回答和生成图片。下方使用现有 Skill 中的参考样图演示查看、修改和归档，未进行实际生成。', pictures: batchPictures() })
      busy.value = false; scroll()
    }, 1100)
  }
  function stop() { clearTimeout(timer); busy.value = false; messages.value.push({ id: ++serial, role: 'assistant', text: '已停止本轮模拟，可以继续补充要求。' }); scroll() }
  function modify(url: string) { reference.value = url; text.value = ''; void nextTick(() => document.querySelector<HTMLTextAreaElement>('.studio-composer textarea')?.focus()) }
  function toggle(url: string) { selected.value = selected.value.includes(url) ? selected.value.filter(s => s !== url) : [...selected.value, url] }
  function toggleGroup(pictures: string[]) {
    selected.value = pictures.every(url => selected.value.includes(url))
      ? selected.value.filter(url => !pictures.includes(url))
      : [...new Set([...selected.value, ...pictures])]
  }
  function archive() { archived.value = [...new Set([...archived.value, ...selected.value])]; selected.value = []; archiveOpen.value = false; ElMessage.success('已归档到本次预览的成品库') }
  async function removeArchive(url: string) {
    try { await ElMessageBox.confirm('从本次预览成品库移除此图片？对话中的图片仍保留。', '移除归档', { type: 'warning', confirmButtonText: '移除', cancelButtonText: '取消' }); archived.value = archived.value.filter(s => s !== url) } catch { /* cancelled */ }
  }
  async function clear() {
    try { await ElMessageBox.confirm('清空本次预览对话和附件？已归档图片保留。', '清空对话', { confirmButtonText: '清空', cancelButtonText: '取消' }) } catch { return }
    clearTimeout(timer); busy.value = false; messages.value = []; attachments.value = []; selected.value = []; text.value = ''; reference.value = ''
    urls.forEach(url => URL.revokeObjectURL(url)); urls.clear()
  }
  function example() {
    messages.value.push({ id: ++serial, role: 'user', text: '按照需求，帮我制作这款落地灯的整套主图。', skill: skills[0] }, { id: ++serial, role: 'assistant', text: '以下为交互示例。你可以点击图片放大，继续提出修改要求，或勾选满意的图片归档。图片来自你提供的 Skill 参考资料，并非本次生成。', pictures: batchPictures() }); scroll()
  }
  onBeforeUnmount(() => { clearTimeout(timer); urls.forEach(url => URL.revokeObjectURL(url)) })
  return { text, skill, busy, messages, attachments, selected, archived, chat, reference, archiveOpen, materialsOpen, allFiles, canSend, addMaterials, upload, receive, paste, removeAttachment, send, stop, modify, toggle, toggleGroup, archive, removeArchive, clear, example }
}
