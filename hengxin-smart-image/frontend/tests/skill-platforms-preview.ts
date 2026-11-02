// Isolated, in-memory API fixtures for manual cua_repl checks of the real Vue pages.
// Run: node --import tsx tests/skill-platforms-preview.ts
import { createServer, loadConfigFromFile } from 'vite'
import { createServer as createNetServer } from 'node:net'
await new Promise<void>((resolve, reject) => { const probe = createNetServer(); probe.once('error', reject); probe.listen(3038, '127.0.0.1', () => probe.close(() => resolve())) })
import { mkdir, readFile, writeFile } from 'node:fs/promises'
const controlFile = '../../output/skill-platforms/preview-control.json'
const skills = [
  { id: 's', name: 'amazon-new-product-image-set', displayName: 'OUTON 亚马逊新品整套主图生成', description: '根据真实产品资料与参考图片生成完整主图。保留商品结构、尺寸及品牌信息，完整描述可换行阅读。', enabled: true, version: 1, platforms: ['Amazon'] },
  { id: 'aplus', name: 'amazon-new-product-aplus', displayName: '亚马逊新品A+整套图片生成', description: '根据商品资料与品牌信息制作完整 A+ 页面图片，保留商品结构与真实卖点。', enabled: true, version: 1, platforms: ['Amazon'] },
  { id: 'disabled', name: 'other', displayName: '已安装的其他 Skill', description: '此项仍保留在管理目录，关闭后工作台不能选择。', enabled: false, version: 1, platforms: ['Wayfair'] }
]
const caps = ['task.read', 'task.design', 'skills.manage', 'settings.manage']
const task = { id: 't', name: 'Skill 开关隔离验收', productName: '灯具', brand: 'HX', platform: 'Amazon', market: '美国', remarks: '', skus: [{ code: 'A' }], workflow: 'studio', status: 'studio', version: 1, createdAt: '2026-10-22', updatedAt: '2026-10-22', createdBy: { id: 'u', name: '运营' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities: caps, events: [] }
const conversations = ['skill-preview', 'second'].map(id => ({ id, name: id === 'second' ? '第二会话' : '平台验收会话', version: 1, createdAt: '2026-11-02T00:00:00Z', updatedAt: '2026-11-02T00:00:00Z', activeTurnId: null, status: 'empty', turnCount: 0 }))
const recoverable = ['Result.ZIP', '设计说明.pdf', 'chair.png'].map((name, i) => ({ id: String(i), name, path: i === 2 ? 'work/Images/chair.png' : 'work/exports/' + name, source: 'work', sizeBytes: 1024, version: 'v1' }))
const state = (conversationId = 'skill-preview') => ({ taskId: 't', taskVersion: 1, archiveId: null, completed: false, reopened: false, conversationId, conversations, activeConversationCount: 0, maxConversations: 10, turns: [], materials: [], skills: skills.filter(s => s.enabled && s.platforms.includes(task.platform)).map(({ enabled, version, ...s }) => s), activeTurnId: null })
await mkdir('../../output/skill-platforms', { recursive: true })
await writeFile(controlFile, JSON.stringify({ owner: true, mode: '', platform: 'Amazon', readOnly: false }))
const config = (await loadConfigFromFile({ command: 'serve', mode: 'development' }, 'vite.overseas.config.ts'))!.config
const server = await createServer({ ...config, configFile: false, mode: 'development', server: { host: '127.0.0.1', port: 3038, strictPort: true }, plugins: [{ name: 'isolated-skill-fixtures', configureServer(vite) {
  vite.middlewares.use(async (req, res, next) => {
    const path = new URL(req.url || '/', 'http://127.0.0.1:3038').pathname
    if (!path.startsWith('/api/')) return next()
    try {
      const control = JSON.parse(await readFile(controlFile, 'utf8'))
      task.platform = control.platform || 'Amazon'
      if (typeof control.skillEnabled === 'boolean') skills[0].enabled = control.skillEnabled
      let body: unknown = {}, status = 200
      if (path.endsWith('/config')) body = { configured: true, corpId: 'isolated', clientId: 'isolated' }
      else if (path === '/api/identity/v1/me') body = { name: '隔离验收账号', sessionId: 'skill-preview' }
      else if (path.endsWith('/tickets')) body = { ticket: 'isolated' }
      else if (path === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
      else if (path.includes('/auth/')) { body = { id: 'd', name: '隔离验收账号', identitySessionId: 'skill-preview', status: 'active', roles: ['super_admin'], capabilities: caps }; if (path.endsWith('/access')) body = { state: 'allowed', member: body } }
      else if (path.endsWith('/skills/platforms') && req.method === 'PATCH') {
        let raw = ''; for await (const chunk of req) raw += chunk
        const input = JSON.parse(raw)
        if (control.readOnly) status = 403
        else if (control.mode === 'conflict') { skills[0].version++; status = 409 }
        else if (control.mode === 'failure') status = 503
        else if (input.items.some((item: { id: string; version: number }) => skills.find(s => s.id === item.id)?.version !== item.version)) status = 409
        else for (const item of input.items) { const skill = skills.find(s => s.id === item.id)!; skill.platforms = item.platforms; skill.version++ }
        body = status === 200 ? { items: skills, canToggle: control.owner, canManagePlatforms: !control.readOnly } : { detail: '平台保存隔离故障场景' }
      }
      else if (path.endsWith('/recoverable-files')) body = { items: recoverable, busy: false }
      else if (path.endsWith('/recover-files')) {
        let raw = ''; for await (const chunk of req) raw += chunk
        const input = JSON.parse(raw)
        body = { saved: input.files.map((file: { id: string }) => ({ id: 'saved-' + file.id, kind: 'file' })), errors: [] }
        if (control.mode === 'failure') { status = 503; body = { detail: '取回保存失败' } }
      }
      else if (path.endsWith('/availability') && req.method === 'PATCH') {
        let raw = ''; for await (const chunk of req) raw += chunk
        const input = JSON.parse(raw), item = skills.find(s => s.id === decodeURIComponent(path.split('/').at(-2)!))
        if (!control.owner) { status = 403 }
        else if (control.mode === 'conflict') { if (item) item.version++; status = 409 }
        else if (control.mode === 'failure') status = 503
        else if (!item || item.version !== input.version) status = 409
        else { item.enabled = input.enabled; item.version++ }
        body = status === 200 ? { items: skills, canToggle: control.owner, canManagePlatforms: !control.readOnly } : { detail: '隔离故障场景' }
      } else if (path.endsWith('/management/skills')) { if (control.mode === 'load-failure') status = 503; body = { items: skills, canToggle: control.owner, canManagePlatforms: !control.readOnly } }
      else if (path.endsWith('/studio/transcript')) body = { items: [], cursor: 0, hasMore: false }
      else if (path.endsWith('/studio')) body = state(new URL(req.url || '/', 'http://local').searchParams.get('conversationId') || undefined)
      else if (path.endsWith('/tasks/t')) body = task
      else if (path.endsWith('/materials')) body = []
      else if (path.endsWith('/jobs')) body = { items: [] }
      else if (path.endsWith('/execution-events')) body = { items: [], cursor: 0 }
      else if (path.endsWith('/plans') || path.endsWith('/pictures')) body = { items: [], taskVersion: 1 }
      else { status = 404; body = { detail: 'Unmocked endpoint' }; console.error('UNMOCKED', path) }
      res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(body))
    } catch (error) { console.error(error); res.writeHead(500); res.end('{}') }
  })
} }, ...(config.plugins || [])] })
await server.listen(); console.log('Isolated Skill UI: http://127.0.0.1:3038/#/overseas/admin/skills')
