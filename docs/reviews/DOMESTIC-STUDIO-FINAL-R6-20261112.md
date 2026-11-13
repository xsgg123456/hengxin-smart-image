# 国内 AI 工作台及联合发布独立审查 R6 · 2026-11-12

## 结论与范围

- **candidateId：`071056415a3a73d61f60b9085d57156b03c612c8910164077ad349d95b478740`；Stage 1：FAIL；Stage 2：未执行。** 新的单图/批量标注会产生逐图参考材料，但整会话归档丢失其中的用途、说明和文件关联；删除源会话后无法从归档找回。这是核心归档资料完整性 HIGH，不得登记本候选两阶段 PASS。
- 范围：`Product-Spec.md:1-13` 的五工作台、私人会话、输入附件及结果恢复、Skills、成品库和国内外隔离；`DEV-PLAN.md:1-30` 的开发、构建、联合升级及恢复；`Design-Brief.md:1-3` 和用户确认的 `hengxin-smart-image/frontend/preview-domestic-studio/`。已读取 `AGENTS.md`、`.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、`docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md` 和 FINAL R1–R5 报告。本报告中 `backend/`、`frontend/` 相对于 `hengxin-smart-image/`。
- 本轮只读业务代码，测试使用本机隔离 PostgreSQL 的随机 schema、内存对象存储与合成图片，不连接生产、不调用真实模型、不提交或批准。下列“部分”均不等于整项通过。发现 HIGH 后停止完整审查；新候选修复后须重新固定并从 Stage 1 重审。
- 独立探针开始时、完成后及通知主 Agent 可开始修复前，`review-status` 均显示目标 candidateId、`approved: false`。报告编写后复查时 `currentId` 已变为 `89d0f6e246200b91065e57eba7f9602560ef2356ada99c0274e369c2f2861740`，主 Agent 已获通知可开始修复；具体后续变化未在本报告复审。以下结论只对应上述旧快照，不覆盖后续修改。

## Stage 1 · HIGH

### H1：归档丢失图片修改的参考用途、说明和逐图关联

**要求。** `Product-Spec.md:6,10` 要求沿用既有图片修改能力、按产品名称归档当前会话成品及相关对话资料，删除源会话后归档独立保留。`Product-Spec.md:78` 和 `docs/STUDIO-BATCH-ANNOTATION-20261105.md` 的既有修改协议按图片分别冻结意见和参考材料。`DEV-PLAN.md:30` 指定国内复用单图、批量标注、参考图上传及国内发送接口。

**真实调用链。** 前端将每张图片的 `pictureId`、`annotationId`、参考图的 `attachmentId`、`kind`、`customPurpose` 和 `note` 放入 `imageEdits`（`frontend/src/views/shared/studio/use-studio.ts:153-157`）。服务端在 `backend/app/modules/domestic_studio/turn_service.py:61-80` 冻结到源轮次 `snapshot.imageEdits`；`backend/app/overseas/studio/image_edits.py:7-30,58-73` 按图绑定并向模型提供原图、标注、参考用途和说明。源会话查询通过 `backend/app/modules/domestic_studio/queries.py:87-100` 公开这些修改资料，源页面可查看本轮修改材料（`frontend/src/views/shared/studio/StudioTurns.vue:6,23`）。

归档准备时 `backend/app/modules/domestic_studio/archive_service.py:149-169` 复制附件、引用图片、输出、文字和 transcript，却没有读取或保存 `turn.snapshot.imageEdits`；`backend/app/modules/domestic_studio/archive_queries.py:59-75` 不返回这些字段；`frontend/src/api/hengxin/domestic-archives.ts:6,25-30` 及 `frontend/src/views/hengxin/domestic-studio/library.vue:10-11` 也没有相应结构或详情。`message_text` 会把每图的文字意见拼入普通消息（`backend/app/overseas/studio/image_edits.py:34-41`），所以不能说所有标注文字都丢失；但参考 `kind`、自定义用途、参考说明、标注图/参考图与各原图之间的机器可识别关联没有保留。即使图片字节都已复制，无法判断哪张参考图属于哪张原图及具体怎样参考。源会话删除后该结构不在归档数据中，无法由归档恢复。

**独立复现。** `output/review_r6_archive_edits_probe.py` 使用真实 `turn_service.send`、`archive_service.prepare/complete` 和 `archive_queries.detail`，隔离 PostgreSQL 随机 schema、内存存储替身；构造两张原图、一张标注图和一张自定义用途参考图，确认原轮次成功后真实归档。末尾断言当前缺陷存在，因此 pytest PASS 表示缺陷得到复现，不表示产品验收通过。原始关键输出：

```text
source_text= 修改图片1.png：
change first

