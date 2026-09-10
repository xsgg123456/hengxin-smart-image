# Phase 11 独立审查报告

审查范围：Phase 11 下载、成品归档与生命周期；包含 archives 模型/服务/路由、0007 迁移、任务归档统计、服务端 ZIP 与前端接入、归档请求重放、默认禁用清理服务及专项测试/集成脚本。

初始 candidateId：`8bb3ef44385877019063d24b2166f70cf9b5ee7490c0c8d569cc2d39db01eba8`。

最终 candidateId：`9d487f4582f4a518ce7b6ba840097e8ff6bdb439e940d376084fcfce8b2820b3`。

最终结论：**Stage 1：PASS；Stage 2：PASS**。无未解决 HIGH/MEDIUM；保留一项已明确运行边界的 LOW 运维建议。两阶段结论仅适用于此最终快照，由主 Agent 用 review-approve 登记；reviewer 未登记批准、未写 clean、未改业务代码。

审查期间变更已逐项复核：新增 `backend/tests/test_archives.py:123` 四角色跨归档所有者删除测试；`infra/verify_phase8.py:49` 增加失败快照与 Vite 日志保留；`scripts/phase11/archives.js:2`、`:63`、`:79` 修正 runner 沙箱 URL/Buffer 和对话框 locale 前提，未删减业务断言。中间 candidateId 为 `c2444985dacc2e80c8f3184402d2b1c3ee928e118b4d791cc1da98170817aa03`，旧结论不直接批准新快照。`.agents/skills/dev-builder/SKILL.md` 和 `.codex/hooks.json` 是主 Agent 明确交接的既有用户改动，不属于 Phase 11 产品实现，未修改或回退。

浏览器测试快照为 `4c0e6b23ee2c195bf94972b7a0629159b5aeaafdc38d6b0ab517da1ba3916230`。Vite 曾按需扫描删减 `frontend/src/types/import/components.d.ts:75` 等处的 19 项生成声明；审查发现后主 Agent 精确恢复到 HEAD 完整声明。reviewer 直接核对最终 git diff 为空，业务/脚本无其他变化，最终 vue-tsc 退出 0。恢复生成声明后的最终候选已再次由 review-status 核对一致，未用旧候选覆盖新内容。

依据：Product-Spec.md REQ-006、REQ-007、第 9.1–9.2 节和第 13 节权限矩阵；DEV-PLAN.md:333 的 Phase 11；Design-Brief.md；code-review SKILL 与 docs/HARNESS-REVIEW.md。下文代码路径均相对于 `hengxin-smart-image/`。

## Stage 1：Spec Compliance

逐项静态及实际浏览器检查无 HIGH 问题，Stage 1：PASS。

