# CLI 自动清理修正快照独立复审（2026-10-10）

- candidateId：`bbcad08bdbb76e324a82671c515060ce3c2dee7c2a6701c1f2aa38423109170e`。
- 范围：该候选全部 Git 差异，新增 `backend/app/retention/`、0024 迁移、5 份 retention 测试、前端草稿模块与两份浏览器脚本、维护 service 示例；包含 `.agents/skills/dev-builder/SKILL.md:28` 已接受的通用模板约束。
- 依据：根目录 `Product-Spec.md:920-928`、DEV-PLAN 的 2026-10-10 节、`hengxin-smart-image/docs/CLI-RETENTION.md`、code-review skill、HARNESS-REVIEW 协议及首轮报告。
- **Stage 1：FAIL，新增 1 项 HIGH。Stage 2：未执行。** 文件名中的 FINAL 不代表通过，不授权 review-approve。
- 审查时 `harness.py review-status` 原始 `currentId` 与该候选相同，`approved: false`。未改应用、未提交、未部署、未调用收费模型；仅使用独立测试 PostgreSQL 随机 schema 和临时目录复现。修复需新候选及独立复审。
- 报告收尾时主 Agent 通知已修改 API 终态判断并固定新候选 `ca78c7cee2a9ddb8a87350adda7abefee3198ea3ae019d93f8574b1c800ac3e7`。本报告行号、缺陷复现及 FAIL 仅适用于上述 `bbcad08...` 快照，不覆盖新候选；新候选由新 reviewer 完整审查。

## Stage 1 · HIGH：API 域将未知状态当作可清理终态

Spec `Product-Spec.md:925` 明确要求“先复核无排队/运行/收图/取消中/待核实、无未结束执行凭据”“未知状态保留现场”。

实际 `hengxin-smart-image/backend/app/retention/api.py:30-36` 的 `busy()` 只排除 ACTIVE 列表：item、turn、job 的未知状态均未受到保护。即使记录状态无法确认，只要 turn 带 finished_at、job 没有租约，就会进入 `api.py:98` 删除执行目录，继而 `api.py:50-73` 删除轮次/事件/候选与任务记录。这与已修正为终态白名单的 `backend/app/retention/legacy.py:22-28` 不一致。

独立实测使用真实 PostgreSQL `127.0.0.1:64651/retention_test`，分别调用 `tests/test_api_cli_concurrency.py:25` 的 `pg_edit.__wrapped__` 创建随机 schema，通过 `tests/test_retention_concurrency.py:35` 的 `prepared_api()` 真实提交建立完整测试资源。每组只把 turn.status、job.status 或 item.state 之一设为 `unknown`；保留真实 finished_at、无 lease、超过 7 天的活动记录。为该 UUID 建立 TemporaryDirectory 下的 history.json，调用真实 `api.process()`；finally 删除 fixture schema，临时目录自动回收。三次结果均为：

```text
turn_unknown: result=expired, history_exists=False
job_unknown: result=expired, history_exists=False
item_unknown: result=expired, history_exists=False
```

模型允许这种数据：`backend/app/modules/api_image_edits/conversation_models.py:26` 为普通 String 状态，不存在数据库枚举约束。该复现针对明确的未知状态保护要求，不将未知值冒充正常业务产生的状态。

建议：明确列出 item、turn、job 已确认结束的合法状态，其余均保护；补三层未知状态及已知安全终态的真实 PG 用例。`tests/test_retention_concurrency.py:182-196` 目前只枚举 ACTIVE 字符串，`:218-237` 覆盖结束时间/租约/异节点身份，均没有证明未知状态保留。

## 首轮问题复核

