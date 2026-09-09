# Harness 独立终审报告

日期：2026-09-09。Reviewer：独立 code-reviewer；使用 `.agents/skills/code-review/SKILL.md`。

candidateId：`f99d6cb15d30998e24cfa5fb26fbf269fbfb272b55aad8474ea72817d93f225a`

**Stage 1：PASS。Stage 2：PASS。阻断问题：无。** 本报告仅审查，不登记批准、不修改代码、不提交。

## 范围及快照

源规格：`docs/HARNESS-REVIEW-PLAN.md:7` 的七项验收，以及 `docs/HARNESS-REVIEW.md:5` 的开发、审查、提交、暂停、存储协议。框架维护任务不以产品 Spec 作为新增功能验收依据。

范围：相对 HEAD 的 AGENTS.md、README.md、.gitignore、dev-builder/bug-fixer/code-review 技能及 reviewer 角色改动；harness.py、review_files.py、review_store.py、review_gate.py、test_harness.py、test_review_gate.py、test_review_recovery.py。后五个新增模块/测试同样纳入审查，未仅依赖 git diff 对已跟踪文件的输出。

开始及结束均独立执行 `harness.py review-status '{}'`，原始关键字段两次一致：

```json
{"currentId":"f99d6cb15d30998e24cfa5fb26fbf269fbfb272b55aad8474ea72817d93f225a","reviewedId":null,"approved":false}
```

审查期间未发现受控快照变化。status 相对原 baseline 额外列出的技能模板/参考 Markdown，在 `git status --short` 中没有改动；它们属于 `review_files.py:23` 新增受控范围带来的差异，不视为本次新增产品功能。产品代码与 hooks.json 无 diff。本报告是普通 Markdown，不改变候选快照（`review_files.py:25`）。

## Stage 1：Spec Compliance

| 验收条目 | 结论与代码证据 | 验证证据 |
| --- | --- | --- |
| 1. prepare 固定哈希、approve 绑定候选/双阶段/报告、拒绝期间改动 | 完整实现。`review_gate.py:21` 校验 JSON 对象，`:31` 固定 candidate，`:34` 至 `:45` 检查编号、文件映射、PASS、报告后批准；`review_store.py:43` 验证仓库内真实报告 | 独立执行 `test_change_during_review_rejects_approval` 通过；全量日志包含 supersedes_old_candidate、failed_or_missing_stage、missing_and_external_reports |
| 2. 文件检测/Stop 不覆盖批准，差异明确，旧 clean 无效 | 完整实现。`harness.py:39` 只取 status；`review_gate.py:8` 保留 approved 优先参考，`:54` 比较当前内容列出文件；`review_store.py:60` 校验报告及状态 | 全量日志 approval_survives_repeated_stop_and_status、status_preserves_previous_approval_after_edit、legacy_clean_cannot_approve_dirty 均 ok |
| 3. 提交核对真实索引，阻止 -a/路径/复合脚本，普通 commit 不失效 | 完整实现。`review_gate.py:72` 用 Git index 与 HEAD 比较后逐文件对照批准版本；`harness.py:90` 限制提交形式，`:176` 先门禁再类型检查 | 独立 index_old_version_worktree_reviewed_new_version_rejected、commit_modes_require_explicit_staging、attached_git_directory_cannot_skip_gate 通过；全量 reviewed_index_commit_does_not_invalidate_stop、partial_commit 用真实临时仓库提交通过 |
| 4. checkpoint 必须原因、同快照一次 Stop、不能批准/提交 | 完整实现。`review_gate.py:46` 设置 id/reason/used，`:59` 消耗或失效，`:72` 提交不读取 checkpoint | 全量 checkpoint_allows_exactly_one_stop_never_commit、checkpoint_invalidated_by_later_change 均 ok；测试实际暂存未审内容并断言提交被拒 |
| 5. 源码/配置/依赖/规则受控，生成文件及普通报告排除，仅归一 CRLF | 完整实现。`review_files.py:8` 至 `:25` 文件范围，`:36` 仅归一 CRLF，`:52` 获取 Git 条目，`:115` 加入未跟踪且非忽略文件；`:101` 不读外部符号链接目录 | 独立 skill_reference_markdown_is_controlled_but_report_is_not 通过；全量 config_and_framework、ignored_generated、crlf_normalized_but_code_whitespace_not_ignored 均 ok |
| 6. 临时仓库覆盖故障路径，保留类型检查和推送保护 | 完整实现。`test_review_gate.py:15`、`test_harness.py:18` 创建独立 temp Git；`test_harness.py:224`、`:233` 测本地编译器选择和失败；`:246` 至 `:278` 测推送开关、分支、退出状态 | 已读取全部三份测试源码及完整 60 项日志；独立抽查 14 项通过，见下方原始输出 |
| 7. 同步规则和文档，不关闭 hook/降低未审检查 | 完整实现。`AGENTS.md:103`、`dev-builder/SKILL.md:83`、`bug-fixer/SKILL.md:32`、`code-review/SKILL.md:48`、`.codex/agents/code-reviewer.toml:23` 改为候选凭据；`README.md:63` 描述行为；`.gitignore:32` 排除运行状态 | git diff HEAD 确认 hooks.json、产品代码未变；旧 clean 授权步骤已替换。实际 review-approve 留给主 Agent 根据本报告执行，未冒称已批准 |

