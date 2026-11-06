# Skill 隔离测试目录属主修复 · 独立差异审查

结论：**Stage 1 PASS；Stage 2 PASS。** 当前差异未发现 HIGH/MEDIUM 阻断项。仅批准源码审查，不代表新正式包安装或生产发布验收通过。

## 快照、范围与依据

- candidateId：`c0d2c7ab07263b3d2a55f85c917d5dee66d3b417c143bac8a5c9ddb8b3da63f4`。
- 基线 HEAD：`db56bf1`。受控差异仅 `scripts/release/skill-reuse-test.py:21` 的属主选择/调用顺序和 `scripts/release/test_skill_reuse_recovery.py:126` 新测试，共一行替换、24 行新增。普通 Markdown 验证记录的增补不属于代码快照。
- 审查开始、测试后 currentId 均匹配交接；报告写入后再次核对。未观察到代码变化。由主 Agent 登记同一候选的 review-approve；本 reviewer 不写 clean、不修代码、不 commit、不操作生产、不 spawn。
- 已读 AGENTS.md、code-review SKILL.md、HARNESS-REVIEW.md、Product-Spec.md/DEV-PLAN.md 本轮条款、实施合同、发布计划、验证记录、FINAL-REVIEW 和 VENDOR-REVIEW 原文。
- 未变化功能沿用 `docs/STUDIO-SKILL-REUSE-FINAL-REVIEW-20261106.md:24` 的逐条审查，以及 `docs/STUDIO-SKILL-REUSE-VENDOR-REVIEW-20261106.md:14` 的依赖修复审查；本次不冒称重复执行全部前后端验证。

## Stage 1：功能及隔离合同

| 条目 | 结论、代码位置与验证 |
|---|---|
| 实际执行身份拥有私有 scratch | 匹配。`scripts/release/skill-reuse-test.py:19` 仍创建 0700；`:21` 先选择实际 UID；`:22` 服务分支使用服务 UID/GID，root 分支使用 0/0。新测试 `scripts/release/test_skill_reuse_recovery.py:136` 遍历两分支，`:140` 实际 stat 并核对属主、组、0700。独立 Linux 运行通过。 |
| 服务用户执行和 root 补充测试分别保留 | 匹配。`scripts/release/skill-reuse-test.py:28` 服务分支仍 runuser，root 分支仍保留外部 root；`:24` 断言 UID；`:32` root 只跑 Linux 文件。candidate 的两次调用 `:80`、`:81` 和 installed 的 `:91`、`:92` 均未改。测试 `test_skill_reuse_recovery.py:144` 检查生成的 UID 断言。 |
| 无网、清空环境、原生解释器与指定安装路径 | 匹配、未放宽。`skill-reuse-test.py:25`、`:26` 校验 app/pytest 来源；`:28` unshare --net、env -i；`:30` 禁用插件自动加载；`:80`、`:91` 仍使用原生 venv。此次仅变 scratch 属主。 |
| 安装测试失败不得产出通过标记 | 匹配。`skill-reuse-test.py:35` 要求退出 0、含 passed 且无 failed/skipped/xfail/xpass；`:82`、`:93` 在两身份调用成功后才写通过标记。未修改失败判定。 |
| 仅海外 Studio、完整内容身份、A/A 与 A/B/A、内容变更新版及同内容重发 | 合同保持，无业务文件 diff。沿用 FINAL-REVIEW 对 `hengxin-smart-image/backend/app/overseas/execution/materials.py:22`、`skill_content.py:12`、`skill_cache.py:60`、`:66`、`:72` 的逐条证据。 |
| 会话私有、只挂当前只读版本、取消选择隐藏、两来源与命中资源不重复下载 | 合同保持，无业务/挂载文件 diff。沿用 FINAL-REVIEW 对 `skill_cache.py:63`、`:27`、`:69`、`skill_content.py:20`、`:40`、`hengxin-smart-image/backend/app/execution/workspace.py:103`、`persistent_mounts.py:41` 的证据。前述三个短文件名均位于 backend/app/overseas/execution。 |
| 暂存/校验/原子发布、互斥、危险文件/越界/损坏拒绝、异常明确失败 | 合同保持。沿用 FINAL-REVIEW 对 `hengxin-smart-image/backend/app/overseas/execution/skill_cache.py:27`、`:62`、`:72`、`:81` 和 `hengxin-smart-image/backend/app/overseas/studio/context_fs.py:24`、`:63` 的证据；相关文件未改。 |
| 全历史保留、旧会话下轮复用、执行互斥与删除兼容，不批量迁移或回收 | 合同保持。沿用 FINAL-REVIEW 对 `hengxin-smart-image/backend/app/overseas/execution/skill_cache.py:88`、`hengxin-smart-image/backend/tests/test_studio_skill_cache.py:130`、`test_studio_skill_cache_safety.py:159` 的证据；本次 chown 只作用于刚创建的随机隔离 scratch（`skill-reuse-test.py:18`），不遍历历史。 |
| 固定包/白名单、真实路径安装、关门排空、温和停机、恢复、健康及保留验证 | 合同保持。未改其它发布工具；沿用 FINAL-REVIEW 对 `scripts/release/skill-reuse-package.py:19`、`skill-reuse-deploy.py:96`、`:118`、`:128`、`:139`、`skill-reuse-native.py:74`、`:96` 的证据。修改同时覆盖 candidate 和 installed scratch；实际新包安装仍必须完成。 |
| 不改 UI、DB、模型、凭据、技能内容及不扩展范围 | 匹配。diff 仅发布隔离测试与其回归；`docs/STUDIO-SKILL-REUSE-20261106.md:12` 的边界保持。无新页面/API/表，UI 文案、设计数值、邻居渲染比较不适用。 |

