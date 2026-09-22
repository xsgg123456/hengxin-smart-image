# 图片历史版本预览验证 · 2026-09-22

范围：本地 demo/mock，可点击预览，无生产 API、部署或提交。

- 最终 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit` 退出 0。
- 最终 `node node_modules/tsx/dist/cli.mjs --test --test-concurrency=1 tests/*.test.ts`：149 pass / 0 fail。首次并行执行时既有 demo-state 定时器用例受负载影响失败，串行完整重跑通过。日志：output/api-optimization-preview/version-tests.log。
- 最终 `node node_modules/vite/bin/vite.js build`：41.97s，退出 0。日志：output/api-optimization-preview/version-build.log。
- 隔离 Chromium 实测：三版列表、双图对比、取消恢复不变、V1 恢复保留三版、当前版 ZIP、V1 基础修改生成 V4、意见与标注图留存、处理中禁恢复、仅一版提示。无页面错误及生产业务 API 请求。
- 脚本 output/api-optimization-preview/versions.cjs；结果 version-evidence.json；截图 version-1440.png、version-1280.png、version-v4.png。单图历史失败锁由状态单测与源码验证，打包锁由源码验证，未把这两条称为浏览器实测。
- 审查者独立验证 version-v1.jpg 与 sample-1.jpg 真实字节一致；version-restored.zip 的 11 张图片按当前版本/原图顺序、CRC 与真实字节一致。
- 回归覆盖失败不新增历史、恢复后编号递增、旧历史不变、其他图片不变，以及初始版本生成时间使用成功时刻。

当前页面：http://127.0.0.1:3010/#/api-image-edits/records 。点“三版对比与恢复”，再点原图1的“历史版本（3）”。
