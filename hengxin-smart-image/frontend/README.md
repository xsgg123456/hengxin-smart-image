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
当前阶段进度以根目录 [DEV-PLAN.md](../../DEV-PLAN.md) 为准；最新阶段证据见 [Phase 11 验证记录](../docs/PHASE11-VALIDATION.md)。真实模式已接文件、模板、任务、返工和成品接口；钉钉认证、其余管理接口和生产联调仍属 Phase 12–14。模拟预览不能作为真实 AI 生成或容量验证证据。

真实联调先按 [后端开发说明](../docs/BACKEND-DEVELOPMENT.md) 启动服务，在后端本机 `.env` 设置 `ENABLE_DEV_IDENTITY=true`，再执行 `pnpm dev:api`。默认关闭开发身份时业务请求返回 401。若更改后端 API_PORT，在前端 `.env.local` 设置对应的 `VITE_API_PROXY_URL` 并重启前端。真实 AI 还需 [专用 Linux Worker](../docs/CODEX-EXECUTION.md)。

保留上游 `LICENSE`。项目沿用根仓库及其 hooks，不在前端安装嵌套 Git hooks。
