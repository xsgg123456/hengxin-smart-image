# 原生工作台独立审查 R1（2026-10-14）

- candidateId：`507b2e0b2d2536541d7b707338f1dbc140a4568ea83fce78188d844c99369d5d`。
- **Stage 1：FAIL（1 项 HIGH）。Stage 2：未执行。** 不得据本报告登记两阶段 PASS。
- 使用 `.agents/skills/code-review/SKILL.md`，遵循 `docs/HARNESS-REVIEW.md`。只审查、运行隔离验证及写报告；未修代码、未提交、未批准、未调用收费模型。
- 范围：送审时全部 Git diff/untracked 源码，即海外 studio 后端、runner、清理兼容、0015 迁移、对应测试、正式工作台前端/API/Markdown/轮询、0.2.32 包版本与锁文件、新发布脚本和打包脚本；需求以 Product-Spec.md:1100 最新迭代、DEV-PLAN.md 最后迭代及 docs/NATIVE-STUDIO-RELEASE-20261014.md 为准。
- 快照：独立执行 `review-status` 时 `currentId` 与本 candidateId 完全相同，`approved:false`。报告发现 HIGH 后主 Agent 已通知开始修复；本报告只覆盖上述旧快照，修复内容必须重新 prepare、从 Stage 1 重新审查。
- 报告落盘后再次实查：当前内容已变为 `14d6220c8f1837761a243f663ed4dbbcb1a937583d61d18aafd2e46b63f1a670`，仍 `approved:false`。该修复中快照不在本轮结论覆盖范围内。

## Stage 1 阻断问题

### HIGH S1-01：明确草稿/中间文件仍会被收入正式图片和归档

**需求原文**（Product-Spec.md:1106）： “临时图、草稿、试验图、中间文件不显示、不归档，不做候选区”；“Markdown正文中的图片也遵守同一交付门禁”。

**位置**：`hengxin-smart-image/backend/app/overseas/studio/delivery.py:18`、`:26`、`:36`。

`references()` 仅检查当前 inline token 和最近标题。普通非交付说明没有保存在后续上下文，因此 Markdown 常用的空行分段可使“草稿，暂不交付”失效；词表还漏掉 Spec 明确要求的“中间文件”。两种最终答复都能收取图片：

```markdown
## 中间文件
![预览](/work/a.png)
```

```markdown
这是草稿，暂不交付。

![预览](/work/a.png)
```

**独立实跑**：创建临时隔离 work/home、一个真实 12×13 PNG，使用合法当前 session、`turn_completed=True`、`error=None`，调用生产 `collect_delivery()`，不是仅测试正则。上述两例均得到 `accepted=["/work/a.png"]`、`warnings=[]`；正式交付对照组也得到同样结果。输入满足真实 CLI 完成事件和本轮文件前提，不依赖异常状态或越权路径。

原始输出（JSON 的 Unicode 转义保留工具原文）：

```text
{"final_text": "## \u4e2d\u95f4\u6587\u4ef6\n![\u9884\u89c8](/work/a.png)", "accepted": ["/work/a.png"], "warnings": []}
{"final_text": "\u8fd9\u662f\u8349\u7a3f\uff0c\u6682\u4e0d\u4ea4\u4ed8\u3002\n\n![\u9884\u89c8](/work/a.png)", "accepted": ["/work/a.png"], "warnings": []}
{"final_text": "## \u6b63\u5f0f\u4ea4\u4ed8\n![\u6210\u54c1](/work/a.png)", "accepted": ["/work/a.png"], "warnings": []}
```

**实际影响链**：`studio/execution.py:88` 收取并上传，`:120` 写入 `Picture`；`queries.py:51` 返回鉴权图片 DTO；`frontend/src/views/overseas/studio/studio-markdown.ts:36` 将已收取 `sourcePath` 映射成可加载图片；`StudioTurns.vue:12` 提供选图；`studio/service.py:93` 可按 SKU 归档。后续鉴权正确也不能纠正“草稿被当作正式交付”的分类错误。

