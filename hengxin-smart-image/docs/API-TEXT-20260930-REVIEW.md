# API 文案操作与创建预填 · 独立审查报告

日期：2026-09-30。审查者：独立 code-reviewer；遵循 `.agents/skills/code-review/SKILL.md` 与 `docs/HARNESS-REVIEW.md`。

**最终 candidateId：`12ad6b443c35833b41e2ceb6a8cc1477fc1b514e12503975e6af2309f552aaf7`。Stage 1：PASS；Stage 2：PASS。无未解决 HIGH / MEDIUM / LOW 问题。**

## 范围及快照变化

范围为本轮全部 Git 工作区变更：API 修复文案、单张文字修改、创建预填、共享画布可选参数、0022 迁移及相关测试/验证脚本；源需求为根目录 `Product-Spec.md:3`、`DEV-PLAN.md:3`、`Design-Brief.md:3` 的 2026-09-30 段。历史需求只核对本次涉及的兼容边界，不将未开发的其他阶段计作缺陷。

最初派发 `156c195d9171380031efbc8a2cea144cf0b75306a7e22727be14946ab6e06555`；审查中主 Agent 两次变更浏览器测试：先增加窄屏截图前加载等待/滚动，形成 `4f78ca6df4df47f02452cdc7e3609e0e42ace06458b85e0810dfd6d8582a3664`；再修复圈注自动化的动画时序，形成上述最终 candidate。审查者重新阅读 `scripts/api-text/browser.mjs:110` 的加载与有限动画等待、`:137` 的窄屏等待，并在最终快照独立重跑脚本成功。报告仅批准最终 candidate，不把中间结论直接转用于其他版本。

以下 `backend/`、`frontend/` 路径相对 `hengxin-smart-image/`；根目录文档、`scripts/`、`output/` 相对仓库根。

## Stage 1 · Spec Compliance：PASS

### 完整实现

