# 内网 Codex 升级脚本修复复审

- candidateId：`67dddc7f3eb5042e3d6f39dd1652025062dbde085103104f8e04c33c758b2122`。
- 范围：仅 `hengxin-smart-image/scripts/migration245/upgrade_codex.py`，下表代码行号均指此文件。源文档为 `docs/INTRANET-CODEX-UPGRADE-20261111.md`。
- 脚本 SHA256：`D6E34D3911BA8772021EA7254557BB90F7EFB62376DF2ECA84E76F8ECD6E5B01`。
- **Stage 1 PASS；Stage 2 PASS。前次 R1/R2 HIGH 已修复；R3 按源文档明确后置验收责任后关闭。**
- 本轮只读代码、本地编译、临时目录替身故障注入；未连接服务器、未修改源码、未提交、未执行升级。其他已独立批准的脏文件不在本轮范围。PASS 是脚本审查结论，不是升级执行或付费生图验收结论。

## Stage 1：Spec Compliance

| 源文档条目 | 结论 | 文件位置及证据 |
|---|---|---|
| 第 3 行：仅 `.245`，不修改公网、业务源码、模型、授权数据 | 完整实现范围限制 | `upgrade_codex.py:10-20,166-180` 固定主机名、root、八个配置路径及版本替换；无业务源码、模型、auth 写入。主机与 IP 对应由主 Agent 实查，本轮不声称独立联网证明。 |
| 第 5、9 行：官方版本、下载校验、实际引用 | 脚本外前置步骤，责任清晰 | `upgrade_codex.py:1,168-169` 要求先并排安装并校验可执行版本。主 Agent 提供官方 changelog/npm latest、SHA512 及引用核对证据；本轮不重复下载，也不把转述作为本地独立实证。 |
| 第 10、22 行：版本独立安装、双身份与 Bubblewrap 验证、同版 helper、保留旧版 | 脚本外前置步骤及保留逻辑满足 | `upgrade_codex.py:10-11,168-181` 只改引用，不覆盖或删除旧版。主 Agent 已提供双 UID、隔离启动和 helper exit 0；不将该测试解释为付费生成通过。 |
| 第 11 行：暂停双 Celery，检查 active/reserved/scheduled/数据库 | 完整实现 | `upgrade_codex.py:35-53,75-103` 指定节点响应结构校验、暂停记录先于控制调用、双队列和四种数据库在途状态检查；未知响应抛错。`control` 本地验证剩余期限为 2.5 秒时传入子进程 timeout=2.5，期限到达不启动子进程。 |
| 第 11 行：未知状态拒绝切换并恢复消费 | 完整实现；R2 关闭 | `upgrade_codex.py:185,223-239`。真实 main 替身注入 drain 失败与首个 resume 超时：无 stop，第二个 resume 仍被调用，原始异常对象保留；CONTROL 实际代码对 ack 成功而队列为空抛出 `Consumer restoration unconfirmed`，队列恢复后通过（第 41-48 行）。 |
| 第 11 行：账号无在途登录或检测子进程 | 完整实现；R1 关闭 | `upgrade_codex.py:106-127,186,214-216`。正向和回退均 gate 并检查空闲。故障注入 verify 失败后第二次 gate 先于第二次 stop；第二次 gate 判忙时不执行第二次 stop，保留当前配置。真实 gate 函数另测两代 inode，记录全部六项并两次调用 idle。 |
| 第 12、19-21 行：备份、精确持久化引用、必要服务重启 | 完整实现 | `upgrade_codex.py:17-20,170-182,189-202` 固定八个文件、私有事务目录/0600 备份、拒绝 symlink/非 root、原子替换、排空后再次对比原文、reload 与重启。真实 main 正常路径测试输出 APPLIED，备份/替换在临时目录执行，系统调用全部替身。 |
| 第 12 行：实际环境、账号命令行和队列恢复 | 完整实现 | `upgrade_codex.py:140-162,203-206` 检查六服务 active、五运行环境的 binary/version、账号 cmdline 和两消费队列；不是只检查配置文本。运行环境读取未在本地冒充远端验证。 |
| 第 12 行：失败恢复配置和服务 | 完整实现安全回退路径 | `upgrade_codex.py:207-222` 重新排空已启动双 worker，部分启动拒绝盲停；active 账号重新 gate。注入 verify 失败：两次 stop 之前分别有 gate、旧配置恢复、服务启动、最终抛出原始异常；账号忙时保留现场。 |
| 第 12、15 行：HTTP 和完整交付验收 | R3 关闭；明确脚本外后置责任 | `docs/INTRANET-CODEX-UPGRADE-20261111.md:15` 明确 APPLIED 只代表 native 切换，主 Agent 必须后置验证首页、双 ready、容器、auth 摘要、实际版本；关联失败重新排空后恢复，不在未知状态强停。`upgrade_codex.py:204-206` 不再被解释为整体验收完成。后置实际执行仍待主 Agent 完成。 |
| 第 13、24 行：记录结果，不更换/重授权，不冒充付费验收 | 完整实现记录责任 | `upgrade_codex.py:204-206,221,237` 记录版本、队列、回退及恢复异常；无付费生成或重新授权操作。源文档第 24 行保留待执行结果，本次尚未升级，不要求虚构完成记录。 |

