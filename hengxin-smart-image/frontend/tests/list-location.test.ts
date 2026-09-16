import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { useListLocation } from '../src/views/hengxin/list-location'

async function setup(url: string) {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/tasks/index', component: {} }, { path: '/archive/index', component: {} },
    { path: '/image-processing/product', component: {} }
  ] })
  await router.push(url)
  return router
}
function travel(router: Router, amount: number) {
  return new Promise<void>(resolve => {
    const remove = router.afterEach(() => { remove(); resolve() })
    router.go(amount)
  })
}
function changed(router: Router, change: () => void) {
  return new Promise<void>(resolve => {
    const remove = router.afterEach(() => { remove(); resolve() })
    change()
  })
}
test('任务 A 关闭后查看 B，刷新重建与前进后退均保持对象一致', async () => {
  const router = await setup('/tasks/index?task=A&search=商品&page=3')
  const location = useListLocation(router, '/tasks/index', 'task')
  assert.equal(location.detailId.value, 'A')
  await location.closeDetail()
  assert.equal(location.detailOpen.value, false)
  assert.equal(router.currentRoute.value.query.task, undefined)
  await location.openDetail('B')
  const refreshed = await setup(router.currentRoute.value.fullPath)
  assert.equal(useListLocation(refreshed, '/tasks/index', 'task').detailId.value, 'B')
  await travel(router, -1)
  assert.equal(location.detailOpen.value, false)
  assert.equal(location.page.value, 3)
  await travel(router, -1)
  assert.equal(location.detailId.value, 'A')
  await travel(router, 1)
  await travel(router, 1)
  assert.equal(location.detailId.value, 'B')
  assert.equal(location.search.value, '商品')
})
test('旧 taskId 可进入，新打开和关闭会消除旧别名，不能复活旧对象', async () => {
  const router = await setup('/tasks/index?taskId=A')
  const location = useListLocation(router, '/tasks/index', 'task')
  assert.equal(location.detailId.value, 'A')
  await location.openDetail('B')
  assert.deepEqual(router.currentRoute.value.query, { task: 'B' })
  await location.closeDetail()
  assert.equal(location.detailId.value, '')
})
test('跨页面返回保留筛选和分页，筛选变化原子重置分页并保留详情', async () => {
  const router = await setup('/tasks/index?mode=product&state=失败&search=SKU&page=4&task=A')
  const location = useListLocation(router, '/tasks/index', 'task')
  await router.push('/archive/index')
  await travel(router, -1)
  assert.equal(location.mode.value, 'product')
  assert.equal(location.state.value, '失败')
  assert.equal(location.page.value, 4)
  await changed(router, () => { location.search.value = '新商品' })
  assert.equal(location.page.value, 1)
  assert.equal(location.detailId.value, 'A')
  await location.clearFilters()
  assert.equal(location.mode.value, 'all')
  assert.equal(location.state.value, 'all')
  assert.deepEqual(router.currentRoute.value.query, { task: 'A' })
})
test('成品深链支持关闭、刷新恢复，并拒绝重复值及非法页码', async () => {
  const router = await setup('/archive/index?archive=R1&mode=product&page=2')
  const location = useListLocation(router, '/archive/index', 'archive')
  assert.equal(location.detailId.value, 'R1')
  await location.closeDetail()
  await location.openDetail('R2')
  const refreshed = await setup(router.currentRoute.value.fullPath)
  assert.equal(useListLocation(refreshed, '/archive/index', 'archive').detailId.value, 'R2')
  await router.push('/archive/index?archive=A&archive=B&mode=invalid&page=-2')
  assert.equal(location.detailId.value, '')
  assert.equal(location.mode.value, 'all')
  assert.equal(location.page.value, 1)
})
