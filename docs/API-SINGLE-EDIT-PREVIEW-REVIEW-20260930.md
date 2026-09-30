# API 单张修改隔离预览审查

- candidateId：`100299e8ed22c0b71810c26fd67925f62b0343e1abcdfbfa51f7e6970b5e7a06`
- 范围：`hengxin-smart-image/frontend/preview-single-edit/` 的 7 个新增文件，仅本地交互预览；不审查正式产品功能完成度，不批准生产发布。
- 依据：`docs/API-SINGLE-EDIT-PREVIEW-20260930.md:3` 的范围和第 1～4 条；使用 `.agents/skills/code-review/SKILL.md`。
- Stage 1：PASS（预览实现）；Stage 2：PASS（本轮新增代码）。网络采集及在线基准限制见下文，不能解释为这两项已实测通过。
- 审查开始与结束执行 review-status，currentId 均为上述 candidateId；未发现快照变化。未修改代码、未提交、未写 clean。

## Stage 1 · Spec Compliance

| Spec 条目 | 结论与证据 |
| --- | --- |
| 1. 复用弹窗及现有画布，保留 1380px、左画布右意见、工具与预览 | 完整实现。`preview-single-edit/Preview.vue:5` 使用 `min(1380px, 96vw)`，与 `src/views/hengxin/api-image-edits/RealRevisionDialog.vue:2` 相同；`:10` 实际引用 AnnotationEditor，后者 `src/views/hengxin/components/annotation/AnnotationEditor.vue:5` 引用 AnnotationCanvas。独立打开 3016 页面，实际看到框选、画笔、缩放、左图右意见；1280×720 截图中标题、底部关闭及预览按钮均可见。 |
| 2. 双模式，说明、示例、提示词和确认类型联动；草稿独立保留 | 完整实现。`preview-single-edit/Preview.vue:7`、`:10`、`:23`～`:29`。浏览器将图片草稿改为“审查图片草稿”，切到文字模式看到原文字示例，再切回图片模式仍为“审查图片草稿”；确认窗口显示“本次基于 V1 · 图片修改”，文字模式显示“本次基于 V1 · 文字修改”。草稿映射证据：`src/views/hengxin/components/annotation/annotation-drafts.ts:10`～`:14`。 |
| 3. 图片示例包含居中、透视、修复；文字沿用既有提示词；可展开、空意见阻断、标注可选 | 完整实现。`preview-single-edit/Preview.vue:24`～`:29`；文字函数直接引用 `src/views/hengxin/api-image-edits/text-edit-prompt.ts:3`。浏览器实际展开两种完整提示词，图片包含清除旧位置残留、修复背景规则；文字包含原模板的文字长度及布局规则。0 处标注、有文字时成功进入确认；清空意见后显示“请填写修改意见，说明标注位置需要如何调整”。校验实现在 `annotation-drafts.ts:17`～`:22`，调用在 `AnnotationEditor.vue:87`。 |
| 4. 截图背景与素材、演示确认、不联网生图、头尾按钮可见 | 实现符合隔离预览范围。`preview-single-edit/style.css:2` 使用截图背景；`phone.svg:1` 为包含 PNG 的 800×800 SVG 视口，非服务器原始图片；`Preview.vue:11` 明示素材来源和不会生成。`:30`～`:35` 仅取本地静态素材并显示消息。浏览器确认后显示“已演示「图片修改」提交；未调用生图接口，未创建新版本。”**网络面板未单独采集，不能宣称“浏览器无业务请求”已实测**；源码检查无业务请求，主 Agent 已明确接受该预览验证限制。 |
| 独立入口，无生产路由接入 | 完整实现。`preview-single-edit/main.ts:1`～`:6` 独立挂载，`vite.config.ts:5` 使用独立 root；review-status 的 changedFiles 仅含本目录 7 个新增文件，无生产组件修改。 |

部分实现/未实现：未发现本范围内缺失的实现。验证缺口：网络日志未采集。无 HIGH 问题。

## Stage 2 · Code Quality

- 代码质量：PASS。`Preview.vue:14`～`:35` 有明确模式联合类型、组件引用类型和加载失败处理；新增源码均不超过 300 行，无 any。草稿、画布与文字模板直接复用。`style.css:1`～`:4` 压缩排版可读性一般，但属于本次短期预览，不作为阻断。
- 安全扫描：PASS（范围内静态检查）。新增文本文件搜索 eval、innerHTML、dangerouslySetInnerHTML、密钥前缀及敏感 VITE 变量，未命中；`phone.svg:1` 是单一 SVG/image/base64 PNG，无脚本或外链加载；`Preview.vue:31` 的 fetch 仅使用构建导入的本地素材 URL；`:35` 无业务调用。`vite.config.ts:8` 服务只绑定 127.0.0.1。
- 测试真实性：核心交互和空输入故障路径由 reviewer 在实际 3016 浏览器复验，不以 mock 测试充数；本轮没有新增自动化测试。未测试上传损坏文件、所有画布交互和移动端，这些不能据本报告宣称全面回归通过。
- Spec 漂移：未发现。独立页面、示例、提示词及演示消息均对应预览范围；`Preview.vue:10` 复用的上传标注属于既有编辑器能力。
- 视觉检查：实际检查本地页面截图，蓝色按钮、灰色说明、左大图右意见及白色圆角弹窗与现有源码和用户截图基准相符；`style.css:1`～`:3`、`AnnotationEditor.vue:99`～`:105` 为证据。已打开线上邻居页面，但其停留在“正在连接工作区…”，**未完成在线页面并排渲染对比**；仅完成本地渲染与用户截图、现有组件源码对照，不宣称像素级一致。截图素材自带红框和底部引导，不是新增实际标注，符合截图素材预览的限制。
- LOW：全量注册 Element Plus 导致约 982 kB JS chunk（`main.ts:2`、`:6`），仅本地隔离预览可接受；如转为正式入口应重新评估。

## 独立编译结果

执行：前端目录 `npx vite build --config preview-single-edit/vite.config.ts`，exit code 0。原始输出：

```text
npm warn Unknown project config "package-manager-strict-version". This will stop working in the next major version of npm. See `npm help npmrc` for supported config options.
npm warn Unknown project config "manage-package-manager-versions". This will stop working in the next major version of npm. See `npm help npmrc` for supported config options.
vite v7.1.7 building for production...
transforming...
✓ 1434 modules transformed.
rendering chunks...
computing gzip size...
../output/single-edit-preview-build/index.html                        0.38 kB │ gzip:   0.31 kB
../output/single-edit-preview-build/assets/background-BH70RQVS.png  331.25 kB
../output/single-edit-preview-build/assets/phone-B02-NmFU.svg       459.14 kB │ gzip: 335.94 kB
../output/single-edit-preview-build/assets/index-C6KMp451.css       345.74 kB │ gzip:  47.82 kB
../output/single-edit-preview-build/assets/index-ASDqw4p1.js        981.87 kB │ gzip: 324.42 kB

(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
✓ built in 5.97s
```

此为 Vite 构建通过，不等同于独立 TypeScript 类型检查或正式产品验收。由主 Agent 使用同一 candidateId 登记审查凭据。
