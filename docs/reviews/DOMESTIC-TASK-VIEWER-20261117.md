# 国内任务中心只读浏览优化独立审查

- 日期：2026-11-17
- candidateId：`9bffde69c80fd48a83d329dbf7f4f5fa11373ef0285abfabfc79e35009041992`
- Stage 1：**PASS**
- Stage 2：**PASS**
- 发现：HIGH 0，MEDIUM 0。没有需要修复的阻断项。
- 审查者：独立 code-reviewer；采用 `.agents/skills/code-review/SKILL.md` 和 `docs/HARNESS-REVIEW.md`。只审查与写报告，未修改产品代码、提交或登记批准。

## 范围与快照

源合同为 `Product-Spec.md:1` 本次章节的四条需求、`Design-Brief.md:1` 浏览补充及 `DEV-PLAN.md:1` 四步安排。审查范围：管理任务会话四个 Vue 组件、管理样式与新增资源适配器，共享 StudioAssetImage、studio-images、use-image-viewer，相关新增/修改测试和 `frontend/package.json:3` 版本 0.2.77。以下前端路径以 `hengxin-smart-image/frontend/` 为根。

审查开始与结束执行 `review-status`，currentId 均等于以上 candidateId。过程中主 Agent 将本次普通 Markdown 章节从文末移至顶部并补验证文档；代码快照未变。`studio-download.browser.mjs` 虽出现在工作区状态中，`git diff --numstat` 无内容差异，不属于受控候选变化。报告不批准任何后续不同代码快照。

## Stage 1：需求完整性

