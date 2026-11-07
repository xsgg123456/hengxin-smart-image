# 海外管理及任务轻量化独立复审 · 2026-11-07

## 快照、范围与结论

- candidateId：46c8a03fe017ef34f5958b83361741af490e6d6d59a4bacef962579cb188afbb。
- 范围：Product-Spec.md:1 同日条目、Design-Brief.md:1、DEV-PLAN.md:1、hengxin-smart-image/frontend/preview-overseas-light/；海外 management、tasks、archives 本轮服务端查询和路由、正式前端及 API、状态映射与测试；scripts/release/overseas-light-{runtime,package,deploy}.py 和相应发布测试。基线报告：docs/reviews/overseas-light-review-20261107.md:1。
- **Stage 1：FAIL**。3 项 MEDIUM，见下。**Stage 2：未执行**：Stage 1 未通过，不能登记两阶段 PASS。上轮 1 项 HIGH 和 3 项 MEDIUM 的复核情况单列，不代表本轮整阶段通过。
- 审查开始及报告写入前运行 review-status，currentId 均等于上述 candidateId，approved 为 false；审查期间代码快照未变。普通 Markdown 报告不属于代码快照。若后续代码修改，须重新 prepare 并按新 candidateId 从 Stage 1 复审。
- 本审查未修改业务代码、未提交、未部署、未访问生产。正式提交后的包构建与真实包交互、部署均待完成。

## Stage 1：发现

### S1-01 · MEDIUM · 正式任务列表缺少预览中的记录位置范围

**要求**：Product-Spec.md:21 要求顶部及底部分页、总数和位置。确认预览 frontend/preview-overseas-light/TasksPreview.vue:9 在底部显示当前范围，例如“1–20 / 47 条”，最后一页和空结果也有定义。

**实际**：正式 frontend/src/views/overseas/OverseasTasksPage.vue:38 仅显示总数和每页条数，:40 底部只有分页按钮，没有当前记录起止范围。frontend/tests/overseas-lightweight.browser.mjs:81 测页码及返回，没有断言该文本；output/playwright/overseas-light-live/tasks-mobile.png 可见底部分页按钮但没有范围。应补当前页范围并验证首页、末页和空结果。

### S1-02 · MEDIUM · 删除成品后归档人候选不随可见归档刷新

**要求**：Product-Spec.md:16 要求候选来自当前用户可见成品的真实归档事件，并保留既有删除行为。

**实际**：backend/app/overseas/archives/cleanup.py:71 在成品删除完成时删除其归档事件，archives/service.py:90 按剩余可见归档事件查询候选；但 frontend/src/views/overseas/OverseasArchivePage.vue:46 收到 deleted 仅调用 load，候选只在 :64、:69、:73 的初始或显式刷新路径加载。某人唯一一套可见归档被删除后，该人仍留在下拉，直到手动刷新或重挂载。

**独立复现**：以真实 SFC、模拟 API 和删除完成事件执行 frontend/output/review-archive-operator-observation.test.ts；archiveEmpty 为 true 表示模拟 API 的剩余归档为空，operatorCalls 为 1 表示仅初始候选请求，旧选项仍在：

~~~text
{"operatorCalls":1,"archiveEmpty":true,"options":["实际确认者"]}
✔ review observation: deleted archive does not refresh operators
ℹ tests 1
ℹ pass 1
ℹ fail 0
~~~

这是模拟交互，不是生产删除。应在删除完成时重新获取候选，并覆盖唯一归档删除、所选候选消失和请求失败。

### S1-03 · MEDIUM · 列表内删除任务后负责人候选不随可见任务刷新

**要求**：Product-Spec.md:20 要求候选来自当前可见任务中的实际负责人。

**实际**：frontend/src/views/overseas/OverseasTasksPage.vue:98 的列表内 deleted 回调只移除任务并可能调用列表 load，不刷新候选；:147 的 loadAssignees 仅由身份、权限、返回列表、全局刷新或手动刷新触发（:154）。后端 backend/app/overseas/tasks/queries.py:127 的候选来自当前实际任务。因此删除某负责人唯一可见任务后，直到上述刷新路径，旧候选仍会显示。此项为源码路径分析，未独立运行浏览器复现；应覆盖列表内删除唯一任务和已选负责人消失。详情页删除返回列表会触发路径监听，不能泛化为所有删除路径。

## 上轮四项复核

