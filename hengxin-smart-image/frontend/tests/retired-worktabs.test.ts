import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import * as Vue from 'vue'
import * as Pinia from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import * as access from '../src/router/business-route-access'

test('所有角色清理旧固定/当前/缓存标签，404不能充当有效路由，API标签保留', async () => {
  const source = readFileSync(new URL('../src/store/modules/worktab.ts', import.meta.url), 'utf8')
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
  for (const role of ['super_admin', 'design_manager', 'designer', 'operator']) {
    Pinia.setActivePinia(Pinia.createPinia())
    const router = createRouter({ history: createMemoryHistory(), routes: [
      { path: '/api-image-edits/create', name: 'HxApiImageCreate', component: {} },
      { path: '/:pathMatch(.*)*', name: 'Exception404', component: {} }
    ] })
    const dependencies: Record<string, unknown> = {
      pinia: Pinia, vue: Vue, '@/router': { router }, '@/hooks/core/useCommon': { useCommon: () => ({ homePath: Vue.ref('/api-image-edits/create') }) },
      './user': { useUserStore: () => ({ info: { roles: [role] } }) }, '@/router/business-route-access': access
    }
    const module = { exports: {} as { useWorktabStore: () => { opened: { path: string; name?: string; fixedTab?: boolean }[]; current: { path?: string }; keepAliveExclude: string[]; validateWorktabs: (router: ReturnType<typeof createRouter>) => void } } }
    new Function('require', 'module', 'exports', 'localStorage', code)((name: string) => {
      assert.ok(name in dependencies, name); return dependencies[name]
    }, module, module.exports, {})
    const store = module.exports.useWorktabStore()
    store.opened = [
      { path: '/tasks/index', name: 'HxtasksPage', fixedTab: true },
      { path: '/management/skills', fixedTab: true },
      { path: '/wallpaper/index', fixedTab: true },
      { path: '/unknown' },
      { path: '/api-image-edits/create', name: 'HxApiImageCreate' }
    ]
    store.current = store.opened[0]
    store.keepAliveExclude = ['HxtasksPage', 'HxAdminskills', 'HxApiImageCreate']
    store.validateWorktabs(router)
    assert.deepEqual(store.opened.map(t => t.path), ['/api-image-edits/create'])
    assert.equal(store.current.path, '/api-image-edits/create')
    assert.deepEqual(store.keepAliveExclude, ['HxApiImageCreate'])
  }
})
