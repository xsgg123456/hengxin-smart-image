# 批量标注与单图参考图独立预览审查

- 审查日期：2026-11-05；独立 code-reviewer，执行 code-review 两阶段审查。
- 最终 candidateId：`ed3e2858f2f6c7672905a87834c6faa2177900566b972bb323419642a374b4b5`。
- 结论：**Stage 1 PASS；Stage 2 PASS**。仅批准此独立预览快照，不代表正式实现、生产发布或真实 AI 效果验收。
- 范围：`hengxin-smart-image/frontend/preview-batch-annotation/` 的 12 个受控文件，加 README 验收文档；交接所称“11个文件”与实际清单不符，以 harness 的 12 文件清单为准。下文 `P/` 均指该完整目录。
- 已读依据：`P/README.md:3`、`:7`—`:11`、`:21`；`Product-Spec.md:1237`、`:1242`、`:1245`、`:1247`—`:1253`；`Design-Brief.md:210`、`:218`—`:219`。历史正式产品条款只用于组件和交互基准；本轮授权明确限定独立预览。
- `git status --short` 只有新增预览目录及审查/验证文档；未发现生产 src、正式 Spec、Brief、DEV-PLAN 改动。最终 `review-status` 的 currentId 与上述 candidateId 一致，尚未登记批准，由主 Agent 执行 review-approve。

## 快照变化与旧问题

最初候选 `3a0f02bb4a0f4545f3842a53e3d2e07a90b8766c32db7a6fff260647d3c04797` 存在 **HIGH / Stage 1**：模拟发送后仅保存文件名和说明文本，历史没有原图、标注图及参考图材料入口，不满足 README 第4项“模拟发送展示冻结的实际材料/意见”。旧版 `P/App.vue:75`—`:78` 继承空附件，独立浏览器复现结果为发送前核对有2张图，发送后最后一条用户消息 `img=0`、`button=0`。旧候选未通过，不将其结论用于新候选。

主 Agent 修复后重新固定上述最终候选：`P/App.vue:15`、`:63`、`:76`、`:82` 保存按轮次区分的材料快照并提供查看入口；`P/PreviewTurns.vue:6` 增加历史材料插槽；`P/state.ts:18`、`:31`—`:42` 增加读取序号，忽略异步替换/重试的过期结果。本 reviewer 重新读过差异，并独立操作验证历史材料修复后，重新完成 Stage 1，随后执行 Stage 2。旧 HIGH 已关闭。

## Stage 1：Spec Compliance — PASS

以下覆盖 README 五项验收及交接中的逐项约束。没有未实现或部分实现的范围内条目。

