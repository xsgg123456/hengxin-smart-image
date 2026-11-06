# Skill 发布 vendor 单文件依赖修复 · 独立差异审查

结论：**Stage 1 PASS；Stage 2 PASS。** 未发现 HIGH/MEDIUM 阻断项。本报告不代表真实服务器安装测试、真实 catalog 探针或生产部署已经通过。

## 快照与审查范围

- candidateId：`8c22e131deb7f41d8c0e8c739e649ee5d2762bc0d86d088c3ec433a5b7bed1ae`。
- 受控差异仅 `scripts/release/skill-reuse-test.py` 与 `scripts/release/test_skill_reuse_recovery.py`，相对 HEAD `731c84e`。开始、验证后及报告完成后核对 currentId；均匹配该候选，未发现代码漂移。前批准快照为 `fe2bb8c483ca7ef2298789c9fdcfbf38ba6cd09c1db2f0d2602bd43fa52ec826`。
- 已读 AGENTS.md、code-review/SKILL.md、HARNESS-REVIEW.md、实施合同、发布计划、验证记录与前独立审查报告全文，以及 Product-Spec.md、DEV-PLAN.md 本轮条款。未改部分明确沿用 `docs/STUDIO-SKILL-REUSE-FINAL-REVIEW-20261106.md:1` 的结论，本次不冒称重新执行其后端/前端验证。
- 本 reviewer 仅写本报告，未修改代码、登记批准、提交、连接或操作生产。主 Agent 负责对同一 candidateId 执行 review-approve。

## Stage 1：功能与合同

| 检查项 | 结论与证据 |
|---|---|
| py 单文件依赖完整导出 | 匹配。`scripts/release/skill-reuse-test.py:44` 在六个包之外明确加入 py；`:46` 对 py 使用 spec.origin 文件，其他项仍取包目录；`:52` 目标为 py.py。独立执行实际生成的发现代码，断言返回六包与 py 文件，并验证复制后的文件内容；WSL 用例也实际导入该文件。 |
| 白名单与路径验证 | 匹配。`scripts/release/skill-reuse-test.py:53` 同时要求依赖名称在固定列表、源 basename 与目标预期相同；没有允许任意名字或把包目录判定普遍放宽成文件。`:54` 用固定 filename 构造 vendor 目的地。原目录包路径验证保持。 |
| 权限、链接与真实 UID | 匹配。`scripts/release/skill-reuse-test.py:43` vendor 根 0755，`:58` 拒绝链接，`:59` 目录 0755/文件 0644；candidate 根规则 `:69` 未变。`scripts/release/test_skill_reuse_recovery.py:146` 建 py.py，`:147` 让 pytest 导入 py，`:168` 用真实 nobody UID/GID、空附加组运行 Python；`:180` 使用 umask 077；`:191` 断言 py.py 的 0644。独立 WSL 测试执行且未 skip。 |
| 网络、环境、解释器、安装路径隔离 | 匹配、未放宽。`scripts/release/skill-reuse-test.py:23` 校验 UID、app 根、pytest vendor 根；`:28` unshare --net 与 env -i；`:35` 拒绝失败/跳过等不完整结果；`:48`、`:49` 临时 Docker 均无网；`:70` 仅复制 app 源码；`:80` 使用原生 venv 解释器。所有这些代码与前批准版本相同。 |
| 不修改生产依赖或历史数据 | 匹配。`scripts/release/skill-reuse-test.py:41` 将依赖导出到 candidate/vendor；`:54` 只复制到该目录；`:56` 只删除临时创建的容器；没有生产 venv 写入、会话遍历或历史删除。 |
| 海外 Studio 范围、内容身份、A/A 与 A/B/A、升级与重发 | 合同保持。业务模块未发生差异；沿用前报告逐项实现证据，分别为 `hengxin-smart-image/backend/app/overseas/execution/materials.py:22`、`skill_content.py:12`、`skill_cache.py:60`、`:66`、`:72`。此次仅修测试依赖导出，不改内容身份或版本行为。 |
| 私有会话库、只读当前版本、取消选择、两来源与资源命中 | 合同保持。业务与挂载文件未变；沿用前报告 `skill_cache.py:63`、`hengxin-smart-image/backend/app/execution/workspace.py:103`、`hengxin-smart-image/backend/app/execution/persistent_mounts.py:41`、`skill_content.py:20`、`:24`、`:40`、`skill_cache.py:27`、`:69` 的证据。 |
| 原子发布、互斥、异常明确失败、完整校验与拒绝危险文件 | 合同保持。业务文件未变；沿用前报告 `skill_cache.py:27`、`:62`、`:72`、`:81` 与 `hengxin-smart-image/backend/app/overseas/studio/context_fs.py:24`、`:63` 的证据。 |
| 全历史保留、旧会话兼容、既有执行/删除保护 | 合同保持。业务及删除控制器未变；沿用前报告 `skill_cache.py:88`、`hengxin-smart-image/backend/tests/test_studio_skill_cache.py:130` 与 `test_studio_skill_cache_safety.py:159` 的证据。没有批量迁移、回收或即时释放历史空间的新增行为。 |
| 固定包、关门排空、安装恢复、健康与保留验证 | 合同保持。除本次测试 vendor 外的发布 helper 未变；沿用前报告 `scripts/release/skill-reuse-package.py:19`、`skill-reuse-deploy.py:96`、`:118`、`:128`、`:139`、`skill-reuse-native.py:74`、`:96` 的证据。真实运行验收仍须后续执行，不可据本报告跳过。 |
| UI/DB/model/凭据/Skill 内容与 scope | 匹配。实际 diff 无上述文件变化，无新增页面/API/表；引导真实性、设计数值和邻居页面视觉对比不适用。本次没有浏览器验收。计划对 vendor 的描述已同步，业务合同不变。 |

