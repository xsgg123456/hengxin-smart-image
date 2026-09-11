# 后端本地开发

更新：2026-09-10。当前阶段进度以 [DEV-PLAN.md](../../DEV-PLAN.md) 为准：Phase 1–10 已验收，Phase 11 技术验证与独立两阶段审查通过、待用户验收，Phase 12–14 未开始。后端包含 FastAPI、PostgreSQL、Redis、MinIO、Celery Worker 和 outbox；已接入开发身份、文件、模板与 Skill、任务执行、返工及下载归档。真实钉钉认证和其余管理接口仍待后续阶段。

## 启动

在仓库根目录执行。依赖 Docker Desktop Linux containers；本机 Python 3.12、uv 用于测试。Dockerfile、Compose、迁移和依赖锁均在 Git 中，同事无需复制本机容器。首次使用将 `hengxin-smart-image/infra/.env.example` 复制为同目录 `.env`，不要覆盖已有配置；将密码占位符替换为独立随机十六进制字符串（数据库 URL 中不需要转义）。`.env` 已忽略，不提交、不打印 `docker compose config` 的完整配置。

本机业务联调保持 `APP_ENV=development`，显式设置 `ENABLE_DEV_IDENTITY=true`；否则业务请求返回 401。默认开发用户为 operator，需要管理员接口时，在创建该开发用户前配置 `DEV_USER_ROLE=super_admin`；已有用户的角色不会因修改环境变量自动更新。开发身份不能用于生产。保持 `ENABLE_TEST_JOBS=false`、`ENABLE_FIXTURE_EXECUTOR=false`；fixture 仅用于隔离测试。

```powershell
docker compose --env-file hengxin-smart-image/infra/.env -f hengxin-smart-image/infra/compose.yaml up -d --build
docker compose --env-file hengxin-smart-image/infra/.env -f hengxin-smart-image/infra/compose.yaml ps --all
Invoke-RestMethod http://127.0.0.1:8008/api/v1/health/ready
Invoke-RestMethod http://127.0.0.1:8008/api/v1/auth/me
```

API：`http://127.0.0.1:8008`，OpenAPI 文档 `/docs`，存活 `/api/v1/health/live`，依赖就绪 `/api/v1/health/ready`。PG 默认端口 55433；原开发机 Windows 曾将 55433–55532 列为保留范围，改用经检查的 55431，新机器需自行检查占用和系统保留范围。MinIO API 59002、控制台 59003；Redis 不向宿主发布端口。所有发布端口只监听本机。可在 `.env` 覆盖端口，不结束未知进程；修改 API_PORT 后同步上述 URL 和前端代理。原型 3007 与前端 3008 保持独立。

基础镜像及构建工具镜像固定 digest，应用镜像由仓库源码构建。Compose 项目 `hengxin-smart-image` 创建自己的 `postgres_data`、`redis_data`、`minio_data`、`skill_data` 四个卷，未指定 external 卷，未挂载宿主目录或 Docker socket。`migrate` 在 PG healthy 后执行 Alembic，成功退出 0 后启动 API/Worker/outbox；它不是常驻服务。常规停止用 `docker compose ... stop`，不要对有数据的开发环境运行 `down --volumes`。更换数据库密码不能自动修改已有数据库用户密码。

新机器的数据库和存储为空：迁移创建表结构，不导入现有图片、模板、任务或 Skill 包。需要业务样例时另行交接脱敏素材和包。本机依赖、密码、数据卷与个人认证不随 Git 同步。

前端在 `hengxin-smart-image/frontend` 执行 `pnpm install --frozen-lockfile` 后，用 `pnpm dev:api` 连接后端，`pnpm dev` 仅模拟预览；版本与命令见 [前端说明](../frontend/README.md)。后端源码复制在镜像内，修改后需重新执行 `up -d --build`，没有源码热重载。当前没有统一的前后端一键启动脚本。

真实 AI 执行需按 [CODEX-EXECUTION.md](CODEX-EXECUTION.md) 单独配置 Linux 原生 Worker、CLI 和认证；默认 Compose Worker 不具备该执行环境。健康检查通过不代表能生成图片，也不代表真实业务 Skill 效果已验收。

## 验证

```powershell
# 锁定依赖；第一次安装使用空 .venv
cd hengxin-smart-image/backend
uv sync --locked
uv run pytest -q
# 返回仓库根目录后，运行隔离容器基础回归
cd ../..
python hengxin-smart-image/infra/verify_phase8.py --build
```

普通 pytest 的数据库集成用例需要独立 `TEST_DATABASE_URL`，Linux 专项也可能在 Windows 跳过；不把跳过当作通过。`verify_phase8.py` 虽沿用阶段名，已用于后续回归：创建独立 Compose 项目、随机端口和四个卷，运行 Linux 容器内后端全套、迁移和任务接口验证，结束仅清理自身测试环境。

需要 Phase 10/11 与浏览器闭环时使用 `python hengxin-smart-image/infra/verify_phase8.py --build --browser --phase10 --phase11`，还需已安装前端依赖、Node.js 及脚本使用的 playwright-cli/Chrome；条件与历史证据见 [Phase 11 验证记录](PHASE11-VALIDATION.md)。`verify_phase5.py` 保留为早期基础队列专项，不代表当前全部业务验证。fixture 回归不替代 [Phase 9 真实 CLI 验证](PHASE9-VALIDATION.md)。上述命令是运行指引，本次文档修订未重新执行业务测试。

## 队列边界

内部良性作业仅计算文本 SHA-256。测试入口默认关闭，仅在 development/test 且显式 `ENABLE_TEST_JOBS=true` 时可用；production 启用则启动失败。开发正常环境保持关闭。请求携带 `Idempotency-Key`；数据库保存 job 与 outbox 后即可返回 202，Worker 由独立进程执行。PG 结果是事实来源，Redis 不是持久任务账本；outbox 在 Worker 提交完成前持续允许重派。

纯计算作业在 PG 行锁事务内执行（最长 30 秒），进程死亡回滚，重复消息最终只提交一次结果。此策略仅验证通用基础，不能套用于有外部收费副作用的 AI 作业；Phase 7 已扩展 Skill 安装处理器，Phase 9 已实现 CLI attempt、租约与不确定状态对账。当前仍返回 501 的是 `/workspace` 及尚未实施的用户管理、统计、监控、系统配置接口；具体方法见 [接口契约](API-CONTRACT.md)。

实现参考：[Celery 幂等任务与确认](https://docs.celeryq.dev/en/main/userguide/tasks.html)、[Docker 启动依赖](https://docs.docker.com/compose/how-tos/startup-order/)、[Pydantic 字段序列化](https://docs.pydantic.dev/latest/concepts/serialization/)。测试结果、跳过和依赖警告按实际运行及对应阶段记录解释，不沿用旧阶段的固定数量作为当前结果。
