# 内网 245 原生配置与 Skill 初始种子专项审查

- 日期：2026-11-10；执行者：独立 code-reviewer，使用 `.agents/skills/code-review/SKILL.md`。
- candidateId：`14b030e332df71a01b5717e34c97c2179a2ddd504026aaea95821727953c238c`。
- 结论：**Stage 1 PASS；Stage 2 PASS，仅限以下五文件及所列迁移职责。** 未发现 HIGH/MEDIUM 问题。
- 审查开始、编译验证后的 `review-status` 均显示当前 ID 与上述 candidateId 一致；审查未修改代码。主 Agent 应在登记前再次核对快照；本报告不写入 clean，也不代为 review-approve。
- 未连接旧生产或新机；未启动应用服务。数据库测试仅创建、删除随机名称且 `--network none` 的本地一次性 PostgreSQL 容器。

## 范围及证据定位

以下简写均指 `hengxin-smart-image/scripts/migration245/` 下的文件；行号按当前候选。

| 简写 | 文件 | 行数 | 原始字节 SHA-256 |
|---|---|---:|---|
| N | build_native.py | 238 | 3ca35f5d4a290dd6a6ee50e124169bd8ad2d8bceb4cc61233010ec7176d244b3 |
| NT | build_native_test.py | 257 | bbe8d7aa886364bb5b1096b280cd83a66044eff6043fa27e45229ba2d9432588 |
| D | data_copy.py | 273 | e0e609bacdc5862801bc54055abccaef6ee1756e4b6b3b4c98479e4f3a7d0688 |
| P | data_policy.py | 117 | 4c7da38a9ac581e6b1ba6581e874a9425018d5d2f8dc3b50261e61b24f8b32b5 |
| ST | data_seed_test.py | 76 | 6912b8951b72124b237c29d49f83f7a5933e002631ce7293f8ba8b781c2f1f48 |

参考测试为同目录 `data_copy_test.py`（DT）；参考迁移为 `hengxin-smart-image/backend/migrations/overseas/versions/0020_skill_availability.py`（M20）和 `0023_skill_platforms.py`（M23）。需求依据为 `Product-Spec.md:1–3`、`docs/INTRANET-245-PLAN-20261110.md` 第 3.2、4、5 节；其他产品功能不属于本次送审范围。

## Stage 1：Spec Compliance — PASS

### 完整实现

