# 安装测试执行器增量审查

- 日期：2026-10-26；使用 `.agents/skills/code-review/SKILL.md`。
- candidateId：`f75590f8ed2c4ee350fab8f4b908796b26d535ca87f88626347491138020d6d8`；基线 HEAD `0a948fd`。
- 范围：仅 `git diff HEAD -- scripts/release/account-installed-tests.py`。AGENTS.md 既有改动不属本轮；无代码修复、提交或批准登记。
- **Stage 1 PASS；Stage 2 PASS。无 HIGH/MEDIUM 问题。** 本结论是执行器修正审查，不是最终提交重新打包后的正式发布验收。
- 既有主功能与发布审查沿用 `docs/reviews/2026-10-26-codex-account-management-fixed.md:1`、`2026-10-26-account-release-command.md:1`、`2026-10-26-account-release-permissions.md:1`、`2026-10-26-account-release-parent.md:1`。

## Stage 1：Spec Compliance

受影响合同为 `Product-Spec.md:1352` 的测试通过后发布，以及 `docs/CODEX-ACCOUNT-MANAGEMENT-20261026.md:9` 发布验证和 `:13` 凭据私有边界。范围外产品条目不重复声明验收。

| 条目 | 结论与证据 |
| --- | --- |
| 有限 PATH 下可执行非 root 测试 | 完整实现。`scripts/release/account-installed-tests.py:8`、`:15` 使用 `/usr/sbin/runuser`，不依赖 `:14` 不含 sbin 的 PATH；同一命令保留 `-u codex`。主 Agent 的实际目标 Linux 安装测试输出见下。 |
| 真实 UID 测试不能被跳过 | 完整实现。`:16` 仅将命名的 root 用例从 codex 运行中排除；`:19` 用完整 node id 单独执行该用例；`:22` 要求 1 passed 且无 skipped。`scripts/release/account-deploy.py:277` 保证入口为 root。`backend/tests/test_credential_broker.py:212` 明确要求 root，`:214` 的用例实际以子进程 setuid 切至 1001、999、1002（`:225`），检查 master 拒读、授权 UID 获得无 refresh token 的结果、未授权 UID 被拒绝；这些 UID 与 `account-runtime.py:10`、`:12` 的 worker 一致。 |
| 保留其余测试与失败关闭 | 完整实现。`:17` 继续拒绝 skipped/failed；`account-runtime.py:29`、`:30` 对每条命令先检查退出码，测试异常、失败或找不到 node 均不能放行。四个既有测试文件仍由 `account-package.py:74` 打包。目标 Linux 的 96 passed + 1 deselected，加 root 的 1 passed，覆盖原 97 项。 |
| 安装证据仍在全部验证后写入 | 完整实现。`:23` 合并两段原始测试输出，`:24` 保存私有日志；`:27` 保留 API 源码摘要校验，`:32` 对两个隔离镜像导入；全部成功后 `:35` 才写绑定 manifest/images 的 PASS。`account-deploy.py:119` 先校验安装状态，`:124` 启动前再匹配证据。 |
| 不接触生产凭据和任务数据 | 完整保持。root 用例的 `running` fixture（`backend/tests/test_credential_broker.py:24`）使用 TemporaryDirectory、合成 auth、临时 socket，并禁止真实 refresh；新增 root 调用只选该用例。`:32` 的 API 镜像仍无网络、只读、无生产挂载。 |
| UI、引导及 Spec 漂移 | 不适用 UI/视觉对比；该 37 行 helper 只修复安装验证方式，没有增加页面、接口、数据表或产品行为（`:5`）。 |

部分实现：无。未实现：无。Stage 1 无 HIGH，进入 Stage 2。

## Stage 2：Code Quality

- 质量通过：`account-installed-tests.py:13` 复用唯一测试名，`:14` 复用两次运行的最小环境；完整 helper 37 行，职责集中，无新增依赖。异常由现有 `account-runtime.py:23`、`:28` 与部署入口 `account-deploy.py:293` 处理。
- 安全通过：新增调用均是参数数组，无 shell 拼接、eval、SQL、硬编码真实密钥。`:8`、`:15` 的绝对路径是目标 Linux 系统程序位置，不是开发者私有路径。root 运行范围为已安装且有摘要检查的测试（`account-deploy.py:21`），fixture 不读真实 master。
- 测试真实性通过：独立执行发布 6 测试及语法编译；另用内存 Runtime 替身执行真实 helper 的 7 种流程，确认命令选择、环境相同、两段日志先于 PASS、codex/root 跳过或命令失败、API 返回错误或摘要漂移时都不写新 PASS。替身验证的是编排和失败门禁，不能冒充 Linux setuid 实测。
- 真实 Linux 数据来自主 Agent 的现有安装日志读取与执行输出，非 reviewer 独立远程重测。真实 UID 测试仍以 root fixture/GID 0 模拟 socket 可达环境，证明 UID allowlist 与 master 私有读取边界，不单独证明正式 systemd 的完整组配置；本增量未改变该测试语义。
- 未重复 UI 和邻居页面测试：单文件运行工具增量没有视觉行为。

## 原始验证输出

reviewer 独立运行 `python -m py_compile scripts/release/account-installed-tests.py`，stdout/stderr 为空，退出码：

```text
PY_COMPILE_EXIT=0
```

reviewer 独立运行 `python scripts/release/account-tests.py -v`：

```text
test_command_uses_image_default_only_for_null_or_absent (__main__.ReleaseTests.test_command_uses_image_default_only_for_null_or_absent) ... ok
test_frontend_backup_and_rollback_keep_both_generations (__main__.ReleaseTests.test_frontend_backup_and_rollback_keep_both_generations) ... ok
test_frontend_rejects_shared_asset_collision_before_backup (__main__.ReleaseTests.test_frontend_rejects_shared_asset_collision_before_backup) ... ok
test_no_private_root_in_api_overlay (__main__.ReleaseTests.test_no_private_root_in_api_overlay) ... ok
test_patch_preserves_production_only_code (__main__.ReleaseTests.test_patch_preserves_production_only_code) ... ok
test_worker_rollback_refuses_after_account_change (__main__.ReleaseTests.test_worker_rollback_refuses_after_account_change) ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.104s

OK
```

reviewer 独立执行内存 Runtime 替身编排检查：

```text
PASS success_order_and_coverage
PASS normal_skip
PASS normal_error
PASS root_skip
PASS root_error
PASS api_error
PASS api_drift
```

主 Agent 读取 `/opt/hengxin-releases/account-management-20261026-0a948fd/work/installed-linux-tests.txt` 提供的原始片段：

```text
96 passed, 1 deselected in 4.85s
Root-only UID isolation:
. [100%]
1 passed in 0.30s
```

主 Agent 执行上传至临时目录的修正 helper，针对现有不可变安装源码及两 API 镜像的完整结果：

```text
INSTALLED_DAEMON_AND_API_IMPORTS_PASS
```

上述 Linux 结果验证本修正可执行；最终发布仍须从审查后最终提交重新打包，并针对最终安装再生成对应证据。本报告不将临时 helper 的运行直接认定为最终包验收。

## 快照边界

审查开始和报告完成时 `review-status` 的 currentId 均为本报告 candidateId，changedFiles 仅 `scripts/release/account-installed-tests.py`；审查中未观察到代码变化。主 Agent 应按该 candidateId、本报告和两个 PASS 登记批准，不写 clean。后续代码变化需重新固定快照复核。
