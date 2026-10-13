// Execute the production entry's real preload logic, intercepting only module execution.
import { readFileSync, existsSync } from 'node:fs'
import { resolve, join } from 'node:path'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const dist = resolve(process.argv[2] || 'dist')
const html = readFileSync(join(dist, 'index.html'), 'utf8')
const entry = html.match(/<script type="module"[^>]*src="([^"]+)"/)[1]
const original = readFileSync(join(dist, entry), 'utf8')
const code = original.replace(/\bimport\(("[^"]+")\)/g, 'capture($1)').replace(/export\{[^}]+\};?\s*$/, '')
for (const hash of ['', '#/', '#/auth/business', '#/overseas', '#/overseas/admin/users', '#/api-image-edits/create']) {
  const links = [], imports = []
  const document = {
    createElement: () => ({ relList: { supports: () => true }, setAttribute() {}, addEventListener(event, callback) { if (event === 'load') queueMicrotask(callback) } }),
    querySelector: () => null,
    getElementsByTagName: () => [],
    head: { appendChild: link => links.push(link) },
  }
  vm.runInNewContext(code, { document, window: { location: { hash }, dispatchEvent() {} }, capture: async name => { imports.push(name) }, Event })
  await new Promise(resolve => setImmediate(resolve))
  const css = links.filter(link => link.rel === 'stylesheet').map(link => link.href)
  const domestic = hash === '#/api-image-edits/create'
  assert.equal(imports.length, 1)
  assert.match(imports[0], domestic ? /domestic-main/ : /identity-main/)
  for (const file of css) assert.ok(existsSync(join(dist, file)), file)
  for (const name of domestic ? ['dingtalk-login', 'domestic-main'] : ['IdentityPortal', 'BusinessEntry', 'OverseasShell', 'OverseasTasksPage']) {
    assert.ok(css.some(file => file.includes('/' + name + '-')), `${hash || '/'} missing ${name} CSS`)
  }
  console.log('PASS', hash || '/', css.length, 'CSS dependencies')
}
