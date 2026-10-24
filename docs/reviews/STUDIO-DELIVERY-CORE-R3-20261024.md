# 工作台可靠收图核心审查 R3 · 2026-10-24

- candidateId：`9cb2e67477d2caa74471b72a53e8e1b3b9ae57a89fd280cd56c8ee896a53ef2d`。
- 审查范围：`hengxin-smart-image/backend/app/overseas/studio/` 最终识别、私有快照、逐图保存、恢复、repair、查询；相关 `backend/app/overseas/execution/runner.py`、`reconcile.py`；前端保存状态 DTO、`StudioTurns.vue` 及其功能测试。
- 排除：`scripts/release`（独立 reviewer 负责）、生产发布/补收实际执行、用户修改的 `AGENTS.md`、Skills、Git 操作。未修改产品代码、未调用模型、未另派子 Agent。
- 源需求：`Product-Spec.md:1336`、`DEV-PLAN.md:1558`、`docs/STUDIO-DELIVERY-RELIABILITY-20261024.md:5-24`；前轮报告 `docs/reviews/STUDIO-DELIVERY-CORE-20261024.md`。
- 审查规划：按合同 1–5 及 repair 依次核对最终选择、持久化与故障恢复、租约/取消/删除、前端状态；Stage 1 无 HIGH 后才进入 Stage 2。

## 结论

**Stage 1：FAIL，新增 HIGH 1 项。Stage 2：未执行。不得登记两阶段 PASS。**

前轮“成功历史轮次的原生图片本轮重展 → 0/0 完成”已修复：`backend/app/overseas/studio/native_images.py:218-231` 回查启动 cursor 以前的记录；未知摘要抛错而不返回空集合。当前仍将历史轮次的最终状态作为取图门槛，导致另一条真实可达路径永久卡在收图。

## HIGH-1：旧轮成功生成图片后整轮失败，本轮正常重展仍被旧轮失败状态拒收

**需求**：合同 `docs/STUDIO-DELIVERY-RELIABILITY-20261024.md:7` 规定正常结束时最终回复实际输出的原生附图接收；`:9` 规定“同一授权会话的历史图片可在本轮重新交付，不要求前轮已经交付”，只保留真实文件、会话归属、图片解码及资源限制等必要校验。`:22` 的非零退出禁止冒充成功，应作用于正在判定交付的本轮，不能否决后一正常成功轮次重新给出的有效图片。

**真实可达输入**：第一轮的 `image_gen.generation` 已 `completed`，合法 PNG 已保存在本会话 `generated_images/session-123/old.png`；随后该轮因其他执行错误 `task_failed`、CLI 退出码 1，业务正确标为失败。用户续聊，第二轮只公开展示旧 PNG，`AgentMessage(final_answer)`、`task_complete`、CLI 退出码 0 全部正常，图片 bytes 与旧 generation 摘要完全相同。

**错误位置**（以下路径以 `hengxin-smart-image/` 为前缀）：

1. `backend/app/overseas/studio/native_images.py:158-163`：`generation_history=True` 时遇到旧轮 `task_failed` 仍清空 `active`，此前已成功的 `generated` 全部丢弃。
2. 同文件 `:175-179`：旧轮 `task_complete` 带失败状态同样丢弃已经成功生成的图片。
3. 同文件 `:224-231`：当前成功轮次已选中的公开摘要无法映射回上述真实旧文件，抛 `Displayed native image file is not yet available`。
4. `backend/app/overseas/studio/delivery_evidence.py:33-37` 转为无法读取交付记录；`delivery_job.py:133-135` 拒绝建立选择清单。`runner.py:189-196` 和 `delivery_recovery.py:63-69` 只能重复收取同一固定失败历史，无法自动恢复。

**实际结果**：第二轮没有图，状态一直 `collecting` / `capturing`；不是前轮的假成功问题，但同样违反核心“本轮最后实际输出即收”的要求，并占住会话后续轮次。加入 Markdown 链接才能绕过不符合用户无需固定交付格式的要求。

