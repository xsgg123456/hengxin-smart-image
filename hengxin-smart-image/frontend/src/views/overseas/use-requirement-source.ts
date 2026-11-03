import { computed, onUnmounted, ref, watch, type Ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { IdentityError } from '@/api/identity/request'
import { taskError, type Designer } from '@/api/overseas/tasks'
import type { DraftFields, DraftsApi, Requirement } from '@/api/overseas/requirement-drafts'
import type { createDraftController } from './requirement-draft-controller'
import { mapRequirement } from './requirement-source'
export function useRequirementSource(fields: Ref<DraftFields>, controller: ReturnType<typeof createDraftController>, api: DraftsApi, failure: (reason: unknown) => void, uploading: () => boolean) {
  const querying = ref(false), applying = ref(false), choosing = ref(false), confirming = ref(false), matches = ref<Requirement[]>([]), selected = ref(''), designer = ref<Designer | null>(null)
  const notice = ref(''), warnings = ref<string[]>([]), noticeType = ref<'info' | 'warning' | 'success' | 'error'>('info')
  let generation = 0
  const sku = computed(() => fields.value.skus[0]?.code.trim() || '')
  const sourceMismatch = computed(() => !!controller.state.server?.source && controller.state.server.source.sku !== sku.value)
  watch(sku, () => { ++generation; querying.value = false; choosing.value = false; matches.value = []; selected.value = ''; notice.value = ''; warnings.value = [] }, { flush: 'sync' })
  async function query() {
    if (!sku.value || querying.value || applying.value || confirming.value) return
    const value = sku.value, current = ++generation
    querying.value = true; notice.value = ''; warnings.value = []; matches.value = []; selected.value = ''
    try {
      const result = await api.query(value)
      if (current !== generation) return
      if (result.truncated) throw Error('需求记录超过查询上限，请缩小 SKU 查询；未自动选择或丢弃记录。')
      matches.value = result.list
      if (!result.list.length) { noticeType.value = 'warning'; notice.value = `未找到 SKU「${value}」对应的需求，请检查 SKU 或手动填写。` }
      else if (result.list.length === 1) await apply(result.list[0])
      else choosing.value = true
    } catch (reason) {
      if (current !== generation) return
      noticeType.value = 'error'; notice.value = `查询失败：${taskError(reason)}。已填写内容保持不变。`
      if (reason instanceof IdentityError && [401, 403].includes(reason.status)) failure(reason)
    } finally { if (current === generation) querying.value = false }
  }
  async function apply(record: Requirement) {
    if (applying.value || confirming.value) return
    if (uploading()) {
      noticeType.value = 'warning'; notice.value = '文件正在上传，请等待上传结束后再获取需求。'; return
    }
    const current = generation, value = sku.value
    if (record.files.length > 100) { noticeType.value = 'error'; notice.value = '该需求附件超过 100 份，不能自动导入，请先在需求系统整理附件。'; return }
    const hasContent = Object.entries(fields.value).some(([key, v]) => key !== 'skus' && !!v) || !!controller.state.server?.materials.length || !!controller.state.server?.imports.length
    if (hasContent) {
      confirming.value = true
      try { await ElMessageBox.confirm('将用所选需求的非空信息回填表单。切换需求会替换现有附件，手动修改的内容可能被覆盖；空值或无法匹配的字段保留原值并提示核对。', '确认回填需求', { type: 'warning', confirmButtonText: '确认回填', cancelButtonText: '保留当前内容' }) }
      catch { return } finally { confirming.value = false }
    }
    if (current !== generation || value !== sku.value) return
    applying.value = true
    try {
      const mapped = mapRequirement(fields.value, record)
      const result = await controller.mutate(server => api.source(server.version, value, record.id, mapped.fields), true)
      if (current !== generation || !result) return
      fields.value = { ...result.fields, skus: result.fields.skus.map(s => ({ ...s })) }
      designer.value = record.matchedDesigner; warnings.value = mapped.warnings; choosing.value = false
      noticeType.value = warnings.value.length ? 'warning' : 'success'
      notice.value = warnings.value.length ? '需求已回填，部分字段需要手动核对。' : '需求已回填，可继续修改；附件正在后台自动导入。'
    } catch (reason) { if (current === generation) { noticeType.value = 'error'; notice.value = taskError(reason) } }
    finally { if (current === generation) applying.value = false }
  }
  onUnmounted(() => { ++generation })
  return { querying, applying, confirming, choosing, matches, selected, designer, notice, warnings, noticeType, sourceMismatch, query, apply }
}
