# Phase 5 独立审查

审查日期：2026-09-09。应用 `.agents/skills/code-review/SKILL.md`，fresh 实例从 Stage 1 全量重审后执行 Stage 2。范围依据 `DEV-PLAN.md:200–214`、`Product-Spec.md:114`、`:222`、`:433–437`、`docs/PHASE5-PLAN.md:3–8`。本报告内 backend/frontend/infra/docs 路径相对于 hengxin-smart-image 子目录；根目录需求文档另计。

**结论：Stage 1 PASS；Stage 2 PASS。没有未解决的 HIGH/MEDIUM 问题。** 仅证明 Phase 5 后端基础、目标契约和通用良性测试作业；不把 Phase 6–14 的真实业务、身份、文件、Skill 或 AI 执行计为已完成。

## Stage 1：Spec Compliance — PASS

| 本阶段逐项要求 | 结论及证据 |
|---|---|
| FastAPI、环境配置、统一 /api/v1 | 完整实现。`backend/app/main.py:10–18` 启动配置校验并挂载路由；`backend/app/core/config.py:8–33` 校验必需配置、PG 驱动和环境。独立基础测试通过。 |
| OpenAPI 与 Phase 1–4 前端契约 | 完整实现目标结构。`backend/app/contracts/router.py:8–158` 声明 20 条业务路径、28 个方法，`business.py:18–211`、`management.py:7–193` 对应业务与管理模型。`backend/tests/test_contracts.py:29` 检查受理结构、分页越界，`:81` 起对比 TS 字段；模型及路由已通读。 |
| optional/null 与默认 Skill 三键 | 初审差异已修复。`backend/app/contracts/fields.py:4–11` 缺省省略且拒绝显式 null，`business.py:39–43` 应用；必需 nullable 如 `business.py:157–161` 保留 null。`management.py:154–157` 三键均必需。`backend/tests/test_contracts.py:43–78` 独立执行通过。 |
| 统一错误与内部作业 schema | 第二审查差异已修复。`backend/app/main.py:11–14` 全局 422/500，`backend/app/jobs.py:17–20` 404/409 均声明 ApiErrorBody；`errors.py:9–39` 实际脱敏错误。`tests/test_foundation.py:50–64` 使用真实 app 对照实际 422、请求 ID 和 OpenAPI；独立测试与本机 8008 schema 检查通过。 |
| 业务边界及引导真实性 | 匹配。`backend/app/contracts/router.py:14–17` 统一明确 501 NOT_IMPLEMENTED；`docs/API-CONTRACT.md:5–7` 写明分期与测试能力边界。浏览器统计页、任务页均明确显示模拟提示，没有新增伪生成页面。 |
| 数据库迁移入口 | 完整实现。`backend/migrations/env.py:6–16` 支持迁移；`versions/0001_job_outbox.py:12–36` 建作业/outbox、唯一键、外键和派发索引。真实容器重复迁移通过，见 `docs/PHASE5-VALIDATION.md:18`。 |
| PG、Redis、MinIO 连通及健康检查 | 完整实现。`backend/app/health.py:14–54` 查询迁移表、Redis ping、MinIO 授权 list_buckets；失败 503。独立本机 ready 三项 up；真实 Redis 故障验证见 `infra/verify_phase5.py:109–115`。 |
| 独立 Compose、新命名卷、镜像固定、锁文件 | 完整实现。`infra/compose.yaml:1` 独立项目，`:30`、`:44`、`:54` digest 固定，`:96–99` 三个命名卷；无 external 卷/宿主目录/socket 挂载。`infra/Dockerfile.backend:1–7` 固定基础镜像并 uv locked 安装；`backend/uv.lock:1` 锁记录。容器验证只挂载 3 个随机测试项目卷，`:131–137` 有实际检查。 |
| 作业与 outbox 原子持久化、幂等提交 | 完整实现。`backend/app/jobs.py:47–62` 一个 PG 事务写两表，用唯一键裁决并发、指纹拒绝异内容。`tests/test_queue_integration.py:48–58` 并发同 ID/409/单 outbox；实际 API 返回 202 后无 Worker 重启仍 queued，`infra/verify_phase5.py:78–98`。 |
| 独立派发器及 Worker、可靠恢复 | 完整实现。`backend/app/worker/outbox.py:21–48` 未完成持续重派、失败回滚；`infra/compose.yaml:84–94` 独立进程。实际 Redis 停机仍入 PG，恢复执行；Worker SIGKILL 后恢复，`infra/verify_phase5.py:109–123`。 |
| 重复投递保护 | 完整实现。`backend/app/worker/tasks.py:18–30` PG 行锁下完成 SHA-256、计数和 outbox；`celery_app.py:8–14` late ack/worker lost/json。并发消费和实际重投均 executionCount=1。只适用于无外部副作用计算，`:22–24` 明确不承诺 AI 恰好一次。 |
| 测试入口保护 | 完整实现。`backend/app/core/config.py:12` 默认关闭，`:26–27` production 禁开；`jobs.py:36–39` 与 `worker/tasks.py:15–16` 双端守卫。独立 HTTP 返回 404，生产拒绝及 Worker guard 测试通过。 |
| 干净安装、构建、旧前端、3007 回归 | 匹配。`docs/PHASE5-VALIDATION.md:7` 干净 locked 容器安装；`:36–40` 最新前端 37 测试、构建及两条真实浏览器流程。Phase 5 前端 diff 只有自动生成组件声明一行，无业务 UI 改动；独立查看统计与任务中心完成渲染。 |