| 需求条目 | 对照结论与代码证据 | 验证证据 |
|---|---|---|
| REQ-006 图片预览和授权单张下载 | 完整：`backend/app/modules/files/router.py:44` 校验业务身份及 ready 文件；`frontend/src/views/hengxin/download.ts:12` 接真实下载 | `backend/tests/test_archives.py:20` 下载归档图片；`backend/tests/test_downloads.py:36` 四角色/禁用身份 |
| REQ-006 整套服务端流式 ZIP | 完整：`backend/app/modules/files/downloads.py:24` 限制 1–20 个文件；`:63` 分块打包、长度及校验和验证；`:104` 授权路由；`frontend/src/views/hengxin/download-helpers.ts:65` 真实接口及完整性检查 | `backend/tests/test_downloads.py:17` JPEG/PNG/WebP 名称顺序及原字节；`:98` 8 MiB 输入逐块产出；`:116` 发送失败前/中资源释放 |
| REQ-006 独立成品库搜索/类型筛选/分页/预览 | 完整：`backend/app/modules/archives/service.py:91`；`backend/app/modules/archives/router.py:23`；`frontend/src/views/hengxin/components/Archive.vue:3`、`:26` | `backend/tests/test_archives.py:106` 名称、字面通配符、类型、分页与参数错误 |
| REQ-006 关联任务、选定版本、归档人和时间 | 完整：`backend/app/modules/archives/models.py:11`、`:24`；`backend/app/modules/archives/service.py:31`、`:70` | `backend/tests/test_archives.py:20` 版本变化后旧记录及图片保持；`:73` 归档者为实际操作者 |
| 相同归档动作幂等、异内容冲突 | 完整：`backend/app/modules/archives/service.py:45` 任务锁、`:50` 请求回执优先于新轮次校验；模型 `:13` 活跃快照唯一索引和 `:36` 请求唯一约束 | `backend/tests/test_archives_concurrency.py:31` 独立 PG 会话并发归档；`backend/tests/test_archives.py:34` 忙碌及返工后的原键重放 |
| 网络响应未知保留原版本及请求键 | 完整：`frontend/src/views/hengxin/archive-requests.ts:6` 按身份/任务保存请求；`frontend/src/views/hengxin/components/TaskDetail.vue:100` 接入并验证返回时身份 | `frontend/tests/archive-requests.test.ts:8` 网络故障、401、刷新到新版本仍重放原请求；`:24` 身份隔离及确定拒绝后的新请求 |
| 部分失败可查看单图，完整套图才整套归档 | 完整：`backend/app/modules/archives/service.py:57` 排除所有活跃轮次、失败/缺槽/槽错误；`frontend/src/views/hengxin/components/TaskDetail.vue:8` 与 `:20` 保留单图入口 | `backend/tests/test_archives.py:54` 七种禁止状态；`:61` succeeded 但缺图/槽错误仍拒绝 |
| 归档后返工不改变旧对象，归档不启动 CLI | 完整：归档仅创建不可变版本/文件引用，不调用队列或 CLI，`backend/app/modules/archives/service.py:70`；归档状态不替代任务状态，`backend/app/modules/tasks/queries.py:54`、`:102` | `backend/tests/test_archives.py:20` 新旧版本、下载字节与任务删除后存续；`backend/tests/test_archives_concurrency.py:31` Round/Outbox 数量不增加 |
| 四角色查看/归档全员任务及删除他人成品，记录实际操作者 | 完整：`backend/app/modules/archives/router.py:13` 统一 shared_resources；`backend/app/modules/auth/permissions.py:5`；`backend/app/modules/files/deletions.py:10` | 原 `backend/tests/test_archives.py:73` 仅覆盖自己归档删除，审查发现后新增 `:123` 明确断言 actor != archive.ownerId，覆盖四角色及审计，增量已静态复核 |
| 逻辑删除不损坏仍引用的任务、模板、归档文件 | 完整：`backend/app/modules/archives/service.py:104` 仅逻辑删除；`backend/app/worker/cleanup.py:68` 检查四类引用，包括已逻辑删除父资源 | `backend/tests/test_cleanup.py:96` 四类引用；`backend/tests/test_archives.py:44`、`:123` 删除归档/任务后受保护图片仍可读 |
| 清理默认禁用，不采用未确认天数 | 完整：`backend/app/worker/cleanup.py:21` 默认 cutoff=None；`:65`、`:96`、`:136` 无 cutoff 即返回；未注册调度或公开路由；`docs/CLEANUP-POLICY.md:3` 明确运行边界 | `backend/tests/test_cleanup.py:51` 无数据库或文件系统也直接 disabled；`:134` 新文件及所有 ready 文件保留 |
| 清理与引用写入互斥、对象故障可重试 | 完整：`backend/app/worker/cleanup.py:47` PG NOWAIT 表锁；`:74` 文件行锁；`:83` 同事务持久删除凭据；`:96` 独立重试 | `backend/tests/test_cleanup.py:78` 存储失败回执；`:191` 引用并发写入；`:254` 文件行锁竞争；非 PG 在 `:59` 明确保留 |
| 会话仅清理已删除、无有效执行且无归档引用任务 | 完整：`backend/app/worker/cleanup.py:143` 锁任务/轮次等；`:148` 删除时间门禁；`:151` 轮次/Job 终态；`:155` attempt 明确结束；`:161` 归档引用保护；`:120` UUID/链接路径边界 | `backend/tests/test_cleanup.py:144` 实际删除和审计保留；`:156` 活跃轮次；`:162` 可返工任务；`:169` 未核实执行；`:179` 任务锁；`:216` 归档；`:240` symlink |
| 迁移 | 完整：`backend/migrations/versions/0007_archives.py:8` 承接 0006，创建归档与清理回执四表 | `backend/tests/test_archives_migration.py:9` 重复升级、外键及降级保护上游；隔离集成含真实 PG 首次/重复迁移 |
| UI 一致性与引导真实性 | 真实归档按钮已解禁；说明对应当前版本快照，`frontend/src/views/hengxin/components/TaskDetail.vue:8`；成品页沿用 Art/Element Plus、现有样式，`frontend/src/views/hengxin/components/Archive.vue:3`，`frontend/src/views/hengxin/prototype.css:26`、`:28` | reviewer 实际打开成品空态/模板基准并读取渲染截图；有数据态 `output/playwright/phase11-archives.png` 已独立查看；Phase 11 浏览器闭环 PASS |

