# API 优化预览验收 · 2026-09-22

范围：本地 demo/mock 的 API 换套图交互，未修改真实后端及 Real* 页面，未部署生产。

- `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit` 退出0。
- `node node_modules/tsx/dist/cli.mjs --test tests/*.test.ts`：146通过、0失败，日志 `output/api-optimization-preview/tests.log`。包含10+1批次屏障、1/2/4秒重试、旧结果保留/修改恢复、ZIP顺序/CRC/最新结果及打包中变更拒绝。
- Demo构建29.20秒、production构建35.67秒，均退出0，分别见同目录 `build-demo.log`、`build-production.log`。
- 隔离浏览器上下文验证：52×52缩略图、筛选空态、真实ZIP下载、无效上传拒绝/有效图片解码、图文修改、1440/1280弹框边界、输入保留且无加载遮罩；未发出 `/api/v1` 业务请求。见 `browser-evidence.json` / `exercise.cjs`。
- 失败恢复：单张修改首调后耗尽3次重试，原结果保留且ZIP禁用；重试修改成功；ZIP网络失败提示后可重试成功；十张同时处理且第十一张等待。见 `failure-evidence.json` / `failures.cjs`。
- 交互边界：取消重开清理未提交草稿、空输入禁止提交、仅上传标注图成功、双击仅一条提交记录、抽屉滚动400px等待3.5秒保持400px，无loading遮罩。见 `edge-evidence.json` / `edges.cjs`。
- 本机ZIP实际解包11项且CRC通过。`results.zip` 为首次示例结果，`revised-results.zip` 为修改后当前结果。
- 最终稳定截图：`final-records-1440.png`、`final-records-1280.png`、`final-detail.png`、`final-revision.png`；邻居任务中心对比图 `baseline.png`。均在 `output/api-optimization-preview/`。旧文件名截图含动画中间帧，不能作为最终视觉结果。

本地入口：`http://127.0.0.1:3010/#/api-image-edits/records`。使用原框架独立Demo模式，示例数据在刷新后重置。实机API并行/重试/修改及线上ZIP功能尚待正式实现。
