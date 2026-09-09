# 恒信 AI 换套图前端

正式源码继承已认可原型；原型保留在根目录 `prototype/source` 供对照。

使用 Node.js 24.18.1 和 pnpm 10.33.4。若全局 pnpm 版本不同，可用 `npx --yes pnpm@10.33.4` 代替下列 `pnpm`。

```sh
pnpm install --frozen-lockfile
pnpm dev
pnpm typecheck
pnpm test
pnpm build
```

- `dev`：显式 mock 模式，预览地址 http://127.0.0.1:3008。
- `dev:api`：真实接口模式；请求 `/api/v1`，开发代理指向 http://127.0.0.1:8008。
- `build`：先严格类型检查，再生成真实接口模式产物 `dist`。
- `build:preview`：显式 mock 模式预览构建，产物 `dist-preview`；不能用作生产发布。
- `serve`：本机预览正式 `dist` 产物。

无需复制 `.env` 即可运行；可参考 `.env.example` 配置接口地址，不放密钥。
模拟数据仅在内存中使用，刷新恢复初始状态，不提供持久化、真实生成或真实鉴权。
只有显式 `--mode mock` 启用模拟，真实模式失败不回退模拟数据。
前端 Phase 1–4 已验收；后端基础 Phase 5 技术验证通过、待用户验收，业务接口目前返回 501。用户归属与真实文件从 Phase 6 接入，真实 CLI 执行在 Phase 9、钉钉登录在 Phase 12 接入。前端验证不代表这些真实能力已完成；启动后端见 [后端开发说明](../docs/BACKEND-DEVELOPMENT.md)。

保留上游 `LICENSE`。项目沿用根仓库及其 hooks，不在前端安装嵌套 Git hooks。