1. **源码到发布包的关联**：scripts/release/overseas-light-package.py:30 从固定 Git commit 的 frontend 归档到 frontend/output/release-build 下临时目录，分别执行 vue-tsc 和 Vite；:68 要求受审状态及干净提交，:74 检查生产基线为祖先，:95 收集该次构建。scripts/release/overseas-light-runtime.py:21 钉住 API image、:22 钉住 Git 基线 b8d0b57。隔离构建目录不在 node_modules。已有 output/overseas-light-release-build.log:1 显示构建完成，但主 Agent 明确该次是基线提交演练，不是当前未提交 candidate 的正式包。提交后的候选包仍须重建和实测。
   
   切换前 overseas-light-deploy.py:95 调用验包；overseas-light-runtime.py:58 检查 HTML 直接引用的 JS/CSS。独立合成坏包原始输出：

   ~~~text
   missing entry asset: RuntimeError Frontend entry asset missing
   lazy missing chunk: ACCEPTED
   ~~~

   第二行的合成 JS 包含 import("./missing.js")，但包内缺该延迟块，说明验包**不覆盖 JS 内动态引用的完整性**；没有证据表明本次真实构建缺块。主 Agent 已计划提交后本地启动真实包、复测三页并将缺失资源或页面异常判失败，这一步不得省略或冒称已完成。原来的任取未审 dist 缺口在源码路径上已修复；这不是对未来真实包的运行通过证明。

2. **改派后负责人候选**：OverseasTasksPage.vue:157 在返回列表时刷新候选；frontend/tests/overseas-lightweight.browser.mjs:85 模拟改派给原先无任务的人、返回并筛选。上轮改派问题的场景已覆盖；列表内删除仍有本报告 S1-03。
3. **历史 submitted 引导**：frontend/src/views/overseas/task-status.ts:21 显示“待开始分析”；OverseasPlans.vue:55 允许开始分析，backend/migrations/overseas/versions/0010_requirements_review.py:18 保留历史授权。浏览器脚本 overseas-lightweight.browser.mjs:84 验证列表文案。
4. **排队取消耗时**：frontend/src/views/overseas/admin/OverseasActivityPage.vue:80 对无开始时间的取消终态返回“未执行”，列表及抽屉均使用此函数（:24、:30）；overseas-lightweight.browser.mjs:78 覆盖两处。真实排队取消并统计的 PostgreSQL 用例另见下。

## Stage 1：逐条对照

| Spec 条目 | 结论与证据 |
| --- | --- |
| Product-Spec.md:7 合并入口、旧地址与权限 | 已实现。frontend/src/identity-main.ts:22 定义新路由和旧地址重定向；OverseasPortal.vue:49 按能力生成菜单；backend/app/overseas/management/router.py:12 要求 stats.read。overseas-lightweight.browser.mjs:67 验证旧 usage 地址跳转；未独立访问生产。 |
| :8 发起次数、幂等、状态、北京时间 | 已实现并有实测。backend/app/overseas/studio/service.py:60 对重复请求重放，:94 新建 job 与带实际 actor 的 turn；management/usage.py:30 按持久请求聚合；management/facts.py:21 处理时间边界；OverseasActivityPage.vue:51 生成北京时间自然日区间。独立 PostgreSQL 中 backend/tests/test_overseas_lightweight.py:16 真实发送、幂等重放、排队取消、重新发起，断言 1→1→2 次；:36 覆盖失败和日期边界。 |
| :9 未知历史、范围及保留 | 已实现。management/facts.py:51 在 stats.read 范围内外连接 turn；management/monitor.py:21 可返回空操作者，OverseasActivityPage.vue:3 和 :27 标记未知与删除边界；test_overseas_lightweight.py:42、:68 覆盖未知作业及角色范围。 |
| :10 人员、图片、停用及最近时间 | 已实现。management/usage.py:34 聚合请求、图片和最近时间；facts.py:56 候选不排除有记录的停用人；test_overseas_lightweight.py:38 检查停用、图片和最近时间。插入的图片 fixture 不能替代实际收费生成测试，本轮未进行模型调用。 |
| :11 四种状态、下钻、分页及详情 | 已实现已测范围。management/usage.py:12 将 collecting/cancelling 计入运行中；facts.py:39、:42 处理组及任务关键词；OverseasActivityPage.vue:59 概况查询无人员日期条件，:75 的人员下钻保留日期、状态下钻清空筛选。排队取消修复如上，management/monitor.py:25 返回脱敏错误文案。 |
| :15 归档人、组合搜索、分页前过滤 | 已实现服务端查询。archives/service.py:63 在 count/offset 前按真实事件 EXISTS 和关键词过滤，OverseasArchivePage.vue:4 提供可搜索筛选与更早参与提示；test_overseas_archive_audit.py:37 覆盖两名参与者及关键词。 |
| :16 候选、历史缺失、删除原任务 | 部分实现：初始候选来源和权限正确，但删除成品后有 S1-02。archives/audit.py:19 保存姓名快照，:31 标记历史不完整；OverseasArchiveDetail.vue:15 如实提示。test_overseas_archive_audit.py:47 覆盖删除原任务后归档、事件保留及无权访问。 |
| :20 当前负责人、改派、候选及范围 | 部分实现：改派后刷新已补，列表内删除有 S1-03。tasks/queries.py:84 依据 designer_id 及权限过滤，:127 取候选；OverseasWorkspace.vue:25 提供可搜索筛选，:54 展示负责人。test_overseas_lightweight.py:73 测停用、作用域及跨页。 |
| :21 20 条、两处分页、计数前过滤、位置与返回 | 部分实现：S1-01 缺当前条目范围。tasks/queries.py:84 至 :122 在总数/offset 前应用条件；OverseasTasksPage.vue:37、:40 放置两处 20 条分页，:94 发服务端参数；overseas-lightweight.browser.mjs:85 测详情返回原页。 |
| :22 三类、旧流程、删除异常 | 已实现已测范围。tasks/queries.py:77 定义状态组并排除删除中任务进入普通组；frontend/src/views/overseas/task-status.ts:7 对应显示和引导，OverseasWorkspace.vue:51 显示删除错误；test_overseas_lightweight.py:86 覆盖 reworking、删除异常及历史 submitted。 |
| :23 归档不自动完成、显式完成/解冻 | 源码匹配。backend/app/overseas/studio/service.py:123 归档后仅 finish，:162 显式完成并检查活动作业，:180 解冻回 studio。本轮未操作生产。 |
| :25–:27 视觉、测试及部署验收 | 未完成。三页正式源码本地模拟 API 截图在 output/playwright/overseas-light-live/，确认预览在 output/playwright/review-light-preview-*.png，均为 1280×900；白底卡片、蓝色操作、筛选和表格布局可对照，数据和状态不同，不作像素完全一致结论。预览 preview-overseas-light/style.css:5 至 :9 的状态间距 18px、数字 18px、日期筛选 300px、成品卡最小 420px 与正式 OverseasActivityPage.vue:94、:103 和 OverseasArchivePage.vue:78 一致。预览额外横幅在正式移除符合 Design-Brief.md:3。浏览器脚本 overseas-lightweight.browser.mjs:102 仅断言三页 390px 筛选控件可达；正式任务状态及提示横滚到末端未由该脚本独立断言，仍须实测。生产只读身份、最终真实包浏览器及部署均未执行。 |