**独立全链复现**：`output/studio-delivery-reliability-20261024/test_reviewer_r3_historical_failed_turn.py:13`。使用真实 Studio API、runner、数据库、真实可解码 PNG；只替换 CLI 进程边界和外部对象存储。第一轮失败后，第二次发送 API 返回 200，证明该输入可经正式业务接线到达。没有直接改写业务数据库制造不可能状态。断言与输出位于该文件 `:63-67`。

命令（backend 工作目录）：

```text
.venv/Scripts/python.exe -m pytest ../../output/studio-delivery-reliability-20261024/test_reviewer_r3_historical_failed_turn.py -q -s --junitxml=../../output/studio-delivery-reliability-20261024/reviewer-r3-historical-failure.xml
```

原始关键输出：

```text
{"status": "collecting", "deliveryStatus": {"state": "capturing", "expected": null, "saved": 0}, "pictureCount": 0, "error": null}
E       AssertionError: A successful old generation is wrongly gated by its old turn failure
E       assert 0 == 1
E        +  where 0 = len([])
WARNING  app.overseas.studio.delivery_evidence:delivery_evidence.py:36 Studio native delivery evidence rejected
FAILED ../../output/studio-delivery-reliability-20261024/test_reviewer_r3_historical_failed_turn.py::test_successfully_generated_image_from_failed_old_turn_can_be_redisplayed
1 failed, 2 warnings in 6.63s
```

**修复验收**：本轮的正常退出、精确终态和实际呈现仍须严格校验；历史回查只为本轮选中的摘要解析同会话真实文件，不再要求旧轮最后成功或曾交付。保留成功 generation 元数据、路径归属、校验值/可解码校验，不自动收旧失败轮未在本轮展示的图片。补测旧轮后续失败/中断/另一图片生成失败、同轮新过程图与历史最终批次、摘要无法关联、跨会话、重复补收和跨轮独立对象。修复后重新固定 candidate 并从 Stage 1 复核。

## Stage 1 逐条核对

下表“完整实现”仅是各项具体代码及本轮执行证据，不代表整个阶段通过。路径前缀为 `hengxin-smart-image/`。

