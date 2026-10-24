# 工作台可靠收图核心审查 · 2026-10-24

- candidateId：`c2c523e34fb1edd5fa1228caafb1a17ce5bbcdb8780b40f2f80e19163f73c410`
- 审查范围：`hengxin-smart-image/backend/app/overseas/studio/` 的 completion、delivery、native 识别、私有快照、恢复、repair、查询及其接入的 execution runner/reconcile；前端 `src/api/overseas/studio.ts`、`StudioTurns.vue` 保存状态及相关测试。
- 排除：另一 worker 修改中的 release 脚本、版本发布动作、用户自行修改的 `AGENTS.md`、生产写入和 Git 操作。未修改受审产品代码或 Skill，未启动模型。
- 需求原文：`Product-Spec.md:1336`、`DEV-PLAN.md:1558`、`docs/STUDIO-DELIVERY-RELIABILITY-20261024.md:5-24`。按最新“最后输出即收、历史同会话可复用、不扫描临时图”规则审查。
- 规划：逐条核对最终识别 → 故障/恢复/租约与删除 → 状态与原八图 repair → Stage 1 通过后才执行 Stage 2。发现 HIGH 即向主 Agent 回报。

## 结论

**Stage 1：FAIL。HIGH 1 项。Stage 2：未执行。不得登记两阶段 PASS。**

### HIGH-1：历史同会话图片原生再次展示且本轮没有生成事件时静默丢图，并发布 0/0 完成

**Spec 原文**：合同 `:7` 要求“最终回复中的图片引用、下载图片链接和原生附图均接收”；`:9` 要求“同一授权会话的历史图片可在本轮重新交付，不要求前轮已经交付。已存图片本轮再次给出也要展示”；`:16` 要求“全部保存才交付完成”。

**实现差异及定位**：

1. `backend/app/overseas/studio/native_images.py:54` 每轮重新创建空 `generated`；`:72-84` 只收集该轮的 `image_gen.generation`，`:133-134` 将最终实际展示的 digest 与该轮 `generated` 交集。历史文件即使已存在、同会话、可解码且最终原生展示，也被丢弃。
2. `backend/app/overseas/studio/delivery.py:99-111` 对该情况返回空 references、空 warnings。无文字最终回复不触发“称已生成”告警。
3. `backend/app/overseas/studio/delivery_snapshot.py:32-34` 把空 targets 视为 ready；`delivery_job.py:174-179` 因而将任务置为 `succeeded`、交付 `complete 0/0`，并允许后续轮次开始。最终图片没有入库，无明确失败提示。

**独立复现**：`output/studio-delivery-reliability-20261024/test_reviewer_native_history_e2e.py:15` 使用真实 runner、Studio API、数据库与本地真实 PNG；仅替换进程边界及外部存储。第一轮留下同会话原生 PNG 和成功生成证据；第二轮通过 `custom_tool_call_output/input_image` 公开展示同一 PNG，metadata 绑定第二轮，最后 `AgentMessage(final_answer)` 的文字为空，随后 `task_complete` 与 CLI 正常退出。本轮没有生成图片事件，符合用户“不要求当轮新生成”的输入。

运行命令（backend 工作目录）：

```text
.venv/Scripts/python.exe -m pytest ../../output/studio-delivery-reliability-20261024/test_reviewer_native_history_e2e.py -q -s --junitxml=../../output/studio-delivery-reliability-20261024/reviewer-native-history-failure.xml
```

原始关键输出：

```text
{"status": "succeeded", "deliveryStatus": {"state": "complete", "expected": 0, "saved": 0}, "pictureCount": 0, "error": null}
E       AssertionError: Final historical native image was silently lost
E       assert 0 == 1
E        +  where 0 = len([])
FAILED ../../output/studio-delivery-reliability-20261024/test_reviewer_native_history_e2e.py::test_historical_native_without_new_generation_must_not_complete_with_zero
1 failed, 2 warnings in 2.95s
```

