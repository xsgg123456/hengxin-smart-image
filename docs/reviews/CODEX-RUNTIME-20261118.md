# 双业务 Codex CLI 运行时维护审查

## 最终审查

候选编号 `4eb0424bff2b7a166b447e9e02a1cf1e4fd94bb23ee4a98dadb0b04c4b8ab274`。独立运行 `harness.py review-status` 核对与当前代码相同。**Stage 1 PASS，Stage 2 PASS。** 本结论覆盖双侧运行时维护、两条日常发布门禁、accounts 凭据恢复和获准的 sosreport 单项登记；业务命令参数及分组部署另案审查。

| 阶段 | 最终代码与验收证据 |
| --- | --- |
| Stage 1，版本与配置 | `scripts/release/intranet/codex_runtime_config.py:19` 固定两版与 SHA，`:46` 限制配置中字段、版本值和引用计数；`:98` 核对主机上的 helper 和两份二进制，`:120` 记录文件身份、权限与前后摘要。 |
| Stage 1，排空、重启、恢复 | `scripts/release/intranet/codex_runtime_maintenance.py:131` 核对原现场与门禁；`:158` 调既有双队列排空；`:68` 禁强杀并核对实时和原 cgroup；`:100` 在启动前清理已死 accounts socket、等待三端点后启动 worker；`:217` 区分台账已写和需回退的情况。`joint_studio_credentials.py:67` 和 `:105` 保留 UID/GID、权限、活监听、inode 和 cgroup 防护；第四 auth socket 保持服务。 |
| Stage 1，台账与发布互斥 | `codex_runtime_config.py:70` 至 `:96` 生成全局预期快照、重算两组当前状态并保留历史；`codex_runtime_maintenance.py:179` 与 `:187` 串联现场核验、写账、开放入口；`release_cli.py:36`、`stage.py:74` 在日常操作前检查未完成事务。 |
| Stage 1，sosreport | `record_sosreport_20261118.py:21` 校验完整前后包清单哈希；`:44` 查 dpkg 版本和完整性；`:49` 至 `:59` 对完整现场比对成功后只更新 shared accounts 摘要。重复执行不另写，独立现场漂移在写账前拒绝。 |
| Stage 2，结构和安全 | 维护入口 288 行，配置模块 151 行，marker 24 行，运行时测试 217 行；原 426 行文件问题关闭。`codex_runtime_config.py:98` 按固定哈希执行 helper，核实二进制和版本；`codex_runtime_maintenance.py:253` 限制 root、主机与全程共享锁；`joint_studio_credentials.py:100` 以目录描述符核对清理对象。界面、SQL 和自由拼接 shell 命令不在本次变更中。 |
| Stage 2，故障测试 | `test_codex_runtime_maintenance.py:130` 核验双向切换及历史，`:146`、`:158`、`:179` 分别覆盖恢复、写账中断和残留子进程，`:200` 覆盖 socket 延后建立；`test_joint_studio_credentials.py:140` 和 `:169` 在真实 Unix socket 上覆盖 000/0660 死端点、活监听、错误权限及保持第四端点；`test_record_sosreport.py:25` 覆盖额外漂移引发零写入。 |

最终快照独立运行 WSL Ubuntu root 三份专项和 Windows 暂存/登记两份专项，退出码均为 0。两组包含重复的登记用例。原始输出如下。

```text
.............................................                            [100%]
45 passed in 6.27s
..............                                                           [100%]
14 passed in 0.36s
```

十个送审 Python 文件的 `py_compile` 退出码 0、标准输出为空。Linux 测试使用隔离 socket 与子进程，事务切换使用模拟 systemd。生产切换、实际服务版本与账户可用性应以生产验收记录为准。下文保留各旧候选的审查记录。

## 复审 b38d1bb

本次 `harness.py review-status` 返回 `b38d1bb383266e7fc72752b1e4238da8140805c2716e0db2071641f8c25e9ed3`，覆盖上一轮全部范围。**Stage 1 PASS，Stage 2 FAIL（一个 MEDIUM 结构问题）。** sosreport 登记子范围两阶段通过。

**Stage 1。** `joint_studio_credentials.py:67` 绑定原来三个 accounts socket 的清单、UID、GID 和 0660；`:92` 在此维护入口可处理 000 和原 0660，`:100` 至 `:118` 验证目录、活监听拒绝、停机和同一 inode 后才清理。旧四端点入口在 `:61` 保持 000 限制。`test_joint_studio_credentials.py:140` 验证两种死 socket 均可恢复，第四个 auth socket 仍可连接；`:169` 验证 0660 活监听者、错误 GID、错误权限及旧联合模式全部拒绝，保持 inode。首次两项 HIGH 和第二次复审 HIGH 全部关闭。排空、事务快照、台账、门禁与 sosreport 全量核验逐条见下两段历史证据；已重新核对 `codex_runtime_maintenance.py:269`、`:325`、`:355`、`record_sosreport_20261118.py:30`、`release_cli.py:36`、`stage.py:74`。

