# 海外 Phase 16 独立两阶段审查

- 日期：2026-10-12；角色：独立 code-reviewer；依据 `.agents/skills/code-review/SKILL.md`。
- candidateId：`2b819922af2b0630eee81560cbb10b047a297121abbc956f2395d6ea91f1cae8`。
- **Stage 1：PASS；Stage 2：PASS。HIGH 0，MEDIUM 0，LOW 1（非阻断测试增强）。**
- 审查期间只读取代码、运行专项测试、写本报告；没有修复、提交或写 `.needs-review`。开始及收尾 `review-status` 的 currentId 均匹配上述 candidateId。

## 范围与源文档

源文档：`DEV-PLAN.md:64` 的 Phase 16、`Product-Spec.md:956` 正式海外章节及其引用背景、`docs/OVERSEAS-PHASE16-CONTRACT.md:1`、`docs/OVERSEAS-DATABASE-CONTRACT.md:1`、`docs/OVERSEAS-LOCAL-RUNBOOK.md:1`。

下文 `backend/`、`infra/` 均相对于仓库内 `hengxin-smart-image/`。本次完整审查以下 22 个代码/配置文件（也是 review-status 相对于既有批准快照的变化清单）：

- `backend/app/core/config.py`、`backend/app/main.py`、`backend/app/storage/minio_store.py`、`backend/migrations/env.py`。
- `backend/app/overseas/__init__.py`、`config.py`、`db.py`、`health.py`、`main.py`。
- `backend/alembic.overseas.ini`、`backend/migrations/overseas/env.py`、`script.py.mako`、`versions/overseas_0001.py`。
- `backend/tests/test_overseas_configuration.py`、`test_overseas_database.py`、`test_overseas_health.py`。
- `infra/.env.overseas.example`、`infra/compose.overseas.yaml`、`infra/overseas/bootstrap-postgres.sh`、`bootstrap-minio.sh`、`probe_resources.py`、`verify_resources.py`。

工作树包含先前前端预览及 `.agents/skills/dev-builder/SKILL.md` 等未提交变更；不属于本次审查范围，不因本报告重新获得批准。正式认证、五角色、任务、资料及 CLI 调度属于 Phase 17–25，本次不以未实现这些能力判定缺陷。当前只验配置并发上限，不验运行作业总并发。无新增或修改产品页面，设计数值与邻居页面渲染对比不适用。

## Stage 1：Spec Compliance

