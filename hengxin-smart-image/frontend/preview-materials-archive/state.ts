import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { PreparedAnnotation } from '@/views/hengxin/components/annotation/AnnotationEditor.vue'
import { useMaterials } from './materials-state'
export type Asset = { id: string; name: string; url: string; image: boolean; caption?: string; fingerprint?: string }
export type Turn = { id: string; role: 'user' | 'assistant'; text: string; files: Asset[]; pictures?: Asset[] }
export type Revision = { base: Asset; annotation?: Asset; text: string }
const samples = [1, 2, 3, 4, 5, 6, 7].map(i => new URL(`../preview-ai-studio/assets/sample-${i}.jpg`, import.meta.url).href)
export const pictures: Asset[] = samples.slice(0, 2).map((url, i) => ({ id: `result-${i}`, name: `0${i + 1}.jpg`, url, image: true, caption: '灯具样图 · 交互示例' }))
const document: Asset = { id: 'doc', name: '图需说明（示例）.txt', url: new URL('../preview-ai-studio/assets/task-brief.txt', import.meta.url).href, image: false, caption: '图需资料 · 示例文件' }
export const initialMaterials: Asset[] = [document, ...samples.map((url, i) => ({ id: `material-${i}`, name: `产品参考-${i + 1}.jpg`, url, image: true, caption: '产品参考 · 示例素材' }))]
export function usePreview() {
  const urls = new Set<string>()
  const duplicates = initialMaterials.slice(0, 3).map(a => ({ ...a, id: `${a.id}-duplicate` }))
  const { materials, removeMaterial, register, rememberSent, demoDuplicate, resetMaterials } = useMaterials([...initialMaterials, ...duplicates], urls)
  const attachments = ref<Asset[]>(initialMaterials.slice(2, 4))
  const turns = ref<Turn[]>([
    { id: 'seed-user', role: 'user', text: '请结合需求资料和这些产品图片，制作灯具主图。', files: initialMaterials.slice(0, 4) },
    { id: 'seed-assistant', role: 'assistant', text: '以下是交互示例图片。点击图片查看原图，点击“修改这张”圈出需要调整的位置。', files: [], pictures },
  ])
  const text = ref(''), skill = ref('OUTON 亚马逊新品整套主图生成'), revisions = ref<Revision[]>([])
  const editing = ref<Asset>(), epoch = ref(0), selected = ref<string[]>([]), archived = ref<string[]>([])
  const chat = ref<HTMLElement>()
  const sending = ref(false)
  const canSend = computed(() => !sending.value && (!!text.value.trim() || (revisions.value.length ? revisions.value.some(r => !!r.text.trim()) : !!attachments.value.length)))
  function scroll() { void nextTick(() => chat.value?.scrollTo({ top: chat.value.scrollHeight, behavior: 'smooth' })) }
  function add(items: Asset[]) {
    const newItems = items.filter(a => !attachments.value.some(b => a.id === b.id))
    if (attachments.value.length + newItems.length > 100) { ElMessage.warning('每轮最多100个附件'); return }
    attachments.value.push(...newItems)
  }
  async function receive(files: File[]) {
    for (const file of files) {
      if (attachments.value.length >= 100) { ElMessage.warning('每轮最多100个附件'); break }
      const image = /\.(jpe?g|png|webp)$/i.test(file.name) && /^image\/(jpeg|png|webp)$/.test(file.type)
      if (!image && !/\.(pdf|docx|pptx|xlsx?|csv|txt)$/i.test(file.name)) { ElMessage.warning(`${file.name}：不支持此文件格式`); continue }
      if (!file.size || file.size > 500000000) { ElMessage.warning('文件不能为空，单个最大500 MB'); continue }
      try { add([await register(file, image)]) } catch { ElMessage.error('本地预览保存失败，请重试') }
    }
  }
  function confirm(value: PreparedAnnotation) {
    if (!editing.value) return
    let annotation: Asset | undefined
    if (value.file) {
      const url = URL.createObjectURL(value.file); urls.add(url)
      annotation = { id: crypto.randomUUID(), name: `${editing.value.name.replace(/\.[^.]+$/, '')}-标注.png`, url, image: true, caption: '标注图 · 仅用于定位' }
    }
    const revision = { base: editing.value, annotation, text: value.text }
    const index = revisions.value.findIndex(r => r.base.id === editing.value?.id)
    if (index >= 0) revisions.value[index] = revision
    else revisions.value.push(revision)
    editing.value = undefined
    ElMessage.success('已带回输入区，补充后点击发送')
    void nextTick(() => {
      const files = window.document.querySelector<HTMLElement>('.composer-files')
      files?.scrollTo({ top: files.scrollHeight, behavior: 'smooth' })
      window.document.querySelector<HTMLTextAreaElement>('.studio-composer textarea')?.focus()
    })
  }
  async function send() {
    if (!canSend.value) return
    const files = [...attachments.value]
    for (const r of revisions.value) files.push(r.base, ...(r.annotation ? [r.annotation] : []))
    sending.value = true
    try { await rememberSent(files) }
    catch { ElMessage.error('本地附件保存失败，请重试'); return }
    finally { sending.value = false }
    const message = [...revisions.value.map(r => `修改 ${r.base.name}：\n${r.text}`), text.value.trim()].filter(Boolean).join('\n\n') || '请查看这些附件。'
    turns.value.push({ id: crypto.randomUUID(), role: 'user', text: message, files })
    turns.value.push({ id: crypto.randomUUID(), role: 'assistant', text: '模拟发送成功。正式接入后，Codex 会收到原图、标注图和修改意见；本预览未调用 AI，也没有生成新图片。', files: [] })
    text.value = ''; attachments.value = []; revisions.value = []; epoch.value++; scroll()
  }
  function toggle(id: string) { selected.value = selected.value.includes(id) ? selected.value.filter(x => x !== id) : [...selected.value, id] }
  function toggleGroup(group: Asset[]) { const ids = group.map(p => p.id); selected.value = ids.every(id => selected.value.includes(id)) ? selected.value.filter(id => !ids.includes(id)) : [...new Set([...selected.value, ...ids])] }
  async function archive() {
    try { await ElMessageBox.confirm(`将所选 ${selected.value.length} 张图片归档到本次预览？`, '归档成品', { confirmButtonText: '确认归档', cancelButtonText: '取消' }) } catch { return }
    archived.value = [...new Set([...archived.value, ...selected.value])]; selected.value = []; ElMessage.success('已在本次预览中归档')
  }
  onBeforeUnmount(() => urls.forEach(url => URL.revokeObjectURL(url)))
  return { materials, attachments, turns, text, skill, revisions, editing, epoch, selected, archived, chat, canSend, add, receive, confirm, send, toggle, toggleGroup, archive, removeMaterial, demoDuplicate, resetMaterials }
}