**Stage 2。** 新 `codex_runtime_maintenance.py:1` 至 `:426` 共 426 行，超过 code-review skill 的单文件 300 行标准。文件同时承担八个配置的变换及快照（`:53`）、systemd/socket 生命周期（`:206`）、事务和恢复（`:258`）。此项 MEDIUM 可通过按现有职责拆分解决。其它安全与质量核对通过：`codex_runtime_maintenance.py:113` 先用根所有权与固定 SHA 验证读入的 helper 字节，再在 `:118` 执行同一字节；`release-retention-state.py:119` 在私有目录内以 mkstemp、fsync 与原子替换保存私有事务。 `record_sosreport_20261118.py:44` 对命令传固定参数列表，`:53` 独立比对完整现场，无外部输入进入 shell。范围内没有 UI，不适用页面渲染。

Ubuntu WSL root 独立重跑运行时、真实凭据和登记三个专项；Windows 单独重跑暂存与登记两个专项。原始输出如下（两组有重复登记用例）。

```text
.............................................                            [100%]
45 passed in 7.78s
..............                                                           [100%]
14 passed in 0.38s
```

本轮九个 Python 文件均成功编译，原始标准输出为空、退出码 0。结合 `test_codex_runtime_maintenance.py:45` 的隔离 fixture，本轮证明事务分支与 Linux socket 行为；未在生产制造停机或回退故障。

## 复审 9f57d81

候选编号 `9f57d81a83f0c8ad1a892d9e0a0bc2c1607147e832f88a3f962dc6e3b5534763`，已与 `harness.py review-status` 独立核对。范围增加 `codex_runtime_marker.py`、`joint_studio_credentials.py`、`test_joint_studio_credentials.py`、`record_sosreport_20261118.py` 和 `test_record_sosreport.py`。

**Stage 1 FAIL。上一版两项 HIGH 已修复；还有一条新账号服务启动失败的回退路径被阻断。Stage 2 未执行。**

| 项目 | 结论及证据 |
| --- | --- |
| 停机后 cgroup | 通过。`codex_runtime_maintenance.py:287` 持久化六项服务的原组；`:221` 同时验证当前和已记录 cgroup。`test_codex_runtime_maintenance.py:178` 实测 systemd 已清除属性、子 cgroup 仍有 PID 时拒绝。 |
| 旧 000 socket 与启动时序 | 通过。`joint_studio_credentials.py:69` 单独处理 accounts 三个端点，`:87` 起验证路径、无监听者与 inode；`codex_runtime_maintenance.py:239` 在启动前接入，`:249` 在启动 worker 前有界等待三端点；`test_joint_studio_credentials.py:140` 验证第四端点保持活动。 |
| HIGH，候选账号服务异常退出留下 0660 死 socket | `codex_runtime_maintenance.py:329` 关闭入口但保持 workers 门禁开放，因此新服务在 `hengxin-smart-image/backend/app/execution/credential_broker.py:74` 起以 0660 创建 socket。若新服务异常退出，`codex_runtime_maintenance.py:375` 对 inactive/failed 且 PID 0 的服务跳过 gate，`:382` 回退启动时，`joint_studio_credentials.py:87` 拒绝仍为基线 0660 的 socket，业务入口无法恢复。应只在此独立三端点维护中允许已审基线权限，沿用 UID/GID、无监听者、停机和 inode 身份检查；原四端点联合迁移仍仅允许 000。 |
| sosreport 登记与范围 | 通过。`record_sosreport_20261118.py:21` 对完整包清单验证新 SHA 并仅回写 sos 版本计算旧 SHA；`:32` 校验各维护门禁，`:44` 检查 Ubuntu 包版本和 dpkg 校验；`:49` 仅改 accounts 包摘要，`:53` 对整个现场快照比较，`:56` 只重建 shared.current 并重新签封，历史版本保留。入口 `:63` 限制主机、root 及共同发布锁；`test_record_sosreport.py:24` 覆盖额外现场漂移时零写入。 |

本次独立使用本机 WSL Ubuntu root 的临时目录及真实 Unix socket，绑定监听后关闭、设 UID/GID 65534 和 0660，模拟 systemd 已报告 failed 且 MainPID 0，调用新 `prepare_accounts`。未访问生产。原始输出如下。

```text
connect_ex 111
prepare_accounts Unrecognized leftover credential socket exists True
```

本机两份可跨平台运行的运行时及登记专项结果为 `28 passed in 3.89s`；九个 Python 文件的 `py_compile` 退出码 0，无输出。Windows 合跑 Linux 专项在收集时因 `signal.SIGKILL` 不存在失败，不能据此计 Linux 测试通过。主 Agent 另提供 WSL root 的 37 项通过结果。

