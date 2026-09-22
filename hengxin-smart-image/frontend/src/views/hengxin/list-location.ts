import { computed } from 'vue'
import type { LocationQuery, LocationQueryRaw, Router } from 'vue-router'
import type { Mode, TaskQuery } from '../../types/hengxin'

const modes: readonly string[] = ['wallpaper', 'product', 'text']
const states: readonly string[] = ['排队中', '执行中', '待查看', '部分失败', '失败']
function scalar(value: LocationQuery[string]) { return typeof value === 'string' ? value : '' }

/** 列表和详情共用地址状态；筛选替换当前记录，打开/关闭详情保留浏览历史。 */
export function useListLocation(router: Router, path: string, detailKey: 'task' | 'archive') {
  const query = computed(() => router.currentRoute.value.path === path ? router.currentRoute.value.query : {})
  function update(patch: LocationQueryRaw, replace = true) {
    if (router.currentRoute.value.path !== path) return Promise.resolve()
    return router[replace ? 'replace' : 'push']({ path, query: { ...query.value, ...patch } })
  }
  const mode = computed<Mode | 'all'>({
    get: () => modes.includes(scalar(query.value.mode)) ? scalar(query.value.mode) as Mode : 'all',
    set: value => { void update({ mode: value === 'all' ? undefined : value, page: undefined }) }
  })
  const search = computed({
    get: () => scalar(query.value.search),
    set: value => { void update({ search: value || undefined, page: undefined }) }
  })
  const scope = computed<'all' | 'mine'>({
    get: () => query.value.scope === 'mine' ? 'mine' : 'all',
    set: value => { void update({ scope: value === 'mine' ? 'mine' : undefined, page: undefined }) }
  })
  const state = computed<TaskQuery['state'] | 'all'>({
    get: () => states.includes(scalar(query.value.state)) ? scalar(query.value.state) as TaskQuery['state'] : 'all',
    set: value => { void update({ state: value === 'all' ? undefined : value, page: undefined }) }
  })
  const page = computed({
    get: () => {
      const value = Number(scalar(query.value.page))
      return Number.isSafeInteger(value) && value > 0 ? value : 1
    },
    set: value => { void update({ page: value > 1 ? String(value) : undefined }) }
  })
  const detailId = computed(() => scalar(query.value[detailKey]) || (detailKey === 'task' ? scalar(query.value.taskId) : ''))
  function openDetail(id: string) { return update({ [detailKey]: id, ...(detailKey === 'task' ? { taskId: undefined } : {}) }, false) }
  function closeDetail() { return update({ [detailKey]: undefined, ...(detailKey === 'task' ? { taskId: undefined } : {}) }, false) }
  const detailOpen = computed({ get: () => !!detailId.value, set: value => { if (!value && detailId.value) void closeDetail() } })
  function clearFilters() { return update({ mode: undefined, search: undefined, state: undefined, scope: undefined, page: undefined }) }
  return { mode, search, state, scope, page, detailId, detailOpen, openDetail, closeDetail, clearFilters }
}
