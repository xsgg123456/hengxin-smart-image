# 国内 AI 工作台、成品库与联合发布独立审查 R9

## 结论、快照与范围

- **candidateId：`37ee6ac8e1329496a0e212d42d0834ae872845135fcb1e31733864dbd4b1e9d9`；Stage 1：FAIL；Stage 2：未执行。** 同视口下正式工作台的输入区和中窄屏会话头与用户确认的预览不一致，均为 MEDIUM；按照本项目对确认预览逐项匹配的标准，不能登记 Stage 1 PASS。已核查范围内未发现新的 Stage 1 HIGH；未穷尽的场景见逐项表，不等于证明不存在 HIGH。
- 范围：`Product-Spec.md:1-13` 的五工作台、空白对话、私人会话、附件及恢复、新品归档与国内共享、超管 Skills 管理、固定绑定及国内外隔离；`DEV-PLAN.md:1-36` 的联合迁移、故障恢复、大文件、归档完整性和响应式；`Design-Brief.md:1-3` 与用户确认的 `hengxin-smart-image/frontend/preview-domestic-studio/`。`backend/`、`frontend/` 以下均相对于应用目录 `hengxin-smart-image/`。
- 已读取 `AGENTS.md`、`.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、本轮 Spec/计划/Brief、预览、实现记录及 FINAL 至 FINAL-R8 报告。旧报告用于定位问题，不用旧结论代替本轮验证。审查开始及浏览器、测试完成后的只读 `review-status` 均为该 `currentId`、`approved:false`；本报告只针对这一内容快照。
- 隔离 PostgreSQL `127.0.0.1:35439/hx_studio_test` 使用随机 schema；真实 MinIO `127.0.0.1:35441` 使用测试凭据和随机 bucket。部分故障测试使用本机 HTTP 对象替身或内存存储；实际 FastAPI 路由通过 TestClient 调用。浏览器使用当前工作树的真实 Vue 与请求拦截夹具/模拟身份，不是真实后端登录、真实模型或生产。没有修改候选业务代码、访问生产、提交、批准或写 clean。

## Stage 1 · 不匹配

### M1 · 输入区尺寸未匹配确认预览

`Design-Brief.md:1-3` 指定确认预览为视觉基准。预览 `frontend/preview-domestic-studio/Workspace.vue:20-23` 与正式 `frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:17-25` 均为三行输入，但正式样式在 `frontend/src/views/hengxin/domestic-studio/workspace.css:8` 显式强制 `min-height:80px!important`。同一浏览器、相同页面数据结构及视口测量：

| 视口 | 预览输入容器 / textarea 高度 | 正式输入容器 / textarea 高度 |
| --- | --- | --- |
| 1920×911 | 148.5625px / 85.5625px | 145px / 80px |
| 1000×844 | 148.5625px / 85.5625px | 145px / 80px |

复现脚本 `output/playwright/review-r9-visual-compare.js`；截图 `output/playwright/review-r9-preview-1920.png`、`review-r9-formal-1920.png`、`review-r9-preview-1000.png`、`review-r9-formal-1000.png`。差异未阻止输入，归类 MEDIUM；不能称为像素一致。正式版移除预览专用提示和示例内容是需求要求，不算此项缺陷。

### M2 · 中窄屏会话头的换行和高度与预览不一致

预览会话头见 `frontend/preview-domestic-studio/Workspace.vue:15`，正式见 `frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:14`、`workspace.css:7-12`。同浏览器量测：

| 视口 | 预览会话头 | 正式会话头 | 正式操作位置 |
| --- | --- | --- | --- |
| 1920×911 | 54px | 54px | 三个操作同一行 |
| 1000×844 | 54px | 79px | 前两个操作一行，“查看成品库”另起一行 |
| 390×844 | 81px | 113px | 三个操作分三行 |

复现脚本 `output/playwright/review-r9-header.js`；截图见 M1 及 `output/playwright/review-r9-preview-390.png`、`review-r9-formal-390.png`。正式增加的“取回文件”对应 `Product-Spec.md:6` 的恢复要求，应保留；本项指出它加入后的布局差异，非要求删除该功能。模拟浏览器另验证 1000px 会话栏不遮挡输入与上传，390px 默认收起、抽屉可关闭和选择，输入草稿保留；不把视觉差异描述成操作完全不可用。

## Stage 1 · 逐项核查及边界

“所测通过”限定于列出的测试及环境；“部分”不是整项通过。未测试过的真实生产能力不标通过。

| 本轮需求 | 当前证据与状态 |
| --- | --- |
| 两个新品入口、三个替换入口、独立成品库和仅超管 Skills | 所测通过：入口配置 `frontend/src/api/hengxin/domestic-workspaces.ts:3-8`，菜单与角色 `frontend/src/router/modules/index.ts:12-30`，管理权限 `backend/app/modules/auth/permissions.py:7-8`、`domestic_studio/management_router.py:26`。本轮浏览器使用模拟身份逐一打开五个正式路由；服务端权限在隔离 PG 测试中检查，未作真实身份登录。 |
| 直接聊天、初始空白、无预填/自动发送 | 所测通过：`DomesticWorkspace.vue:15-29` 和共享组件的 `hideEmptyGuide`；本轮模拟 API 下空输入、无欢迎引导、未绑定禁发，脚本 `output/playwright/review-r9-workspaces.js`。M1/M2 为视觉不匹配。 |
| 多会话新建、切换、重命名、删除，源会话及文件仅创建人可读 | 部分：`backend/app/modules/domestic_studio/conversation_service.py:29-44,70-109`、`file_service.py:75-97`、`conversation_deletion.py:14-46`；隔离 PG/HTTP 覆盖跨成员拒绝、会话创建与删除，浏览器模拟切换、草稿隔离和删除。未穷尽每入口真实身份及并发矩阵。 |
| 用户实际姓名、时间在右，Codex 和时间在左、北京时间 | 部分：`backend/app/modules/domestic_studio/queries.py:22,84-92`、`frontend/src/views/shared/studio/StudioTurns.vue:6-7`；浏览器模拟姓名“张三”和 UTC 时间，显示北京时间 17:30 且用户位于右侧。未验证真实登录账户和所有时区边界。 |
| 输入、附件、连续对话、结果、单图及批量修改、停止和异常 | 部分：`DomesticWorkspace.vue:17-36,81-105`、`backend/app/modules/domestic_studio/turn_service.py:42-116`；隔离 PG 的逐图执行工作区/跨用户材料拒绝用例通过；真实 Vue 配模拟 API 完成单图标注、参考图、两图逐图意见、会话切换和两次发送，`output/playwright/review-r9-annotation.js`。未调用实际 Skill 或模型，不能据此声称真实生成、全部停止与异常链已验收。 |
| 部分文件保留和手动取回，不重新调用模型；进程未知时保留并发占用、只在原节点核实 | 部分：`backend/app/modules/domestic_studio/runner.py:66-83`、`recovery.py:39-76`、`recovery_files.py:190`；本轮恢复/执行定向测试及模拟浏览器的选文件取回通过，模拟 CLI 不等于真实模型；未穷尽节点故障时序。 |
| 上传、收取和归档不确定写入的凭据、迟到写与有界大文件 | 部分：`file_service.py:29-72`、`output_intents.py:13-61`、`archive_service.py:214-260`。本轮真实隔离 PG/MinIO 跑输出、归档、手动取回迟到 PUT 和 multipart 完成，以及 128 MiB 归档/64 MiB 输出；另跑进程被杀后真实 HTTP 存储替身迟到上传和 4096×4096 有效大 PNG 的真实 MinIO 原图预览/下载。`tracemalloc` 是测试 Python 堆，不是生产并发 RSS；未运行真实模型与全部 500 MB/多并发组合。 |
| 五入口各有教程，未提供时显示待补充 | 部分：`DomesticWorkspace.vue:3,33` 以入口名称显示教程及占位；本轮浏览器操作相机教程，其余入口共享组件，未逐个展开。 |
| 只有新品按产品名归档；产品替换后端拒绝 | 所测通过：`backend/app/modules/domestic_studio/policy.py:12-30`、`archive_service.py:124-125`；隔离 HTTP 用例验证 product 403，模拟浏览器验证三个替换页无归档按钮；并未枚举所有畸形请求。 |
| 归档为独立副本，其他国内成员可读，源私有，删除源会话不破坏副本 | 所测路径通过：`archive_service.py:38-53,164-207`、`conversation_cleanup.py:44-56`；本轮两成员、隔离 PG、存储替身和真实 FastAPI 验证跨成员私有源拒绝与删源后详情/图片/附件；独立探针还验证删源后 GET/HEAD/预览/缩略图及 304，见下文。对象内容被同长度替换时的非图片附件风险单列于下，不将其夸大为已证实的 HTTP 越权。 |
| 逐图参考、说明、公开过程、真实终态/错误和旧归档 | 部分：`archive_service.py:172-207`、`archive_edits.py:8-38`、`archive_queries.py:57-83`、`frontend/src/views/hengxin/domestic-studio/library.vue:11,37-44`、`archive-transcript.ts:4-6`。隔离 PG/HTTP 测试验证两图对应关系、源删后跨成员副本和伪造引用拒绝；浏览器模拟真实 Vue 显示去重后的中途消息、旧无 ID 消息、未知状态、失败和部分完成及两图说明。终态后端用例是直接设置 DB 状态，不是真实失败/取消/部分收取执行链。 |
| 成品搜索、来源、详情、删除、ZIP 和图片保护 | 部分：`archive_queries.py:24-54`、`archive_router.py:36-98`、`archive_deletion.py:16-45,79-102`；定向组覆盖搜索、权限、ZIP 字节、图片读取和删除；损坏清单/对象路径的专门测试与并发探针见下文。未穷尽所有真实存储故障。 |
| 仅超管 Skills 完整文件夹上传、校验、同名确认更新、启停、删除和 ZIP，不提供版本管理/在线编辑 | 部分：`management_router.py:77-163`、`frontend/src/views/shared/skills/SkillFolderUpload.vue:2-27`、`SkillFolderActions.vue:19-40`；本轮管理、发布器与引用/恢复相关测试通过，前端全量测试包含组件/ZIP。未独立用原生浏览器完成真实文件夹拖入、同名更新和 ZIP 落盘；未系统盘点所有界面漂移。 |
| 五入口绑定、上线为空、未绑定或停用不执行、后端防绕过及冻结 | 所测路径通过：`backend/migrations/versions/0033_domestic_studio_bindings.py:10-26` 仅建表不插绑定；`bindings.py:36-82`、`policy.py:33-51`、`turn_service.py:42-80` 处理并发、校验和冻结。隔离 PG 双连接及相关角色测试通过，模拟浏览器验证未绑定不可发送；未以真实 Skill 全链执行。 |
| 国内外身份、库、对象和队列隔离，旧国内及海外功能保持 | 部分：`domestic_studio/router.py:28-29`、`recovery_transport.py:4-14`、`scripts/release/intranet/domestic_studio_wiring.py:42-114`；前端全量及国内/海外范围构建通过。后端测试覆盖部分权限，未进行全部旧业务或真实跨业务部署验收。未配置 Redis 的一个隔离队列测试跳过，不计通过。 |
| 联合发布：进程/数据库屏障、排空备份、迁移、旧台账重入、前向恢复及安装身份 | 部分：`scripts/release/intranet/joint_studio_fence.py:26-60`、`joint_studio_engine.py:33-52,141-157`、`joint_studio_release.py:160-198`、`backend/migrations/env.py:39-47`；本轮隔离 Linux/PG 的进程锁、事务等待、备份恢复、旧台账重入、前向恢复及 publisher 相关 22 项通过。部分发布编排测试使用替身，未在真实生产 Docker/身份下安装、切换或核验。 |
| 确认预览及响应式、避免额外产品功能 | **不匹配：M1、M2。** 本轮实际对照相机工作台 1920/1000/390，未对五入口、Skills、成品库所有状态做完整数值对照；未完成全部新增页面/API/表漂移盘点。 |
| 构建、独立审查、中文提交、部署和真实入口 | **不通过：本轮 Stage 1 FAIL。** 下述为工作树构建和隔离测试；尚未登记两阶段 PASS，未提交、部署或真实入口验收。 |

## R8 归档校验与生命周期复核

- `archive_service.py:38-40,76-121` 校验快照摘要、全量文件清单、引用及 `object_key == archive_key(record, row.id)`；`archive_queries.py:47-54,86-91` 将详情与单文件统一到 `verified`；`archive_router.py:59-85` 的 GET/HEAD/预览/缩略图/条件请求和 ZIP 先取已校验文件行，`archive_deletion.py:79-95` 清理前也校验。`backend/tests/test_domestic_archive_integrity_pg.py:21-85` 的两组真实 FastAPI/隔离 PG 测试在归档后新增未归档私人附件，分别修改记录及连 manifest 一起重封，断言详情、GET、HEAD、预览、缩略图、条件请求、ZIP 为 503，追踪源文件未打开，损坏归档清理失败且源对象保留。本轮独立重跑通过。这是先模拟数据库损坏/篡改的条件，**没有证据表明普通 HTTP 用户可以修改数据库或对象存储**。
- 专项探针 `output/review-r9-archive-race.py` 让另一 PG 连接在校验返回后、`FileDelivery.capture` 前或 ZIP 使用文件行前提交指向源文件的修改。正在处理的 GET/ZIP 使用已加载的旧合法副本，随后新请求 503，追踪的源对象打开次数 0；同时验证坏清单删除失败、人工恢复后首次部分删除失败、重试完成且重复请求幂等，源资料保留。当前 GET 在 `archive_router.py:63-67` 先捕获不可变数据并关闭 ORM session；`row.kind` 已在校验时加载。此探针只覆盖所注入时序，不能证明所有可能的数据库或对象存储竞态。
- 合法源删除后的真实 FastAPI 探针使用第二国内成员：`GET=200 HEAD=200 thumbnail=200 preview=200 conditional=304 bytes=match`。正常大图的真实 MinIO 测试为直接调用路由处理函数后消费 ASGI response，非生产网络 HTTP；64 MiB ZIP 的测试对象存储为替身。
- **补充完整性风险，非已证实的 R8 私有路径绕过。** 当归档后的非图片附件在对象存储中被替换成同长度内容，`backend/app/overseas/attachment_delivery.py:20-28` 仅校验对象大小并直接流式返回，没有与 `FileDelivery.checksum` 比较。本轮独立探针观察详情和 GET 均 200，但封存 SHA-256 为 `10c832303eb295a91a89799aa5c10b4cbb4be82c44e18cc9553994adc8a2c36d`，实际字节为 `3fc14a5ad0906f2d3b1a2839a87dfa35be1b0219908665cc3e97a7fc8607eb31`。这是既有共享海外附件下载语义，需先发生对象损坏或被修改；本轮 Spec 明确要求复用既有逻辑，不能将此等同于普通用户可篡改、私有源被读取或无条件外部攻击。应将其列为下载完整性和故障测试盲区，由主 Agent 结合既有流式合同决定处理；不能宣称所有归档文件的实际字节都在 GET 前经摘要核验。

## 本 reviewer 独立执行的测试与编译原始输出

- 后端归档完整性/编辑/HTTP/会话/身份组（内存存储替身，隔离 PG；一个未配置隔离 Redis 跳过）：

```text
................s..................                                      [100%]
34 passed, 1 skipped, 1 warning in 24.05s
```

- 真实隔离 MinIO/PG 的归档大文件、输出/归档/手动取回迟到写与 multipart：

```text
......                                                                   [100%]
6 passed, 1 warning in 15.07s
```

- 上传进程被杀后迟到 HTTP 替身、真实隔离 MinIO 大图、逐图工作区隔离：

```text
.....                                                                    [100%]
5 passed, 1 warning in 19.46s
```

- 绑定/权限/轮次/恢复/上传组：`29 passed, 1 warning in 35.34s`；管理/发布器/引用/初始化/模拟 CLI 组：`41 passed, 1 warning in 41.15s`。这些分组有重叠，不将数字相加当作独立全量。上述警告均为 `fastapi.testclient` 使用 `httpx` 的 `StarletteDeprecationWarning`。未独立重跑当前候选后端全量。
- 隔离 Linux 迁移、进程/PG 屏障、发布器和编排定向组：

```text
......................                                                   [100%]
22 passed in 20.09s
```

- 独立并发/删除重试探针（初次从 `output` 收集时缺少测试 Settings 导致 collection error；显式设置本地测试 DATABASE_URL 与假 MinIO 凭据后重跑）：

```text
FILE_RACE=200 original; next=503; ZIP_RACE=200 archive copy; next=503; source_opens=0
.CORRUPT=delete_failed; REPAIRED_PARTIAL=delete_failed; RETRY=deleted; source_retained=yes; repeat=deleted
.
2 passed, 1 warning in 9.14s
```

  另两个探针分别输出 `SOURCE_DELETED GET=200 HEAD=200 thumbnail=200 preview=200 conditional=304 bytes=match`、`1 passed, 1 warning in 18.01s`，以及上文同长度对象损坏的 `detail=200 GET=200`、`1 passed, 1 warning in 17.41s`；后者的 PASS 表示故障现象复现，不表示完整性通过。
- 前端 `pnpm test` 原始汇总：

```text
ℹ tests 564
ℹ suites 0
ℹ pass 564
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 15331.3188
```

- `pnpm run typecheck` 退出码 0，原始输出：

```text
> hengxin-smart-image-frontend@0.2.70 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

