# 内网 Codex 升级脚本增量审查

- candidateId：`e0e11ab3b7265a1aa9b65216e287581cbd432352caad191a3a2d699122d6dd3b`
- 范围：仅新增 `hengxin-smart-image/scripts/migration245/upgrade_codex.py`（以下简写 `upgrade_codex.py`）。源文档：`docs/INTRANET-CODEX-UPGRADE-20261111.md`。
- 脚本 SHA256：`8E236BCA649C3F6973B97D5AC6D565DFA2C845CF568343D8BDC23F567705BD0D`。
- 结论：**Stage 1 FAIL / HIGH；Stage 2 未执行。不得批准或执行当前候选。**
- 仅做代码阅读、编译及本地替身故障注入；未连接服务器、未执行切换、未修改脚本。其他已审脏文件不在本轮范围。

## Stage 1：Spec Compliance

| 源文档条目 | 结论 | 证据及验证边界 |
|---|---|---|
| 第 3 行：仅内网、保留模型及授权数据 | 已实现静态范围约束 | `upgrade_codex.py:9–19,149–152,183–188` 固定主机名、root 身份及固定配置清单；不写 auth/业务表。主机实际对应 192.168.1.245 由主 Agent 实查，本轮未独立联网验证。 |
| 第 9 行：下载、完整性、实际引用 | 脚本外前置步骤 | `upgrade_codex.py:1,151–152` 明确要求预先并排安装，仅检查版本。主 Agent 提供官方版本、npm SHA512、引用实查结果；脚本不承担下载校验，不将转述证据算成本轮运行证明。 |
| 第 10 行：独立安装、双身份、隔离、保留旧版 | 脚本外前置步骤及静态保留满足 | `upgrade_codex.py:9–10,151–152,163` 仅切换引用，不覆盖旧运行时。双 UID 的直接启动、Bubblewrap 启动及 helper 验证由主 Agent 完成；本轮不重复执行。 |
| 第 11 行：暂停两套消费者、排空任务及数据库 | 正常路径实现 | `upgrade_codex.py:34–50,81–97` 检查目标节点响应类型、队列、active/reserved/scheduled 和四种数据库在途状态；未知响应抛错。海外四种状态与 `backend/app/overseas/execution/models.py:13` 一致。 |
| 第 11 行：未知状态拒绝切换并恢复消费 | **部分实现；HIGH R2** | `upgrade_codex.py:84–85,214–215` 记录需恢复服务，但第一次 resume 抛错会跳过后续服务；本地故障注入复现。 |
| 第 11 行：账号无在途登录/检测 | 正向切换实现；回退不完整 | `upgrade_codex.py:100–110,169–175` gate 三个 socket、检查线程/temporary/cgroup；回退缺少相同步骤，见 HIGH R1。 |
| 第 12、17–20 行：备份、持久化引用、重启必要服务、保留旧版 | 正常路径实现 | `upgrade_codex.py:11–19,153–165,178–191` 固定八个文件、私有备份、切换前比较内容、替换后 reload/start。未运行远端验证，不宣称切换已经成功。 |
| 第 12 行：实际环境、账号命令行与队列恢复 | 正常路径实现 | `upgrade_codex.py:123–145` 检查六服务 active、五环境及账号命令行和两消费队列。 |
| 第 12 行：HTTP 健康 | 脚本未实现；MEDIUM R3 | `upgrade_codex.py:192–195` verify 返回即可记录 APPLIED，`123–145` 无 HTTP 健康请求。主 Agent 提供的是切换前 HTTP 200，不能替代切换后验收。 |
| 第 12 行：失败恢复配置和服务 | **部分实现；HIGH R1** | `upgrade_codex.py:196–208` 回退会排空 worker，但未重新隔离和检查已经重启的账号服务。 |
| 第 13、22 行：记录结果、不冒充付费验收、不重新授权 | 实现自动结果记录；正式记录待执行 | `upgrade_codex.py:193–195,208` 记录版本、队列或回退日志；没有付费生成/重新授权操作。源文档第 22 行明确执行结果待追加。 |

UI、设计稿、视觉对比：本次为运维脚本，没有 UI 变更，不适用。Spec 漂移：上述范围内未新增业务功能；`upgrade_codex.py:153` 拒绝复用同一事务目录属于实施保护。

## 阻断项

### R1 — HIGH：回退停止账号服务前没有重新确认账号空闲