| 条目 | 结论 | 代码与验证证据 |
|---|---|---|
| 16.1 显式选择海外上下文；默认国内兼容 | 完整实现 | `backend/app/core/config.py:90` 校验选择器；`:98` 分支加载。`tests/test_overseas_configuration.py:49`、`:67` 覆盖默认与非法值；独立专项通过。 |
| 16.1 仅 OVERSEAS_，不加载国内 dotenv/补缺 | 完整实现 | `backend/app/overseas/config.py:8` 设置前缀和 env_file=None；`:13` 必需资源；`:32` 拒绝空白。`tests/test_overseas_configuration.py:75` 逐字段以国内环境及带海外前缀的国内 dotenv 尝试补缺，均拒绝。 |
| 16.1 海外并发配置 1–5、危险开关默认关闭 | 完整实现 | `backend/app/overseas/config.py:22`；`core/config.py:15` 默认关闭；`infra/compose.overseas.yaml:23` 固定5并关闭执行/测试/清理。`tests/test_overseas_configuration.py:90`、`:113` 验证继承国内开关不生效和越界拒绝。 |
| 16.1 双入口互斥、路由不混挂 | 完整实现 | `backend/app/main.py:7`；`app/overseas/main.py:8`、`:19`。`tests/test_overseas_configuration.py:129`、`:143` 验证错误入口拒绝、仅两个海外业务路由、国内路径404。 |
| 16.1 复用设置、错误及 HTTP 计时 | 完整实现 | `backend/app/overseas/config.py:5` 直接继承；`main.py:5`、`:15` 复用中间件。`tests/test_overseas_configuration.py:143` 验证请求ID、Server-Timing和脱敏500。没有复制工程。 |
| 16.2 独立元数据、共享连接池、空业务表 | 完整实现 | `backend/app/overseas/db.py:6`、`:13`；`migrations/overseas/versions/overseas_0001.py:9` 无业务DDL。`tests/test_overseas_database.py:48`、`:60` 验证不导入国内模型和同一池函数。 |
| 16.2 独立迁移树、版本表与在线事务 | 完整实现 | `backend/alembic.overseas.ini:2`；`app/overseas/db.py:9`；`migrations/overseas/env.py:23` 在同一事务内校验和迁移。`tests/test_overseas_database.py:67`、`:147` 验证首次/重复升级均只有 overseas_0001 版本记录。 |
| 16.2 双向错库防护，国内库保持不变 | 完整实现 | `backend/app/overseas/db.py:17`、`:22` 校验上下文、public、所有非系统schema及表/视图；`backend/migrations/env.py:6`、`:35` 拒绝海外上下文与标记。真实PG专项 `tests/test_overseas_database.py:147`、`:177` 验证拒绝且快照不变。 |
| 16.2 离线SQL与测试数据库安全边界 | 完整实现 | `backend/migrations/overseas/env.py:14` 仅生成海外SQL；`tests/test_overseas_database.py:100` 验证只有一张版本表；`:111` 仅接受显式 PostgreSQL *_test，随机建库并只清理自建库。在线隔离能力未冒充为离线已验证。 |
| 16.3 同机独立 PG/Redis/MinIO/网络/卷 | 完整实现 | `infra/compose.overseas.yaml:31`、`:56`、`:68`、`:132` 独立资源，资源不发布端口，`:116` API仅localhost。`infra/overseas/verify_resources.py:76` 实查容器网络和挂载归属，资源日志通过。 |
| 16.3 管理、迁移、运行凭据最小权限 | 完整实现 | `infra/overseas/bootstrap-postgres.sh:13` 非超级用户；`:19` 撤销PUBLIC及限定应用权限；`:30` 与 `backend/migrations/overseas/env.py:33` 保持版本表只读。Compose `:94` 仅迁移使用owner；`probe_resources.py:45` 实测DML允许、DDL/临时表/schema/版本写拒绝，`:35` 双向PG认证拒绝。 |
| 16.3 私有桶与独立认证 Redis | 完整实现 | `infra/overseas/bootstrap-minio.sh:11` 无匿名策略，`:15` 桶级权限；Compose `:60` Redis密码认证。`probe_resources.py:67` 起验证隐藏桶、禁止创建桶、双向get/put拒绝及匿名拒绝；`:96` Redis无密码/跨业务密码拒绝。 |
| 16.3 非root与独立可写目录，不持有管理密码 | 完整实现 | `infra/compose.overseas.yaml:102` 无网络初始化海外卷，`:111` API使用既有Dockerfile非root用户；`verify_resources.py:76`、`:116` 实际检查用户、管理密码不在API环境、三个目录可写。未启动国内Worker。 |
| 16.3 live / ready 真实语义及精确版本 | 完整实现 | `backend/app/overseas/health.py:21` 查询唯一正确版本；`:32` Redis ping；`:39` 私有MinIO检查；`:49` live不访问依赖。`tests/test_overseas_health.py:33`、`:47`、`:55`、`:68`；资源脚本 `verify_resources.py:130` 对三个真实依赖逐个停服，ready503/live200，恢复ready200。 |
| 16.3 只读探测、有限超时、响应不泄漏 | 完整实现 | `backend/app/overseas/health.py:22`、`:32`、`:37` 设置超时，`:40` 禁止建桶，`:58` 仅状态与名称；`backend/app/storage/minio_store.py:22` 注入客户端、`:54` 禁止建桶分支。`tests/test_overseas_health.py:55`、`:75`、`:84` 验证脱敏/只读/公共策略拒绝。 |
| 16.3 本地说明与隔离验收 | 完整实现 | `docs/OVERSEAS-LOCAL-RUNBOOK.md:1` 写明独立启动、初始化链、权限及生产边界；`infra/overseas/verify_resources.py:43` 随机凭据和唯一项目，`:142` 清理自建资源。计划列出的 test_overseas_resources.py 由此真实Compose脚本承担，不是缺失测试能力。 |

部分实现：无（以本 Phase 合同为界）。未实现：无本 Phase 应交付项。Spec 漂移：未发现；新增接口只有两条健康路由，新增数据库对象只有版本表（`app/overseas/main.py:19`，`tests/test_overseas_database.py:157`）。

## Stage 2：Code Quality