| 合同要求 | 结果 | 代码与验证证据 |
| --- | --- | --- |
| 1：正常退出、准确完成回执，中途确认不是终态，多 final 取实际完成者 | 完整实现 | `backend/app/overseas/studio/completion.py:47-129`、`backend/app/overseas/execution/runner.py:138-156`；`tests/test_studio_completion.py:29,50,79,94,101,110,145` 本轮通过。非零退出/缺回执/事件截断不得因已有图判成功，`tests/test_studio_delivery_fencing.py:136` 通过。 |
| 1：最终链接无标题或正式/预览措辞门槛；最终显式列表优先、不混入过程图 | 完整实现 | `backend/app/overseas/studio/delivery.py:22-43,79-105`；`tests/test_studio_delivery_bridge.py:51,57,177` 通过，含 17 过程图仅取最终 8 图。 |
| 1：准确当前轮边界，重试不读取后来轮次，最后原生批次按展示顺序 | 局部完整实现 | `backend/app/overseas/studio/native_rollout.py:109-138`、`native_images.py:113-131,202-217`；`tests/test_studio_native_images.py:278,289,299,322,351,393` 通过。历史旧轮失败见 HIGH-1。 |
| 1：最终文字链接不受无关原生解析故障阻断 | 完整实现 | `backend/app/overseas/studio/delivery_evidence.py:16-29`；`tests/test_studio_delivery_bridge.py:161,169` 通过。 |
| 1/4：同会话历史 work/native 文件允许重新交付，不要求前轮正式交付；已存图本轮仍展示 | **部分实现，HIGH-1** | 显式引用：`delivery.py:109-121`；成功旧轮的原生回查：`native_images.py:218-231`；`tests/test_studio_delivery_recovery.py:171,206`、`test_studio_native_images.py:362,373` 通过。旧轮成功生成后失败的本轮重展由本报告反例证实失败。 |
| 2：私有最终回复、选中路径、按序原字节与摘要，原子提交和落盘 | 完整实现 | `backend/app/overseas/studio/delivery_job.py:124-164`、`delivery_snapshot.py:28-92`、`delivery_snapshot_fs.py:48-56,76-112,130-154`；`tests/test_studio_delivery_snapshot.py:36,77,84,108,123,148,227,242` 通过。本地 Windows 无法替代 Linux 的真实目录 fsync 验证，Linux 由主 Agent 另组进行。 |
| 2：捕获失败保留原任务活动状态、恢复依据与目录，后轮不得覆盖 | 完整实现 | `backend/app/overseas/execution/runner.py:187-196`、`studio/delivery_job.py:103-117`、`delivery_context.py:21-60`；`tests/test_studio_delivery_recovery.py:17,93,113,147` 通过，含快照前/中断、退出回执复制/DB 退出状态/正文持久化失败。 |
| 3：复用 Job/Turn、确定性图片身份、对象台账先提交、逐图入库 | 完整实现 | `backend/app/overseas/studio/delivery_snapshot_fs.py:48-50`、`delivery_job.py:60-100`；`tests/test_studio_delivery_recovery.py:17,54,71` 通过，覆盖单图失败、上传结果不明、上传成功而 DB 提交失败。 |
| 3：已上传对象检查摘要后复用，仅补缺失项；图片与当前轮关联同事务 | 完整实现 | `backend/app/overseas/studio/delivery_job.py:70-100`；`tests/test_studio_delivery_recovery.py:54,71` 验证重试无第二次 put、对象数与图片数一致；`files.py:54-69` 校验存储内容大小与 SHA256。 |
| 3：失效租约/迟到上传/取消/任务删除/会话删除不能发布结果 | 完整实现 | `backend/app/overseas/studio/delivery_job.py:22-35,88-100`、`delivery_recovery.py:45-57`、`backend/app/overseas/execution/reconcile.py:28-40`；`tests/test_studio_delivery_fencing.py:39,63,80,100` 通过，含删除真实清理后旧 collector 重放。真实 PG 并发证据由另组负责，本报告不将本地 SQLite 验证等同 PG 并发验证。 |
| 4：保存未齐显示实际数量、成功部分立即可见、全部保存才 complete | 局部完整实现 | `backend/app/overseas/studio/queries.py:103-115`、`delivery_job.py:38-57,163-179`；前端 `src/views/overseas/studio/StudioTurns.vue:11-15,31-36`。前端专项 3/3 本轮通过；核心失败场景 `test_studio_delivery_recovery.py:17` 通过。HIGH-1 会永久处于 capturing，不能总体验收。 |
| 4：自动补收退避、不调用模型、不重复图片/对象，跨轮独立交付版本 | 完整实现 | `backend/app/overseas/studio/delivery_job.py:103-117`、`delivery_recovery.py:19-72`、`delivery_snapshot_fs.py:48-50`；`tests/test_studio_delivery_recovery.py:54,71,171`、`test_studio_delivery_repair.py:94` 通过，验证 execution_count/commands 不增长、跨轮对象与图片 ID 不同而字节相同。 |
| 5：真实文件、会话归属、可解码、路径逃逸/受保护输入/链接及资源上限 | 局部完整实现 | `backend/app/overseas/studio/delivery.py:46-62,109-121`、`delivery_snapshot_fs.py:76-112`，沿用 `backend/app/execution/final_delivery.py` 的受保护目录/安全文件检查；`tests/test_studio_delivery_snapshot.py:184,191,217` 通过可执行项，4 项符号链接测试因 Windows 权限 skip。未把 skip 声称为已验证。 |
| 5：正常最终混合文字图片、缺文件、存储/DB/崩溃/删除/原图哈希等故障测试 | **部分实现** | 本轮独立 174 passed、4 skipped；新增历史失败后正常重展反例 1 failed。用现有回归数量无法覆盖这一合同缺口。 |
| repair：权限、暂停与排空、原成功退出、事件 hash、每图 hash、审计、幂等，不重生 | 完整实现（代码范围） | `backend/app/overseas/studio/image_recovery.py:30-56` 维护权限和暂停/任务排空；`delivery_repair.py:23-44,48-87` 验证原事件/字节及会话删除，复用 collect，记录审计；`tests/test_studio_delivery_repair.py:58,82,94` 本轮通过。测试将 runner.execute 设为必失败，恢复仍成功。 |
| 6：原任务八图生产补回、安装升级/健康/浏览器下载哈希、提交推送 | 本子范围不验收 | 属另组发布和真实生产执行，原八图 hash 或原生历史生产记录只读重放不等于本次代码已满足全部正常输入。当前 Stage 1 FAIL，不能以此报告作为发布两阶段批准凭据。 |

