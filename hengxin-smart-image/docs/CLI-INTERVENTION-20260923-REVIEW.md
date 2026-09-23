# CLI 首轮换套图自动干预审查

最终复审结论：**Stage 1 PASS；Stage 2 PASS**，仅适用于 `a4bbb23a84540702a09d190fab3bccc551928e9f88d3e9fc2a15b76d6f67e10c`。初审失败及修复记录保留如下。未执行真实付费 CLI 生图或实际浏览器渲染验证。

## 快照与范围

- 初审 candidateId：`1e4c0817106845dc8f75c60cd9cfcbbffe831db71c161f18d4d8c4535fcc6b0f`。
- 上次批准快照：`daf60c91c556044428d09c1812be98cc6dac9f6d23c346f8430ce75469ea7d48`。
- 对比 review-state 中两份文件哈希，增量恰为 backend/app/execution/{codex_runner,intervention}.py、backend/app/modules/tasks/attempts.py、backend/app/worker/reconcile.py、backend/tests/{intervention_helpers,test_cli_intervention,test_cli_intervention_recovery}.py。
- 需求依据：根 Product-Spec.md:3、DEV-PLAN.md:3、Product-Spec-CHANGELOG.md:3 的 2026-09-23 自动干预条目。此前 CLI 升级、详情提示词、单张修改不重复验收。
- 审查只读代码、隔离测试及临时文件复现；无生产连接、部署、付费调用、提交。

## 初审 Stage 1：FAIL

### HIGH-01：会话不一致错误被覆盖后仍自动续跑

需求原文（Product-Spec.md:7）：会话丢失/不一致不续跑。

位置：backend/app/execution/intervention.py:46、:70；调用位置 codex_runner.py:182；关联既有解析器 events.py:41、:48、:71。

首次事件流依次含 `thread.started(session-A)`、`thread.started(session-B)`、`turn.failed(stream disconnected)` 时，解析器先记录 session_mismatch，随后覆盖为 turn_failed。新门禁允许 turn_failed，逐条扫描只检查认证/额度词，未验证会话一致性。因此存在 session-A 材料、退出码 1、剩余 300 秒时放行一次付费续跑。既有解析器问题由本次新增自动续跑路径转化为违反明确禁止条件的行为。

独立临时目录复现原始输出：

```text
EventSummary(session_id='session-A', usage=None, turn_completed=False, error='turn_failed')
can_continue = True
```

应保留结构性错误，或在新门禁中独立验证完整事件流的 session。需增加第一次调用出现 A→B→turn.failed/error 的 runner 回归，断言只有一次调用。

### 逐项对照

以下位置相对 hengxin-smart-image；结论仅限初审快照及所列证据。