**修复验收**：非交付声明须覆盖其关联图片，包括空行、标题层级、说明在图片前后等常见 Markdown 结构；明确重新进入正式交付后应允许真正成品。新增收取层与真实 worker→DTO/归档或等价集成回归，证明非交付图既不进入 `Picture`，也不能在正文或图组中加载。不得通过修改用户原文或强制交付话术掩盖问题。

既有 `tests/test_studio_formal_delivery.py:50` 仅验证“草稿”标题，再切至“正式交付”标题，没有覆盖上面两种可达排版。本次已有 35 项专项全通过仍能复现该缺陷。

## Stage 1 逐项核对

下表中的“匹配”仅针对该条代码和所列隔离证据；整阶段仍因 S1-01 不通过。路径前缀 `backend/`、`frontend/` 均位于 `hengxin-smart-image/`。

| Spec/审查项 | 结论 | 代码与验证证据 |
|---|---|---|
| 普通消息原样；首轮仅指定一句人设 | 匹配 | `backend/app/overseas/studio/execution.py:47`、`:63`；`schemas.py:9` 不 trim 原文；`tests/test_overseas_studio_conversations.py:40` 验证两轮精确字符串，包括前后空白。独立专项通过。 |
| 仅主动选附件/Skill；不拼商品背景/数量/步骤 | 匹配 | `studio/service.py:51` 只读取附件/引用 ID，`:63` payload 无商品背景；`execution.py:50`、`:65` 仅选中项追加路径；`overseas/execution/materials.py:17` 无 Skill 时不复制包。测试 `test_overseas_studio_execution.py:74` 校验原始附件。 |
| CLI 隔离与权限保持 | 匹配 | `execution.py:38` sandbox 参数；`backend/app/execution/workspace.py:54` 既有隔离；`studio/queries.py:14` 统一 task.read/design 授权；`router.py:16`、`:36` 新接口接同一身份/数据库依赖。`test_overseas_studio_transcript.py:43` 含撤权后 403。 |
| 公开 assistant 全文、多消息、更新、顺序持久化 | 匹配 | `studio/transcript.py:15`、`:41` Text 字段保存快照；`queries.py:92` ID 顺序分页；`studio-transcript.ts:4` 同轮 item 原位替换、跨轮隔离。`test_overseas_studio_transcript.py:43` 长文/代码/更新，独立专项通过。 |
| 公开 reasoning 摘要与工具状态；不输出任意 stdout/内部 reasoning | 匹配 | `transcript.py:30` 仅公开 reasoning.text；`:35` 工具只返回固定标签，未知类型丢弃；同一专项用 SECRET command、PRIVATE_STDOUT、hidden_reasoning 验证均未进入 API。 |
| Markdown、代码、链接及 HTML 禁执行 | 匹配；图片分类除外 | `studio-markdown.ts:4` html:false；`:12` 图片只接受批准映射；`:18` 本地/自定义协议下载链接无授权时文本化；`tests/studio-markdown.test.ts:8` 原始 HTML 与危险链接；图片上游错误见 S1-01。 |
| 近实时回显、半行 UTF-8、不重复、分页/重连 | 匹配 | `backend/app/execution/process.py:64` 0.2s monitor，`overseas/execution/runner.py:115` 调 poll；`transcript.py:54` 持久 byte offset，不消费未完成行；`queries.py:92` 500+1 分页；`use-studio.ts:34` 活跃轮 1000ms、`:42` 循环拉页；独立测试覆盖半 UTF-8、重读、502 条分页。 |
| 默认展开执行过程，终态可折叠 | 匹配 | `StudioTranscript.vue:4` details open 绑定 running；`StudioTurns.vue:29` 状态映射；浏览器 `studio-native.browser.mjs:81`、`:124` 验证运行/终态。截图 running-markdown.png 显示执行消息展开。 |
| 保留历史滚动、隐藏/卸载停止、恢复补齐 | 匹配 | `StudioTurns.vue:38`、`:41` old DOM 判断底部；`use-studio.ts:62` visibility abort/恢复、`:105` 卸载释放；`tests/studio-native.browser.mjs:92` 历史位置保持与底部跟随；既有 `overseas-studio.test.ts` 覆盖隐藏/卸载与轮询。 |
| 失败/停止已收文字保留，图片失败不清文字 | 匹配 | `runner.py:152` 异常 final_poll；`execution.py:90` 图片故障只产生 warning；`transcript.py:50` 独立持久化；`test_overseas_studio_transcript.py:95` 三类失败/取消/crash，`:125` collector 错误，独立专项通过。 |
| 本轮最终答复、完整完成、归属/有效性、无目录发现图 | 部分实现 | `delivery.py:58` 要求完成、无 error、有 final；`:69` 只迭代引用；复用 `backend/app/execution/final_delivery.py:53` 当前工作区/会话边界及历史文件拒绝。`test_studio_formal_delivery.py` 未引用、输入/Skill/外部/其他会话/坏图/去重用例通过；草稿语义门禁失败见 S1-01。 |
| 草稿/临时/试验/中间图不显示不归档，正文同门禁 | **不匹配 HIGH** | `delivery.py:18`、`:36`，完整复现及正式图库/正文/归档影响见 S1-01。 |
| 无在途才能开始新对话；旧历史/材料/归档保留 | 匹配 | `service.py:73` 仅新建 Conversation；`:26` 非 TERMINAL 一律阻止，包括 uncertain/未知状态；`queries.py:63` 全 task 历史；`execution.py:19` 以 conversation UUID 使用独立 CLI home。`test_overseas_studio_conversations.py:17` 保留历史/素材、不同 home、无 resume。 |
| 新对话首轮与会话分界 | 匹配 | `execution.py:62` 新 session 才人设；`StudioTurns.vue:5` 与 `:19` 分界，包括尚无新轮次；`OverseasStudio.vue:20` 新对话确认、保留说明；`use-studio.ts:76` 成功才清草稿与引用。 |
| 并发/幂等；未知响应必须原 key 核实 | 匹配 | `service.py:16` actor/task lock、请求指纹与 replay；`:73` active 检查；`use-studio.ts:10` sessionStorage、`:65` pending、`:79` 未知响应保留；`tests/test_overseas_studio_postgres.py:15`、`:33` 真实 PG 同 key 并发和 send/reset 锁竞争，提供日志 66 passed；浏览器 `:128` 断网后同 key 重试。 |
| 预览、引用修改、SKU 归档保持 | 匹配；收取分类除外 | `StudioTurns.vue:14` 预览/修改；`use-studio.ts:102` 引用追加；`studio/service.py:93` SKU 属于本任务、已归档冲突保护、protect 独立归档；`test_overseas_studio_conversations.py:57` 新多会话删除时归档仍保留。 |
| 0.2.31 上传限制、Skill 中文名/描述、刷新保持 | 匹配 | `frontend/src/api/overseas/studio.ts:44` 20 MiB 与原格式；`StudioSkillSelect.vue:3` 名称/描述；`use-studio.ts:53` 手动 spinner、自动静默合并读取；`overseas-studio.test.ts:30` 及 `studio-refresh-skills.browser.mjs:46`；提供刷新浏览器 PASS。北京时间公共格式化相关代码无本轮改动，全量前端回归无失败。 |
| 390px 与桌面、引导真实性 | 匹配（隔离浏览器范围） | `OverseasStudio.vue:5` 新会话、刷新和归档均有真实 handler；`:13` 设计要求与 Ctrl+Enter 对应 send。独立目视 running-markdown.png、mobile-confirm.png；390px 确认按钮/文字未越界，桌面代码/链接/工具播报可读；浏览器 `:144` 断言容器和按钮边界。未冒充真实生产登录验收。 |
| 海外 0014→0015、存量保持、重复迁移、国内0028不变 | 匹配（隔离 PG） | `backend/migrations/overseas/versions/0015_studio_transcript.py:10` 添加字段/表/索引、保留旧 reply 并回填一次；`:56` 禁 downgrade；`tests/test_overseas_studio_migration.py:16` 真 0014 数据每列比较、再执行 upgrade、第二会话、国内库快照比较。提供 PG 66 passed，无 skip。 |
| 0.2.32 打包、同安装测试镜像迁移、备份排空、失败只前进 | 匹配（实现/隔离测试）；生产待执行 | `scripts/release/package-overseas.py:16`、`:181` 版本/schema；`native-studio-runtime.py:52` image_id 验安装凭据、`:79` 同 identity migrate；`native-studio-deploy.py:50` 关闭入口→停 API→双轮排空→备份→迁移→切换；`:103` failure，`runtime.py:118` 失败重关入口、保存真实 schema；禁止重放/降库。实际 build 指向 `overseas-deploy.py:29` 生成 INSTALL_TEST_IMAGE_ID。重点发布测试提供 73 passed。 |

