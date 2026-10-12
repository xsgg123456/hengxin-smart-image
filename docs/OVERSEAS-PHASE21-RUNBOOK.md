# 海外执行运行说明

## 本地/部署配置

沿用 `infra/.env.overseas.example` 的独立数据库、Redis、MinIO及三个目录；执行服务仅加载 `OVERSEAS_` 配置，`HX_BUSINESS_CONTEXT=overseas`。先迁移 `alembic -c alembic.overseas.ini upgrade head` 到0006，种下独立门闩，缺门闩失败关闭。

CLI执行显式配置 `OVERSEAS_ENABLE_CODEX_EXECUTOR=true`、`OVERSEAS_CODEX_BINARY`、`OVERSEAS_CODEX_AUTH_FILE`、`OVERSEAS_CODEX_BWRAP_BINARY`、`OVERSEAS_CODEX_EXECUTION_ROOT`，版本须与 `OVERSEAS_CODEX_VERSION` 一致。认证文件及会话目录不能使用国内可写目录；同账号只可复制认证材料，作业home始终隔离。CLI生产沙箱要求Linux Bubblewrap，Windows只用于开发/测试编排。

启动独立服务：

```
celery -A app.overseas.execution.worker:celery_app worker --pool=prefork --concurrency=5 --queues=overseas.cli
python -m app.overseas.execution.outbox
```

示例service在 `infra/hengxin-overseas-{worker,outbox}.service`。同一节点的worker/outbox须共享海外执行目录、相同PID视图及 `OVERSEAS_WORKER_NODE_NAME`（跨节点不可重名）。门闩限制所有worker总数，不因增加worker突破5。queued由outbox周期投递；消息丢失可复发，领取不重复执行。

## 取消与恢复

页面停止操作受设计权限和作业版本校验，运行中变为cancelling，不能提前释放名额。租约过期进入uncertain，仍占名额，不能直接重投启动。维护进程仅核实本节点的PID、启动时刻、系统boot身份；确认旧执行退出后失败/取消结束。缺身份证据或无法读取进程时保留uncertain，须人工核实主机，不能以过期时间猜测退出。

磁盘剩余低于512MiB时暂停领取；`overseas_execution_gate.paused`也可暂停接纳。阈值不是整机资源配额，CPU/内存/存储配额仍需部署前核定。任务等待人工方案确认/审核时无活动作业，不占槽。

Phase21只交付执行底座与真实状态查询，业务协议在Phase22/23注册；未知协议失败关闭。不得用本地替身结果声称真实模型效果已验收。

## 重复验证

`python hengxin-smart-image/infra/overseas/regression.py` 创建本次专用PG/Redis及Linux测试容器，结束清理；挂载源码只读，测试数据在临时schema/库中，保留已有容器。`python hengxin-smart-image/infra/identity-test/run.py --phase21` 验证三API、两库、独立存储及真实Redis投递/授权/取消/游标续传。若镜像不是默认测试镜像，设置 `IDENTITY_TEST_IMAGE=hengxin-smart-image-backend:phase20`。
