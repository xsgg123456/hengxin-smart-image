# 海外图片缓存隔离浏览器回归

在仓库根目录运行：

```powershell
# 已安装 playwright 且 Node 可解析时无需环境变量。
# 否则设为现有 playwright/index.mjs 的绝对路径。
$env:PLAYWRIGHT_MODULE = '<现有 Playwright 模块路径>'
node scripts/image-cache/browser.mjs
```

要求前端锁定依赖已安装，Playwright 对应 Chromium 已安装。脚本使用前端自己的 Vite、Vue、Element Plus；直接挂载生产 `StudioAssetImage.vue` 和生产缓存模块。

服务器仅监听随机 `127.0.0.1` 端口，API 全部由当前进程生成的 PNG fixture 回答，不访问真实 API、身份服务、数据库或用户浏览器。浏览器使用临时隔离 context，最终关闭浏览器与 HTTP/Vite 服务。没有调用 Playwright route，因为它会禁用 HTTP 缓存。

验收覆盖：缩略/原件分离、缩略图429自动重试、后台预取与点击共用请求、HEAD 权限/版本校验、刷新真实 304、1600×1000 原图、左右键/Enter/缩放/下载哈希、附件与素材链路、401/403/404 清除、失败重试、ETag 更新、换账号/退出/切会话取消、点击优先和双并发、LRU/字节预算。

`output/image-cache/result.json` 保存检查结果、实际 HTTP 请求记录和下载 SHA256，六张编号 PNG 保存主要状态截图。失败保存 `failure.json` 和 `failure.png`，后续通过会清除过期失败证据。整个 output 目录已被 Git 忽略。

边界：本脚本证明真实浏览器和生产组件/缓存的集成行为，不替代后端权限实现验证、生产延迟测量或完整工作台页面回归。
