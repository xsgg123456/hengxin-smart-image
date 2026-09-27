# CLI 成品验收对抗审查报告

日期：2026-09-27。审查者：独立 code-reviewer；使用 `.agents/skills/code-review/SKILL.md`。仅审查，未修复、未部署、未访问生产、未调用模型、未提交 Git。

## 结论与快照

**Stage 1：FAIL（存在 HIGH）。Stage 2：未执行。** 当前实现仍能把完整有效交付判为失败；这不是只有一种重连文案的问题。确认两类既有契约不匹配：恢复性重连误拒、合法图片引用格式误拒。另确认存储恢复能力缺口；它属于用户新目标下需要补齐的能力，不冒充旧 Spec 已明确承诺自动恢复。

- candidateId：`30176f8f46b4e4a112b05ea81624f34f6fbe8bfbe72177bbc775744070b5de9e`。
- 范围：`backend/app/execution/{events,final_delivery,codex_runner,intervention,output_collector,process,workspace}.py`；`backend/app/worker/{reconcile,repair_delivery}.py`；任务执行权、发布事务、文件验证/保存及相关测试。下文 `app/`、`tests/` 相对 `hengxin-smart-image/backend/`。
- 输入：`Product-Spec.md:49–77,244–252,434–459,592–594,626`，`hengxin-smart-image/docs/CLI-FINAL-DELIVERY-FALSE-FAILURE-20260923.md`，`docs/HARNESS-REVIEW.md`，本轮主 Agent 的审查 brief。
- 结束时 `review-status` 的 `currentId` 与 candidateId 相同、`changedFiles: []`，未发现审查范围代码变化。报告和 `output/cli_acceptance_review/` 临时复现脚本不改变代码快照。
- 状态文件原已有 `approved: true`，是历史凭据，**不表示本轮通过**。本轮没有调用 `review-approve`，不得以历史 PASS 覆盖新发现。

## 发现

### F1 · HIGH：以完整网络错误文案做恢复白名单，真实成功被三条路径一致否决

证据等级：主 Agent 已核实生产事故；本 reviewer 另做本地业务链路复现，未重复访问生产。

Spec 原文：`Product-Spec.md:59`“中途可恢复重连不应否决最终成功”；同会话正常完成、进程成功退出、明确交付并通过图片校验时必须入库。`:626` 要求以最终答复的明确交付为成品列表。

`app/execution/events.py:14–18` 只认 `websocket closed by server before response.completed`。生产出现的下列恢复通知不匹配：

```text
Reconnecting... 4/5 (stream disconnected before completion: WebSocket protocol error: Connection reset without closing handshake)
```

`events.py:85–90` 把它留成 `cli_error`；后续 `turn.completed` 只清除 reconnect_pending，不清除该错误。`final_delivery.py:75–77` 再次使用相同判定。普通与续接在 `codex_runner.py:169–172` 尚未收图即失败；恢复在 `worker/reconcile.py:130–132` 同样提前失败。只改其中一个入口无法根治。

事故诊断 `4b841c26-5480-4cb9-baa1-0fb25f07a186`：首次只交付 01/03，自动续接最终明确交付 01/02/03；两次均正常完成、exit 0，续接 stderr 空。三张 JPEG 可解码、72 DPI；790×1456、790×1362、790×1177。该事故的文件与进程证据由主 Agent 提供；视觉效果未重新验收。生产 events.py 哈希与本地一致，详见同目录审查 brief。

本地将上述通知插入成功 CLI 事件流，实际调用 runner/reconcile、图片验收和版本发布链路（CLI 边界模拟）：普通路径 failed/0 版本/1 次执行；自动续接 failed/0 版本/2 次执行；恢复 failed/0 版本/1 次执行。复现脚本 `output/cli_acceptance_review/test_adversarial_delivery.py:62`。

建议：统一调用级终态解释器，区分可恢复过程通知与终止失败；恢复性只作为过程状态，在后续同调用可信完成后消解。保留原始 error 和失败边界。不要用扩大任意 `error` 忽略范围替代分类，也不要继续穷举每个底层英文异常全文。

