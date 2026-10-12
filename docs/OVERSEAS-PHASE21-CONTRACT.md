# Phase 21 执行合同

本轮用户授权连续完成 Phase21–25，每阶段验收后独立本地提交，不推送、不部署、不调用收费模型。先完成当前阶段，再推进后继阶段。

## 有序实施与验收

1. 持久执行底座：海外 Job、ExecutionGate、JobOutbox、ExecutionEvent 和冻结迁移0006；准入锁串行统计全部活动作业，分析/重分析/生图/返工共享最多5槽。幂等入队、重复消息不重跑、过期租约转 uncertain 且仍占槽，资源不足停留 queued。验收真实PG至少6作业多worker竞争与回滚。
2. 隔离执行器：直接复用 execution.workspace/process 和事件脱敏，海外独立路径、认证、Skill快照和物料快照；停止请求只标 cancelling，确认进程退出才能释放。执行成功须同时检查租约、令牌、进程回执和协议产物。无法确认的旧进程保留 uncertain，不自动重试。验收本地子进程替身、超时、失联、迟到结果和独立会话。
3. 任务执行查询与事件续传：GET tasks/{id}/jobs，GET tasks/{id}/execution-events?after=N，POST jobs/{id}/cancel（version）。每次请求重验海外身份与任务权限，取消限 task.design；JSON游标拉取用于断线续传，前端自动轮询并在离页停止。前端使用现有ElCard/Tag/Button/Alert，显示真实排队/运行/错误，无假百分比。验收改派撤权、取消冲突、故障恢复与浏览器。
4. 完整回归、类型构建、隔离功能验证、独立两阶段审查及快照批准后提交。未通过只能标进行中未验收。

## 模块合同

- execution.queue.enqueue(session, task_id, kind, dedupe_key, payload)：事务内冻结JSON输入并创建作业及outbox；合法kind为analysis/reanalysis/generation/revision。不自行commit，不创建任务业务方案。
- claims.claim(factory, job_id) -> UUID | None；claims.renew(factory, job_id, token) -> bool；claims.finish(factory, job_id, token, status, result=None, error=None) -> bool。成功只接受有效租约、当前token、已确认退出；取消/失联不接受成功。
- Job字段：id/task_id/kind/dedupe_key/payload/status/version/claim_token/lease_until/worker_node/process_id/process_boot/process_started/cancel_requested/result/error/started_at/completed_at/execution_count；进程身份证据供恢复核实。ExecutionEvent按自增id作游标，仅发布脱敏的固定状态和安全消息。
- worker任务调用runner.run(factory, job_id)，独立Celery队列overseas.cli；outbox可安全重复投递，queued周期重发。runner提供内部协议handler注册以供Phase22/23接入，未注册协议失败关闭，不能冒充业务完成。
- Phase21不将task.created作为分析指令；Phase22连接资料提交与方案分析，Phase23连接生图返工。测试内部入队不开放任意payload公共API。

## 复用与边界

沿用一期执行门闩/租约/事务outbox设计，抽取中立公共算法时保留一期回归。不能导入国内模型承载海外状态。外部库维持锁定版本；已核查SQLAlchemy2.0行锁与Celery5.6预取/晚确认文档，数据库门闩是总并发事实来源。