补充协议逐项核对：

- CLI 第二参数 JSON 与 stdin：`harness.py:215` 至 `:223`；run/stop/check_commit 接口及响应字段：`review_gate.py:13`、`:21`、`:54`、`:72`，均匹配。
- status 只读：`harness.py:148` 提前返回，`review_store.py:145` 无 bootstrap、锁、写入；独立 `test_status_performs_no_writes` 在有/无状态两种前提下注入写入/锁失败并通过。
- baseline 仅既有 HEAD：`review_store.py:133` 与 `:153`；初始脏改动、删除、未跟踪均有真实 Git 回归（`test_review_gate.py:57`、`:61`、`:65`）。
- schema、报告哈希、串行原子写：`review_store.py:60`、`:92`、`:107`。独立恢复测试验证报告删改仍阻断，重新 prepare 不擦除旧批准，错误候选/PASS 仍拒绝，并验证并发等待、超时不删除外来锁。
- Git 大小写和紧凑 -C：`harness.py:56`、`:58`、`:93`、`:101`、`:174` 使用不区分大小写检测；`:72` 处理紧凑 -C。独立 `test_git_executable_case_cannot_skip_gate` 经过生产 `handle(pre-tool-shell)` 并对真实未审索引断言 deny。
- 未知 global 参数明确拒绝：`harness.py:174`，独立 test_unknown_git_global_options_fail_closed 通过；Shell 插值/换行/重定向及复合命令拒绝：`:98` 至 `:121`，对应回归通过。

部分实现：无。未实现：无。Spec 漂移：未发现；过期报告恢复与有界锁等待服务于既定凭据/错误恢复职责（`review_gate.py:27`，`review_store.py:116`）。UI、设计稿和邻居页面视觉对比：不适用，本次无页面或产品渲染变更。

## Stage 2：Code Quality

- 质量通过：四个运行模块分别 233/145/156/86 行，三个测试 283/240/133 行，均未超过 300 行；snapshot、store、gate 职责分开。Python 无 TypeScript any 问题。入口异常输出 stderr 并退出 2（`harness.py:228`）；Git 子进程有超时且使用参数数组（`review_files.py:28`）。
- 安全扫描通过：对 `.codex/hooks/*.py` 执行 rg 搜索 eval、DOM 注入、VITE 密钥变量、sk-ant/sk-proj、OpenAI/Anthropic 密钥、硬编码 password，零命中。报告路径/状态结构/外部 symlink 保护分别见 `review_store.py:28`、`:43`、`:60` 和 `review_files.py:101`；未使用 shell=True 或拼接执行 Shell。
- 测试真实性通过：版本不一致用真实 Git blob/index 建立；提交后 Stop 用临时仓库真实 commit；大小写/紧凑参数经过 handle 入口；只读测试明确让潜在写入报错；并发测试用实际线程争锁（`test_review_recovery.py:91`）。类型检查测试使用 Node 小脚本验证编译器选择/退出传播，它们不证明产品 TypeScript 全量编译，本报告不作该声明。推送测试使用 mock，证明调用条件，不声称执行远程推送。
- 边界：本次在 Windows 执行，不声称本轮实测 POSIX 或外部符号链接场景；路径保护已静态核对。协作凭据不是抗恶意篡改签名，符合 `docs/HARNESS-REVIEW.md:31` 明示的协议边界。
- 非阻断日志限制：复用的完整自检日志开头存在旧 `scripts/check_harness.py:14` 未指定编码导致的 gbk 解码线程异常；该文件不在本次修改范围。下面的 unittest 60 项实际全部 OK，独立抽查及语法编译也通过。不能把该日志描述为完全无告警。

