# 单画布标注正式接入独立审查

日期：2026-09-24；使用 code-review skill。正式实现重新逐项审查，旧预览 PASS 不作为正式业务通过依据。

最终 candidateId：`957cf362abfbb37d63b10431a63565c51bb5517435de7e0c81115db20c883ef7`。初始交接 candidate 为 f38aa20066a20ae36e2caba989a9115d6719f0fff96c08876c29729012017881；审查期间 CLI 上传必填意见及浏览器测试发生变更，初始快照不可批准。

最终结论：Stage 1 PASS；Stage 2 PASS。所审最终快照无遗留 HIGH/MEDIUM 问题。

范围：frontend/src/views/hengxin/components/annotation/ 全部7文件、components/TaskDetail.vue、api-image-edits/RealRevisionDialog.vue / DemoRevisionDialog.vue、生成的 components.d.ts、backend/app/image_revision_prompt.py / execution/prompts.py 及新增/修改测试；另复核 .agents/skills/product-spec-builder/references/workflow-iteration.md:20 已授权规则。下文 frontend/backend 路径均以 hengxin-smart-image/ 为根。历史 previews 仅作为已审参考；性能文档不在本轮范围。

需求依据：Product-Spec.md:3–9、DEV-PLAN.md:3–8、Design-Brief.md:3。

## Stage 1：Spec Compliance

| 条目 | 结论及证据 |
| --- | --- |
| 一个画布，框选/画笔两工具，固定手柄，缩放平移不切工具 | 完整实现。AnnotationCanvas.vue:3–123；use-annotation-canvas.ts:99–161、165–172。正式浏览器 checks.json 记录 API/CLI 两工具连续标注和手柄拖动。 |
| 矩形、自由笔迹、顺序编号、独立意见、整体补充 | 完整实现。AnnotationCanvas.vue:43–91、AnnotationEditor.vue:10–25、annotation-drafts.ts:17–23。独立单测验证删除后编号同步与完整文本；浏览器混合两处标注及预览意见。 |
| 撤销、删除、确认清空、缩放原坐标 | 完整实现。use-annotation-canvas.ts:59–117；annotation-model.ts:22–88。独立单测覆盖反向矩形、越界移动/调整、画笔点及撤销保留最新意见。清空实现等待确认且再次检查锁定。 |
| 当前选定成品原文件、真实尺寸、完整 PNG、不降采样 | 完整实现。RealRevisionDialog.vue:31–46 固定版本文件，CliAnnotationDialog.vue:22–25 按 base.fileId 下载；annotation-export.ts:9–43 使用 naturalWidth/Height 和 drawImage(image,0,0)。浏览器缩略图79×150、原文件790×1500，上传PNG头实际为790×1500，证明未用缩略图。 |
| 无标注成品仍是修改对象、标注图独立参照 | 完整实现。RealRevisionDialog.vue:73 的 baseVersion / annotationFileId 分离；TaskDetail.vue:133–136 的 baseVersionId / annotationFileId 分离。image_revision_prompt.py:7–12 明确定位语义，既有后端快照测试验证引用顺序。 |
| API当前版本冲突、CLI历史版本 | 完整实现。RealRevisionDialog.vue:60、72 两次当前版校验；TaskDetail.vue:112–114、133–136 保留选择版本；正式浏览器实际CLI选V1且请求baseVersionId=version-1，API为V2。后端冲突契约未改。 |
| 关闭重开按用户/任务/位置/版本隔离草稿 | 完整实现。annotation-drafts.ts:10–16；RealRevisionDialog.vue:28；CliAnnotationDialog.vue:18；TaskDetail.vue:121–126。单测身份隔离、清除；浏览器API关闭重开标注意见保留。Demo仅本地场景以task/index/version隔离（DemoRevisionDialog.vue:18）。 |
| 预览合成图与完整意见、不承诺像素锁定 | 完整实现。AnnotationEditor.vue:29–31、82–94；annotationText超限报错不截断；实际检查api-preview.png/cli-preview.png，图及对应完整两处意见可见。 |
| 冻结版本/文件/文本/键，不确定重试不再上传 | 完整实现。RealRevisionDialog.vue:48–57；CliAnnotationDialog.vue:27–38；TaskDetail.vue:119–139 调用既有 revision-session.ts:47–76；item-command.ts:10–25 深拷贝冻结API请求。checks.json两入口各两次请求body/key逐字相同，各上传一次，CLI仍指定V1。 |
| 身份/任务变化、加载失败及错误状态 | 完整实现。RealRevisionDialog.vue:29–38、49–55、68–74 使用generation/alive；CliAnnotationDialog.vue:18、29–40 校验draftKey/alive，TaskDetail.vue:34为身份任务版本key且:106关闭旧弹框；AnnotationEditor.vue:50–63处理异步旧结果、重试及卸载。浏览器验证原图503后重新读取。身份切换异步分支为代码检查及既有session回归，未声称浏览器实测全部竞态。 |
| 既有上传点击/拖拽/聚焦粘贴、格式和10MiB限制 | 完整实现。AnnotationEditor.vue:20–24复用UploadInteraction，:65–81校验数量、扩展名/MIME、magic bytes与解码。annotation-export.ts:3–7对原尺寸超限明确拒绝，不压缩。复用上传交互既有单测在170项前端回归中。 |
| 既有意见长度及CLI必填保持 | 已修复后完整实现。审查发现CLI仅图空note会被backend/modules/tasks/service.py:106拒绝；现CliAnnotationDialog.vue:3 require-text，AnnotationEditor.vue:25、41、87按入口校验，annotation-drafts.ts:21拒绝CLI空文本，API保留仅图。独立9项标注单测包含该回归。 |
| 后端矩形/画笔/编号语义、兼容外部图，无图调用不变 | 完整实现。image_revision_prompt.py:5–12、38–39；execution/prompts.py:27。test_image_revision_prompt.py:33–75覆盖四种模式、外部图/有无编号、无图golden输出。独立27项提示词测试通过。 |
| 旧冻结API请求继续原提示词、其他流程保持 | 完整实现。test_api_image_revision_execution.py:16–65 与 snapshot.py:108起分别覆盖旧policy及新policy重试，恢复后的请求等于原失败调用；TaskDetail.vue:35–55仍保留整套与无成品入口。本次未改首次生成、后端版本模型及执行服务。 |
| 本轮不部署、不收费生成 | 符合。浏览器仅本地正式Vue界面，所有业务API拦截；changes不包含部署配置。未验证真实付费生成或生产用户操作。 |

