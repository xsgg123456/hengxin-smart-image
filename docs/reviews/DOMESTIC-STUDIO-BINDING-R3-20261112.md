# 国内工作台绑定基础任务第三轮审查

- 审查候选：`b3285d9dea897ab2e7b487178979930f5810bbee9b9dcfb8e92d5c2d73142ef8`。
- 范围：`hengxin-smart-image/backend/app/modules/domestic_studio/{policy,models,bindings}.py`、`backend/migrations/versions/0033_domestic_studio_bindings.py`、`backend/migrations/env.py` 中新增导入，以及 `backend/tests/test_domestic_studio_{policy,bindings,bindings_pg,migration}.py`。对照 `Product-Spec.md:1-11` 中五入口、仅新品归档、服务端固定 Skill、空绑定拒绝及绑定中的 Skill 停用/删除保护。路由、真实目录、执行记录、文件快照和 UI 均属于后续任务。
- **Stage 1：PASS（仅上述基础策略和锁原语的范围，前提及未接线部分见下）。**
- **Stage 2：FAIL。** 存在以下两个 MEDIUM 质量/测试问题；不能登记两个阶段均 PASS。
- 快照变化：审查开始 `review-status` 为候选 ID；审查中主 Agent 修改了范围外的 `hengxin-smart-image/frontend/src/views/overseas/studio/StudioTurns.vue` 和 `hengxin-smart-image/frontend/tests/studio-message-metadata.test.ts`。使用 `review_files.changes` 对照候选文件哈希，审查结束前当前 ID 为 `0d2c6ac78165a124f0c1486660b595bbb2d1a03303c0f9fa5a1892c7c54b267b`，差异仅为这两个文件，以上后端审查范围未变。不能将此报告当作当前全仓快照的批准；代码再变化须重新固定并复核。

## Stage 1：Spec 逐项对照

| 条目 | 结论与证据 |
| --- | --- |
| 五个入口 | 策略集合恰为 `camera/case/product/scene/phone`，未知值返回 404（`policy.py:13-25`、`test_domestic_studio_policy.py:21-25`）。名称对应预览中的相机配件、手机壳、只换产品、换场景/模特/产品/尺寸和换手机/壁纸/膜（`frontend/preview-domestic-studio/workspaces.ts:10-11,20-21,30-31,40-41,50-51`）。这里只确认策略 ID，生产菜单及路由尚未审查。 |
| 仅新品可归档 | `camera/case` 允许，三个产品替换入口返回 403（`policy.py:13-18,28-31`；`test_domestic_studio_policy.py:9-18`）。归档 HTTP 路由尚未接入，故产品替换绕过前端的完整拒绝尚未验证。 |
| 当前固定 Skill，禁止客户端覆盖 | `freeze_for_send` 先取门锁并重新读取当前绑定，拒绝任何非 `None` 的客户端 Skill，冻结结果的 `skill.id` 必须匹配绑定（`bindings.py:69-77`，`policy.py:45-53`；`test_domestic_studio_policy.py:28-44,60-63`）。真实发送路由和 catalog 尚未接入，不能声称全链路防绕过完成。 |
| 空绑定拒绝、无默认 Skill | 空或空白绑定返回 409，不调用 freezer（`policy.py:48-49`；`test_domestic_studio_policy.py:47-51`）；迁移只建空表（`0033_domestic_studio_bindings.py:19-26`；独立 SQLite 实测 0 行，原始输出见下）。提示文案的 UI 展示和真实目录初始化不在本次范围。 |
| 仅绑定启用且存在的 Skill | 整批写入前逐个调用 `verify_enabled`（`bindings.py:34-45`）；发送时依赖传入的可信 freezer（`policy.py:50-53`）。`test_domestic_studio_bindings.py:44-54` 和 `test_domestic_studio_policy.py:66-72` 使用抛异常的替身；真实国内目录未实现，无法证明真实停用/不存在文件的拒绝行为。 |
| 绑定禁止停用或删除 | `assert_unbound` 在同一门锁下查询，发现绑定返回 409（`bindings.py:60-66`；`test_domestic_studio_bindings.py:64-71`）。真正停用及删除接口必须在相同事务中接入该检查，当前未接线。 |
| 换绑后旧请求保持快照 | `bindings.py:69-71` 和 `policy.py:40-44` 只把快照持久化职责交给调用方；尚无真实国内执行记录与文件快照，**未验证完整需求**。 |
| 事务及隔离 | PostgreSQL 门锁前检查实际事务隔离级别为 `read committed`，其他级别拒绝（`bindings.py:18-25`）；刷新绑定使用 `populate_existing`（`bindings.py:46-48,74-76`），避免同 Session 旧对象覆盖查询结果。PostgreSQL 测试的设计覆盖不同物理连接、锁竞争及已有快照的 REPEATABLE READ 拒绝（`test_domestic_studio_bindings_pg.py:52-87`），但锁竞争断言范围存在下述质量问题。主 Agent 转述该文件在临时 PostgreSQL 18 上 `3 passed`、空库升至 0033 成功；本 reviewer 按交接要求未重复启动 PostgreSQL，未见那次运行的原始完整输出。 |
| Schema 和迁移失败语义 | 模型使用国内 `Base`（`models.py:5-14`）；迁移建相同列、主键和约束，发现既有同名表立即拒绝（`0033_domestic_studio_bindings.py:11-26`；`test_domestic_studio_migration.py:13-34`）。本次独立 SQLite 检查和模型 PostgreSQL DDL 编译结果见下；`migrations/env.py:4-7,25,34-36` 注册模型且保留国内上下文检查。 |
| 其他 Spec 与 UI | 教程、会话、真实姓名、附件、执行器、成品库、Skill 文件包、权限及实际页面不在审查范围（`Product-Spec.md:5-11`），未验证，不代表最终产品通过验收。 |

