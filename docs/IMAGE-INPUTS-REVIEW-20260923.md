# 原图参照、统一上传与模板弹窗独立审查

审查日期：2026-09-23。角色：独立 code-reviewer；使用 `.agents/skills/code-review/SKILL.md`。只审查和验证，未修复代码、提交、推送或部署。

最终 candidateId：`6f315d059e40a9f2bde956817a0ad96f19e9f70c47e8be94bbbc2643ccaf0c16`。

初始交接 candidateId：`d0bec37954a64d2943b17ce4c48923629e98c441459e32e09a34eb1e656db68e`。审查期间主 Agent 清理 `.pnpm-store/v11/index.db` 并重新固定候选，报告该缓存删除是唯一快照差异。旧快照未另存，reviewer 不把该差异声明作为独立核验结果；已对最终候选重新核验全部 22 个变更/新增前端文件，按 CRLF→LF 归一计算 SHA256，全部与最终 candidate.files 相符，Mismatches 为空。以下结论只批准最终候选的本轮范围。

## 范围与结论

依据 `Product-Spec.md:3` 正式授权、`DEV-PLAN.md:3` 四项计划、`Design-Brief.md:3` 和认可预览 `docs/UI-REFERENCE-UPLOAD-PREVIEW-20260923.md:5`。审查本轮 17 个生产前端文件及 5 个测试文件；包括全部 git diff、新增 SharedMaterial、SourceComparison、UploadInteraction、upload-interaction 及三个新测试。PERFORMANCE 文档、依赖缓存、后端既有功能不在范围。

- **Stage 1 Spec Compliance：PASS。** 无 HIGH、MEDIUM 未解决问题；本轮要求均找到实现与证据。
- **Stage 2 Code Quality：PASS。** 未发现本轮引入的阻断质量或安全问题。
- 不表示整份历史 Spec、生产上传、钉钉容器或真实模型生成通过验收；本轮不涉及生产连接。

## Stage 1：逐条需求对照

以下路径中的 `src/`、`tests/` 均相对 `hengxin-smart-image/frontend/`。

