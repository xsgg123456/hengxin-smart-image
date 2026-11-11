# 内网 245 数据复制模块独立审查

- 日期：2026-11-10。
- candidateId：`ba560f0d367323165afdbbd9d8fe6442bcb61a4dfd9bc8a1fc90b740927661f3`。
- 代码范围仅为 `hengxin-smart-image/scripts/migration245/data_copy.py` 与 `data_copy_test.py`。下文路径以该目录为基准。
- 依据：`docs/INTRANET-245-PLAN-20261110.md:113` 的第 5 节、`:276` 的附录 A，以及 `output/migration-inventory-20261110/db_inventory.json`。Product-Spec.md 存在；本次专项授权以部署方案为验收合同。
- 未连接任何服务器；仅复跑本地测试和新建隔离 PostgreSQL 16 容器的故障复现。临时容器无网络、无发布端口、数据放 tmpfs，结束删除。
- 起始范围文件原始字节 SHA-256：`data_copy.py=C451873887C5AFF4C0CED81B5EB6E02F57E9E9220D2F44F28EB8AE344115CF8E`；`data_copy_test.py=A607F38B387993191158C6432A0CEF5C0648DAC7A4EF0C1B632FFD0B13C0BFAE`。本次缺陷复现与原始 10 项测试对应这两份起始文件。
- **审查期间代码发生变化**：报告落盘前末次校验变为 `data_copy.py=93ADC198BEC7A4D0FFCF3502A127859F08356CE1499129104FD26610C829A4BB`、`data_copy_test.py=C5D5F8070357A085C4B3C6C80CA034D58F7C396D51E468F8DD8E8EDCF6350973`。下文结论与行号属于起始版本，不能直接覆盖新版本；需重新固定 candidateId 并复审差异。

## 结论

**Stage 1：FAIL（1 项 HIGH）；Stage 2：未执行。** 原有 10 项测试通过不足以批准该快照。主 Agent 应修复、重新固定 candidateId，并从 Stage 1 复审；本报告不授权 review-approve，不写 `.needs-review`。

## Stage 1：Spec Compliance

### HIGH：版本校验遇到空版本表会放行

- 需求：方案 `:140` 要求记录真实版本，`:143` 要求当前完整迁移链建库；附录 `:285`、`:329` 禁止只写版本号冒充迁移完成。交接明确只接受精确新 schema。
- 实现：`data_copy.py:68` 的通用断言生成 `IF NOT (condition) THEN ...`；`:89` 使用 `array_agg(version_num::text) = ARRAY[...]`。版本表无记录时聚合为 NULL，`NOT NULL` 仍是 NULL，不执行异常分支。`:128` 随后将预设版本写进导出包，不能证明源库真实版本；目标同样复用该校验（`:186`）。
- 证据：在本次独立创建的 PostgreSQL 16 容器中，调用测试夹具建表，删除 `overseas_alembic_version` 全部记录，执行 `source_sql` 后 `validate` 成功；重新初始化目标，再删除版本行，执行 `target_sql` 亦提交成功。没有改被审代码或访问用户数据库。

```text
source_empty_version_export_accepted= True
target_empty_version_import_accepted=True
owned_reproduction_container_removed=True
```