## 测试与编译结果

本轮独立执行：completion、delivery_bridge、delivery_recovery、delivery_fencing、delivery_repair、delivery_snapshot、native_images 七个文件。JUnit：`output/studio-delivery-reliability-20261024/reviewer-r3-core-tests.xml`。

```text
.venv/Scripts/python.exe -m pytest tests/test_studio_completion.py tests/test_studio_delivery_bridge.py tests/test_studio_delivery_recovery.py tests/test_studio_delivery_fencing.py tests/test_studio_delivery_repair.py tests/test_studio_delivery_snapshot.py tests/test_studio_native_images.py -q --junitxml=../../output/studio-delivery-reliability-20261024/reviewer-r3-core-tests.xml
174 passed, 4 skipped, 2 warnings in 56.03s
```

4 项 skip 为 Windows 符号链接权限限制；2 项为 Starlette 对 httpx/anyio 接口的弃用警告。新增独立反例的失败输出见 HIGH-1，不包含在上述既有回归统计内。

前端命令：`node node_modules/tsx/dist/cli.mjs --test tests/studio-delivery-status.test.ts`。原始输出：

```text
✔ 保存进度DTO兼容旧响应并接收真实数量，拒绝未知状态和非法数字 (0.9989ms)
✔ 真实消息组件收图期间立即展示已存图片并更新进度，完成后移除提示 (12.6026ms)
✔ 旧轮次没有收图状态时不增加提示或额外操作 (1.2495ms)
ℹ tests 3
ℹ suites 0
ℹ pass 3
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1001.1921
```

**编译未执行**：Stage 1 发现 HIGH 后停止，不以主 Agent 已提供的前端 build 通过声明代替本次独立编译证据。本轮没有网页视觉或 Stage 2 质量/安全扫描 PASS 声明。

## Stage 2

**未执行。** 按 `.agents/skills/code-review/SKILL.md`，Stage 1 存在 HIGH 时不得继续。代码质量、测试真实性全审、安全扫描、邻居页面实际渲染对比不作 PASS；本报告中的反例前提检查属于 Stage 1 证明需求不符合。

## 快照与交接

发现 HIGH 并完成反例后，逐一对比 candidate 中 87 个相关 backend/frontend 文件的归一化 SHA256，无差异。证据：`output/studio-delivery-reliability-20261024/reviewer-r3-snapshot.json`。

```json
{"candidateId":"9cb2e67477d2caa74471b72a53e8e1b3b9ae57a89fd280cd56c8ee896a53ef2d","checked":87,"differences":[]}
```

本结论仅覆盖此快照；后续修复不得沿用本报告批准。主 Agent 应走 Stage 1 修复路径、重新 `review-prepare`，独立复核通过后再进入 Stage 2。不写 `.needs-review` 的 clean，不登记 review-approve。
