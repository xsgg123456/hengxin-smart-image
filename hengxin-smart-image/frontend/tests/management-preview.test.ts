import assert from 'node:assert/strict'
import test from 'node:test'
import { managementComponent } from '../src/router/management-preview'
import { buildUsage, usageEvents, previewTasks } from '../src/views/hengxin/admin/preview/usage-data'

test('management preview requires both explicit mock mode and opt-in query', () => {
  for (const mode of ['production', 'development', 'demo', undefined]) {
    assert.equal(managementComponent('usage', mode, '?managementPreview=api'), '/hengxin/admin/usage')
  }
  assert.equal(managementComponent('usage', 'mock', ''), '/hengxin/admin/usage')
  assert.equal(managementComponent('usage', 'mock', '?managementPreview=api'), '/hengxin/admin/preview/UsagePreview')
  assert.equal(managementComponent('monitor', 'mock', '?managementPreview=api'), '/hengxin/admin/preview/MonitorPreview')
  assert.equal(managementComponent('settings', 'mock', '?managementPreview=api'), '/hengxin/admin/preview/SettingsPreview')
  assert.equal(managementComponent('users', 'mock', '?managementPreview=api'), '/hengxin/admin/users')
  assert.equal(managementComponent('skills', 'mock', '?managementPreview=api'), '/hengxin/admin/skills')
})

test('preview events preserve counts and separate CLI rounds from API attempts', () => {
  assert.equal(previewTasks.length, 52)
  assert.equal(previewTasks.reduce((n,t) => n+t.currentImages, 0), 376)
  for (const event of usageEvents) {
    for (const value of Object.values(event)) if (typeof value === 'number') assert.ok(value >= 0)
    assert.equal(event.requests, event.requestSuccess + event.requestFailed + event.requestUnknown)
    if (event.kind === 'cli') { assert.equal(event.cliRounds, 1); assert.equal(event.requests, 0) }
    if (!event.versions) assert.equal(event.publishedDate, '')
    if (!event.delivered) assert.equal(event.outputDate, '')
    if (event.kind !== 'cli') { assert.equal(event.adopted, 0); assert.equal(event.candidates, 0) }
    else { assert.equal(event.versions, event.adopted); assert.equal(event.candidates, event.delivered); assert.equal(event.publishedDate, event.adoptedDate) }
    if (!event.adopted) assert.equal(event.adoptedDate, '')
  }
})

test('daily summaries reconcile and event dates remain independent', () => {
  for (const filter of [{}, {user:'设计师甲'}, {from:'2026-10-03',to:'2026-10-05'}, {kind:'cli' as const,user:'设计师甲'}]) {
    const report = buildUsage(filter)
    assert.equal(report.rows.reduce((n,r) => n+r.created,0),report.created)
    assert.equal(report.rows.reduce((n,r) => n+r.summary.requests,0),report.summary.requests)
    assert.equal(report.rows.reduce((n,r) => n+r.summary.cliRounds,0),report.summary.cliRounds)
    assert.equal(report.rows.reduce((n,r) => n+r.versions,0),report.versions)
    assert.equal(report.rows.reduce((n,r) => n+r.adopted,0),report.adopted)
    assert.equal(report.rows.reduce((n,r) => n+r.candidates,0),report.candidates)
    if ('user' in filter) assert.ok(report.rows.every(r => r.user === filter.user))
  }
  const first = buildUsage({from:'2026-10-01',to:'2026-10-01'})
  assert.ok(first.created > 0 && first.summary.requests > 0)
  assert.equal(first.versions,0)
  assert.equal(first.adopted,0)
  assert.ok(buildUsage({from:'2026-10-02',to:'2026-10-02'}).versions > 0)
  assert.equal(buildUsage({from:'2026-10-03',to:'2026-10-03',kind:'cli'}).adopted,0)
  assert.ok(buildUsage({from:'2026-10-03',to:'2026-10-03',kind:'cli'}).candidates > 0)
  const adoptionDay = usageEvents.find(e => e.adopted > 0)!.adoptedDate
  assert.ok(buildUsage({from:adoptionDay,to:adoptionDay,kind:'cli'}).adopted > 0)
  const empty = buildUsage({from:'2027-01-01',to:'2027-01-02'})
  assert.equal(empty.rows.length,0)
  assert.equal(empty.summary.requests,0)
  assert.equal(empty.inventory.length,52)
})

test('CLI unadopted candidates do not become formal versions', () => {
  const candidate = usageEvents.find(e => e.kind === 'cli' && e.candidates > 0 && e.adopted === 0)!
  assert.ok(candidate)
  assert.equal(candidate.versions, 0)
  assert.equal(candidate.publishedDate, '')
  assert.notEqual(candidate.outputDate, '')
  assert.equal(buildUsage({kind:'initial'}).adopted, 0)
})
