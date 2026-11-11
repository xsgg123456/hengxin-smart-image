# 国内调用与执行独立预览审查 · 2026-11-11

## 结论与快照边界

- **Stage 1：PASS（仅下述预览范围）。Stage 2：PASS（仅下述预览范围）。** 未发现该独立预览合同内的 HIGH / MEDIUM 阻断问题。
- 收到的 candidateId：`b77584a015bdae5db9fa3505f5acb75bf0a21e5c356c6e3c4efa41deb6451a24`。审查开始时 `review-status` 返回相同 currentId。
- 审查结束时全仓 candidate/currentId 已变为 `75a326324d594b92f5009ba012e322c811d8648e85912a2d461118f31e243de4`。并行流程已覆盖 review-state 内旧 candidate；不能声称已做旧/新完整候选的逐文件哈希比对。预览代码当前内容与本次逐行审查内容一致，最终受审范围摘要为 `8081ae589223e08e8106d9dc57d50e7c9d5a5247dd3c91535f12a5804c320647`（harness identity 算法）。结论以文末明确文件摘要为准，不扩展到新全仓候选。
- 范围：`hengxin-smart-image/frontend/preview-domestic-activity/` 内 10 个代码/配置文件，以及 README 预览合同。下文短文件名均相对此目录。
- 排除：正式业务实现、生产权限与数据、历史待核对入口移除、Product-Spec/CHANGELOG 的另行记录，以及并行 `scripts/maintenance/install_panel.py`、`scripts/maintenance/test_install_panel.py`、`docs/INTRANET-1PANEL-20261111.md`。本报告不能用于批准整个全仓候选。
- 主 Agent 明确不做全仓 review-approve、不提交、不部署。Reviewer 未修改实现、未写 clean、未批准快照。README 的验证记录在审查中追加，未改变第 1–6 项合同。

## Stage 1 · Spec Compliance

适用源：README 第 3–11 行是本次独立预览合同。Product-Spec.md 第 1–5 行明确历史待核对仅记录待实施；国内合并方案仍待确认。既有 Design-Brief 的组件继承要求通过真实组件和基准页面核验，未把海外已批准功能误当作国内正式实施授权。

