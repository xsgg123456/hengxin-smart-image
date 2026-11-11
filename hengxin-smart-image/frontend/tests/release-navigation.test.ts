import { test } from 'node:test'
import assert from 'node:assert/strict'
import { entryDestination, releaseDestination } from '../src/release/navigation'
import { logoutDestination } from '../src/api/hengxin/logout'
import { parseReleaseScope } from '../release-scope.config'

test('旧根链接按hash分组，原始查询和fragment完整保留且只跳一次', () => {
  for (const [hash, target] of [['#/overseas/tasks/abc?tab=files', 'overseas'], ['#/api-image-edits/records?id=1', 'domestic'], ['#/auth/callback?auth=provider_error&state=x', 'shared']] as const) {
    const destination = entryDestination('shared', { pathname: '/', search: '?workspace=identity&x=%2F', hash })
    assert.equal(destination, `/${target}/?workspace=identity&x=%2F${hash}`)
    const next = new URL(destination!, 'http://localhost')
    assert.equal(entryDestination(target, next), undefined)
  }
})

test('裸分组入口选择本域默认页，跨组hash进入所属入口', () => {
  assert.equal(entryDestination('shared', new URL('http://localhost/')), '/shared/#/auth/business')
  assert.equal(entryDestination('domestic', new URL('http://localhost/domestic/')), '/domestic/#/api-image-edits/create')
  assert.equal(entryDestination('overseas', new URL('http://localhost/overseas/')), '/overseas/#/overseas/tasks')
  assert.equal(entryDestination('domestic', new URL('http://localhost/domestic/#/auth/login?redirect=%2Fx')), '/shared/#/auth/login?redirect=%2Fx')
  assert.equal(entryDestination('shared', new URL('http://localhost/shared/#/overseas/tasks')), '/overseas/#/overseas/tasks')
})

test('退出分组业务回共享登录，未指定scope的通用预览保持旧地址', () => {
  for (const scope of ['domestic', 'overseas', 'shared']) {
    const destination = new URL(logoutDestination(`http://localhost/${scope}/?role=operator#/api-image-edits/records`))
    assert.equal(destination.pathname, '/shared/')
    assert.equal(destination.search, '')
    assert.ok(destination.hash.startsWith('#/auth/login?redirect='))
    assert.equal(entryDestination('shared', destination), undefined)
  }
  assert.equal(releaseDestination('shared', '/auth/business', '?workspace=identity'), '/?workspace=identity#/auth/business')
})

test('构建作用域拒绝拼写错误，防止误发整站', () => {
  assert.equal(parseReleaseScope('domestic'), 'domestic')
  assert.equal(parseReleaseScope('overseas'), 'overseas')
  assert.equal(parseReleaseScope('shared'), 'shared')
  assert.equal(parseReleaseScope(''), undefined)
  assert.throws(() => parseReleaseScope('all'), /Invalid VITE_RELEASE_SCOPE/)
})