- PostgreSQL 官方 [PL/pgSQL 条件控制文档](https://www.postgresql.org/docs/16/plpgsql-control-structures.html) 明确 IF 只有条件为真时才执行分支；NULL 不是真。与本地复现一致。
- 修复方向：断言对 NULL 也应失败，例如 `(condition) IS NOT TRUE`；增加源端和目标端空版本表测试，目标失败后验证没有导入数据。此处仅提建议，reviewer 未修改实现。

### 完整实现及证据

| 需求项 | 结论与证据 |
|---|---|
| 国内 8 表白名单 | 完整实现：`data_copy.py:14`–`:23` 显式列出 users、user_identities、role_assignments、domestic_membership_applications、domestic_membership_application_events、domestic_member_audits、system_settings、settings_audit。与方案 `:119`–`:121` 及盘点列类型逐项比较一致。 |
| 海外 8 表白名单 | 完整实现：`data_copy.py:24`–`:33` 显式列出海外成员、角色、申请、申请事件、成员审计、设置、Skills 可用性和管理审计，表名及全部列类型与盘点一致。 |
| 身份 UUID、角色、审批、启停状态原样保留 | 完整实现：`:110` 显式列导出，`:204` 显式列导入，无状态重写；`:213` 比较导入后完整行、摘要和数量。`data_copy_test.py:142` 验证 disabled，`:199` 验证 pending。生产实际行内容尚未验收。 |
| 海外管理审计仅 skill.* | 完整实现：`:112` 源 SQL 过滤，`:158` 导入前再检验 action；`:160`–`:176` 拒绝未知 JSON 键及不符合允许格式的值，不静默删字段。测试 `:43` 覆盖 studio.*、prompt、嵌套正文，`:142` 验证真实 SQL 排除 studio.delete。 |
| 业务历史、登录态、旧任务不导出 | 完整实现：`:121` 仅遍历上述 SCHEMA，不导出其它表；`:35`–`:38` 的完整 39/44 表清单与盘点集合精确相同。完整逐表判定见下附表。 |
| 每库单独 REPEATABLE READ READ ONLY 快照 | 完整实现：`:134`–`:138` 一个事务包含 schema_guard 与全部白名单查询，设置语句、锁及空闲事务超时；`:129` 记录事务时间与 snapshot。测试 `data_copy_test.py:190` 在同事务注入建表操作，数据库拒绝且未创建表。 |
| 新目标定位及人工参数确认 | 完整实现：`:221`–`:231` 仅本地 Unix Docker socket 与容器内 PostgreSQL socket，容器名须 hengxin-lan-*，confirmation 精确匹配 container/database；参数以数组调用，不经 shell。测试 `:32` 覆盖旧名称、缺失/错误确认和非法名称。此校验不能单独证明执行宿主机就是 .245，需执行层确认。 |
| 目标非空拒绝，禁止覆盖已用实例 | 完整实现：`:185` 先锁完整表集合，`:188`–`:198` 检查全部非版本表。只有 `SEEDS` 中精确默认值可非空（时间列被明确忽略）；设置种子在事务内替换。测试 `:159` 验证业务记录与 paused=true 默认门闩被拒绝；`:142` 验证重复导入被拒绝。 |
| 默认运行状态不继承旧状态 | 完整实现：`:44`–`:54` 定义默认种子白名单；这些运行表不进入源导出 SCHEMA。仅保留目标已生成的默认种子，不能把源租约、队列、会话带入；非种子运行表要求为空（`:191`）。 |
| FK 保持开启、按依赖导入 | 完整实现：`:184` 使用 origin；`:91`–`:106` 拒绝未验证约束、禁用的内部约束触发器和逆向 FK 依赖；`:209` 强制约束即时检查。11 条白名单实际 FK 均符合静态导入顺序。测试 `:181` 验证引用不存在成员导致失败且已插入成员回滚。该检查不替代完整迁移链部署证明。 |
| 摘要一致、失败回滚 | 完整实现：`:183` BEGIN，`:213`–`:217` 在 COMMIT 前比较完整行、SQL SHA-256 和 count；失败由 ON_ERROR_STOP 中止连接并回滚。测试 `:170` 验证错误摘要回滚插入和设置种子删除；`:142` 验证高精度 JSON 数字与全表摘要往返一致。 |
| SQL 值安全引用 | 本阶段实现核对通过：`:57`–`:65` 值转 UTF-8 十六进制后解码，标识符正则过滤且双引号引用；`:203` 将原始 JSON 作为字面值导入。测试 `:53` 验证恶意引号与 psql 元命令没有原样进入 SQL。Stage 2 全面安全扫描未执行。 |
| 数据库失败输出不泄露记录 | 实现及已有测试通过：`:237`–`:242` 隐去捕获的数据库错误，仅对静态已知表名输出 target not empty；测试 `:58` 验证 stderr 中的客户记录不出现在异常文本中。超时异常输出仅类型（`:274`）。 |

### 部分实现与范围外验收

- **真实版本校验部分实现**：版本不同的非空数组能被拒绝，但空版本表放行，详见 HIGH。
- **私有文件保护须由调用端提供证据**：`data_copy.py:255`–`:260` 仅拒绝 TTY；普通管道或文件不会检查属主、目录 0700、文件 0600。source 正常输出包含敏感数据。本次只审两文件，不把该条件声称为已验证；在调用端保证受保护管道、新机 root 私有落盘后才可执行真实导出。不能将工具捕获 stdout 当作脱敏输出。
- **迁移链、序列、跨库/Skills 一致性及消费者关闭**：方案 `:141`、`:143`–`:145` 要求由整套部署与验收实现，本模块不创建 schema、不执行 Alembic、不复制文件、不控制消费者/Redis/MinIO，也不核对文件指针和跨库引用。盘点未含序列定义，本次不能证明序列要求已满足。此范围限制不被包装成生产迁移完成。
- **UI、设计稿与邻居页面**：两文件为 CLI 模块，无新增 UI；UI 引导与视觉对比不适用。
- **Spec 漂移**：范围内没有新增页面/API/业务功能。允许迁移默认种子符合交接约束；未发现额外业务数据导出入口（`:13`、`:121`、`:204`）。

## 原始本地验证输出

命令：在 `hengxin-smart-image/scripts/migration245` 设置 `DATA_COPY_PG_TEST=1` 后运行 `python -m unittest data_copy_test -v`。

```text
test_business_data_and_dirty_seed_refused (data_copy_test.PostgreSQLTests.test_business_data_and_dirty_seed_refused) ... ok
test_digest_failure_rolls_back_seed_and_insertions (data_copy_test.PostgreSQLTests.test_digest_failure_rolls_back_seed_and_insertions) ... ok
test_domestic_roundtrip_and_pristine_seeds (data_copy_test.PostgreSQLTests.test_domestic_roundtrip_and_pristine_seeds) ... ok
test_filter_roundtrip_state_and_precision (data_copy_test.PostgreSQLTests.test_filter_roundtrip_state_and_precision) ... ok
test_foreign_key_failure_rolls_back (data_copy_test.PostgreSQLTests.test_foreign_key_failure_rolls_back) ... ok
test_source_is_read_only_and_catalog_drift_rejected (data_copy_test.PostgreSQLTests.test_source_is_read_only_and_catalog_drift_rejected) ... ok
test_audit_policy_rejects_business_or_unknown_payload (data_copy_test.UnitTests.test_audit_policy_rejects_business_or_unknown_payload) ... ok
test_errors_do_not_leak_records (data_copy_test.UnitTests.test_errors_do_not_leak_records) ... ok
test_sql_values_are_hex_encoded (data_copy_test.UnitTests.test_sql_values_are_hex_encoded) ... ok
test_wrong_target_refused_before_subprocess (data_copy_test.UnitTests.test_wrong_target_refused_before_subprocess) ... ok

----------------------------------------------------------------------
Ran 10 tests in 10.591s

OK
```

编译命令：`python -m py_compile hengxin-smart-image/scripts/migration245/data_copy.py hengxin-smart-image/scripts/migration245/data_copy_test.py`。原始 stdout/stderr 均为空，进程 exit code 0。

静态盘点集合比较原始结果：

```text
hengxin
table_inventory_match= True
whitelist_columns_match= True
hengxin_overseas
table_inventory_match= True
whitelist_columns_match= True
```

测试夹具仅重建已知列及选定约束（`data_copy_test.py:99`），没有运行完整 Alembic，不能替代新机实际 schema/全部 FK 验收。原测试均通过但漏测空版本表，这是上述缺陷能通过测试的具体原因。

## 附表：83 表逐项处理核对

所有表均与盘点集合匹配。以下“通过”仅指该表数据选择规则；不覆盖上文版本校验失败。

### hengxin

| 表 | 规则匹配 | 代码证据 |
|---|---|---|
| `alembic_version` | 部分实现：不复制版本数据，但空版本校验失败 | data_copy.py:89、:189 |
| `api_edit_conversations` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `api_edit_events` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `api_edit_turns` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `api_image_attempts` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `api_image_channel` | 通过：不导出源记录，仅接受目标默认种子 | data_copy.py:44、:121、:192 |
| `api_image_dispatch` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `api_image_files` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `api_image_items` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `api_image_operations` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `api_image_tasks` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `api_image_versions` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `api_task_deletions` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `api_usage_facts` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `api_worker_heartbeats` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `auth_login_states` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `auth_sessions` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `capacity_gate` | 通过：不导出源记录，仅接受目标默认种子 | data_copy.py:44、:121、:192 |
| `capacity_reservations` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `cli_retention` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `cli_retention_object_links` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `cli_retention_objects` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `cli_retention_records` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `cli_retention_runs` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `cli_retention_service` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `cli_retention_totals` | 通过：不导出源记录，仅接受目标默认种子 | data_copy.py:44、:121、:192 |
| `domestic_member_audits` | 通过：显式列保留并核对行/摘要 | data_copy.py:13、:110、:204、:213 |
| `domestic_membership_application_events` | 通过：显式列保留并核对行/摘要 | data_copy.py:13、:110、:204、:213 |
| `domestic_membership_applications` | 通过：显式列保留并核对行/摘要 | data_copy.py:13、:110、:204、:213 |
| `execution_gate` | 通过：不导出源记录，仅接受目标默认种子 | data_copy.py:44、:121、:192 |
| `image_variants` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `job_outbox` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `job_records` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `role_assignments` | 通过：显式列保留并核对行/摘要 | data_copy.py:13、:110、:204、:213 |
| `settings_audit` | 通过：显式列保留并核对行/摘要 | data_copy.py:13、:110、:204、:213 |
| `system_settings` | 通过：显式列保留并核对行/摘要 | data_copy.py:13、:110、:204、:213 |
| `user_identities` | 通过：显式列保留并核对行/摘要 | data_copy.py:13、:110、:204、:213 |
| `users` | 通过：显式列保留并核对行/摘要 | data_copy.py:13、:110、:204、:213 |
| `worker_heartbeats` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |

### hengxin_overseas

| 表 | 规则匹配 | 代码证据 |
|---|---|---|
| `overseas_alembic_version` | 部分实现：不复制版本数据，但空版本校验失败 | data_copy.py:89、:189 |
| `overseas_archive_assets` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_archive_deletions` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_archive_events` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_archives` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_draft_imports` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_draft_materials` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_execution_events` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_execution_gate` | 通过：不导出源记录，仅接受目标默认种子 | data_copy.py:44、:121、:192 |
| `overseas_execution_objects` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_installed_skill_availability` | 通过：显式列保留并核对行/摘要 | data_copy.py:13、:110、:204、:213 |
| `overseas_job_outbox` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_jobs` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_management_audit` | 通过：仅 skill.* 且校验审计 JSON | data_copy.py:112、:158 |
| `overseas_material_versions` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_materials` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_member_audits` | 通过：显式列保留并核对行/摘要 | data_copy.py:13、:110、:204、:213 |
| `overseas_member_roles` | 通过：显式列保留并核对行/摘要 | data_copy.py:13、:110、:204、:213 |
| `overseas_members` | 通过：显式列保留并核对行/摘要 | data_copy.py:13、:110、:204、:213 |
| `overseas_membership_application_events` | 通过：显式列保留并核对行/摘要 | data_copy.py:13、:110、:204、:213 |
| `overseas_membership_applications` | 通过：显式列保留并核对行/摘要 | data_copy.py:13、:110、:204、:213 |
| `overseas_picture_versions` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_pictures` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_plans` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_requirement_drafts` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_requirements_reviews` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_sessions` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_settings` | 通过：显式列保留并核对行/摘要 | data_copy.py:13、:110、:204、:213 |
| `overseas_skill_versions` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_skills` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_studio_conversation_deletions` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_studio_conversations` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_studio_material_visibility` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_studio_output_files` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_studio_pictures` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_studio_transcript` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_studio_turns` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_studio_uploads` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_task_deletions` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_task_events` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_task_outbox` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_task_requests` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_task_skus` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
| `overseas_tasks` | 通过：不导出源记录，目标必须为空 | data_copy.py:35、:121、:191 |