| 合同项目 | 结论与代码证据 | 行为证据 |
| --- | --- | --- |
| 1. 真实 Shell、品牌、导航、页签、主题 | 完整实现。App.vue:2、5、12–13 直接使用 OverseasShell 与 ArtPageContent；main.ts:19–21 使用真实样式，26–49 创建预览身份、菜单与路由。`src/views/overseas/OverseasShell.vue:4–10` 直接组合 ArtSidebarMenu、ArtHeaderBar、ArtGlobalSearch；沿用国内布局样式。 | 实际打开合并页及两个基准页面；1920 截图和独立 computed-style 比对见下节。 |
| 1. 原版对照直接渲染 | 完整实现。main.ts:16–17、46–47 导入原版 ApiUsage.vue / monitor.vue；vite.config.ts:7–10 将其两个 API 模块仅在预览配置内映射至 baseline-api.ts。 | 浏览器原版标题、累计图片卡、监控表均真实渲染；独立打开原版人员每日明细抽屉成功。 |
| 2. 单入口、默认人员、同页执行记录 | 完整实现。main.ts:38 仅一个调用与执行菜单；Activity.vue:10、24–36、47 默认 people，可切换 jobs。 | 默认 6 人人员表；下钻自动切换执行记录。 |
| 2. 共享人员/北京时间日期/生成类型 | 完整实现。Activity.vue:12–19、54–58；data.ts:17 记录含 +08:00，27–28 按该北京时间日期筛选。 | 主测试：林晓 8 条→示例今日 2 条→CLI 1 条。独立补测：先选近 7 天和首次生成，再点陈佳，下钻保留日期及类型，4 条匹配记录。 |
| 2. 状态清空其他条件、范围显式 | 完整实现。Activity.vue:5、19、62–64；顶栏明确全部人员、全部时间、条执行。 | 主测试执行中下钻清空条件且显示 4 条；独立补测当前失败下钻清空人员/日期/类型，范围显示失败，1 条记录。 |
| 3. 执行条数、进行阶段合并 | 完整实现。Activity.vue:61 按记录计数；data.ts:25 将 running/collecting/cancelling/retry_wait 归执行中。 | 默认排队 1、执行中 4、待核实 1、当前失败 1；执行中列表恰为 4 条。 |
| 3. API 与已启动 CLI 分列 | 完整实现。data.ts:26 API 记录与具有 startedAt 的 CLI 轮次独立求和；Activity.vue:10、23、26 文案与单位独立，未相加冒充模型调用数。 | 现有示例总数 API 36 次、CLI 12 轮；人员行分列与总数一致。仅证明该内存模型，未证明真实执行账本映射。 |
| 3. 人员/记录生成数可对账，首次+修改 | 完整实现。data.ts:22、26 仅成功记录含新图数，汇总同一 images 字段；Activity.vue:54–58 共用过滤源；采用/恢复无重复增加路径，统计说明明确排除。 | 人员图片分别 6、9、7、11、7、10，和为 50；原版适配器显示首次 20 + 修改 30 = 50。不以采用/恢复模拟记录验证生产账本。 |
| 4. 任务及服务抽屉、低层信息收纳 | 完整实现。Activity.vue:34、39，Details.vue:2–5；阶段、并发配置、心跳信息在服务抽屉。 | 执行详情和服务详情实际打开；失败任务对应错误文本显示，关闭可回列表。 |
| 4. 服务未知不可伪装在线/零 | 完整实现。Activity.vue:6–7，Details.vue:5 区分未知、不可用；错误/加载阶段使用未获取/更新中，不以服务未知推导在线。服务表的数值来自独立已知队列示例，不将未知心跳当零。 | 服务异常场景 API 未知、CLI 不可用；抽屉显示未收到有效心跳说明。 |
| 4. 模拟标记、手动刷新反馈 | 完整实现。App.vue:3–4 标注预览/示例数据；Details.vue:2、4 标注演示；Activity.vue:20、52、66 为刷新提供 500ms 骨架与 loading 状态。 | 独立实际点击刷新，验证正在读取数据可见，随后列表恢复。 |
| 5. 五类场景 | 完整实现。data.ts:2–3，App.vue:4，Activity.vue:20–23、52–53、66。 | 主测试覆盖正常、空、骨架加载、加载失败及重试恢复、服务异常；零浏览器运行错误。 |
| 5. 筛选/搜索/分页/日期/详情/对照 | 完整实现。Activity.vue:12–17、36、55–56、67；搜索明确处理任务名称及执行 ID。 | 主测试验证第一页20/第二页20、搜索空状态；独立补测第三页8条、DEMO-1048搜索唯一记录且页码重置；原版调用明细可打开。 |
| 5. 不实现成员或历史待核对移除 | 完整实现范围约束。main.ts:33、45 非本次菜单使用明确的预览占位说明；未载入成员页。 | Git 范围中正式成员组件未修改。占位页明确聚焦调用与执行，不宣称已实现相关管理能力。 |
| 6. 内存数据、无代理/生产API/生产写入 | 完整实现。data.ts:12 创建48条数据；baseline-api.ts:15–34 为本地计算；vite.config.ts:5、8–15 使用 demo 和隔离配置；main.ts:24 没有注册持久化插件、44–48 替换真实路由。 | 独立浏览器 reload 后整个交互流程共299个请求，`/api/` 请求0、pageerror 0；外部仅 Iconify 图标JSON，见安全范围说明。 |
| 6. 不正式实施、不改正式业务文件、不提交部署 | 本范围符合。新入口与构建输出均独立（vite.config.ts:15），正式原版文件仅导入。Spec/CHANGELOG 的历史待核对记录是主Agent说明的另一授权事项，不视为此预览正式需求。 | `git status` 正式前端业务文件无修改；本审查未执行提交、发布或生产操作。 |