修改图片2.png：
change second
source_edits= [{'pictureId': '019e2fa8-110b-4a0c-ba52-244f8c907bb8', 'annotationId': 'upload:e4c024e9-ef7e-4247-8564-93c9d7e48d4c', 'text': 'change first', 'references': [{'attachmentId': 'upload:4972aefa-a55b-4801-93c2-fabc4497ac74', 'kind': 'custom', 'customPurpose': 'PAPER_FINISH', 'note': 'USE_MATTE_COPPER', 'inputIndex': 1}], 'pictureInputIndex': 2, 'annotationInputIndex': 0}, {'pictureId': '1f9f6836-835a-40d9-a4e2-66da0271fc69', 'annotationId': None, 'text': 'change second', 'references': [], 'pictureInputIndex': 3, 'annotationInputIndex': None}]
archived_fields= ['actorName', 'attachments', 'createdAt', 'id', 'outputs', 'pictures', 'referencePictures', 'reply', 'replyAt', 'text', 'transcript']
archived_text= 修改图片1.png：
change first

修改图片2.png：
change second
archived_attachments= 2
archived_reference_pictures= 2
note_preserved= False
purpose_preserved= False
structured_edits_preserved= False
.
1 passed in 12.35s
```

探针没有实际删除源会话或调用 HTTP/真实模型：丢失发生在真实归档快照和详情生成阶段；删除后的不可恢复是由归档内没有对应数据、源会话资料随删除清理（`backend/app/modules/domestic_studio/conversation_cleanup.py:117-124`）推得。第一次启动探针因为测试文件在 `tests/` 外，没有自动加载 `tests/conftest.py:1-7` 的假设置，报 `Settings` 缺少 `database_url`、`minio_access_key`、`minio_secret_key`；补充假测试设置并建隔离归档表后，上述复现成功，不把该启动错误当产品缺陷。

建议修复时将每图的公开修改数据映射到**归档副本** ID，校验这些引用属于同一归档并展示用途与说明；不能把源会话的私人 URL 暴露给其他成员。应覆盖单图、批量、多张参考图、重复文件名、跨成员查看、源会话删除后查看、快照篡改拒绝及无修改的旧归档兼容，修后重新送审。

## Stage 1 · 已核对状态与边界

| 条目 | 状态与本轮证据 |
| --- | --- |
| 两个新品、三个替换、一级成品库、超管 Skills | 部分：`frontend/src/api/hengxin/domestic-workspaces.ts:3-8`、`frontend/src/router/modules/index.ts:12-29`。未独立逐角色逐入口渲染。 |
| 初始空白、无预置提示或自动发送 | 部分：`frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:15-27`、`frontend/src/views/shared/studio/use-studio.ts:15,153-157`。未逐入口浏览器实测。 |
| 多会话、新建/切换/重命名/删除、用户隔离 | 部分：`frontend/src/views/shared/studio/use-studio-sessions.ts:87-125,153-164`；本轮会话前端定向测试含切换和迟到回填，后端定向测试含跨成员拒绝。未完整覆盖全部端到端角色。 |
| 真实姓名、北京时间、左右排列 | 部分：`backend/app/modules/domestic_studio/queries.py:87-92`、`frontend/src/views/shared/studio/StudioTurns.vue:6-7`；未用真实登录身份独立验证。 |
| 发送、附件、单图/批量修改及草稿隔离 | 部分：`DomesticWorkspace.vue:15-22,36,76-100` 已接入编辑器和草稿，`use-revision-actions.ts:39-92` 在上传及回填时核查会话；本轮 33 项共享/会话/Skills 前端测试通过、PG 标注定向测试通过。主 Agent 的 `output/playwright/domestic-annotation-functional.js` 使用模拟 API；本轮未独立浏览器复测或调用真实模型。 |
| 教程入口及待补充 | 部分：`DomesticWorkspace.vue:3,33` 标题使用当前工作台名、正文“教程待补充”，已修复 R5 的固定标题；未逐入口实际渲染。 |
| 部分收取、手动取回、不确定进程不重生 | 部分：`backend/app/modules/domestic_studio/runner.py:66-83`、`recovery_files.py:24-40`；本轮未重跑原节点和全部故障矩阵。 |
| 迟到写、大附件与大图 | 部分：`file_service.py:29-72`、`output_intents.py:13-61`、`backend/app/overseas/image_delivery.py:36-93`；本轮未复跑 R1–R4 真实 MinIO 迟到写、大文件、跨进程和内存探针，不能沿用旧快照测试作为本轮通过证据。 |
| 仅新品可归档、产品替换后端拒绝 | 部分：`backend/app/modules/domestic_studio/policy.py:27-30`、`archive_service.py:101-103`；本轮重跑归档测试，但未执行完整绕过矩阵。 |
| 归档整会话、共享副本、源会话私人及源删除后保留 | **不通过：H1。** `archive_service.py:149-169` 丢失结构化修改材料；跨成员原始文件隔离及其他数据删除后保留尚未完整复验。 |
| 搜索、来源、详情、删除、下载、图片保护 | 部分：`backend/app/modules/domestic_studio/archive_queries.py:24-76`、`archive_router.py:36-98`；H1 说明详情不完整，本轮未独立完成全部浏览器、ZIP 和权限场景。 |
| 超管 Skills CRUD/ZIP/绑定、初始空、禁止绕过 | 部分：`backend/app/modules/domestic_studio/management_router.py:77-163`、`bindings.py:37-82`、`backend/migrations/versions/0033_domestic_studio_bindings.py:5-26`；本轮部分前端和 PG 权限测试通过，未实操整个文件夹上传、ZIP 和故障矩阵。 |
| 国内外隔离、旧业务不损坏 | 部分：`backend/app/modules/domestic_studio/recovery_transport.py:4-14`、`scripts/release/intranet/domestic_studio_wiring.py:42-114`；海外共用组件及全部旧业务未作完整回归，未连接生产。 |
| 联合迁移、进程/DB 屏障、台账与前向恢复 | 部分：`scripts/release/intranet/joint_studio_fence.py:25-60`、`joint_studio_release.py:160-198`；本轮未重跑真实 PG 迁移进程或台账故障注入。 |
| 预览 UI、漂移、完整构建及正式验收 | 未完成：未做正式页与确认预览的实际同视口对比，未完整盘点漂移，未独立执行海外生产构建或真实安装部署。国内范围构建与类型检查见下。 |

## 本 reviewer 独立测试及编译输出

前端定向执行 `pnpm exec tsx --test tests/studio-batch-revisions.test.ts tests/overseas-studio-images.test.ts tests/studio-sessions.test.ts tests/domestic-studio-skills.test.ts`，退出码 0。原始汇总：

```text
ℹ tests 33
ℹ suites 0
ℹ pass 33
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1577.5812
```

后端在 WSL、`backend/` 使用指定隔离 `127.0.0.1:35439/hx_studio_test` 和随机 schema，运行 `test_domestic_image_edits_pg.py`、`test_domestic_studio_http_pg.py`、`test_domestic_archive_pg.py`、`test_domestic_admin_permissions_pg.py`；对象存储为测试替身。退出码 0，跳过项不计通过：

```text
.............s.........                                                  [100%]
22 passed, 1 skipped, 1 warning in 16.66s
```

前端 `pnpm run typecheck` 退出码 0，原始输出：

```text
> hengxin-smart-image-frontend@0.2.69 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