| 需求 | 结论与证据 |
|---|---|
| 仅新任务首次壁纸/商品模板整套 | 完整实现。intervention.py:37 查询无其它轮次、无 target、限定模式及模板；codex_runner.py:103 要求无 previous。test_cli_intervention_recovery.py:19、:38 排除人工轮次及文字。 |
| 明确退出后，执行失败或最终交付失败均触发，不依赖模型措辞 | 完整实现。codex_runner.py:159 等 execute 返回，:165 判断结构化失败、:175 捕获收图错误；process.py:64 finally 等待子进程停止。test_cli_intervention.py:19 覆盖网络/退出码/缺图/无交付/坏路径。 |
| 同 session/home/work，保留文件与首次 baseline | 完整实现。codex_runner.py:185 续接 session，intervention.py:80 仅替换 control 并复制原 baseline。test_cli_intervention.py:19 与 intervention_helpers.py:36 验证第一调用候选、进度与基线复用。 |
| 通用干预先复核过度否决，再修复缺陷，不降低标准 | 完整实现。intervention.py:15 提示词逐段对应需求，:25 明确禁止不合格冒充成品。模型是否遵循未做真实付费验证。 |
| 首调外一次，成功整批发布，再失败终止 | 完整实现。codex_runner.py:142 双次上限、:182 只第一次可续跑、:176 精确张数；test_cli_intervention.py:49 断言无第三次及无发布。 |
| 共用总执行时限 | 完整实现。codex_runner.py:140 固定 deadline，:155 第二次扣除已耗时；test_cli_intervention_recovery.py:122 验证 3600→3480 秒，test_cli_intervention.py:76 验证耗尽不续跑。 |
| 取消/删除/租约失效不继续 | 完整实现。intervention.py:87 锁内 valid，codex_runner.py:143 每次启动前复验；test_cli_intervention.py:76 和 test_cli_intervention_recovery.py:96 验证取消和失效。 |
| 状态不明不继续，恢复只收图不重放 | 完整实现。codex_runner.py:224 标 uncertain；reconcile.py:105 检查精确 PID 身份，:122 仅解析/收图。test_cli_intervention_recovery.py:46、:75 验证二次 PID 和未知启动场景。 |
| 会话缺失/不一致不续跑 | 部分实现。intervention.py:50 检查缺失，test_cli_intervention.py:63；不一致存在 HIGH-01。 |
| 明确认证/额度/限流不继续 | 完整实现。intervention.py:31、:53、:71 扫描 stderr 和结构化错误；test_cli_intervention.py:63 覆盖认证、额度、限流及中文错误。 |
| 准备材料/保存/发布失败不重新生成 | 完整实现。codex_runner.py:112 在循环前准备，:193 在循环后保存发布；test_cli_intervention_recovery.py:134 验证保存失败。 |
| 文件安全、格式、完整性、数量继续校验 | 完整实现。codex_runner.py:176 复用 final_delivery.py:236 collect_final_outputs；后者逐图校验路径、硬链接、图片内容和整批对应关系。 |
| 干预前持久次数，独立证据，累计用量 | 完整实现。intervention.py:81 创建独立 control，:93 持久次数，:96 清旧 PID，:105 累加 summary；test_cli_intervention.py:19 与恢复测试验证累计 14/4 token 及单次逻辑 attempt。 |
| 时间线显示自动继续1/1 | API事件完整实现。intervention.py:100 写事件，test_cli_intervention.py:44 经真实 TestClient 验证返回文本。初审未执行实际浏览器视觉验证。 |
| 不部署、无迁移 | 范围匹配。增量文件仅上述七项，无迁移/新页面/API；执行未连接生产。 |

未实现项：会话不一致情况下的禁止续跑门禁，见 HIGH-01。未发现本范围新增页面、API 或数据表漂移。

## 初审验证证据

独立执行 `.venv/Scripts/python.exe -m pytest -q tests/test_cli_intervention.py tests/test_cli_intervention_recovery.py`，退出 0：

```text
.............................                                            [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
29 passed, 2 warnings in 9.10s
```

独立执行 `.venv/Scripts/python.exe -m compileall -q app/execution app/worker/reconcile.py app/modules/tasks/attempts.py`：原始 stdout/stderr 为空，退出码 0。

主 Agent 另提供全后端 894 passed、166 skipped、15 warnings 的结果；非本 reviewer 独立重跑，不用于覆盖 HIGH-01。

## 初审 Stage 2：未执行

Stage 1 存在 HIGH，按 code-review skill 停在 Stage 1。代码质量、安全扫描、实际视觉对比没有给出 PASS。主 Agent 已开始修复；代码发生变化必须重新固定 candidateId 并复核，初审结论不批准任何新快照。

## 修复后复审

主 Agent 修改了 intervention.py、intervention_helpers.py、test_cli_intervention.py，重新提供 candidateId：`a4bbb23a84540702a09d190fab3bccc551928e9f88d3e9fc2a15b76d6f67e10c`。reviewer 重新读取修复和上下游调用，从 Stage 1 复核以上全部条目，再进入 Stage 2。

### Stage 1：PASS

