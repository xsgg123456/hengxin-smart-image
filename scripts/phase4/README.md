# Phase 4 前端验收复跑

从仓库根目录执行，使用独立 Playwright 内存会话，不写生产数据。先检查端口，再在前端目录启动模拟服务 3008 与临时真实 HTTP 模式 3018：

```powershell
npx --yes pnpm@10.33.4 dev --host 127.0.0.1
# 独立终端，仅供 API 拦截测试
npx --yes pnpm@10.33.4 exec vite --mode development --host 127.0.0.1 --port 3018 --strictPort
```

仓库根目录准备空 ZIP 作为模拟上传文件（只演示接收与安装状态，不是真实业务 Skill）：

```powershell
New-Item -ItemType Directory -Force output/playwright | Out-Null
[IO.File]::WriteAllBytes((Join-Path (Get-Location) 'output/playwright/phase4-skill.zip'), [byte[]](80,75,5,6,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0))
npx --yes --package @playwright/cli playwright-cli -s=hx-phase4 open http://127.0.0.1:3008 --browser chrome
npx --yes --package @playwright/cli playwright-cli -s=hx-phase4 run-code --filename scripts/phase4/auth-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase4 run-code --filename scripts/phase4/management-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase4 run-code --filename scripts/phase4/api-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase4 run-code --filename scripts/phase4/visual-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase4 run-code --filename scripts/phase3/create-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase4 run-code --filename scripts/phase3/version-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase4 run-code --filename scripts/phase2/template-flow.js --raw
npx --yes --package @playwright/cli playwright-cli -s=hx-phase4 close
```

逐条执行，不并发控制同一浏览器，不在交互脚本运行中修改源码触发 HMR。结束后关闭独立会话、按进程身份停止本次临时 3018 服务；保留已有 3008 用户预览。不批量终止其他 Node 或浏览器进程。

统一测试和生产构建在前端目录执行 `npx --yes pnpm@10.33.4 test`、`npx --yes pnpm@10.33.4 build`。测试使用内存对象和浏览器接口拦截；截图及下载文件保存在本机 output/playwright，不纳入 Git。
