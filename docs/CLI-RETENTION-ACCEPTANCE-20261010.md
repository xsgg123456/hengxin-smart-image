# CLI 自动清理独立验收审查（2026-10-10）

- 初始送审 candidateId：`7913a9fced847321bc509f1ca8cc20f1b9449373f787f6a90c4756925fc4e4ca`。
- 范围：本候选全部 Git diff 及未跟踪的 retention 模块、0024 迁移、5份 retention 测试、前端草稿模块/浏览器脚本、维护 service/文档；包含 `.agents/skills/dev-builder/SKILL.md:28` 已接受的通用模板约束，以及 `backend/tests/test_api_image_execution_pg.py:40` 完整隔离建表修正。
- 依据：根 `AGENTS.md`、code-review skill、`docs/HARNESS-REVIEW.md`、`Product-Spec.md:920-928`、`DEV-PLAN.md:1086-1090`、`hengxin-smart-image/docs/CLI-RETENTION.md:1-33`。前两轮 FAIL 报告仅用于定位复核，未继承其通过结论。
- 审查顺序：完整 Stage 1 代码/测试/UI 映射，未发现 HIGH 后进入 Stage 2；最终核读全量 Linux 结果后形成验收结论。审查仅本地隔离测试、只读和报告；未调用模型、提交或部署。
- 最终验收 candidateId：`15b3cd63dd3080e35d68e49028ebe118ab0279d2a2239915710f044f6d685376`。审查开始 currentId 与初始送审编号相同；重跑隔离 Vite 自动生成 `frontend/src/types/import/components.d.ts`，此前18行额外类型声明恢复至 HEAD。已及时报告主 Agent，由其重新 review-prepare；本 reviewer 核读当前完整声明文件（:3 自动生成标记、:9-130 声明）、确认 git diff 为空，并核读新快照的最终 vue-tsc 成功输出。此单文件不包含运行时实现；两阶段结论经过本次差异复核后只绑定最终候选。

以下非根目录路径统一以 `hengxin-smart-image/` 为前缀。表内 `retention/`、`modules/` 分别指 `backend/app/retention/`、`backend/app/modules/`；单独 backend 文件名沿用同格已列目录；前端单独组件/会话文件名指 `frontend/src/views/hengxin/api-image-edits/`，`components/TaskDetail.vue` 和 `revision-session.ts` 指 `frontend/src/views/hengxin/` 下相应文件。

## Stage 1 · Spec Compliance · PASS