部分实现/未实现：修复后的所审范围无。Spec漂移：未发现新页面或API；共享组件与既有入口替换属于授权范围。最初CLI必填缺陷为MEDIUM，已由主Agent修复并回归，未遗留。

## Stage 2：Code Quality

- 结构与类型：7个新文件均小于300行（最大AnnotationCanvas.vue 284行、use-annotation-canvas.ts 282行）。模型、导出、草稿、指针交互分离；不引入any。TaskDetail仅增加接入和成功清草稿。
- 错误处理：AnnotationEditor.vue:50–61、65–79、82–95显示原图/解码/合成失败且释放URL；RealRevisionDialog.vue:68–75阻止旧上下文落地；API/CLI未知提交结果由既有冻结会话承接。
- 安全：所审新增组件及两个API弹窗扫描eval、v-html、innerHTML、any、密钥前缀、SECRET/TOKEN无命中。意见使用Vue文本插值，后端JSON字符串保留用户原文；无新SQL、密钥或远程执行能力。
- 测试真实性：export单测使用伪canvas仅证明调用尺寸和编号，不能证明PNG像素；因此另检查正式浏览器真实PNG头尺寸及截图。重试比较同key/body并核对上传次数，不是仅断言按钮。后端170 skipped明确不算通过用例，当前全回归为985 passed。
- 视觉：实际查看正式api-mixed-marks.png及cli-preview.png，与已批准single-canvas.png对照。白底圆角、蓝色Element按钮、左图右意见、两工具、右上手柄、原版标题和确认图文均一致。使用本地真实Vue渲染及批准预览作为基准；不把旧预览截图充当正式页面证据。窄窗CSS由AnnotationEditor.vue:99–106内部滚动/单列实现；独立浏览器1280×720断言页脚完整位于视口，实际查看api-upload-1280x720.png；更广设备矩阵未实测。
- 框架规则：workflow-iteration.md新增一条要求界面合并以工作区/共享状态/连续路径验收，与用户修正一致，没有引入额外审批流程。