审查范围中的新表和策略均可追溯至 `Product-Spec.md:5,8-9`；未发现额外 API 或页面。视觉设计稿对比和邻居页面渲染不适用于此次仅含后端原语与测试的范围，不能代替后续 UI 审查。

## Stage 2：缺陷

### MEDIUM：冻结结果的类型使用 `Any`，不符合审查质量标准

`policy.py:8,34-39` 与 `bindings.py:7,69-70` 将 freezer 输出和函数返回值声明为 `Mapping[str, Any]`。`.agents/skills/code-review/SKILL.md` 的 Stage 2 明确要求“无 any”；此外该类型使静态检查无法约束 `skill.id` 和其他快照字段。建议为实际稳定的快照结构建立明确的类型契约；真实 catalog 尚未接入，若包含开放扩展字段，应显式规定允许的值类型，不能假称已有生产快照类型验证。

### MEDIUM：PostgreSQL 锁竞争测试接受任意 OperationalError

`test_domestic_studio_bindings_pg.py:65-74` 名为验证门锁串行化，设置 `lock_timeout` 后以 `pytest.raises(OperationalError)` 接受全部此类异常，没有核对 PostgreSQL 的锁超时 SQLSTATE 或错误原因。暂时连接错误等也可能满足异常断言，后续恢复后再次取锁仍可能通过，因而该用例的 PASS 本身不充分证明异常由锁竞争产生。应核对实际数据库错误码并保留释放锁后可取得门锁的断言。它不否定上轮报告中独立 `psql` 锁超时实测，也不声称本次测试实际发生了假阳性。

## Stage 2：其他检查及边界

- 安全关键词扫描覆盖本次生产代码、迁移及四个测试，未发现所列密钥、危险函数或绝对路径。命中的动态 SQL 仅为测试中创建/删除隔离 schema（`test_domestic_studio_bindings_pg.py:25-30,38-41`），名称由固定前缀加 `uuid4().hex` 生成，不来自请求；其余 SQL 为测试固定字符串（`test_domestic_studio_migration.py:13-17,28-31`）。这是范围内关键词检查，不是完整渗透测试。
- 文件规模：生产文件为 54、14、77 行，迁移 30 行；作用分别是策略、模型、事务绑定和建表（各文件首行及上述行号）。除 `Any` 外，此次未发现需要报告的命名或拆分问题。
- 数据库使用前提：生产 `session_factory()` 默认没有启用 DBAPI `AUTOCOMMIT`（`app/db/session.py:40-47,64-65`）。`SHOW transaction_isolation` 本身不能识别驱动级 AUTOCOMMIT；在这种模式下 SQLAlchemy 的事务对象可能存在但语句会分别提交，门锁无法跨语句保持。此为依据 [SQLAlchemy 官方事务文档](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#setting-transaction-isolation-levels-dbapi-autocommit) 对未启用模式的推论，未在本次 PostgreSQL 实测中复现；后续接线应继续确保真实事务、同连接和同一门锁，不得仅以 `SHOW` 通过推断这些条件成立。
- 无新 UI 组件，故本范围不执行新页面与邻居页面的视觉对比。

## 验证与原始输出

工作目录 `hengxin-smart-image/backend`；以下为本 reviewer 独立执行，命令退出码均为 0：

```text
> .venv/Scripts/python.exe -m pytest tests/test_domestic_studio_policy.py tests/test_domestic_studio_bindings.py tests/test_domestic_studio_migration.py tests/test_domestic_studio_bindings_pg.py -q
......................................sss                                [100%]
38 passed, 3 skipped in 1.66s

> .venv/Scripts/python.exe -m alembic heads
0033 (head)

> .venv/Scripts/python.exe -m compileall -q app/modules/domestic_studio migrations/versions/0033_domestic_studio_bindings.py migrations/env.py tests/test_domestic_studio_policy.py tests/test_domestic_studio_bindings.py tests/test_domestic_studio_migration.py tests/test_domestic_studio_bindings_pg.py
（无输出，退出码 0）
```

3 个跳过项均为需 `TEST_DOMESTIC_STUDIO_DATABASE_URL` 的 PostgreSQL 测试（`test_domestic_studio_bindings_pg.py:17-24`）；不能将上述独立运行称为 PostgreSQL 测试通过。`compileall` 只验证 Python 编译，不是完整应用构建或类型检查。

独立执行迁移并检查模型：

```text
migration sqlite: [('workspace', 'VARCHAR(20)', False, 1), ('skill_id', 'VARCHAR(100)', False, 0), ('created_at', 'DATETIME', False, 0), ('updated_at', 'DATETIME', False, 0)]
migration check: [{'sqltext': "workspace IN ('camera','case','product','scene','phone')", 'name': None}]
rows: 0
model sqlite: [('workspace', 'VARCHAR(20)', False, True), ('skill_id', 'VARCHAR(100)', False, False), ('created_at', 'DATETIME', False, False), ('updated_at', 'DATETIME', False, False)]
model postgresql:
CREATE TABLE domestic_studio_skill_bindings (
    workspace VARCHAR(20) NOT NULL,
    skill_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (workspace),
    CHECK (workspace IN ('camera','case','product','scene','phone'))
)
```

SQLite 表结构与 ORM 定义一致；PostgreSQL 上述内容是编译 DDL，非本次数据库执行。