另有最小解析链复现 `output/studio-delivery-reliability-20261024/reviewer_native_history_repro.py:17`：`read_current=[]`、`enumerate=([], {}, [])`、`collected=0 warnings=[]`。

**修复验收要求**：在当前轮准确呈现边界内，允许最终展示 digest 解析到该授权会话历史原生文件；保持跨会话、输入路径、真实字节和数量限制。应验证前轮未交付与已交付两种情况、空文字、同轮重试幂等、跨轮独立对象、最终批次顺序及历史证据异常时不得假报 0/0 完成。不得通过要求额外 Markdown 链接、交付声明或重新生成规避。

## Stage 1 逐条核对

以下“局部实现”仅描述可定位代码及本次测试证据，不等于整阶段通过。路径前缀均为 `hengxin-smart-image/`。

| 条款 | 结论 | 代码与验证证据 |
| --- | --- | --- |
| 最终回复，无固定标题/“正式”措辞；显式列表优先 | 局部完整实现 | `backend/app/overseas/studio/delivery.py:24-46,70-101`；`tests/test_studio_delivery_bridge.py:51,57,177` 验证预览措辞仍接收、显式列表排除其他原生图、17 过程生成仅取最终 8 图，本次通过。 |
| 正常退出、最后完成回执、中途确认、多 final；当前轮边界 | 局部完整实现 | `backend/app/overseas/studio/completion.py:49-137`；`native_images.py:85-90,113-121`、`native_rollout.py:109-140`；`tests/test_studio_completion.py:79,94,101,110,145` 本次通过。无有效成功回执不凭现有文件判成功，见 `tests/test_studio_delivery_fencing.py:136`。 |
| 文字引用不受无关原生解析故障阻断 | 完整实现 | `backend/app/overseas/studio/delivery_evidence.py:17-34`，`tests/test_studio_delivery_bridge.py:161,169` 本次通过。 |
| 同会话历史 work/native 可复用；本轮再次交付独立版本 | **部分实现，HIGH-1** | Markdown 引用已实现：`delivery.py:117-131` 不传旧文件禁用表；`delivery_snapshot_fs.py:46-48` 以 job+规范路径生成身份；`tests/test_studio_delivery_recovery.py:170` 验证跨轮图片/对象不同且原字节相同。本轮历史图片原生展示仍失败，详见上方全链复现。 |
| 私有原图快照、最终回复/顺序/摘要；部分捕获失败不让后轮覆盖 | 局部完整实现 | `backend/app/overseas/studio/delivery_job.py:120-164`、`delivery_snapshot.py:28-92`、`delivery_snapshot_fs.py:117-154`。`tests/test_studio_delivery_recovery.py:92,112,146`、`test_studio_delivery_snapshot.py:108,123,148,227,242` 覆盖覆盖原文件、回执复制/退出状态/正文保存错误、原子替换各边界及恢复，本次通过；目录 fsync 的真实 Linux 行为待另组证据。 |
| 持久逐图补收、未知上传结果、DB 失败、台账 | 局部完整实现 | `backend/app/overseas/studio/delivery_job.py:70-100` 先提交对象台账，再验证已有对象或 put，Picture 与所属 turn 同事务；`tests/test_studio_delivery_recovery.py:16,53,70` 本次通过。已上传但 DB 失败恢复不会重复 put。 |
| 新租约、迟到上传、取消/任务和会话删除、cleanup | 局部完整实现 | `backend/app/overseas/studio/delivery_job.py:22-35,99`；`delivery_recovery.py:45-57`；`backend/app/overseas/execution/reconcile.py:28-40`；`tests/test_studio_delivery_fencing.py:39,63,80,100` 本次通过。真实 PG 2/4 worker 同时争抢由另一 worker 执行，本报告未将其标为已验证。 |
| 自动补收有退避且不再启动模型 | 局部完整实现 | `backend/app/overseas/studio/delivery_job.py:103-117` 指数退避；`delivery_recovery.py:19-72` 调用 deliver，未调用 CLI；`tests/test_studio_delivery_recovery.py:16,53` 检查 commands/execution_count 未增加；`test_studio_delivery_repair.py:94` 恢复时执行器被设为必失败，测试仍通过。 |
| 保存中真实数量、部分立即可见、齐全才完成 | **部分实现，HIGH-1** | 通常失败路径已覆盖：`backend/app/overseas/studio/queries.py:103-115`、`delivery_job.py:38-57,163-179`；前端 `src/api/overseas/studio.ts:19-23,47` 和 `StudioTurns.vue:11-15,31-36`；前端状态专项 3/3 通过。HIGH-1 路径假报成功，无图无提示。 |
| 必要校验：真实图片、归属、路径、资源限制；不扫描临时图 | 局部完整实现 | `backend/app/overseas/studio/delivery.py:49-66,117-131`、`delivery_snapshot_fs.py:79-113`；`backend/app/execution/final_delivery.py:48-81` 对只读输入、跨会话、路径/硬链接限制；`tests/test_studio_delivery_snapshot.py:184,191,217` 本次路径/数量/元数据测试通过，3 项链接测试因 Windows 能力跳过。当前交付枚举来自最终引用/呈现事件，没有工作目录候选收集。 |
| 原八图 repair，证据绑定、只读预检、审计、幂等、不重生 | 局部完整实现，生产补收未验收 | `backend/app/overseas/studio/delivery_repair.py:23-45,48-87` 校验事件 hash、每图 hash、原正常退出、权限/暂停/排空并复用 deliver；`tests/test_studio_delivery_repair.py:58,82,94` 本次通过。读取主 Agent 证据 `output/studio-delivery-reliability-20261024/original-eight.json:1`，记录 8 张 1600×1600 JPG 及各原图摘要；本审查没有冒充自行复核生产写入、预览或下载。 |
| 发布、实际安装验证、原八图生产恢复、中文 Git 推送；保护 Skills/国内 | 本子范围未完成且不批准 | 合同 `docs/STUDIO-DELIVERY-RELIABILITY-20261024.md:18`；按主 Agent 派发另组审查 release。当前 HIGH 修复并重新快照复核前，不满足合同“测试与独立审查通过后部署”的条件。 |

