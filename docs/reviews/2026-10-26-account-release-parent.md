# 发布根目录权限：单行增量审查

- 日期：2026-10-26；使用 `.agents/skills/code-review/SKILL.md`。
- candidateId：`1d1320592afbe88583bf36464b686c0a6c5139de85744f1e0c2cdabc34b682c3`；基线 HEAD `b7cd384`。
- 范围：仅 `scripts/release/account-deploy.py:97` 新增 `host.parent.chmod(0o755)`。既有 AGENTS 修改不属于本轮；未修改代码、未提交、未登记批准。
- **Stage 1 PASS；Stage 2 PASS。无 HIGH/MEDIUM 问题。** 结论只覆盖该增量，不代表正式安装、生产切换或冒烟已完成。
- 原功能及既有发布修正参见 `docs/reviews/2026-10-26-codex-account-management-fixed.md:1`、`docs/reviews/2026-10-26-account-release-command.md:1`、`docs/reviews/2026-10-26-account-release-permissions.md:1`。

## Stage 1：Spec Compliance

本轮逐条核对受影响合同：`Product-Spec.md:1352`、`docs/CODEX-ACCOUNT-MANAGEMENT-20261026.md:9` 发布可用与任务不中断、`:13` 凭据私有边界。

| 条目 | 结论与证据 |
| --- | --- |
| codex 服务可遍历程序发布根目录 | 完整实现。`account-deploy.py:278` 设置 umask 0077，`:96` 的 mkdir(0755) 新建目录实际为 0700；新增 `:97` 显式恢复 0755，允许 `account-runtime.py:154` 的 User=codex 遍历。子目录及代码文件已有 `account-deploy.py:102` 的显式权限设置。主 Agent 的 Linux 临时目录实测输出见下。 |
| 凭据和任务保持 | 完整保持。`:95` 明确指向 `/opt/hengxin-account-releases`；新增 chmod 只作用其本身，不递归。私有目录是 `account-runtime.py:17` 的 `/home/codex/account-management`，仍由 `account-deploy.py:136` 以 0700 建立。新增行不涉及凭据、任务数据或服务切换。 |
| UI、引导与 Spec 漂移 | 本增量无 UI、引导、接口或数据结构改动，仅恢复部署所需权限（`:97`），没有新增产品行为；不适用视觉对比。 |

部分实现：无。未实现：无。Stage 1 无 HIGH，进入 Stage 2。

## Stage 2：Code Quality

- 质量通过：`account-deploy.py:97` 是紧随目录建立的明确权限归一操作；文件实测 300 行，未超过 skill 限制。失败由现有 `:293` 捕获、记录后重抛，不静默跳过。
- 安全通过：0755 不给组或其他用户写权限；作用对象由 `:95` 固定父路径限定，不使用外部 shell 或新增输入拼接。`:100` 至 `:103` 仅安装 daemon/tests 程序代码，私有存储位置与权限保持上述边界。
- 测试真实性：独立运行原发布 6 测试通过；这些测试不是 POSIX 权限行为验证。另采用主 Agent 在 Linux 临时目录的 umask/chmod 实测证据，明确不是 reviewer 远程重测，也不是正式目录生产安装验证。
- UI/邻居视觉对比不适用本单行脚本增量；不重复旧 UI 验收。未重新声明范围外全部产品条目通过。

## 原始验证输出

独立执行 `python -m py_compile scripts/release/account-deploy.py`，stdout/stderr 为空，退出码打印：

```text
PY_COMPILE_EXIT=0
```

独立执行 `python scripts/release/account-tests.py -v`：

```text
test_command_uses_image_default_only_for_null_or_absent (__main__.ReleaseTests.test_command_uses_image_default_only_for_null_or_absent) ... ok
test_frontend_backup_and_rollback_keep_both_generations (__main__.ReleaseTests.test_frontend_backup_and_rollback_keep_both_generations) ... ok
test_frontend_rejects_shared_asset_collision_before_backup (__main__.ReleaseTests.test_frontend_rejects_shared_asset_collision_before_backup) ... ok
test_no_private_root_in_api_overlay (__main__.ReleaseTests.test_no_private_root_in_api_overlay) ... ok
test_patch_preserves_production_only_code (__main__.ReleaseTests.test_patch_preserves_production_only_code) ... ok
test_worker_rollback_refuses_after_account_change (__main__.ReleaseTests.test_worker_rollback_refuses_after_account_change) ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.105s

OK
```

主 Agent 消息提供：服务器 `tempfile.TemporaryDirectory` 内执行 `os.umask(63)`，`parent.mkdir(mode=493)` 后与 `parent.chmod(493)` 后依次输出；未触及生产路径：

```text
0o700
0o755
```

## 快照边界

开始及报告写入后的独立 `review-status` 的 currentId 均与派发一致，changedFiles 仅 `scripts/release/account-deploy.py`，审查中未观察到代码变化。主 Agent 应以该 candidateId 和本报告登记两阶段 PASS，不写 clean；后续代码变化不受本报告覆盖。
