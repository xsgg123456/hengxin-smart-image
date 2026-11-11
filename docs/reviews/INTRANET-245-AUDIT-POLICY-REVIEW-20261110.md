# 内网 245 数据审计投影 v2 独立审查

- 最终 candidateId：`6a6dcaaed4f4e40ccbf7ccb533ee68f7de8ab60bbaf96ea0301002c1dfd1c9ed`；初始送审 candidateId：`319b0fa9bbd19c03f6daf94adab675f285a7e709955d64ec698e2816eb0af004`。
- 范围仅为 `hengxin-smart-image/scripts/migration245/data_copy.py`（下文 D）、`data_policy.py`（P）、`data_copy_test.py`（T）；以下缩写加行号均指该目录完整路径。没有审查或批准 `build_native.py`、`build_native_test.py`。
- 依据：`docs/INTRANET-245-PLAN-20261110.md:100、132、140、143`；前版已有 [部署模块两阶段审查](INTRANET-245-DEPLOYMENT-REVIEW-20261110.md)，本次完整阅读三文件，重点复核新投影及原事务保护回归。
- 结论：**本范围 Stage 1 PASS；Stage 2 PASS。** 无 HIGH/MEDIUM 问题。仅准入指定代码，不代表实际服务器迁移或部署验收完成。
- 审查期间没有连接生产、修改实现或提交；仅运行本机隔离 PostgreSQL 16 与内存编译。48 条生产盘点来自主 Agent 的只读实查交接，审查员独立验证的是同形合成夹具，不宣称亲自复核生产内容。

## 快照边界

开始审查的 `review-status.currentId` 与初始送审候选一致。验证后全局候选曾变为 `8ebd129dc92621b8fa7f1ede5bb96f3883a2bb8c58c832de7c6259f3f3025e1c`，变化清单新增范围外 native 模块。主 Agent 暂停写入并重新固定最终候选 `6a6dcaaed4f4e40ccbf7ccb533ee68f7de8ab60bbaf96ea0301002c1dfd1c9ed`；审查员再次执行 review-status 确认 currentId 完全一致，并重新计算三文件原始哈希，全部未变，故两阶段结论适用于最终候选中的这三文件。native 两文件未纳入批准。三份审查文件前后原始 SHA-256：

| 文件 | 原始 SHA-256 |
|---|---|
| D | `7120BC2BB2C18EDF37F1876771F4C94D5093B6B7CCFA695A90A0B44758BDC672` |
| P | `A4B8C4D3A144BD349055BF5CEFBE44630E705D596FF48DD78702E58F544B4468` |
| T | `B95F53C1C527313E17A660F92E3BB04FD6529A2FF4E4D9491BCD863B6C7F2C16` |

最终批准由主 Agent 合并其他范围报告并用 `review-approve` 登记同一最终候选；审查员未写 `.needs-review` 或登记批准。

## Stage 1：Spec Compliance — PASS