| Spec 条目 | 结论 | 实现与验收证据 |
|---|---|---|
| 921 本地授权；生产部署/开启另行确认 | 完整实现 | `backend/app/core/config.py:16` 默认关闭；`retention/worker.py:53` 关闭直接返回；`infra/.env.example:33` 为 false；`infra/hengxin-retention.service.example:1` 仅示例；`docs/CLI-RETENTION.md:3,17` 写明授权与升级前提。 |
| 922 旧 CLI 与 API 修改 CLI 两域，API 初始生成/文字修改/正式业务不删 | 完整实现 | `retention/legacy.py:81,102` 仅 CLI 任务 UUID 目录；`retention/api.py:101` 仅 api-edits 会话 UUID；`retention/worker.py:21,27` 限定登记域。API 正式实体不在历史 delete 集合，`api.py:62-70`；`tests/test_retention_concurrency.py:66,140` 验证正式版本、输入、任务保留，浏览器文字修改仍发 API 请求。 |
| 923 提交/回复/返工/重试/采用/终态续期，读取不续期 | 完整实现 | `retention/state.py:33-45`；`modules/tasks/service.py:38`、`claims.py:28`；`modules/api_image_edits/conversation.py:141,170,196`、`conversation_runtime.py:44`。读取 `conversation.py:68`、`tasks/queries.py:63` 仅 describe；`tests/test_api_retention.py:48` 续期覆盖。 |
| 923 24h 仅私有 cache/plugins，会话认证图片保留且可重建续接 | 完整实现 | `retention/state.py:7,65`；`paths.py:14`；`tests/test_api_retention.py:48-62` 实际 runner resume、auth/session 保留；`tests/test_legacy_retention.py:36` 微秒边界；`tests/test_retention_paths.py:53` 私有缓存/共享认证与重复清理。 |
| 923 7d 清执行目录/聊天/提示词/事件/轮次明细及无引用候选标注 | 完整实现 | `retention/state.py:63`；`api.py:54-75`；`legacy.py:47-74` 清空大字段保留薄关联；`tests/test_api_retention.py:65,97`、`test_legacy_retention.py:36` 实际 API/runner 结果断言。 |
| 924 全部正式版本/归档/原图/共享素材/冻结素材/派生登记保留 | 完整实现 | `retention/objects.py:25-43` 结构化及跨域 JSON 引用检查，`:60-74` 跨域同键/Skill/派生保护；`tests/test_api_retention.py:65,179`、`tests/test_retention_concurrency.py:66,140` 验证采用版本与跨 item 引用。未删除 TaskSource、ImageVersion、ArchiveImage、ApiVersion 表。 |
| 924 对象/DB可重试，失效候选不能采用；薄统计不重复 | 完整实现 | `retention/objects.py:75-110` 事务回执、存储失败重试及最终引用复查；`:68` 缩略图 lease 保留屏障；`api.py:59-61,75`、`legacy.py:51,70` 统计随事务提交一次。`test_api_retention.py:97,127,163`；`test_legacy_retention.py:68`；`test_retention_concurrency.py:66,140`。 |
| 925 专用状态表、持久 pending，同父锁隔离提交/采用/领取/清理 | 完整实现 | `retention/models.py:9`、`state.py:21`；`api.py:18,91`、`legacy.py:15,92` 在删文件前提交屏障；业务 `tasks/service.py:91,109`、`claims.py:20,68`、`conversation.py:83,105,180`、`conversation_runtime.py:25,54`。真实 PG `test_retention_concurrency.py:87,103,122,140` 及 `test_retention_migration_legacy_pg.py:95`。 |
| 925 活动/未知/未结束凭据及未退出进程均保护 | 完整实现 | `retention/api.py:13-15,32-50` 三层终态白名单、finished_at、lease、节点/进程身份；`legacy.py:21-44` 同样保守。`tests/test_retention_concurrency.py:188,221,240` 验证活动、残留凭据、三层未知；`tests/test_legacy_retention.py:101,124,133` 实际 runner 与未知进程故障。 |
| 926 常驻7天规则；过期提示、清候选/草稿；加载/失败/pending | 完整实现 | `frontend/src/views/hengxin/api-image-edits/ImageConversationEditor.vue:3-12,37-43,63`、`conversation-drafts.ts:3`、`use-image-conversation.ts:24,60`；旧域 `components/TaskDetail.vue:8,104`、`revision-session.ts:34`。本 reviewer 独立重跑两份 browser 脚本全部通过，证据见下节。 |
| 926 显式 restartExpired；只用正式输入和新意见，不恢复旧记忆/候选 | 完整实现 | `modules/api_image_edits/conversation.py:102-105` 拒绝过期 baseTurnId；`tasks/service.py:102,109,129` 显式重启并删除旧 session 身份；原未过期缺失会话仍由 `modules/revisions/service.py:31-38` 拒绝。`test_api_retention.py:83-94`、`test_legacy_retention.py:72-98` 真实 runner 不 resume；浏览器确认字段与取消确认覆盖。 |
| 926 retention 响应、未建会话 null；单调事件、旧幂等兼容 | 完整实现 | `retention/state.py:49-55`、`conversation.py:68,86-89`、`api.py:74`、`tasks/idempotency.py:12`；前端 `conversation-feed.ts:4`、`use-image-conversation.ts:27,63` 防旧读取复活；`frontend/tests/api-image-conversation.test.ts:76,90,105`、`backend/tests/test_legacy_retention.py:142`。 |
| 927 索引分批、每小时、首次登记7天缓冲、重启不重置、维护入口 | 完整实现 | `retention/models.py:15,17,32`；`worker.py:19-48,51-79,82-96`；`migrations/versions/0024_cli_retention.py:11-18`；`tests/test_retention_concurrency.py:202`、`test_retention_migration_legacy_pg.py:27`、`test_api_retention.py:140,154`。 |
| 928 全套后端/前端、PG、路径、迁移、浏览器/类型/构建/独立审查 | 完整实现 | 最终 Linux 1617 passed / 17 既有环境条件 skipped；独立 PG 24 passed；前端 221 passed；vue-tsc + vite build 成功。Windows 缺链接权限的4 skip 已由最终 Linux 覆盖。完整原始输出及边界见下节。 |

