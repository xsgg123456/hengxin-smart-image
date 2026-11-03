import { computed, onUnmounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { OVERSEAS_PLATFORMS } from '@/views/overseas/platforms'
import { OVERSEAS_LANGUAGES } from '@/views/overseas/languages'
import { designers, fixtures, pause, type PreviewFile, type Requirement } from './fixtures'

const emptyDraft = () => ({ name: '', productName: '', brand: '', platform: '', language: '', market: '', skus: [{ code: '' }] })
export function useImportPreview() {
  const draft = ref(emptyDraft()), designer = ref(''), files = ref<PreviewFile[]>([])
  const querying = ref(false), applying = ref(false), choosing = ref(false), confirming = ref(false)
  const matches = ref<Requirement[]>([]), selected = ref(''), active = ref<Requirement>(), sourceSku = ref('')
  const notice = ref(''), noticeType = ref<'success' | 'warning' | 'error' | 'info'>('info'), warnings = ref<string[]>([])
  let generation = 0
  const importing = computed(() => files.value.some(f => f.state === 'importing'))
  const locked = computed(() => querying.value || applying.value || confirming.value || importing.value)
  const selectedRecord = computed(() => matches.value.find(r => r.id === selected.value))
  const sourceMismatch = computed(() => !!active.value && sourceSku.value !== draft.value.skus[0].code.trim())
  const canSubmit = computed(() => !locked.value && !!draft.value.skus[0].code.trim() && !!draft.value.name.trim() && !!draft.value.productName.trim() && !!draft.value.brand && !!draft.value.platform && !!draft.value.language && !!designer.value && files.value.some(f => f.state === 'ready') && !files.value.some(f => f.state !== 'ready') && (!active.value || sourceSku.value === draft.value.skus[0].code.trim()))
  const hasContent = () => !!(draft.value.name || draft.value.productName || draft.value.brand || draft.value.platform || draft.value.language || designer.value || files.value.length)
  function updateFileNotice() {
    if (sourceMismatch.value) return
    const failed = files.value.filter(f => f.state === 'failed').length
    noticeType.value = failed || warnings.value.length ? 'warning' : 'success'
    notice.value = failed ? `${failed} 个附件导入失败，请重试或移除后继续。成功附件已保留。` : warnings.value.length ? '需求已回填，部分字段需要手动核对。' : files.value.length ? `需求及 ${files.value.length} 个附件已就绪，请核对后提交。` : '当前没有附件，请至少添加一份资料。'
  }
  function reset(sku = '') {
    ++generation; draft.value = emptyDraft(); draft.value.skus[0].code = sku; designer.value = ''; files.value = []
    querying.value = false; applying.value = false; choosing.value = false; confirming.value = false
    active.value = undefined; sourceSku.value = ''; notice.value = ''; warnings.value = []; matches.value = []; selected.value = ''
  }
  watch(() => draft.value.skus[0].code, () => {
    ++generation; querying.value = false; choosing.value = false; matches.value = []; selected.value = ''
    notice.value = active.value && sourceSku.value !== draft.value.skus[0].code.trim() ? 'SKU 已更改，当前内容来自上一条需求。请重新获取需求，或重置表单后手动填写。' : ''
    noticeType.value = 'warning'
  }, { flush: 'sync' })
  async function query() {
    const sku = draft.value.skus[0].code.trim()
    if (!sku || locked.value) return
    const current = ++generation; querying.value = true; notice.value = ''; matches.value = []; selected.value = ''
    await pause(700)
    if (current !== generation) return
    querying.value = false
    if (sku === 'DEMO-ERROR') { noticeType.value = 'error'; notice.value = '查询失败，暂时无法连接需求系统。请重试，已填写内容保持不变。'; return }
    matches.value = fixtures[sku] || []
    if (!matches.value.length) { noticeType.value = 'warning'; notice.value = `未找到 SKU「${sku}」对应的需求，请检查 SKU 或手动填写。`; return }
    if (matches.value.length === 1) await apply(matches.value[0], sku)
    else choosing.value = true
  }
  async function importFile(f: PreviewFile, current: number, retry = false) {
    f.state = 'importing'; f.progress = 0
    for (const step of [28, 63, 100]) { await pause(230); if (generation !== current) return; f.progress = step }
    f.state = f.id === 'demo-fail' && !retry ? 'failed' : 'ready'
  }
  async function apply(record: Requirement, sku = draft.value.skus[0].code.trim()) {
    if (applying.value || confirming.value) return
    const current = generation
    if (hasContent()) {
      confirming.value = true
      try { await ElMessageBox.confirm('将用所选需求的非空信息回填表单。切换需求会替换现有附件，手动修改的内容可能被覆盖；空值或无法匹配的字段保留原值并提示核对。', '确认回填需求', { confirmButtonText: '确认回填', cancelButtonText: '保留当前内容', type: 'warning' }) }
      catch { return }
      finally { confirming.value = false }
    }
    if (current !== generation || sku !== draft.value.skus[0].code.trim()) return
    applying.value = true; choosing.value = false; warnings.value = []
    const mappings = [
      ['platform', '目标平台', record.platformName, OVERSEAS_PLATFORMS.find(p => p.label === record.platformName || p.value === record.platformName)?.value],
      ['brand', '品牌', record.brandName, ['OUTON', 'OUTONLIFE', 'BELEEV'].find(b => b === record.brandName)],
      ['language', '语言', record.language, OVERSEAS_LANGUAGES.find(l => l.label === record.language || l.value === record.language)?.value],
    ] as const
    for (const [key, label, value, mapped] of mappings) {
      if (mapped) draft.value[key] = mapped
      else warnings.value.push(`${label}：${value ? `「${value}」无法匹配` : '上游未填写'}，请手动核对。`)
    }
    for (const [key, label, value] of [['name', '任务名称', record.title], ['productName', '品名', record.productName]] as const) {
      if (value && value.length <= 80) draft.value[key] = value
      else warnings.value.push(`${label}：${value ? '内容超过 80 字' : '上游未填写'}，请手动补充。`)
    }
    if (designers.filter(d => d === record.designerName).length === 1) designer.value = record.designerName
    else warnings.value.push(`负责设计：「${record.designerName || '未填写'}」无法唯一匹配，请手动选择。`)
    if (active.value?.id !== record.id) files.value = []
    active.value = record; sourceSku.value = sku
    const added: PreviewFile[] = []
    for (const source of record.files) {
      if (files.value.some(f => f.id === source.id)) continue
      files.value.push({ ...source, kind: /\.pptx?$/i.test(source.filename) ? 'requirement' : 'competitor', state: 'importing', progress: 0 })
      added.push(files.value[files.value.length - 1])
    }
    noticeType.value = warnings.value.length ? 'warning' : 'success'
    notice.value = warnings.value.length ? '需求已回填，部分字段需要手动核对。' : '需求已回填，可继续修改；附件正在自动导入。'
    await Promise.all(added.map(f => importFile(f, current)))
    if (current !== generation) return
    applying.value = false
    updateFileNotice()
  }
  async function retry(f: PreviewFile) {
    if (locked.value) return
    const current = generation
    await importFile(f, current, true)
    if (current === generation) updateFileNotice()
  }
  async function remove(f: PreviewFile) {
    if (locked.value) return
    const current = generation
    try { await ElMessageBox.confirm(`移除「${f.filename}」？只移除当前表单中的附件。`, '移除附件', { type: 'warning', confirmButtonText: '确认移除', cancelButtonText: '取消' }); if (current === generation) { files.value = files.value.filter(item => item.id !== f.id); updateFileNotice() } } catch { /* 用户取消 */ }
  }
  function add(raw: File, kind: PreviewFile['kind']) {
    if (locked.value) return
    if (!raw.size || raw.size > 500000000) { ElMessage.error('文件不能为空，单份不得超过 500 MB。'); return }
    files.value.push({ id: crypto.randomUUID(), filename: raw.name, size: raw.size, kind, state: 'ready', progress: 100, local: raw })
    if (active.value) updateFileNotice()
  }
  function download(f: PreviewFile) {
    if (!f.local) { ElMessage.info('这是交互预览中的附件样例，未下载上游原件。你手动添加的本地附件可以下载。'); return }
    const url = URL.createObjectURL(f.local), a = document.createElement('a'); a.href = url; a.download = f.filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  onUnmounted(() => { ++generation })
  return { draft, designer, files, querying, applying, choosing, matches, selected, selectedRecord, active, sourceMismatch, notice, noticeType, warnings, locked, canSubmit, reset, query, apply, retry, remove, add, download }
}
