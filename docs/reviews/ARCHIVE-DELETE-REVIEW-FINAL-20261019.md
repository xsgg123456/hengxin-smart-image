# 海外成品库整套删除：独立两阶段复审

- 最终 candidateId：`a38ead4468645a66de9c79d2b468c7044028a40f195da4aa483231d2b717de66`。
- Stage 1：**PASS**。Stage 2：**PASS**。未发现本次范围内的 HIGH / MEDIUM 问题。
- 初始交接 candidateId 为 `8fb79ac6d666bca2458fc6c0b1b5209b7b0cf1f723c607cfbb5276d9d42e1598`。审查中主 Agent 还原 Vite 自动删除的 17 个组件声明；已重新检查 `frontend/src/types/import/components.d.ts` 对 HEAD 无差异，review-status 当前 ID 等于上述最终 ID。本结论只对应最终快照。
- 使用 `.agents/skills/code-review/SKILL.md`；范围为当前全部本功能 tracked diff 与 untracked 业务实现、0019 迁移及前后端测试。需求依据 `Product-Spec.md:1221` 至本节结束，以及 `docs/ARCHIVE-DELETE-IMPLEMENTATION-20261019.md:3`。不把整个产品的其它 Spec 章节宣称为本次重新验收。
- 下列源码路径均相对 `hengxin-smart-image/`。审查未修改业务代码、未提交、未写 clean；批准凭据由主 Agent 登记。

## Stage 1：逐项需求对照

|需求|结果与证据|
|---|---|
|仅超级管理员入口，服务端独立拒绝越权|完整实现。`frontend/src/views/overseas/OverseasArchivePage.vue:41` 根据 task.delete 显示操作，`OverseasPortal.vue:7` 传权限；`backend/app/overseas/archives/deletion.py:55,73,81` 分别校验删除、状态、确认权限。`backend/app/overseas/permissions.py:24` 只有 super_admin 获得 task.delete。HTTP 四角色拒绝测试在 `backend/tests/test_overseas_archive_deletion.py:124`，真实浏览器亦四角色均 403。|
|删除前二次确认、品名/数量、不可恢复及原任务保留说明|完整实现。`frontend/src/views/overseas/OverseasArchiveDelete.vue:5` 至第 9 行显示完整确认内容；第 40 行取得最新确认摘要后开窗。`frontend/tests/overseas-archive-delete.test.ts:44` 检验取消零提交及确认。实际双端截图文字与按钮可读。|
|确认仅读元数据，缺失/损坏图片也能清理|完整实现，旧 HIGH 关闭。`backend/app/overseas/archives/deletion.py:81` 只授权、加锁、初始化历史元数据、计算 token，不调用 protect/read/store；`frontend/src/api/overseas/archives.ts:63` 与 `OverseasArchiveDelete.vue:44` 使用该接口。`backend/tests/test_overseas_archive_deletion.py:24` 分别覆盖 missing、corrupt、missing_asset，且先删源 Task、强制 store.open 抛错，仍确认并清空剩余对象。真实浏览器脚本 `frontend/tests/overseas-archive-delete-real.browser.mjs:85` 附近实际预删 MinIO 图片后走页面确认并通过。|
|真正删除全部归档对象、Asset、Event、Archive；历史归档可删|完整实现。`backend/app/overseas/archives/cleanup.py:31` 同时查资产及该 archive UUID 命名空间孤儿对象；第 76 行先删除并重新列举/stat 验证，第 58 行删除业务行，第 103 行才置 deleted。`backend/tests/test_overseas_archive_deletion.py:53` 覆盖 Task 存在/已删除、孤儿对象、SQL 行与字节实际消失。|
|保护源任务、原始资料、其它成品及共享对象|完整实现。`cleanup.py:20,31` 校验精确规范化命名空间、来源 Task、五类源对象及其它归档引用；检测到不安全引用则整批在删除前失败。`test_overseas_archive_deletion.py:161,236` 检验不安全路径、共享源引用及其它成品字节/记录存活；真实浏览器比较前后完整对象清单及 tasks.items。|
|持久请求与最小回执，不以软删除替代|完整实现。`backend/app/overseas/archives/models.py:51` 仅 archive_id/status/error/时间，无产品信息及 FK；`deletion.py:55` 在 HTTP 返回前提交请求，`cleanup.py:103` 实际清理后提交完成。`backend/migrations/overseas/versions/0019_archive_deletion.py:11` 与模型一致。|
|失败安全错误、重试入口、刷新/重启后恢复|完整实现。`cleanup.py:106,113` 持久失败及扫描 deleting；`backend/app/overseas/execution/outbox.py:21` 接入维护循环。`OverseasArchiveDelete.vue:30,35,66` 恢复轮询、失败重试与生命周期清理。`test_overseas_archive_deletion.py:99,208,227` 覆盖部分物理失败、SQL 失败与无效 remove；真实 MinIO 停机/启动后重试完成。没有把“请求已接受”当成功。|
|清理期间禁止追加、保护复制、图片读取与下载|完整实现。`backend/app/overseas/archives/snapshot.py:28` 统一检查回执；`backend/app/overseas/archives/service.py:89` 拦截读取；`backend/app/overseas/studio/service.py:113,140` 拦截追加/完成；页面 `OverseasArchivePage.vue:9,19` 取消封面读取并禁用下载。HTTP 与真实浏览器检查 409。|
|Task→Archive 锁序，阻止 Task 清理把归档重新复制或 detach|完整实现。`deletion.py:28` 锁 Task 后重读 Archive/Receipt；`backend/app/overseas/tasks/cleanup.py:40,58` 在两阶段分别拦截。真实 PG 测试 `backend/tests/test_overseas_archive_deletion_postgres.py:46,67,88,116,142` 覆盖删除优先、追加优先、并发 worker、Task detach 及两事务之间收到删除请求。|
|最新快照、内容变化重确认、重复点击/请求幂等|完整实现。`deletion.py:18` 对 Archive、Asset、Event 的字段生成内容 hash，第 55 行锁内验证，已有回执复用；`OverseasArchiveDelete.vue:21,53` 防重复提交、冲突清空确认。`test_overseas_archive_deletion.py:137` 验证相同数量但 asset/event/versions 改动均 409；前端测试第 64、94 行覆盖冲突与双击。|
|成功后刷新列表、总数与页码，关闭详情/预览|完整实现。`OverseasArchivePage.vue:42,50` 关闭对应视图、刷新并回退空页；`frontend/tests/overseas-archive-ui.test.ts:95` 断言页码请求 [1,2,2,1]、总数归零、删除中无封面和下载。|
|保留源任务并解除归档状态，可再次归档|完整实现。`cleanup.py:58` 清 Picture.sku、恢复 studio/generating、增加 task.version、使旧归档/完成请求 hash 失效；`archives/service.py:24` 重新检查重放 hash。`test_overseas_archive_deletion.py:53,181,194` 验证 studio、completed、legacy 的重新归档及旧 key 409。|
|验收使用隔离数据，不破坏生产现有成品|完整实现于测试范围。`frontend/tests/overseas-archive-delete-real.browser.mjs:9` 校验 localhost 与一次性 runner 命名，结果 modelCalls=0。HTTP、PG、浏览器覆盖取消、成功、权限、重复、冲突、物理删除、故障恢复、来源两态及并发；没有生产删除验收声明。|