| 首轮问题 | 本候选结论 | 证据 |
|---|---|---|
| H1 旧 CLI 缺结束时间/残留租约仍清理 | 已修正 | `backend/app/retention/legacy.py:26-28` 两项均拒绝；`backend/tests/test_legacy_retention.py:140` 使用实际 runner 完成资源后分别移除结束时间、留下已过期但未解除的租约，断言保留目录。 |
| M1 过期材料通知被覆盖、误报未采集/未提交 | 已修正 | `backend/app/modules/tasks/round_materials.py:21-28,38-41,83` 先读 evidence 后追加清理通知，过期分支禁止缺失误导；`backend/tests/test_legacy_retention.py:58-60` 真实 materials GET 返回断言。 |
| M2 缺路径越界/链接验收 | 已补测试，Linux 执行结果待最终核对 | `backend/tests/test_retention_paths.py:14-54` 非 UUID、root/task/cache/nested 链接；`:57-74` 缓存、会话、共享认证保留及幂等。Windows 日志 4 个链接用例因权限 skip，不能冒充 POSIX 已验证。 |

## Spec 逐项对照

下表非根目录文件均以 `hengxin-smart-image/` 为前缀。“匹配”限该条列举的实现及证据，不代表整体通过。

| 需求 | 结论 | 代码及验证证据 |
|---|---|---|
| 920-922 本地授权、两域分离；API 初始生成/文字修改及业务正式数据保留 | 匹配 | `retention/api.py:98` 的 api-edits UUID 域、`retention/legacy.py:106` 的旧域、`retention/paths.py:7-14` 私有子目录；`retention/worker.py:51-55` 默认关闭。正式业务删除仅受候选引用检查控制，`tests/test_retention_concurrency.py:72-85` 保留 ApiTask/ApiItem/正式版本/原文件。 |
| 923 有效活动续期，查看/轮询/SSE不续期 | 匹配 | `retention/state.py:33-45`；`modules/tasks/service.py:38` 入队、`tasks/claims.py:29` 终态、`api_image_edits/conversation.py:141,170,196` 提交/停止/采用、`conversation_runtime.py:44` 终态 touch；GET conversation.py:60、tasks/queries.py:63 只 describe。 |
| 923 24h 只清私有 cache/plugins，可重建及续接 | 匹配 | `retention/state.py:7,65`，`paths.py:14`；`tests/test_api_retention.py:48-62` 边界、session/auth 文件保留及真实 runner resume；`test_legacy_retention.py:36-46` 旧域边界。 |
| 923-924 7d 清大过程字段/无引用对象，保留正式全部版本/输入/统计 | 部分实现 | `retention/api.py:50-73`、`legacy.py:47-75`、`objects.py:25-81` 清理流程；`test_api_retention.py:65-119,180` 正式版本/输入保留、对象重试、跨 item JSON 引用；`test_retention_concurrency.py:143` 双版本采用竞争。删除执行前提存在本报告 HIGH。 |
| 924 跨域快照/共享/派生登记保护，缩略图 lease 与对象回执重试 | 匹配 | `retention/objects.py:25-43` 结构引用+两域 JSON，`:59-79` 共享 bucket/key、skill、派生与 lease；`:84-110` 独立回执；`test_api_retention.py:164,183` lease 和跨 item 引用。 |
| 925 同父锁、持久 pending、拒绝新活动、失败重试 | 匹配 | `retention/api.py:16,75-110`；`legacy.py:16,78-118`；`state.py:20` guard；`conversation.py:102-105` 和 `tasks/service.py:108` 提交保护；`conversation_runtime.py:54`、`tasks/claims.py:64` 领取保护；真实 PG `test_retention_concurrency.py:89,106,126,143` 及 `test_retention_migration_legacy_pg.py:102`。 |
| 925 已退出进程、无未结束凭据、未知保留 | 不匹配，HIGH | 旧域 `legacy.py:22-43` 已保守；API `api.py:30-36` 未确认三层合法终态。真实 PG 复现见上。进程异节点/读取错误保留代码见 api.py:38-46、legacy.py:32-42。 |
| 926 常驻7天说明、过期通知、清旧选择/草稿、loading/error/pending | 匹配 | `frontend/.../ImageConversationEditor.vue:4,37,43,63`；`conversation-drafts.ts:3-14`；`use-image-conversation.ts:24,60`；`components/TaskDetail.vue:8,104`、`revision-session.ts:34`。两份浏览器结果与实际查看截图支持页面状态，详见下文。 |
| 926 显式 restartExpired、新意见/正式基础，不恢复旧记忆，旧候选拒绝 | 匹配 | `api_image_edits/conversation.py:102-105`、`tasks/service.py:99-111,129-134`；`test_api_retention.py:84-95`、`test_legacy_retention.py:73-99` 真实 runner 非 resume；`ImageConversationEditor.vue:89` 和 `TaskDetail.vue:132` 显式提交。 |
| 926 retention 响应、单调事件、旧幂等兼容 | 匹配 | `retention/state.py:48-54`、`api.py:72`；`conversation.py:86-88`、`tasks/idempotency.py:12-13`；`frontend/.../conversation-feed.ts:4`、`tests/api-image-conversation.test.ts:76` 旧响应/倒序及新生命周期测试；`tests/test_legacy_retention.py:156` 原幂等摘要比对。 |
| 927 索引分批、每小时、默认关闭、首次启用7天缓冲、service示例 | 匹配 | `retention/models.py:15,17,32`、`worker.py:19-48,51-78,82-94`；`0024_cli_retention.py:11-17` 仅建表/保留回执；`test_retention_concurrency.py:199` 首次启用；`test_retention_migration_legacy_pg.py:28` 重复迁移保留旧业务及回执。 |
| 928 全套测试、类型/编译、PG、路径、UI、独立审查 | 未完成 | 现有通过证据如下；Windows 路径 skip 待 Linux 全量；本候选 Stage 1 FAIL，Stage 2 未执行。 |

