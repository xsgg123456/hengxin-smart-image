# Phase17 前端实施与验证

1. 隔离启动：原国内启动链移至 domestic-main，根登录/业务选择/海外路径动态加载统一入口；国内已有业务路径保持启动与重连内存。完成标准：海外单授权不启动国内工作区。
2. 复用登录布局、AuthTopBar、BusinessEntry 和钉钉容器 SDK；BusinessEntry 只依赖通用业务权限类型。统一身份与海外请求采用无国内身份副作用的轻量封装，严格验证响应。完成标准：独立 ticket 兑换、403 禁用、503 重试、401 重登。
3. 正式海外本阶段仅身份、切换与退出；不导入模拟业务。统一退出先撤销身份，再清业务 cookie，错误可见。国内登录授权优先统一服务，仅 config 404 兼容旧服务。
4. 验证：新增协议状态单测，全套单测、typecheck、生产构建；真实 API 浏览器脚本使用隔离浏览器及服务端替身登录，不用角色 URL 伪造授权。独立审查由主 Agent 负责。

本地正式入口：Vite development 3013，身份代理 VITE_IDENTITY_PROXY_URL（默认8010），海外代理 VITE_OVERSEAS_PROXY_URL（默认8009），国内 VITE_API_PROXY_URL（默认8008）。入口 /#/auth/business；海外 /#/overseas。外部钉钉真实配置与双端验收不由本地替身覆盖。

2026-10-12 验证证据：`pnpm test` 258/258；`pnpm build`（包含 vue-tsc）通过，最终 Vite 40.75s。`tests/unified-identity-faults.browser.mjs` 503重试、403禁用、海外身份页、统一退出故障重试与国内bootstrap隔离通过；该脚本明确为HTTP故障注入。
`tests/unified-identity-real.browser.mjs` 连接集成worker隔离Docker三API/数据库/provider替身，both/domestic/overseas/neither 四组均通过：业务按钮、海外刷新/切换、全局退出三个me401、无JS异常，未拦截API也未使用角色URL参数。环境及服务证据由主Agent/集成worker记录。测试启动的Vite3013/3014已停止。真实钉钉及生产尚未验证。
