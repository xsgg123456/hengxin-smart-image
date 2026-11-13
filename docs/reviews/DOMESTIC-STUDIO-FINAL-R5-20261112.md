# 国内 AI 工作台及联合发布独立审查 R5 · 2026-11-12

## 结论、快照与范围

- **candidateId：`322b72ef31f27af38a27e5d3fa898b4f4395a139c9589d67f1888d3bcb012afd`；Stage 1：FAIL；Stage 2：未执行。** 存在核心图片标注修改能力缺失，不能登记两阶段 PASS 或用旧凭据批准该候选。
- 审查范围为 `Product-Spec.md:1-13` 的五个国内工作台、会话、附件、结果及恢复、成品归档、Skills 和国内外隔离；`DEV-PLAN.md:1-28` 的构建、迁移、发布和故障恢复；`Design-Brief.md:1-3` 及已确认预览 `hengxin-smart-image/frontend/preview-domestic-studio/`。重点追踪 R1–R4 的迁移、迟到写、大文件工作区和大图原件修复。以下 `backend/` 与 `frontend/` 均相对于 `hengxin-smart-image/`。
- 已阅读 `AGENTS.md`、`.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md` 和 `docs/reviews/DOMESTIC-STUDIO-FINAL-20261112.md` 至 `DOMESTIC-STUDIO-FINAL-R4-20261112.md`。开始时与报告撰写前 `review-status` 的 currentId 均为上述候选，approved 为 false。只读实现并执行隔离测试，没有修改受控代码、提交、登记批准、访问生产或调用真实模型。下述通过仅限明确列出的独立测试及其替身边界。

## Stage 1 · HIGH

### H1：国内结果图不能使用既有单图及批量标注修改

**要求与基准。** `Product-Spec.md:3,6,12` 要求复用海外实现并沿用现有结果、修改能力；`frontend/preview-domestic-studio/README.md:13` 明确图片标注与真实输出待正式接入时复用已有组件。既有单图能力包括框选/画笔、编号意见、缩放平移、撤销和带回草稿（`Product-Spec.md:1326-1331`）；既有海外批量逐张标注和参考材料见 `Product-Spec.md:78` 与 `docs/STUDIO-BATCH-ANNOTATION-20261105.md:7`。

**实际调用链。** 国内正式页将 `StudioTurns` 的 `@modify` 绑定为 `modify`，并固定 `simple-pictures`（`frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:15`）。结果图“修改这张”发出 `modify` 事件（`frontend/src/views/shared/studio/StudioTurns.vue:14-16`），实际接到的 `frontend/src/views/shared/studio/use-studio.ts:228-232` 只是将原图加入 references。国内正式页完整模板和 imports（`DomesticWorkspace.vue:1-85`）没有挂载标注编辑器、标注摘要或调用 `confirmRevisions`。用户仍可引用原图并填写普通文字，但无法框选/画笔、逐处描述、添加标注图、查看或继续编辑标注摘要。

同一组件的“批量标注”被 `!simplePictures` 条件包住（`StudioTurns.vue:13`），国内页固定 `simple-pictures`，因此批量入口也不可达；即使人为发出批量事件，当前处理器也只是逐张调用上述 `modify`（`DomesticWorkspace.vue:15`）。海外现有页分别把单图和批量事件接到 `openAnnotation`/`openBatchAnnotation`，挂载 `StudioEditDialog` 和 `StudioRevisionDraft`，并调用 `confirmRevisions` 回填（`frontend/src/views/overseas/studio/OverseasStudio.vue:23,29-31,43,99-123`）。国内后端已有 `freeze_edits`/`prompt_edits` 调用（`backend/app/modules/domestic_studio/turn_service.py:61-78`、`execution_workspace.py:67-75`），不能代替缺失的前端入口。

**批量与归档边界。** 本轮将既有批量标注计入“沿用现有修改能力”；国内新品归档按整会话，而非海外的按 SKU 选择图片，因此不将海外归档全选或按选中图片归档本身视为必须复用。已确认预览的 `state.ts:11-16` 只生成模拟文字，`README.md:13` 明确不伪造图片，所以预览不能证明真实结果区或批量按钮布局；本轮也没有实际浏览器渲染，以上是源代码控制流证据，不能称已实测图片编辑流程。

