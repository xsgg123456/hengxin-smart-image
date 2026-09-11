# Codex 执行环境

Phase 9 已验收；当前整体进度以 [DEV-PLAN.md](../../DEV-PLAN.md) 为准，实机证据见 [Phase 9 验证记录](PHASE9-VALIDATION.md)。真实执行采用 Linux 原生 Celery Worker，API/PG/Redis/MinIO 可保持 Compose 运行。选择原生 Worker 是为了使用已部署的 CLI 与受控 Bubblewrap，而非给通用 Worker 容器特权或 Docker socket。以下已部署配置描述原验证服务器，新机器仍需单独安装和验证，拉取仓库不会复制服务器环境或认证。

## 配置

Worker环境配置 ENABLE_CODEX_EXECUTOR=true、ENABLE_FIXTURE_EXECUTOR=false；CODEX_BINARY 指向已核实0.153.4可执行文件，CODEX_AUTH_FILE指向专用身份认证文件，CODEX_EXECUTION_ROOT为专用可写目录。不要把认证复制到仓库或前端。CODEX_BWRAP_BINARY默认/opt/hengxin-runtime/bwrap，必须为受信、root拥有的辅助程序。

CODEX_TIMEOUT_SECONDS=3600、QUEUE_VISIBILITY_SECONDS=4200、GENERATION_CONCURRENCY=1；失败自动重跑0。节点名 WORKER_NODE_NAME 必须唯一标识执行主机，不可在不同服务器复用；恢复过程只处理该节点记录。

原生Worker通过专用venv的 `celery -A app.worker.celery_app:celery_app worker --concurrency=1` 启动；其环境变量指向仅本机暴露的专用PG、Redis、MinIO。API和outbox使用同样executor接纳配置，但无需访问认证文件。真实模式时不要同时让缺少CLI的开发Worker消费相同队列。

## 隔离与产物

每任务home持久化；每轮work和不挂载给模型的control分开。外层Bubblewrap仅挂载该任务home、本轮work、固定CLI及同一发行版的codex-code-mode-host辅助程序，以及只读系统运行时；/proc为独立PID命名空间，/tmp独立，环境变量重建，不传递业务存储凭据。CLI内层仍使用workspace-write。认证为任务私有副本，不共享可写CODEX_HOME。

原生图片在任务home/.codex/generated_images/<sessionId>/。开始前保存哈希快照；单张仅接受唯一新增文件，多张必须有本轮slot清单。文件解码、数量、链接、目录边界和历史完整性通过后才能上传，并再次通过PG认领凭证发布。

进程退出后不会销毁会话。续接只接受已绑定ID，材料缺失则失败。失联/过期不重跑；本机核实精确进程身份已消失后轮换认领凭证，恢复收集完整且来源可信的本轮结果。明确失败则结束，证据不足继续待核实并保留材料；取消不发布图片，旧凭证始终不能发布。

## Ubuntu 24.04 专用许可

系统全局 kernel.apparmor_restrict_unprivileged_userns 保持1。服务器已在用户明确批准后安装精确路径 /opt/hengxin-runtime/bwrap 的userns许可；辅助程序root拥有，不改变全局限制。CLI已有0.153.4精确二进制规则。升级路径变化时需重新审阅，不自动扩大到全目录通配。

规则由root维护，语法如下：

```
abi <abi/4.0>,
include <tunables/global>
profile hengxin-task-isolation /opt/hengxin-runtime/bwrap flags=(unconfined) {
  userns,
}
```

这里只启用辅助程序所需的命名空间能力；任务可见文件边界由外层挂载白名单定义。不能将此配置或CLI自身沙箱等同于已通过全部隔离验收。

## 验证入口

`infra/verify_phase9_sandbox.py`验证两任务真实会话与跨任务读写；执行时需让workspace.py在Python导入路径中。`infra/verify_phase9_live.py`创建独立临时服务与数据，验证真实HTTP到图片回传；不会部署生产环境。验证记录汇总在PHASE9-VALIDATION.md。