| 要求 | 判定和证据 |
|---|---|
| 保留 skill.* 管理审计，排除 studio.* 业务审计 | 完整实现。D:109–114 仍按 action 过滤，没有丢弃整条 reclaim；P:43–47 仅替换 before/after。T:230–265 实际 PostgreSQL 导出 48 条，校验普通审计保留及 reclaim 的 ID、actor、target、时间不变。 |
| 只保留必要 Skill 元数据，旧业务正文不出源 | 完整实现。P:8–18 固定普通/原始 reclaim/投影白名单；P:45–47 仅保留 release、容量、清理结果、dryRun 等 8 类元数据；P:75–95 拒绝嵌套业务对象及不合法值。T:234–261 将业务 marker 注入所有排除字段，导出全包无 marker，而源 jobs 字段仍保留 marker。D:241–243 在输出前验证值。 |
| 原始字段未知时拒绝，不能先投影后掩盖漂移 | 完整实现。D:134–138 在同一 RR READ ONLY 事务中先 schema guard、再 P:26–39 原始 JSON 类型/键守卫、最后生成包；P:32–33 按 action 区分白名单。T:267–280 真实 SQL 覆盖 reclaim before/after 未知字段、NULL 和普通 audit 夹带 jobs 的拒绝。 |
| 记录字段变换及计数，不带业务值 | 完整实现。P:50–59 仅生成 reclaim_rows、排除字段名与计数；P:62–72 严格检查结构、字段集合及计数范围。D:130、159–160、250–252 携带和输出报告。T:254–258 精确断言字段计数；独立 5 个异常报告输入均拒绝，见验证输出。 |
| 源只读、同一快照、保留原记录 | 完整实现。D:135–138 只读可重复读事务和限时；所有投影均 SELECT，没有源 UPDATE/DELETE。T:190–197 验证写入被真实数据库拒绝；T:261 验证被省略正文仍留在源记录。 |
| 目标不重新投影，按导出结果核验 | 完整实现。D:164–201 原事务导入，rows_query(..., False) 对完整目标审计核对行、count、SHA-256；D:110 的 filtered 条件阻止目标投影。T:263–265 导入后摘要往返一致，查询不含 reclaim 分支。 |
| 非空目标、FK、摘要失败、NULL 门禁仍有效 | 完整实现。D:167–200 锁表、查空、正常约束和提交前核验不变。T:159–188、199–211 真 PG 验证拒绝旧业务/脏种子、摘要/FK 失败回滚、空版本及 NULL/false 拒绝。 |
| 国内与普通 audit 行为保持 | 完整实现。P:27–28 国内没有审计投影，P:51–52 国内报告为零；P:47 普通行原样 JSONB 输出；T:142–155、213–228 验证禁用状态、高精度 JSON、国内 pending 和种子行为。 |

未实现：指定差异范围无。Spec 漂移：无新增产品页面/API/表；审计包版本标记和变换报告落实计划第 5 节，不扩张迁移范围（D:130、P:7）。UI 一致性、引导真实性和邻居页面视觉对比不适用：本次全部是离线迁移脚本，无 UI。

## Stage 2：Code Quality — PASS

- 结构：D 262 行、P 95 行、T 284 行，均小于 300。投影和字段策略独立在 P:1–95，SQL/导入执行仍由 D 负责；常量生成 SQL 字段集合，无业务包输入参与标识符拼接（P:21–23、D:61–64）。
- 安全：三文件逐行阅读及危险模式检索未发现硬编码真实密钥、eval/exec、shell=True 或前端秘密暴露。D:56–58 以 UTF-8 hex 保留输入且隔离 SQL/psql 注入；D:218–226 隐藏数据库原始错误；P:83–95 限制保留元数据的值形态。固定 Docker/socket 路径为已授权部署隔离边界（D:205–215）。
- 测试真实性：T:69–91 创建独占随机容器，network none、无发布端口、tmpfs，只清理自身容器；T:230–280 走真实生成 SQL，非纯字符串模拟。14 项全部实际执行，无 skip；另独立验证 4 个异常行值和 5 个异常变换报告均拒绝。
- 测试边界：T:99–120 自建表/部分 FK，不能替代真实完整 Alembic 迁移链验收；48 条夹具是 47 条普通加 1 条 reclaim，并非生产数据库副本。源导出文件的权限、跨 DB/文件一致性和真实上线验收沿用前版报告的部署层前置。
- 未发现需要修复的代码质量或安全问题。没有执行范围外 native 模块测试，不能从本报告推导其通过。

## 原始验证输出

本机执行 `DATA_COPY_PG_TEST=1 python -B -m unittest data_copy_test -v`，退出码 0，输出：

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

----------------------------------------------------------------------
Ran 14 tests in 15.603s

OK
```

三个源文件用 Python `compile()` 内存编译，退出码 0，无 stderr：

```text
compile PASS: data_copy.py
compile PASS: data_policy.py
compile PASS: data_copy_test.py
```

独立失败输入检查（嵌套 centralBytes、字符串 dryRun、未知字段、historyContents，以及缺报告/bool 计数/正文计数/越界计数/未知计数字段），退出码 0：

```text
independent malformed row/report cases rejected: 9
```
