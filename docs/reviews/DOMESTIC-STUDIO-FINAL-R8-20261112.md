# 国内 AI 工作台、成品库与联合发布独立审查 R8 · 2026-11-12

## 结论、快照与边界

- **candidateId：`013e0b7033f8b53fa40e06f7ee064a4e74efc1b78c24d661797d7aa14c41e01e`；Stage 1：FAIL；Stage 2：未执行。** 归档详情会校验封存清单，但归档文件内容和 ZIP 下载绕过同一校验。在数据库中的归档文件记录被篡改或损坏后，已授权国内成员仍可通过归档文件 URL 读到未归档的私人附件。此结论的前提是记录已被修改，**没有证据表明普通 HTTP 用户能够自行修改数据库记录**；它不应被描述为已证实的无前提外部攻击。此问题违背归档快照完整性和源文件私有边界，属 HIGH。
- 审查范围：`Product-Spec.md:1-13` 的五工作台、会话、结果恢复、权限、成品库、Skills 和国内外隔离；`DEV-PLAN.md:1-32` 的实施和联合发布；`Design-Brief.md:1-3` 与用户确认的 `hengxin-smart-image/frontend/preview-domestic-studio/`；重点为 FINAL 至 FINAL-R7 的历史问题及本候选对 R7 的归档状态/过程和响应式修正。本报告 `backend/`、`frontend/` 均相对于 `hengxin-smart-image/`。
- 已读取 `AGENTS.md`、`.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、本轮 Spec、计划、Brief、实现说明、R7 报告及前几轮 HIGH 索引；本轮实际覆盖程度见逐项表，不能把旧报告的测试或实现说明当成当前快照的通过证据。由于发现 HIGH，未完成全部旧报告细节复审、独立浏览器对照、发布工具审计或整体验收。
- 本次测试使用 `127.0.0.1:35439/hx_studio_test` 上随机隔离 PostgreSQL schema 和测试内存对象存储；经 FastAPI TestClient 的真实路由与依赖替身进行访问，不是生产 HTTP、真实登录或真实模型。未修改业务代码、未提交、未批准、未写 clean、未访问生产。
- 审查开始、第一次独立复现后、通知主 Agent 修复前，`review-status` 均为 `currentId=013e0b7033f8b53fa40e06f7ee064a4e74efc1b78c24d661797d7aa14c41e01e`、`approved:false`。通知后主 Agent 已开始修复，报告期间观察到 `archive_service.py`、`archive_queries.py`、`archive_router.py`、`conversation_cleanup.py` 以及新增测试发生变化；随后只读状态为 `currentId=65cd4bba493b2695df778d3c85f8dc21f86a0636dd8158ade2f6c309d3125134`、`approved:false`。下列代码行与结论仅针对原候选，**不评判或批准变动后的代码**；必须重新固定并审查新快照。

## Stage 1 · HIGH

### H1：归档文件和 ZIP 不核验封存清单，损坏后仍会读取源私有对象

**要求。** `Product-Spec.md:10` 要求归档独立保存、所有已授权国内成员只访问归档副本，源会话及原始文件仍仅创建人可见；本轮交接明确要求核验快照防篡改和源私有 ID/文件隔离。`DEV-PLAN.md:28-32` 要求逐图资料校验及归档内独立副本。

**原候选代码链。** `backend/app/modules/domestic_studio/archive_service.py:72-115` 的 `verify_snapshot` 将快照摘要、归档文件行及其封存 manifest 比对；`archive_queries.py:47-53` 的详情查询会调用它并在不匹配时拒绝。相反，`archive_queries.py:81-85` 的文件查询只检查归档可用及 `ArchiveFile.archive_id`，不调用该校验；`archive_router.py:59-66` 直接据此读取对象。`archive_router.py:70-81` 的 ZIP 路径直接列举 picture 行并复制，也不先比较完整 manifest。保留或获知归档 URL 的成员因此不必先成功取得详情。

**独立复现。** `output/review-r8-archive-manifest-probe.py` 使用真实归档 prepare/complete、FastAPI 路由和两个国内测试身份：先完成合法归档，再由创建人上传一份从未归档的私人附件；仅在测试数据库中把一条归档 `ArchiveFile` 的对象位置、长度和摘要改为该附件，保持封存 snapshot 原样，同时将原归档副本从测试存储移除。对 picture 行也改为源图片位置以验证图片与 ZIP 读取路径。第二成员直接访问私人文件获得 404，详情因 manifest 不符获得 503；但归档附件、图片及 ZIP 仍成功。原始输出：

```text
other_member_direct_private= 404 tampered_detail= 503 archive_upload= 200 archive_picture= 200 archive_zip= 200 source_bytes= 从未归档的私人附件
.
=============================== warnings summary ===============================
../../../../../../tmp/hengxin-domestic-studio-python/lib/python3.14/site-packages/fastapi/testclient.py:1
  /tmp/hengxin-domestic-studio-python/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1 passed, 1 warning in 12.37s
