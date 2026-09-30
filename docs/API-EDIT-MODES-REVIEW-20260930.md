# API 单张图片/文字修改互斥 · 独立审查

审查角色：code-reviewer；依据 `.agents/skills/code-review/SKILL.md`。范围限 Product-Spec.md:3 的本轮互斥需求及相关正式实现，不重新审查已批准的 preview-single-edit 基线，不包含生产发布或收费模型效果。

首次 candidateId：`cb9fdec781f178ac72b41f7385e3d3b4665c146c82f2797c76af0de325c6c320`。

最终 candidateId：`b8f3a7b80b3a78fc370183bdb22c13d393c47b8471cb69cedca05a5ccf577170`。审查者执行 review-status，currentId 与该编号一致。

最终结论：**Stage 1 PASS；Stage 2 PASS**。无未闭合 HIGH/MEDIUM 问题。由主 Agent 用上述最终编号登记 review-approve，本报告不批准首次快照。

审查中代码发生变化：API 弹窗新增专属高度、窄屏缩放按钮/画布分配样式；共享 use-annotation-canvas.ts 调整贴边既有手柄命中判断。已重新审查增量及 Product-Spec.md:15 补充验收条目，最终 390px 首笔稳定、16 组合和真实 CLI 专项回归通过。

下述路径除特别说明，均相对 `hengxin-smart-image/`。

## Stage 1 · Spec Compliance · PASS

