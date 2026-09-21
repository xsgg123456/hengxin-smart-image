# 单张所见版本与圈注截图审查

日期：2026-09-21。独立 code-reviewer 使用 code-review skill。

- 最终 candidateId：`84d1beecb927d282f736e9d276c0c4a7cdb074a81c27eae995a0119a2bf1f866`
- Stage 1：PASS。
- Stage 2：PASS。
- 未解决 HIGH / MEDIUM：0。结论限定本次实现，不代表生产部署或真实付费模型效果验收。
- 范围：本轮全部未提交差异，包括 Product-Spec / CHANGELOG / DEV-PLAN / API-CONTRACT，以及 review-status 列出的 27 个前后端代码、迁移、测试文件。未重新验收产品全部历史功能。下列代码路径相对 `hengxin-smart-image/`，源需求文档相对仓库根。

## 快照与复核

首次候选为 `a8c8ee6b7fec734d1d6123329a99347cde84d7085cceb809b9aedeb0fad44713`。审查发现并反馈两项 MEDIUM，由主 Agent 修复：

1. 整套弹窗错误使用圈注截图示例，但没有截图入口。现 `frontend/src/views/hengxin/components/TaskDetail.vue:38` 按目标选择整套通用意见或单张圈注示例。
2. mock 接受已有结果却显式传 null 基础版本，与后端 422 契约不一致。现 `frontend/src/api/hengxin/mock-tasks.ts:146` 拒绝该输入，`frontend/tests/tasks.test.ts:24` 增加对应断言。

已读取修复差异及更新后的 114 项测试、构建输出。最终 review-status 返回 currentId 与本报告最终 candidateId 完全一致。旧候选结论不用于批准新快照；批准由主 Agent 使用 review-approve 登记，本 reviewer 未写 clean、未修改代码、未提交。

## Stage 1：Spec Compliance

依据 Product-Spec.md:81（FLOW-004）、:133（REQ-005 全部相关条目）、:342（AC-007/007A/007B），DEV-PLAN.md:3 本轮四步，Design-Brief.md:23 复用要求，以及 API-CONTRACT 最后一节。

