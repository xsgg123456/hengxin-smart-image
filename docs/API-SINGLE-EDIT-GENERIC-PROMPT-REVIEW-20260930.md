# API 单张修改通用提示词增量审查

- candidateId：`e319fcea28534942bb5fae099b2da9b7bbc134b5724c866df7ef7e2d7bcfc3a2`。
- 范围：仅 `hengxin-smart-image/frontend/preview-single-edit/Preview.vue` 与 `image-edit-prompt.ts`；本地隔离预览，不是生产功能验收。
- 依据：`docs/API-SINGLE-EDIT-PREVIEW-20260930.md:6`、`:7`（第 2、3 条）；其余条目沿用 `docs/API-SINGLE-EDIT-PREVIEW-REVIEW-20260930.md` 基线。本次使用 code-review skill。
- Stage 1：PASS。Stage 2：PASS（增量源码与独立构建范围）。
- 开始和结束 review-status 的 currentId 均等于本 candidateId；changedFiles 仅为上述两文件，未发现审查期间代码变化。报告由主 Agent 登记，不写 clean。

## Stage 1 · Spec Compliance

下列路径均相对 `hengxin-smart-image/frontend/`。

| 条目 | 结论及源码证据 |
| --- | --- |
| 通用于不同图片，不含示例对象及固定目标位置 | 完整实现。`preview-single-edit/image-edit-prompt.ts:3`～25 明确由用户决定对象、位置、效果；操作约束、局部融合、标注及输出规则没有手机、摄像头或居中等示例要求。 |
| 两种模式初始意见为空，草稿分别保留 | 完整实现。`preview-single-edit/Preview.vue:11` 按模式传 draft-key，脚本不再预填；`src/views/hengxin/components/annotation/annotation-drafts.ts:10`～14 按 key 缓存，新草稿 general 为空、marks 为空。 |
| 未填意见也能查看固定模板 | 完整实现。`preview-single-edit/Preview.vue:9`、14～17 的独立弹窗无意见校验前置，35 按模式选模板；文案说明占位内容来自用户输入。 |
| 完整提示词组合实际意见；文字模式沿用现有模板 | 完整实现。`preview-single-edit/Preview.vue:24`、34～35；`image-edit-prompt.ts:27`～28 通过回调替换占位符，保留用户输入字面内容；`AnnotationEditor.vue:31` 展开实际 prepared.text 组合结果。 |
| 空意见拦截，标注可选 | 完整实现。`Preview.vue:11` 传 marking-optional 与 require-text；`AnnotationEditor.vue:87`、88 允许无标注文件，`annotation-drafts.ts:19`～22 检查实际意见、长度及各标注说明。 |
| 模式说明及确认类型联动 | 完整实现。`Preview.vue:8`、11、30～35；修改草稿、说明、完整提示词和固定模板按同一 mode 选择。 |

部分实现、未实现、HIGH 问题：未发现。Spec 漂移：未发现，查看模板入口对应第 3 条。第 1、4 条未因本次增量改变：`Preview.vue:5`、11～12、36～41 保留现有画布、素材加载与演示消息。

## Stage 2 · Code Quality

- 代码质量：PASS。`Preview.vue:27`～35 使用明确模式联合类型和计算属性；42 行，模板模块 29 行；图片模板及组合函数职责明确，无 any。替换回调（`image-edit-prompt.ts:28`）避免用户输入中的替换特殊字符被解释。
- 安全静态扫描：PASS。两文件搜索 eval、innerHTML、dangerouslySetInnerHTML、敏感 VITE 变量、密钥前缀、绝对用户目录均未命中；`Preview.vue:16` 使用文本插值，36～41 保留本地素材请求及演示消息，没有新增业务请求。
- 测试真实性：独立 Vite 构建和 diff 检查通过；本次按委托只审源码，没有重新实测浏览器、真实生图或上传故障。主 Agent 提供“初始意见为空、弹窗展示通用模板”浏览器观察，属于外部交接证据，不冒充 reviewer 实测。继承基线中的网络日志、画布回归和在线视觉对比限制。
- UI：`Preview.vue:9`、14～17 复用 Element Plus 按钮和弹窗，文本可换行并限高滚动。此次没有新增设计稿；未独立打开邻居页面，不宣称像素一致或完成全面视觉回归。
- LOW：继承全量 Element Plus 引入造成的大包体警告，本次构建 JS 983.38 kB；仅隔离预览，不作为阻断。
- 文档备注：`docs/API-SINGLE-EDIT-PREVIEW-20260930.md:12` 的旧验证记录仍描述“示例草稿”，属于基线历史验证，不能用作本次空草稿验收证据。

## 编译结果

reviewer 在前端目录执行 `npx vite build --config preview-single-edit/vite.config.ts`，exit code 0。原始输出：

```text
npm warn Unknown project config "package-manager-strict-version". This will stop working in the next major version of npm. See `npm help npmrc` for supported config options.
npm warn Unknown project config "manage-package-manager-versions". This will stop working in the next major version of npm. See `npm help npmrc` for supported config options.
vite v7.1.7 building for production...
transforming...
✓ 1435 modules transformed.
rendering chunks...
computing gzip size...
../output/single-edit-preview-build/index.html                        0.38 kB │ gzip:   0.31 kB
../output/single-edit-preview-build/assets/background-BH70RQVS.png  331.25 kB
../output/single-edit-preview-build/assets/phone-B02-NmFU.svg       459.14 kB │ gzip: 335.94 kB
../output/single-edit-preview-build/assets/index-C6KMp451.css       345.74 kB │ gzip:  47.82 kB
../output/single-edit-preview-build/assets/index-DaBPZBCh.js        983.38 kB │ gzip: 325.05 kB

(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
✓ built in 6.57s
```

`git diff --check` 无输出，执行成功。Vite 构建不等同于独立 TypeScript 类型检查；未批准生产发布。

