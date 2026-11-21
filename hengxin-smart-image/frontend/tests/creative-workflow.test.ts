import test from 'node:test'
import assert from 'node:assert/strict'
import { compile, mount, find, flush, text, click, update } from './membership-test-harness'
import { IdentityError } from '../src/api/identity/request'
import { taskError, type TaskQuery } from '../src/api/overseas/tasks'

const component = compile('views/overseas/creative-tools/MyCreations.vue', {
  '@element-plus/icons-vue': { Search: {} }, '@/api/identity/request': { IdentityError },
  '@/api/overseas/tasks': { taskError }
})
const row = (id: string) => ({ id, productName: id, brand: '', platform: '', skus: [{ code: 'SKU-' + id }] })
test('我的创作以本人范围分页、搜索归首页、迟到响应不得覆盖新页面', async () => {
  const requests: TaskQuery[] = []
  let finish!: () => void
  const view = mount(component, {
    api: { async list(query: TaskQuery) {
      requests.push(query)
      if (query.page === 2) await new Promise<void>(resolve => { finish = resolve })
      return { items: [row(query.search || '第' + query.page + '页')], total: 22 }
    } }, refresh: 0
  })
  try {
    await flush()
    assert.deepEqual(requests[0], { search: '', scope: '', status: '', toolScope: 'mine', page: 1, pageSize: 20 })
    assert.ok(text(view.root).includes('第1页'))
    const pager = find(view.root, 'ElPagination')
    const changePage = pager.props['onUpdate:currentPage'] as (n: number) => void
    changePage(2)
    await flush()
    assert.equal(requests[1].page, 2)
    assert.ok(text(view.root).includes('正在加载'))
    update(find(view.root, 'ElInput'), '  灯具  ')
    await flush()
    assert.equal(requests[2].page, 1)
    assert.equal(requests[2].search, '灯具')
    finish()
    await flush()
    assert.ok(text(view.root).includes('SKU-灯具'))
    assert.ok(!text(view.root).includes('第2页'))
  } finally { view.close() }
})
test('我的创作加载故障可重试，空状态与权限拒绝独立展示', async () => {
  let attempts = 0
  const failures: unknown[] = []
  const view = mount(component, {
    api: { async list() {
      if (++attempts === 1) throw new Error('服务中断')
      if (attempts === 2) throw new IdentityError(403, '暂无权限')
      return { items: [], total: 0 }
    } }, refresh: 0, onFailure: (reason: unknown) => failures.push(reason)
  })
  try {
    await flush()
    assert.equal(find(view.root, 'ElAlert').props.title, '服务中断')
    click(view.root, '重试'); await flush()
    assert.equal(find(view.root, 'ElAlert').props.title, '暂无权限')
    assert.equal(failures.length, 1)
    click(view.root, '重试'); await flush()
    assert.ok(text(view.root).includes('暂无创作'))
  } finally { view.close() }
})
