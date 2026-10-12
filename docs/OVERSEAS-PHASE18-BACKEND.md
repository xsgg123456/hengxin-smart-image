# Phase 18.2 成员后端本地验证

2026-10-12。范围仅本地开发；本报告不替代主线程全量回归、真实浏览器和独立两阶段审查。

## 实现与复用

- `backend/app/overseas/members/` 增加分页检索、详情、严格 PATCH、最近100条审计与显式初始化命令；复用既有海外成员/多角色/会话、统一身份绑定、`browser_request`、SQLAlchemy事务和主线程的 `permissions`，未新增依赖。
- 所有授权写入与初始化共用 PostgreSQL `pg_advisory_xact_lock(7318041802)`；锁后刷新操作者状态并读取当前角色再次授权。最后有效管理员检查、角色变更、版本递增、停用撤销全部海外会话、审计插入在同一事务。
- 姓名/部门只读；目标按UUID定位。检索支持姓名/部门并转义 LIKE 通配符；分页、状态、五角色参数校验，active至少一角色、角色去重、未知字段和非整数版本拒绝。
- 海外0002冻结历史表定义，避免后续模型字段提前进入旧迁移。0003新增 `version`（已有成员默认1）和 `overseas_member_audits`，兼容在线/离线SQL；未改国内schema。
- 新增配置 `OVERSEAS_BOOTSTRAP_ADMIN_CORP_ID` 和 `OVERSEAS_BOOTSTRAP_ADMIN_USER_IDS`，例子与Compose透传已补，默认空值。

## 一次初始化

部署前用户明确企业及provider用户ID，逗号分隔。配置值去首尾空白并去重；不能用姓名匹配。目标必须先通过统一身份登记为海外成员，命令不创建身份。

```text
HX_BUSINESS_CONTEXT=overseas
OVERSEAS_BOOTSTRAP_ADMIN_CORP_ID=<已核实企业>
OVERSEAS_BOOTSTRAP_ADMIN_USER_IDS=<已登记provider用户ID列表>
python -m app.overseas.members.bootstrap
```

上述环境展示为跨平台配置说明，不是PowerShell赋值语法。资源配置仍须完整使用海外专属值。

配置空、身份缺失、企业不匹配、已有有效管理员均拒绝。同一初始化审计目标仍全部有效时可幂等返回0；已降权的初始化管理员不能靠重跑命令恢复。命令不在启动或登录调用，不读取国内管理员配置，初始化审计actorId为空、action为bootstrap。

## 当场验证

使用唯一临时容器 `hx-p18-members-pg-20261012`（postgres:17-alpine），仅本机随机端口59545，创建 `p18_test`。测试各自使用随机schema/数据库并清理，不使用生产资源。PG fixture强制驱动 `postgresql+psycopg` 且库名以 `_test` 结尾。

```powershell
docker run --rm --mount 'type=bind,source=D:/Work_Project/hengxin-smart-image/hengxin-smart-image/backend,target=/src,readonly' -w /src -e PYTHONDONTWRITEBYTECODE=1 -e TEST_OVERSEAS_MEMBERS_DATABASE_URL=postgresql+psycopg://postgres:p18test@host.docker.internal:59545/p18_test -e TEST_OVERSEAS_DATABASE_URL=postgresql+psycopg://postgres:p18test@host.docker.internal:59545/p18_test hx-management-test:local /app/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_overseas_members.py tests/test_overseas_members_bootstrap.py tests/test_overseas_members_postgres.py tests/test_overseas_members_migration.py tests/test_overseas_database.py tests/test_overseas_auth.py tests/test_overseas_configuration.py
```

最终输出：`92 passed, 2 warnings in 31.38s`，退出0、无跳过。2条为既有Starlette/httpx/anyio弃用提示。命令凭据仅该一次性测试容器使用。

覆盖：

- 接口查询、分页、同名身份、详情404、pending激活、五角色校验/多选去重、普通/无角色拒绝、CSRF/Origin拒绝、409、审计上限/顺序与插入失败回滚。
- 停用两个海外会话全部撤销且token解析失败；角色撤销后原管理员会话立即403，仍可读取普通成员身份。
- **真实PG 6项并发**：两个管理员同时自行降权、相互降权；两操作者同版本编辑仅一次提交；已读取旧身份的等待者在被撤权/停用后均403（`pg_locks`确认实际阻塞）；两个初始化竞争只成功一次。
- **真实PG迁移**：0002不含version，写入pending/active既有成员及designer角色，升级0003后状态/角色原样保留且version=1；同时运行既有新建、重复迁移、拒绝国内库、国内数据不变及离线SQL回归。
- Bootstrap空配置、缺失目标、跨企业、同名无法替代、已有管理员拒绝、首次授权、幂等与禁止重提权。

尚未在本子任务验证：真实钉钉、生产权限/迁移/部署；全项目完整测试和最终审查由主线程执行。没有生产写入、收费调用、Git提交或子Agent派生。