**范围漂移**：本范围新增 /management/people、/task-assignees、/archive-operators，分别对应获准需求，见 management/router.py:23、tasks/router.py:34、archives/router.py:28；未发现额外产品页面。此结论只针对派发范围，不代表全仓功能扫描。

**发布与回退静态边界**：overseas-light-deploy.py:195 先关闭入口、等待旧请求，仅切换海外 API 后安装前端；:221 错误时先关闭入口、恢复前端、恢复旧 API 并确认 ready 后开放。skill-platform-runtime.py:61 检查其他容器及 native 单元身份；overseas-light-deploy.py:102 检查数据库 schema 版本。独立发布单测覆盖模拟前端切换失败和停止未确认路径，不等同生产中真实服务、数据内容或在途作业保全验证。

## 独立验证原始输出

1. 后端 SQLite：backend 目录运行 .venv/Scripts/python.exe -m pytest -q tests/test_overseas_lightweight.py tests/test_overseas_archive_audit.py tests/test_overseas_management.py tests/test_overseas_management_operators.py tests/test_overseas_tasks.py，exit 0：

~~~text
....................................................                     [100%]
52 passed, 2 warnings in 21.06s
~~~

2. 临时 PostgreSQL 17 容器、独立 review_light_test：backend 目录运行 .venv/Scripts/python.exe -m pytest -q tests/test_overseas_lightweight_postgres.py，exit 0，容器已停止并自动删除：

~~~text
....                                                                     [100%]
4 passed, 2 warnings in 5.64s
isolated-container-cleaned 7b4eb3a21ca4012f1ec75b2f058eb35383f45b1fa4edffe7ea9113fc9d1c3df3
~~~

3. 发布脚本隔离测试：仓库根目录运行 backend/.venv/Scripts/python.exe -m pytest -q scripts/release/test_overseas_light_release.py，exit 0：

~~~text
...                                                                      [100%]
3 passed in 1.85s
~~~

4. 前端运行 node node_modules/tsx/dist/cli.mjs --test tests/*.test.ts，exit 0，原始汇总：

~~~text
ℹ tests 529
ℹ suites 0
ℹ pass 529
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 14627.641
~~~

5. 正式和预览类型检查：分别运行 node node_modules/vue-tsc/bin/vue-tsc.js --noEmit 与 node node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p preview-overseas-light/tsconfig.json，两次 exit 0，原始 stdout/stderr 均为空。没有在当前工作树运行 Vite dev/build。

6. 主 Agent 提供的基线隔离 Vite 构建日志 output/overseas-light-release-build.log:1 的原始首尾：

~~~text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 4822 modules transformed.
...
✓ built in 37.69s
~~~

此日志不是提交后当前 candidate 的正式包证据。运行真实包、真实身份下的只读接口及生产切换验证仍由主 Agent 后续执行。

## Stage 2

**未执行**。上述代码位置、模拟与构建证据用于 Stage 1，不代表代码质量、安全扫描、测试真实性及邻居页面视觉对照的完整 Stage 2 PASS。修复 S1-01 至 S1-03 后重新固定快照，从 Stage 1 复审；两阶段均通过才由主 Agent使用 review-approve 登记同一 candidateId。