- `VITE_RELEASE_SCOPE=domestic` 与 `overseas` 分别执行 `pnpm exec vite build --mode production --outDir ../../output/review-r9-{domestic,overseas}-dist --logLevel warn`，两次退出码均为 0。原始输出共同部分及对应警告如下；`--logLevel warn` 不输出成功模块清单：

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1

(!) outDir D:\Work_Project\hengxin-smart-image\output\review-r9-domestic-dist is not inside project root and will not be emptied.
Use --emptyOutDir to override.

[plugin vite:reporter]
(!) D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/views/auth/dingtalk-login.vue is dynamically imported by D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/core/ComponentLoader.ts, D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/core/ComponentLoader.ts, D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/routes/staticRoutes.ts but also statically imported by D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/App.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
```

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1

(!) outDir D:\Work_Project\hengxin-smart-image\output\review-r9-overseas-dist is not inside project root and will not be emptied.
Use --emptyOutDir to override.

[plugin vite:reporter]
(!) D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/views/overseas/OverseasTasksPage.vue is dynamically imported by D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/core/ComponentLoader.ts, D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/views/overseas/OverseasPortal.vue?vue&type=script&setup=true&lang.ts but also statically imported by D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/views/overseas/OverseasPortal.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
```

输出目录在项目外，工具提示不会自动清空；这是当前工作树构建，不能冒充审查后 Git 提交的正式包。