| Spec 条目 | 核查结论与证据 |
| --- | --- |
| 同一画布、单选、默认图片、空意见 | 完整实现。`frontend/src/views/hengxin/api-image-edits/RealRevisionDialog.vue:4` 仅两项单选；`:8` 复用 AnnotationEditor；`:37` 默认 image_edit。`frontend/src/views/hengxin/components/annotation/annotation-drafts.ts:13` 初始意见为空。浏览器脚本 `frontend/tests/api-image-edit-modes.browser.mjs:60` 起实际打开生产组件验证。 |
| 两种模式的意见、标注、上传草稿隔离 | 完整实现。RealRevisionDialog.vue:49 的 key 包含用户、任务、图片、基版本、成品文件及模式；`:61` 切换时清理上传缓存；`:65` 保留未知请求持有附件。AnnotationEditor.vue:44、:64、:65 根据 key 读取草稿及上传图。浏览器覆盖两个模式往返后的意见、框选和上传图保留。 |
| 通用图片规则及独立文字规则、不能混合 | 完整实现。`backend/app/modules/api_image_edits/image_edit_prompt.txt:5` 不预设类型对象；`:8` 禁止改字。`text_edit_prompt.txt:2` 禁止图片修改要求；原文字样式、布局、局部修补、溢出保留规则继续存在。`image_prompts.py:4` 与 `text_prompts.py:5` 独立版本。互斥为软件契约与提示词约束，没有虚构语义分类或像素保真保证。 |
| 查看固定规则、预览模式/意见/完整提示词 | 完整实现。RealRevisionDialog.vue:13、:41、:42 与 AnnotationEditor.vue:31；前端模板与后端逐字一致由 `frontend/tests/api-image-edit-modes.test.ts:10` 及既有文字契约测试验证，用户 `$&` 等输入按字面替换。 |
| 后端单一有效类型及服务器固定提示词 | 完整实现。`backend/app/modules/api_image_edits/schemas.py:28` extra forbid、去空白，`:32` Literal；`:38` 空意见校验。`versions.py:121` 服务端按 kind 构建，未使用客户端 prompt。`backend/tests/test_api_image_edit_modes.py:15` 覆盖数组、混合值、额外 kinds、无效值和空意见，均 422 且不改周期；`:33` 覆盖跨模式锁及客户端覆盖失败。 |
| 当前成品＋可选标注，源图仅锚定尺寸 | 完整实现。versions.py:108 的 fileIds 首项是当前无标注成品，只有 text_repair 添加原图；`:111` 可选标注。`execution.py:31` 源图宽高计算请求尺寸。`backend/tests/test_api_text_operations.py:29` 参数化两种编辑模式/有无标注/方长图，真实序列化请求验证图片顺序、尺寸、多轮 PNG。 |
| 模式在预览准备、上传、提交、未知确认时冻结 | 完整实现。RealRevisionDialog.vue:38、:39 锁定控件与 setter；`:84` 在上传前捕获 kind/version/prompt。AnnotationEditor.vue:48 同步上报 preparing 或 previewOpen，`:95` 确认使用已准备内容。浏览器验证预览、上传与未知响应期间单选禁用。 |
| 冻结请求、重试、旧请求兼容 | 完整实现。versions.py:118、:123 保存基版本、kind、policyVersion、prompt、fileIds；`:27` 旧 snapshot 原样读取；`:95` 旧无 kind/prompt 幂等确认；`:136` 手动重试不重建快照。RealRevisionDialog.vue:55 恢复未知类型与基版本，`:73` 使用 frozen.input；`item-command.ts:11` 拷贝并持久化原载荷。后端 modes 测试:49 修改模板后重试仍读原快照；text_operations 测试:109 覆盖升级前未知请求及旧 annotation-only 确认。浏览器刷新后请求体/幂等键完全相等。 |
| 历史与处理中类型标签、原修复入口 | 完整实现。`frontend/src/types/api-image-edits.ts:5` 新增图片标签并保留文字/修复/历史 fallback；`frontend/src/api/api-image-edits-validate.ts:17` 接纳 image_edit。`RealTaskDetail.vue:30`、`RealVersionDialog.vue:23` 使用共享标签；`backend/app/modules/api_image_edits/presentation.py:29`、:64 返回版本/快照类型。text_repair 模板和入口未改。 |
| 同图在途锁、幂等、冲突、旧图及 PNG | 完整实现。versions.py:92、:106、:129 保留幂等、状态与基版本检测和收图周期；旧 result_id 在新图发布前保留。后端定向 42 项通过，含真实 wire/生成结果本地解码校验；不将模拟上游视为模型效果。 |
| UI 与既有页面一致、窄屏可用 | 完整实现。最终桌面及390截图已查看，1380px 双列大图、蓝色按钮与 CLI 邻居一致；390px 模式控件换行、意见区内部滚动、底部操作可达。RealRevisionDialog.vue:2、:106 的样式仅作用于 API 包装层；AnnotationEditor.vue:101 保留共享布局。原画布浏览器脚本16组合通过。 |
| 贴边既有手柄可操作，图外禁止新建 | 完整实现。`frontend/src/views/hengxin/components/annotation/use-annotation-canvas.ts:108` 先识别真实已有 mark 的 move/resize 命中；`:115` 仅对新建标注施加起点图界限制；`:193`、:199 仍调用 clamp 的 moveMark/resizeMark。`annotation-model.ts:55`、:76 保证移动/缩放结果在图内。原浏览器脚本未放松断言，包含长图390px贴边手柄用例并通过。 |

部分实现/未实现：无。Spec 漂移：本轮增加要求的模式、模板、DTO、可选事件和验收中发现的共享手柄命中修复，未新增独立画布、接口、表或 CLI 编辑规则。

## Stage 2 · Code Quality · PASS

