import { computed, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getTemplate, listTemplates } from '@/api/templates'
import { listSkills } from '@/api/skills'
import type { Mode, Picture, SkillVersion, Template } from '@/types/hengxin'
import { createTask } from './model'

export function useCreateTask(mode: Ref<Mode>) {
  const router = useRouter(), route = useRoute()
  const available = ref<Template[]>([]), template = ref<Template>()
  const skillVersions = ref<SkillVersion[]>([])
  const sources = ref<Picture[]>([]), name = ref(''), sku = ref(''), note = ref('')
  const search = ref(''), page = ref(1), total = ref(0), pageSize = 4
  const loading = ref(false), loadError = ref(''), error = ref(''), submitting = ref(false), uploadBlocked = ref(false)
  let sequence = 0, alive = true
  onBeforeUnmount(() => { alive = false; sequence++ })
  const skill = computed(() => skillVersions.value.find(s => s.mode === mode.value && s.status === 'available'
    && (mode.value === 'text' ? s.isDefault : s.id === template.value?.skillVersionId)))
  const blocked = computed(() => submitting.value || loading.value || !!loadError.value || uploadBlocked.value || !skill.value
    || (mode.value !== 'text' && !template.value))
  function select(value: Template) { template.value = value; error.value = '' }
  async function load() {
    const current = ++sequence
    const requestedMode = mode.value
    loading.value = true; loadError.value = ''
    try {
      const [catalog, result] = await Promise.all([
        listSkills(requestedMode), requestedMode === 'text' ? undefined : listTemplates({
          page: page.value, pageSize, search: search.value.trim(), mode: requestedMode, activeOnly: true, sort: 'updated'
        })
      ])
      if (current !== sequence) return
      skillVersions.value = catalog
      available.value = result?.items ?? []; total.value = result?.total ?? 0
      const requestedId = typeof route.query.template === 'string' ? route.query.template : undefined
      if (requestedMode !== 'text' && requestedId && !template.value) {
        const linked = await getTemplate(requestedId)
        if (current !== sequence) return
        if (linked.mode !== requestedMode || !linked.active) throw new Error('链接中的模板不可用于当前类型，请前往模板库重新选择')
        template.value = linked
      } else if (!template.value) template.value = available.value[0]
      else if (result?.items.some(t => t.id === template.value?.id)) template.value = result.items.find(t => t.id === template.value?.id)
    } catch (cause) {
      if (current === sequence) loadError.value = cause instanceof Error ? cause.message : '模板或 Skill 加载失败，请重试'
    } finally { if (current === sequence) loading.value = false }
  }
  watch(search, () => { page.value = 1 }, { flush: 'sync' })
  watch([search, page], load)
  watch([mode, () => route.query.template], () => {
    template.value = undefined; sources.value = []; name.value = ''; sku.value = ''; note.value = ''; error.value = ''
    search.value = ''; page.value = 1; void load()
  }, { immediate: true })
  function example() {
    if (!name.value) name.value = mode.value === 'text' ? '秋日上新 · 文案更新' : mode.value === 'product' ? '新品钢化膜 · 商品主图' : '秋日山川 · 手机屏幕套图'
    if (mode.value === 'text' && !note.value) note.value = '将「新品上市」改为「秋日上新」，其他内容保持不变'
    error.value = ''
  }
  async function submit() {
    if (blocked.value) return
    error.value = !sources.value.length ? '请先上传素材' : !name.value.trim() ? '请填写任务名称'
      : mode.value === 'text' && !note.value.trim() ? '请填写文字修改要求' : ''
    if (error.value) { ElMessage.warning(error.value); return }
    submitting.value = true
    const submittedFrom = route.fullPath
    try {
      const accepted = await createTask({ mode: mode.value, name: name.value.trim(), sku: sku.value.trim() || undefined,
        templateId: template.value?.id, templateVersion: template.value?.version, skillVersionId: skill.value?.id,
        sources: sources.value.map(p => ({ ...p })), note: note.value.trim() })
      // 工作区读取错误会卸载表单，但不应丢弃已经受理的任务标识。
      if (router.currentRoute.value.fullPath === submittedFrom) await router.push({ path: '/tasks/index', query: { task: accepted.taskId } })
    } catch (cause) {
      if (alive) { error.value = cause instanceof Error ? cause.message : '提交失败，请重试'; ElMessage.error(error.value) }
    } finally { if (alive) submitting.value = false }
  }
  return { available, template, sources, name, sku, note, search, page, pageSize, total, loading, loadError, error,
    submitting, uploadBlocked, skill, blocked, select, load, example, submit }
}
