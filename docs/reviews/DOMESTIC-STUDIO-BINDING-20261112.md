# 国内工作台绑定基础任务审查（2026-11-12）

- candidateId：`2566618fccac267fdc85ea75bff2a0fbc6b66c98d073e45803d02f5f95c10236`
- 审查范围：`hengxin-smart-image/backend/app/modules/domestic_studio/{policy.py,models.py,bindings.py}`、`backend/migrations/versions/0033_domestic_studio_bindings.py`、`backend/migrations/env.py` 的新增导入、`backend/tests/test_domestic_studio_{policy,bindings,migration}.py`。参考 `Product-Spec.md:1-11` 和海外实际冻结、锁定及 Skill 管理实现。国内路由、身份授权、真实 Skill 库、发送执行与归档接线属于后续工作，不按本基础任务漏交判定。
- 审查期间开始和结束的 `review-status` 当前快照均为上述 candidateId；报告为普通 Markdown，不在代码快照内。
- **Stage 1：FAIL（存在 HIGH）**。
- **Stage 2：未执行**。不视为 PASS；也没有执行 Stage 2 的安全扫描和视觉对比。

## Stage 1 缺陷

### HIGH：获得执行锁后仍可读取旧绑定，也可能保存成功但数据库未更新

Spec 要求“服务端在发送时以当前入口的实际绑定为准”，且替换绑定要生效（`Product-Spec.md:9`）。`bindings.py:66-69` 在取得 `execution_gate` 行锁后用 `session.get(WorkspaceBinding, workspace)`；如果同一 SQLAlchemy Session 先前加载并持有该对象，该调用直接返回 identity map 中的旧对象，不会读取数据库。`bindings.py:40-50` 在保存时也用同样的 `session.get`，而 `read_bindings` 的 ORM 查询同样没有 `populate_existing`。因此，其他事务已提交新绑定后，本事务仍可能冻结旧 Skill，或因 ORM 认为值没有变化而不发 UPDATE，却返回旧缓存冒充成功。

独立 SQLite 文件库、两个 Session 的可复现输出（两事务均通过这些绑定函数；第一事务持有先前加载的模型对象，第二事务先提交，随后第一事务才冻结/保存）：

```text
database_binding= new
retained_binding= old
frozen_skill= old
save_requested=new, returned= new , database= third
```

SQLite 不证明 PostgreSQL 行锁的实际阻塞；此复现证明的是 SQLAlchemy identity map 刷新缺失，与是否有行锁无关。[SQLAlchemy 2.0 官方 Session.get 文档](https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.get)确认未过期对象可直接从 identity map 返回。海外实现对需要刷新当前值的查询显式使用 `populate_existing`（`backend/app/overseas/management/skills.py:18-20,37-43`）。建议在锁取得后针对绑定实施新鲜读取，同时覆盖存在、替换、删除、同 Session 重复调用和两事务交错，验证读取值和提交后的数据库一致。

### MEDIUM：已存在表的迁移校验不验证列类型、非空约束及 CHECK 的准确语义

`backend/migrations/versions/0033_domestic_studio_bindings.py:15-24` 仅检查列名、主键及某个 CHECK 文本是否包含五个名称；不检查 `skill_id` 和时间列非空、字段长度/类型，也不检查 CHECK 是否额外允许非法工作台。下面的真实执行创建错误的已存在表（`workspace VARCHAR(1)`、可空 `skill_id`/时间列、CHECK 含 `OR 1=1`），迁移仍返回成功，随后非法数据可插入：

```text
migration accepted malformed table; inserted row: ('other', None, None, None)
```

这不是正常全新建表的失败；风险出现在目标表已存在但结构错误的部署。现有测试只验证只有 `unexpected` 一列的明显错误表（`backend/tests/test_domestic_studio_migration.py:27-33`），不能证明兼容性检查完整。建议对列类型、长度、nullability、主键及 CHECK 所允许的精确集合进行校验，并增加部分相似但不兼容表的回归用例。

### MEDIUM：冻结器接口没有核验返回结果与绑定身份一致

`policy.py:34-53` 将可信绑定 ID 传给回调后，只检查返回值的 `skill` 是否为真，不核验 `skill.id` 等身份。传入绑定 `bound-a`、回调返回 `{'skill': {'id': 'other-b'}}` 的实际输出为：

```text
binding=bound-a, callback_frozen_id= other-b
```

当前回调由服务端代码提供，不是已证明可由 HTTP 客户端直接控制的漏洞；当前范围也没有真实国内 catalog 可验证。此处尚不能独立证明 Spec 所需“实际绑定就是最终执行 Skill”（`Product-Spec.md:9`）。需明确跨旧 ID/新 ID 的规范化契约，在可信适配层核对最终冻结身份，并对错误/意外回退的冻结器做失败测试；不能简单假设海外旧 ID 的解析结果必然与输入字面相同（`backend/app/overseas/management/settings.py:25-30`）。

## Spec 逐项对照与边界

