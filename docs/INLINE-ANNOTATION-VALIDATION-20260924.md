# 单画布标注正式接入验证 · 2026-09-24

## 回归与构建

- 前端 `node --import tsx --test --test-concurrency=1 tests/*.test.ts`：170 passed、0 failed，原始日志 `output/annotation-frontend-tests.txt`。首次并行运行遇既有 Demo 定时器测试时序失败；串行完整重跑通过，未修改该测试。
- `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`：PASS，日志 `output/annotation-typecheck.txt`。
- `node node_modules/vite/bin/vite.js build`：PASS，35.10 秒；Demo 构建 `build --mode demo --outDir dist-demo`：PASS，35.29 秒。日志分别为 `output/annotation-production-build.txt`、`output/annotation-demo-build.txt`。
- 后端 `.venv/Scripts/python.exe -m pytest -q`：985 passed、170 skipped、15 warnings，68.90 秒；日志 `output/annotation-backend-tests.txt`。跳过项涉及平台/符号链接权限和专用 PostgreSQL 环境，未计为通过。本轮没有数据库迁移。
- 独立审查发现 CLI 仅上传无文字与既有后端必填意见契约不符，已补入口校验和提示，并完成单测与浏览器复验；API 保留仅标注图提交。
- 本轮未提交 Git、未部署生产、未调用收费生图。
- 独立审查 Stage 1/Stage 2 PASS；复跑浏览器首屏一次超时，未改代码第二次完整通过。开发服务自动删减的生成类型文件已恢复，最终 `review-status` 返回 `approved: true`、`changedFiles: []`，快照 `957cf362abfbb37d63b10431a63565c51bb5517435de7e0c81115db20c883ef7`。审查报告：`docs/INLINE-ANNOTATION-IMPLEMENTATION-REVIEW-20260924.md`。

## 隔离浏览器证据

执行脚本：`hengxin-smart-image/frontend/tests/inline-annotation.browser.mjs`。真实开发模式 Vue 页面，由独立本地 Vite `127.0.0.1:3024` 提供；Playwright 使用全新无持久化浏览器上下文。全部 `/api/` 由浏览器拦截契约响应，未匹配业务请求立即报错；外站请求全部阻止（Iconify 字体图标端点尝试记录在 JSON）。没有连接生产 API、数据库或收费生成服务。

本轮执行通过，浏览器未捕获 JavaScript 异常。原始证据位于 `output/inline-annotation-20260924/checks.json`，截图为同目录 `api-mixed-marks.png`、`api-preview.png`、`cli-preview.png`、`api-upload-1280x720.png`。

| 范围 | 实际验证与断言 |
| --- | --- |
| 原图来源 | 列表图片为 79×150 缩略图；API 标注请求 V2 文件 `content?download=true`，CLI 选择历史 V1 后请求 V1 文件下载；编辑器显示真实 790×1500。 |
| 加载失败 | 第一次原图下载返回 503，点击重新读取后正确加载，未退回缩略图。 |
| 混合标注 | 真实鼠标矩形框选、填第 1 条意见；放大至 150%、固定手柄平移；切画笔添加第 2 条意见；画笔选中时再次平移、继续画笔生成第 3 条；撤销恢复 2 条并保留第 1 条意见。每次平移断言 viewBox 改变且未增加标注。 |
| 草稿 | API 关闭、重开编辑弹框，2 条编号意见仍在，意见原文一致。 |
| 合成提交 | 预览含两条编号意见与整体补充；解析真实 multipart 请求内 PNG IHDR，两入口均为 790×1500；外部上传保持同尺寸。 |
| 不确定结果重试 | API 与 CLI 第一次修改请求均主动断网；点击确认原请求后逐字比较请求 body 与 Idempotency-Key 一致，每个入口仅上传一次合成 PNG。CLI 请求保留历史 `baseVersionId=version-1`，API 保留 `baseVersion=2`。 |
| 外部标注 | API 文件选择器上传有效 PNG，允许仅图片无文字预览及提交；CLI 仅图片无文字时明确提示填写意见，禁止进入预览。 |
| 版本冲突 | 模拟 API 提交返回 409 VERSION_CONFLICT，显示当前版本已更新，弹框保持打开，没有切成不确定请求确认按钮。此项为服务器冲突响应验证，不代表并发真实服务测试。 |
| 窄窗 | 1280×720 下编辑器内容限制高度、页脚位于视口内，关闭及预览按钮可见可点击。 |

复现（在 `hengxin-smart-image/frontend`，先确认 3024 空闲）：

```powershell
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 3024 --mode development
$env:PLAYWRIGHT_MODULE='file:///C:/Users/82358/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'
node tests/inline-annotation.browser.mjs
```

边界：这是实际浏览器、真实产品组件与请求构造的 HTTP 契约隔离验收；没有验证生产连接、真实模型修改效果或线上部署。旧上传入口拖拽/剪贴板通用交互已有 `image-inputs.browser.mjs`，本次新增脚本实跑文件选择上传，不将历史脚本未重跑的结果算作本轮通过。
