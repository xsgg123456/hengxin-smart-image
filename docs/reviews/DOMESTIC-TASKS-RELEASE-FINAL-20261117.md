# 国内任务专项发布最终独立审查

- candidateId：`bdc78af52f5564caa852690e03d2626b14a94ce73ff07e295256dcc2bff51fe5`。
- 日期：2026-11-17。使用 code-review、release-builder Skill；fresh reviewer 独立读取实现和调用链，未直接沿用初审结论。
- 范围：`scripts/release/intranet/` 本次5个既有文件修改、5个新增运行模块、7个专项测试；0044固定hash、dingtalk两条国内返回路径例外；只读追踪既有engine/scope/锁/备份/台账/GC。另审不纳Git的 `output/install-tasks-tools.py`。产品API/UI由另一独立reviewer负责。
- 依据：Product-Spec.md新增国内任务合同、专项维护方案全部规划及恢复条目、AGENTS生产规则、内网工具说明、最近国内角色发布验收及初审问题。
- 结论：**Stage 1 PASS；Stage 2 PASS。此范围未发现 HIGH/MEDIUM 阻断。** 这是实现与隔离测试审查，不代表生产安装、迁移、切换已经执行。
- 未修改代码、未提交、未写clean、未生产写入。由主Agent将同一candidate与产品审查合并登记批准。

## Stage 1：需求符合性

以下未写全前缀的发布文件均位于 `scripts/release/intranet/`；迁移及应用文件位于 `hengxin-smart-image/backend/`。