- **质量通过**：新增 Python/脚本文件1–197行，最大 `backend/tests/test_overseas_database.py:197`，均低于300行；Compose 140行。配置、元数据、健康检查、初始化与验证职责分开；复用关系见 Stage 1。公共MinIO参数保持默认行为，`backend/app/storage/minio_store.py:22`、`:30`；原调用路径专项一并通过。`git diff --check -- hengxin-smart-image/backend` 无输出、退出0。
- **安全扫描通过**：扫描实现及脚本未发现硬编码真实密钥、eval、前端暴露密钥或动态执行输入。初始化 SQL 使用 psql 标识符/值引用（`infra/overseas/bootstrap-postgres.sh:17`、`:19`）；策略桶名先限制字符（`bootstrap-minio.sh:8`）。测试动态库名由固定前缀与uuid生成（`tests/test_overseas_database.py:120`）；测试凭据随机生成并在诊断中替换（`verify_resources.py:21`、`:46`）。绝对目录为明确海外容器路径，不挂载国内卷。
- **测试真实性通过**：mock用于精确故障/脱敏/禁止写入断言；真实PG专项执行实际 Alembic，并比较国内库前后表和数据；Compose脚本执行真实镜像，不覆盖其源码。跨资源失败要求明确认证/权限错误，不能把连接不通算隔离成功（`probe_resources.py:13`、`:35`）。检查实际应用UID/挂载/凭据与目录写入，覆盖生产运行方式；国内对象是一次性独立替身，未宣称访问国内生产。
- **LOW-1，可选补强**：`backend/app/overseas/db.py:25`、`:31`、`:38` 的非public默认schema、视图、物化视图拒绝已有实现；`backend/tests/test_overseas_database.py:177` 真实PG用例目前只构造未知表和额外schema表。可增加这些分支的集成案例，避免未来回归。本次没有观察到实现错误，不阻断通过。
- **视觉对比**：不适用，本范围无UI文件；本报告不替代既有前端审查。前端250测试仅作为共享项目回归旁证。

## 验证与编译原始结果

审查员亲自重跑只读挂载源码的隔离容器，使用 `--init`，显式连接本轮可销毁 PostgreSQL 测试实例；命令核心：

```text
/app/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_overseas_configuration.py tests/test_overseas_health.py tests/test_overseas_database.py tests/test_minio_policy_revalidation.py tests/test_delivery_storage.py tests/test_db_pool_budget.py
77 passed, 2 warnings in 27.89s
```

退出0；77项包含全部12个数据库专项，没有跳过数据库。两项警告来自既有 Starlette httpx / AnyIO deprecated API，不是失败。

读取并核对最终完整后端日志 `output/overseas-phase16-backend-final.log:1`，末行原始输出：

```text
................................................................         [100%]
1703 passed, 17 skipped, 15 warnings in 304.38s (0:05:04)
```

这是使用 `--init` 的最终完整回归；旧的PID1/subreaper失败运行不作为批准证据。17项跳过不计作已验证能力，海外数据库路径由本次独立77项实际覆盖。

构建日志 `output/overseas-phase16-build.log` 原始末段（复用 `infra/Dockerfile.backend:1`，未新增依赖）：

```text
#14 naming to docker.io/library/hengxin-smart-image-backend:overseas-phase16 done
#14 unpacking to docker.io/library/hengxin-smart-image-backend:overseas-phase16
#14 unpacking to docker.io/library/hengxin-smart-image-backend:overseas-phase16 1.5s done
#14 DONE 6.5s
```

真实资源验证日志 `output/overseas-phase16-resources.log:1` 原始关键输出：

```text
PASS: overseas non-root API, private mounts/network, no admin secrets, writable roots; bootstrap/migration idempotency and readiness
PASS: domestic non-root API, private mounts/network, no admin secrets, writable roots; bootstrap/migration idempotency and readiness
PASS: bidirectional PostgreSQL/MinIO/Redis credential isolation; DML allowed, DDL denied; private buckets
PASS: redis failure => ready 503, live 200; recovery => ready 200
PASS: minio failure => ready 503, live 200; recovery => ready 200
PASS: postgresql failure => ready 503, live 200; recovery => ready 200
PASS: Phase 16 disposable real-resource verification
Cleaned disposable projects: hx-overseas-p16-b450d4d5fd
```

前端日志 `output/overseas-phase16-frontend-tests.log` 原始计数：

```text
ℹ tests 250
ℹ pass 250
ℹ fail 0
ℹ skipped 0
```

未实测生产、真实钉钉或收费CLI。批准仅对应上述 candidateId 的本次范围；由主 Agent 用 review-approve 登记同一快照及本报告，两阶段PASS不能覆盖之后的代码变化。
