# 图需格式与北京时间审查

- 收到的 candidateId：`f27118c87adf617a947820177d10fc3bf28eb97fcbf99c6ad1a9a66efa90a2fa`。
- 范围：该候选所有未提交变更，包括上传校验/绑定、共享时间工具、国内海外业务展示、筛选、相关测试与需求文档。依据 Product-Spec.md:1089–1092、docs/MATERIAL-UPLOAD-20261014.md:1–5、docs/BEIJING-TIME-FIX-20261014.md:9–18。
- 使用 `.agents/skills/code-review/SKILL.md`；只读审查，未修代码、未提交、未登记批准。
- **Stage 1：FAIL（1 项 MEDIUM）；Stage 2：未完成，不得登记 PASS。**
- 首次 review-status 确认与收到候选一致；审查结束检测当前快照已变为 `0ac321164bc73c34f01af5cccbbf31643d0f2a2fc671ca0807a3025e6ca47174`。以下缺陷是原候选结论，不能用其覆盖修复后的新快照，需重新 prepare 并审查。

## Stage 1：功能逐项核对

|需求|结论与证据|
|---|---|
|两类资料不限扩展名，包含 PPT/PPTX/DOC|完整实现：backend/app/overseas/materials/parsers.py:32–41 去除扩展名白名单；frontend/src/api/overseas/materials.ts:25–29 只校验空文件/大小/类别；OverseasMaterialsPanel.vue:18 不再设置 accept。前端参数化两类格式测试、后端 PPT/PPTX/DOC/ZIP/无扩展名测试验证。路径均相对 hengxin-smart-image。|
|非空、20 MiB、每类一份|完整实现：parsers.py:33–36、materials/service.py:65–68；前端 materials.ts:26–33 保留相应边界。backend/tests/test_overseas_materials.py:85–92 保留拒空与超限。|
|可解析格式继续解析，无法解析保留原件与真实状态|完整实现：parsers.py:44–92 保留受限子进程解析；materials/service.py:51–61 保留 failed 与空 text；未知格式提示下载。test_overseas_materials.py:222–237 验证保存、提交、原件字节一致、attachment、nosniff。|
|允许创建、补充、退回重提|完整实现：materials/service.py:65–80 只要求上传版本存在；同一 bind 被创建/补充/重提复用，submit:96–100；frontend/src/views/overseas/requirements.ts:7–11 放开 failed、保留任务归属及每类一份；backend/tests/test_overseas_requirements.py:124–140 验证退回重提与越权冲突。|
|原件下载鉴权、旧自动分析限制|完整实现：materials/service.py:29–36 按绑定任务鉴权，materials/files.py:101–114 下载为 private/no-store/nosniff、非 PDF attachment；plans/snapshot.py:27–30 仍检查 ready，未伪造可解析文字。|
|北京时间、固定格式、不随浏览器时区变化|完整实现：frontend/src/utils/beijing-time.ts:2–5 显式 Asia/Shanghai 与 h23；19–23 统一格式。tests/beijing-time.test.ts:7–24 覆盖原始微秒样例、偏移、跨年与旧无时区值。洛杉矶真实浏览器配 mock API 验证上传和列表/审核展示。|
|国内海外业务时间覆盖|完整实现：海外列表 OverseasWorkspace.vue:54/82，详情 OverseasTaskInfo.vue:8/21–24，审核 requirements.ts:4，资料 OverseasMaterialReader.vue:12，计划 OverseasPlans.vue:12，图片历史 OverseasPictureResults.vue:19，成品 OverseasArchivePage.vue:8、OverseasArchiveDetail.vue:8，执行 OverseasExecution.vue:9/14、admin/OverseasLiveActivity.vue:24；国内 Tasks.vue:74、TaskDetail.vue:124、Archive.vue:120、Templates.vue:85、TemplateHistory.vue:8、RoundHistory.vue:49、api-image-edits/item-command.ts:43、DemoVersionDialog.vue:9/22；管理 users.vue:12、settings.vue:19、monitor.vue:42、ApiUsageDetail.vue:39；成员申请 MembershipApplications.vue:12。扫描业务目录无遗留 toLocale 时间展示。|
|缺失/非法时间显示占位|**部分实现，MEDIUM M1**：普通无效文本与无效月份返回占位，但不存在日期被 Date 自动滚动为另一日。详见下项。|
|海外管理时间筛选按北京时间|完整实现：OverseasLiveActivity.vue:10–11 使用字符串 value-format 并明确标签；:45 调用 beijingFilterTime，utils/beijing-time.ts:26–28 添加 +08:00；tests/beijing-time.test.ts:34–38 验证转换瞬间。|
|保留 UTC 存储、排序与耗时|完整实现：本次后端只修改材料上传/绑定，未改时间持久化；前端调用位于展示层。workflow.ts:42/58 的本地预览事件改用 ISO 保存瞬间。|