| 条目 | 结论与证据 |
|---|---|
| 整套预览、单张查看与文字意见 | 完整实现。`frontend/src/views/hengxin/components/ResultCard.vue:1` 保留预览和版本选择；`TaskDetail.vue:8`、`:38` 保留整套/单张意见；无截图可提交，附件非必填。主 Agent 浏览器完成无图提交。 |
| 点击时冻结所见版本并显示 | 完整实现。`ResultCard.vue:11` 发出当前 picture；`TaskDetail.vue:97` 捕获版本；`frontend/src/views/hengxin/revision-session.ts:26` 复制版本；弹窗 `TaskDetail.vue:33` 展示缩略图及 V 号。独立浏览器看到“本次基于 V1 修改”。 |
| 后端版本归属、可用性、禁止静默换最新 | 完整实现。`backend/app/modules/tasks/revision_inputs.py:33` 查询目标槽并校验版本所属槽及文件，显式 null 与旧调用省略字段分别处理。`backend/tests/test_single_revision_inputs.py:41` 覆盖跨任务、跨槽、非法 ID、显式 null 与旧调用。 |
| 可选一张圈注、格式大小、预览移除替换、失败阻止提交 | 完整实现。`ImageUpload.vue:3`、`:20`、`:33`；`frontend/src/views/hengxin/use-image-upload.ts:33`、`:92` 单图替换/阻塞状态；`TaskDetail.vue:35`、`:42` 上传配置和提交禁用。后端 `revision_inputs.py:13`、`:47` 校验 ready/未删除/MIME/上传者/大小及后台上限。测试 `test_single_revision_inputs.py:59`、`:104` 覆盖非法材料。主 Agent 浏览器覆盖损坏 PNG、移除恢复、有效上传及替换仅一张。 |
| 修改底图为选定无标注成品，模板/素材辅助 | 完整实现。`backend/app/execution/materials.py:55` 按冻结版本读取 currentPath，`:73` 圈注独立目录；`prompts.py:20` 明确基础与辅助角色。`backend/tests/test_single_revision_materials.py:30` 构造实际不同的 V1/V2 字节，核对 V1 与圈注文件内容，不只核对标签。 |
| 圈注只定位、标记不复制、歧义不猜 | 输入协议完整实现。`backend/app/execution/prompts.py:25` 明确圈线、箭头、文字及界面不进入成品，无法定位时说明歧义；`:35` 禁止沿用历史截图/版本。测试 `test_single_revision_materials.py:57` 验证提示词。真实模型是否遵守尚未付费运行，不能宣称最终画面已验收。 |
| 本轮意见、基础、圈注保存；失败重试冻结 | 完整实现。`backend/app/modules/tasks/models.py:40` 持久引用；`service.py:112` 写入轮次；`queries.py:101` 返回展示；`revision_inputs.py:24` 重试复制原输入并拒绝篡改；`TaskDetail.vue:25` 展示记录。`test_single_revision_inputs.py:68` 覆盖跨操作者重试保留快照和显式更换 409。 |
| 同任务原 CLI 会话、指定 Skill 和范围 | 完整实现。`backend/app/execution/codex_runner.py:91` 读取原会话，`:134` resume；`materials.py:82` 校验冻结 Skill，`:34` 限定目标槽；`prompts.py:23` 明确只输出一张且覆盖技能初始批次要求。`backend/tests/test_revision_execution.py:60` 检查 resume 原 ID 及材料路径。未修改业务 Skill。 |
| 历史 V1 生成 V3、保留 V1/V2 和其他槽；失败保留当前 | 完整实现。`backend/app/modules/tasks/results.py:17` 限定目标，`:21` 失败不改 current，`:27` 最大版本号加一。`test_single_revision_inputs.py:16` 验证 V1/V2 保留、V3 追加及其他槽相同；前端 `tests/tasks.test.ts:10` 同步验证。 |
| 整套基于当前版本，查看历史不改下载归档 | 完整实现。`materials.py:55` 整套取各槽 current；`TaskDetail.vue:128` 归档、`:137` 下载取 currentVersionId；`ResultCard.vue:19` 只维护本地查看选择。 |
| 互斥、已受理重放、意见保留、无主管审批 | 完整实现。`service.py:70` 授权、`:80` 任务锁及锁后重放、`:89` 资格检查；`backend/app/modules/revisions/service.py:14` 活跃轮次互斥。`idempotency.py:10` 保持旧请求 hash 并纳入新字段，`:21` 重放原回执。`revision-session.ts:46` 冻结请求/键，`:66` 不确定状态保留输入。`frontend/tests/revision-session.test.ts:126` 丢响应后仍发送原版本/截图；无新增审批步骤。 |
| 草稿隔离与上传状态 | 完整实现。`revision-session.ts:20` 按身份和任务隔离、`:27` 按目标和基础版本隔离意见及截图；`:30` 保留上传数组引用。`tests/revision-session.test.ts:110` 验证隔离和引用相同，防止上传 watcher 误重置。 |
| 持久化迁移与文件引用保护 | 完整实现。`backend/migrations/versions/0013_revision_inputs.py:12` 可空外键兼容旧轮次；`backend/app/worker/cleanup.py:73` 锁定轮次表并保护圈注引用。独立 PostgreSQL 专项 2 项通过，见下方原始日志。 |

部分实现/未实现：本轮已约定的软件实现范围内无。真实生成画面、生产部署属于未执行验证范围，不以 mock 替代。

Spec 漂移：未发现新增无需求页面、接口或业务流程。新增引用字段、冻结标记、迁移及上传组件参数分别服务所见版本、圈注与旧调用兼容（`models.py:40`、`service.py:115`、`ImageUpload.vue:48`）。