### F2 · HIGH：合法最终图片链接因 Markdown 表达形式被丢掉

证据等级：本地构造已复现；未证明这两种格式已在生产发生。

Spec 原文：`Product-Spec.md:626`“最终 assistant 答复中明确交付的本地图片引用”“不要求改 Skill 或生成平台专用清单”。实现隐含限定了更窄的 Markdown 子集，Spec 没有写这个限定。

`app/execution/final_delivery.py:110–111` 无条件删除四空格/Tab 开头的行；`:120` 仅匹配内联 `[](...)`。下列两份最终答复都有完整的单张交付、文件实际存在且可解码、同会话 `turn.completed`，但均得到 `final_reply_missing`：

```markdown
![成品][final]

[final]: /work/final.png
```

```markdown
1.  成品

    ![成品](/work/final.png)
```

第一份是引用式图片，第二份是有序列表内的图片段落，四空格是列表内容缩进而非独立代码块。语法依据：[CommonMark 引用式链接](https://spec.commonmark.org/0.31.2/#reference-link)、[列表项](https://spec.commonmark.org/0.31.2/#list-items)。本地使用真实 `collect_final_outputs` 验证，见复现脚本 `:32`；纯 collector 复现，不宣称已对这两种格式另做三路径端到端测试。三路径使用同一 collector，代码入口为 `codex_runner.py:180`、`reconcile.py:144`。

建议：按 Markdown 结构识别明确图片/下载引用，再做统一路径和槽位校验；代码块排除应依赖块结构，不依赖行首空格。保留“示例代码不构成交付”的防线。不能退化为全文扫描所有 `.jpg` 字符串。

### F3 · HIGH（新目标能力缺口）：正常收图存储失败后终结，恢复路径却能重试保存

证据等级：本地故障注入已复现；未证明本次生产事故发生过存储故障。旧 Spec `Product-Spec.md:75` 明确存储/发布失败不重新生成，未明确承诺自动补收；**不列为违反该条的缺陷**，但不满足本轮“已有有效成品应最终交付”的目标。

`app/execution/codex_runner.py:197–222` 已通过收图后，save_upload 临时异常会以 storage_failed 结束本轮为 failed；恢复扫描 `app/worker/reconcile.py:98–102` 仅看 uncertain。存储恢复后再次 reconcile 不会处理该轮。人工补收函数 `repair_delivery.py:27–32` 又限定 `attempt.error == 'cli_error'`，普通成功执行后的存储失败不满足资格。

对照复现：

| 相同完整交付 + 一次临时存储异常 | 服务恢复后的结果 |
| --- | --- |
| 正常 runner 路径 | failed，0 个版本；reconcile 不补收；prepare_recollection 拒绝 |
| Worker 已中断、走 reconcile 的路径 | 首次存储失败保留 uncertain，第二次成功，2 个版本；再次扫描不重复发布 |

调用次数两者均为 1，未重新生成。复现脚本 `:91` 和 `:112`；恢复异常保留逻辑在 `reconcile.py:170–173,83–86`。原测试 `tests/test_cli_intervention_recovery.py:147` 只证明存储失败不启动第二次生成，不能证明后来可补收。

建议：统一正常/恢复两条路径的持久化阶段，保存验收完成证据和稳定文件快照，存储失败进入可恢复的待保存/待发布状态。按 round/slot/content 身份幂等保存后再事务发布；重试不能绕过当前轮次、取消和执行权检查。必须先同步产品契约，再实施。

### R1 · MEDIUM：重复完成事件被摘要去重，但最终回复器拒收

证据等级：构造事件流已复现；没有证据证明固定生产 CLI 会实际输出重复终态，不计入已发生事故。

`events.py:67–68` 对重复 turn.completed 去重，保留成功和不重复计量；`final_delivery.py:80,89–95` 机械要求最后两条事件必须是 agent_message、turn.completed。追加同一个完成事件后 summary 成功，collector 却 final_reply_missing。复现脚本 `:39`。`tests/test_execution_outputs.py:132` 有摘要去重测试，但没有证明最终收图也兼容。

建议：以调用/turn 身份状态机锁定最终 assistant 答复，容忍已验证为幂等的重复终态。后续工具执行、另一个未完成 turn 或终止错误仍应使旧答复失去最终性。缺完成、非零退出目前属于 Spec 明确拒收，不能据此直接删掉门禁。

### R2 · MEDIUM：usage 校验与成品验收耦合

证据等级：构造事件流已复现；未发现生产 usage 为 null/嵌套字段的证据。

`events.py:74–81` 要求 usage 每个值均为非负整数，任何字段不符就产生 invalid_usage；runner `:169` 将此视为执行失败。构造 `{"input_tokens":1,"cached_input_tokens":null}`，实际成品 collector 通过，但摘要 invalid_usage。复现脚本 `:50`。`Product-Spec.md:594` 要求可靠用量、缺失显示未提供，不要求计量异常否决有效成品。

建议：计量单独记录可信/缺失/异常，未知字段不能污染可信计量，也不应单独否决已独立证明有效的交付。若视为事件整体损坏则进入证据核实，不伪造 0 用量或直接当生图失败。

## Stage 1 逐项覆盖

此表覆盖本次 CLI 验收范围，不把整份产品的无关 UI/API 功能列为已审。完整实现仅指列明代码和本地验证边界。

| Spec 要求 | 结果与证据 |
| --- | --- |
| `:59` 恢复性重连后正常完成应交付 | **部分实现/不匹配**，F1；已有旧文案测试通过，生产 reset 文案三路径失败 |
| `:626` 只用本次最终 assistant 答复 | 已实现排除工具/早期消息，`final_delivery.py:60–96`；`tests/test_final_delivery.py:63,74` 通过；尾部兼容见 R1 |
| `:626` 明确本地图片引用，不要求平台清单 | **部分实现/不匹配**，F2；内联链接及旧 manifest 不覆盖最终回复的测试通过，`tests/test_final_delivery_roundtrip.py:88` |
| `:626` 清晰编号/展示顺序，完整数量，不猜槽位 | 已实现，`final_delivery.py:165–178,224–235`；中文/数字/标题/列表编号、排序、缺图/多图、冲突、预览下载去重测试通过，`tests/test_final_delivery.py:49,113,137,189,209,227` |
| `:626` 合成/修复成品不要求原生字节一致 | 已实现，`final_delivery.py:238–250`；实际修复图入库/单张与整套返工回归通过，`tests/test_final_delivery_roundtrip.py:88` |
| `:626` 本轮 work 或同会话本轮新增原生图片 | 已实现路径与 baseline 限制，`final_delivery.py:181–213`，历史及跨会话拒收测试 `tests/test_final_delivery.py:126,166` 通过 |
| `:626` 输入/当前图/Skill、越界、链接、重复文件拒收 | 路径/硬链接/重复路径测试通过，`final_delivery.py:183–210,239–242`、`output_collector.py:19–37`；符号链接两例受 Windows 权限跳过，不能称实测通过 |
| `:626` 格式、完整解码、文件大小、尺寸安全限制 | 已实现，`final_delivery.py:244–252`，`files/validation.py:11–14,40–65`；坏图和路径测试通过。没有增加固定 790×1500 或 DPI 门槛；技术有效不代表视觉合格 |
| `:626` 最终缺失/不完整/无效应明确失败 | 已实现，`final_delivery.py:224–252`；现有缺图/坏图/不完整列表测试通过。事故首次 01/03 不应当作三张齐全放行 |
| `:626` manifest 只用于升级前恢复 | 已实现，runner `:124` 写 final-reply-v1；reconcile `:136–154` 按协议分流，未知协议不降级；`tests/test_execution_reconcile.py:224–254` 通过 |
| `:73–75` 仅首次模板整套、明确退出后最多一次干预 | 已实现，`intervention.py:37–77`、runner `:145–192`；`tests/test_cli_intervention.py:19,49,63` 和 recovery `:16,36` 通过 |
| `:73` 续接原会话、原工作目录/候选/初始 baseline | 已实现，`intervention.py:80–104`、runner `:189`；`tests/test_cli_intervention.py:19` 通过；会话错配拒绝 `test_cli_intervention_recovery.py:114` 通过 |
| `:49–51,75` 共用冻结总时限 | 已实现，runner `:105,143,158–160`；`test_cli_intervention_recovery.py:127` 的 3600/7200 用例通过 |
| `:75` 取消/失权/不确定/缺会话/认证额度限流不续跑 | 已实现，`intervention.py:44–76`、runner `:146,173,186`；干预负例和取消门禁测试通过 |
| `:75` 材料或保存发布失败不重新生成 | 已实现“不自动再生成”，runner `:186–209`；存储后续恢复能力见 F3 |
| `:77` 先记录次数、独立证据、汇总已知 usage | 已实现，`intervention.py:83–103,107–123`；`test_cli_intervention.py:19` 和 recovery `:45` 通过；usage 格式兼容见 R2 |
| `:77` 中断只核实已执行结果，不重放干预 | 已实现，`reconcile.py:95–173` 没有 CLI 启动；进程身份切换/缺身份/无 exit 回执测试 `test_cli_intervention_recovery.py:45,80` 通过 |
| `9.2(1)` 同任务互斥、uncertain 占权、跨任务环境隔离 | `claims.py:52–80`，workspace `:29–36,106–107` 有实现；任务 active 状态阻断测试通过。真实 Linux 挂载隔离本轮未测，不用 Windows stub 宣称验证 |
| `9.2(2)` 请求重放幂等、同键异内容拒绝 | 现有 `tests/test_tasks.py:49,80`、`tests/test_revisions.py:36,89,169` 通过；实现 `tasks/service.py:9` 使用 fingerprint/replay。真实 PG 多进程并发本轮未测 |
| `9.2(3)` 重复消息不重新执行 | `claims.py:59–60`；`tests/test_codex_runner.py:114`、重复恢复 `tests/test_execution_reconcile.py:138,199` 通过 |
| `9.2(4)` 发布再次验证未删除/当前轮/当前执行权 | `results.py:11–14` 调 `claims.valid:77–80`，同事务追加版本/切当前/终态 `results.py:27–36`；`tests/test_tasks.py:96,160`、reconcile `:97,138` 对应测试通过 |
| `9.2(5)` 未核实不启动第二份，能恢复则收集 | `reconcile.py:105–120` 核实精确 PID/boot/start，`:124–166` 补收；恢复测试通过；F3 是正常存储失败未进入该通道的缺口 |
| `9.2(6)` 取消持久化、不能因晚到结果复活 | `claims.py:61–63,77–80`、reconcile `:39–42,75–77`；取消前/上传中/发布前、租约丢失负例通过 |
| 补收必须保留原诊断且不覆盖后续版本 | `repair_delivery.py:27–59,60–67`；`tests/test_repair_delivery.py:23,37` 的审计/失效证据拒收测试通过；新 reset 文案未修前也不能直接用此函数补收 |

未实现项：完整 Markdown 交付引用兼容未实现；正常路径可恢复存储阶段未实现（新目标）。本范围未发现新增页面、API、模型或 Skill 的功能扩张；F2 属实现收窄契约。UI、引导文案与视觉对比不在本次后端范围。

## 本地验证与原始输出

复现脚本保存在 `output/cli_acceptance_review/test_adversarial_delivery.py`，不纳入正式产品测试。它断言的是“当前错误行为确实存在”，因此测试绿色不等于产品验收通过。

运行目录 `hengxin-smart-image/backend`；使用项目 `.venv/Scripts/python.exe`。真实运行 HTTP 受理、材料准备、SQLite 测试数据库事务、收图验证、版本发布/恢复逻辑；CLI 启动及 sandbox/version、MinIO 对象 IO 使用现有测试夹具替代，进程退出检查在恢复用例注入。没有真实 Linux CLI/容器、生产数据库或收费生成。本地两种失败 Markdown 直接调用真实 collector；故障存储通过 save_upload 边界抛错。没有宣称 SQLite 可证明 PostgreSQL 多 Worker 竞争。

第一批命令：

```text
.\.venv\Scripts\python.exe -m pytest -q -s ../../output/cli_acceptance_review/test_adversarial_delivery.py tests/test_reconnect_delivery.py tests/test_final_delivery.py tests/test_final_delivery_roundtrip.py tests/test_codex_runner.py tests/test_cli_intervention.py tests/test_cli_intervention_recovery.py tests/test_execution_outputs.py
```

原始摘要：

```text
DUPLICATE_COMPLETION => summary accepts, collection final_reply_missing
NULL_USAGE => summary invalid_usage, real collection accepts
RESET_NOTICE normal => failed, 0 versions, 1 invocation(s)
RESET_NOTICE intervention => failed, 0 versions, 2 invocation(s)
RESET_NOTICE recovery => failed, 0 versions, 1 invocation(s)
STORAGE_RECOVERED => remains failed, 0 versions, no new invocation
160 passed, 2 skipped, 2 warnings in 21.60s
```

其中当时新增复现 8 passed，既有回归 152 passed / 2 skipped。两跳过为 Windows 无符号链接权限：`tests/test_final_delivery.py:261` 的 `symlinks unavailable on this host`、`tests/test_execution_outputs.py:114` 的 `OS does not grant symlink creation`；硬链接检查已运行。两个 warning 为 Starlette 的 httpx 和 BlockingPortal 弃用提示。中文打印被控制台编码替换，不影响用 UTF-8 写入的测试事件或断言。

第二批增加恢复路径存储对照，并验证任务/恢复/补收边界：

```text
.\.venv\Scripts\python.exe -m pytest -q -s ../../output/cli_acceptance_review/test_adversarial_delivery.py tests/test_execution_reconcile.py tests/test_repair_delivery.py tests/test_tasks.py tests/test_revisions.py tests/test_revision_execution.py
```

原始摘要：

```text
STORAGE_RECOVERED => remains failed, 0 versions, no new invocation
RECOVERY_STORAGE_RECOVERED => succeeded, 2 versions, no new invocation
94 passed, 6 warnings in 13.24s
```

其中新增复现 9 passed，既有回归 85 passed。警告为上述两条及 `app/modules/auth/dependencies.py:28` 的 4 条既有 NULL 主键 SQLAlchemy 提示。两批有 8 个复现重复运行，不将其当成新增覆盖数量。

语法编译命令及原始工具输出：

```text
.\.venv\Scripts\python.exe -m compileall -q app/execution app/worker/reconcile.py app/worker/repair_delivery.py app/modules/tasks/results.py app/modules/tasks/claims.py
exit_code: 0
output: ""
```

快照核对原始输出：

```json
{"currentId":"30176f8f46b4e4a112b05ea81624f34f6fbe8bfbe72177bbc775744070b5de9e","reviewedId":"30176f8f46b4e4a112b05ea81624f34f6fbe8bfbe72177bbc775744070b5de9e","changedFiles":[],"approved":true}
```

## 根治方向与验收边界

1. 统一证据模型：进程/事件诊断、交付验证、存储发布分别记录，三条执行路径共用同一判定实现。原始证据保留，不用一条 error 同时表达网络、用量、成品和存储失败。
2. 最终答复提取用调用状态机，交付引用用结构解析；每个已接收文件冻结字节/摘要、来源与槽位，使发布重试不重新解释可变文件。
3. 持久化恢复不重跑模型。按业务轮次和槽位保证幂等，避免每次补收重新创建无引用 FileRecord（当前 save_upload 每次 uuid4，`files/service.py:13–18`），发布仍走数据库短事务门禁。
4. 扩展回归必须覆盖同一输入在正常、续接、恢复下结论一致；重连多原因、合法 Markdown、重复终态、异常计量、存储/事务失败后恢复都要有对照，不能只验证某条英文文案。
5. 取消、跨任务、旧轮次、历史文件、输入冒充成品、链接逃逸、损坏/超限、数量不足与槽位歧义继续拒收。缺 exit 回执应保持待核实；非零退出、真正 turn.failed 仍遵守现有 Spec，若用户要扩展容错，先补充受限核实契约。

Stage 2 的质量、安全全量扫描与视觉比较未执行，不能据本报告宣称两阶段通过。本轮验证的是平台交付正确性，不是成品画面质量，也不是生产已修复或已补收。