| 要求 | 结论及代码、测试证据 |
|---|---|
| 旧生产只读获取，不把写操作发往旧环境 | D:134–138 使用 REPEATABLE READ READ ONLY、超时及 UTC；D:216–226 固定本地 Docker socket 和 PostgreSQL Unix socket，写入要求新端容器前缀及明确库/容器确认。DT:190–197 在真实 PG 注入建表语句，验证只读事务拒绝且表不存在。N:219–230 在读取敏感输入前检查新机 hostname/root/UID/GID；NT:237–253 验证旧 hostname 和错误 UID 均在读取前拒绝。 |
| 七个原生服务按已采集配置重建，不遗漏 drop-in | N:18–24、121–147 精确检查七项集合、四个代码根、fragment/drop-in 来源，按输入顺序保留资源、权限和运行目录指令；仅替换环境、工作目录、命令。NT:122–150 验证资源覆盖顺序、SupplementaryGroups 清空语义、环境替换和七项输出。实际敏感采集包仅位于新机，未作为本地输入验证，见边界。 |
| 修复 WorkingDirectory / EnvironmentFile 的错误引号 | N:39–45、140–143 使用无引号绝对路径，拒绝空白、控制字符、反斜杠、引号、非规范路径，转义 `%`。NT:89–120 既检查路径拒绝，又调用真实 systemd-analyze verify 验证七单元通过、重新加入 WorkingDirectory 引号则拒绝。本轮 WSL systemd 259 实测通过；未声称已验证新机 255。 |
| 环境与 argv 字面值保持，工作节点替换为新机 | N:31–56 对 argv 与环境文件分别转义，N:100–117 修改明确的节点名；NT:74–87、144–150 验证美元、百分号、反斜杠、引号、换行及主机名。语义与官方 [systemd.exec](https://www.freedesktop.org/software/systemd/man/255/systemd.exec.html)、[systemd.service](https://freedesktop.org/software/systemd/man/latest/systemd.service.html) 描述相符。 |
| 海外 UID 1002，保留国内 1001 与旧默认 999，仅新端授权补丁 | N:105–114 将兼容授权服务 allowed-uid 的 999 映射为 1002，并检查集合为 1001/1002；N:15–17、151–161 仅替换已知 BusinessBroker 调用，默认仍为 999。N:224 检查真实用户/组；NT:152–179 验证正确适配、错误 UID、哈希漂移、重复 anchor 拒绝及补丁编译。参考 `backend/app/account_management/service.py:81–95` 已有按 UID 区分业务 manager 的实现，补丁未删除此隔离。 |
| 候选不自动启用消费者，重复/漂移不覆盖 | N:182–216 拒绝已存在候选目录和正式 unit/drop-in，预先验证原源码哈希、记录备份和补丁摘要，再核对 inode/内容后原子替换；不调用 systemctl。NT:192–218 验证候选数量、原件备份、正式 systemd 目录无写入、二次运行与漂移拒绝。 |
| 仅迁认证/授权及海外 Skills 管理数据，业务历史排除 | D:14–42 明确国内/海外各八表白名单及 39/44 表库存；D:109–138 只导出白名单与 skill.* 审计；D:172–190 验证其他表为空或严格初始门闩。DT:142–168、213–228 验证 pending/disabled 原状态、精度、业务记录拒绝及国内往返。 |
| skill.reclaim 的历史业务正文不离开源库，保留审计元数据 | P:12–18、48–81 在源端检查原始字段并投影；D:157–160、P:84–117 验证目标格式和值，目标不再次投影。DT:230–280 在真实 PG 验证 48 条保留、历史正文标记不导出、原库数据未改、字段计数/摘要及未知字段拒绝。此处回归既有 v2 策略，未新增投影规则。 |
| 仅允许迁移自动产生的 15 条 Skill availability 初始行替换 | P:20–40 固定 id/enabled/version/platforms；D:181–188 对完整排序 JSON 集合比较，并要求非空时间、创建不早于 24 小时、更新时间不早于创建且不晚于当前 5 分钟。独立对照 M20:21–24 和 M23:13–50：15 项 ID/平台逐项一致，只有两个初始启用、版本均为 1，非引用应用动态常量。 |
| 非初始目标拒绝，不能覆盖已有测试数据 | D:169 先独占锁所有表，D:172–190 完整前置检查；ST:45–62 验证启停变更、版本变更、平台变更、缺行、多行、过期及 NULL 时间均拒绝且数据保持。初始空表也可导入，适配没有种子的合法候选库。 |
| 15 初始行替换 24 源行，保留源内容/时间并可回滚 | D:194–203 在同一事务内仅按固定 15 ID 删除，然后插入源记录；D:204–212 强制约束并核对全部表的内容、SHA-256、行数，最后 COMMIT。ST:27–43 验证 15→24 全量内容一致；ST:64–72 验证摘要故障后原 15 行及原时间完整恢复；DT:170–188 验证设置种子和 FK 失败回滚。 |

### 部分实现、未实现、Spec 漂移

本次五文件职责内无部分实现、未实现或未授权功能。UID 部署差异对应计划第 4.2 节明确授权；种子兼容用于按真实迁移链建立空库后白名单导入，未增加业务表或页面（N:151–161、D:181–203）。

UI 一致性及引导真实性不适用：五文件没有用户页面、交互入口或设计稿对应物（N:1–238、NT:1–257、D:1–273、P:1–117、ST:1–76）。不以未开发的整站部署步骤冒充这些脚本的缺陷。

## Stage 2：Code Quality — PASS

| 维度 | 证据与结论 |
|---|---|
| 命名、结构、文件长度 | 五文件分别 238/257/273/117/76 行，均不超过 300 行；N 将转义、构建、补丁计划、安装分开，D 将源/目标 SQL 和执行分开，P 固定审计与种子策略；无 any 类型绕过。以编译和 29 个用例验证实际分支。 |
| 测试真实性 | NT:99–120 使用真实 systemd 解析器，包含故障回归负例；ST:37–72 在真实 PostgreSQL 执行事务、删除、插入及回滚。另独立从 M23 AST 提取 INITIAL，验证实现常量与真实迁移相同，避免仅复用 P 常量自证。DT:99–121 的 PG schema 是合成测试夹具，不是完整 Alembic 演练；不扩大该测试结论。 |
| SQL 注入与秘密日志 | D:56–64 对数据 UTF-8 hex 编码、标识符正则限制；P:43–45 仅插入受审常量；D:229–237 屏蔽 PostgreSQL 错误中的业务记录。DT:53–63 验证恶意值及泄密路径。扫描未发现 eval、动态 exec、shell=True 或硬编码真实密钥；NT 中仅合成 secret 字符串。 |
| 文件保护 | N:164–179 拒绝 symlink 路径，独占创建且初始 mode 0600；N:202 候选目录 0700；N:226–229 要求 root 拥有且组/其他用户不可访问的输入。N:209–214 保持原代码权限/属主并原子替换，manifest 只列环境键不列值（N:146–147；NT:150）。 |
| 错误处理与边界 | N:186–216 对存在文件、漂移、跨文件系统失败关闭并保留候选；D:167–212 使用事务保护，摘要失败不提交；D:257–259 限制载荷，D:270–273 非零退出；NT:205–253、ST:45–72 覆盖关键拒绝路径。 |
| 视觉对比 | 不适用；审查范围无页面或邻居页面，依据同 Stage 1 UI 范围说明。 |

## 独立验证原始输出

### Python 编译

执行 `python -m compileall -f`，参数为上述五个文件；exit code 0。原始输出：

```text
Compiling 'hengxin-smart-image/scripts/migration245/build_native.py'...
Compiling 'hengxin-smart-image/scripts/migration245/build_native_test.py'...
Compiling 'hengxin-smart-image/scripts/migration245/data_copy.py'...
Compiling 'hengxin-smart-image/scripts/migration245/data_policy.py'...
Compiling 'hengxin-smart-image/scripts/migration245/data_seed_test.py'...
```

### 原生测试

WSL Ubuntu，Python 3.14.4，systemd 259 (259.5-0ubuntu3.4)；在脚本目录执行 `python3 -m unittest build_native_test -v`，exit code 0。WSL 启动另有本机 localhost 代理提示，不影响解析测试。测试输出原文：

```text
test_argv_exact_percent_dollar_backslash_quotes (build_native_test.NativeTests.test_argv_exact_percent_dollar_backslash_quotes) ... ok
test_bad_paths_command_directives_and_inventory_fail_closed (build_native_test.NativeTests.test_bad_paths_command_directives_and_inventory_fail_closed) ... ok
test_candidates_exclusive_patch_backup_and_second_run_refused (build_native_test.NativeTests.test_candidates_exclusive_patch_backup_and_second_run_refused) ... ok
test_envfile_exact_escaping_and_multiline (build_native_test.NativeTests.test_envfile_exact_escaping_and_multiline) ... ok
test_host_guard_before_reads (build_native_test.NativeTests.test_host_guard_before_reads) ... ok
test_patch_hash_drift_anchor_default_and_syntax (build_native_test.NativeTests.test_patch_hash_drift_anchor_default_and_syntax) ... ok
test_path_directives_have_no_quotes_and_escape_specifiers (build_native_test.NativeTests.test_path_directives_have_no_quotes_and_escape_specifiers) ... ok
test_preflight_drift_and_existing_final_unit_cause_no_writes (build_native_test.NativeTests.test_preflight_drift_and_existing_final_unit_cause_no_writes) ... ok
test_real_account_id_mismatch_refused_before_reads (build_native_test.NativeTests.test_real_account_id_mismatch_refused_before_reads) ... ok
test_real_systemd_parser_accepts_units_and_rejects_quoted_path_regression (build_native_test.NativeTests.test_real_systemd_parser_accepts_units_and_rejects_quoted_path_regression) ... ok
test_uid_adaptation_and_wrong_values_rejected (build_native_test.NativeTests.test_uid_adaptation_and_wrong_values_rejected) ... ok
test_unit_resources_order_and_runtime_configuration_preserved (build_native_test.NativeTests.test_unit_resources_order_and_runtime_configuration_preserved) ... ok

----------------------------------------------------------------------
Ran 12 tests in 0.071s

OK
```

### 数据测试

Windows 本地 Docker，`DATA_COPY_PG_TEST=1`，执行 `python -m unittest data_copy_test data_seed_test -v`，exit code 0。共 17 项，其中 13 项执行真实 PG、4 项普通单元测试；没有 skip。原始输出：

```text
test_assertion_rejects_null_and_false_accepts_true (data_copy_test.PostgreSQLTests.test_assertion_rejects_null_and_false_accepts_true) ... ok
test_business_data_and_dirty_seed_refused (data_copy_test.PostgreSQLTests.test_business_data_and_dirty_seed_refused) ... ok
test_digest_failure_rolls_back_seed_and_insertions (data_copy_test.PostgreSQLTests.test_digest_failure_rolls_back_seed_and_insertions) ... ok
test_domestic_roundtrip_and_pristine_seeds (data_copy_test.PostgreSQLTests.test_domestic_roundtrip_and_pristine_seeds) ... ok
test_empty_version_rejects_source_and_target (data_copy_test.PostgreSQLTests.test_empty_version_rejects_source_and_target) ... ok
test_filter_roundtrip_state_and_precision (data_copy_test.PostgreSQLTests.test_filter_roundtrip_state_and_precision) ... ok
test_foreign_key_failure_rolls_back (data_copy_test.PostgreSQLTests.test_foreign_key_failure_rolls_back) ... ok
test_reclaim_projection_keeps_48_audits_and_verifies_digest (data_copy_test.PostgreSQLTests.test_reclaim_projection_keeps_48_audits_and_verifies_digest) ... ok
test_source_is_read_only_and_catalog_drift_rejected (data_copy_test.PostgreSQLTests.test_source_is_read_only_and_catalog_drift_rejected) ... ok
test_unknown_reclaim_or_normal_fields_rejected_before_export (data_copy_test.PostgreSQLTests.test_unknown_reclaim_or_normal_fields_rejected_before_export) ... ok
test_audit_policy_rejects_business_or_unknown_payload (data_copy_test.UnitTests.test_audit_policy_rejects_business_or_unknown_payload) ... ok
test_errors_do_not_leak_records (data_copy_test.UnitTests.test_errors_do_not_leak_records) ... ok
test_sql_values_are_hex_encoded (data_copy_test.UnitTests.test_sql_values_are_hex_encoded) ... ok
test_wrong_target_refused_before_subprocess (data_copy_test.UnitTests.test_wrong_target_refused_before_subprocess) ... ok
test_digest_failure_restores_all_15_original_seed_rows (data_seed_test.AvailabilitySeedTests.test_digest_failure_restores_all_15_original_seed_rows) ... ok
test_exact_seed15_replaced_by_source24 (data_seed_test.AvailabilitySeedTests.test_exact_seed15_replaced_by_source24) ... ok
test_modified_partial_extra_and_stale_seeds_rejected (data_seed_test.AvailabilitySeedTests.test_modified_partial_extra_and_stale_seeds_rejected) ... ok

----------------------------------------------------------------------
Ran 17 tests in 26.179s

OK
```

独立迁移常量比较输出：

```text
Migration-frozen seed comparison: 15/15 IDs+platforms; enabled 2/15; version 1: PASS
```

## 验证边界

主 Agent 确认真实 source-runtime.json/native-env.json 只在新机受保护目录，本次未读取真实包、未验证新机 systemd 255、实际安装源码、完整 Alembic 链、授权 socket 或消费者启动。N:121–147 的合成配置测试证明构建逻辑，不证明现场七项服务已运行。主 Agent 需在安装启动前对新端真实生成物运行 systemd 255 verify，并按部署验收核对敏感配置、路径、UID/socket 和数据库结果。此为现场交付验证边界，不把本地五文件 PASS 宣称为整个应用或迁移完成。