## 候选外上线辅助脚本 · 补充只读核验

`output/domestic-studio-release-bin/` 不在 candidateId。11 个 `.py` 本轮 SHA-256 均与 `docs/reviews/DOMESTIC-STUDIO-FINAL-R7-20261112.md` 所列一致，本轮另行读取调用链并在隔离临时目录重跑两个防篡改测试，输出：

```text
Tool verification: trusted tree passes; content, extra file, symlink, manifest and unsafe permissions rejected
Staged backend verification: valid tree passes; content, extra file, symlink, manifest and unsafe permissions rejected
```

`build_committed.py:12-18,22-59` 和 `install_committed.py:12-51` 使用当前 Git HEAD 与 Git blob；它们不会自行证明 HEAD 等于已获两阶段批准的提交，且辅助脚本、本地 `packages.json`、`installation.json` 自身均不在候选内。`run_server_helper.py:19-38` 依赖本地元数据提供的 manifest 哈希；`server_verify_tools.py:10-37`、`server_verify_candidate.py:10-39` 验证受保护路径、文件清单、链接、权限和内容。哈希一致只说明与 R7 检查的工具版本一致，不等于提交、包或远端状态已获验证。

`upload_and_stage.py:33-65` 检查已安装工具、包哈希并用 `wx` 独占上传，再 stage；上传、stage 和台账并非一个原子操作。`server_activate_tools.py:26-56` 受发布锁、空闲台账和运行基线约束，其异常中恢复工具链接不是业务或数据库回滚。`server_publisher_smoke.py:22-27,38-41,94-101` 用随机标签/临时路径，仅在核对自身标签后删除对应 Docker 容器及自身临时目录。`server_installed_checks.py:24-43` 的精简环境可能使需隔离 DB 的测试跳过，不能记为通过。本轮没有执行服务器操作；任何上传、stage、安装、冒烟或发布中断后须先只读核对已知路径、哈希、标签、生产台账及引用，再据实恢复，不覆盖未知资源或假称回滚。

## Stage 2

**未执行。** Stage 1 存在上述 MEDIUM 且未通过确认预览的严格对照。本轮没有系统完成代码质量、安全扫描、测试真实性全面审计、Spec 漂移盘点及正式页与邻居基准页面的实际对比；上述限定范围的测试真实性检查和候选外辅助脚本检查不能构成 Stage 2 PASS。主 Agent 修复后须重新 `review-prepare`，提供新 candidateId 并从 Stage 1 重审；本报告不能用于 `review-approve` 登记两阶段 PASS。