| 合同条目 | 结论与证据 |
| --- | --- |
| 固定国内0043基线、唯一入口 | 完整。domestic_tasks_release.py:53校验版本2台账、无pending、0043、固定国内提交、publisher及已stage候选；:220仅接受domestic/full。release_cli.py:21校验主机/root，:26持既有全局发布锁。 |
| 固定0044和登录例外，不放开普通发布 | 完整。domestic_tasks_policy.py:7固定基线及迁移/登录前后hash；:19比较其余迁移、依赖、runtime inputs；:31仅过滤0044再走普通ownership。scope_changes.py:171仍拒绝unknown和未批准共享改动；允许完整包携带未被国内加载的独占海外代码不等于部署海外。app/modules/auth/dingtalk.py:24实际只增加task-center/workspace-sessions返回路径。 |
| Hash真实性 | 独立计算0044原始/LF SHA均为 `c6a9fb63e97f4b9460ebc37667a4116ae72bd380574f7baa0770093534bf0d01`；dingtalk LF SHA为 `ef7cbbbffd754d9e552117e15487a896b088927261847524edf8ca1e9b6a29a1`，匹配policy。dingtalk工作区CRLF原始hash不同，正式Git包仍须检查归档内容。 |
| 持久事务和普通操作互锁 | 完整。domestic_tasks_release.py:66先写preparing，:73绑定pending；:159覆盖准备、取消/恢复台账中断及ledger-writing。domestic_tasks_marker.py:19、release_cli.py:40、full_cleanup.py:14阻断未完成维护时普通发布/回退/恢复入口/清理。test_domestic_tasks_state.py:41起覆盖故障分支。 |
| 仅国内入口关闭、排空、停止 | 完整。scope_engine.py:138绑定国内APPS/NATIVE/ENTRIES；scope_actions.py:27仅排空国内worker，:35在domestic上下文不关闭共享凭据socket。专项不调用共享release-gate关闭。engine.py:147起保持入口关闭→排空→停止。hengxin-smart-image/scripts/migration245/unify_release.py:444保留SendSIGKILL=no及容器宽限停止，无新增强杀。 |
| 持久停机围栏与重启窗口 | 完整。domestic_tasks_engine.py:36保存完整策略并禁国内容器自动重启；:60核原生PID/cgroup和容器停止；:119加入无法满足的ConditionPathExists。joint_studio_credentials.py:16检查MainPID及cgroup后代进程。engine.py:161起安装全部新drop-in/compose，scope_actions.py:76才解除围栏启动。未执行真实宿主重启演练。 |
| 初审HIGH-1：重启策略实际恢复 | 已修复并独立实测。scope_actions.py:82、:85经u.app_command实际分派到domestic_tasks_engine.py:121 force-recreate；:16、:28核完整RestartPolicy及MaximumRetryCount；:133、:137覆盖首次启动/既有applied回执。真实Docker四项重现普通up保留restart=no，并验证迁移前失败恢复、候选成功及提交后前向恢复，海外/shared身份和策略保持。 |
| 国内备份与单事务迁移 | 完整。domestic_tasks_engine.py:68、:82在停止后备份domestic、核大小/hash、采集历史，再upgrade0044。operations.py:52调用pg_dump -Fc及pg_restore --list，不备份/恢复海外。migrations/env.py:39起以同一事务及咨询锁执行。专项没有自动restore调用。 |
| 文件锁和DB锁 | 完整。domestic_tasks_release.py:85、:126、:195持迁移文件锁；domestic_tasks_engine.py:92传descriptor到子进程。joint_studio_fence.py:26不显式unlock继承锁，:54等待DB事务；guarded_recover及recover先等待已有迁移再核schema。本reviewer未把mock迁移用例称为真实数据库验证。 |
| 历史行及归属 | 发布验收实现完整。domestic_tasks_history.py:17对所有既有domestic_studio表确定排序计数/hash，只排除新增task_id和两张新表；:37核归属和成员/业务组数量。0044_domestic_tasks.py:49增加并回填关联，保留旧ID；:67复合FK保证归属。数据库业务完整性另由产品reviewer审查。 |
| 提交前恢复、提交后仅前向 | 完整。domestic_tasks_engine.py:148仅旧schema允许engine.recover，提交后关闭国内入口并拒绝旧恢复；:166复核prepared/config/manifest，只安装同一候选。domestic_tasks_release.py:200区分0043/0044/未知schema，未知拒绝自动恢复。scope_release.py:52拒绝普通跨schema rollback。 |
| 初审HIGH-2：全量配置隔离 | 已修复。domestic_tasks_release.py:90从完整before.configs构造精确预期，只替换prepared中的compose及国内三个source drop-in，然后完整比较；:99核runtime和海外/shared组/fallback；:106核非目标容器和进程身份。test_domestic_tasks_verify.py:47起新增/删除/修改矩阵及国内错误hash全部拒绝，本轮重跑通过。 |
| finish失败关闭、close后重试 | 完整。domestic_tasks_release.py:109在capture/verify/catalog/ledger/marker异常时只stop国内ENTRIES，保留worker；:125先核迁移/applied候选，再只启动实际停止的入口、核策略并完整capture/verify。test_domestic_tasks_finish.py:52覆盖各失败；:78重试顺序；:100候选漂移保持关闭；:123台账已写而complete标记失败重入；:132入口stop失败保留pending。 |
| 清理失败不撤成功 | 完整。domestic_tasks_release.py:122将cleanup放在失败关闭块外；test_domestic_tasks_finish.py:114验证已成功后cleanup失败不关闭入口。既有release.py:171起将自动清理失败记录warning，不恢复旧业务。 |
| 成功台账、GC两版 | 完整。domestic_tasks_release.py:141起先verify、advance、ledger-writing、写台账、complete，最后cleanup。scope_catalog.py:30只推进国内组current/previous；:50保留全部组两版及staged/pending引用。full_cleanup.py:20实时核验，:23同口径计量，:64计算包含回执的净释放。139项scope/catalog/GC回归通过；实际生产净释放仍待部署验收。 |
| Spec漂移、UI与引导 | 无本范围漂移。新增五个tasks命令对应专项方案；发布CLI无产品页面或占位引导，UI设计/邻居视觉比较不适用，交产品reviewer执行。 |

