# 最终回复收图独立审查 · 2026-09-17

- candidateId：`d20c54f18fcb2ed9eec66c9dbc3fccb1ae31460eb79781d0e355989f86c217d2`。
- 范围：本候选相对已批准版本的 14 个后端代码/测试文件，包括新增 `final_delivery.py`、两个最终回复测试，以及已在工作树的 Astra/high 固定参数。依据 `Product-Spec.md:477`、`:479` 与 `DEV-PLAN.md:3` 当前调整；未重新验收历史全产品功能。
- 开始及完成复现/测试后运行 `review-status`，currentId 均为上述候选。报告收尾时主 Agent 已开始修复，最后检查 currentId 变为 `da161b3df27bd6905fcb356c5df5dca38f68c7a2a5b2abf8e298ddedd85773ce`；本报告的结论、测试与代码行号仅针对原候选，不覆盖该新版本，修复内容未在此复核。
- **Stage 1：FAIL。Stage 2：未执行（Stage 1 存在 HIGH）。禁止登记两阶段 PASS。**

## Stage 1：发现的问题

### HIGH · FR-01：清晰编号变体被忽略，整套结果静默错配

Spec `Product-Spec.md:479`：按清晰编号或展示顺序对应本轮底图，不猜测缺失槽位。

`backend/app/execution/final_delivery.py:19` 仅识别 `主图` 紧接数字；`:120` 未匹配的标签变为 `None`；`:175`–`:181` 将全部未识别编号当成无编号，直接保持显示顺序。如下清晰标注的最终回复按 4、2、3、1 展示时，返回文件也是 4、2、3、1：

```markdown
![主图 (4)](/work/final_4.png)
![主图 (2)](/work/final_2.png)
![主图 (3)](/work/final_3.png)
![主图 (1)](/work/final_1.png)
```

`![第4张]`、`![第2张]` 等也复现相同问题。`backend/app/modules/tasks/results.py:15`–`:20` 再按结果槽升序 zip，导致槽 1 获得图 4、槽 4 获得图 1，并被发布为成功。这是结果归属错误，不能归为可选格式增强。

建议：识别常见明确编号表达及标题；存在编号线索但无法无歧义解释时明确拒绝，不能静默退回顺序。测试应覆盖乱序括号编号、`第 N 张`、混合编号、冲突编号及最终发布槽位。

### MEDIUM · FR-02：同一成品同时预览和下载会被按两张计数

`backend/app/execution/final_delivery.py:73` 收集全部引用，`:173` 在规范化路径/识别文件之前检查链接数。四张成品各同时展示 `![主图1](/work/final_1.png) [下载](/work/final_1.png)` 时，8 个引用导致 `final_output_count_mismatch`，虽实际明确交付的唯一成品为 4 张。

Spec `Product-Spec.md:479` 要求完整成品列表并阻止重复文件；它没有要求一张成品只能出现一次链接。当前代码把重复呈现同一成品和用同一文件填充不同底图槽混为一谈。

建议：先按受控规范路径归并一致的展示/下载引用，再检查唯一文件数量；相同文件被明确分配到不同编号仍拒绝，别放松重复槽位保护。补充同图嵌图+下载、相对/绝对路径别名、编号冲突用例。

## Stage 1：逐项核对

以下路径以 `hengxin-smart-image/` 为前缀；除注明外，验证来自本次独立执行的 90 项回归。

