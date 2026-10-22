import { computed, ref, watch } from 'vue'
import type { ApiTaskSummary, ApiTaskState } from '@/types/api-image-edits'
export const people = [{ id: 'me', name: '张三（我）' }, { id: 'gan', name: '甘双荣' }, { id: 'chen', name: '陈润达' }, { id: 'lin', name: '林晓' }]
export interface PreviewTask extends ApiTaskSummary { creatorId: string }
const names = ['丝印主图', '红米 K90 Pro Max 详情壁纸修改', '秋日壁纸 · 手机主图', '丝印详情图', '新品配色 · 第一批', '手机屏幕替换', '蓝色款详情页', '京东主图 · 第二版']
export function makeTasks(): PreviewTask[] {
  return Array.from({ length: 105 }, (_, i) => {
    const person = people[i % people.length], total = [5, 7, 4, 3, 6][i % 5]
    const status: ApiTaskState = i === 0 || i === 1 ? 'running' : i === 4 ? 'queued' : i % 17 === 0 ? 'failed' : i % 9 === 0 ? 'partial_failed' : 'succeeded'
    const success = status === 'succeeded' ? total : status === 'failed' || status === 'queued' ? 0 : total - 2
    const failed = status === 'failed' ? total : status === 'partial_failed' ? 2 : 0
    const day = new Date(Date.UTC(2026, 9, 22 - Math.floor(i / 3))).toISOString().slice(0, 10)
    const picture = (i + Math.floor(i / 4)) % 4 + 1
    return { id: `a8e26022-${String(i + 1).padStart(4, '0')}-417a-94a7-04605ddd03ae`, name: `${names[(i + Math.floor(i / 4)) % names.length]}${i >= 8 ? ` · ${Math.floor(i / 8) + 1}` : ''}`, creatorId: person.id, operator: person.id === 'me' ? '张三' : person.name,
      created: `${day}T${String(14 - i % 3).padStart(2, '0')}:02:50+08:00`, status,
      cover: { fileId: `sample-${picture}`, name: `手机主图-${picture}.jpg`, url: `/demo-images/sample-${picture}.jpg` },
      counts: { total, success, failed, uncertain: 0 }, batch: { current: 1, total: 1, running: status === 'running' ? 2 : 0 }, canDelete: !['queued', 'running'].includes(status), deletionState: 'idle' }
  })
}
export function usePreviewRecords(initialScope: 'mine' | 'all' = 'mine') {
  const records = ref(makeTasks()), scope = ref(initialScope), creator = ref(''), filter = ref<ApiTaskState | ''>(''), search = ref(''), period = ref('all'), dates = ref<[string, string] | null>(null)
  const page = ref(1), pageSize = ref(20), loading = ref(false), error = ref(''), selected = ref<PreviewTask>(), scene = ref('normal')
  const matches = computed(() => records.value.filter(task => {
    if (scene.value === 'empty') return false
    if (scope.value === 'mine' && task.creatorId !== 'me') return false
    if (scope.value === 'all' && creator.value && task.creatorId !== creator.value) return false
    if (filter.value && task.status !== filter.value) return false
    if (!`${task.name} ${task.id}`.toLowerCase().includes(search.value.trim().toLowerCase())) return false
    const date = task.created.slice(0, 10)
    if (period.value === 'custom') return !dates.value || (date >= dates.value[0] && date <= dates.value[1])
    const start = period.value === 'today' ? '2026-10-22' : period.value === 'week' ? '2026-10-16' : period.value === 'month' ? '2026-09-23' : ''
    return !start || (date >= start && date <= '2026-10-22')
  }))
  const total = computed(() => matches.value.length)
  const tasks = computed(() => matches.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
  const stats = computed(() => [
    { label: '当前筛选任务', count: total.value, unit: '套' },
    { label: '排队 / 处理中', count: matches.value.filter(t => ['queued', 'running', 'uncertain'].includes(t.status)).length, unit: '套' },
    { label: '成功图片', count: matches.value.reduce((n, t) => n + t.counts.success, 0), unit: '张' },
    { label: '未完成图片', count: matches.value.reduce((n, t) => n + t.counts.failed, 0), unit: '张' },
  ])
  const scopeText = computed(() => scope.value === 'mine' ? '我的任务' : creator.value ? `${people.find(p => p.id === creator.value)?.name}的任务` : '全部人员的任务')
  const hasFilters = computed(() => !!(creator.value || filter.value || search.value || period.value !== 'all'))
  watch([scope, creator, filter, search, period, dates, pageSize, scene], () => { page.value = 1 }, { flush: 'sync' })
  watch(scope, () => { creator.value = '' })
  watch(total, count => { page.value = Math.min(page.value, Math.max(1, Math.ceil(count / pageSize.value))) })
  async function refresh() { loading.value = true; error.value = ''; await new Promise(resolve => setTimeout(resolve, 400)); loading.value = false; if (scene.value === 'error') error.value = '记录刷新失败，已保留当前筛选和上次数据。请重试。' }
  watch(scene, () => { error.value = ''; if (scene.value === 'error') void refresh() })
  function reset() { creator.value = ''; filter.value = ''; search.value = ''; period.value = 'all'; dates.value = null; page.value = 1; scene.value = 'normal'; error.value = '' }
  return { records, scope, creator, filter, search, period, dates, page, pageSize, loading, error, selected, scene, matches, total, tasks, stats, scopeText, hasFilters, refresh, reset }
}