| 条目 | 本基础任务结论与证据 |
| --- | --- |
| 五个指定工作台 | 策略集合恰有 `camera/case/product/scene/phone`，未知值拒绝：`policy.py:13-25`；相关测试 `test_domestic_studio_policy.py:21-25,28-37`。实际菜单/直接进入工作台属后续。 |
| 仅新品可归档、禁止产品替换绕过 | 纯服务端策略允许 `camera/case` 并拒绝 `product/scene/phone`：`policy.py:13-18,28-31`；测试 `test_domestic_studio_policy.py:9-18`。归档路由尚未接线，不能据此声称 HTTP 防绕过已验证。 |
| 空白会话、无默认提示词和演示数据 | 本范围的绑定表未预置记录：迁移 `0033_domestic_studio_bindings.py:25-32`；SQLite 测试 `test_domestic_studio_migration.py:13-23`。对话/UI 和 Skill 包初始化不在此范围，不能宣称已验证完整要求。 |
| 后端固定绑定、拒绝客户端指定、未绑定不回退 | `policy.py:45-52` 拒绝任何非 `None` 客户端 ID、空绑定及空冻结结果；覆盖 `test_domestic_studio_policy.py:40-57`。冻结身份一致性及旧 Session 值存在上述问题，实际发送路径未接入。 |
| 已停用 Skill 拒绝、绑定不得停用或删除 | `bindings.py:35-39,53-59` 委托可信 catalog 的 `verify_enabled`，提供绑定检查；测试 `test_domestic_studio_bindings.py:43-53,63-70` 使用替身。没有真实国内 catalog、停用/删除接线，因而未验证真实拒绝和竞态；这些是后续交付责任。 |
| 持久化、整批更新 | 表模型 `models.py:9-14`，迁移 `0033_domestic_studio_bindings.py:25-32`；先验证整批再操作、由调用方提交 `bindings.py:29-50`；校验失败回滚测试 `test_domestic_studio_bindings.py:43-53`。缓存缺陷导致保存结果可能与数据库不一致，见 HIGH。 |
| 并发顺序及请求快照 | `bindings.py:18-20,34,55,65-69` 使用国内 `execution_gate` 的 `FOR UPDATE`，原门锁在 `backend/migrations/versions/0005_tasks.py:14-20` 建立。SQLite 不实现等效行锁，现有测试 `test_domestic_studio_bindings.py:14-23` 不能证明 PostgreSQL 并发行为。独立手工测试同一 Session 顺次绑定 A、冻结、换绑 C、再冻结，输出 `same_session previous_snapshot= bound-a , current_snapshot= bound-c`；它只证明该同步顺序和测试回调产生的独立字典，不能证明未来 Job 负载及文件副本真正持久冻结。 |
| 国内超级管理员及国内外隔离 | 此层没有 actor 参数或权限检查，路由/服务接线未实现；须在后续入口使用国内在职超级管理员校验并同事务锁权限（现有参考 `backend/app/modules/auth/member_policy.py:16-21`），并测试普通用户和跨业务身份。新绑定模型继承国内 Base（`models.py:5-10`），国内迁移入口限制业务上下文（`backend/migrations/env.py:4-7,25,34-36`），这不能替代全链路隔离测试。海外 freezer 直接依赖海外门锁和 catalog（`backend/app/overseas/management/settings.py:6-10,69-74`，`backend/app/overseas/management/installed_catalog.py:25-32`），不可未经国内隔离适配直接接用。 |
| 帮助、真实会话、附件、结果、归档库、上传 ZIP 及 UI | 这些不属于本次基础任务审查范围，均未验证；不得将本报告理解为最终功能验收。对应 Spec `Product-Spec.md:5-11`。 |

本范围未发现预置绑定/预置 Skill；除此之外的 Spec 漂移与完整产品 UI 无法仅凭本范围断定。

## 验证与原始输出

工作目录：`hengxin-smart-image/backend`。

```text
> .venv/Scripts/python.exe -m pytest tests/test_domestic_studio_policy.py tests/test_domestic_studio_bindings.py tests/test_domestic_studio_migration.py -q
..................................                                       [100%]
34 passed in 1.62s

> .venv/Scripts/python.exe -m pytest tests/test_domestic_retirement.py tests/test_local_skills_migration.py tests/test_overseas_skill_availability_migration.py tests/test_overseas_skill_platforms_migration.py -q
ssssssss.sss                                                             [100%]
1 passed, 11 skipped in 2.41s

> .venv/Scripts/python.exe -m pytest tests/test_api_text_kind_migration.py tests/test_api_image_dimensions_migration.py tests/test_builtin_text_migration.py -q
.s.s.s                                                                   [100%]
3 passed, 3 skipped in 0.88s

> .venv/Scripts/python.exe -m alembic heads
0033 (head)

> .venv/Scripts/python.exe -m compileall app/modules/domestic_studio migrations/versions/0033_domestic_studio_bindings.py migrations/env.py tests/test_domestic_studio_policy.py tests/test_domestic_studio_bindings.py tests/test_domestic_studio_migration.py
Listing 'app/modules/domestic_studio'...
```

上述命令退出码均为 0。相关 PostgreSQL 回归因未配置隔离测试库被跳过；本机无 5432/5433/15432 监听，Docker daemon 未运行。未执行 PostgreSQL 实际迁移链、锁阻塞或竞态验证，不得将 SQLite 结果等同于生产数据库验证。