**测试范围。** 本轮执行现有共享组件与海外标注/批量草稿测试 32 项全部通过，原始输出见下；这些测试验证共享动作和海外路径，没有挂载国内正式页，因此不能证明国内存在编辑入口。修复后需覆盖国内真实组件动作、单图及批量编辑、返回草稿、发送前不自动执行、真实 `imageEdits`、切换会话与用户隔离，再从 Stage 1 起重新审查。

## Stage 1 · MEDIUM

### M1：教程没有按入口区分的可识别内容

`Product-Spec.md:9` 要求五入口教程按入口区分，正式内容缺失时如实显示待补充；`frontend/preview-domestic-studio/README.md:3,15` 记载各入口独立教程和切换时内容跟随。正式页 `DomesticWorkspace.vue:3,29` 五入口共用固定标题“使用教程”和唯一固定内容“教程待补充”，无 `config.title`、入口名称或其他区分。它没有编造教程，这部分符合；但抽屉内容无法区分五入口。本项为静态差异，未做同视口 UI 验证；正式图文/视频尚无授权素材，不能为了修复而编造。

## Stage 1 · 逐项状态与未验证边界

| 条目 | 本轮证据及状态 |
| --- | --- |
| 两个新品、三个替换、成品库一级、超管 Skills | 部分：入口 `frontend/src/api/hengxin/domestic-workspaces.ts:3-8`、路由 `frontend/src/router/modules/index.ts:12-29`；本轮未实际逐入口登录导航或逐角色验收。 |
| 空白、无欢迎/示例、无预填与自动发送 | 部分：`DomesticWorkspace.vue:15-23` 隐藏空态引导且输入绑定空草稿；`frontend/src/views/shared/studio/use-studio.ts:15,153-157` 的发送由动作触发。未对五入口做实际渲染和完整自动触发盘点。 |
| 会话创建、切换、重命名、删除及私人文件 | 部分：`backend/app/modules/domestic_studio/conversation_service.py:29-47,70-106`、`file_service.py:75-97`；本轮 `tests/test_domestic_files_pg.py:59-85` 对跨用户、跨工作台找文件有真实隔离 PG 加存储替身的测试。未独立覆盖所有角色和浏览器会话流程。 |
| 真实姓名、北京时间和消息位置 | 部分：`backend/app/modules/domestic_studio/queries.py:68-100`、`frontend/src/views/shared/studio/StudioTurns.vue:6-7`、`frontend/src/utils/beijing-time.ts:1`；未完成真实登录及同视口显示核对。 |
| 输入、附件、连续对话、结果、修改、停止、异常 | **不通过：H1。** 发送/停止入口 `backend/app/modules/domestic_studio/router.py:94-113`；未独立调用真实模型。 |
| 部分收取保留和手动取回、原进程未核实不重生 | 部分：`backend/app/modules/domestic_studio/runner.py:66-83`、`recovery_files.py:89-100,113-187`；独立的真实 MinIO 迟到取回测试通过，未覆盖所有原节点和进程故障。 |
| 上传/输出/手动取回/归档迟到写及分片 | 部分：`file_service.py:43-72`、`output_intents.py:13-32,35-61`、`archive_service.py:203-225`；本轮真实隔离 MinIO + PG 定向用例通过，包括迟到写、重试单次写与分片完成故障，但不能外推至所有远端故障。 |
| 大附件上传、工作区、输出与归档 ZIP | 部分：`file_service.py:29-40,64`、`backend/app/overseas/studio/context_assets.py:91-113`、`archive_router.py:70-98`；本轮真实 MinIO 测试包含 500,000,000 字节合成文件上传、工作区和归档/输出，ZIP 测试使用存储替身及尾随零的 64 MiB PNG。`tracemalloc` 不是全部原生内存或生产并发 RSS。 |
| 大图预览/下载、权限、类型、校验及释放 | 部分：`backend/app/overseas/image_delivery.py:36-54,63-93` 先复制校验再经 `app/modules/files/streaming.py:4-21` 分块响应；`backend/app/modules/domestic_studio/router.py:160-175` 查拥有者。隔离真实 MinIO + PG 的有效 4096×4096 PNG 原图预览和下载均测完整哈希、Python 堆峰值及摘要错误；普通流断连前/中关闭有独立测试。海外小图 HTTP 用例覆盖 PNG/JPEG/WebP 类型、HEAD、权限及下载，国内跨用户查找有 PG 用例。该大图测试直接调用路由函数并构造 actor，非完整 HTTP 登录；本轮未独立验证大图并发、所有长度错误、所有缩略图缓存及条件请求组合。 |
| 教程入口与入口差异 | 部分：有入口与如实待补充；入口区分不符 M1，证据见 `DomesticWorkspace.vue:3,29`。 |
| 仅新品可归档、替换防绕过 | 部分：`backend/app/modules/domestic_studio/policy.py:27-30`、`archive_service.py:101-103`；本轮重跑归档 PG 测试，未完成全部 HTTP 绕过矩阵。 |
| 独立归档、共享副本、源会话私人及源删后保留 | 部分：`archive_service.py:37-50,101-176`、`conversation_cleanup.py:44-57`、`archive_queries.py:10-21,47-84`；重跑 `tests/test_domestic_archive_pg.py`，但未完成全部角色、源删后真实浏览器和存储故障矩阵。 |
| 搜索、来源、详情、下载、删除及图片保护 | 部分：`archive_queries.py:33-44`、`archive_router.py:36-98`、`frontend/src/views/hengxin/domestic-studio/library.vue:3-11`；独立 ZIP 定向回归通过。未全面实测 UI 下载/删除和图片保护。 |
| 超管 Skills 文件夹 CRUD、同名更新、ZIP、无版本/在线编辑 | 部分：`backend/app/modules/domestic_studio/management_router.py:77-163`、`frontend/src/views/hengxin/admin/skills.vue:1`；未独立复测整个上传、同名冲突、ZIP及权限交互矩阵。 |
| 五入口空绑定、服务端防绕过、冻结及绑定保护 | 部分：`backend/migrations/versions/0033_domestic_studio_bindings.py:5-26`、`backend/app/modules/domestic_studio/bindings.py:37-82`、`turn_service.py:42-78`；未完成本候选所有并发和 UI 路径。 |
| 国内外身份、库、对象、队列及旧能力 | 部分：`backend/app/modules/domestic_studio/recovery_transport.py:4-14`、`scripts/release/intranet/domestic_studio_wiring.py:42-114`；部分海外图片 HTTP 测试通过，未完成全量跨业务真实端到端或生产隔离验收。 |
| 迁移、子进程/DB 锁、旧台账重入和前向恢复 | 部分：`scripts/release/intranet/joint_studio_engine.py:33-52`、`joint_studio_fence.py:25-60`、`joint_studio_release.py:160-198`、`backend/migrations/env.py:39-47` 可见屏障及恢复分支；本轮未独立重放联合迁移及所有故障，不能沿用旧候选结论。 |
| UID/GID、socket、部署工具、备份、切换 | 未完成：`scripts/release/intranet/joint_studio_verify.py:36-86` 为配置和身份检查代码；未在真实 Docker 身份下安装运行，未做生产操作。主 Agent 另交付 `output/domestic-studio-release-bin/` 临时脚本不属于候选快照；因 Stage 1 HIGH，未进入其单独安全审查。 |
| 预览同视口、邻居基准、漂移、构建与发布验收 | 未完成：`Design-Brief.md:1-3` 与预览为基准；本轮未实际对照正式页面与预览/邻居，也未完整盘点新增页面、API、表。仅做下列类型及定向测试，不是生产构建/发布验收。 |