**部分实现：无。未实现：无（按本次独立预览合同）。Spec 漂移：无。** 原版按钮、示例场景控件和非本次菜单占位均属预览支撑，不新增正式业务功能。Stage 1 通过后进入 Stage 2。

## Stage 2 · Code Quality

### 代码与安全

- ✅ 类型与结构：data.ts:5–9 使用 Kind/Status/RecordItem；Details.vue:11–12 的 props/事件有类型；未发现 `any`。各文件为 1–69 行，未超过300行；Activity 管理交互、Details 管理抽屉、data 管理内存语义、baseline-api 管理原版适配。Activity.vue:65–68 清理刷新计时器并重置依赖筛选的页码/抽屉。
- ✅ 错误处理：Activity.vue:20–21、66 明确加载、失败、重试恢复；不可把未知数据展示成0。App.vue:17 对真实业务切换/退出按钮提供明确未连接说明，避免误报真实操作完成。
- ✅ 安全扫描：对该目录扫描 eval、dangerouslySetInnerHTML、innerHTML、前端密钥变量、sk-ant/sk-proj、OpenAI/Anthropic密钥、绝对用户路径、any、fetch、axios。仅 README 的本地 URL 命中，无动态代码执行、密钥、请求调用或注入拼接。Vue 文本插值用于任务/错误展示（Details.vue:2）。
- ✅ 隔离：配置复用 `frontend/vite.config.ts` 的 demo 无代理和 isolatedPreview 禁止生成声明文件逻辑；新配置别名只影响本入口（vite.config.ts:5–15）。真实路由守卫未调用 initRouter，预览 main.ts:44–50 重建路由且使用预览数据适配器。
- 信息说明：并非完全离线。真实 `src/components/core/base/art-svg-icon/index.vue:3、7` 使用 Iconify；独立网络实测发现 `https://api.iconify.design/` 的5个图标JSON请求。未发现生产业务请求或写入。这符合“无生产API”，不得扩写为“零外网请求”。
- LOW 可维护性建议：Details.vue:2、5 与 Activity.vue:5、10、31–34 有较长单行模板。后续正式实施时适合展开格式化以便审查；此预览未因此产生功能问题，不要求为此改变已验快照。

### 测试真实性与边界

- ✅ `output/domestic-activity-preview/browser-check.js:1` 通过可见控件执行完整交互，21项结果来自 `browser-results.txt:1`；包含故障/恢复、空/加载/异常路径，不只验证纯函数。
- ✅ reviewer 独立 session `review-domestic` 补测10项；脚本 `output/playwright/domestic-review.js:1`，原始结果 `output/playwright/domestic-review-results.txt:1`。额外覆盖日期类型保留下钻、刷新反馈、失败详情、分页末页、ID搜索、原版详情、较宽网络监听范围。
- ✅ 原版与新版使用同一内存源，可核对示例数字；这是预览的有效前提。未验证生产 API 契约、真实鉴权、真实心跳、真实执行账本、生产历史归属、取消或重试写入能力。没有把这些未实现/未测能力声称为已验证。
- 主Agent布局脚本首轮点击被 Element Plus 原生 radio 的可见 span 拦截；修正为点击 label 后重跑，最终 `layout-results.txt:1` 成功。这是测试定位修正，未据旧失败日志误报实现故障。Reviewer首次文本断言也修正为归一DOM换行后重跑。

### 视觉与布局

Reviewer 实际打开合并页、原版调用统计、原版执行监控，并查看三张稳定桌面截图及390窄屏截图；独立提取渲染值（`output/playwright/domestic-review-visual.js:1` / `domestic-review-visual-results.txt:1`）：