完整实现：本次 scratch 属主修复及两身份 Linux 回归。部分实现、未实现、Spec 漂移：本差异未发现。Stage 1 通过后执行 Stage 2。

## Stage 2：代码质量、安全、测试真实性

- 代码质量通过：`scripts/release/skill-reuse-test.py:21` 将 UID 选择置于 chown 前，服务身份数据仍来自现有账号查询；没有扩大 helper 职责。两文件为 93/219 行，低于 300 行；两文件编译通过。
- 安全扫描通过：两文件未命中 eval/exec 调用、shell=True、危险 HTML、前端 KEY/SECRET/TOKEN、密钥前缀、密码赋值或危险 SQL 模式。核心安全证据为 `skill-reuse-test.py:18` 随机新目录、`:19` 0700 未变、`:22` 仅匹配执行身份、`:28` 参数列表及网络/环境隔离未变。本次没有权限放宽、生产目录 chown 或凭据读取。
- 测试真实性通过：`test_skill_reuse_recovery.py:126` 明确要求 Linux root，`:132` 用系统 nobody 替代服务账号，`:142`、`:143` 直接验证真实 chown/stat 的 UID/GID/mode；没有 mock chown 或 stat，独立 WSL 运行未 skip。两分支均调用真实 invoke，能检测旧代码让 root scratch 归服务用户的错误。
- 测试边界：`test_skill_reuse_recovery.py:147` mock subprocess.run；`:144` 检查的是命令内 UID 断言，未实际执行该命令。本次 16 项本地测试不能证明真实 unshare、生产 UID999、原生 venv 或 Bubblewrap 运行成功。既有权限回归 `:192` 使用真实 nobody 子进程导入候选/vendor，但仍不是生产安装验收。
- 视觉对比不适用：两文件均为后台发布与测试脚本，无 UI diff。
- git diff --check 退出 0，仅输出验证 Markdown 的 CRLF/LF 转换提示，无空白错误。

## 本 reviewer 独立验证原始输出

命令：`wsl -d Ubuntu --cd /mnt/d/Work_Project/hengxin-smart-image python3 -B -m unittest discover -s scripts/release -p 'test_skill_reuse*.py' -v`，退出 0。WSL 另输出终端编码损坏的本机代理提示，以下为完整 unittest 原始输出：

```text
test_invoke_private_scratch_owned_by_execution_uid (test_skill_reuse_recovery.CandidatePermissionTests.test_invoke_private_scratch_owned_by_execution_uid) ... ok
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
Ran 16 tests in 0.406s

OK
UNGATED_RELEASE_CANCELLED_NO_SERVICE_CHANGED
```

使用 `compile(Path(p).read_bytes(), p, 'exec')` 编译两份变更文件，退出 0，原始输出：

```text
COMPILE_PASS files=2
```

## 生产证据边界与交接

`docs/STUDIO-SKILL-REUSE-VALIDATION-20261106.md:25` 记录旧正式包 db56bf1 的服务 UID999 74/74、额外 root 失败，以及仅更改隔离 scratch 属主后的原包 root 2/2 诊断。该证据来自主 Agent，本 reviewer 未连接服务器复核。诊断不替代当前候选的新固定提交、新正式包完整 candidate/installed 测试与真实 catalog 验证。

截至交接记录，生产仍未关门或切换（验证记录 `:25`）。两阶段 PASS 仅允许主 Agent 对本 candidate 登记批准；随后按 `docs/STUDIO-SKILL-REUSE-RELEASE-PLAN-20261106.md:18` 至 `:25` 执行新包完整安装与发布。不能用本报告或 2 项诊断跳过任何安装/保留/健康门禁。

