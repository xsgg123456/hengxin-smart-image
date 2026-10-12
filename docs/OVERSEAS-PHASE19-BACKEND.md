# Phase19 后端实施与验证

## 实现

- 海外独立五表：任务、多 SKU、版本事件、幂等请求、outbox；仅依赖海外 Member/Base 与共享 Timestamps。
- 冻结 `overseas_0004` 历史表结构，逐表 checkfirst；0003 既有成员、角色、会话、审计保留。更新海外模型登记、schema head 与路由隔离断言。
- POST tasks 严格字段/长度/平台/SKU/指定设计校验，保存状态 created；不创建 Job，不启动 Worker。
- 范围分页、SKU/完整 ID 查询、详情与精确任务 capabilities；设计候选最小字段、搜索与分页。
- 改派采用权限事务锁 → 共享幂等锁 → 任务行锁；等待后刷新操作者与候选，版本冲突拒绝；保留状态和 SKU。
- 创建/改派同事务保存事件、outbox、请求；重复请求返回当前任务，不回滚后续负责人，仍验证当前权限。

## 验证环境与命令

运行器 `hx-management-test:local` 内 `/app/.venv/bin/python`，源码挂载 `/workspace`，工作目录与 PYTHONPATH 均为 `/workspace`。真实数据库只使用本轮临时 PostgreSQL `57266/overseas_test`；并发测试逐例创建独立 schema，迁移测试逐例创建/销毁独立数据库；未触及生产。

```text
python -m pytest tests/test_overseas_tasks.py tests/test_overseas_assignment.py tests/test_overseas_tasks_postgres.py tests/test_overseas_tasks_migration.py tests/test_overseas_auth.py tests/test_overseas_members.py tests/test_overseas_permissions.py tests/test_overseas_configuration.py tests/test_overseas_database.py -q
176 passed, 2 warnings in 50.47s
```

覆盖：五角色及兼任、分页前授权/搜索、跨人访问、候选无效、空白/重复/额外字段、浏览器写入保护、幂等与冲突、事务中途故障回滚、改派后权限变化、停用负责人接续。真实 PG 覆盖同键同体/异体并发、跨操作者 key、同版本改派竞争，以及创建/改派 × 操作者/候选 × 停用/撤权的八种等锁竞争。

## 边界

任务写入仅保存基础信息；资料上传及执行准入留 Phase20。task.design 只表示当前权限资格，未提供设计执行接口。outbox 仅持久化、published_at 为空。2 条 warning 为已有 Starlette/httpx/anyio 弃用提示。全量国内回归、真实 HTTP/浏览器和独立两阶段审查由主线程统一执行，不在本报告中冒充通过。

冻结0004历史 schema 后单独重跑迁移验证：

```text
python -m pytest tests/test_overseas_tasks_migration.py tests/test_overseas_database.py -q
13 passed in 30.87s
```
