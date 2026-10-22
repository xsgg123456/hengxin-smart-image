// Isolated, in-memory API fixtures for manual cua_repl checks of the real Vue pages.
// Run: node --import tsx tests/skill-availability-preview.ts
import { createServer, loadConfigFromFile } from 'vite'
import { readFile, writeFile } from 'node:fs/promises'
const controlFile = '../../output/skill-availability/preview-control.json'
const skills = [
  { id: 's', name: 'amazon-new-product-image-set', displayName: 'OUTON 亚马逊新品整套主图生成', description: '根据真实产品资料与参考图片生成完整主图。保留商品结构、尺寸及品牌信息，完整描述可换行阅读。', enabled: true, version: 1 },
  { id: 'aplus', name: 'amazon-new-product-aplus', displayName: '亚马逊新品A+整套图片生成', description: '根据商品资料与品牌信息制作完整 A+ 页面图片，保留商品结构与真实卖点。', enabled: true, version: 1 },
  { id: 'disabled', name: 'other', displayName: '已安装的其他 Skill', description: '此项仍保留在管理目录，关闭后工作台不能选择。', enabled: false, version: 1 }
]
const caps = ['task.read', 'task.design', 'skills.manage', 'settings.manage']
const task = { id: 't', name: 'Skill 开关隔离验收', productName: '灯具', brand: 'HX', platform: 'Amazon', market: '美国', remarks: '', skus: [{ code: 'A' }], workflow: 'studio', status: 'studio', version: 1, createdAt: '2026-10-22', updatedAt: '2026-10-22', createdBy: { id: 'u', name: '运营' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities: caps, events: [] }
const state = () => ({ taskId: 't', taskVersion: 1, archiveId: null, completed: false, reopened: false, conversationId: 'skill-preview', turns: [], materials: [], skills: skills.filter(s => s.enabled).map(({ enabled, version, ...s }) => s), activeTurnId: null })
await writeFile(controlFile, JSON.stringify({ owner: true, mode: '' }))
const config = (await loadConfigFromFile({ command: 'serve', mode: 'development' }, 'vite.overseas.config.ts'))!.config
const server = await createServer({ ...config, configFile: false, mode: 'development', server: { host: '127.0.0.1', port: 3037, strictPort: true }, plugins: [{ name: 'isolated-skill-fixtures', configureServer(vite) {
  vite.middlewares.use(async (req, res, next) => {
    const path = new URL(req.url || '/', 'http://127.0.0.1:3037').pathname
    if (!path.startsWith('/api/')) return next()
    try {
      const control = JSON.parse(await readFile(controlFile, 'utf8'))
      if (typeof control.skillEnabled === 'boolean') skills[0].enabled = control.skillEnabled
      let body: unknown = {}, status = 200
      if (path.endsWith('/config')) body = { configured: true, corpId: 'isolated', clientId: 'isolated' }
      else if (path === '/api/identity/v1/me') body = { name: '隔离验收账号', sessionId: 'skill-preview' }
      else if (path.endsWith('/tickets')) body = { ticket: 'isolated' }
      else if (path === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
      else if (path.includes('/auth/')) { body = { id: 'd', name: '隔离验收账号', identitySessionId: 'skill-preview', status: 'active', roles: ['super_admin'], capabilities: caps }; if (path.endsWith('/access')) body = { state: 'allowed', member: body } }
      else if (path.endsWith('/availability') && req.method === 'PATCH') {
        let raw = ''; for await (const chunk of req) raw += chunk
        const input = JSON.parse(raw), item = skills.find(s => s.id === decodeURIComponent(path.split('/').at(-2)!))
        if (!control.owner) { status = 403 }
        else if (control.mode === 'conflict') { if (item) item.version++; status = 409 }
        else if (control.mode === 'failure') status = 503
        else if (!item || item.version !== input.version) status = 409
        else { item.enabled = input.enabled; item.version++ }
        body = status === 200 ? { items: skills, canToggle: control.owner } : { detail: '隔离故障场景' }
      } else if (path.endsWith('/management/skills')) { if (control.mode === 'load-failure') status = 503; body = { items: skills, canToggle: control.owner } }
      else if (path.endsWith('/studio/transcript')) body = { items: [], cursor: 0, hasMore: false }
      else if (path.endsWith('/studio')) body = state()
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
await server.listen(); console.log('Isolated Skill UI: http://127.0.0.1:3037/#/overseas/admin/skills')