国内生产范围设定 `VITE_RELEASE_SCOPE=domestic`、`VITE_ACCESS_MODE=frontend`、`VITE_API_URL=/api/v1`、`VITE_BASE_URL=/`，执行 `pnpm exec vite build --mode production --outDir ../../output/review-r6-domestic-dist`，退出码 0。工具截断了大量文件清单，下列为返回的原始起止片段，不冒称完整日志：

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 4911 modules transformed.

(!) outDir D:\Work_Project\hengxin-smart-image\output\review-r6-domestic-dist is not inside project root and will not be emptied.
Use --emptyOutDir to override.
...
✓ built in 33.08s
```

这不是从提交 Git 字节构建的正式包；本 reviewer 未独立重跑全量前后端、海外生产构建、真实模型和生产验收。

## 候选外发布辅助脚本 · 补充只读检查

这些脚本位于被忽略的 `output/domestic-studio-release-bin/`，不属于 candidateId，以下不是生产运行或安全通过证明。审查期间主 Agent 调整 `server_publisher_smoke.py`，将生产镜像 ID 的只读检查移至创建临时目录之前；下列针对修改后版本。未运行它们或执行生产操作。

- `build_committed.py:12-39` 固定 HEAD 并核对三范围包 manifest；实际 `scripts/release/intranet/package_release.py:73-117` 用 Git blob 哈希核验 archive 原始字节，`:125-141` 限制构建环境，`:234-247` 校验锁文件。前提是正式提交后再次确认 HEAD 与已批准快照一致，并保证运行的工作树打包器本身是已审版本；包构建脚本从工作树调用（`build_committed.py:23-26`），不能只凭包内 commit 推定调用器也来自 HEAD。
- `install_committed.py:15-47` 用 Git blob 校验工具树并以独占方式写新目录；`:57-72` 对路径做 root 所有权及写权限检查。`run_server_helper.py:11-30` 限定三个 helper 名，SSH 传输 `hengxin-smart-image/scripts/migration245/transport.py:15-29` 使用已知 host key、固定目标与主机名检查。但两个本地脚本在执行前均从**工作树**导入 `transport.py`（分别见 `install_committed.py:11-13`、`run_server_helper.py:7-9`），且 helper 自身不在候选中；实际运行前须核对这些文件及辅助脚本的确切哈希与本次检查版本。
- `server_activate_tools.py:26-59` 在既有 release 锁内检查空闲台账、基线及服务清单，原子替换 `current` 链接；异常时只尝试恢复该工具链接，没有回滚数据库或业务服务。风险前提：`:13-24` 在校验受控路径所有权的 `u.safe(root)` 之前就从目标目录导入 Python；manifest 也由同一目录提供，未自行证明等于提交的清单。应在运行前独立核对安装目录/所有祖先和文件权限、manifest 摘要及提交对应关系，不能仅以其自带 manifest 校验自身来建立信任。
- `server_publisher_smoke.py:14-17,22-35,37-56,87-97` 限定主机和候选目录、随机标记临时容器，使用无网络、只读根文件系统和隔离 `/var/tmp`，清理前核验标记；它不写正式数据库或重启正式容器。临时目录的建立和 `chown` 仍位于 `try/finally` 之前（`:26-35,58`），这些步骤中断会遗留临时目录；强制终止也不保证 finally 执行，应先核对自身标记和实际引用后清理，不得批量删。当前检查未验证生产 Docker 身份或运行结果。
- `server_installed_checks.py:24-43` 用私有临时目录、精简环境运行测试；`test_joint_studio_migration_linux.py:14-20`、`test_domestic_publisher_linux.py:17-24` 无显式测试数据库时跳过，因此这些跳过不能冒充真实数据库/发布身份通过。其 `smoke_docker.py:17-69` 会真实创建测试镜像和停止容器，并以随机 label、已知 ID 清理；`image_gc.py:101-123` 将待删除范围限定于传入的已知集合并排除当前、保留及容器引用。运行中断仍可能留下测试资源；前后 Docker 全量清单若受外部并发变化会使最终一致性断言失败，需要核实而不能按失败自动清理其他资源。
- `upload_and_stage.py:38-61` 校验本地哈希、通过独占方式上传，再对远程文件复算哈希及调用 `stage.py`；`scripts/release/intranet/stage.py:18-51,68-90` 先核验成员与清单，并在发布锁及台账门禁下登记。上传中断可留下部分 tar，stage 中断可留下未登记目录，前三组并非单个原子事务；重跑可能因文件已存在而拒绝。应只读核对三组实际文件、哈希、台账和引用后处理，不能覆盖或自动回滚生产。

辅助脚本审核时 SHA-256（以后若改变须重审）：

```text
CC16403D3F3AE80AC34B5A81B81A643F6302FB140D494B13DF766CE7C4ADDF02 build_committed.py
50E097CF5C6F16960F4776185A096DD78B5D04C7BF2FCDFA45C186B9F41442B3 install_committed.py
C2109E599997CBC4125EAA6AB2AB8EF137D314A7EC8E80C28BA023BA35076F2D server_publisher_smoke.py
C6C7EC61BC87BB3F17F47712E518F3484BA4F526E754091AADE4FDA511226C6A server_activate_tools.py
AD9546ACDA72BAF31A7296E52F7D59428DA7F3F7AFB1A8571C07FA9ACBC25B9F server_installed_checks.py
E6D69BB5AE5A7AD666331B71FA3B519F77D0E7398EDEE9AB5308EB6021C24A49 run_server_helper.py
8793E34EFF02042B73904AD9140706DED6569A11935746DC46CAA7C6157390E8 upload_and_stage.py
```

## Stage 2

**未执行。** Stage 1 存在 HIGH，没有系统执行代码质量、安全扫描、测试真实性全面审查及正式页面与邻居基准的实际视觉对比。上面的辅助脚本专项只读检查不构成 Stage 2 PASS。修复 H1 后重新固定候选、从 Stage 1 重新审查；不要调用 `review-approve` 为本候选登记通过。

复现后、主 Agent 开始修复前只读快照状态的原始输出：

```json
{"currentId": "071056415a3a73d61f60b9085d57156b03c612c8910164077ad349d95b478740", "reviewedId": "d3a967332ae14940e06e774849782af11917f8c7bc2e0902deee6d698edc3ce1", "approved": false}
```