| 验收条目 | 结果及证据 |
|---|---|
| 独立入口；不改正式需求或生产实现 | PASS。`P/vite.config.ts:3`—`:6` 使用 isolatedPreview、127.0.0.1:3036 和独立输出目录；受控变更清单仅预览目录。`P/README.md:3` 明示边界。 |
| 真实外壳、会话、素材、图片和标注组件 | PASS。`P/App.vue:2`、`:11`、`:31`、`:50`—`:53`；`P/PreviewTurns.vue:15`；`P/EditorDialog.vue:11`、`:44`；`P/BatchBoard.vue:15`、`:26`；`P/style.css:1`—`:2`。已实际打开 baseline 与新页面，非仅检查 import。 |
| 样图明确，原组件对照可打开 | PASS。`P/state.ts:11` 使用既有 sample-1至6；`P/App.vue:6` 显示示例/本地/不调用AI/刷新重置，`:36`—`:38` 对照模式挂载生产 StudioAnnotationDialog。不是用户截图原文件。 |
| 每组六图上方批量入口；2行3列 | PASS。`P/PreviewTurns.vue:13` 在图片组上方发出 batch；`P/BatchBoard.vue:33` 使用列余数和行整除定位，实际1440截图六张完整显示为2行3列。 |
| 同一大画布整体缩放、平移、适应 | PASS。`P/BatchBoard.vue:8` 用唯一SVG viewBox；`:35`—`:38` 缩放/适应，`:45`、`:67` 平移。主验证实际断言125%和viewBox变化。 |
| 逐图选择、矩形和画笔 | PASS。`P/BatchBoard.vue:41`—`:60` 按data-picture定位草稿，`:64`—`:76` 更新和结束标注。reviewer独立在第2图框选、第4图画笔，分别填写不同意见并成功带回。 |
| 同工作区精细标注及逐图切换 | PASS。`P/EditorDialog.vue:6`—`:11` 切换整组/原AnnotationCanvas，`:8` 上一张/下一张，`:52` 按当前ID取草稿。主验证实操返回整组和逐图切换。 |
| 逐处意见必填、无通用意见框 | PASS。`P/EditorDialog.vue:17`—`:22` 仅标注意见；`P/state.ts:24`—`:28` 验证；`P/App.vue:28` 整体要求留在工作台。主验证空意见阻止确认。 |
| 批量只带回已标注图及各自材料 | PASS。`P/EditorDialog.vue:53`、`:62` 仅筛marks；`:66` 为每张独立snapshot；`P/state.ts:52`—`:60` 复制该ID的意见和参考图。reviewer独立返回结果严格为02.jpg、04.jpg两项。 |
| 仅有参考图的批量项排除并保留 | PASS。`P/EditorDialog.vue:25`、`:35`、`:54` 提示及核对名单，`:62` 排除且不清草稿。主验证第1张只有参考图未被带回；缺失用途的被排除图不会阻断其他已标图。 |
| 单图1380px及原画布 | PASS。`P/EditorDialog.vue:2`、`:11`；同1920视口基准和新单图实测均1380×926。实际对照画布位置、工具栏、底部按钮和蓝白样式一致；右侧按授权增加参考区。 |
| 多参考图、两种用途、逐图说明必填 | PASS。`P/ReferencePanel.vue:5` multiple、`:15` 两种选项、`:17` 独立说明；`P/state.ts:27` 校验。reviewer亲测只上传未填用途/说明时错误阻止确认；主验证两张参考图流程。 |
| 参考图预览、替换、删除 | PASS。`P/ReferencePanel.vue:9`、`:11`、`:29`。主验证实际打开查看器并关闭、替换保留说明、删除减少数量；reviewer另实操替换。 |
| 读取错误、重试及错误反馈 | PASS。`P/state.ts:31`—`:42` 校验类型/大小/解码并输出错误，`P/ReferencePanel.vue:10`、`:13` 提供重试，`P/state.ts:25`—`:26` 阻止未就绪材料。主验证使用损坏PNG真实触发解码失败、重试后保留错误、禁止确认。 |
| 原图加载错误与重试 | PASS。`P/EditorDialog.vue:9`、`:55`—`:57` 显示错误和重试，并通过epoch防止跨图旧结果回写；`P/BatchBoard.vue:13`、`:17` 明示批量读取失败及精细重试入口。此路径为代码核查，未声称已模拟网络故障。 |
| 单图无标注可带回，再填主输入 | PASS。`P/EditorDialog.vue:62` 单图不按marks过滤；`P/App.vue:75` 无逐图描述时要求主输入。reviewer独立仅上传参考图、无标注带回并补意见后模拟发送成功；主验证空主输入阻止发送。 |
| 批量与单图按图片ID共用草稿；不串图 | PASS。`P/state.ts:15`、`:19`，`P/EditorDialog.vue:52`，`P/ReferencePanel.vue:25`。主验证第2图参考内容在第4图不出现，回第2图仍存在；批量带回后单图继续编辑保持意见。 |
| 关闭保留、刷新重置 | PASS。`P/EditorDialog.vue:59` 关闭不删草稿；`P/state.ts:15` 内存状态无持久化。主验证关闭重开保留；reviewer独立reload后批量0张且确认禁用。 |
| 带回前核对；带回后手动发送 | PASS。`P/EditorDialog.vue:33`—`:38`、`:66`—`:70` 两步确认；`P/App.vue:68` 只回填。reviewer批量回填后用户消息仍1条；发送需点击工作台发送及模拟确认。 |
| 更新同图不重复；取消待发；重新批量清理旧卡片 | PASS。`P/state.ts:62`—`:66` 按picture.id替换；`P/App.vue:23` 取消、`:68` 清理该组旧项。主验证更新仍2项，清除第4图再确认仅1项，取消后0项。 |
| 模拟发送历史冻结实际材料和意见 | PASS（修复后）。`P/App.vue:15`、`:76`、`:82`，`P/RevisionDetails.vue:6`—`:8`。reviewer独立发送后打开历史：原图及参考图2张；修改参考说明并替换文件后，再打开历史，文本与全部图片URL严格等于发送前快照。主验证另覆盖标注图。 |
| 不自动生成、不改原六图、无业务上传 | PASS。`P/App.vue:83` 新轮pictures为空并明确模拟；原seedTurn保留。`P/state.ts:38` 仅createObjectURL；reviewer实际流程请求中无/api/业务请求、无非GET请求。主验证原结果仍6张。 |
| 桌面1920/1440及390窄屏主控件可达 | PASS。`P/style.css:5`、`:10`—`:11` 内部滚动与520px图片区；主验证390弹窗x=7.8125、宽374.390625、底部y=748高58，均在390×844内。reviewer独立390画笔→滚动填意见→确认→带回成功；实际审看1440/390截图。 |
| 控件和引导真实性、范围边界 | PASS。新增上传、标注、核对、再编辑、取消、历史按钮有真实本地行为；`P/App.vue:64` 非本轮业务操作统一明确预览边界，`P/README.md:21` 已声明。不将会话管理/下载归档/真实生成列为本预览实现。 |