```

这里 pytest 的 PASS 代表**缺陷成功复现**，不代表产品验收通过。附件示例证明读取到了不同于合法归档内容的私人字节；图片和 ZIP 的本次样例指向原源图片，其字节也曾被合法归档，单独只能证明这两条路径没有拒绝同样的清单不匹配。测试主动模拟了数据库记录损坏/篡改，不证明用户能通过产品 API 发起该修改，也不证明真实 MinIO 或生产受到影响。

应在每个归档内容读取入口验证同一完整封存清单和所请求的文件，包含 GET、HEAD、图片预览、缩略图与 ZIP，并注意校验与捕获读取参数之间的并发边界；不应以仅详情校验代替文件接口校验。修复后用合法副本、篡改对象位置/元数据/清单、第二成员私有文件、源删除和大文件路径重新测试，重新固定候选。

## Stage 1 · 逐项审查状态

“部分”只表示列出的证据和定向测试，不等于整项端到端通过。发现 HIGH 后按派发要求停止，未完成的情况如实保留。

| 条目 | 本轮状态、证据与边界 |
| --- | --- |
| 新品两入口、替换三入口、独立成品库与超管 Skills | 部分：`frontend/src/api/hengxin/domestic-workspaces.ts:3-8`、`frontend/src/router/modules/index.ts:12-30` 有相应配置；未独立逐角色和五入口浏览器操作。 |
| 直接对话、空白、无默认提示词/自动发送 | 部分：`frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:15-27` 复用工作台与输入组件；未独立复测所有入口和自动发送路径。 |
| 各入口独立多会话、新建、切换、重命名、删除、源私有 | 部分：`backend/app/modules/domestic_studio/conversation_service.py:29-33,70-106`、`file_service.py:75-97`；本轮前端会话组和后端隔离组通过，包含切换和跨用户拒绝；未完成真实身份全角色端到端。H1 是数据库记录损坏情形的归档文件隔离失效。 |
| 真实姓名、时间、左右布局 | 部分：`backend/app/modules/domestic_studio/queries.py:84-92`、`frontend/src/views/shared/studio/StudioTurns.vue:6-7`；本轮未独立用真实登录身份或页面截图验证。 |
| 附件、连续对话、结果、修改、停止和异常 | 部分：`DomesticWorkspace.vue:15-36,81-100`、`backend/app/modules/domestic_studio/turn_service.py:42-80,91-116`；已有浏览器日志 `output/playwright/domestic-annotation.log` 使用模拟 API，不能当真实后端或模型的证明；本轮未独立执行该浏览器场景。 |
| 部分收取、手动取回、进程不确定时不重生 | 部分：`backend/app/modules/domestic_studio/runner.py:66-83`、`recovery.py:38-76`；本轮没有独立故障注入完整重跑。 |
| 上传、输出、取回、归档迟到写及大附件/高像素有界 | 部分：`file_service.py:43-72`、`output_intents.py:13-61`、`archive_service.py:203-253`；本轮未重跑真实 MinIO、并发 RSS、大图或迟到写矩阵，不把 R7 的结果当本候选复验。 |
| 五入口教程且未提供内容时待补充 | 部分：`DomesticWorkspace.vue:3,33` 以当前入口名显示教程和待补充；未独立逐入口展开。 |
| 仅新品按产品名归档，产品替换服务端拒绝 | 部分：`backend/app/modules/domestic_studio/policy.py:12-30`、`archive_service.py:118-120`；本轮后端归档及 HTTP 定向组通过，未完成所有绕过组合。 |
| 整会话、公开过程、真实终态/错误、删源后供国内成员查看 | 部分：原候选 `archive_service.py:166-198` 保存真实 `Job.status`、`turn.error or job.error`、归档本地 `event-N`；`archive_queries.py:59-64` 返回，`frontend/src/views/hengxin/domestic-studio/library.vue:11,37` 调用 `StudioProcess` 显示状态和错误，`archive-transcript.ts:4-6` 调用共享合并函数，旧项无 ID 按索引区分。`backend/tests/test_domestic_archive_edits_pg.py:70-116,162-175` 和 `frontend/tests/domestic-archive-edits.test.ts:51-58` 在本轮定向执行；后三种终态测试直接设置数据库状态和错误，**不等于独立复现真实失败、取消或部分收取执行链**。删源后第二成员与修改资料覆盖测试存储替身；H1 导致整体不通过。 |
| 成品查询、来源、详情、删除、下载及图片保护 | **不通过：H1。** `archive_queries.py:24-44`、`archive_router.py:36-90` 有对应路由；存在清单损坏后文件和 ZIP 读取绕过。未穷尽所有资源或条件请求组合。 |
| 超管 Skills 文件夹 CRUD、ZIP，无版本/在线编辑器 | 部分：`backend/app/modules/domestic_studio/management_router.py:77-163`，前端 Skills 定向测试通过；本轮未独立浏览器完成上传、同名更新、启停、删除和 ZIP 内容矩阵，也未完整盘点界面漂移。 |
| 五个绑定上线空白、服务端强制、冻结和禁用保护 | 部分：`backend/migrations/versions/0033_domestic_studio_bindings.py:5-26`、`bindings.py:37-82`、`turn_service.py:42-80`；本轮前端绑定和后端权限部分定向测试通过，未完成完整竞态验证。 |
| 国内外身份、库、对象、队列隔离及原业务兼容 | 部分：`domestic_studio/router.py:28-29`、`recovery_transport.py:4-14`、`scripts/release/intranet/domestic_studio_wiring.py:42-114`；本轮未重新执行海外全量、真实跨业务端到端或生产环境。 |
| 迁移屏障、已写旧台账后的重入、前向恢复 | 未完成：`scripts/release/intranet/joint_studio_fence.py:26-60`、`joint_studio_release.py:160-198`、`backend/migrations/env.py:39-47` 为相关实现；本轮未重跑真实进程、隔离 PG 迁移或故障注入。 |
| 正式页对照确认预览和 R7 响应式问题 | 未完成：`frontend/src/views/hengxin/domestic-studio/workspace.css:4,8-11` 和 `DomesticWorkspace.vue:32,71-72` 有相关修改；已阅读 `output/playwright/domestic-responsive.log` 与模拟脚本，它声称测量 1920、1000、390，但本 reviewer 发现 HIGH 后未独立重测，也未将其视为本轮视觉通过。 |
| 构建、测试、独立两阶段审查和联合发布 | **不通过：Stage 1 有 HIGH。** 本轮只完成下列定向测试和类型检查，没有独立重新运行生产构建、全量测试、真实安装、正式入口或模型验收；禁止凭此报告登记两阶段通过或宣称上线。 |

## 本 reviewer 独立测试与编译原始输出

- 隔离 PostgreSQL：`test_domestic_archive_edits_pg.py`、`test_domestic_archive_pg.py`、`test_domestic_studio_http_pg.py`、`test_domestic_transcript_pg.py`、`test_domestic_conversations_pg.py`、`test_domestic_admin_permissions_pg.py`，退出码 0；对象存储为测试替身。一个未配置隔离 Redis 的测试跳过，跳过不计通过：

```text
..............s.................                                         [100%]
=============================== warnings summary ===============================
../../../../../../tmp/hengxin-domestic-studio-python/lib/python3.14/site-packages/fastapi/testclient.py:1
  /tmp/hengxin-domestic-studio-python/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