| 当前需求 | 结论与证据 |
|---|---|
| 两个 Skill 保持原样，名称调用，简洁图片/意见 prompt | 完整实现。代码差异未含 Skill 文件；`backend/app/execution/prompts.py:9`–`:34` 使用 `$名称`、实际路径、三种模式要求和 JSON 引用意见，不再附平台 manifest/内部任务 JSON/原生来源限制；`tests/test_task_prompt.py:16`、`:29`、`:35`、`:45` 通过。 |
| 完整冻结 Skill 两处只读可见 | 代码完整。`backend/app/execution/workspace.py:92`–`:103` 对本地及旧 ZIP Skill 都 ro-bind 至 work 与私有 HOME 发现目录，遮盖旧发现目录；真实 Linux 61 项是主线提供证据，本轮未另行运行，不能算 reviewer 实测。 |
| 仅当前调用最终 assistant 答复 | 完整实现。`backend/app/execution/final_delivery.py:22`–`:52` 限制最后事件为 turn.completed、前一项为完成 agent_message，校验 session；`:55`–`:70` 排除代码文本。`tests/test_final_delivery.py:53`、`:67`、`:115`、`:196` 通过。 |
| 明确本地图片引用及空格/括号/角括号/编码路径 | 完整实现。`backend/app/execution/final_delivery.py:73`–`:124`；`tests/test_final_delivery.py:80` 路径参数化测试通过；真实 events 回放另行通过。 |
| 清晰编号优先，否则按展示顺序；完整数量 | **部分实现，FR-01 HIGH、FR-02 MEDIUM**。标准 `主图1` 乱序可排序，但明显编号变体会错槽，重复呈现会拒绝完整成品。 |
| 不收候选、较早消息、旧轮次答复；允许合成修复图 | 完整实现。`backend/app/execution/final_delivery.py:43`–`:52`、`:169`–`:170` 不扫描候选目录；runner `:167` 直接交给收集器，无原生 hash 条件。`tests/test_final_delivery.py:44`、`:53`、`:86` 与 `tests/test_final_delivery_roundtrip.py:70` 通过。 |
| 本轮 work 排除输入/当前图/Skill；本会话原生仅新文件 | 完整实现。`backend/app/execution/final_delivery.py:127`–`:159` 限制逻辑路径，baseline 中原生文件无论内容变化都拒绝；`backend/app/execution/codex_runner.py:116`–`:119` 启动前快照。`tests/test_final_delivery.py:98`、`:133` 通过。 |
| 拒绝越界、链接、重复文件，校验解码/格式/大小 | 受控读与校验实现于 `backend/app/execution/final_delivery.py:151`–`:198`，复用 `output_collector.py:21`、`diagnostics.py:79`、`modules/files/validation.py:35`。损坏/目录/越界/重复测试通过；Windows 符号链接测试因宿主权限跳过，硬链接部分已执行。重复引用问题另见 FR-02。 |
| 缺失/不完整/无效明确失败，不声称视觉合格 | 完整实现。`backend/app/execution/diagnostics.py:14`–`:19` 提供相应错误，runner `:186`–`:198` 结束失败；恢复缺图测试 `tests/test_execution_reconcile.py:232` 通过。没有新增视觉验收承诺。 |
| 取消/无权不得发布，单图及整套返工 | 完整实现。runner `:154`–`:168`、`:181`，`modules/tasks/results.py:13` 原子核验权属；`tests/test_codex_runner.py:156` 与 `tests/test_final_delivery_roundtrip.py:70` 通过。单图原编号 `tests/test_final_delivery.py:92` 通过。 |
| 新旧恢复兼容，同一收图逻辑、未知协议不降级 | 完整实现。runner `:119` 写 marker；`backend/app/worker/reconcile.py:134`–`:150` 按 marker 选择新收集器或历史 manifest+provenance，`:158`–`:167` 新协议收图失败明确结束；当前恢复专项通过。未删除旧来源校验。 |
| 新任务和 resume 固定 Astra/high | 完整实现。`backend/app/execution/codex_runner.py:132`–`:137` 两支共享参数；`tests/test_codex_runner.py:113`、`:136` 通过。 |
| 不改前端、无新 UI/接口/表/Skill 协议漂移 | 送审变更仅后端执行链与测试，git diff 无前端和 Skill 改动；无需新页面视觉比较。本次未部署或进行在线付费生成。 |

## 独立验证与原始输出

运行目录 `hengxin-smart-image/backend`，使用已有 `.venv/Scripts/python`。系统 Python 无 fastapi，首次探测出现 `ModuleNotFoundError: No module named 'fastapi'`；改用项目虚拟环境完成验证，未更改依赖。

复现实验：临时目录创建四个不同颜色的有效 PNG，构造一轮 thread.started / 最终 agent_message / turn.completed，通过生产 `collect_final_outputs` 读取。原始输出：

```text
parenthesized ['final_4.png', 'final_2.png', 'final_3.png', 'final_1.png']
chinese ['final_4.png', 'final_2.png', 'final_3.png', 'final_1.png']
duplicate OutputCollectionError final_output_count_mismatch
```

命令 `.venv/Scripts/python -m pytest tests/test_final_delivery.py tests/test_final_delivery_roundtrip.py tests/test_execution_reconcile.py tests/test_task_prompt.py tests/test_codex_runner.py -q`：

```text
.............................................s.......................... [ 79%]
...................                                                      [100%]
90 passed, 1 skipped, 2 warnings in 7.93s
```

两条 warning 为 Starlette 对 httpx TestClient 和 anyio BlockingPortal 别名的弃用提示。现有通过测试未覆盖本报告复现的编号和重复引用形态，不能推翻失败结论。

编译命令 `.venv/Scripts/python -m compileall -q app tests` 原始 stdout/stderr 为空，退出码 0。

命令 `.venv/Scripts/python -m pytest ../../output/diagnostics/exact-prompt/test_replay_delivery.py -q`：

```text
.                                                                        [100%]
1 passed, 2 warnings in 2.34s
```

回放脚本 `output/diagnostics/exact-prompt/test_replay_delivery.py:17`–`:32` 以实际归档 events 和四 PNG 替代 CLI 执行，真实经过 HTTP 接纳、runner、测试存储与下载并断言字节相同。证明该实际回复格式可用；不证明任意回复均可解析，不等于线上生成验收。主线其他后端全套、Linux、前端证据见 `FINAL-REPLY-DELIVERY-VALIDATION.md:11`，本 reviewer 不声称重新执行。

## Stage 2

未执行。按 code-review skill，Stage 1 存在 HIGH 时停止，不出具安全扫描、完整代码质量或两阶段 PASS。主 Agent 修复后需重新 review-prepare，并从 Stage 1 开始独立复核新候选；不得批准本候选或将本报告套用到新版本。
