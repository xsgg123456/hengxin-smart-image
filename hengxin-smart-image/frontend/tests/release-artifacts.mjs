import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { resolve, join } from 'node:path'

for (const scope of ['domestic', 'overseas', 'shared']) {
  const root = resolve(process.env.RELEASE_BUILD_ROOT || '.', `dist-release-${scope}`)
  const manifest = JSON.parse(readFileSync(join(root, 'release-scope.json'), 'utf8'))
  assert.equal(manifest.scope, scope)
  assert.equal(manifest.base, `/${scope}/`)
  const overseas = manifest.modules.some(id => id.startsWith('src/views/overseas/'))
  const domestic = manifest.modules.some(id => id.startsWith('src/views/hengxin/') && !id.startsWith('src/views/hengxin/components/') && id.endsWith('.vue'))
  assert.equal(overseas, scope === 'overseas', `${scope} overseas implementation boundary`)
  assert.equal(domestic, scope === 'domestic', `${scope} domestic implementation boundary`)
  const html = readFileSync(join(root, 'index.html'), 'utf8')
  const assets = [...html.matchAll(/(?:src|href)="([^"#]+)"/g)].map(match => match[1])
  for (const asset of assets) {
    assert.ok(asset.startsWith(`/${scope}/`), asset)
    assert.ok(existsSync(join(root, asset.slice(scope.length + 2))), asset)
  }
  assert.ok(assets.some(asset => asset.endsWith('.js')))
  console.log(`PASS ${scope}: ${manifest.modules.length} source modules, isolated graph and prefixed assets`)
}
