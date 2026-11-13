# 国内工作台绑定基础任务复审（2026-11-12）

- candidateId：`3c098d823291433d4c4f9d36c3820c0fa58879525ec26852a6c10e34f5f8e234`。
- 审查范围：`hengxin-smart-image/backend/app/modules/domestic_studio/{policy.py,models.py,bindings.py}`、`backend/migrations/versions/0033_domestic_studio_bindings.py`、`backend/migrations/env.py` 新增导入及 `backend/tests/test_domestic_studio_{policy,bindings,migration}.py`。对照 `Product-Spec.md:1-11` 中五工作台、可信 Skill 绑定、未绑定拒绝和产品替换不可归档；使用 `backend/app/db/session.py` 和现有海外冻结代码作为接口及环境参考。国内路由、身份授权、真实 Skill 目录、执行链、成品库和 UI 属后续任务，不计作本次基础任务缺项；本报告不代表完整产品验收。
- **Stage 1：FAIL，发现一个 HIGH，影响取决于 PostgreSQL 事务隔离级别。** 实际目标库隔离级别未实查，不声称现有生产环境已发生此缺陷。
- **Stage 2：未执行完整阶段，不作 PASS。** 发现 HIGH 之前曾做一次范围内安全关键词预查，未完成质量、安全及视觉审查；不得据此登记两阶段通过。
- 开始审查和撰写本报告前的 `review-status` 当前代码快照均为上述 candidateId。普通 Markdown 报告不属于代码快照；审查结论只对该 candidateId 有效。

## Stage 1 缺陷

### HIGH：REPEATABLE READ 下取得门锁后仍可冻结旧绑定

Spec 原文要求“服务端在发送时以当前入口的实际绑定为准”（`Product-Spec.md:9`）。`bindings.py:18-20` 对 `execution_gate` 的固定行执行 `SELECT ... FOR UPDATE`，但并不更新该行；`bindings.py:64-72` 随后才查询并刷新 `WorkspaceBinding`。应用创建引擎时没有指定事务隔离级别（`app/db/session.py:40-47,64-65`），本范围函数也没有检查或限制隔离级别。

已在全新隔离的 PostgreSQL 18.6 临时实例使用两个独立 `psql` 连接，按代码的 SQL 顺序复现：事务 A 在 REPEATABLE READ 下先读到 `old` 建立快照；事务 B 取得 gate，换绑为 `new` 并提交；A 随后取得 gate 再查询绑定，得到的仍是 `old`，第三条新连接看到 `new`。旧快照可先由同一请求的任何数据库读取建立；`populate_existing=True` 只能刷新 ORM 对象，不能改变 PostgreSQL 事务快照。实际输出和 SQL 序列见下方“验证与原始输出”。