完整实现：本次补齐 py.py 导出、复制和权限回归。部分实现、未实现、Spec 漂移：本次差异未发现。Stage 1 通过后执行以下 Stage 2。

## Stage 2：质量、安全与测试真实性

- 代码质量通过：`scripts/release/skill-reuse-test.py:40` 维持 vendor 单一职责，特殊文件规则只针对明确的 py；两个文件分别 93/195 行，均低于 300 行。未知路径继续明确失败，临时容器仍在 finally 清理（`:50`、`:55`）。两文件 Python 编译通过。
- 安全扫描通过：对两个范围文件搜索 eval/exec、shell=True、危险 HTML、前端敏感变量、密钥前缀、密码赋值及 DELETE/DROP/TRUNCATE，未命中。`scripts/release/skill-reuse-test.py:45` 的执行代码仅由固定白名单构造；Docker 与子进程调用继续使用参数列表（`:48`、`:54`、`:33`）。未新增凭据、shell 插值或数据删除。
- 测试真实性通过：`scripts/release/test_skill_reuse_recovery.py:147` 使 pytest 必须成功导入 py 才产生预期 VALUE，避免仅检查目录可读；`:158`、`:159` 分别复制包目录和单文件；`:168` 真实子进程以 nobody 导入候选 app 与 vendor，`:173` 检查退出码。真实 Linux 内核权限验证未被 mock。
- 测试边界明确：同一用例的 Docker 与 invoke 外围是替身（`test_skill_reuse_recovery.py:151`、`:183`），不证明真实 Docker/原生 venv/pytest 9.1.1/bwrap 已跑通。为补足其未执行发现代码的空白，本 reviewer 另行执行实际生成的 importlib 发现代码，用临时六包与 py.py 断言发现/复制结果；Docker 仍为替身。无生产连接。
- LOW，非阻断格式项：`docs/STUDIO-SKILL-REUSE-RELEASE-PLAN-20261106.md:66` 在 git diff --check 中报告末尾新空行。属于文档格式，不影响候选代码或发布行为；本 reviewer 未修复。
- 视觉对比不适用：`scripts/release/skill-reuse-test.py:1` 与 `test_skill_reuse_recovery.py:1` 均为后台发布/测试脚本，且候选没有 UI 差异。