## Stage 2：质量、安全、测试真实性

- 质量通过：五个新运行模块22–231行，分别负责policy/marker/history/engine/orchestration；七个测试71–156行，均低于300行。domestic_tasks_release.py:109清楚区分迁移后恢复与成功后清理；上下文适配用scopes.replace恢复原函数。无新外部依赖或any类型逃逸。
- 安全通过：domestic_tasks_history.py:24对动态表名先完整正则校验，其余SQL固定；命令使用argv，无shell=True。domestic_tasks_engine.py:68校验备份证据，:148拒绝自动DB倒灌。扫描新增运行模块未命中eval/exec/shell=True/硬编码密码/token模式；生产绝对路径是受控部署合同。新文件未输出用户行/凭据。
- 测试真实性通过：test_domestic_tasks_restarts_docker.py:40使用随机独立Compose项目，无端口/挂载/持久卷；真实engine journal、Actions分派及Docker操作，native/schema/health明确模拟。:101检查目标恢复与非目标不变，:86清理并核容器/网络为空。本reviewer实际再跑四项通过，并再次确认随机测试容器/网络为零。
- 边界：没有实际生产重启、工具安装、排空、0044迁移或GC。作者维护文档中504 passed/15 subtests/4 skip，以及真实数据库fence、UID1001、bwrap、pg_dump证据是交接验证，不混作本reviewer亲自运行。正式包仍须从已审commit构建并核hash、安装路径行为；本次没有以mock故障注入冒充真实生产演练。

## 本轮独立验证原始输出

专项六个非Docker测试文件：

```text
90 passed in 4.17s
```

scope_changes、scope_engine、scope_flow、scope_snapshot、catalog、full_cleanup、cleanup、cleanup_refs八个既有测试文件：

```text
139 passed, 8 subtests passed in 11.08s
```

真实宿主Docker命令：`TEST_TASKS_DOCKER=1 python -m unittest discover -s scripts/release/intranet -p test_domestic_tasks_restarts_docker.py -v`：

```text
test_committed_start_failure_only_recovers_forward (test_domestic_tasks_restarts_docker.DockerRestartTests.test_committed_start_failure_only_recovers_forward) ... ok
test_plain_up_reproduces_drift_then_scoped_hook_restores (test_domestic_tasks_restarts_docker.DockerRestartTests.test_plain_up_reproduces_drift_then_scoped_hook_restores) ... ok
test_precommit_failure_restores_old_compose_and_exact_policies (test_domestic_tasks_restarts_docker.DockerRestartTests.test_precommit_failure_restores_old_compose_and_exact_policies) ... ok
test_successful_candidate_keeps_exact_restart_policies (test_domestic_tasks_restarts_docker.DockerRestartTests.test_successful_candidate_keeps_exact_restart_policies) ... ok

----------------------------------------------------------------------
Ran 4 tests in 67.445s

OK
```

内存 `compile(source,path,'exec')`（不写pyc），原始输出：

```text
scripts\release\intranet\domestic_tasks_engine.py lines=197 COMPILE_OK
scripts\release\intranet\domestic_tasks_history.py lines=52 COMPILE_OK
scripts\release\intranet\domestic_tasks_marker.py lines=22 COMPILE_OK
scripts\release\intranet\domestic_tasks_policy.py lines=47 COMPILE_OK
scripts\release\intranet\domestic_tasks_release.py lines=231 COMPILE_OK
scripts\release\intranet\test_domestic_tasks_engine.py lines=139 COMPILE_OK
scripts\release\intranet\test_domestic_tasks_finish.py lines=139 COMPILE_OK
scripts\release\intranet\test_domestic_tasks_policy.py lines=93 COMPILE_OK
scripts\release\intranet\test_domestic_tasks_restarts.py lines=123 COMPILE_OK
scripts\release\intranet\test_domestic_tasks_restarts_docker.py lines=156 COMPILE_OK
scripts\release\intranet\test_domestic_tasks_state.py lines=107 COMPILE_OK
scripts\release\intranet\test_domestic_tasks_verify.py lines=71 COMPILE_OK
scripts\release\intranet\release_cli.py lines=76 COMPILE_OK
scripts\release\intranet\full_cleanup.py lines=70 COMPILE_OK
scripts\release\intranet\scope_changes.py lines=196 COMPILE_OK
scripts\release\intranet\scope_release.py lines=64 COMPILE_OK
scripts\release\intranet\scope_actions.py lines=135 COMPILE_OK
output\install-tasks-tools.py lines=93 COMPILE_OK
```