前两轮问题闭环：`legacy.py:25-26` 已补结束时间与租约；`modules/tasks/round_materials.py:21-28,38,83` 保留过期通知且不误称未采集/未标注；`test_retention_paths.py:14-69` 真实路径/链接/幂等覆盖；`api.py:13-15,33-40` 未知三层状态保护；`test_api_image_execution_pg.py:40` 全模型建表仅改隔离 fixture，未改业务处理。

部分实现、未实现：本轮范围未发现。范围漂移：未发现额外业务功能；状态表、回执、维护入口/响应字段均映射本期 Spec；通用模板约束按明确送审范围纳入。`frontend/src/types/import/components.d.ts` 属自动生成类型声明，快照处理见最终结论。

## Stage 2 · Code Quality · PASS

- 结构与类型：新增模块按域、状态、路径、对象回执、调度拆分，最长变更源码271行、并发测试257行，均不超过300行（`output/retention-acceptance-static.log:1` 全清单）。`frontend/src/api/api-image-conversation.ts:5,16` 使用 unknown 校验；无新增 TypeScript any，扫描命中为 Python `any()` 或 `AbortSignal.any`。
- 安全：全变更代码扫描 eval、dangerouslySetInnerHTML、innerHTML、公开密钥变量/常见密钥前缀、用户绝对路径；没有危险代码命中。`retention/paths.py:7-28` UUID/根解析/链接拒绝；真实 Linux 全量执行 `tests/test_retention_paths.py:14,25,53`。SQL格式化命中仅随机内部 schema 的测试建删语句（`test_api_image_execution_pg.py:34-40,58`、`test_retention_migration_legacy_pg.py:35-47`），不接受业务输入。未发现安全问题。
- 错误路径：`retention/api.py:108-114`、`legacy.py:110-116` 出错保留 pending；`objects.py:102-108` 存储失败保留回执。测试确实进入实际文件/存储故障与事务回滚，不只断言辅助函数。PG使用独立连接与随机schema，测试收尾删除各自schema（`test_api_cli_concurrency.py:25-61`、`test_api_image_execution_pg.py:31-59`）。
- 测试真实性：API与旧域基础用例先调用真实应用/runner再清理（`test_api_retention.py:23`、`test_legacy_retention.py:20`），仅模型子进程为隔离模拟；并发 fixture 明确补finished_at/no lease（`test_retention_concurrency.py:41-46`），未知状态作为故障前提明确植入，未冒充正常产生状态。独立PG重跑24项通过。
- UI与引导：实际重跑正常会话、过期会话和旧任务修改三个页面状态，对照渲染截图 `output/playwright/api-image-conversation/conversation.png` / `expired.png` 与 `output/playwright/legacy-retention/expired-restart.png`。蓝色操作按钮、既有对话框/标注编辑器、间距及字体沿用邻居正常态；过期仅替换状态提示/确认标签，输入区、正式图、底部操作完整可见。旧CLI确认弹窗明确新会话，取消不提交；新意见失败后保留。对应 `ImageConversationEditor.vue:4,7,117`、`RealRevisionDialog.vue:16`、`TaskDetail.vue:132`。本轮没有单独设计稿，按既有组件先例检查，不虚构设计数值。
- 质量、安全、视觉未发现 HIGH / MEDIUM / LOW 新问题。不扩大到既有非本轮功能重构。

