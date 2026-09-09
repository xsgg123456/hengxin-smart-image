# Phase 8 后端独立审查

审查日期：2026-09-09。范围为 PHASE8-PLAN Task 1/2 及任务 API 接入；依据 Product-Spec REQ-003/004、9.2、DEV-PLAN Phase 8、API-CONTRACT。使用 `.agents/skills/code-review/SKILL.md`。仅审查，不修改业务代码。

## Stage 1：Spec Compliance

**最终复核结论：Stage 1、Stage 2 均通过；0 个未关闭 HIGH/MEDIUM。** 原 2 项契约 MEDIUM 和 1 项测试盲区已修复。以下缺陷保留初次读取位置用于追踪。主 Agent 修复后，本审查者重新读取查询实现和新增测试，并独立执行针对性回归通过。真实 CLI、执行环境隔离、会话恢复属于 Phase 9；用户返工 HTTP 属于 Phase 10，不计作本期缺陷。前端视觉与登录恢复不在本报告范围。

路径除特别说明外，相对 `hengxin-smart-image/backend/`。

### 部分实现

以下两项已关闭：`app/modules/tasks/queries.py:87`–100 先计算工作区统计，再按 mode/search/state 过滤列表；搜索 OR 覆盖名称、SKU、规范化编号。`tests/test_task_queries.py:6`–27 覆盖名称/SKU/完整编号/前8位、状态类型筛选、空搜索结果保持统计、逻辑删除排除。独立运行：`1 passed, 2 warnings in 1.53s`。

1. **MEDIUM：搜索遗漏任务编号与 SKU。** `../docs/API-CONTRACT.md:95` 原文要求“支持名称、编号、SKU 搜索及类型筛选”。`app/modules/tasks/queries.py:89`–90 只对 `TaskRecord.name.icontains(...)` 加条件；SKU 与 id 未参与。对名称不含 SKU 的任务使用其 SKU 或编号搜索，会返回空列表。补齐三个字段的 OR 条件，并增加名称/SKU/编号分别命中的 API 回归。
2. **MEDIUM：统计随搜索和类型筛选缩小。** 同一契约行要求“统计为全工作区”。`app/modules/tasks/queries.py:87`–96 先将 mode/search 应用于 statement，再从该 statement 计算 stats。搜索不存在名称时，工作区有任务也返回 `stats.total=0`；类型筛选同样改变总量。列表 total 应随筛选，stats 应从只排除逻辑删除的独立基础查询计算。

既有 `tests/test_tasks.py:139`–154 仅检查跨用户读取、分页、不存在搜索的 items，没有检查 SKU/编号命中或过滤后的 stats，因此测试通过不能证明这两项契约成立。

### 逐项证据