## Stage 2：Code Quality

- 代码质量 PASS：本轮改动代码文件未超过 300 行；前端未新增 any。`revision_inputs.py:20` 集中输入冻结与校验；`revision-session.ts:46` 管理幂等状态；`use-image-upload.ts:64` 通过存活 entry 检查拒绝已移除上传的迟到回写，错误保留在失败条目。`git diff --check` exit 0，仅 CRLF/LF 提示。
- 安全 PASS：新增 UUID 字段使用 `business.py:236` 校验，ORM 条件查询；`revision_inputs.py:48` 检查附件上传者和限制；`materials.py:16` 限制读取大小并核对 SHA-256，输出路径由服务端固定组成。检查新增差异未发现硬编码密钥、动态 eval、HTML 注入或拼接客户端 SQL。`idempotency.py:27` advisory lock 参数绑定；迁移测试的动态 schema 来自 uuid4，并非用户输入（`test_revision_inputs_migration.py:20`）。
- 测试真实性 PASS：V1/V2 材料用不同真实字节断言（`test_single_revision_materials.py:43`），版本与范围通过实际业务受理/fixture 发布路径验证（`test_single_revision_inputs.py:16`），网络不确定和身份隔离通过状态层测试覆盖（`revision-session.test.ts:35`、`:51`、`:126`）。上传组件故障路径采用主 Agent 实际浏览器验收，未将纯函数测试声称为组件端到端测试。
- 视觉 PASS：reviewer 独立 CUA 打开本机 mock，实际查看 1280×720 单张弹窗、既有整套弹窗及模板库邻居页面。单张弹窗 560px，基础图 72px，内容高度限制 66vh（`TaskDetail.vue:29`、`:143`），取消/提交 footer 可见；白底、蓝色操作、灰色说明、圆角及 ElImage/ElInput/ElButton 与邻居一致。复用邻居 `TemplateEditor.vue:2` 的 ElDialog、`:21` 的 ImageUpload，无独立设计稿数值可另行比对。未刷新或改动主 Agent 演示页。

## 测试与编译证据

reviewer 阅读原始日志并核对测试源码；以下执行由主 Agent 完成，reviewer 未重复运行写入型测试。

`output/single-revision/backend-pg-tests-final.txt` 最终原始摘要：

```text
785 passed, 105 skipped, 15 warnings in 82.72s (0:01:22)
```

`output/single-revision/backend-pg-specific.txt`：

```text
tests/test_revision_inputs_migration.py::test_0013_preserves_old_rounds_and_enforces_input_foreign_keys PASSED [ 50%]
tests/test_cleanup.py::test_all_references_protect_even_deleted_parents[annotation] PASSED [100%]
======================== 2 passed, 2 warnings in 1.99s ========================
```

此前 PG 全量一次因 Windows 测试临时路径超过 260 字符失败；`backend-pg-tests.txt` 为 WinError 206。缩短 basetemp 后上述全量通过，代码未为此改变。105 条条件跳过仍保留，不能说全平台专项已执行。

`output/single-revision/frontend-tests.txt`：

```text
ℹ tests 114
ℹ suites 0
ℹ pass 114
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 2812.8493
```

`output/single-revision/frontend-build.txt`：

```text
vite v7.1.7 building for production...
✓ 4352 modules transformed.
✓ built in 41.77s
```

编译记录 `output/backend-single-revision-validation.md:14`：

```text
python -m compileall -q app migrations
exit 0
```

主 Agent 回报最终 `vue-tsc --noEmit` exit 0（成功时无 stdout）；前端最终生产构建日志已读取。现有依赖弃用警告保留。

交付边界：本机代码、mock 交互、fixture/材料/同会话回归和临时 PostgreSQL 迁移/清理通过；未部署生产，未执行付费模型返工，未实测最终模型图片中的圈注消除效果。
