import { computed, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getTemplate, listTemplates } from '@/api/templates'
import { listSkills } from '@/api/skills'
import type { Mode, SkillVersion, Template } from '@/types/hengxin'
import { getService } from '@/api/hengxin/client'
import { useUserStore } from '@/store/modules/user'
import { useTaskCreationSession } from './task-creation-session'

export function useCreateTask(mode: Ref<Mode>) {
  const router = useRouter(), route = useRoute()
  const user = useUserStore()
  const identity = () => user.isLogin && user.info.userId != null ? String(user.info.userId) : undefined
  const { submission, session, template, sources, name, sku, note } = useTaskCreationSession(identity, () => mode.value,
    () => route.query.template, async (input, key) => {
      const owner = identity(), service = await getService()
      if (!owner || owner !== identity()) throw new Error('登录身份已变化，请重新确认提交')
      return service.createTask(input, key)
    })
  const { accepted, uncertain } = submission
  const available = ref<Template[]>([])
  const skillVersions = ref<SkillVersion[]>([])
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
    if (!identity()) { loading.value = false; return }
    const requestedSession = session.value
    const isCurrent = () => current === sequence && requestedSession === session.value
    const requestedMode = mode.value
    loading.value = true; loadError.value = ''
    try {
      const [catalog, result] = await Promise.all([
        listSkills(requestedMode), requestedMode === 'text' ? undefined : listTemplates({
          page: page.value, pageSize, search: search.value.trim(), mode: requestedMode, activeOnly: true, sort: 'updated'
        })
      ])
      if (!isCurrent()) return
      skillVersions.value = catalog
      available.value = result?.items ?? []; total.value = result?.total ?? 0
      const requestedId = typeof route.query.template === 'string' ? route.query.template : undefined
      if (requestedMode !== 'text' && requestedId && !template.value) {
        const linked = await getTemplate(requestedId)
        if (!isCurrent()) return
        if (linked.mode !== requestedMode || !linked.active) throw new Error('链接中的模板不可用于当前类型，请前往模板库重新选择')
        template.value = linked
      } else if (!template.value) template.value = available.value[0]
      else if (result?.items.some(t => t.id === template.value?.id)) template.value = result.items.find(t => t.id === template.value?.id)
    } catch (cause) {
      if (isCurrent()) loadError.value = cause instanceof Error ? cause.message : '模板或 Skill 加载失败，请重试'
    } finally { if (isCurrent()) loading.value = false }
  }
  watch(search, () => { page.value = 1 }, { flush: 'sync' })
  watch([search, page], load)
  watch(session, () => {
    error.value = ''; skillVersions.value = []; available.value = []
    search.value = ''; page.value = 1; void load()
  }, { immediate: true })
  function example() {
    if (!name.value) name.value = mode.value === 'text' ? '秋日上新 · 文案更新' : mode.value === 'product' ? '新品钢化膜 · 商品主图' : '秋日山川 · 手机屏幕套图'
    if (mode.value === 'text' && !note.value) note.value = '将「新品上市」改为「秋日上新」，其他内容保持不变'
    error.value = ''
  }
  async function viewAccepted() {
    if (accepted.value) await router.push({ path: '/tasks/index', query: { task: accepted.value.taskId } })
  }
  function startNew() { submission.startNew(); error.value = '' }
  async function submit(resolvePrevious = false) {
    if (accepted.value) { await viewAccepted(); return }
    if (submitting.value || (!resolvePrevious && blocked.value)) return
    error.value = !sources.value.length ? '请先上传素材' : !name.value.trim() ? '请填写任务名称'
      : mode.value === 'text' && !note.value.trim() ? '请填写文字修改要求' : ''
    if (error.value && !resolvePrevious) { ElMessage.warning(error.value); return }
    submitting.value = true
    const submittedFrom = route.fullPath
    const submittedSession = session.value, submittedOwner = identity()
    try {
      const receipt = resolvePrevious ? await submission.resolvePrevious() : await submission.submit({ mode: mode.value, name: name.value.trim(), sku: sku.value.trim() || undefined,
        templateId: template.value?.id, templateVersion: template.value?.version, skillVersionId: skill.value?.id,
        sources: sources.value.map(p => ({ ...p })), note: note.value.trim() })
      // 工作区读取错误会卸载表单，但不应丢弃已经受理的任务标识。
      if (alive && identity() === submittedOwner && session.value === submittedSession && router.currentRoute.value.fullPath === submittedFrom) await router.push({ path: '/tasks/index', query: { task: receipt.taskId } })
    } catch (cause) {
      if (alive) { error.value = cause instanceof Error ? cause.message : '提交失败，请重试'; ElMessage.error(error.value) }
    } finally { if (alive) submitting.value = false }
  }
  return { available, template, sources, name, sku, note, search, page, pageSize, total, loading, loadError, error,
    submitting, uploadBlocked, skill, blocked, select, load, example, submit, accepted, uncertain, viewAccepted, startNew }
}