## 测试、编译与功能原始证据

主 Agent 最终 Linux 全量 `output/retention-linux-tests.log` 原始结束输出：

```text
1617 passed, 17 skipped, 15 warnings in 248.96s (0:04:08)
```

核读该日志 skip 原因：test_local_skills_linux 9项、test_skill_catalog_linux 7项要求 Linux root/Bubblewrap；test_phase11a_environment 1项要求既有非root WSL。均非本次清理用例，不把跳过称通过。日志有原有 Starlette 弃用及SQLAlchemy警告。

reviewer 本地独立命令：在 backend 设置两个测试数据库变量指向授权的127.0.0.1:64651隔离库，执行 `.venv/Scripts/python -m pytest -q tests/test_retention_concurrency.py tests/test_retention_migration_legacy_pg.py tests/test_api_image_execution_pg.py`。所有 fixture 为随机schema。`output/retention-acceptance-pg.log`：

```text
........................                                                 [100%]
24 passed, 2 warnings in 17.58s
```

已有专项日志核读：`output/retention-fix-tests.log` 为47 passed / 4 Windows链接权限skip；`output/retention-unknown-tests.log` 为27 passed；`output/retention-api-pg-tests.log` 为12 passed。它们只作专项证据，最终后端结论依据上述最终全量。

`output/retention-frontend-tests.log`：

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

`output/retention-frontend-build.log`：

```text
> hengxin-smart-image-frontend@0.2.19 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4506 modules transformed.
✓ built in 50.16s
```

该日志存在pnpm字段忽略、打包提示，不称为无警告。独立浏览器两脚本实际重跑均exit0：`output/retention-acceptance-browser-api.log:1` 7组checks及errors=[]；`output/retention-acceptance-browser-legacy.log:1` passed=true，`output/playwright/legacy-retention/checks.json:16` errors=[]。先前启动失败为本机Playwright1247浏览器缺失、3024未监听；换用已安装1234引擎并启动隔离Vite后成功，无需改应用。独立Vite会话17859已停止，未操作其他进程。

## 最终结论

已逐行核对 `output/retention-generated-types.diff:1-57`：唯一差异为移除18项 Element Plus 自动全局类型声明（ElBadge、ElCalendar、ElCheckbox、ElCol、ElDatePicker、ElDescriptions、ElDescriptionsItem、ElRadio、ElRate、ElRow、ElSegmented、ElSpace、ElTabPane、ElTabs、ElText、ElTimeline、ElTimelineItem、ElTree）。均为 `typeof import('element-plus/es')` 声明，无运行时代码。主Agent重生成内容的SHA256与7913原声明相同，再恢复最终HEAD声明；当前文件、成功类型检查和浏览器结果支持该差异两阶段通过。再次核读 `output/retention-final-build.log:3-10` 及末行，原始输出：

```text
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4506 modules transformed.
✓ built in 30.57s
```

最终候选 `15b3cd63dd3080e35d68e49028ebe118ab0279d2a2239915710f044f6d685376`：**Stage 1 PASS；Stage 2 PASS**。没有本轮待修复问题。该结论来自初始7913快照的完整独立审查及生成声明单文件差异复核，未沿用旧FAIL报告批准新版本。

最终 `output/retention-final-typecheck.log:3-4` 原始输出（主Agent执行exit0，本reviewer核读）：

```text
> hengxin-smart-image-frontend@0.2.19 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

收尾 `harness.py review-status` 的 currentId 与最终候选一致；approved=false 是尚未由主Agent登记凭据，不是审查失败。请主Agent用本报告与同一candidateId执行review-approve，再核对review-status。此结论限本地实现验收，不授权生产启用、提交或部署。
