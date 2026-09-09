"""Configure the isolated, frontend-only Art Design Pro prototype."""
from pathlib import Path
import json

root = Path(__file__).resolve().parents[1] / 'source'
def write(name, content):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
def replace(name, old, new):
    path = root / name
    content = path.read_text(encoding='utf-8')
    assert old in content, name
    path.write_text(content.replace(old, new), encoding='utf-8')

write('.env', 'VITE_VERSION=hx-prototype-1\nVITE_PORT=3007\nVITE_BASE_URL=/\nVITE_ACCESS_MODE=frontend\nVITE_API_URL=/\nVITE_API_PROXY_URL=http://127.0.0.1:9\n')
write('.env.example', (root / '.env').read_text())
replace('vite.config.ts', 'host: true', "host: '127.0.0.1',\n      strictPort: true")
replace('vite.config.ts', 'vueDevTools()', '// Prototype: devtools overlay disabled')
replace('src/config/index.ts', "name: 'Art Design Pro'", "name: '恒信 · 智能图像'")
replace('src/config/setting.ts', 'showSettingGuide: true', 'showSettingGuide: false')
replace('src/config/setting.ts', 'SystemThemeEnum.AUTO', 'SystemThemeEnum.LIGHT')
for feature in ['fastEnter', 'notification', 'chat', 'language', 'settings']:
    replace('src/config/modules/headerBar.ts', feature + ': {\n    enabled: true', feature + ': {\n    enabled: false')
replace('src/main.ts', "import App from './App.vue'", "import App from './App.vue'\nimport { useUserStore } from './store/modules/user'")
replace('src/main.ts', 'initStore(app)', "initStore(app)\n// Local interaction prototype only; no production authentication or API.\nuseUserStore().setLoginStatus(true)")
write('src/api/auth.ts', '''// Frontend prototype fixtures. Replace with real authentication before production.
export async function fetchLogin(_params: Api.Auth.LoginParams): Promise<Api.Auth.LoginResponse> {
  throw new Error('此页面是本地原型，不提供真实登录')
}
export async function fetchGetUserInfo(): Promise<Api.Auth.UserInfo> {
  return { userId: 1, userName: '运营同事', email: '', roles: ['R_SUPER'], buttons: [] }
}
''')
write('src/router/modules/index.ts', '''import type { AppRouteRecord } from '@/types/router'
const pages = [
  ['wallpaper', '替换壁纸', 'ri:landscape-line'],
  ['product', '替换商品', 'ri:box-3-line'],
  ['text', '替换文字', 'ri:font-size-2'],
  ['tasks', '任务中心', 'ri:time-line'],
  ['templates', '模板库', 'ri:layout-grid-line'],
  ['archive', '成品库', 'ri:folder-check-line']
]
export const routeModules: AppRouteRecord[] = pages.map(([path, title, icon]) => ({
  name: `Hx${path}`, path: `/${path}`, component: '/index/index',
  meta: { title, icon }, children: [{
    name: `Hx${path}Page`, path: 'index', component: `/hengxin/${path}`,
    meta: { title, icon, keepAlive: false, fixedTab: path === 'wallpaper' }
  }]
}))
''')
for mode in ['wallpaper', 'product', 'text']:
    write(f'src/views/hengxin/{mode}/index.vue', f'<template><CreateTask mode="{mode}" /></template>\n<script setup lang="ts">\nimport CreateTask from \'../components/CreateTask.vue\'\n</script>\n')
for page, comp in [('tasks','Tasks'), ('templates','Templates'), ('archive','Archive')]:
    write(f'src/views/hengxin/{page}/index.vue', f'<template><{comp} /></template>\n<script setup lang="ts">\nimport {comp} from \'../components/{comp}.vue\'\n</script>\n')
replace('src/components/core/layouts/art-header-bar/index.vue', '<ArtUserMenu />', '<span class="hx-demo-badge">交互原型 · 演示数据</span><ElAvatar :size="32">运</ElAvatar>')
replace('src/main.ts', "import '@styles/index.scss'", "import '@/views/hengxin/prototype.css'\nimport '@styles/index.scss'")
pkg = json.loads((root/'package.json').read_text())
pkg['name'] = 'hengxin-smart-image-prototype'
pkg['scripts']['dev'] = 'vite --host 127.0.0.1 --port 3007 --strictPort'
pkg['scripts']['build:prototype'] = 'vite build'
write('package.json', json.dumps(pkg, ensure_ascii=False, indent=2))
write('PROTOTYPE.md', '''# 恒信智能图像交互原型

基于本机 art-design-pro 源码副本，保留 MIT LICENSE。原布局、导航、主题、Pinia 与 Element Plus 直接复用。

启动：`npm run dev`，打开 http://localhost:3007/#/wallpaper/index 。
构建：`npm run build:prototype`，生成 dist/index.html 与静态资源；需要 HTTP 静态服务器预览。

当前 node_modules 是指向参考项目依赖的本机目录联接，不进入 Git。在其他电脑请先按 pnpm-lock.yaml 安装依赖，并将 .env.example 复制为 .env。

这是独立本地演示：用户身份是 fixture，任务模拟执行，SVG 是示例商品图，未连接真实 CLI、Skill 或生产认证。不能作为已完成生产系统部署。
''')
