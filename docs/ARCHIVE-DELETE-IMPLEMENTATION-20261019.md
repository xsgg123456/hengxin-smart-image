# 海外成品库删除实施与验收

需求原文：这边成品库也帮我加一个删除的功能，点击删除后显示二次确认，然后直接删除对应的所有东西。

范围以 Product-Spec.md「2026-10-19 · 海外成品库整套删除」为准。本次是成品库独立归档删除，保留还存在的来源任务和源材料；生产用户现有归档不作为删除测试数据。

## 执行顺序与完成标准

1. 后端：持久删除请求、快照冲突检查、权限和清理维护接入。完成标准为归档记录/资产/历史及对应对象真实消失，失败可恢复，其他资源保持；历史归档与源任务存在两种情况均覆盖。
2. 前端：卡片危险操作、最新详情二次确认、删除状态及重试、列表分页联动。完成标准为取消不发删除、确认后仅真实完成显示成功，失权/失败/刷新均可正确处理，桌面和窄屏可操作。
3. 集成：专项和全套测试、类型检查及生产构建、隔离浏览器交互与文件清理验证；固定快照后独立两阶段审查。按实际证据记录上线状态，不能以本地验证代替生产验证。

分工：后端 worker 只负责 backend 源码/迁移/测试；前端 worker 只负责 frontend 归档页面/API/测试；主 Agent 负责源文档、接口协调、集成验证、审查及交付。各 worker 不提交、不再派发代理。

## API 合同

- 列表/详情增加 deleteToken、deletionStatus、deletionError。
- GET /api/overseas/v1/archives/{id}/deletion-preview 返回仅管理员可读的最新确认摘要；不读取或复制图片，缺失/损坏文件不能阻塞删除确认。
- DELETE /api/overseas/v1/archives/{id}，请求 deleteToken；返回 archiveId、status、error。
- GET /api/overseas/v1/archives/{id}/deletion 查询最小删除凭据。status 为 deleting、delete_failed、deleted。
- 当前归档内容与确认 token 不一致拒绝提交。删除中禁止读取文件与追加归档，实际完成才删除本体并返回 deleted。

## 验证记录

本地实现完成，生产尚未部署，现有生产归档未修改。验证使用独立 PostgreSQL、Redis、MinIO 和测试身份服务，没有模型调用。

- `pnpm test`：301 项通过，0 失败，见 `output/archive-delete-frontend-tests.log`。
- `pnpm build`：类型检查及生产构建通过，见 `output/archive-delete-frontend-build.log`。
- 后端 HTTP 删除专项：22 项通过；真实 PostgreSQL 并发与迁移 6 项通过（`output/archive-delete-pg-tests.log`），另有既有数据库回归 17 项通过。
- `overseas-archive-delete-real.browser.mjs`：5 组通过、浏览器异常 0。验证四种非管理员真实 403、取消零 DELETE、桌面与390px确认、已有图片缺失仍可删除、刷新恢复进度、真实 MinIO 停机失败与恢复重试、所有归档对象消失且其余对象与任务保持。结果及截图：`output/playwright/archive-delete/`。
- 第一轮独立审查发现删除确认依赖图片读取，已改为仅元数据确认接口，并补缺失图片、损坏字节、资产记录缺失三类用例。确认接口不触发保护复制，实际删除仍检查对象归属。
- 全后端首次完整运行暴露新增路由清单漏项、旧认证模拟未创建被断言保留的文件、测试容器未启用 init 导致进程测试父PID为1。已同步路由清单，明确种入无凭据的测试文件，使用 `docker run --init --network none` 重跑；不修改生产进程逻辑以适配测试。
- 最终全 Linux 后端：`docker run --rm --init --network none ... /app/.venv/bin/python -m pytest -q -p no:cacheprovider`，2087 passed、155 skipped、6 warnings，259.33秒；条件跳过不计为通过，归档新增 PG 并发和迁移已单独真实执行。日志 `output/archive-delete-backend-tests.log`。
- 最终两阶段审查均 PASS，报告 `docs/reviews/ARCHIVE-DELETE-REVIEW-FINAL-20261019.md`；批准快照 `a38ead4468645a66de9c79d2b468c7044028a40f195da4aa483231d2b717de66`。审查者另跑删除与retention 31项通过。测试结束已关闭本次Vite及隔离数据库/Redis/MinIO容器，既有测试PG未动。

部署时必须同时更新海外 API、原生维护循环并执行海外 `0019` 迁移，发布共享前端；保留已恢复的双域凭据代理、worker环境及原工作目录。仅更新按钮或仅更新 API 不足以交付生产删除能力。