部分实现/未实现：本阶段要求无遗留；未来业务路由仅契约、返回 501，是既定阶段边界。Spec 漂移：未发现越界新增业务；测试 SHA-256 作业有 `docs/PHASE5-PLAN.md:6` 明确授权范围。

## Stage 2：Code Quality — PASS

- 结构与类型：`backend/app/models.py:16–44` 使用 SQLAlchemy Mapped；契约使用 Pydantic/Literal/泛型。新增 Python 文件最长 `backend/app/contracts/business.py` 211 行，其次 management 193、router 158，均低于 300。配置、路由、存储、派发、执行分离。扫描没有 Any/any 宽泛类型。`contracts/fields.py:4–11` 的内部 None 缺省已有注释和显式 null 回归。
- 错误与故障：`backend/app/errors.py:33–39` 不回显输入和服务异常；`worker/outbox.py:45–48` 不打印连接字符串；`db/session.py:10–14` 有连接/语句超时。持久化、并发与计算中断的测试使用实际 PG 事务，非只测纯函数，见 `backend/tests/test_queue_integration.py:48–109`。
- **安全扫描通过（本阶段新增范围）**：app/infra 搜 eval、exec、shell=True、innerHTML、前端密钥变量、真实密钥前缀，无命中。SQL 为 ORM 参数绑定或固定语句（`jobs.py:52–59`、`health.py:19–21`）；验证脚本使用 subprocess 参数数组（`infra/verify_phase5.py:33–36`）。`.gitignore:2–5` 与 `hengxin-smart-image/.dockerignore:5` 排除本地凭据，配置密码 repr 隐藏（`core/config.py:13–17`）；`infra/Dockerfile.backend:9–10` 非 root；发布端口限 localhost（`compose.yaml:36`、`:61–62`、`:78`）。测试凭据在 `tests/conftest.py:3–7` 明确为假值。未读取或输出本地真实 .env。
- 测试真实性：`test_foundation.py:50–64` 从真实 app 发非法可达请求并比对 schema；`test_contracts.py:43–78` 能重现先前 null/缺键错误。真实容器脚本观察 Worker 收到延迟作业后才 SIGKILL（`infra/verify_phase5.py:117–123`），检查恢复结果校验和和单次完成（`:70–76`）。本地 PG skips 未冒充通过，主 Agent 隔离容器 16 项无 skip 补足。
- 视觉对比：本审查通过 Chrome 实际打开 3008 调用统计和邻居任务中心，检查完成渲染后的截图；两页同源侧栏、标签栏、蓝色主按钮、圆角白卡片、表格与灰底匹配，无遮挡或空白。对应 `frontend/src/views/hengxin/admin/usage.vue:2–23`、`frontend/src/views/hengxin/tasks/index.vue:1–4`、`frontend/src/views/hengxin/components/Tasks.vue:1`。本阶段无新页面，不存在需要重新对照的新增设计数值；没有把初始异步空白截图当成最终渲染。
- LOW 非阻断：Starlette/httpx、anyio 两项上游弃用警告如下；不影响当前 16 项容器测试通过。后续更新测试依赖时再回归。

## 原始验证证据

本审查独立执行 `.venv/Scripts/python.exe -m pytest -q`，exit 0：

```text
............ssss                                                         [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
12 passed, 4 skipped, 2 warnings in 1.69s
```

独立执行 `.venv/Scripts/python.exe -m compileall -q app migrations tests`：exit 0，原始 stdout/stderr 均为空。

独立本机 HTTP 检查输出：

```text
{"status":"ready","checks":{"postgresql":"up","redis":"up","minio":"up"}}
404 {"code":"NOT_FOUND","message":"接口不存在","requestId":"8f8eba00-d38b-4f67-8bd9-630086773f55"}
```

`/openapi.json` 的 POST test-jobs 404、409、422、500 均实际引用 `#/components/schemas/ApiErrorBody`；202 引用 JobResponse。

以下完整容器验证由主 Agent 在最终镜像执行，本审查读取 `docs/PHASE5-VALIDATION.md:14–28` 并核查脚本，不冒称独立再次执行：

```text
PASS PG/Redis/MinIO ready
PASS repeat migration
PASS accepted job survives API/outbox restart without Worker
PASS real Celery execution
PASS duplicate messages preserve single completion
PASS Redis outage durable recovery
PASS Worker received delayed job
PASS Worker crash rollback and recovery
16 passed, 2 warnings in 2.47s
PASS only three isolated test volumes mounted
PHASE5 INTEGRATION PASS
```

主 Agent 最终前端验证：37 pass、0 fail、0 skipped（1553.7707ms）；vue-tsc 零错误，Vite `built in 31.99s`，exit 0。`create-flow.js` 和 `version-flow.js` PASS、pageerror=0；3007/3008 HTTP 200。原始完整构建日志保留在主 Agent 工具输出，记录索引 `docs/PHASE5-VALIDATION.md:36–40`。