### Spec 漂移/未实现

- 未发现超范围新增业务页面或候选图区域。新增 Conversation 接口、Transcript 表/API、sourcePath 映射与发布脚本分别对应 Product-Spec.md:1102–1107；`studio/router.py:32`、`:37`，`models.py:64`，`native-studio-deploy.py:19`。
- 已确认未完整实现项只有 S1-01 正式交付分类。生产切换、真实页面验收属于审查后发布步骤，尚未执行，不计当前已验收；本报告不授权提前宣称部署成功。

## 验证与编译证据

独立运行（退出码 0）：

```text
.venv/Scripts/python.exe -m pytest -q tests/test_studio_formal_delivery.py tests/test_overseas_studio_transcript.py tests/test_overseas_studio_conversations.py tests/test_overseas_studio_execution.py
...................................                                      [100%]
35 passed, 2 warnings in 6.31s
```

两条 warning 为既有 Starlette/httpx 弃用及 anyio BlockingPortal 弃用，不是本轮断言失败。以上并不覆盖 S1-01 的两个缺失输入；独立追加复现结果已列出。

已实际读取主 Agent 提供的原始日志，其输出摘录如下；未把主 Agent 的全部测试误记为 reviewer 重跑：

```text
# output/native-studio-backend-full.log
2038 passed, 188 skipped, 15 warnings in 281.45s (0:04:41)
# output/native-studio-backend-pg-20261014.log
66 passed, 2 warnings in 48.13s
# output/native-studio-frontend-tests.log
ℹ tests 356
ℹ pass 356
ℹ fail 0
ℹ skipped 0
# output/native-studio-frontend-final-typecheck.log
> hengxin-smart-image-frontend@0.2.32 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
# output/native-studio-build.log
✓ built in 37.70s
# output/native-studio-browser.log
PASS: incremental pages/updates, full messages/long text, safe Markdown and delivery images, failure/cancel/reload, scroll follow/history, draft selection persistence, idempotent new conversation, 390px
# output/native-studio-release-tests.log
Result: 73 passed, 26 subtests passed in 3.01s
Exit code: 0
Result: 1 failed, 242 passed, 1 skipped, 117 subtests passed in 13.78s
Exit code: 1
```

编译日志没有错误诊断，主 Agent 报告 typecheck/build exit 0；typecheck 原始日志仍包含 pnpm 字段配置弃用警告。发布全目录不是全绿：`scripts/release/test_release_native.py:100` 的旧 overlay 断言失败，提供说明为既有 HEAD 不一致，新发布链不执行该旧断言。未将该失败写成通过。

## Stage 2

**未执行**：按照 skill，Stage 1 出现 HIGH 即停止，不进行代码质量、安全扫描或邻居页面实际视觉对比，也不出具它们的 PASS。下一轮必须对新快照从 Stage 1 开始；主 Agent 不得将本报告用于 `review-approve`。