## 初审 66a4312

候选编号 `66a4312dcca8f11e04a44bd7c9cadd564a040f80af54b40048994e2a7d7c2606`。前序编号 `5bb7cf93c1a1cdf1f122da807a4f925a18c9af3ac5f3a5dc7c4c32e4ba074044` 仅用于开始阅读。审查范围为 `scripts/release/intranet/codex_runtime_maintenance.py`、`test_codex_runtime_maintenance.py` 及 `stage.py`、`release_cli.py` 的运行时事务门禁。业务模型参数及后端分组发布由另案审查。

**Stage 1 FAIL。账号服务异常退出可令正向切换和回退同时无法启动；六项服务的残留进程检查也不完整。Stage 2 未执行。**

| 优先级 | 要求及证据 | 实现差异 |
| --- | --- | --- |
| HIGH | 账号服务重启前须能处理已停服务留下的 000 socket，且不能删除活监听。见 `docs/INTRANET-RELEASE-TOOLS.md:72`。生产 accounts 配置保留目录，既有非 root Linux 复现实证见 `docs/reviews/DOMESTIC-STUDIO-FINAL-R13-20261113.md:15`、`:20`。 | `codex_runtime_maintenance.py:327` 关闭三个 socket，`:330` 停机，`:332` 启动，`:376` 起的恢复走同一路径。异常退出未运行清理时，服务 UID 对 000 死 socket 的 connect 收到 EACCES；`hengxin-smart-image/backend/app/execution/credential_broker.py:85` 只接受 ECONNREFUSED。两条路径都缺少固定账号 socket 身份、原模式、无监听者及 cgroup 的停后核验与恢复。既有可用实现位于 `scripts/release/intranet/joint_studio_credentials.py:56`，其原四 socket 入口会同时要求 auth 已停，本次仅能处理三个 accounts socket。此外 `codex_runtime_maintenance.py:251` 启动后没有等账号 socket 建立，`:333` 立即 lstat。|
| HIGH | 使用禁止强杀的停止保护，确认原进程已全部退出后才能替换配置或启动。见 `docs/INTRANET-RELEASE-TOOLS.md:20`、`:72`。 | `codex_runtime_maintenance.py:235` 验证 SendSIGKILL=no，`:238` 接受 failed 且 MainPID=0。该判据没有观察服务 cgroup 中的子进程。异常退出留下的子进程因而不能阻止 `:331` 的配置替换。可复用 `joint_studio_credentials.py:16` 的停止条件逐项验证六项服务，并对非空 cgroup 的拒绝作故障断言。 |

| Stage 1 核查项 | 证据 |
| --- | --- |
| 双向升级与版本绑定 | `codex_runtime_maintenance.py:26` 固定两版摘要，`:131` 核验 helper 和两个二进制的摘要及版本，`:410` 选择正向或反向；`:53` 验证各字段位置和引用计数，`:179` 限定八个目标文件。 |
| 排空与失败恢复 | `codex_runtime_maintenance.py:277` 核验入口门禁，`:325` 关入口后排空两条原生队列。底层 `hengxin-smart-image/scripts/migration245/unify_release.py:397` 先检查运行中、预留、定时、数据库与 broker，再暂停并复查。 `codex_runtime_maintenance.py:379` 恢复 socket、核验消费者并重开入口；完整故障恢复受上述 HIGH 阻断。 |
| 台账与重入 | `codex_runtime_maintenance.py:95` 只更新当前两侧快照并重新签封，`:338` 在实际快照匹配后准备写账，`:354` 识别写账已成功而客户端中断的情况。`test_codex_runtime_maintenance.py:128` 验证正反切后两版历史一致，`:156` 模拟原子替换后的异常。 |
| 暂停时排斥其它日常发布 | `scripts/release/intranet/stage.py:70` 与 `release_cli.py:26` 使用发布锁并判断未终结事务；`codex_runtime_maintenance.py:396` 在同一锁中执行。 |
| 界面与范围 | `codex_runtime_maintenance.py:387` 只有命令行运维入口，包括检查、切换、回退和恢复。此次差异没有页面或样式。 |

仓库后端虚拟环境独立执行 `python -m pytest -q scripts/release/intranet/test_codex_runtime_maintenance.py`，退出码 0。原始输出如下。

```text
.......................                                                  [100%]
23 passed in 3.72s
```

`test_codex_runtime_maintenance.py:92` 至 `:108` 将停启、socket 创建和 worker 服务模拟为内存状态，因此以上 23 项不能证明实际处理过 000 死 socket 和残留子进程。四个送审 Python 文件均通过 `python -m py_compile`，退出码 0，原始输出为空。本次审查没有写生产。
