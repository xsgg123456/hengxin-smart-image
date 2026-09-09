# Phase 1 浏览器回归

这些文件是 Playwright CLI `run-code --filename` 的函数输入，不是后端服务，也不是普通 Node 入口。执行方式见 `hengxin-smart-image/docs/PHASE1-VALIDATION.md`，从仓库根目录运行，服务仅绑定 localhost。输出目录与隔离会话使用以下初始化：

```powershell
New-Item -ItemType Directory -Force output/playwright | Out-Null
[IO.File]::WriteAllBytes((Join-Path (Get-Location) 'output/playwright/pixel.png'), [Convert]::FromBase64String('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jP5cAAAAASUVORK5CYII='))
```

每条命令完成后再执行下一条；不要并发操作同一浏览器会话。完成后运行 `playwright-cli -s=hx-phase1 close` 关闭独立会话，停止本次临时3018服务。生成结果仅存浏览器临时内存；不读取用户生产数据。脚本不持久化登录凭据。
