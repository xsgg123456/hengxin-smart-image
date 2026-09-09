# 后端本地开发

Phase 5 提供 FastAPI、PostgreSQL、Redis、MinIO、独立 Celery Worker 和 outbox 派发器。业务页面继续在 3008 使用显式 mock 预览；真实身份/文件从 Phase 6 开始，图片执行从 Phase 9 接入。

## 启动

在仓库根目录执行。依赖 Docker Desktop Linux containers；本机 Python 3.12、uv 用于测试。先将 `hengxin-smart-image/infra/.env.example` 复制为同目录 `.env`，将密码占位符替换为独立随机十六进制字符串（数据库 URL 中不需要转义）。`.env` 已忽略，不提交、不打印 `docker compose config` 的完整配置。当前机器已生成独立本地配置。

```powershell
docker compose --env-file hengxin-smart-image/infra/.env -f hengxin-smart-image/infra/compose.yaml up -d --build
docker compose --env-file hengxin-smart-image/infra/.env -f hengxin-smart-image/infra/compose.yaml ps
```

API：`http://127.0.0.1:8008`，OpenAPI 文档 `/docs`，存活 `/api/v1/health/live`，依赖就绪 `/api/v1/health/ready`。PG 默认端口 55433；当前 Windows 将 55433–55532 列为保留范围，本机 `.env` 改用已检查的 55431。MinIO API 59002、控制台 59003；Redis 不向宿主发布端口。所有发布端口只监听本机。启动前检查占用及 Windows 保留范围，不结束未知进程；可在 `.env` 覆盖端口。原型 3007 与前端 3008 保持独立。

镜像全部固定 digest。Compose 项目 `hengxin-smart-image` 创建自己的 `postgres_data`、`redis_data`、`minio_data` 卷，未指定 external 卷，未挂载宿主目录或 Docker socket。`migrate` 在 PG healthy 后执行 Alembic，再启动 API/Worker/outbox。常规停止用 `docker compose ... stop`，不要对有数据的开发环境运行 `down --volumes`。更换数据库密码不能自动修改已有数据库用户密码。

## 验证

```powershell
# 锁定依赖；第一次安装使用空 .venv
cd hengxin-smart-image/backend
uv sync --locked
uv run pytest -q
# 返回仓库根目录后，运行真实容器测试
cd ../..
python hengxin-smart-image/infra/verify_phase5.py
```

普通 pytest 不连接本地业务库：4 个 PG 用例无 `TEST_DATABASE_URL` 时跳过。容器验证脚本创建随机 `hx-phase5-test-*` 项目、随机本机端口及独立卷，并在其内部创建 `hengxin_test`，运行所有用例（包括跨语言契约检查）。结束仅删除该测试项目的卷。脚本验证：202 入库、幂等冲突、无 Worker 时持久排队、API/outbox 重启、重复投递、Redis 故障、Worker SIGKILL 后恢复及卷边界。脚本使用已构建镜像，改代码后先重新 build。

## 队列边界

内部良性作业仅计算文本 SHA-256。测试入口默认关闭，仅在 development/test 且显式 `ENABLE_TEST_JOBS=true` 时可用；production 启用则启动失败。开发正常环境保持关闭。请求携带 `Idempotency-Key`；数据库保存 job 与 outbox 后即可返回 202，Worker 由独立进程执行。PG 结果是事实来源，Redis 不是持久任务账本；outbox 在 Worker 提交完成前持续允许重派。

纯计算作业在 PG 行锁事务内执行（最长 30 秒），进程死亡回滚，重复消息最终只提交一次结果。此策略仅验证通用基础，不能套用于有外部收费副作用的 AI 作业；Phase 7 扩展 Skill 安装处理器，Phase 9 实现 CLI attempt、租约与不确定状态对账。当前尚不提供图片生成、真实钉钉登录、用户归属或文件存储业务接口。OpenAPI 的业务接口已标记 planned-business-contracts，调用明确 501。

实现参考：[Celery 幂等任务与确认](https://docs.celeryq.dev/en/main/userguide/tasks.html)、[Docker 启动依赖](https://docs.docker.com/compose/how-tos/startup-order/)、[Pydantic 字段序列化](https://docs.pydantic.dev/latest/concepts/serialization/)。依赖锁中测试工具包含两项上游弃用警告，测试当前仍通过；未将这些警告记作业务失败。