- 要求：源文档第 11 行“确认账号管理无在途登录/检测子进程”，第 12 行“失败恢复配置和服务”；授权范围要求账号授权数据不动。
- 位置：`upgrade_codex.py:190–203`，尤其第 203 行。
- 触发：第 190 行启动新版账号服务，socket 重新可接收请求；第 192 行验证失败后进入回退。
- 差异：仅第 200 行重新排空 worker，第 203 行直接 stop 全部服务。初次切换时第 169–175 行的 socket gate 和空闲证明不适用于重启后的进程与新 socket。这个窗口内新开始的登录/检测可能被停止。
- 必须修复：每次停止当前账号服务前重新 gate 当前 socket，并检查当前进程线程、temporary、cgroup。无法证明空闲时拒绝 stop，保留现场并明确报告。
- 本地证据：调用真实 `main()`，只替换外部进程、路径、等待及验证边界；注入 verify 失败，记录两次 stop，但 `account_idle()` 仅一次。无远端操作。

### R2 — HIGH：消费者恢复失败会阻断另一个消费者恢复

- 要求：源文档第 11 行“未知状态拒绝切换并恢复消费”。
- 位置：`upgrade_codex.py:210–215`。
- 触发：两消费者暂停后检查失败，进入 finally；国内 resume 超时或返回错误。
- 差异：异常立即退出 for 循环，海外 resume 根本不执行；原始失败原因也被覆盖。另有同类风险：第 211–213 行 socket 恢复异常也会跳过全部消费者恢复。
- 必须修复：逐项恢复 socket 和消费者，各自收集异常且继续执行其他恢复；报告原始失败和恢复失败。对 resume 成功还须确认队列恢复。
- 本地证据：真实 `main()` 外部边界替身注入两消费者已暂停、检查失败、国内 resume 失败，海外 resume 调用次数为零。

### R3 — MEDIUM：APPLIED 未包含切换后的 HTTP 健康验收

- 要求：源文档第 12 行“核对……HTTP 健康”。
- 位置：`upgrade_codex.py:123–145,192–195`。
- 必须补齐：将切换后健康检查纳入成功判定及失败处理，或在执行源文档中明确人工后置验收、错误处置步骤，且 APPLIED 不作为全部验收完成的凭据。切换前 200 不是切换后证据。

## 原始验证输出

命令：`python -m py_compile hengxin-smart-image/scripts/migration245/upgrade_codex.py`

```text
exit_code: 0
stdout: (empty)
stderr: (empty)
```

本地故障注入原始输出（临时目录、unittest.mock，不连接实际服务）：

```text
CASE rollback after verify failure
ROLLED_BACK
FINAL_ERROR verify failed
RUN /opt/hengxin-runtime/codex-0.167.1/bin/codex --version
DRAIN
ACCOUNT_IDLE
RUN systemctl stop hengxin-vps-codex-worker hengxin-overseas-worker hengxin-retention hengxin-domestic-deletions hengxin-overseas-outbox hengxin-codex-accounts
RUN systemctl daemon-reload
RUN systemctl start hengxin-codex-accounts hengxin-retention hengxin-domestic-deletions hengxin-overseas-outbox
RUN systemctl start hengxin-vps-codex-worker hengxin-overseas-worker
DRAIN
RUN systemctl stop hengxin-vps-codex-worker hengxin-overseas-worker hengxin-retention hengxin-domestic-deletions hengxin-overseas-outbox hengxin-codex-accounts
RUN systemctl daemon-reload
RUN systemctl start hengxin-codex-accounts hengxin-retention hengxin-domestic-deletions hengxin-overseas-outbox hengxin-vps-codex-worker hengxin-overseas-worker
resume hengxin-vps-codex-worker
resume hengxin-overseas-worker
REPRODUCED: second service stop lacked fresh account gate/idle check
CASE resume failure after refused switch
FINAL_ERROR first resume unavailable
RUN /opt/hengxin-runtime/codex-0.167.1/bin/codex --version
DRAIN
resume hengxin-vps-codex-worker
REPRODUCED: second worker resume was never attempted
```

180/60 秒计时：`upgrade_codex.py:86–97,135–145` 是轮次边界检查，单轮允许继续耗时；源文档没有严格墙钟上限，因此本轮不将此判为新增阻断，但不应描述为精确硬截止。

## Stage 2

**未执行**：Stage 1 有 HIGH，依 skill 停止；不出代码质量、安全扫描、测试完整性 PASS。修复后需重新 review-prepare 并从 Stage 1 复核；本报告不授权 review-approve，不写 `.needs-review`。