`git diff --check -- scripts/release/intranet` 无空白错误，只有scope_release.py的CRLF→LF提示。首次回归命令误写不存在的test_scope_actions.py，原始输出为 `no tests ran in 0.03s / ERROR: file or directory not found`；随后按真实文件名运行上述139项通过，不把首次称为通过。首次直接传通配符路径的rg在PowerShell报路径语法错误，已用目录加 `-g domestic_tasks_*.py` 完成扫描，零命中。

## 一次性工具安装稿

- 文件 `output/install-tasks-tools.py`，93行；**原始字节 SHA256：`4ff4a01fa1954546996e06d38c7bc1c64cb6860e1e279793e99cd19181786868`**；LF归一摘要：`cc5e9fc4cb58c66b90e161ea691b945d991b1560ff7e009e652d3000d2701de5`。该执行稿不纳Git，不能声称受candidate自动保护。
- **可执行结论：主Agent将同一已审代码提交后，以明确40位已审commit为参数，可执行此稿安装工具。本次未执行。** 不得以工作区或其他commit替代；业务0043→0044维护仍需最后具体授权，工具安装成功不等于业务部署。
- :10、:12固定40位commit并从git show读取17文件；:20固定旧目录31249944c5fea417；:29持既有release锁；:32检查pending空；:34起校验旧manifest所有文件及root所有权/不可外写/非符号链接；:41精确核12新增文件，其余5项为修改。
- :43起派生新版本目录、保留旧安装；:65在最终安装目录用实际worker解释器，通过bwrap只读根、隔离网络、独立可写/tmp执行pytest；:76失败不激活；:77核台账字节和current不变；:78复核新文件hash；:82原子替换current链接。没有服务重启、迁移、发布、业务台账写入或旧工具删除调用。该sandbox只用于受审测试，不宣称能约束任意恶意root代码。
- 本reviewer只读取得实际旧manifest477项，payload17项/新增12项匹配。未替换release.py与本地文本一致；unify_release.py差异仅旧CLI壳仍在，安装稿没有调用旧CLI。安装中的旧后端辅助源码保持原样，业务新源码由随后业务包提供，不暗中更新业务。
- 最终安装路径pytest尚未执行；正式执行仍须检查实际pytest输出及安装回执。任何失败不得称工具激活成功，也不得自动进入业务维护。

## 生产只读核实及快照

使用既有 `ssh -o BatchMode=yes hengxin-prod`，只读台账及工具manifest，实际结果摘要：

```text
tools=/opt/hengxin-intranet-tools/releases/31249944c5fea417
domestic=c79924625230275bad65fa778020d5b4a3b272e0 (backend/frontend)
overseas=3b38a2c445149d4a0d12c4145cc90f9e173ab4aa (backend/frontend)
shared=2bc8acc7ecf412626a6a635a9413b1644b55417e (backend/frontend)
schema={domestic:0043, overseas:overseas_0026}
pending=null
installed files 477 payload files 17 new files 12
```

这只是本轮时点只读台账，不冒充生产切换后验收；维护执行前仍须重新实时verify。报告落盘后运行review-status，currentId仍为 `bdc78af52f5564caa852690e03d2626b14a94ce73ff07e295256dcc2bff51fe5`；审查期间代码快照未变化。主Agent只能据此登记同一candidate。