## 验证原始输出与边界

reviewer独立执行 `node --import tsx --test tests/annotation-canvas.test.ts tests/annotation-drafts.test.ts`，退出码0：

```text
ℹ tests 9
ℹ suites 0
ℹ pass 9
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 418.6067
```

reviewer独立执行 `.venv/Scripts/python.exe -m pytest tests/test_image_revision_prompt.py -q`，退出码0：

```text
...........................                                              [100%]
27 passed in 0.13s
```

前端全回归原始日志：output/annotation-frontend-tests.txt。

```text
ℹ tests 170
ℹ suites 0
ℹ pass 170
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
```

后端全回归原始日志：output/annotation-backend-tests.txt。

```text
985 passed, 170 skipped, 15 warnings in 68.90s (0:01:08)
```

前述独立命令首次在受限环境分别遇到 `uv_os_get_passwd returned ENOMEM` 与Python无法创建进程；以工具许可的正常环境重跑成功，不计为产品断言失败。

正式浏览器证据：output/inline-annotation-20260924/checks.json，passed=true，errors=[]；两入口混合标注各一次上传，另有API外部PNG上传；尺寸均790×1500；两次重试请求body和幂等key相同。外部图标服务请求被拦截并另记blockedExternal。业务API为契约模拟，不是生产后端联调。

最终类型检查、构建与快照见下。reviewer只输出审查结论，不执行review-approve、不写clean、不commit。


## 最终复核

- 源码哈希与 output/inline-annotation-20260924/review-source-hashes.json 中所审版本一致。复读 RealRevisionDialog.vue:39–42 的附件清理：捕获原 operation，pending/busy时不删除，避免新身份状态误用于旧冻结附件；:55在正常受理后先清cache再关闭。未修改后端输入保护。
- 初始candidate后发生CLI必填、附件清理及浏览器覆盖更新，均已纳入本次复核。最终 review-status 的 currentId = `957cf362abfbb37d63b10431a63565c51bb5517435de7e0c81115db20c883ef7`，approved=false，等待主Agent登记。
- reviewer独立复跑最终 tests/inline-annotation.browser.mjs：退出码0，输出如下。先前服务未启动导致connection refused；重启后首次首屏15秒超时，第二次未改代码完整通过，记为启动时序限制，不将失败运行计为通过。

```json
{
  "passed": true,
  "checks": [
    "API原始790×1500下载/失败重读、矩形+画笔、两工具固定手柄平移、草稿关闭重开、原尺寸PNG、预览编号意见、网络失败同key/body重试且仅上传一次",
    "CLI真实任务入口指定历史V1下载、混合标注与原尺寸导出、完整编号意见、冻结历史版本及同key/body重试且仅上传一次",
    "API外部PNG选择上传与无文字预览提交、版本冲突409保持弹窗不误报受理；CLI仅上传无意见阻止预览；1280×720固定页脚可见"
  ]
}
```

类型检查原始 output/annotation-typecheck.txt：

```text
vue-tsc --noEmit: PASS
```

正式构建原始 output/annotation-production-build.txt（完整日志保留，以下原文摘录）：

```text
vite v7.1.7 building for production...
✓ 4455 modules transformed.
✓ built in 35.10s
```

Demo构建原始 output/annotation-demo-build.txt：

```text
vite v7.1.7 building for demo...
✓ 4455 modules transformed.
✓ built in 35.29s
```

交付边界：本地实现和隔离验证通过；没有部署，没有请求真实模型，不将API拦截验收写成线上端到端通过。

快照注意：独立浏览器复跑曾使 Vite 自动生成 components.d.ts（删除18项全局组件声明），临时 currentId 为 2d0d9c4c97786e8e3ce556bdacbe4e7b57d54e1a798fd6b7003e1488377b0e33。该临时快照不在上述批准结论内；主Agent须恢复到957cf362快照并再次核对，或重新prepare交审。