Spec漂移：没有新增业务API、持久化或生产路由。历史材料插槽是修复README第4项的必要内容，属于授权范围；README第1项“仅增加批量入口”对派生组件的描述还应结合该修复理解，不影响验收范围。基准模式及示例材料均已有预览明确授权。

## Stage 2：Code Quality — PASS

| 项目 | 结论与证据 |
|---|---|
| 类型和职责 | PASS。`P/state.ts:8`—`:10` 明确Reference/Draft/Revision；App负责工作台、EditorDialog协调编辑、BatchBoard处理整组坐标、ReferencePanel处理文件、RevisionDetails只读展示。扫描无新增any；独立vue-tsc最终快照exit 0。 |
| 文件规模与复用 | PASS。12个受控文件均少于300行，最大App.vue为87行；日志不计源文件。`P/PreviewTurns.vue:6`、`:13`、`:27`—`:32` 与生产组件diff只涉及历史插槽、批量入口、baseline及导入路径，未重新复制共享画布算法。预览派生组件符合本轮隔离要求。 |
| 快照与异步安全 | PASS。`P/state.ts:54`、`:60` 复制marks/references；`P/App.vue:76` 深复制marks；`:82` 按turn保存独立列表。`P/state.ts:32`—`:34`、`:39`、`:41` 阻断旧读取结果回写。File/Blob内容不被后续替换修改。 |
| 输入和错误处理 | PASS。`P/state.ts:24`—`:28`、`:36`—`:42` 对缺意见、缺用途、空/超限/不支持/损坏文件给出明确反馈；`P/EditorDialog.vue:63`—`:68` 捕获准备失败且解锁，不吞异常假成功。 |
| 安全扫描 | PASS（本范围）。对12个源/配置文件扫描eval、innerHTML、dangerouslySetInnerHTML、暴露凭据前缀、常见密钥、用户绝对路径及any，无匹配。`P/RevisionDetails.vue:7`—`:8` 文本插值，非HTML注入；`P/vite.config.ts:5` 仅监听127.0.0.1；实测无业务请求。 |
| 测试真实性 | PASS。检查`output/batch-annotation-preview/browser-check.cjs`：真实鼠标绘制、真实文件上传及坏PNG解码，断言DOM/消息数量/请求/图片URL，不是只测函数或仅按按钮存在判断。旧测试只验历史文本的盲区已补真实图像材料及说明冻结；最终35项均通过。独立复测批量目标筛选、390画笔带回、无标注参考图、缺用途说明阻止、历史替换冻结、刷新重置。 |
| 视觉对比 | PASS。亲自打开1920 baseline生产单图与新单图，截图展示相同外壳、1380宽弹窗、原工具栏/画布尺寸和底部层次，参考图位于右栏。审看batch-1440.png及single-390.png，六图组完整、窄屏工具与确认可达。`P/style.css:1`—`:11` 继承生产CSS与颜色变量，未引入另一套视觉体系。 |

没有未解决的HIGH或MEDIUM问题。资源URL在本页生命周期内保留，以支持草稿及历史预览；`P/state.ts:68` 和 `P/App.vue:86` 卸载统一释放，符合本次刷新重置的内存预览范围。没有扩大为长期持久化或真实上传可靠性结论。

## 编译与运行证据

最终候选由reviewer独立运行：

```text
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p preview-batch-annotation/tsconfig.json
[stdout/stderr为空]
exit_code: 0
```

构建为主 Agent 当场执行，reviewer读取原始日志`P/build.log:1`及`:72`，关键原始输出如下；不是reviewer重复构建：

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 4614 modules transformed.
rendering chunks...
computing gzip size...
✓ built in 21.61s
```

主 Agent 在最终候选上再次执行既有回归，仅作为生产基线证据，未冒称新增预览的功能测试。读取`P/regression.log:837`起原始摘要：

```text
ℹ tests 514
ℹ suites 0
ℹ pass 514
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 10523.0465
```

主 Agent 的`output/batch-annotation-preview/validation.json:2`包含35条通过断言、errors=[]、requests=[]。reviewer独立浏览器使用独立Chromium context，关键原始输出：

```text
returned [ '修改 02.jpg标注1处 · 参考图0张 · 待发送', '修改 04.jpg标注1处 · 参考图0张 · 待发送' ]
messages 1
requests []
mobileReturned [ '修改 01.jpg标注1处 · 参考图0张 · 待发送' ]
PASS 历史入口打开实际原图与参考图，后续替换图片和修改说明均不改变冻结材料
PASS 刷新重置草稿
```

独立历史测试首次遇到隐藏发送弹窗导致宽泛locator重复匹配，收窄到“本次修改材料”可见dialog后重跑通过；这是测试定位问题，不作为产品缺陷。未覆盖人为控制解码完成顺序、长时间内存压力和真实服务中断，相关结论仅限代码核查或本轮本地操作，不声称真实生产能力已验证。

最终登记应使用本报告与最终candidateId的两阶段PASS；禁止为旧候选登记，也不得通过写`.needs-review` clean替代快照凭据。
