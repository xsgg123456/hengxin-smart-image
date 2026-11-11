import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { getActivity } from '@/api/activity'
import type { ActivityReport, ActivityRecord, GenerationKind } from '@/types/activity'
export function useActivity() {
  const view = ref<'people'|'jobs'>('people'), person = ref(''), dates = ref<string[] | null>(null), kind = ref<GenerationKind | ''>(''), status = ref(''), keyword = ref(''), page = ref(1), currentOnly = ref(false)
  const report = ref<ActivityReport>(), loading = ref(false), error = ref('')
  const users = ref<ActivityReport['users']>([])
  const selected = ref<ActivityRecord | null>(null)
  let active = true, generation = 0, timer: ReturnType<typeof setTimeout> | undefined
  const scope = computed(() => `${person.value === '__unknown' ? '未记录操作者' : users.value.find(p => p.id === person.value)?.name || (person.value ? '已选人员' : '国内全员')} · ${dates.value?.length ? dates.value.join(' 至 ') : '全部时间'}`)
  async function load() {
    const epoch = ++generation
    loading.value = true; error.value = ''; report.value = undefined; selected.value = null
    try {
      const result = await getActivity({ view:view.value, userId:person.value && person.value !== '__unknown' ? person.value : undefined, unassigned:person.value === '__unknown' || undefined,
        from:dates.value?.[0], to:dates.value?.[1], generationType:kind.value || undefined, status:view.value === 'jobs' ? status.value || undefined : undefined,
        keyword:view.value === 'jobs' ? keyword.value.trim() || undefined : undefined, currentOnly:view.value === 'jobs' && currentOnly.value, page:page.value, pageSize:20 })
      if (active && epoch === generation) { report.value = result; users.value = result.users }
    } catch (reason) { if (active && epoch === generation) { users.value = []; error.value = reason instanceof Error ? reason.message : '数据加载失败，请重试' } }
    finally { if (active && epoch === generation) loading.value = false }
  }
  function reset() { person.value=''; dates.value=null; kind.value=''; status.value=''; keyword.value=''; currentOnly.value=false; page.value=1 }
  function showPerson(id: string | null) { person.value = id || '__unknown'; status.value=''; keyword.value=''; currentOnly.value=false; view.value='jobs'; page.value=1 }
  function showStatus(key: string) { reset(); status.value=key; currentOnly.value=true; view.value='jobs' }
  function refresh() { clearTimeout(timer); void load() }
  watch([person, dates, kind, status, view, currentOnly, keyword], () => { page.value = 1 }, {flush:'sync'})
  watch([person, dates, kind, status, view, currentOnly, keyword, page], (values, before) => {
    ++generation; report.value = undefined; loading.value = true; selected.value = null
    clearTimeout(timer); timer = setTimeout(() => void load(), values[6] !== before[6] ? 250 : 0)
  }, {flush:'post'})
  onMounted(refresh)
  onUnmounted(() => { active=false; ++generation; clearTimeout(timer) })
  return { users,view,person,dates,kind,status,keyword,page,currentOnly,report,loading,error,selected,scope,load,reset,showPerson,showStatus,refresh }
}