| 验收项 | 判定与证据 |
|---|---|
| 三模式输入、文字无模板、名称/SKU/意见边界 | 完整实现。`app/modules/tasks/snapshots.py:9`–43；`tests/test_tasks.py:48`–73、83–88。 |
| 每组 1–20 个 ready 文件及服务端可信引用 | 完整实现。`snapshots.py:14`–27、44–49；`tests/test_tasks.py:128`–135 验证模板文件未就绪拒绝。图片字节格式/大小沿用 Phase 6 上传校验，本期消费 ready 记录。 |
| 模板版本/类型/启用状态与 Skill 绑定 | 完整实现。`snapshots.py:38`–58，模板加锁，版本不符 409，类型或不可用 422，Skill 再加锁刷新后检查；`app/modules/skills/service.py:28`–32 使用 populate_existing 避免锁等待后的旧状态。 |
| 输入/模板/Skill 冻结，更新禁用不改受理回执 | 完整实现。`app/modules/tasks/service.py:45`–58 保存模板 JSON、Skill checksum/version、素材顺序、意见；`tests/test_tasks.py:49`–73 对三模式及受理后 Skill 禁用重放验证。 |
| 授权先于幂等判定 | 完整实现。`app/modules/tasks/router.py:13`、18–20；`service.py:38`–43；`app/modules/auth/permissions.py:14`–20。客户端 owner/role 不作为可信身份。 |
| 同范围同键重放202、异内容409 | 完整实现。`app/modules/tasks/idempotency.py:15`–29；`service.py:40`–45 在业务校验前重放；`tests/test_tasks.py:49`–60；`tests/test_tasks_concurrency.py:74`–93。 |
| PG advisory 锁先于可变资源验证 | 完整实现。`idempotency.py:18`–21 为事务级参数化 advisory lock，随后读取请求；`service.py:41` 先于 `frozen_input`。 |
| Task/Round/Job/outbox/request 同事务落库 | 完整实现。`service.py:21`–35、46–60，只有最终 commit；无 Redis 调用或执行等待。`tests/test_tasks_concurrency.py:74`–88 检查重复请求只留一组实体。 |
| 同任务未结束轮次互斥 | 完整实现。`app/modules/tasks/models.py:29`–32 活跃状态部分唯一索引，包含 uncertain；`service.py:77`–96 在任务行锁下检查再受理；`tests/test_tasks_concurrency.py:98`–125、144–157。内部服务不等于用户返工已实现。 |
| 全局并发与短事务原子认领 | 完整实现。`app/modules/tasks/claims.py:10`–24 锁序 gate→Task→Round→Job；52–73 计数和认领同事务。`app/core/config.py:15` 默认1、范围1–10。`tests/test_tasks_concurrency.py:128`–141 验证不同任务争抢限额。 |
| 重复消息单次启动 | 完整实现。`claims.py:57`–60 排除非 queued，69–72 原子更新 token/count；`app/worker/tasks.py:49`–51 接 generation runner；`tests/test_tasks_concurrency.py:89`–96 在限额2下验证同作业只认领一次。 |
| 租约缺失/过期转待核实、不自动接管、保持占用 | 完整实现。`claims.py:35`–49、57–66、76–79；`app/worker/outbox.py:25`–31 不重派 generation 非 queued。`tests/test_tasks.py:112`–125、156–164 验证失效结果拒绝及容量仍占用。 |
| 逻辑删除、实际操作者审计、历史文件保留 | 完整实现。`app/modules/tasks/cancellations.py:10`–28；`app/modules/files/deletions.py:9`–19 只写逻辑删除与审计；`tests/test_tasks.py:138`–153 参数化四角色跨 owner。 |
| 排队/运行/上传后取消与迟到结果屏障 | 完整实现。`cancellations.py:16`–25 持久化取消；`claims.py:82`–96 确认 fixture 停止；`app/modules/tasks/results.py:11`–31 在同一事务复核 task/current round/token/lease 后发布。`tests/test_tasks.py:91`–109、156–164。 |
| 结果文件与版本发布原子性 | 完整实现。`results.py:15`–31 校验所有目标数量、ready 文件后在单事务创建版本/切 current/完成轮次；异常回滚该事务。`app/execution/fixture_runner.py:65`–78 实际读原图字节、重新验证上传为独立 FileRecord；不是引用输入充当新版本。 |
| fixture 默认关闭、test 专用、不伪造 CLI | 完整实现。`app/core/config.py:14`、36–39；`service.py:14`–17；`fixture_runner.py:18`–21；`app/modules/tasks/queries.py:44`、49 明确 sessionId=null/source=fixture。`tests/test_foundation.py:89`–108 与 `test_tasks.py:49`–80。 |
| 生产无执行器新请求503，历史重放202 | 完整实现。`service.py:41`–45 重放先于 available；`tests/test_tasks.py:76`–81。 |
| 状态独立查询、列表排序分页 | 完整实现（搜索和全局统计除外）。`queries.py:8`–9、30–81、97–105；运行进度未知为 null，完成为100，按创建时间/id排序。 |
| 服务端操作资格、待核实阻断 | 完整实现。`queries.py:72`–81；Phase8 两能力均 false，忙碌/待核实/未开放原因明确。 |
| Redis 中断恢复与终态停止重派 | 完整实现。`app/worker/outbox.py:23`–38 保留 durable outbox、只派可执行状态；`claims.py:27`–32 终态完成 outbox。容器日志证据见下。 |
| 迁移与既有 Skill 集成 | 完整实现。`migrations/versions/0005_tasks.py:16`–23 建表并幂等初始化 gate；`migrations/env.py:7` 注册模型；`app/modules/skills/service.py:100`–103 将任务引用计入 referenced。 |

### Spec 漂移

未发现本期新增的越界业务 HTTP：`app/main.py:36` 注册四项 tasks API，`app/contracts/router.py:25` 的 rounds 仍为未实现契约；`service.py:70` 明示内部并发验收接口。fixture 标记及受控执行器来自 `../docs/PHASE8-PLAN.md:12` 的显式范围，不是额外产品功能。

## 编译与测试原始输出

独立运行虚拟环境 Python。初次在沙箱启动失败，改用获批的绝对路径运行后成功，非代码编译错误。

```text
Unable to create process using '"C:\Users\82358\AppData\Local\Programs\Python\Python312\python.exe" -m pytest -q'
```