## 资源观察与测试真实性

`backend/app/overseas/studio/files.py:50-65` 允许最多 6000 万像素并执行 Pillow `image.load()`；`backend/app/modules/domestic_studio/router.py:144-154` 通过工作线程处理国内上传，没有在该路径看到解码并发门限。独立 WSL 探针同时调用两次真实 `validate_stream`，输入均为合法 10000×6000、189468 字节 PNG，两次均返回 `image/png`，进程 `ru_maxrss=545996 KiB`。探针输入为高度压缩的单色图片，直接调用校验函数，非 HTTP 端到端、非生产压测；该解码逻辑原已存在于海外校验（对照 `git show HEAD:hengxin-smart-image/backend/app/overseas/studio/files.py`），本次被国内入口复用。主 Agent 随后提供当前只读实查结果：国内 API 未设置容器级内存上限、宿主 MemTotal 16328704 kB；本 reviewer 未独立访问生产，不能使用旧的 384 MiB 记录推断当前必然 OOM。应将高像素多用户并发及原生内存列为尚未验证的资源风险；上述 `tracemalloc` 不能覆盖 Pillow 原生解码内存。

## 本 reviewer 独立验证与编译原始输出

后端在 WSL、`backend/` 设置 `PYTHONPATH=.:tests`，仅使用 `127.0.0.1:35439/hx_studio_test` 随机 schema 和 `127.0.0.1:35441` 随机测试 bucket，启用 `TEST_DOMESTIC_MINIO_LARGE=1`；fixture 清理自身随机测试资源。真实 MinIO 测试为 `test_domestic_image_stream_real_minio_pg.py`、`test_downloads.py`、`test_domestic_upload_real_minio_pg.py`、`test_domestic_late_outputs_real_minio_pg.py`、`test_domestic_multipart_real_minio_pg.py`、`test_domestic_workspace_real_minio_pg.py`、`test_domestic_archive_large_real_minio_pg.py`。退出码 0，原始汇总：