### M1：不存在日期显示成另一真实日期

- 优先级：MEDIUM。
- 需求原文：docs/BEIJING-TIME-FIX-20261014.md:11「缺失/非法时间返回占位」。
- 位置：原候选 `hengxin-smart-image/frontend/src/utils/beijing-time.ts:19–20`。
- 原因：`new Date(input)` 后仅检查 getTime 有限，无法拦截 JavaScript 的日期自动归一。
- 独立执行 `pnpm exec tsx -e` 导入实际模块，原始输出：

```text
2026-02-30T00:00:00Z => 2026-03-02 08:00:00
2026-02-30 08:00:00 => 2026-03-02 08:00:00
```

- 完成标准：不存在日期/非闰年二月29日/非法时间返回占位，合法闰日和带偏移日期继续正确转换；为源字符串显式校验日历字段并补测试。

## 测试证据与审查边界

已读取主线程提供的日志并检查对应测试源；这不等同 reviewer 独立重跑全部测试。仅上述反例为 reviewer 独立执行。

编译原始输出（output/material-time-build.log:3–4 与末行）：

```text
> hengxin-smart-image-frontend@0.2.30 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
✓ built in 50.04s
```

其余原始输出：

```text
ℹ tests 341
ℹ pass 341
ℹ fail 0
59 passed, 1 skipped, 2 warnings in 27.62s
PASS: America/Los_Angeles browser renders Beijing list/review time; unparsed PPTX uploads and submits to review
```

分别来自 output/beijing-time-tests.log、output/material-time-backend.log、output/material-time-smoke.log。收尾重新读取 Linux 全量 output/material-time-backend-full.log，原始汇总为 `1996 passed, 185 skipped, 15 warnings in 289.86s (0:04:49)`；不将185个跳过项宣称为已执行。Windows skip 为平台限制，未以其代替 Linux 检查。

查看了 output/material-time-upload.png 与 output/material-time-review.png：文件保留提示、未解析原件状态及 2026-10-14 08:59:59 清晰显示，原有卡片/按钮样式延续。尚未完成新页面与邻居基准页面的独立现场浏览器视觉对比，不能凭静态截图宣布 Stage 2 PASS。

### 预先发现的回归脚本问题 M2

- MEDIUM：`hengxin-smart-image/frontend/tests/overseas-materials-real.browser.mjs:27–32` 仍等 DOC 拒绝文案、旧“解析失败”展示，并断言失败原件不能补充提交，与本轮实际实现冲突。该脚本未包含在已通过的 mock 浏览器日志中，不能据此宣称真实后端浏览器流程通过。
- 该脚本 :35/45/46 的旧预览选择器与 :47 的“分析中”终态也需和当前页面核对；这些是既有脚本积欠，未据此判定生产功能故障。
- 修改脚本使其验证 DOC/PPT 原件上传、可补充提交与 pending_review，实际运行后保存证据。faults 脚本末行日志仍写 no ready no submit，实际断言已反转，宜同步描述避免误导。

## Stage 2

未完成：Stage 1 尚未通过，且主线程已开始修改快照。安全、结构、测试真实性及邻居页面现场视觉对比不得登记成完整 PASS。待新候选从 Stage 1 复核修复，再完成 Stage 2。

主线程收尾反馈：已修日期校验并补测试，已同步旧真实后端浏览器脚本但未执行；将重新固定快照并派独立 reviewer。本报告未对这些后续修复给出批准。