| 需求与结论 | 代码证据 | 验证证据 |
| --- | --- | --- |
| 完整实现：展开占满视口，保留会话、成员/业务和只读提示 | `src/views/hengxin/admin/workspace-sessions/ManagedTaskWorkspace.vue:2`、`:19` 保存状态；`SessionDetail.vue:3`、`:5`、`:11` 保留工具、侧栏和提示；`style.css:11` fixed/inset/100dvh | `tests/workspace-viewer-browser-helpers.mjs:13` 验证1920×1080边界、可达按钮和页脚；实看展开桌面截图 |
| 完整实现：展开退出不重载，阅读位置不重置，同任务切方案保持展开，自动同步保持 | `ManagedTaskWorkspace.vue:6` 只绑定展开状态，`:22` 限定任务内会话；`SessionMessages.vue:30` 保留原滚动跟随；`use-monitor.ts:70` 保留同步 | helper `:17` 同任务切换、`:19` 详情请求计数不增加、`:39` 长内容120px位置两次切换保持；`workspace-sessions.browser.mjs:97` 真实定时器轮询验证 |
| 完整实现：用户附件与每轮结果卡片继承正常工作台 | `ManagedAsset.vue:2` 使用 studio-image-file/studio-picture；`:3` 复用 StudioAssetImage；`SessionMessages.vue:8`、`:16` 每轮传入独立组 | 实看管理展开截图与正常工作台 desktop；附件80px、结果128px沿用现有卡片规则，蓝色按钮、浅色边框、白色卡片一致 |
| 完整实现：按轮/标签分组，非图片不混入序列 | `SessionMessages.vue:8`、`:16` 分离附件/结果；`SessionDetail.vue:14`、`:30`、`:31` 分离抽屉标签；`StudioAssetImage.vue:22` 使用 isImage 过滤；`studio-images.ts:14` 图片类型判定 | helper `:23` 三张结果依次导航、`:47` 两张附件组、`:53` 抽屉结果3/3；`workspace-sessions.browser.mjs:192` SVG无预览且无缩略请求。多轮边界另由每轮参数代码逐项确认，测试fixture仅一轮，不冒称多轮实测 |
| 完整实现：点击/Enter/Space、文件名/序号、左右切换、缩放、拖动、Esc和原图下载 | `StudioAssetImage.vue:2` 键盘入口，`:6` 同一ElImageViewer，`:8` 进度/文件名/下载；`managed-image-access.ts:10` 原件下载 | helper `:22`—`:38` 检查导航、真实图片解码、缩放/拖动transform变化、下载事件文件名和关闭位置；`:47`—`:48` Enter/Space |
| 完整实现：查看器覆盖展开区域及抽屉，关闭回原处 | `style.css:11` 展开z-index 2000，`SessionDetail.vue:14` 抽屉4000，`StudioAssetImage.vue:6` teleported查看器6000 | helper `:54` elementFromPoint验证实际层级，`:55` Esc先关闭查看器且抽屉仍在；`:38` 阅读位置相同；实看390查看器截图 |
| 完整实现：缩略、原图、下载走管理授权GET，无写操作 | `managed-image-access.ts:4`、`:19` 委托现有readManagedAsset；`src/api/hengxin/workspace-sessions.ts:53` 校验管理地址、include/no-store/redirect:error、失败抛IdentityError；`ManagedAsset.vue:3` 注入适配 | 独立复跑单测验证GET参数与拒绝海外URL；构建浏览器报告111个业务请求全部GET；`workspace-sessions.browser.mjs:46` 拒绝非GET，`:188` 无文本框及发送/停止/删除/归档等操作 |
| 完整实现：撤权清除、切会话/卸载取消及URL回收，迟到响应不得回填 | `StudioAssetImage.vue:27` watch cleanup中止缩略请求并release，`:35` 拒绝迟到lease；`use-image-viewer.ts:12` close取消并回收，`:22` epoch与signal保护，`:48` 组变化关闭，`:49` 卸载关闭；`ManagedAsset.vue:31` 下载中止；`managed-image-access.ts:6` aborted不创建URL、`:16` 下载后延迟1秒回收 | 独立单测 `managed-image-viewer.test.ts:12` 检查全部分配URL被回收及卸载后迟到不分配；helper `:69` 预览403后查看器/消息/资产全部移除；`use-monitor.ts:15` 和 `ManagedTaskWorkspace.vue:23` 错误上抛清除；浏览器同时覆盖迟到详情与401 |
| 完整实现：桌面/390无横向溢出，侧栏与消息独立滚动，退出/图片操作可达 | `style.css:8` 会话列表独立overflow，`:11`—`:12` 展开flex/min-height/窄屏规则；`SessionMessages.vue:2` 消息滚动容器 | helper `:60` 检查1000与390视口横溢出、退出、刷新、只读页脚和下载按钮；实看390展开及图片查看器截图 |
| 完整实现：正常工作台默认行为、同步、身份锁回归 | `StudioAssetImage.vue:26` 未传access仍用原thumbnailUrl，`:42` 管理适配与原HEAD重试分支分离，`:57` 原下载保持；`use-image-viewer.ts:21` 默认仍走overseasImageCache | `studio-viewer-regression.browser.mjs:74` 起验证ZIP字节/数量/重名、两图原图导航、故障重试、切会话取消及窄屏；管理浏览器报告五业务隐藏恢复/401/静默同步共16组通过 |

部分实现：无。未实现：无。死引导：未发现；空态只说明暂无已提交内容，失效/失败可刷新或重载，不引导管理员修改业务（`ManagedTaskWorkspace.vue:8`、`SessionMessages.vue:3`、`StudioAssetImage.vue:9`）。

Spec 漂移：无新增页面、后端API、数据库或依赖；资源适配是授权要求内的实现，原角色及管理API契约保持。`DEV-PLAN.md:8` 提交与生产部署属于主 Agent 下一步，尚未完成，未将其计为本地验收通过。

## Stage 2：质量、安全、测试真实性

