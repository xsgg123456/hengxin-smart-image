# API 换套图预览验证 · 2026-09-22

## 本轮结果
- 类型检查：在 frontend 执行 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`，退出 0。
- 测试：`node node_modules/tsx/dist/cli.mjs --test --test-concurrency=1 tests/*.test.ts`，128 通过、0 失败，包含新增全局串行、1/2/4 秒退避耗尽和失败项恢复测试。日志 `output/api-preview-tests.log`。
- Demo 构建：`node node_modules/vite/bin/vite.js build --mode demo --outDir dist-demo`，退出 0。日志 `output/api-preview-build-demo.log`。
- production 构建：`node node_modules/vite/bin/vite.js build`，退出 0。日志 `output/api-preview-build-production.log`。新增菜单仅 demo 模式注册。
- 浏览器：独立临时 Chromium 上下文运行 `node output/api-preview-check.cjs`，退出 0；检查结果 `output/api-preview-browser.json`。覆盖空输入、损坏图片、顺序调整、指定素材、移除、提交、串行重试、关闭详情再打开、部分失败、失败项重试、图片查看器、实际示例文件下载、搜索空态、删除取消/确认、1280 宽度无横向溢出。未请求 `/api/v1`，无页面异常。
- 图片样例不是实际换图结果，未调用公司中转站，也未修改后端。
- 独立审查追加上传故障边界：延迟损坏图片解码回调，切换页面再返回仍不可提交；释放失败回调后损坏图从共享草稿移除。`node output/api-preview-review-boundary.cjs` 输出 `Route-change decode guard PASS`，冻结输入恢复为 6 张。修复后类型检查、128 项测试和两种构建重新全部通过。

## 截图与访问
位于仓库 output：`api-preview-baseline.png`（现有页面对照）、`api-preview-create.png`、`api-preview-create-1280.png`、`api-preview-retry.png`、`api-preview-partial.png`、`api-preview-results.png`、`api-preview-records.png`。

本地运行：frontend 下 `node node_modules/vite/bin/vite.js --mode demo --port 3010 --host 127.0.0.1`。打开 `http://127.0.0.1:3010/`，侧栏进入 API 换套图 → 新建换图，点击“填入示例套图”，选择演示场景并提交。当前模块内存数据刷新重置，不影响原 CLI Demo 持久化数据。

## 交付边界
本次交付为本地交互评审，不代表生产 API 功能完成，未提交、未部署。独立审查结论见 API-IMAGE-PREVIEW-REVIEW.md。
