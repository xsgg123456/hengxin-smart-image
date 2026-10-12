# Phase 16 海外数据库合同

依据 Product-Spec 正式海外需求及 DEV-PLAN 16.2：海外使用独立数据库和凭据；连接池直接复用 `app.db.session`，模型元数据独立，不导入国内业务模型。

1. `app.overseas.db.Base` 为独立 DeclarativeBase；Phase 16 无业务表。
2. 海外迁移使用 `alembic -c alembic.overseas.ini upgrade head`；必须显式设置 `HX_BUSINESS_CONTEXT=overseas`，配置来自 `OVERSEAS_` 环境变量。国内迁移拒绝 overseas 上下文，双方在线迁移均拒绝另一业务的版本标记。
3. 海外迁移目录为 `migrations/overseas`，版本表固定 `overseas_alembic_version`，初始 revision 为 `overseas_0001`。初次迁移只建立版本标记，重复 upgrade 不新增业务表。
4. 海外在线迁移在写入前检查 schema：拒绝国内 `alembic_version`、未知业务表、视图和物化视图，以及其他非系统 schema 内的这些对象；本阶段只允许空库或仅含海外版本标记的库。后续新增业务表时由海外 Base.metadata 声明允许表。默认 schema 必须为 public，禁止借 search_path 绕开检查。
5. 在线迁移使用共享连接池与事务；离线 SQL 仅供审阅，不能验证目标数据库隔离，正式执行必须通过在线入口。
6. readiness 查询 `overseas_alembic_version.version_num`，Phase 16 必须恰有一行且值为 `overseas_0001`。未迁移或版本不符不可就绪。
   Compose 应用角色 `overseas_app` 对版本表仅能读取，迁移结束及重复 bootstrap 均撤销版本表写权限；业务表仍按默认权限允许 DML。
7. 测试仅使用显式 `TEST_OVERSEAS_DATABASE_URL` 且库名以 `_test` 结尾的独立 PostgreSQL；测试创建随机独立库，结束删除自己创建的库，不能清空已有库。

验收顺序：上下文/元数据单测 → 独立数据库首次及重复升级 → 错库拒绝且原表/版本/数据不变 → 主 Agent 汇总 Phase 16 审查。