| 源需求 | 结论及实现证据 | 验证证据 |
| --- | --- | --- |
| `Product-Spec.md:7` 用户主动一键修复，不输入/圈选 | 完整。`frontend/src/views/hengxin/api-image-edits/RealTaskDetail.vue:31`、`:89` 提交 `text_repair`、空意见及当前版本，无新增弹窗。 | 独立浏览器真实 Vue 页面点击；`scripts/api-text/browser.mjs:76` 检查载荷、未知确认及禁重复。 |
| 同条：当前成品为图1、上传原图为图2、不附共用素材 | 完整。`backend/app/modules/api_image_edits/versions.py:107` 按类型构造冻结 fileIds；`execution.py:45` 读取冻结图片；`relay.py:106` 按序序列化。 | `backend/tests/test_api_text_operations.py:30` 真正经过 RelayClient 序列化，断言图数、顺序和解码后的图片字节。 |
| 同条：增强版通用修复原文 | 完整。`backend/app/modules/api_image_edits/text_prompts.py:8`、`:12` 内置修复策略。 | 审查者直接比较 `text_repair_prompt.txt` 与 `output/text-repair-v2-test/prompt.txt`，统一换行并去首尾空白后 `repair_prompt_baseline_equal= True`。 |
| `Product-Spec.md:8` 文字修改仅当前成品及可选标注，文字必填，保留上传标注 | 完整。`versions.py:107`；`schemas.py:27`；`frontend/src/views/hengxin/api-image-edits/RealRevisionDialog.vue:3`、`:59`；`components/annotation/AnnotationEditor.vue:19`、`:87`。 | 单图/双图载荷、空白/无文字/非法类型拒绝见 `test_api_text_operations.py:30`、`:96`；PNG/JPEG 上传限制见 `test_api_image_revision_guards.py:45`。浏览器走纯文字、框选意见、PNG 导出上传。 |
| 同条：前端完整保护提示预览，后端重新权威构建 | 完整。`RealRevisionDialog.vue:74`；`AnnotationEditor.vue:31` 折叠显示完整提示；`versions.py:120` 不采用客户端 prompt。 | `frontend/tests/api-image-text.test.ts:11` 精确比对前后端模板并验证 `$&` 等用户字符不被替换解释；后端 `test_api_text_operations.py:43` 发送恶意删保护 prompt，断言仍是服务端模板。 |
| 同条：保留字体/布局/光照/非文字，清残留、去标注，长文案不缩字改版，不能虚构溢出判定 | 完整。`backend/app/modules/api_image_edits/text_edit_prompt.txt:1` 至输出段逐项包含固定规则；前端 `text-edit-prompt.ts:2` 与后端契约一致。代码未新增自动溢出判断。 | 模板全文检查与契约测试；`AnnotationEditor.vue:31` 明确不承诺框外像素逐一不变。真实模型效果不在本轮通过结论内。 |
| `Product-Spec.md:9` 类型、输入、提示词、基版本冻结；同图互斥、幂等/未知确认 | 完整。`versions.py:88` 校验幂等摘要；`:105` 状态与基版本检查；`:117` 冻结；`frontend/.../item-command.ts:9` 原 key 原 command 重放；`RealTaskDetail.vue:81` 区分两类待确认。 | `test_api_text_operations.py:30`；`frontend/tests/api-image-operations.test.ts`；独立浏览器真实提交未知路径验证相同 key 和载荷。 |
| 同条：队列/处理中/重试/失败可见，失败保旧，成功新版本，查看下载恢复 | 完整。复用 `versions.py:42`、`:66`、`:134`、`:147`；`presentation.py:26`、`:61`；`RealTaskDetail.vue:27`；`RealVersionDialog.vue:23`。 | `test_api_image_revision_execution.py:18` 连续失败、保留旧版本/邻图、同输入重试；`test_api_image_versions.py:30`、`:108`、`:138` 版本、ZIP、恢复和权限；浏览器失败 V1、恢复执行后 V2、历史类型。 |
| 同条：历史无 kind 和旧冻结请求兼容 | 完整。`versions.py:26` 接受旧3/4图及无快照六参数；`:93` 仅缺少 kind/prompt 的旧请求允许旧摘要确认；`presentation.py:29` 回退旧语义。`models.py:128` / `migrations/versions/0022_api_text_operation_kind.py:12` nullable 字段，降级保留证据。 | `test_api_image_revision_snapshot.py:109`、`:138`；`test_api_image_revision_execution.py:18`；`test_api_text_operations.py:104` 验证旧原文/纯标注幂等确认，异载荷拒绝、全新纯标注拒绝；SQLite 迁移实际通过。 |
| `Product-Spec.md:10` 始终 source_id 锚点、动态尺寸、Lanczos PNG、当前/历史/下载/ZIP一致 | 完整。`execution.py:30`、`:66`；`dimensions.py:12`、`:29`；成品只在 `execution.py:125` 发布，下载读取版本同一文件。 | `test_api_text_operations.py:30` 用790×1500/800×800原图、500×600当前图、333×444模型返回，验证请求800×1520/1024×1024、最终源尺寸PNG、多轮和恢复；原尺寸专项也在独立68项回归内。 |
| `Product-Spec.md:11` 完整创建预填、可改可清空、已有草稿优先、提交框内值、与两类操作隔离 | 完整。`frontend/.../default-wallpaper-prompt.txt:1` 保留“输出像素宽高与图1一致”；`real-draft.ts:11`、`:13`、`:51`、`:79` 首次初始化/待确认覆盖/原框内内容/用户草稿复用。`preview-state.ts:24` 同步演示新任务。 | `frontend/tests/api-image-text.test.ts:11` 与原文文件逐字一致；`api-image-draft.test.ts` 新草稿/编辑/清空/重进/不同身份/恢复快照；独立浏览器实际路由切换后文本和空值保留。 |
| `Product-Spec.md:12` 与 `Design-Brief.md:3` 原布局、1380画布、按钮相邻且换行、不改CLI/不自动批量 | 完整。`RealTaskDetail.vue:30`、`:128` 相邻按钮、8px间距和wrap；`RealRevisionDialog.vue:2` 宽度min(1380px,96vw)；`AnnotationEditor.vue:41` 新参数保留旧默认描述。CLI调用 `components/annotation/CliAnnotationDialog.vue:3` 未改。 | 实际1440/1920/390视口，框选/纯文字/窄屏输入均可用；全量前端207项通过，包含共享画布与CLI回归；实际截图见下节。无自动触发器、批量入口或新CLI提示策略。 |

部分实现：无。未实现：无（本轮明确排除的收费模型效果验收不计入工程实现缺陷）。Spec 漂移：无；未增加额外业务页面/API/表，仅版本 kind 增量字段及需求内入口，证据 `schemas.py:32`、`models.py:128`、`RealTaskDetail.vue:31`。

## Stage 2 · Code Quality：PASS

