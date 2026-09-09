# Phase 8 执行计划

2026-09-09。用户已验收Phase7并授权继续；依据Product-Spec v0.17 REQ003/004及9.2、DEV-PLAN Phase8。保留之前未提交成果，不提交代码。

1. 任务数据与受理：持久化任务/素材快照、轮次、图片版本、幂等请求和全局执行占用；模板、Skill、素材及意见冻结，同事务写任务/轮次/Job/outbox。完成标准：三入口校验、同操作者同键同内容返回原202、异内容409、跨用户共享读取和删除审计、版本/图片数与快照一致。
2. 执行控制：数据库原子认领、短事务全局并发门限（初值1）、同任务最多一个未结束轮次、终态停止消息派发；持久取消和失效结果屏障。生成作业过期租约不自动接管，转待核实并保持占用。完成标准：两个独立Worker重复消息单次启动、限额1时第二任务排队、可读状态且可取消、排队/运行/上传后取消不发布、过期/旧token不重启不发布；内部轮次服务验证同任务不同新请求互斥，返工HTTP留Phase10。
3. 前端接入：请求幂等键随同一次提交保留，网络不确定/已受理读取失败不换键重复新建；任务分页/筛选/详情/删除/轮询真实API；详情显示服务端executionControl与禁止原因，保留原布局。测试来源明确标注。完成标准：41项既有测试回归、新契约和重试测试、浏览器三入口/关闭页面继续/详情结果下载/删除/错误表单保留通过。
4. 验证与交付：新迁移、Linux PG/Redis/MinIO多Worker隔离测试、完整后端pytest/前端tests/typecheck/build、Phase7回归、独立两阶段审查→修复，形成PHASE8-VALIDATION/REVIEW。

审查补充验收：登录失效卸载表单后，同一可信用户重新登录必须恢复该入口的请求快照、幂等键、受理回执和草稿；切换用户不得显示或重放原用户请求。状态需跨组件生命周期保留，验证卸载重建及身份隔离，不能只测同一实例的401。

运行边界：enable_fixture_executor默认false，仅APP_ENV=test可以启用；generation_concurrency初值1、范围1–10；fixture_delay_seconds用于受控测试。没有生产执行器时新生成明确503且不建立伪成功任务；已受理幂等重放仍返回原回执。fixture从已冻结图片生成可读取的独立结果文件，用executionSource=fixture标记，不伪造CLI会话或用量。Phase9接真实CLI。executionControl={canRevise,canRetry,blockedReason}由服务端返回；Phase8尚无返工HTTP功能，能力为false并给原因。

分工：后端执行者独占backend（含contracts/main/migrations/tests），前端执行者独占frontend（含mock和测试），主Agent负责根源文档、infra、scripts及整体验证。后端传输约定：Task新增可选executionSource:'fixture'|'unavailable'|'cli'；TaskDetailData新增必需executionControl。CreateTaskInput字段不变，POST/tasks通过Idempotency-Key请求头必需传入；202 Accepted不变，GET/tasks及GET/tasks/:id保留既有结构，DELETE/tasks/:id返回DeletionReceipt。前端createTask(input,idempotencyKey?)第二参数兼容老mock调用，HTTP无指定时只在直接调用边界生成一次，UI必须显式保留键。各方先读相关原文，不覆盖他人，不spawn、不commit。
