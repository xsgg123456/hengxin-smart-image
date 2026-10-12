// Run only against infra/identity-test/run.py --phase25 --serve disposable topology.
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3016'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const scripts = ['unified-identity', 'overseas-members', 'overseas-tasks', 'overseas-materials',
  'overseas-plans', 'overseas-pictures', 'overseas-management']
for (const name of scripts) {
  const script = fileURLToPath(new URL(`./${name}-real.browser.mjs`, import.meta.url))
  const result = spawnSync(process.execPath, [script], {
    env: { ...process.env, IDENTITY_UI_URL: base }, stdio: 'inherit', timeout: 300000
  })
  if (result.error) throw result.error
  assert.equal(result.status, 0, `${name} real browser failed`)
  console.log(`PASS Phase25 browser group: ${name}`)
}
console.log('PASS Phase25 all seven real API browser groups')