部分实现：无。未实现：无。Spec 漂移：未发现产品范围扩展；新增 preview、DELETE、状态 API、receipt 表与维护接入分别服务元数据确认、真实删除、恢复和幂等（`archives/router.py:43`、`models.py:51`、`execution/outbox.py:21`）。retention fixture 是测试前提修正，无生产行为变更。

## Stage 2：质量、安全、视觉与测试真实性

- 结构与类型通过：新增删除请求、清理及 UI 分开，分别 94、119、75 行；所有送审源代码/测试文件均不超过 300 行。`frontend/src/api/overseas/archives.ts:4,63` 有状态联合类型及运行时返回值校验；未新增 any。API 请求 schema 在 `backend/app/overseas/archives/deletion.py:13` 禁止额外字段并严格限制 token。
- 安全扫描通过：检查本次新增及修改实现，无硬编码凭据、eval、innerHTML、前端 SECRET/TOKEN 环境变量或字符串拼接 SQL。`cleanup.py:72` 使用 SQLAlchemy 条件删除，`cleanup.py:20` 限定对象路径，第 106 行仅保存固定安全错误；DELETE 在 `archives/router.py:43` 沿用 browser_request 防跨站保护，且 `deletion.py:56` 在成员权限锁内复核。
- 故障测试并非仅顺畅纯函数：`test_overseas_archive_deletion.py:99,208,227` 真实操作存储 fixture 后注入失败并断言字节及数据库状态；真实浏览器通过 Docker 停止隔离 MinIO 触发存储故障，恢复后核对完整 key 集。PG 线程使用 Event 控制锁持有顺序，而非用 SQLite 假装并发锁验证（`test_overseas_archive_deletion_postgres.py:46`）。
- retention 修正有效：`backend/tests/test_api_cli_conversation.py:45` 原 fixture 明确将 sync_credentials 替换为 no-op；`backend/tests/test_api_retention.py:34` 新增无害 auth.json 前提，使第 55 行仍能真实检验清缓存保留文件。原清缓存、保留会话、续聊断言未删除；未以此测试证明真实认证成功。reviewer 独立运行该文件与删除专项共 31 项全部通过。
- 迁移与回归检查通过：`backend/tests/test_overseas_archive_deletion_migration.py:9` 对真实数据库重复 upgrade，检查精确最小列集、无 FK 及国内库不变；`test_overseas_database.py:73,170` 的版本/表清单随 0019 更新；`test_overseas_configuration.py:202` 仅将新增合法路由加入允许列表，没有放宽任意路由。
- 视觉对比通过：reviewer 用 view_image 打开 `output/playwright/archive-delete/confirm-desktop.png`、`confirm-mobile.png`，并打开邻居 `output/playwright/delete-skills-final-review/delete-confirm-desktop.png` 实际渲染截图比较。两者沿用相同白色圆角对话框、黄色危险说明、右侧取消/红色确认操作。当前邻居源码 `frontend/src/views/overseas/OverseasTaskDelete.vue:5` 与新组件第 5 行均使用 `min(560px, 94vw)` 与同类 ElDialog/ElAlert/ElButton。390px 新截图对话框左右保留边距、文案换行、按钮未裁切。邻居历史截图多一个输入区；当前源码已无该输入，不以历史字段作为本次需求。
- 未发现需要阻断的质量或安全问题。浏览器服务在复审中已关闭，视觉结论基于打开的实际渲染产物及源码对照，没有声称 reviewer 另起浏览器重演。