- 代码结构与类型通过：新增适配器23行，只负责授权读取/Blob生命周期；变更产品文件14—69行，均未超过300行；测试文件也未超300行。共享可选接口有明确StudioImage/ImageLease/AbortSignal类型，无新增显式any（`studio-images.ts:7`、`managed-image-access.ts:4`、`use-image-viewer.ts:7`）。
- 错误处理通过：缩略、原图与下载错误沿failure事件上抛；401/403使父级清内容；普通503保留内容并支持重新加载（`StudioAssetImage.vue:37`、`:58`，`use-image-viewer.ts:24`，`use-monitor.ts:15`）。未发现资源缓存绕过管理授权；正常工作台原缓存失效和HEAD路径保留。
- 安全扫描通过（本次变更范围）：扫描eval、innerHTML、dangerouslySetInnerHTML、暴露的VITE密钥变量、已知密钥前缀和绝对用户目录，未命中新增危险项。`AbortSignal.any`为组合信号方法，不是any类型。URL受现有管理路径白名单和禁止重定向保护（API文件`:54`—`:55`），文件名通过文本/属性和download属性使用，无字符串HTML注入。
- 测试真实性通过：本次浏览器运行真实Vue/Element组件并拦截HTTP，不是静态预览；加载断言要求blob图片complete且naturalWidth>1，拖动/缩放校验transform，下载检查浏览器download事件，ZIP回归检查实际字节。单测注入一个忽略abort的迟到fetch，实际验证回填防护（helper `:10`、`:27`，`managed-image-viewer.test.ts:35`）。
- 边界如实记录：浏览器HTTP数据和401/403均为隔离故障响应，证明前端处理，不代替本次重新实查真实后端权限；隐藏/恢复由visibility生命周期驱动，不是OS实际切页。单元测试的正常下载成功由浏览器下载事件补足；普通工作台ZIP测试有字节比对，管理单张下载只有事件和文件名验证。未宣称生产已部署。
- 实际视觉对比通过：独立打开并查看 `output/playwright/task-viewer/viewer-expanded-desktop.png`、`viewer-expanded-390.png`、`viewer-image-390.png` 与 `output/playwright/studio-viewer-regression/normal-image-viewer.png`、`desktop.png`。卡片/字体/蓝色工具按钮继承相邻工作台；窄屏工具栏换行、侧栏与消息分区且底部只读条可见，查看器关闭/导航/下载可见。正常desktop中503提示属于测试故障注入后遗留提示，后续下载成功有断言，不能当本次新增缺陷（普通回归脚本`:89`）。

## 验证与原始输出

审查者独立执行 `pnpm exec tsx --test tests/managed-image-viewer.test.ts`，退出0：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
✔ 管理预览逐次GET核权、切图和关闭回收URL、失败重试及会话卸载拒绝迟到图 (40.7977ms)
✔ 管理图片下载使用原件GET且拒绝其他作用域和中止响应 (1.5314ms)
ℹ tests 2
ℹ suites 0
ℹ pass 2
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 796.1843
```

审查者独立执行 `pnpm exec vue-tsc --noEmit`，退出0，原始输出仅有以下包管理器警告，无类型错误：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
```

主 Agent 全量测试日志 `output/task-viewer-unit.log` 已读取，原始汇总：

```text
ℹ tests 599
ℹ suites 0
ℹ pass 599
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 27044.2188
```

国内production构建日志 `output/task-viewer-build.log` 已读取；未由审查者重复构建，原始关键输出：

```text
🚀 API_URL = /api/v1
🚀 VERSION = task-viewer-validation
vite v7.1.7 building for production...
transforming...
✓ 4937 modules transformed.

(!) outDir D:\Work_Project\hengxin-smart-image\output\task-viewer-build is not inside project root and will not be emptied.
Use --emptyOutDir to override.
✓ built in 36.69s
```

另有既有静态/动态导入混用提示（dingtalk-login），构建成功；完整警告保留在原日志，不宣称构建零警告。

主 Agent 的实际浏览器证据已读取并对照脚本断言：开发服务 `output/playwright/task-viewer/report.json` 为PASS/16组/112业务GET；生产构建本地预览 `output/playwright/task-viewer-build/report.json` 为PASS/16组/111业务GET，errors和unexpected为空。请求数因定时器次数不同，不是固定验收计数。普通工作台日志 `output/task-viewer-normal-browser.log` 原始输出：

```text
PASS: 正常工作台分组原图查看、键盘切换、下载ZIP字节校验、失败重试、切会话取消及桌面/窄屏布局
```

旧studio-download浏览器脚本的过期平台选择表单超时不计PASS；此次用独立普通工作台图片脚本覆盖变更影响，未用删除旧断言来获得通过。

## 交接

本候选两阶段PASS，可由主 Agent 对同一candidateId执行review-approve，再进入已授权中文提交及国内前端发布。生产服务器版本、正式入口权限、海外/共享保持及两版清理仍须后续发布验收，不能以本报告替代。
