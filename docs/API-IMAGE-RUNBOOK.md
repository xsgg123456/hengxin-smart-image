# API 换套图运行说明

此模块在同一平台内独立运行。认证、数据库服务器、MinIO 和 Redis 服务共享；业务表、文件记录/对象前缀、接口、队列、worker 和配置独立。它不调用 Codex CLI，也不在失败后切换 CLI。

## 配置与启动

服务端环境变量见 `hengxin-smart-image/infra/.env.api-image.example`。将实际密钥通过部署环境注入 `API_IMAGE_API_KEY`；不写入前端变量、Git 或日志。默认 `API_IMAGE_ENABLED=false`，配置完成后设为 `true`。

部署前备份数据库，使用当前后端代码构建镜像，并执行 `alembic upgrade head`，新增迁移为 `0015_api_image_edits`。现有部署可叠加 `infra/compose.api-image.yaml`，新增 `api-image-worker` 和 `api-image-outbox`，API 服务读取同一组 API_IMAGE 配置。需保留原部署的环境变量和镜像构建流程；不能只启动新 worker 而遗漏迁移和新版 API。

独立进程命令（在 backend 目录，且已配置数据库/MinIO/认证环境）：

```sh
celery -A app.modules.api_image_edits.celery_app:celery_app worker -Q api_image_edits --concurrency=1 --hostname=api-image@%h --loglevel=WARNING
python -m app.modules.api_image_edits.outbox
```

队列使用 Redis 数据库 1。数据库闸门额外限制模块全局并发为 1，即使误开多个 worker 也不会并发调用。停用模块需同步更新 API、worker、outbox 环境并重启这些进程；已发出的请求可能仍在上游执行，不应立刻手动补发。

## 故障处理

- 连接尚未发出时的失败、429、5xx：初次之外自动重试最多 3 次，默认等待 1/2/4 秒，兼容 Retry-After。
- 单张失败后保留其他成功结果；手动“重试失败项”不会重新生成成功项。
- 认证、额度或模型通道拒绝：暂停通道。修复服务端配置后由超级管理员恢复。
- 读超时、发出后断线、执行进程丢失：标记“不确定”，阻止继续调用。管理员先核实旧请求已结束，再确认处理，之后才允许手动重试。本地幂等不保证上游绝不重复扣费。
- 已拿到图片结果：只重试下载/存储，不重复请求生成。图片通过 HTTPS 域名白名单检查、格式/大小校验后存入本平台 MinIO。域名变化需审查并更新 `API_IMAGE_ALLOWED_RESULT_HOSTS`，不要开放通配域名。

任务详情提供实际请求次数、重试次数和耗时；上游未提供费用时不估算。日志和事件只保留脱敏摘要。

## 本地验证

`infra/compose.api-image-test.yaml` 是独立临时 PostgreSQL、Redis、MinIO 测试资源，使用专用端口和内存数据目录，不连接正式数据库。`infra/verify_api_image_live.py --output <证据目录>` 仅接受 localhost:8009，会提交两张原图和一张素材，产生真实计费请求，并检查重复提交幂等、结果顺序与平台文件下载。密钥只需提供给测试 worker。测试结束清理专用进程和容器，证据保留在 Git 忽略的 output 目录。

前端 demo 模式保留明确的演示标识；正式模式使用真实接口，失败不会回落到示例图片。开发完成并不等于已部署到线上。