未实现：本范围内未发现。Phase 12 钉钉真实认证、Phase 13 管理统计和 Phase 14 实机/真实图像效果不属于本轮，不把 fixture 证据当成这些阶段验收。

Spec 漂移：未发现无依据的新页面或产品权限。ArchiveRequest 和 CleanupObject 为幂等及故障恢复基础设施，分别支撑既定归档/清理要求；ready 文件保留及显式 cutoff 是未确认保留期限下的保守策略，不自动启用建议的 30 天回收。

## Stage 2：Code Quality

已完成静态质量、安全、测试真实性与视觉核对，最终候选生成声明文件的类型检查补证据已通过。Stage 2：PASS。

- 代码结构：新增业务模块均未超过 300 行，ZIP、归档、清理和前端请求重放分离；新增前端没有 any。`backend/app/modules/archives/service.py:41`、`backend/app/worker/cleanup.py:65`、`frontend/src/views/hengxin/archive-requests.ts:6`。
- 安全扫描：对新增归档/清理/下载实现和前端接入执行 rg 检查 eval、innerHTML、dangerouslySetInnerHTML、前端 KEY/SECRET/TOKEN 与常见模型密钥前缀，未命中。SQL 动态部分只由 ORM 表元数据和 dialect quote 构造（`backend/app/worker/cleanup.py:47`），搜索值参数化且转义通配符（`backend/app/modules/archives/service.py:96`）。[PostgreSQL 16 锁文档](https://www.postgresql.org/docs/16/explicit-locking.html) 确认 SHARE ROW EXCLUSIVE 与引用写入的 ROW EXCLUSIVE 冲突。
- ZIP 资源释放：提前打开对象失败时关闭已打开对象，结束/发送失败统一由 OwnedStreamResponse finally 清理，单个 close/release 异常不阻止其他连接释放。证据 `backend/app/modules/files/downloads.py:51`、`:83`、`backend/app/modules/files/streaming.py:10` 及 `backend/tests/test_downloads.py:59`、`:116`。
- 测试真实性：PG 并发用独立 session 与真实数据库；图片处理是明确 fixture，不宣称真实 CLI 成像质量。归档快照断言同时覆盖版本 ID、记录、图片下载字节，服务端 ZIP 另校验真实格式；清理测试确实删除临时目录并检查邻居。原跨 owner 删除盲区已新增用例关闭并纳入最终快照，349 项后端测试覆盖该增量。
- LOW 运维边界：`backend/app/worker/cleanup.py:143` 至 `:166` 会在表锁持有期间递归删除任务目录，耗时随材料数量增加，会阻塞其它任务的对应表写入。默认禁用、显式单任务调用及 `docs/CLEANUP-POLICY.md:17` 已公开此限制，本阶段不阻塞；生产启用时应验证最大材料目录耗时并安排运维窗口。
- 视觉对比：reviewer 已用独立 CUA 隐藏标签实际打开隔离服务 `http://127.0.0.1:53618/#/archive/index` 空态及侧栏模板库有数据页并读取渲染截图，1280×720 下侧栏/工作标签、内容标题、蓝色主操作、白色圆角卡片、筛选行/搜索框一致；对应 `frontend/src/views/hengxin/prototype.css:26`、`:28`。另独立 view_image 查看最终 `output/playwright/phase11-archives.png` 的 1024×768 有数据态，归档名称、图片数、时间、查看/下载入口与基准卡片一致；白色图片是本轮已验证字节的 fixture，不能当成业务图像效果。脚本 `scripts/phase11/archives.js:84` 验证控件未被祖先容器裁切，预览图 naturalWidth > 0。

## 已读取的原始验证输出

来源为主 Agent 本轮运行日志，reviewer 已直接读取文件核对；没有把未执行测试写成 reviewer 独立运行。

`output/phase11-integration.log`（初始快照）：

```text
345 passed, 10 warnings in 31.96s
PASS real Worker Skill installation wallpaper
PASS real Worker Skill installation product
PASS real Worker Skill installation text
PASS durable queued/running deletion, no late versions, restart no resurrection
PHASE10 API PASS: asynchronous revision, queued/running barriers, stable replay, competing new requests, unchanged other slot IDs/object/hash, historical bytes and feedback
```

`output/phase11-frontend-tests.log`：

```text
ℹ tests 60
ℹ suites 0
ℹ pass 60
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1964.2179
```

`output/phase11-build.log`：

```text
✓ built in 35.38s
```

`output/phase11-typecheck.log` 原始 stdout 为空；主 Agent 提供 vue-tsc 退出码 0。初次 Vite 提前退出及 Phase 11 脚本沙箱前提错误均已复核后重跑；其失败记录不算通过证据。

补充最终回归原始输出：`output/phase11-regression.log` 保存四角色新用例及 Phase 10 浏览器结果；`output/phase11-integration.log` 保存最终脚本与故障回归。

```text
349 passed, 10 warnings in 29.97s
"PHASE10 BROWSER PASS: real single/whole revisions, 409 draft retained, stable key, unknown accepted response replay, background completion, readable historical image, feedback history; pageerrors=0"
```

```text
PASS fresh Linux PG/Redis/MinIO/API/Worker
PASS fresh and repeated migration
349 passed, 10 warnings in 29.54s
"PHASE8 BROWSER PASS: three real submissions, idempotency headers, background completion after leaving page, fixture label, executionControl, download, delete; pageerrors=0"
"PHASE11 BROWSER PASS: archive lost-response replay, revision preserves snapshot/bytes, old-version preview, single/streaming ZIP download, error/empty/retry, deletion reference protection; pageerrors=0"
PASS Phase11 single/ZIP exact archived fixture bytes
PASS hard SIGKILL plus expired lease remains uncertain, duplicate messages do not restart, slot retained
PHASE8 INTEGRATION PASS (four isolated volumes)
PASS isolated Compose volumes cleaned
```

最终完整隔离集成进程退出码 0（主 Agent 提供进程结果；上述原始日志已由 reviewer 读取），后端 349 项无 skip。最终 `output/phase11-typecheck-final.log` 原始 stdout 为空，主 Agent 提供 vue-tsc 退出码 0。

reviewer 最后实际运行 `harness.py review-status` 退出 0，原始输出关键字段如下：

```json
{"currentId":"9d487f4582f4a518ce7b6ba840097e8ff6bdb439e940d376084fcfce8b2820b3","approved":false}
```

currentId 与最终候选一致；approved=false 是尚未由主 Agent 登记凭据，不是测试失败。