## 本 reviewer 独立验证原始输出

命令：`wsl -d Ubuntu --cd /mnt/d/Work_Project/hengxin-smart-image python3 -m unittest discover -s scripts/release -p 'test_skill_reuse*.py' -v`，退出 0。WSL 启动还输出本机代理提示（终端编码损坏），下面保留完整 unittest 输出：

```text
test_umask_077_candidate_and_vendor_importable_by_nobody (test_skill_reuse_recovery.CandidatePermissionTests.test_umask_077_candidate_and_vendor_importable_by_nobody) ... ok
test_busy_initial_gate_then_recover_releases_owner_without_mutation (test_skill_reuse_recovery.RecoveryTests.test_busy_initial_gate_then_recover_releases_owner_without_mutation) ... ok
test_missing_gate_marker_with_cutover_evidence_retains_owner (test_skill_reuse_recovery.RecoveryTests.test_missing_gate_marker_with_cutover_evidence_retains_owner) ... ok
test_started_gate_cannot_use_ungated_cancellation (test_skill_reuse_recovery.RecoveryTests.test_started_gate_cannot_use_ungated_cancellation) ... ok
test_ungated_recovery_rejects_changed_originals (test_skill_reuse_recovery.RecoveryTests.test_ungated_recovery_rejects_changed_originals) ... ok
test_api_identity_tracks_restart_even_same_container_and_image (test_skill_reuse_release.ReleaseTests.test_api_identity_tracks_restart_even_same_container_and_image) ... ok
test_backup_tamper_missing_or_added_record_rejected (test_skill_reuse_release.ReleaseTests.test_backup_tamper_missing_or_added_record_rejected) ... ok
test_backups_record_absent_and_preserve_old_bytes (test_skill_reuse_release.ReleaseTests.test_backups_record_absent_and_preserve_old_bytes) ... ok
test_metadata_detects_change_without_reading_private_contents (test_skill_reuse_release.ReleaseTests.test_metadata_detects_change_without_reading_private_contents) ... ok
test_old_nginx_workers_must_exit (test_skill_reuse_release.ReleaseTests.test_old_nginx_workers_must_exit) ... ok
test_package_required_scope_includes_linux_and_catalog_probe (test_skill_reuse_release.ReleaseTests.test_package_required_scope_includes_linux_and_catalog_probe) ... ok
test_proxy_scope_and_ambiguity (test_skill_reuse_release.ReleaseTests.test_proxy_scope_and_ambiguity) ... ok
test_recovery_guard_accepts_absent_original_but_rejects_restart (test_skill_reuse_release.ReleaseTests.test_recovery_guard_accepts_absent_original_but_rejects_restart) ... ok
test_recovery_guard_rejects_unrelated_file (test_skill_reuse_release.ReleaseTests.test_recovery_guard_rejects_unrelated_file) ... ok
test_recovery_pending_job_cannot_reopen_gate (test_skill_reuse_release.ReleaseTests.test_recovery_pending_job_cannot_reopen_gate) ... ok

----------------------------------------------------------------------
Ran 15 tests in 0.368s

OK
UNGATED_RELEASE_CANCELLED_NO_SERVICE_CHANGED
```

直接 `compile(path.read_bytes(), str(path), 'exec')` 编译两份变更文件，并执行上述临时发现/复制验证，退出 0：

```text
COMPILE_PASS files=2
DISCOVERY_AND_COPY_PASS packages=6 single_file=py.py generated_code_executed=True docker_mocked=True
```

Git 格式检查原始诊断（文档 CRLF/LF 提示省略，不将该检查记为全绿）：

```text
docs/STUDIO-SKILL-REUSE-RELEASE-PLAN-20261106.md:66: new blank line at EOF.
```

## 交接

同一候选可登记两阶段 PASS。主 Agent 随后按计划中文提交、重新打包，在真实机器从新准备目录执行 candidate/installed 测试与 catalog 探针；任一失败停止推进。此前服务器缺 py 的失败未被本地测试冒充消除，生产保留、关门、切换和 resume 证据仍须实际取得。