## UI、引导真实性与范围

本次实际打开 `output/playwright/api-image-conversation/expired.png`：0 轮、历史已清理、7 天规则、正式 V2 底图、新意见为空、开启新会话按钮可见；打开 `output/playwright/legacy-retention/expired-restart.png`：正式 V3 保留、清理提示、新意见及失败保留说明可见。对应代码为 `ImageConversationEditor.vue:3-10,63-72`、`TaskDetail.vue:8,104,132`。截图为隔离 fixture，无生产或收费执行结论。

`output/playwright/legacy-retention/checks.json:2` 为 passed=true，`:16` errors=[]；API `result.json` errors=[]，覆盖旧候选、草稿、清理中禁用、失败读取、明确新会话及文字修改请求。未进行 Stage 2 邻居实时视觉对比，不把现有截图称为该步骤通过。

新增保留表、对象回执、维护入口、响应字段均对应 Spec 922-927；未发现新增业务页面或收费调用。`.agents/skills/dev-builder/SKILL.md:28` 的通用模板约束在主 Agent 明确交接范围内。类型生成文件新增既有 Element Plus 声明，本身未新增运行时业务。

## 现有测试与编译原始输出

核读 `output/retention-fix-tests.log`：

```text
47 passed, 4 skipped, 2 warnings in 21.67s
```

核读 `output/retention-frontend-tests.log`：

```text
ℹ tests 221
ℹ suites 0
ℹ pass 221
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 4252.8753
```

核读 `output/retention-frontend-build.log`：

```text
> hengxin-smart-image-frontend@0.2.19 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ built in 50.16s
```

构建日志含 pnpm 配置字段被忽略警告；后端含 Starlette 弃用警告，不称为无警告。Linux 全量测试运行中，本报告不引用未知最终总数；修复本次 HIGH 后还需验证最终候选。

## Stage 2

**未执行**。由于 Stage 1 HIGH，代码质量、完整安全扫描、邻居实时视觉对比不出 PASS。主 Agent 修复后应重新固定快照，交独立 reviewer 从 Stage 1 开始；本报告不能用于两阶段通过登记。