- 结构/类型：本次变更的 `.py/.ts/.vue/.mjs` 文件逐个计数，均未超过300行；未增加 TypeScript `any`。API专用提示策略集中在 `text_prompts.py:1`，未污染CLI共享策略；`frontend/src/types/api-image-edits.ts:4` 用联合类型明确操作种类；兼容可选kind由 `frontend/src/api/api-image-edits-validate.ts:17` 验证。
- 安全：扫描业务增量及关联API/画布模块，未发现新增硬编码秘密、eval、innerHTML、危险HTML注入、客户端暴露密钥或拼接用户SQL。`backend/app/modules/api_image_edits/router.py:25`、`:135` 继续使用shared_resources依赖；`backend/app/modules/auth/permissions.py:13` 拒绝未登录/停用/非法角色。共享资源权限语义保持既有设计，不错误添加“仅作者可操作”。`versions.py:56` 验证任务/子项归属；`:111` 检查实际附件资格；`execution.py:46` 解码冻结输入后才调用上游。
- 测试真实性：`test_api_text_operations.py:30` 不是仅断言拼接函数，实际走受理、冻结、失败状态重试、RelayClient JSON、收图/PNG/版本/恢复；源、当前、返回尺寸刻意不同，能抓到锚点混淆。`test_api_image_revision_snapshot.py:67` 损坏输入阻止上游；`:109` 验证旧冻结策略不漂移。浏览器脚本 `scripts/api-text/browser.mjs:30` 拦截所有业务API、阻断非本地请求，使用真实Vue组件；不能被表述为真实模型效果验证。
- 已解决的测试问题：审查补拍邻居页面时发现圈注自动化偶发在弹窗动画中取坐标，导致未产生“标注1”。主Agent在 `scripts/api-text/browser.mjs:110` 增加等待加载和有限动画完成；审查者复核后以最终快照独立重跑exit0。该项是测试时序问题，未发现产品交互缺陷，不遗留LOW项。
- 实际视觉对比：审查者打开并截图既有换图记录页和本次详情/画布，人工检查 `output/playwright/api-text/review-neighbor-records.png`、`detail-before.png`、`annotation-edit.png`、`edit-narrow.png`。蓝色Element Plus按钮、白底圆角卡片、次级文字密度与邻居基准一致；修复与修改并排，窄屏可换行；桌面单画布左右分栏，窄屏上下滚动且底部按钮可见。代码证据为 `RealTaskDetail.vue:128`、`AnnotationEditor.vue:99`、`RealRevisionDialog.vue:2`。截图是隔离数据，未把图片占位素材视作模型结果。

## 独立执行及编译原始输出

审查者执行后端重点回归（文案、迁移、修订执行/保护/快照/版本/尺寸）、域权限测试、前端全量、类型检查、compileall、最终浏览器脚本。后端未配置独立PostgreSQL，因此本机迁移PG用例跳过；不宣称独立重跑了PG。主Agent提供的完整Linux回归日志和构建日志已实际读取，与本机专项区分记录。

独立重点后端输出摘要（原文）：

```text
68 passed, 1 skipped, 2 warnings in 9.20s
9 passed, 2 warnings in 2.13s
```

警告为现有 FastAPI TestClient/httpx 与 anyio BlockingPortal 弃用提示。独立前端全量输出（原文）：

```text
ℹ tests 207
ℹ suites 0
ℹ pass 207
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 3885.5846
```

独立类型编译原始输出，退出码0：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.

> hengxin-smart-image-frontend@0.2.13 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

独立 `backend/.venv/Scripts/python.exe -m compileall -q app`：退出码0，无标准输出。正式构建由主Agent执行，审查者读取 `frontend/build-latest.log:3` 与 `:428`，原始关键输出：

```text
> hengxin-smart-image-frontend@0.2.13 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4485 modules transformed.
✓ built in 55.84s
```

完整前置回归原始日志：`output/api-text-backend-full.log` 为 `1419 passed, 79 skipped, 15 warnings in 154.67s (0:02:34)`；`output/api-text-backend-final.log` 为 `39 passed, 2 warnings in 12.05s`。主Agent记录的独立PG专项见 `docs/API-TEXT-20260930-VALIDATION.md:9`，本审查不把该声明替代为审查者亲自运行的证据。

最终候选独立浏览器脚本退出码0，`output/playwright/api-text/result.json`：6组检查、`errors: []`、请求类型 `text_repair, text_repair, text_edit, text_edit`、`uploads: 1`；覆盖完整默认提示词/草稿、未知确认、失败保旧/重试、纯文字、圈注、历史、390px窄屏。审查补拍邻居页使用忽略目录中的临时脚本，未修改实现。

## 验收边界

本报告只确认当前快照的本地工程行为。没有提交、部署或调用收费模型；字体清晰度、杂色清理及布局保持的真实生成质量仍需单独效果验收（`Product-Spec.md:14`）。部署时需迁移0022并同步前后端。由主Agent使用最终 candidateId 与本报告路径登记两阶段PASS，禁止写 `.needs-review` 为 clean；后续代码变化必须重新固定并审查。
