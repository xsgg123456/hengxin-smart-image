# 多图参考交互预览独立审查

- candidateId：6597d2802ca0e0bc77875d5013e540b43760936dc9c8fb750c951e7954f34d10
- 范围：Product-Spec.md:3 新首节、docs/REFERENCE-EDIT-PREVIEW-20260930.md，以及 hengxin-smart-image/frontend/preview-reference-edit/。下文代码位置均相对此预览目录，另有说明除外。
- 审查方式：code-review skill，两阶段；只审查本地预览，不验收正式后端、多图快照、部署或模型效果。未修改产品代码、未提交。
- 结论：Stage 1 PASS；Stage 2 PASS。无 HIGH / MEDIUM 阻塞发现。开始审查时 review-status 的 currentId 与上述候选一致。

## Stage 1 · Spec Compliance：PASS

| 需求（Product-Spec.md:4–5） | 结论与证据 |
|---|---|
| 隔离预览，不改生产，不生成/部署 | 完整实现。vite.config.ts:5–9 独立入口且仅监听127.0.0.1；Preview.vue:43–44 仅GET本地图与演示消息。git status 仅新增预览及文档；复跑测试写请求为空。 |
| 当前成品、原图、素材按顺序自动带入，同区三缩略图可放大 | 完整实现。Preview.vue:7–10、39–42；静态导入30–32，本地参考数组按顺序展示。原图放大实际点击通过；素材和成品复用同一showImage及23行弹窗处理。 |
| 成品画布与可选第四标注图 | 完整实现。PreviewEditor.vue:6、38–41直接复用AnnotationCanvas、草稿和导出模块；Preview.vue:10、16–17及PreviewEditor.vue:90–92输出3/4图。实际圈选、填写对应意见、四卡确认通过。 |
| 无标注可直接意见三图预览 | 完整实现。PreviewEditor.vue:89–92；requireText由Preview.vue:5启用；实际意见→三卡预览通过。 |
| 当前成品唯一底图，不扩大修改、不恢复历史差异 | 完整实现。image-edit-prompt.ts:2、5–19明确限制；Preview.vue:41使用该模板，PreviewEditor.vue:32展开完整提示词。 |
| 文字一/二图与独立草稿 | 完整实现。Preview.vue:5按mode隔离key，40行文字仅保留当前成品；17行共用可选标注。实测切文字初始空意见/1图，切回图片恢复4图；底层annotation-drafts.ts:11–14为按key缓存。文字双图为同一可选标注分支静态核查，未另增完整文字画笔回归。 |
| 原图尺寸策略 | 本轮预览完整表达。image-edit-prompt.ts:25声明最终尺寸锚定初始原图；本轮不生成文件，实际后处理明确属于后续正式实现，未冒充验证。 |
| 使用任务V1及原图/素材只读副本 | Preview.vue:30–32、39静态引用本地图片；查看当前/原图/素材及截图为对应的800×800、800×800、1440×1440预览素材。原业务文件读取来源由主Agent提供，审查未扩大访问业务服务。 |
| 示例主动点击、不预填 | 完整实现。Preview.vue:14按钮→PreviewEditor.vue:98；annotation-drafts.ts:13初始general为空。1920初始截图为空，测试显式点击后才产生意见。 |
| 放大不丢草稿、窗口可操作 | showImage只设置zoom状态（Preview.vue:42），不改draft；预览复跑原图放大返回、圈选、模式来回成功。1280/600截图已检查；另在600×850实测意见填写→预览→确认演示成功。 |
| 引导真实性 | Preview.vue:21、44明确演示；图片放大、固定提示词、示例按钮均有对应处理；未发现死引导。 |

部分实现/未实现：本预览范围内无；生产API发送、尺寸后处理、多图历史兼容及部署不属于本轮，不计为已实现。
Spec漂移：未发现新增业务API、数据表或生产页面。复制预览编辑器是交接文档明确的隔离实现方式。

## Stage 2 · Code Quality：PASS

- 类型与结构：Preview.vue:37定义Reference；PreviewEditor.vue:42–44定义props/提交类型；代码文件均小于300行，安全检索未发现any。PreviewEditor.vue:52–64、67–81、84–94保留图像加载/格式及预览错误处理。
- 复用核查：与生产AnnotationEditor做完整diff，新增仅参考图区、示例和确认输入插槽、相对导入路径、示例填充；底层画布未复制（PreviewEditor.vue:38–41）。LOW维护记录：预览复制的编辑器今后可能漂移，进入正式实现时应回到生产组件扩展；本轮已明确隔离预览，非阻塞。
- 安全扫描：对预览目录执行eval、dangerouslySetInnerHTML、innerHTML、VITE密钥变量、SECRET/TOKEN、常见API密钥及绝对用户路径检索，无命中。Preview.vue:43仅GET本地静态图；44行确认仅消息提示。定向确认演示也未产生写请求。
- 测试真实性：复读output/reference-preview-check.mjs后独立执行，真实鼠标绘制标注并断言确认卡数量、草稿切换、异常及写请求数组。补充output/reference-reviewer.mjs实点600px确认演示按钮，弥补原脚本只滚动到按钮的盲区。上传损坏图/网络失败未逐一注入测试，错误分支本轮未改，仅静态检查；不宣称生产全回归。
- 实际视觉对比：打开3017预览并复跑截图，再打开邻居3016已有编辑预览；证据output/reference-edit-preview/editor-1280.png、editor-600.png、reviewer-neighbor.png，并比对output/release/api-edit-20260930-df0bc8d/production-image-preview.png。现有蓝色按钮、框选/画笔工具栏、左右画布/意见布局、圆角弹窗保持一致；新参考条在画布上方，600px上下布局可滚动操作。对应style.css:1、3、6–11及PreviewEditor.vue:101–108。
- LOW构建提示：预览全量ElementPlus入口（main.ts:2、6）产生987.07kB JS，Vite报告超过500kB；本地临时预览可用，不作为正式性能验收。

## 执行证据及编译原始输出

审查独立复跑原始输出：
```text
REFERENCE_PREVIEW_PASS
{"narrowSubmit":true,"writes":[]}
```

主Agent构建日志原文（output/reference-preview-build.log；主Agent提供退出码0；审查读取核验日志，未冒称独立类型检查）：
```text
vite v7.1.7 building for production...
transforming...
✓ 1437 modules transformed.
rendering chunks...
computing gzip size...
../output/reference-edit-preview-build/index.html                        0.38 kB │ gzip:   0.32 kB
../output/reference-edit-preview-build/assets/background-BH70RQVS.png  331.25 kB
../output/reference-edit-preview-build/assets/original-ZrS5riOm.jpg    349.45 kB
../output/reference-edit-preview-build/assets/current-COtFEXTr.png     413.59 kB
../output/reference-edit-preview-build/assets/material-B3zw19iQ.png    420.38 kB
../output/reference-edit-preview-build/assets/index-CfqJwPlw.css       348.50 kB │ gzip:  48.34 kB
../output/reference-edit-preview-build/assets/index-C2QvJkGE.js        987.07 kB │ gzip: 326.21 kB

(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
✓ built in 5.67s
```

审查报告不登记批准、不写clean；主Agent需以同一candidateId执行review-approve。报告产生后如代码变化，应重新固定快照并复核。