- 命名与类型：RealRevisionDialog.vue:37 使用两值联合类型，DTO 使用已有 ApiOperationKind；新增生产文件均小于 300 行。模板重复属前后端预览/执行一致性契约，由测试逐字核对，不是两套编辑逻辑。
- 错误与资源：RealRevisionDialog.vue:62、:92、:98 处理上传清理、异步过时代次与错误展示；AnnotationEditor.vue:96 释放 URL 并复位可选事件，原 CLI 不订阅该事件。
- 安全扫描：对变更生产文件扫描 eval、dangerouslySetInnerHTML、innerHTML、VITE 秘密变量、绝对用户路径、密钥特征及 any，未命中。提示词在 pre 文本插值展示，未引入 HTML 执行或动态 SQL。服务器模板构造证据见 versions.py:121。
- 测试真实性：新增后端测试通过 HTTP TestClient 走 schema、幂等、持久化和执行输入；text_operations.py:75 断言实际 relay HTTP body，并在 :85 解码结果验证尺寸及 PNG。浏览器使用真实 Vue 组件和 HTTP 客户端，本地 fixture 截获外部调用，未知响应以网络 abort 触发；不是以手写页面替代实现。其限制是未验证收费模型语义质量。
- 视觉证据：已查看最终 `output/playwright/api-image-edit-modes/editor-1920.png`、`output/playwright/annotation-workspace/790-1500-390-rect.png` 和本轮真实 CLI 邻居 `output/image-edit-cli-regression/cli-preview.png` 实际渲染，确认共享蓝色按钮、白底圆角、左右布局及预览形式，390px 保留可见拖动手柄和提交按钮。
- 故障闭环：首次390px首笔 CTM e 从133.75变146，API专属布局修复；随后贴边手柄不响应，修复 use-annotation-canvas.ts:108 的命中顺序。最终原断言通过，未用改断言掩盖故障。旧 inline-annotation 整脚本因过时 pre 单元素选择器失败，不计通过；CLI 改用只抽取实际CLI流程的隔离专项，并独立核对脚本真实导航、交互与请求断言。

## 实际验证与原始输出

审查者独立运行后端三个本轮测试文件：

```text
..........................................                               [100%]
42 passed, 2 warnings in 6.55s
exit_code: 0
```

两个 warning 为 Starlette TestClient 的 httpx 与 anyio 兼容弃用提示，不是测试失败。独立前端新增测试：

```text
✔ 图片模板与后端一致，通用规则和文字规则互斥，用户输入原样拼接 (1.2313ms)
✔ 图片未知请求确认始终复用原类型/提示词/标注，不能被文字请求替换 (17.1277ms)
ℹ tests 2
ℹ pass 2
ℹ fail 0
exit_code: 0
```

审查者独立执行 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`：原始 stdout 为空，`exit_code: 0`。实施者前端全量日志 `output/image-edit-frontend-tests.log` 原始摘要：

```text
ℹ tests 209
ℹ pass 209
ℹ fail 0
ℹ skipped 0
```

最终构建日志 `output/image-edit-build.log` 原始摘要：

```text
✓ built in 28.26s
```

主 Agent 最终前端全套执行返回 typecheck/test/build 均退出0；类型检查 stdout 为空。Vite日志的既有体积等提示不隐去，完整原始输出保留在上述日志。

API模式浏览器 `output/image-edit-browser.log` 原始输出：

```text
API_IMAGE_EDIT_MODES_BROWSER_PASS [
  '两种意见、直接标注和上传标注草稿隔离并保留',
  '图片真实API请求与未知响应重开确认不改变类型、提示词、标注和幂等键',
  '文字真实API请求不携带图片模式意见和标注',
  '1920/1280/600视口提交操作可见可达'
]
```

共享画布本轮原脚本回归 `output/image-edit-annotation-regression.log` 原始输出：

```json
{"passed":true,"cases":16,"checks":"首笔/后笔/意见/滚动/模式切换无跳动；100%、滚轮锚点、空格/中键平移、blur取消、输入空格"}
```

该16组合实际在API入口执行；脚本含CLI fixture定义不能当作执行了CLI。补跑 `output/image-edit-cli-regression.mjs:78` 实际导航任务中心、选择历史V1，并验证框选画笔、平移、上传无意见拒绝、预览原尺寸、完整意见及未知确认冻结。`output/image-edit-cli-regression.log` 原始输出：

```json
{
  "passed": true,
  "checks": [
    "CLI真实任务入口指定历史V1下载、混合标注与原尺寸导出、完整编号意见、冻结历史版本及同key/body重试且仅上传一次"
  ]
}
```

证据数据为同目录 checks.json，审查者已读取脚本与请求断言、查看本轮CLI预览截图。后端全量 1350 passed/174 skipped 来自实施者记录，本审查独立复跑的是上述 42 项；跳过项不算通过。工程验收通过不等于真实模型语义修改效果已验收；未执行收费生成、提交或部署。
