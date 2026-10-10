# CLI 自动保留清理首轮审查（2026-10-10）

- candidateId：`662fd37202dd14dbd6c1a649115b741c0c91b26becc1c400dfc702af494c0295`
- 审查范围：本轮全部 Git 工作区差异及新增 retention 模块、0024 迁移、三份后端测试、前端草稿模块/浏览器测试、维护 service/文档；包含 `.agents/skills/dev-builder/SKILL.md:28` 的可复用模板约束改动。
- 依据：`Product-Spec.md:920-928`、`DEV-PLAN.md` 2026-10-10 节、`hengxin-smart-image/docs/CLI-RETENTION.md`、code-review skill 和 HARNESS-REVIEW 协议。
- Stage 1：**FAIL**。发现 1 项 HIGH、2 项 MEDIUM；不满足交付验收。
- Stage 2：**未执行**。遵循 Stage 1 存在 HIGH 时停止的规则；不能登记两阶段 PASS。
- 审查期间执行 `harness.py review-status`，currentId 与上述 candidateId 相同。未修改应用、未提交、未部署、未调用模型。后续修复必须重新固定快照并复审。

## Stage 1 问题

### H1 · HIGH：旧 CLI 清理忽略未结束凭据，可能不可逆删除应保护的现场

Spec 原文：`Product-Spec.md:925` 要求“无未结束执行凭据”“未知状态保留现场”。

实际：`hengxin-smart-image/backend/app/retention/legacy.py:21-42` 只核查 round/job 的终态字符串、已存在 attempt 的结束及进程身份；未核查 `RoundRecord.finished_at`，也未核查 `Job.lease_until`。因此轮次没有结束时间、或者 job 尚持有租约时，只要状态字符串为 succeeded，就会进入 `legacy.py:90-110` 的目录删除。

独立实测：在用户明确授权的隔离 PostgreSQL `127.0.0.1:64651/retention_test` 上，调用既有 `pg_tasks` fixture 创建唯一测试 schema，通过真实 create_task 建立任务。分别构造终态但 `finished_at=None`，以及结束时间已写入但 `lease_until=now+1h` 的资源；有效活动设为 8 天前，在 TemporaryDirectory 内建立历史文件，调用真实 `legacy.process`。fixture 最终删除独立 schema，临时目录自动回收。原始输出：

```text
missing_finished_at: result=expired, history_exists=False
remaining_lease: result=expired, history_exists=False
```

这两种输入应返回保护状态并保留文件。API 对应防线已存在于 `backend/app/retention/api.py:36`，旧 CLI 没有保持同等保守原则。

现有测试还掩盖此缺口：`backend/tests/test_retention_concurrency.py:281-309` 将新排队轮次仅改成 succeeded，没有建立 finished_at，却断言清理成功；`:313-339` 的 pending fixture 同样缺少终态时间。应修正为真实完整结束前提，并独立覆盖残留租约、缺失结束时间及未决进程凭据。

### M1 · MEDIUM：过期轮次材料接口丢失清理说明，显示原因不实

Spec 原文：`Product-Spec.md:926` 要求“显示历史已清理”。

实际：`backend/app/modules/tasks/round_materials.py:21-25` 先将“本轮会话历史已按 7 天保留规则清理”加入 notices，紧接着遍历 `('systemPrompts', 'toolCalls', 'notices')`，以空 evidence 的 notices 覆盖它。由于清理后配置只有 `{'historyExpired': True}`（`backend/app/retention/legacy.py:53`），覆盖必然发生。

随后 `round_materials.py:37-40` 提示“未采集/无法回溯”，`:81-84` 还可能提示“未提交标注图”，会将被清理的数据解释成从未采集/提交。页面顶部总体规则不能替代该轮执行材料的准确说明。应保留明确的过期原因，并覆盖该材料 API 的实际返回断言。

### M2 · MEDIUM：新路径删除实现缺少 Spec 要求的越界和链接验收

`Product-Spec.md:928` 明确要求“路径越界与链接保护”。`backend/app/retention/paths.py:7-29` 实现 UUID 子目录、resolve 比较、子树链接拒绝，但本次三份 retention 测试没有直接验证这些保护。

`backend/tests/test_cleanup.py:242` 的符号链接用例针对既有 cleanup 实现，不能证明新 `retention.paths.clean` 的真实行为。应新增使用真实临时目录/链接的测试：执行根链接、目标链接、cache/plugins 父目录链接、子树链接、非法 UUID、两域与相邻目录不受影响；POSIX 用例需在 Linux 实际运行。此项为缺少验收证据，未据此声称已有越界删除漏洞。

## Spec 逐项核查

下表路径以 `hengxin-smart-image/` 为相对前缀，根目录需求除外。完整实现指本项代码和列举验证匹配，不代表整轮通过。