| 1920×911 实测项目 | 合并页 | 调用统计原版 | 执行监控原版 |
| --- | --- | --- | --- |
| 标题左坐标 | 259px | 259px | 259px |
| 标题字号/字重/颜色 | 28px / 650 / rgb(56,56,83) | 相同 | 相同 |
| 主色 | #5D87FF | 相同 | 相同 |
| 卡片内边距/圆角 | 23px / 16px | 相同 | 相同 |
| 标题区域刷新按钮高度 | 32px | 无该按钮 | 32px |

证据对应 Activity.vue:2–9、main.ts:19–21、style.css:4–11；共同定义位于 `src/views/hengxin/prototype.css:2–8`。白底卡片、字体层级、蓝色操作、边框、真实侧栏和页签一致；合并页的信息密度变化来自合同内的信息合并及详情收纳。不是声称两个不同信息结构逐像素相同。

布局脚本实际文档宽度为1920/1280/390，等于各视口宽度；概况、服务、筛选、汇总区左右边界分别283–1868、283–1228、41–349。390宽表格内部横向滚动、操作列固定；页面没有水平溢出。截图：`output/domestic-activity-preview/merged-1920.png`、`merged-1280.png`、`merged-390.png`、`baseline-usage.png`、`baseline-monitor.png`。代码依据 style.css:11 与真实 ElTable。

### 编译原始结果

Reviewer 独立运行：

```text
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p preview-domestic-activity/tsconfig.json
exit_code: 0
stdout: （空）
stderr: （空）
```

主Agent提供的最终完整构建日志已读取，`output/domestic-activity-preview/build.log` 原始末尾节选：

```text
dist-preview/domestic-activity/assets/index-DGOzK7hw.js                                              30.65 kB │ gzip:  10.27 kB
dist-preview/domestic-activity/assets/index-DZ-OV1no.js                                              78.15 kB │ gzip:  31.12 kB
dist-preview/domestic-activity/assets/index-F0-TJWfI.js                                             896.46 kB │ gzip: 303.06 kB
✓ built in 21.48s
```

命令：`node node_modules/vite/bin/vite.js build --config preview-domestic-activity/vite.config.ts --mode demo`。此处区分 reviewer 独立类型复跑与已检查的主Agent构建证据，不声称 reviewer 另跑第二次构建。

## 最终受审文件摘要

以下 SHA-256 按 harness 的 UTF-8 CRLF→LF 归一算法生成，模式均 `100644`；摘要仅对应预览目录当前完整受审内容。

| 文件 | SHA-256 |
| --- | --- |
| Activity.vue | 0c8acaf44dc039c93d2511bc5044c220649236660db49f5ba9113dd72dc0376b |
| App.vue | 729a0b3ac6de7c3e33a9448fef15a5b4a36e678c64b7f7c3b2c4c533a17e07cd |
| Details.vue | 5414fc64cec7966021052a6e18b6a1430ca12c6d7b352c539b207dcc44ff2ba9 |
| baseline-api.ts | 1dcd4e43291697603367d58fb468c87b0ac4e409eb0fadebc4aaea907b616a57 |
| data.ts | a81a4e1a2ec809b2c5443b584506fb3980326de81a622c41f009855cdf143309 |
| index.html | 6f3df26c65153f74a0616765286bd3142e2a51ddcc2600a86ce1495010d3f98a |
| main.ts | 0d29cb3d9479111a2e9a840d45c3a88d14c49a1836f252f93b99fe2081bb4e81 |
| style.css | d504fd61b0158be98bd05fc490a58641cce2c5efe1fcaca674ae04bfaa473f82 |
| tsconfig.json | 512e72d22af0c763c1054bf3796efeb52f93de3da5cda08b8d29fa05ea8a23e8 |
| vite.config.ts | 8ed075055a425a2f28aec9d0ce0d6590992b98c4bfe10e58d40a6ea3c865df64 |

本报告仅确认该可交互预览可供用户评审设计，不能代替正式实施验收、生产数据验证或全仓快照批准。