| 正式需求 | 结论及实现证据 | 验证证据 |
|---|---|---|
| API 正式与 Demo 详情顶部共用素材、可放大 | 完整实现。`src/views/hengxin/api-image-edits/RealTaskDetail.vue:22`、`TaskDetail.vue:13` 读取 task.material；`SharedMaterial.vue:4` 使用 PicturePreview，没有读取最新模板或成品回填。 | 独立复跑浏览器检查冻结素材 src；`tests/image-inputs.browser.mjs:49`。 |
| 每张原图与当前成品对照，版本切换同步 | 完整实现。`RealTaskDetail.vue:42`、`:71` 按 item.id 响应式取当前对象；`TaskDetail.vue:32`、`:54` 绑定对应 Demo 项；`SourceComparison.vue:4`、`:8` 分别接 source/result。 | 浏览器先断言 source/v2 URL，再刷新当前版本并断言 v1；`tests/image-inputs.browser.mjs:54`。 |
| 历史输入缺失明确提示，不伪造；失败可重试 | 完整实现。`SharedMaterial.vue:5`、`SourceComparison.vue:5` 缺失提示；`src/api/api-image-edits-validate.ts:14`、`:23` 仅新增显式 null 输入兼容；`:10` 版本成品仍要求有效 picture；`src/views/hengxin/components/PicturePreview.vue:7` 保留重新加载。`RealRecords.vue` 的列表缩略图同步使用原图可选访问。 | DTO 测试拒绝损坏对象/undefined source/null 成品；`tests/api-image-operations.test.ts:49`。浏览器显式 null 后成品仍可见，404→重新加载恢复；`tests/image-inputs.browser.mjs:78`。 |
| 所有业务图片入口选择文件、拖入、Ctrl+V、粘贴按钮 | 完整实现。共享 `src/views/hengxin/components/UploadInteraction.vue:2`、`:6`、`:24`、`:34`、`:40`；通用 `ImageUpload.vue:2` 覆盖 `TemplateEditor.vue:22`、`CreateTask.vue:19` 和 CLI `TaskDetail.vue:42`；两套 API sequence/revision 分别在 `RealImageSequence.vue:2`、`ImageSequence.vue:2`、`RealRevisionDialog.vue:9`、`DemoRevisionDialog.vue:9` 接入。 | 搜索全部业务 ElUpload/file/ImageUpload 入口无遗漏；浏览器覆盖正式 API sequence/标注、模板新建/配置、三类创建和 CLI 问题截图；选择文件另有 `tests/core-template-revision.browser.mjs:56`。 |
| 保留各入口格式/大小/数量/真实 API | 完整实现。`src/views/hengxin/use-image-upload.ts:90` 保留 MIME、10 MiB、数量和解码，`:74` 调用原 uploadFile；`api-image-edits/real-draft.ts:24` 保留 21 张与独立上传 API；`RealRevisionDialog.vue:77` 保留 JPG/PNG、扩展名、签名、解码，`:92` 调用 apiImages.upload。 | 正式组件浏览器断言 WebP 标注拒绝、多图拒绝和上传调用计数；`tests/image-inputs.browser.mjs:67`。未新增上传接口。 |
| 单图已有图片先移除，多图上传中仍可追加 | 完整实现。`components/upload-interaction.ts:5` 单图批次/占用校验；`ImageUpload.vue:65` 仅 maxCount=1 时将 uploading 作为禁用原因，`:73` 接收统一批次；`use-image-upload.ts:92` 在 await 前占位并执行数量限制。两套 revision 都先 singleImageError。 | 浏览器满额拒绝且原图片保留、移除后上传；`tests/core-template-revision.browser.mjs:59`。`tests/api-image-draft.test.ts:20` 覆盖异步完成倒序与多图占位。 |
| 提交锁定、操作待核实、单图在传/禁用阻止上传 | 完整实现。`RealImageSequence.vue:28` 复查 disabled/locked；`real-draft.ts:12` 锁定 busy/pending；CLI `TaskDetail.vue:42` 传 uncertain；`RealRevisionDialog.vue:44`、`:70`、`:91` 对 pending、blocked、reading 以及迟到上传回包复查；`UploadInteraction.vue:16`、`:46` 取消禁用期间发起的异步剪贴板结果。 | SFC 生命周期专项测试独立执行，禁用、禁用后恢复、卸载均不投递；`tests/upload-interaction-component.test.ts:78`。原请求锁定测试 `tests/api-image-draft.test.ts:30`。 |
| 不抢文字粘贴、只投递聚焦区、排序不误上传 | 完整实现。`UploadInteraction.vue:25` 判断 activeElement 与文本目标；`:30`、`:36` 仅捕获 Files；API 卡片 dragend 清理 dragIndex，排序事件没有 Files 时继续原路径。 | 真实 Ctrl+V 输入意见无上传；浏览器 dragTo 不增加上传调用；`tests/image-inputs.browser.mjs:102`、`:139`；SFC 专项 `tests/upload-interaction-component.test.ts:53`、`:73`。 |
| 剪贴板权限拒绝有可操作提示 | 完整实现。`upload-interaction.ts:1` 提供 Ctrl+V/选择文件；`UploadInteraction.vue:49` 显示错误；没有偷偷上传 URL/文字。 | `tests/upload-interaction-component.test.ts:92` 拒绝与卸载竞态；`tests/upload-interaction.test.ts:12` 文件过滤。 |
| 模板居中、窗口内限高、内部滚动、固定头尾 | 完整实现。`TemplateEditor.vue:2` 使用 align-center、min(680px,100vw−32px)；`:107` 最大 100dvh−48px、body 滚动、header/footer 不收缩。表单初始化/保存逻辑未改。 | 独立浏览器 1440×900 与 1280×720 中心误差 <3px、底部可见；`tests/image-inputs.browser.mjs:113`；已查看 template-1280 与认可预览对应截图。 |
| 保留原下载、修改、版本、重试 | 完整实现。`RealTaskDetail.vue:30` 原按钮/命令及 `:78`、`:87`、`:94` 行为保留；Demo `TaskDetail.vue:22`、`:23`、`:80` 保留原入口；单图变更仅统一输入入口。 | git diff 核对没有改写原下载/重试/版本执行函数；12 项专项中的原幂等键、ZIP和版本 DTO 回归通过。 |
| 不改后端、模型/提示词/计费/数据库、不部署推送 | 符合。变更清单仅前端与文档；`tests/image-inputs.browser.mjs:19` 拦截本地页面全部 /api/v1 请求。 | git diff 范围检查；测试脚本未调用生产或模型。 |