| Spec 条目 | 结论 | 证据 |
|---|---|---|
| 920-922 本地授权、两域范围、禁止共享凭据/安装/整桶清理 | 完整实现 | `backend/app/retention/api.py:98` 使用 api-edits 域；`legacy.py:103` 使用旧任务域；`paths.py:7` 限定 UUID 子目录；`worker.py:53` 默认关闭直接返回；`infra/hengxin-retention.service.example:1` 仅模板，未安装。 |
| 923 有效活动更新、查看不续期 | 完整实现 | `backend/app/retention/state.py:33` touch；`modules/tasks/service.py:38`、`tasks/claims.py:29`、`api_image_edits/conversation.py:141,170,196`、`conversation_runtime.py:44` 在提交/终态/采用等写入；GET `conversation.py:60` 和 `tasks/queries.py:63` 只 describe。 |
| 923 24h 私有 cache/plugins、保留会话认证 | 完整实现 | `retention/state.py:7,58`，`paths.py:14`；`tests/test_api_retention.py:48` 验证边界、auth/session 文件仍在且后续 resume；`tests/test_legacy_retention.py:36` 覆盖旧域边界。 |
| 923-924 7d 过程清理、正式版本/输入/引用保护、薄统计 | 部分实现 | `retention/api.py:51` 删除事件/轮次/jobs，保留正式业务；`legacy.py:46` 清空过程字段；`objects.py:25,46,84` 引用检查、派生登记与回执；`tests/test_api_retention.py:65,98,180` 覆盖采用保留、未采用删除重试和跨 item 快照。全量及全部边界未完成验收，H1 阻断安全前提。 |
| 925 持久 pending、同父行锁、失败重试 | 部分实现 | `retention/models.py:9`、`api.py:16,75`、`legacy.py:15,76`，提交与领取 guard；PG 并发用例 `tests/test_retention_concurrency.py:78,98,115,146`。H1 表明旧域未完整确认无未结束凭据。 |
| 926 过期常驻说明、禁用/草稿清理、正式图新会话 | 部分实现 | `frontend/src/views/hengxin/api-image-edits/ImageConversationEditor.vue:3-10,63`、`conversation-drafts.ts:1`、`RealRevisionDialog.vue:16`；旧域 `components/TaskDetail.vue:8,104,131`、`revision-session.ts:34`；两份隔离浏览器 checks 及截图支持交互。轮次材料原因存在 M1。 |
| 926 restartExpired、拒绝旧候选、幂等兼容、事件不倒退 | 完整实现 | `backend/app/modules/api_image_edits/conversation.py:86,102`；`tasks/service.py:99`；`tasks/idempotency.py:12`；`retention/api.py:71`；前端 `conversation-feed.ts:4`、`use-image-conversation.ts:24,60`，15 秒只读 refresh 在 `:79`。`test_api_retention.py:65` 验证过期旧候选拒绝及新命令不 resume。 |
| 927 有索引分批、每小时、默认关闭、首次启用宽限 | 完整实现 | `backend/app/retention/models.py:15,17,32`；`worker.py:19,51,82`；`migrations/versions/0024_cli_retention.py:11` 只建表；`tests/test_api_retention.py:140,154` 与 `tests/test_retention_concurrency.py:204,244` 覆盖首次启用及迁移保留。 |
| 928 全套测试/类型/构建/功能/独立审查 | 未完成 | 前端证据通过；Linux 后端全量运行中，不宣称通过；新路径保护 M2 缺证据；Stage 1 FAIL。 |

## UI 证据与范围漂移

已实际查看 `output/playwright/api-image-conversation/expired.png`：过期提示、7 天常驻说明、0 轮历史、正式 V2 底图、输入清空和“开启新会话”按钮可见。查看 `output/playwright/legacy-retention/expired-restart.png`：正式 V3 图片保留、过期提醒、失败后新意见保留。对应组件证据见上表。截图是隔离 fixture，不代表真实付费模型或生产验证。Stage 2 邻居页面实时视觉对比尚未执行。

未发现本轮新增业务页面或收费调用。`.agents/skills/dev-builder/SKILL.md:28` 实际变更是“多输入复用模板不得固化示例专属对象/数值”，不是隔离测试规则；按主 Agent 明确要求纳入且未回退。新增表、维护入口、配置项均对应本轮 Spec。

## 现有测试与编译证据

核读 `output/retention-frontend-tests.log` 原始末尾：

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

核读 `output/retention-frontend-build.log` 原始输出：

```text
> hengxin-smart-image-frontend@0.2.19 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4506 modules transformed.
✓ built in 50.16s
```

同一日志还存在 pnpm 配置字段被忽略的 WARN；不将构建成功描述为无警告。`output/playwright/legacy-retention/checks.json:2` 为 passed=true、`:16` errors=[]；API 浏览器 `output/playwright/api-image-conversation/result.json:72` errors=[]。

本 reviewer 的新增真实 PG 故障前提复现见 H1，成功证明缺陷。主 Agent 正运行 Linux 全套，首轮报告不等待、不引用未完成总数。

## Stage 2 状态

**未执行**：代码质量、安全扫描、邻居页面实时对比不出通过结论。

读取 Stage 1 并发验收材料时附带发现 `backend/tests/test_retention_concurrency.py:339` 共 339 行，超过 skill 的 300 行规范；留待修复拆分及新快照 Stage 2 检查，不能伪称已完成质量审查。

主 Agent 应先修复 H1/M1、补足 M2、修正并发测试前提，再 review-prepare 并重新派发从 Stage 1 开始复审。本报告不授权 review-approve。