HIGH-01 已关闭：backend/app/execution/intervention.py:71 对每个 thread.started 独立检查 thread_id 等于 summary.session_id，不再依赖最后一次 error 值。backend/tests/intervention_helpers.py:57 构造第一次 A→B→turn.failed；backend/tests/test_cli_intervention.py:62 通过真实 runner 验证只有一次调用、失败终止且未消费干预次数。独立重跑 30 项通过。其余逐项对照结论不变，原“部分实现”现在为完整实现。

时间线渲染链进一步核对：frontend/src/views/hengxin/components/execution-presentation.ts:11 将非 Codex 前缀事件分入 timeline，:27 保留非阶段默认文案；ExecutionProgress.vue:56 遍历 timeline，:58 输出 timelineDetail。自动干预文本不会被丢弃。该事件在现有折叠的“系统时间线与诊断详情”内显示。

### Stage 2：PASS

| 审查项 | 结论与证据 |
|---|---|
| 结构、职责、文件规模 | 通过。本次七文件行数依次为230、123、56、167、74、99、141，均不超300。intervention.py:37/44/80/107 分离范围判定、门禁、持久准备、用量合并；codex_runner.py:142 控制两次调用，reconcile.py:122 复用同一 summary，未复制累计逻辑。 |
| 类型与错误处理 | 通过本次增量。intervention.py:46 要求确切 int 退出码，:115 检查用量键值类型及非负值；:73 拒绝不可读或非法事件。codex_runner.py:210 保留明确结束和未知执行的分流。没有新增 any 绕过类型边界。 |
| 测试真实性 | 通过。intervention_helpers.py:17 仅替换外部 execute 边界，真实材料准备、数据库门禁、文件交付校验、用量写入和 HTTP 事件读取仍执行。test_cli_intervention.py:19 验证保留候选/基线；恢复测试:46 验证二次 PID及重复恢复幂等，:75 验证旧 PID 清理；新增 session_change 场景确实经过 runner。无付费模型质量或真实 Linux 子进程验证声明。 |
| 安全扫描 | 本次增量未发现问题。对七文件搜索 eval/exec调用、innerHTML、dangerouslySetInnerHTML、密钥前缀、password赋值、拼接SQL及前端密钥变量，无命中。intervention.py:65 使用有限额安全读日志，固定提示词未拼接 shell；codex_runner.py:146 使用参数列表；intervention.py:87 使用已有事务锁门禁，reconcile.py:108 保留控制路径边界与符号链接检查。 |
| Spec 漂移 | 未发现。本次七文件没有新页面/API/表或额外任务类型；attempts.py:25 仅注释说明单逻辑 attempt 内部续接。 |
| 视觉对比 | 本次无前端代码、布局或样式变更，无新页面可与邻居比较，视觉布局项不适用。没有打开浏览器，不声称视觉验证通过；显示文本的数据契约和现有渲染链已在 Stage 1 核对。 |

### 修复后验证原始证据

独立命令 `.venv/Scripts/python.exe -m pytest -q tests/test_cli_intervention.py tests/test_cli_intervention_recovery.py`，退出码0：

```text
..............................                                           [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
30 passed, 2 warnings in 7.84s
```

独立编译命令 `.venv/Scripts/python.exe -m compileall -q app/execution app/worker/reconcile.py app/modules/tasks/attempts.py`：原始 stdout/stderr 为空，退出码0。

复审结束时独立运行 harness.py review-status：currentId 为 `a4bbb23a84540702a09d190fab3bccc551928e9f88d3e9fc2a15b76d6f67e10c`，reviewedId 仍为先前 `daf60c91c556044428d09c1812be98cc6dac9f6d23c346f8430ce75469ea7d48`，approved=false；changedFiles 为本报告七文件。当前代码与送审 candidateId 相同。reviewer 未写 clean 或登记批准；由主 Agent 对此最终快照执行 review-approve。
