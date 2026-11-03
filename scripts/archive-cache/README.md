# 归档图片真实组件回归

在仓库根运行 `node scripts/archive-cache/browser.mjs`。通过 `PLAYWRIGHT_MODULE` 指定已安装的 Playwright 模块；不新增依赖。

脚本仅启动随机 localhost 端口上的隔离 HTTP fixture，使用实际 OverseasArchivePage / Detail / Cover / Picture / Viewer 及共享缓存；不连接生产、不写用户数据、不使用 route 拦截（避免禁用 Chromium HTTP 缓存）。独立浏览器 context 随运行关闭，fixture 无数据库或持久用户配置。输出位于忽略的 output/archive-cache。

覆盖缩略失败重试、列表零原图、详情2并发渐进预取、放大切换/重开HEAD304、浏览器刷新GET304、原件下载哈希、缩略未完成时独立下载、筛选/关闭取消、失败恢复、403清整套缓存、删除/退出/换号、390px窄屏。result.json记录请求数/字节/耗时与下载哈希，PNG记录视觉状态。耗时仅代表本机fixture，不代表生产延迟。

共享缓存单测另覆盖40张/128MiB预算机制（小预算等价边界）、超大原件、点击队列晋升、独立owner互不取消、去重、乱序、版本变化及401/403/404。