部分实现、未实现：限定脚本职责内无。Spec 漂移：未新增业务功能；事务目录拒绝重用、恢复错误汇总均服务于升级安全。UI、引导文案、设计稿、邻居页面渲染对比不适用：本范围只有运维脚本，没有页面改动。

## Stage 2：Code Quality

| 项目 | 结论与证据 |
|---|---|
| 命名、结构、文件大小 | PASS。`upgrade_codex.py:1-243` 共 243 行，低于技能 300 行标准；run/context/control/drain/gate/account_idle/atomic/verify/main 职责可区分，无 TypeScript any。Python 采用动态类型，涉及外部响应处有结构/字段检查（第 35-53、66-84 行）。 |
| 错误处理 | PASS。第 207-239 行保留拒绝不安全回退的分支；socket 的 OSError 与每个 consumer 的 Exception 分别捕获、继续后续恢复并汇总；存在原始异常时不覆盖。实测同时发生 socket/首 consumer 恢复失败仍调用第二 consumer，并保持原 verify 异常对象。 |
| 测试真实性 | PASS（范围限本地逻辑）。调用真实 main，只替换进程、路径、服务状态及外部边界；配置真实读写临时目录。包含正常切换、verify 失败、回退账号忙、排空失败、恢复失败；另执行真实 gate 和 CONTROL 代码、真实 control 剩余期限逻辑。替身没有把 `verify` 或真实服务器服务状态测试冒充远端证明。 |
| 安全扫描 | PASS。第 57-59、82-83、190-220 行采用 argv 列表，无 shell=True；CONTROL 为固定源码，side/action/node 通过 argv 传递；第 51-52 行为 SQLAlchemy 查询表达式。硬编码密钥、eval、浏览器危险注入、前端密钥变量扫描无匹配。第 10-20 行绝对路径属于已授权服务器固定部署位置；第 170-181 行私有备份，不打印 env/auth 内容。 |
| 代码漂移、视觉对比 | PASS / 不适用。限定脚本内容与源文档升级职责匹配；没有页面/API/业务表新增，无视觉交付物，不能虚构视觉验证。 |

未发现需要阻断当前候选的 HIGH 或 MEDIUM。远端后置验收与付费生图不在本轮本地验证覆盖内，不能根据本报告宣称已经通过。

## 编译与故障注入原始输出

命令：`python -m py_compile hengxin-smart-image/scripts/migration245/upgrade_codex.py`

```text
exit_code: 0
stdout: (empty)
stderr: (empty)
```

测试脚本：临时目录 `%TEMP%/codex_upgrade_recheck.py`，未纳入仓库。命令 `python $env:TEMP/codex_upgrade_recheck.py`，exit_code 0：

```text
R1 rollback fresh gate PASS
EVENTS ['DRAIN', 'GATE_IDLE_1', 'STOP', 'START', 'START', 'VERIFY', 'DRAIN', 'GATE_IDLE_2', 'STOP', 'START', 'resume hengxin-vps-codex-worker', 'resume hengxin-overseas-worker']
ROLLED_BACK
R1 busy rollback refuses stop PASS
EVENTS ['DRAIN', 'GATE_IDLE_1', 'STOP', 'START', 'START', 'VERIFY', 'DRAIN', 'GATE_IDLE_2', 'resume hengxin-vps-codex-worker', 'resume hengxin-overseas-worker']

R2 consumer failure does not skip second PASS
EVENTS ['DRAIN', 'resume hengxin-vps-codex-worker', 'resume hengxin-overseas-worker']
RESTORE_UNCONFIRMED ["consumer hengxin-vps-codex-worker"]
R2 socket and consumer failures preserve original PASS
EVENTS ['DRAIN', 'GATE_IDLE_1', 'STOP', 'START', 'START', 'VERIFY', 'DRAIN', 'GATE_IDLE_2', 'STOP', 'START', 'socket restore', 'resume hengxin-vps-codex-worker', 'resume hengxin-overseas-worker']
ROLLED_BACK
RESTORE_UNCONFIRMED ["socket /fake/socket", "consumer hengxin-vps-codex-worker"]
normal successful switch PASS
EVENTS ['DRAIN', 'GATE_IDLE_1', 'STOP', 'START', 'START', 'VERIFY']
APPLIED 0.167.1
real gate tracks both generations and calls idle twice PASS
{"queues": ["celery"], "active": 0, "reserved": 0, "scheduled": 0, "database": 0}
CONTROL resume rejects acknowledgment without queue and accepts restored queue PASS
control passes remaining deadline and refuses expired subprocess PASS
ALL 8 CASE GROUPS PASS
```

快照核对：开始与结束均核对脚本 SHA256 和 `harness.py review-status`，candidateId 与交接一致，审查过程中脚本未变化。主 Agent 按此 candidateId 和本报告登记两阶段 PASS；本 reviewer 不写 `.needs-review`、不自行批准其他文件。