## 测试与编译证据

本次独立运行 6 个核心测试文件：completion、delivery_bridge、delivery_recovery、delivery_fencing、delivery_repair、delivery_snapshot。原始汇总：

```text
114 passed, 3 skipped, 2 warnings in 21.45s
```

JUnit：`output/studio-delivery-reliability-20261024/reviewer-core-tests.xml`。3 个 skip 是 Windows 无创建符号链接权限；FastAPI/Starlette 的 2 个弃用警告不影响此次断言。

前端命令：`node node_modules/tsx/dist/cli.mjs --test tests/studio-delivery-status.test.ts`。原始输出：

```text
✔ 保存进度DTO兼容旧响应并接收真实数量，拒绝未知状态和非法数字 (1.5484ms)
✔ 真实消息组件收图期间立即展示已存图片并更新进度，完成后移除提示 (23.3569ms)
✔ 旧轮次没有收图状态时不增加提示或额外操作 (2.0744ms)
ℹ tests 3
ℹ suites 0
ℹ pass 3
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1124.3585
```

编译：本次未执行编译。主 Agent 提供的前端全套/构建及 Linux 完整回归结果不替代本报告的独立验证，最终整包审查需引用对应原始输出。新增对抗用例 1 failed，不能用既有 114 passed 覆盖。

## Stage 2

**未执行**：按 code-review skill，Stage 1 有 HIGH 时停止。代码质量、安全扫描及新旧页面实时渲染对比不作 PASS 声明；本报告无“两阶段通过”或 clean 凭据。

## 快照边界

发现并复现 HIGH-1 时，completion、delivery*、native_images/native_rollout 逐文件归一化 SHA-256 与上述 candidate 的记录一致。该报告不覆盖后续修复；主 Agent 必须重新 `review-prepare`，对新快照从 Stage 1 复核，再决定是否执行 Stage 2。Release worker 的同期修改不在本报告结论内。