31 passed, 1 skipped, 1 warning in 22.17s
```

- 前端定向 `pnpm exec tsx --test tests/domestic-archive-edits.test.ts tests/domestic-studio-skills.test.ts tests/studio-process-component.test.ts tests/studio-sessions.test.ts`，退出码 0，原始汇总：

```text
ℹ tests 27
ℹ suites 0
ℹ pass 27
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1839.6198
```

- `pnpm run typecheck` 退出码 0，原始输出：

```text
> hengxin-smart-image-frontend@0.2.70 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

本轮没有独立执行构建；类型检查不能冒充生产构建。`frontend/package.json:3` 版本已为 `0.2.70`。主 Agent 给出的 38 项后端、564 项前端及双范围构建属于其提供的验证记录，不能冒充本 reviewer 独立结果，更不能把修改之前的后端全量测试称为本候选全量。

## 候选外上线辅助脚本

`output/domestic-studio-release-bin/` 不在 candidateId 中。发现 HIGH 前只读计算的 11 个 `.py` SHA-256 均与 `docs/reviews/DOMESTIC-STUDIO-FINAL-R7-20261112.md` 所列一致；未独立完整重审或运行生产辅助脚本，也没有操作服务器。哈希一致不证明这些脚本、提交后工作树、安装目录或服务器状态自动安全。上传、stage、安装、冒烟或发布中断时仍应先只读核对已知路径、哈希、台账、标记和引用，不能覆盖或自动回滚生产。

## Stage 2

**未执行。** Stage 1 存在 HIGH，本轮没有系统开展代码质量、安全扫描、测试真实性全面审查、Spec 漂移盘点，以及正式页与邻居基准页的实际视觉对比。以上局部读取、单个安全边界复现与辅助脚本哈希核对不构成 Stage 2 PASS。主 Agent 修复后必须重新 `review-prepare`、交新的 candidateId 并从 Stage 1 重审；本报告不能用于 `review-approve` 登记两阶段 PASS。

报告写成后的再次只读状态：`currentId=10e1f7ea120450ff491fb6c282c4e84f11fbe51afe32a7ec96d0361447d4b67d`，`approved:false`。该后续快照未由本报告审查。
