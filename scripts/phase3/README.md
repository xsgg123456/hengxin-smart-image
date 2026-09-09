# Phase 3 浏览器验收复跑

从仓库根目录运行。使用独立 Playwright 内存会话 `hx-phase3`，只访问本地前端；API 错误由浏览器拦截模拟，不连接生产数据库。需 Chrome、Node、现有 pnpm 依赖。脚本逐条执行，不并发控制同一会话。

先检查端口，再在前端目录启动：

```powershell
npx --yes pnpm@10.33.4 dev --host 127.0.0.1
# 独立终端：仅 API 故障回归使用，结束后停止本次进程
npx --yes pnpm@10.33.4 exec vite --mode development --host 127.0.0.1 --port 3018 --strictPort
```

仓库根目录执行：

```powershell
New-Item -ItemType Directory -Force output/playwright | Out-Null
npx --yes --package @playwright/cli playwright-cli -s=hx-phase3 open http://127.0.0.1:3008 --browser chrome
npx --yes --package @playwright/cli playwright-cli -s=hx-phase3 run-code --filename scripts/phase3/create-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase3 run-code --filename scripts/phase3/version-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase3 run-code --filename scripts/phase3/failure-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase3 run-code --filename scripts/phase3/api-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase3 run-code --filename scripts/phase3/visual-flow.js --raw
# Phase 2 模板及身份/启动兼容回归
npx --yes --package @playwright/cli playwright-cli -s=hx-phase3 run-code --filename scripts/phase2/template-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase3 run-code --filename scripts/phase2/response-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase3 close
```

脚本在需要时主动刷新，重置当前模拟数据；同一失败场景内的重试不刷新。version-flow 下载 `phase3-history.svg` 与 `phase3-current.zip` 到 output/playwright，其他未保存下载随独立会话关闭清理。保留本次验收截图；关闭会话并结束临时 3018 服务，不停止已存在的其他服务。

Phase 1/2 旧 core-flow 和 accepted-flow 保留各自验收时点；新的结果槽、版本选择和独立详情接口由本目录对应流程覆盖。当前全服务测试仍统一执行前端目录 `npx --yes pnpm@10.33.4 test`。