```text
..............                                                           [100%]
14 passed, 1 warning in 24.56s
```

第二组 `test_domestic_recovery_lock_pg.py`、`test_domestic_admin_permissions_pg.py`、`test_domestic_archive_pg.py`、`test_domestic_transcript_pg.py`、`test_domestic_studio_http_pg.py`、`test_studio_context_assets.py`；退出码 0，跳过项不计通过：

```text
..............s.................                                         [100%]
31 passed, 1 skipped, 1 warning in 24.41s
```

第三组 `test_studio_image_preview.py`、`test_domestic_files_pg.py`、`test_domestic_archive_zip_stream_pg.py`；退出码 0：

```text
.....................                                                    [100%]
21 passed, 1 warning in 23.69s
```

前端 `pnpm exec tsx --test tests/studio-batch-revisions.test.ts tests/overseas-studio-images.test.ts tests/studio-process-component.test.ts tests/studio-sessions.test.ts` 退出码 0；原始汇总：

```text
ℹ tests 32
ℹ suites 0
ℹ pass 32
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1108.4689
```

前端 `pnpm run typecheck` 退出码 0，原始输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.

> hengxin-smart-image-frontend@0.2.69 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

这只是类型检查，不是生产构建。本 reviewer 没有独立执行全量前后端及发布测试；主 Agent 报告的全量结果需单独记录，不可冒充本轮独立结果。既有依赖审计中的 high 风险未在本轮修复，不能声称依赖安全已全部通过。

## Stage 2

**未执行。** Stage 1 有 HIGH；没有系统执行质量、安全或测试真实性的完整扫描，也未打开正式页与邻居、确认预览做同视口视觉对比，未审候选外的临时部署辅助脚本。修复后由主 Agent 重新固定快照并重派，从 Stage 1 开始；不得把本报告用于 `review-approve` 的两阶段 PASS。

报告写成后只读核对的原始状态（报告自身不纳入受控代码快照）：

```json
{"currentId": "322b72ef31f27af38a27e5d3fa898b4f4395a139c9589d67f1888d3bcb012afd", "reviewedId": "d3a967332ae14940e06e774849782af11917f8c7bc2e0902deee6d698edc3ce1", "approved": false}
```

审查期间受控代码快照未变；该状态不是通过凭据。