部分实现：无。未实现：无。Spec 漂移：无新增页面、接口或数据库结构，新增组件均服务于本次授权。

## Stage 2：质量、安全、视觉与测试真实性

1. **结构/类型 PASS。** 新生产组件 20、27、59 行，helper 24 行；全部 17 个变更/新增生产文件不超过 170 行。共享输入事件和展示组件避免把新逻辑复制到所有业务入口。`UploadInteraction.vue:10` 事件类型、`upload-interaction.ts:13` Clipboard 类型明确；扫描生产变更无新增 any。
2. **异步处理 PASS。** `UploadInteraction.vue:16`、`:17`、`:46` 使用 generation/alive；`RealRevisionDialog.vue:91`、`:93` 在解码与上传之后再次核查状态并清理失效文件；Demo `DemoRevisionDialog.vue:38` 使用 readToken。文件选取统一批次 `ImageUpload.vue:95` 避免单图批量误接收。
3. **安全扫描 PASS。** 对本轮生产文件检索 eval、innerHTML、dangerouslySetInnerHTML、前端 KEY/SECRET/TOKEN、已知密钥前缀，未命中；图片经过原校验与上传接口。`tests/upload-interaction-component.test.ts:22` 的 new Function 只编译执行仓库内固定 SFC 测试源码，未引入产品运行时动态执行或外部输入执行。
4. **视觉 PASS。** 实际查看 `output/image-inputs-20260923/template-1280.png`、`real-comparison.png` 与 `output/ui-preview-20260923/template-1280.png`、`comparison.png`：模板宽 680px、上下 24px 边距与固定底部一致；对照宽 1040px、双列/按钮/留白沿用认可稿。缩略图区保留 PicturePreview；72px 共用素材尺寸见 `SharedMaterial.vue:16`；窄屏单列见 `SourceComparison.vue:26`。独立浏览器复跑真实页面同时确认既有模板库背景、表单控件、详情操作可见；沿用既有主题变量。
5. **测试真实性 PASS，有明确边界。** 新 SFC 测试执行 compileScript 产物，不重写事件实现；使用 FakeElement 仅替代宿主 DOM，真实 DOM/系统剪贴板由浏览器用例补充。浏览器的拖入是合成 DataTransfer 事件，Ctrl+V 和粘贴按钮使用真实 Chromium 剪贴板。API 通过 route 拦截，证明真实前端调用及契约消费，不能证明真实服务器存储。针对单图先移除规则的既有浏览器断言同步修改，确实断言旧图片保留而不是仅把断言名称改掉。
6. **验证边界，非失败项。** 未在钉钉容器、生产浏览器权限策略或所有浏览器执行；Demo 两个独立 API 入口主要通过代码核查与共享行为测试覆盖，未宣称新浏览器脚本逐入口完整执行四种方式。没有真实收费生成、ZIP 网络下载端到端或线上后端测试；这些并非本轮隔离验证的授权范围。

## 原始验证结果

主 Agent 提供且 reviewer 已读取的完整输出：`output/image-inputs-20260923/tests.log`、`build.log`、`build-demo.log`。两条 build 命令本身包含 `vue-tsc --noEmit`，因此类型检查有编译日志佐证。

```text
> hengxin-smart-image-frontend@0.2.3 build
> vue-tsc --noEmit && vite build
✓ built in 28.66s

✓ built in 30.55s

ℹ tests 161
ℹ suites 0
ℹ pass 161
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 17309.0518
```

reviewer 独立运行 `node --import tsx --test tests/upload-interaction.test.ts tests/upload-interaction-component.test.ts tests/api-image-operations.test.ts`，退出 0：

```text
ℹ tests 12
ℹ suites 0
ℹ pass 12
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1018.2897
```

reviewer 独立运行 `node tests/image-inputs.browser.mjs`，本地 3014/3015、独立 Chromium context，退出 0；重新生成的 `output/image-inputs-20260923/checks.json` 为 passed:true、6 组检查、errors:[]。主 Agent 额外提供的 core-template-revision PASS JSON 已读取；compact-upload PASS 仅作为补充声明，不冒充独立复跑。

本报告不写 `.needs-review`、不调用 review-approve。由主 Agent 对最终 candidateId 登记 Stage 1 PASS / Stage 2 PASS，并检查快照仍一致。