同实例 READ COMMITTED 下相同交错能看到 `new`；持锁时另一个独立连接的 gate 查询发生锁超时，证明测试确实具有锁竞争。按照同一隔离规则，可推断 `assert_unbound`（`bindings.py:55-61`）在旧快照未见新绑定时也可能错误放行，但该衍生场景没有单独执行完整应用复现。PostgreSQL 对不同隔离级别的快照和锁行为见[官方事务隔离文档](https://www.postgresql.org/docs/current/transaction-iso.html)。

影响条件是连接使用 REPEATABLE READ 等不满足该算法假设的隔离级别且事务快照先于换绑提交；本次没有连接生产库验证实际设置。应明确并强制受支持的隔离级别或改变并发协议，使上述交错无法返回旧绑定，再以真实应用函数和独立 PostgreSQL 连接覆盖发送、绑定、解绑/停用与回滚场景。不可把 READ COMMITTED 默认值或 SQLite 测试当作无条件保证。

## 范围内 Spec 与上轮缺陷逐项对照

| 条目 | 结论与证据 |
| --- | --- |
| 五个工作台及无默认绑定 | **基础策略已实现。** `policy.py:13-25` 恰有 `camera/case/product/scene/phone`，未知入口拒绝；`0033_domestic_studio_bindings.py:19-26` 不预置绑定；`test_domestic_studio_policy.py:21-25,28-37` 和 `test_domestic_studio_migration.py:13-24` 覆盖相关单元行为。实际菜单、会话及未绑定提示 UI 不在本次范围。 |
| 仅新品可归档 | **策略层已实现，完整服务端防绕过尚未验证。** `policy.py:13-18,28-31` 允许 `camera/case`，拒绝 `product/scene/phone`；`test_domestic_studio_policy.py:9-18` 验证返回。未来归档路由仍须实际调用该策略并做 HTTP 防绕过测试。 |
| 当前可信绑定与未绑定拒绝 | **有条件 FAIL。** `bindings.py:67-72` 在门锁下读取绑定，`policy.py:45-53` 拒绝非 `None` 客户端 Skill、空绑定、缺失或不匹配的冻结身份；但 REPEATABLE READ 实际可读到旧绑定，见 HIGH。`test_domestic_studio_policy.py:40-63` 验证了拒绝分支。 |
| 绑定到启用的真实 Skill | **仅完成委托边界。** `bindings.py:29-40` 调用 `verify_enabled`，`policy.py:50-53` 依赖外部 freezer 并检查结果身份；测试使用回调替身（`test_domestic_studio_bindings.py:34-53`、`test_domestic_studio_policy.py:66-72`）。国内真实 catalog 未接线，不能证明已停用或伪造安装的真实对象必然拒绝。 |
| 已有请求不被后续换绑改写 | **本范围未验证最终行为。** `bindings.py:64-66` 要求调用方在执行记录中提交快照，`policy.py:40-44` 将不可变快照职责交给调用方；当前没有国内执行记录、真实文件副本及冻结 Job 负载测试。测试替身只返回字典（`test_domestic_studio_bindings.py:34-40`），不能证明生产持久快照。 |
| 绑定的 Skill 不可停用或删除 | **仅完成保护原语。** `bindings.py:55-61` 提供同事务锁定与绑定检查，`test_domestic_studio_bindings.py:63-70` 验证同步调用。真实停用、删除、更新和权限入口尚未接线；RR 下保护读取还有上述条件风险。 |
| 上轮 identity map 陈旧值 | **在 READ COMMITTED 假设和 SQLite 测试范围内已修复。** `bindings.py:23-26,41-52,68-72` 对查询使用 `populate_existing=True`；现有 `test_domestic_studio_bindings.py:87-111` 覆盖旧值换绑与保存。另用 SQLite 文件数据库及两条独立物理连接实测旧对象刷新、新绑定冻结、解绑后 409 与重新插入，输出见下。此测试不验证 PostgreSQL 锁或快照。 |
| 上轮既有同名表兼容检查不足 | **当前策略已拒绝该情形。** `0033_domestic_studio_bindings.py:11-18` 对任何既有同名表拒绝继续；`test_domestic_studio_migration.py:13-34` 分别覆盖已建同名表和畸形同名表。该策略要求运维人工处理既有表，并非已有表自动迁移。SQLite 中迁移表与 ORM 模型的字段、类型、非空、主键和 CHECK 比对一致，见下；真实 PostgreSQL 完整迁移链未运行。 |
| 上轮 freezer 返回错误身份 | **拒绝分支已实现。** `policy.py:50-53` 校验冻结结果为映射且 `skill.id == binding_id`，`test_domestic_studio_policy.py:60-63` 覆盖不匹配。实际国内 freezer 尚无；涉及 ID 规范化时须在后续集成中验证绑定与冻结使用同一稳定身份。 |
| 事务、权限和国内外隔离 | **部分基础约束。** `bindings.py:29-52` 在修改前验证整批并由调用方提交；`test_domestic_studio_bindings.py:43-53` 覆盖校验失败并由调用方回滚。`models.py:5-10` 使用国内 `Base`，`migrations/env.py:4-7,25,34-36` 限制国内迁移上下文并拒绝海外迁移标记。actor 授权、真实目录和路由接线不在本次范围，不能推断普通用户、跨业务身份或并发停用已获保护。 |
| 其他 Spec 与 UI | `Product-Spec.md:5-11` 中帮助、会话、附件、执行、结果、归档库、Skill 上传/ZIP、真实身份及 UI 不在此次基础任务范围，均未验证；本次没有需按设计稿比较的新页面。 |

本范围新增的绑定表和五入口策略可追溯到 `Product-Spec.md:5,8-9`，未发现另加的页面或 API；完整产品范围的 Spec 漂移不在本次审查内。

## 验证与原始输出

后端目录为 `hengxin-smart-image/backend`。以下测试、heads 和编译命令退出码均为 0：

```text
> .venv/Scripts/python.exe -m pytest tests/test_domestic_studio_policy.py tests/test_domestic_studio_bindings.py tests/test_domestic_studio_migration.py -q
.....................................                                    [100%]
37 passed in 1.55s

> .venv/Scripts/python.exe -m alembic heads
0033 (head)

> .venv/Scripts/python.exe -m compileall -q app/modules/domestic_studio migrations/versions/0033_domestic_studio_bindings.py migrations/env.py tests/test_domestic_studio_policy.py tests/test_domestic_studio_bindings.py tests/test_domestic_studio_migration.py
（无输出，退出码 0）
```

现有二 Session 测试的 `create_engine('sqlite://')`（`test_domestic_studio_bindings.py:14-23,87-111`）在同线程复用同一底层物理连接，独立验证输出 `sqlite_single_thread_dbapi_same_connection= True`；因此它们覆盖 ORM identity map，不覆盖两个独立数据库事务。另用 SQLite 文件数据库及两条独立物理连接测试的原始输出：

```text
distinct physical connections: True
stale cached: old fresh frozen: new
deleted binding rejected: 409
reinsert database: restored
```

迁移实际在 SQLite 执行，模型 DDL 编译为 PostgreSQL 方言，原始输出：

```text
migration columns: [('workspace', 'VARCHAR(20)', False, 1), ('skill_id', 'VARCHAR(100)', False, 0), ('created_at', 'DATETIME', False, 0), ('updated_at', 'DATETIME', False, 0)]
model columns: [('workspace', 'VARCHAR(20)', False, 1), ('skill_id', 'VARCHAR(100)', False, 0), ('created_at', 'DATETIME', False, 0), ('updated_at', 'DATETIME', False, 0)]
migration checks: [{'sqltext': "workspace IN ('camera','case','product','scene','phone')", 'name': None}]
postgresql model DDL: CREATE TABLE domestic_studio_skill_bindings (
    workspace VARCHAR(20) NOT NULL,
    skill_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (workspace),
    CHECK (workspace IN ('camera','case','product','scene','phone'))
)
```

隔离 PostgreSQL 实测只创建最小测试表 `execution_gate(id)`、`domestic_studio_skill_bindings(workspace, skill_id)`，使用 Unix socket、临时数据目录及独立 `psql` 连接；测试后关闭临时实例。它验证与代码相同顺序的 SQL 和数据库事务语义，**没有运行应用 ORM 函数、完整迁移链或目标生产配置**。执行序列：

```sql
-- A: BEGIN ISOLATION LEVEL REPEATABLE READ;
-- A: SELECT skill_id FROM domestic_studio_skill_bindings WHERE workspace='camera'; -- old
-- B: BEGIN;
-- B: SELECT id FROM execution_gate WHERE id=1 FOR UPDATE;
-- B: UPDATE domestic_studio_skill_bindings SET skill_id='new' WHERE workspace='camera'; COMMIT;
-- A: SELECT id FROM execution_gate WHERE id=1 FOR UPDATE;
-- A: SELECT skill_id FROM domestic_studio_skill_bindings WHERE workspace='camera'; -- old
-- A: COMMIT;
```

```text
server: PostgreSQL 18.6 (Ubuntu 18.6-0ubuntu0.26.04.1) on x86_64-pc-linux-gnu, compiled by gcc (Ubuntu 15.2.0-16ubuntu1) 15.2.0, 64-bit
default_isolation: read committed
RR session A begin + snapshot: ['old']
session B lock + change + commit: ['1']
RR session A lock + binding after B commit: ['1', 'old']
fresh connection binding: new
RC session A begin + snapshot: ['old']
session B lock + change + commit: ['1']
RC session A lock + binding after B commit: ['1', 'new']
independent connection competing lock exit= 1 stderr= ERROR:  canceling statement due to lock timeout | CONTEXT:  while locking tuple (0,1) in relation "execution_gate"
```

**尚未验证：** 真实国内 PostgreSQL 配置及完整迁移、应用级两事务交错、真实国内 Skill catalog、Job 负载与文件快照、路由权限、防绕过和最终用户界面。修复后须重新固定 candidateId 并从 Stage 1 起重新审查。

## 复用隔离 PostgreSQL 的方式

本次实例位于本机 WSL 的 `Ubuntu` 发行版，二进制为 `/usr/lib/postgresql/18/bin/`；实例使用临时目录和 Unix socket，仅本机 WSL 可连接，已停止且临时目录已删除。WSL 默认用户为 root，运行 PostgreSQL 使用 `postgres` 系统账号。复现启动及连接示例（在 WSL 的 shell 执行）：

```bash
pgbin=/usr/lib/postgresql/18/bin
review_dir=$(mktemp -d /tmp/hx-binding-review-XXXXXX)
chown postgres:postgres "$review_dir"
runuser -u postgres -- "$pgbin/initdb" -D "$review_dir/data" --auth=trust --no-locale
runuser -u postgres -- "$pgbin/pg_ctl" -D "$review_dir/data" -l "$review_dir/server.log" -o "-F -c listen_addresses= -c unix_socket_directories=$review_dir" -w start
"$pgbin/psql" -X -U postgres -h "$review_dir" -d postgres
# 测试结束后：
runuser -u postgres -- "$pgbin/pg_ctl" -D "$review_dir/data" -m fast -w stop
```

测试完应确认目录确为本次创建的 `/tmp/hx-binding-review-*` 后再删除；不要作用于现有数据库目录。Python/SQLAlchemy 可从 WSL 使用 `postgresql+psycopg://postgres@/postgres?host=<review_dir>` 连接，但本次 WSL 默认 Python 未安装 SQLAlchemy、psycopg 或 pytest，需在隔离虚拟环境安装项目依赖；Windows Python 不能直接访问此 WSL Unix socket。

主 Agent 另行反馈，国内生产只读 `SHOW` 得到 `read committed`；本 reviewer 未独立核验该结果。这不影响本报告对支持其他隔离级别时的条件性缺陷结论。
