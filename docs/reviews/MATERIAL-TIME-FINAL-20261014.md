# 图需格式与北京时间 · 最终独立复核

- candidateId：`1ada934facfa9b633aa2c0d0a91a4a544b8b5ce5a2890bc61f27f2d091039920`。
- 范围：本候选全部未提交代码与测试变更；Product-Spec.md:1089–1092 的本轮增量，及 docs/MATERIAL-UPLOAD-20261014.md、docs/BEIJING-TIME-FIX-20261014.md。不是对历史全部产品功能重新验收。
- 依据：`.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、Design-Brief.md:169/187，以及前审报告中的 M1/M2。
- **Stage 1：PASS；Stage 2：PASS。未发现本轮需要修复的 HIGH/MEDIUM 问题。**
- 开始与结束均执行 review-status，currentId 与上述候选一致；审查期间未发现受控代码变化。reviewer 仅写本报告，未修代码、未提交、未登记批准、未写 clean；批准由主 Agent 对同一候选登记。

## Stage 1：Spec Compliance

下表代码路径以 `hengxin-smart-image/` 为根。

|需求条目|结论与实现证据|验证证据|
|---|---|---|
|两类图需不限扩展名，包含 PPT/PPTX/DOC/其他文件|完整实现。backend/app/overseas/materials/parsers.py:32–41 只校验大小、非空和类别；frontend/src/api/overseas/materials.ts:25–29 同步；frontend/src/views/overseas/OverseasMaterialsPanel.vue:18 不设 accept。|frontend/tests/overseas-materials.test.ts:13 起覆盖两类、PPT/PPTX、无扩展名；backend/tests/test_overseas_materials.py:222 起覆盖原件上传。reviewer 独立浏览器 PPTX 上传及提交通过。|
|每类一份、非空、不超过20 MiB|完整实现。parsers.py:33–36 保留限制；materials/service.py:65–68 限每类一份；frontend/src/api/overseas/materials.ts:26–33 对等检查。|后端 test_overseas_materials.py:85 起空文件/超限用例；前端 materials.test.ts:13 起边界；独立 faults 浏览器验证空文件/超限/无资料不可提交。|
|可解析格式继续解析；不能解析保留原件和真实 failed 状态，不伪造文字|完整实现。parsers.py:44 起保留独立受限解析进程；materials/service.py:51–61 在 ParseError 时记录 failed、空文本；parsers.py:49 显示原件已保存及下载指引。|后端原件完整性、重试/解析测试；独立浏览器解析失败/重试与保留提示通过。|
|未知格式私有附件下载，保留鉴权|完整实现。parsers.py:41 未知格式 octet-stream；materials/files.py:96–110 按 readable 校验并返回 attachment、private/no-store、nosniff；materials/service.py:29–37 按绑定任务权限校验。|test_overseas_materials.py:222–239 原件字节相等、attachment、nosniff；既有鉴权回归包含于全量后端日志。|
|未解析原件允许创建、补充提交、退回重提进入人工审核|完整实现。materials/service.py:65–81 要求有解析版本但不要求 ready；:96 由补充提交复用 bind；frontend/src/api/overseas/materials.ts:30–33、frontend/src/views/overseas/requirements.ts:7–11 保留归属及重复校验，放开 failed。|test_overseas_materials.py:222 起创建为 pending_review；test_overseas_requirements.py:124 起退回重提、越权与原子性；独立浏览器验证提交请求携带真实选中 materialIds。|
|人工审核/工作台原件引用仍鉴权；旧自动分析仍需文字|完整实现。backend/app/overseas/studio/queries.py:14–19、30–39 按任务和附件归属鉴权，材料上传 ready 与解析 failed 分离；backend/app/overseas/plans/snapshot.py:22–30 仍要求解析 ready 且 text 非空。|检查实际调用链及后端全量回归，未声称调用真实付费模型或验证 PPT 在线解析。|
|固定 Asia/Shanghai、YYYY-MM-DD HH:mm:ss，不受本机时区影响|完整实现。frontend/src/utils/beijing-time.ts:2–5 显式时区与 h23；:12–17 兼容旧北京墙上时间；:27–30 按瞬间转换。|独立 formatter/SFC 7项通过；独立 America/Los_Angeles 浏览器显示原始微秒 UTC 样例为 2026-10-14 08:59:59。|
|缺失及非法日期/时分秒为占位|完整实现，前审 M1 已修复。beijing-time.ts:19–25 校验日历天数及时间范围，:28 拦截无效 Date。|frontend/tests/beijing-time.test.ts:41 起包含2月30日、非闰年2月29日、4月31日、24时/60分/60秒及合法闰日；reviewer 独立执行通过。|
|海外任务、流转、资料、执行、历史与归档时间|完整实现。OverseasWorkspace.vue:54/82；OverseasTaskInfo.vue:8/21/24；requirements.ts:4；OverseasMaterialReader.vue:12；OverseasMaterialPreview.vue:12；OverseasExecution.vue:9/14；OverseasPlans.vue:12；OverseasPictureResults.vue:19；OverseasArchivePage.vue:8；OverseasArchiveDetail.vue:8。以上位于 frontend/src/views/overseas。|审查展示调用点，扫描业务目录没有遗留 toLocale 时间格式化或 createdAt/updatedAt/at 裸插值；真实 SFC 与浏览器覆盖列表、任务信息及审核。|
|国内任务、版本、归档、管理及成员申请时间|完整实现。frontend/src/views/hengxin/components/Tasks.vue:74、TaskDetail.vue:124、RoundHistory.vue:49、Archive.vue:120、Templates.vue:85、TemplateHistory.vue:8；api-image-edits/item-command.ts:43、DemoRecords.vue:56、DemoVersionDialog.vue:9/22；admin/users.vue:12、settings.vue:19、monitor.vue:42、ApiUsageDetail.vue:39；frontend/src/views/auth/MembershipApplications.vue:12；frontend/src/api/hengxin/execution-data.ts:58–59 共享格式化入口。|逐项检查调用替换和前端342项日志；未声称逐一现场操作每个国内业务页面。|
|海外管理时间展示和筛选均为北京时间|完整实现。frontend/src/views/overseas/admin/OverseasActivity.vue:111/125；OverseasLiveActivity.vue:10–11/24/45；beijing-time.ts:34–35 为日期选择器墙上值附 +08:00。|beijing-time.test.ts:34–38 验证筛选转换瞬间；组件改为 value-format 字符串，避免 Date 依赖浏览器时区。|
|UTC存储、原始API时间、排序和耗时不变|完整实现。后端改动仅材料 parsers/service；展示函数只在展示入口使用。frontend/src/views/overseas/workflow.ts:42/58 的预览事件改存 ISO 瞬间。|完整 diff 核查，无时间模型、数据库、API序列化或耗时计算改动。|
|引导真实性、设计一致性与 Spec 漂移|通过。OverseasMaterialsPanel.vue:4/9/19 明确未解析时下载，不承诺 PPT 在线阅读；OverseasMaterialReader.vue:13–15 保留失败与下载提示。没有新增页面/API/表，新增共享格式化工具及测试属于需求范围。|独立浏览器及截图对照，详见 Stage 2。|

部分实现：无。未实现：无（仅指本次审查范围）。

## Stage 2：Code Quality

- **结构与类型：PASS。** `frontend/src/utils/beijing-time.ts:1–36` 集中负责时间展示/筛选转换，不引入依赖；本轮变更的生产源文件均不超过300行。扫描新增 diff 未引入 any、eval、innerHTML、前端秘密变量或硬编码密钥。材料绑定沿用既有锁定/归属处理（materials/service.py:65–80），没有另建绕过权限入口。
- **安全：PASS。** `materials/parsers.py:39–41` 未知格式走 octet-stream；`materials/files.py:96–110` 私有、no-store、nosniff 和附件下载仍在；`OverseasMaterialReader.vue:55–65` 非 PDF 用 textContent 安全文本展示。上传扩展放开未引入动态执行、Shell拼接、SQL拼接或文件路径拼接。已有解析器仍有15秒时限及受限子进程（parsers.py:53–91）。
- **测试真实性：PASS，有明确覆盖边界。** 后端测试保存不透明真实字节并断言下载相等，未把 failed 伪造为 ready；浏览器 mock 只隔离 API，运行实际 Vue 页面、XHR、按钮和提交请求。reviewer 实际重跑两份浏览器脚本及7项 formatter/SFC 测试，均通过。前审 M2 的旧格式/状态/阅读选择器已在 `frontend/tests/overseas-materials-real.browser.mjs:27–47` 同步；该脚本完整身份HTTP夹具未运行，不把静态修正记作该脚本PASS。
- **现场视觉对比：PASS（本次改动区域）。** reviewer 重新运行 `frontend/tests/material-time.browser.mjs:50–67`，真实浏览器打开列表、详情、提交图需和提交后的审核页，并查看本次生成的 `output/material-time-upload.png` 与 `output/material-time-review.png`。提交页与邻居审核页保持相同 Art 页头/侧栏、白色圆角卡片、蓝色按钮及双栏布局；上传状态与较长说明正常换行，审核提交时间完整显示。对应设计依据 Design-Brief.md:169/187，组件样式 `OverseasMaterialsPanel.vue:85–96` 与 `OverseasMaterialReader.vue:72–79`。独立 faults 脚本同时通过390px窄屏裁切验证。本次没有新增设计稿或新视觉体系。
- **前审修复复核：PASS。** M1 对非法日期的错误归一已用实际执行证明修复；M2 中相反的测试断言与文案已消除，并在当前验证文档中明确未执行完整真实HTTP夹具。未将旧报告的通过项直接覆盖新快照。

## 编译与测试原始证据

主线程提供的最终构建日志 `output/material-time-build-final.log:3–4` 及末行（reviewer 已读取，未重复完整构建）：

```text
> hengxin-smart-image-frontend@0.2.30 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
✓ built in 38.38s
```

`output/material-time-frontend-final.log`、`output/material-time-backend-full.log` 的原始汇总：

```text
ℹ tests 342
ℹ pass 342
ℹ fail 0
1996 passed, 185 skipped, 15 warnings in 289.86s (0:04:49)
```

reviewer 独立运行 `pnpm exec tsx --test tests/beijing-time.test.ts tests/beijing-time-component.test.ts`：

```text
ℹ tests 7
ℹ pass 7
ℹ fail 0
```

reviewer 独立运行两份浏览器脚本（退出码均0）：

```text
PASS: America/Los_Angeles browser renders Beijing list/review time; unparsed PPTX uploads and submits to review
PASS material browser faults: size/type/empty; real XHR progress; cancel and route late response; network/malformed; parse retry; safe text; deletion conflict/cancel; unparsed upload can submit; no upload no submit; narrow clipping; revoked content clears state
```

首次直接运行浏览器脚本提示缺少本地 playwright 模块；按现有运行环境设置 `PLAYWRIGHT_MODULE=file:///C:/Users/82358/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs` 后实际运行成功，未安装或修改项目依赖。

## 验证边界与交接

浏览器使用本地3015真实前端配隔离mock接口；后端由真实TestClient/临时数据库和内存对象存储测试。1996项为主线程提供的Linux全量证据，185个skip不是通过项；没有生产联调、生产部署、付费模型调用，也没有完整身份多角色HTTP浏览器夹具的新运行证据。上述边界不阻断本次局部变更的两阶段审查通过，不能据此宣称生产已修复。

主 Agent 可对本报告及同一 candidateId 执行 review-approve；后续代码变化需重新固定候选并复核。

