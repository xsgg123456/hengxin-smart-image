# 国内合并页服务诊断移除审查

- 日期：2026-11-11。
- candidateId：`43b908341cc78cb11a36927004240bb9c4876c1713ac9042b133f19f5e2017fd`。
- 结论：**Stage 1 PASS；Stage 2 PASS**。本轮范围没有 HIGH / MEDIUM 阻断项。
- 审查依据：`.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、`Product-Spec.md:5` 至本节末、`Design-Brief.md:1`、`DEV-PLAN.md:1`。已读取实际源文档、差异、测试脚本和日志，并独立运行类型检查、打开页面对照截图。
- 范围：`hengxin-smart-image/frontend/package.json` 版本 0.2.69，以及 `src/views/hengxin/admin/` 下 `activity.vue`、`use-activity.ts`、`ActivityDetails.vue`、`activity.css`。下表短文件名均指该目录。源文档同步另含 Product-Spec、CHANGELOG、Design-Brief、DEV-PLAN。
- 此报告批准上述代码实现；固定提交的正式 Vite 构建、frontend 模式生产发布和真实入口验收由主 Agent 后续执行，不能用本报告宣称已发布。

## Stage 1：Spec Compliance — PASS

| Spec 条目 | 结论与证据 |
| --- | --- |
| 删除 API/CLI 服务状态、服务更新时间 | 完整实现。`activity.vue:4` 顶部卡片仅含当前执行；原 service-strip 整段已删除。独立浏览器快照显示四项计数及范围，不含服务标签/更新时间。 |
| 删除服务详情入口及抽屉 | 完整实现。`activity.vue:37` 仅传 selected；`ActivityDetails.vue:2` 至 `:20` 仅剩执行详情，serviceOpen、monitor、close-service 接线和第二个 Drawer 已删除。浏览器脚本 `output/domestic-service-removal/e2e.js:34` 对入口与服务条消失作断言。 |
| 删除对应黄色提醒和监控错误提示 | 完整实现。`activity.vue:4` 至 `:8` 已无监控 Alert；`use-activity.ts:6` 不再有 monitorError；页面无“执行服务状态需要关注”。单条执行异常 Alert 按 Spec 保留，见 `ActivityDetails.vue:10`。 |
| 停止本页 api-monitor 请求 | 完整实现。`use-activity.ts:1` 至 `:3` 无监控 import；`:25` 刷新只 load，`:31` 挂载走 refresh；原 loadMonitor 全部删除。该四个实现文件检索 api-monitor/getApiMonitor/serviceOpen/monitorError 无命中。`e2e.js:2` 在导航前注册 request 监听，`:35` 断言零监控请求；结果 JSON 为 monitorRequestCount=0。 |
| 顶部四计数与点击筛选保留 | 完整实现。`activity.vue:5` 保留四按钮及加载/错误时破折号与禁用态；`:48` 四状态；`:54` 仍取 report.live。`use-activity.ts:24` 清空其他条件并设置 currentOnly。浏览器显示排队2、执行0、待核实0、当前失败0；`e2e.js:18` 至 `:20` 验证下钻2条且未启动队列不计调用。 |
| 人员统计、执行记录、共享筛选、分页和当前范围保留 | 完整实现。`activity.vue:8` 至 `:34` 的两视图、筛选、表格、20条分页未变；`use-activity.ts:15` 至 `:17` 参数未变，`:22` 至 `:29` 保留人员下钻、筛选重置与请求代次保护。浏览器证据验证34条、20/14分页、关键词空态与历史失败1条；无前端静态演示数据替换。 |
| 时间、耗时、图片与脱敏异常执行详情保留 | 完整实现。`ActivityDetails.vue:5` 至 `:11` 保留操作者、状态、提交/开始/结束时间、耗时、图片与异常。实际打开详情并检查“未关联”见 `e2e.js:14` 至 `:17`。脱敏沿用未改的 `backend/app/modules/management/activity_records.py:37` safe_error 及 `:55` 调用；没有改为显示原始服务异常。 |
| 统计手动刷新、加载、错误重试和空态保留 | 完整实现。`activity.vue:3` 刷新；`:17` Skeleton；`:18` 错误及重新加载；`:21` 与 `:27` 两表空态。`use-activity.ts:11` 至 `:20` 仍清旧报告并处理失败，`:25` 刷新数据。`e2e.js:28` 至 `:33` 注入503、验证统计消失、撤销故障并重试恢复真实数据。 |
| 日期、调用、图片、人员和当前/历史状态口径保留 | 完整实现。`activity.vue:8` 说明、`:20` 汇总、`:31` 发起时间及 `use-activity.ts:15` 至 `:17` 查询参数均无变化，后端无本轮差异。只删除独立监控请求，不改变 activity 查询/事实计算。先前实现和口径详审见 `docs/reviews/DOMESTIC-ACTIVITY-RELEASE-20261111.md`，本次不冒充重新跑全量后端。 |
| 单入口、旧路由和成员页保留 | 完整实现。本轮无路由/菜单/成员实现差异；`e2e.js:36` 验证 usage、monitor 均跳 activity，`:37` 至 `:39` 验证成员仅2标签并可切加入申请。独立打开成员页见邻居截图。 |
| 后台监控API、心跳、执行器及海外保持 | 完整实现（代码边界）。git 差异及 harness changedFiles 只有上述5个前端文件；后端、API client、路由、海外、执行器均未改变。生产服务不切换属于 `DEV-PLAN.md:5` 后续发布验收，尚不作已完成判断。 |
| 设计一致性、无死引导 | 完整实现。`Design-Brief.md:3` 明确覆盖旧预览服务区。`activity.css:1` 保留卡片间距18px；`:2` 保留14px正文/18px计数；`:5` 保留筛选间距14px；`:8` 保留700px窄屏规则。删掉服务区专用选择器，没有剩余指向已删服务详情的按钮或引导。 |

部分实现：无。未实现：无（以上代码范围）。Spec 漂移：无；版本号变更见 `frontend/package.json:3`，其余依赖及构建脚本未改。

## Stage 2：Code Quality — PASS

- 结构及类型：四个实现文件分别57、34、21、8行，均低于300行；删除服务监控状态、请求、props、emits、样式成套完成，无悬空引用、无新增 any。加载与组件卸载竞态保护仍在 `use-activity.ts:18`、`:28`、`:32`。
- 安全：对四文件扫描 eval、innerHTML、v-html、dangerouslySetInnerHTML、暴露 KEY/SECRET/TOKEN、密钥前缀、绝对用户路径无命中。渲染仍为 Vue 文本插值/ElAlert title，见 `ActivityDetails.vue:5` 至 `:10`；无新增写接口、SQL、依赖或权限逻辑。未发现需外部查证的可疑新模式。
- 测试真实性：检查 `output/domestic-service-removal/e2e.js:2` 至 `:43`，使用3042实际页面，正常路径不 mock 数据；仅故障恢复明确 route 注入503并 unroute。分页断言实际详情按钮数20/14；零监控断言在导航前开始监听；空态断言等待真实空结果文案；390宽检查 document.scrollWidth。汇总31/32仅 includes 字符串，是较宽松的既有保留项证据，不将其当作全统计口径重新验收。人员/图片精确口径仍由未改后端及上一轮报告覆盖。本轮删除是可逆低影响变化，不要求新增镜像实现单测。
- 视觉对比：reviewer 实际打开3042合并页及邻居用户与角色页，分别保存 `output/playwright/service-removal-review-activity.png` 和 `output/playwright/service-removal-review-users.png` 并目视检查。两页 Art 页头、蓝色操作、白卡圆角、表格密度及边距一致；合并页服务行消失后统计区自然上移。对照 `output/domestic-service-removal/mobile.png`，390宽四计数换行、过滤控件纵排、表格内滚动，页面无整体横溢。代码证据 `activity.vue:2` 至 `:8`、`activity.css:1` 至 `:8`；邻居 `users.vue:2` 至 `:4`。
- 浏览器错误核查：CLI console error 仅1项503，URL 为 `/api/v1/management/activity?view=jobs&currentOnly=false&page=1&pageSize=20`，对应 `e2e.js:28` 故障注入；随后页面已正常显示数据。无证据将该预期错误判作运行回归。

## 编译与测试原始输出

reviewer 独立执行 `npx vue-tsc --noEmit`，最终退出码 **0**，原始输出如下（结束无其它输出）：

```text
npm warn Unknown project config "package-manager-strict-version". This will stop working in the next major version of npm. See `npm help npmrc` for supported config options.
npm warn Unknown project config "manage-package-manager-versions". This will stop working in the next major version of npm. See `npm help npmrc` for supported config options.
```

已读取主 Agent 提供的 `output/domestic-service-removal/tests.log`，没有冒充独立重跑542项：

```text
ℹ tests 542
ℹ suites 0
ℹ pass 542
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 12337.9527
```

`output/domestic-service-removal/e2e-results.json:1`：passed=18、monitorRequestCount=0。本轮未运行正式 Vite 构建；必须在固定提交打包时补充构建输出后才能宣称发布验证完成。未改后端，因此不重复执行后端全量，也不改变前轮记录的既有失败/跳过边界。

## 快照与范围隔离

开始及收尾 `review-status` 的 currentId 均等于本报告 candidateId；changedFiles 均为上述5个前端文件。审查期间主 Agent 暂存了本轮文件，并将 `Product-Spec.md:15` 改成“首次正式上线”澄清0.2.68历史状态；已读差异，不改变本次需求或代码快照。

全局候选中的 `scripts/maintenance/install_panel.py`、`test_install_panel.py` 不在本轮提交/审查范围，沿用独立报告 `docs/reviews/INTRANET-1PANEL-INSTALL-20261111.md`，其内容哈希已经在前轮 `docs/reviews/DOMESTIC-ACTIVITY-RELEASE-20261111.md` 核对。本轮相对已批准候选的 changedFiles 不含它们，不扩大其批准范围。

主 Agent 应以本报告路径与相同 candidateId 执行 review-approve 登记两阶段 PASS；本报告未写 `.needs-review`、未修改代码、未执行提交或生产部署。