## 编译与测试原始结果

本 reviewer 用 Python 3.12 的 compile() 对七个改动 Python 文件逐个内存编译，无字节码写入；退出码 0，原始 stdout：

```text
PASS: 7 Python files compiled (no bytecode writes)
```

独立执行 `python -m unittest` 指定以下 7 项及整个 test_review_recovery 模块；退出码 0，合并两次工具输出如下：

```text
test_git_executable_case_cannot_skip_gate (test_harness.HarnessTests.test_git_executable_case_cannot_skip_gate) ... ok
test_attached_git_directory_cannot_skip_gate (test_harness.HarnessTests.test_attached_git_directory_cannot_skip_gate) ... ok
test_status_performs_no_writes (test_harness.HarnessTests.test_status_performs_no_writes) ... ok
test_unknown_git_global_options_fail_closed (test_harness.HarnessTests.test_unknown_git_global_options_fail_closed) ... ok
test_commit_modes_require_explicit_staging (test_harness.HarnessTests.test_commit_modes_require_explicit_staging) ... ok
test_change_during_review_rejects_approval (test_review_gate.ReviewGateTests.test_change_during_review_rejects_approval) ... ok
test_index_old_version_worktree_reviewed_new_version_rejected (test_review_gate.ReviewGateTests.test_index_old_version_worktree_reviewed_new_version_rejected) ... ok
test_deleted_report_can_be_replaced_after_new_review (test_review_recovery.ReviewRecoveryTests.test_deleted_report_can_be_replaced_after_new_review) ... ok
test_lock_timeout_does_not_delete_foreign_lock (test_review_recovery.ReviewRecoveryTests.test_lock_timeout_does_not_delete_foreign_lock) ... ok
test_modified_report_can_be_replaced_after_new_review (test_review_recovery.ReviewRecoveryTests.test_modified_report_can_be_replaced_after_new_review) ... ok
test_recovery_does_not_relax_candidate_or_stage_guards (test_review_recovery.ReviewRecoveryTests.test_recovery_does_not_relax_candidate_or_stage_guards) ... ok
test_recovery_rejects_corrupt_approval_structure (test_review_recovery.ReviewRecoveryTests.test_recovery_rejects_corrupt_approval_structure) ... ok
test_short_concurrent_transaction_waits_then_succeeds (test_review_recovery.ReviewRecoveryTests.test_short_concurrent_transaction_waits_then_succeeds) ... ok
test_skill_reference_markdown_is_controlled_but_report_is_not (test_review_recovery.ReviewRecoveryTests.test_skill_reference_markdown_is_controlled_but_report_is_not) ... ok

----------------------------------------------------------------------
Ran 14 tests in 14.778s

OK
```

已读取并复用主 Agent 的 `output/harness-review-final-validation.log`，未声称由本 reviewer 重跑 60 项。其测试尾部原始输出：

```text
----------------------------------------------------------------------
Ran 60 tests in 57.267s

OK
PASS: offline harness checks. Runtime discovery/trust: inspect Codex /hooks and /skills.
```

最终结论只适用于上列 candidateId 和范围。由主 Agent 核对当前快照后执行 review-approve；不得把本报告用于批准不同代码版本。
