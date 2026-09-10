# Phase 11 清理策略与运行边界

清理服务默认关闭，未注册 Celery 定时任务、启动任务或生产入口。Q-004/Q-006 的保留期限未确认，不采用 30 天或任何默认时间。

显式调用 `cleanup_file(factory, store, file_id, policy)` 或 `cleanup_session(factory, root, task_id, policy)` 时，调用者须给对应 UTC cutoff。每次只处理一个对象，返回明确状态；其他类别的 cutoff 不会启用本类别。

- 对象仅回收 cutoff 之前的 staging/failed 记录。ready 对象全部保留；模板图片、任务输入、图片版本、归档图片引用始终保留，包括逻辑删除的父资源。
- 使用 PostgreSQL 引用表写入互斥与对象行锁。竞争时立即保留；SQLite 等无所需锁语义的数据库不执行删除。
- 先将重试凭据写入 `cleanup_objects` 并在同一事务删除无引用文件元数据，再删除对象，保证迟到上传或引用写入不能重新发布对象。对象存储失败时保留数据库凭据；可显式调用 `cleanup_pending_object` 重试。数据库提交失败不删除对象，成功删除对象后才移除凭据，重复删除幂等。
- 会话仅处理 cutoff 之前已删除的任务；任务行锁与返工、认领共用。所有轮次与 Job 必须终态，所有执行尝试须明确 finished 且有结束时间；starting/running/uncertain 一律保留。仍有关联归档的任务材料也保留。
- 根目录必须显式传入，目标仅由已验证 UUID 生成。拒绝目录链接、junction、根目录及越界路径，不依据数据库中的 workspace 路径删除。会话记录和审计不删除，清理仅移除任务目录。文件系统失败返回可重试状态。

计划：先实现上述门禁与单对象清理，再用临时库/目录验证实际删除、引用保护、存储故障、越界保护及 PostgreSQL 独立连接竞争。审查与总体 Phase 验收由主 Agent 统一执行。

锁语义依据：[PostgreSQL explicit locking](https://www.postgresql.org/docs/16/explicit-locking.html)。会话删除期间仅对终止任务持有短事务，不等待 CLI；实际目录清理耗时取决于材料数量，生产启用前需确认保留策略和运维窗口。