## 验证原始输出与边界

reviewer 独立执行：

```text
.venv/Scripts/python.exe -m pytest tests/test_overseas_archive_deletion.py tests/test_api_retention.py -q
...............................                                          [100%]
31 passed, 2 warnings in 11.19s
```

两条 warning 为既有 Starlette TestClient/httpx 与 anyio BlockingPortal 弃用提示。其余下列输出来自主 Agent 保存的日志，已读取而非凭口述接受：

`output/archive-delete-frontend-tests.log`：

```text
ℹ tests 301
ℹ suites 0
ℹ pass 301
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8912.594
```

`output/archive-delete-frontend-build.log`：

```text
> hengxin-smart-image-frontend@0.2.41 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4640 modules transformed.
dist/assets/index.vue_vue_type_style_index_0_lang-DcTx83F6.js                             814.14 kB │ gzip: 275.63 kB
dist/assets/index-Dw0eNVU9.js                                                             963.71 kB │ gzip: 307.80 kB
✓ built in 36.01s
```

构建有 pnpm 配置字段弃用 warning，非本次引入。最终恢复组件声明后主 Agent 另报 typecheck exit 0；上述原始构建日志不是恢复后新构建，不混写时间顺序。

`output/archive-delete-pg-tests.log`：

```text
6 passed, 2 warnings in 9.00s
```

`output/playwright/archive-delete/result.json`：五组 checks 覆盖四角色拒绝、桌面/390px取消、预先缺图、一次提交/刷新/读图阻断、真实 MinIO 停机重试及资源隔离；`errors: []`、`modelCalls: 0`。脚本在所有断言完成后才写最终 result.json（`frontend/tests/overseas-archive-delete-real.browser.mjs:124` 附近）。

**全 Linux 后端套件仍在执行，不能据本报告宣称全套通过。** 本次最后读取 `output/archive-delete-backend-tests.log` 进度 64%，未见 F，但这不是最终结果。原先 PID 1/subreaper 诊断由主 Agent 提供，本 reviewer 未独立重演旧容器失败；--init 后最终汇总须由主 Agent 核实，若有失败应继续定位，若涉及代码修改必须重新固定并复核快照。本报告两阶段 PASS 是上述审查范围的结论，不替代最终全套回归和部署验收。

## 交接

主 Agent 可用最终 candidateId 和本报告登记审查凭据；完成交付前必须核对 review-status，收齐全 Linux 后端最终结果。未验证生产部署，不授权使用生产现有归档做破坏性测试。