命令：`.venv/Scripts/python.exe -m pytest -q`，本轮独立执行原始摘要：

```text
.......................................................ssss.........s... [ 51%]
.................................ssss..................s.............    [100%]
131 passed, 10 skipped, 2 warnings in 8.78s
```

两条 warning 为 Starlette TestClient 的 httpx 与 anyio alias 弃用提示。10 项 PG 集成跳过，本地这次运行不能证明 PG 并发通过。

命令：`.venv/Scripts/python.exe -m compileall -q app migrations`。

```text
exit_code: 0
output: ""
```

读取主 Agent 集成运行产物 `../../output/phase8-integration.log`，不是本审查者重新运行容器：

```text
141 passed, 2 warnings in 9.23s
PASS concurrent same-key 202, different-content 409, limit=1, repeated messages single start/results
PASS Redis outage accepted task recovered
PASS three entry API snapshots, real MinIO bytes, fixture provenance and no fake CLI session
PASS independent duplicate claim check with global limit 2
PASS two distinct tasks running concurrently across two workers
PASS durable queued/running deletion, no late versions, restart no resurrection
PASS cross-owner read/delete with second trusted identity and actual operator audit
```

## Stage 2：Code Quality

在 Stage 1 两项修复后执行。

- 代码组织符合模块职责：`app/modules/tasks/claims.py:10` 集中锁序、`results.py:9` 集中发布屏障、`cancellations.py:10` 集中删除。任务模块文件为1–111行，未超过300行。HTTP边界有 Pydantic DTO 与 UUID 参数（`router.py:17`–35、`app/contracts/business.py:224`）；内部服务仍有未标注参数类型，但未发现由此造成的实际行为错误。
- 安全扫描未检出本期业务模块的 eval/exec、硬编码密钥、shell=True 或拼接 SQL 执行。`idempotency.py:21` 使用绑定参数；`queries.py:96`–100 文本搜索使用 autoescape；fixture 通过数据库 fileId 获取存储记录（`fixture_runner.py:55`–67），不使用前端 URL 获取远程资源。绝对 Skill 路径为服务端配置（`app/core/config.py:17`），不是泄露给客户端的凭据。
- 测试前提边界明确：`tests/test_tasks_concurrency.py:44`–46 手建1字节 ready FileRecord，该测试只验证独立 PG 连接的受理和锁，不证明图片可读；实际图片证据来自 `scripts/phase8/api_checks.py:102`–116 的独立 fileId、HTTP读取、PNG解码及字节相等断言。`tests/test_tasks.py:91`–109 的 uploaded 回调实际在上传后删除，足以验证该交错点；running 分支只直接认领，真实运行取消由集成脚本补充。
- **MEDIUM：关键冻结/结果回滚路径缺少回归。** `tests/test_tasks.py:49`–73 的 frozen 测试只在受理后禁用 Skill，未修改/删除模板再断言已受理快照不变；`app/modules/tasks/results.py:20`–30 逐文件 flush，新版本写入后第二个输出非法会抛异常，现有测试没有验证该失败路径是否回滚前一个 ImageVersion/currentVersionId 和轮次状态。代码静态检查符合事务预期，但这两条核心保证尚缺针对性故障证据。建议补模板编辑/删除后冻结快照验证，及“第一个输出有效、第二个无效”的整体回滚测试（包括不完成 outbox）。
- **上述 MEDIUM 已关闭。** `tests/test_task_snapshots_results.py:13`–35 通过真实模板 PUT/DELETE 后重放并执行，断言完整 snapshot、旧版本及两张输出；38–50 用合法第一输出和不存在第二输出实际触发 ValueError，确认先前 flush 的 ImageVersion 与所有 current 指针回滚、Job仍running。该调用在到达 `results.py:31` 的 end/outbox 更新前抛异常，证明失败未进入完成路径。用例输入可达且断言直接覆盖风险，没有将纯函数假结果替代 API/事务行为。
- 视觉对比：本次范围仅后端，无新增可单独比对的渲染页面，不适用；由主 Agent 的前端审查覆盖，不能将此报告当作 UI 通过证明。

浏览器、hard-kill 及最终带修复容器 rebuild 的完整证据仍由主 Agent 集成审查合并；本报告读取的日志只有此前容器测试与队列链路完成记录。

最终针对性独立复核命令：`.venv/Scripts/python.exe -m pytest -q tests/test_task_snapshots_results.py tests/test_task_queries.py`。

```text
...                                                                      [100%]
3 passed, 2 warnings in 2.55s
exit_code: 0
```
