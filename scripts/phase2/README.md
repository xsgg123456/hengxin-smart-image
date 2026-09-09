# Phase 2 浏览器回归

从仓库根目录运行。脚本使用 Playwright CLI 的独立内存会话，不连接生产数据库。每条命令完成后再执行下一条，同一会话不要并行。输出目录不纳入 Git。Phase 1 脚本保存历史时点；当前契约的回归使用本目录（已覆盖 Phase 1 核心、身份错误及写后读失败）。

前端目录启动 `npx --yes pnpm@10.33.4 dev --host 127.0.0.1`（3008 mock），另起临时 API 适配服务 `npx --yes pnpm@10.33.4 exec vite --mode development --host 127.0.0.1 --port 3018 --strictPort`。启动前检查对应端口；不结束未知进程。api-flow/response-flow 在浏览器拦截 API，不需要后端。

初始化测试文件：

```powershell
New-Item -ItemType Directory -Force output/playwright | Out-Null
[IO.File]::WriteAllBytes((Join-Path (Get-Location) 'output/playwright/pixel.png'), [Convert]::FromBase64String('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGL5//8/AwMDEwMYAAAAAP//aYxtrAAAAAZJREFUAwAkMAMEkRkhTQAAAABJRU5ErkJggg=='))
[IO.File]::WriteAllText((Join-Path (Get-Location) 'output/playwright/invalid.png'), 'broken')
[IO.File]::WriteAllBytes((Join-Path (Get-Location) 'output/playwright/empty.png'), [byte[]]@())
[IO.File]::WriteAllBytes((Join-Path (Get-Location) 'output/playwright/too-large.png'), (New-Object byte[] (10 * 1024 * 1024 + 1)))
[IO.File]::WriteAllText((Join-Path (Get-Location) 'output/playwright/wrong.svg'), '<svg xmlns="http://www.w3.org/2000/svg"></svg>')
```

使用 Chrome 和独立会话：

```powershell
npx --yes --package @playwright/cli playwright-cli -s=hx-phase2 open http://127.0.0.1:3008 --browser chrome
npx --yes --package @playwright/cli playwright-cli -s=hx-phase2 run-code --filename scripts/phase2/core-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase2 run-code --filename scripts/phase2/upload-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase2 run-code --filename scripts/phase2/template-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase2 run-code --filename scripts/phase2/pagination-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase2 run-code --filename scripts/phase2/api-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase2 run-code --filename scripts/phase2/response-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase2 run-code --filename scripts/phase2/visual-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase2 close
```

完成后停止本次启动的 3018 临时服务。保留需要交付的截图，删除本次生成的损坏/空/超大等测试文件。mock 的列表/上传/保存/提交失败场景每次刷新只失败一次，所以脚本开头刷新以重置前提；同一场景内的重试不会刷新。
