# 生产五并发试运行 · 2026-09-17

用户授权将并发从1调到5，由用户提交任务压测。先确认无在途任务，短暂停止接纳后复查，再同步Worker进程数、API/Worker环境容量和版本化后台配置。保留原配置与审计，检查真实Worker池大小及后台生效值，不自动创建付费任务。

现有任务冻结提交时配置；变更针对之后新提交任务。模型、提示词、Skill及任务隔离保持不变。服务器为7 vCPU、约8GB内存；此前串行运行不能替代五并发容量验收，完成配置不代表压测通过。

## 执行结果

已完成切换，运维单元 `hx-concurrency5-20260917.service` 成功退出。切换前后确认无在途任务，未创建生成任务。

- `/etc/hengxin-smart-image/worker.env` 和 `infra/.env` 中 `GENERATION_CONCURRENCY=5`。
- systemd覆盖配置 `/etc/systemd/system/hengxin-vps-codex-worker.service.d/50-concurrency.conf` 固定 `--concurrency=5`，原始unit文件不改；以后变更进程数应同步调整此覆盖文件。
- `system_settings` 配置版本3，显式并发5；保留其他设置。使用已有运维管理员记录审计，操作名为“生产运维（用户授权）”。
- 真实Celery inspect报告唯一原生Worker、池最大并发5、实际子进程5；API环境容量5，后台有效并发5。
- Worker active、公开ready检查PG/Redis/MinIO均up；空闲时Worker整组约267MiB，服务器可用内存约5.9GiB。
- 应用代码仍为 `skill-name-20260917-79892f0`，未修改模型、Skill、提示词或依赖。

备份在 `/opt/hengxin-backups/concurrency5-20260917/`（原Worker环境、Compose环境、原后台设置），脚本在 `/opt/hengxin-releases/concurrency5-20260917/`。回退需先停止接纳并等待在途任务完成，恢复原环境、移除上述覆盖配置、将后台并发调整为1并记录新审计版本，再重新加载systemd并启动服务。不得在五个任务运行时直接重启Worker。

用户随后提交五个新任务压测；本记录仅验证容量配置生效，不代表五并发生成及稳定性已验收。
