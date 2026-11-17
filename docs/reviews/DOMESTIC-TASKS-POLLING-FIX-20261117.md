# 国内任务中心静默轮询修复审查

- candidateId：`52cec67ff9657598f7d84431c5142762699eec4ebdf1feaf77ccab731de69938`
- 日期：2026-11-17；独立 code-reviewer；使用 `.agents/skills/code-review/SKILL.md`。
- 结论：**Stage 1 PASS；Stage 2 PASS**。未发现本次变更的 HIGH/MEDIUM 问题；有一项测试类型精度 LOW 建议。
- 范围：`hengxin-smart-image/frontend/` 下 package.json、src/views/hengxin/domestic-studio/{use-tasks.ts,tasks.css}、src/views/hengxin/admin/workspace-sessions/use-monitor.ts、tests/{domestic-tasks.test.ts,workspace-sessions.test.ts,workspace-sessions.browser.mjs} 七个文件相对 HEAD 的变化及其实际组件调用链。
- 不包括：生产历史空任务清理、后端、数据库迁移、部署操作及其他部署文档的真实性复验。本报告不能证明生产已发布。
- 审查开始及完成前分别执行 `python .codex/hooks/harness.py review-status`，currentId 均与上述 candidate 一致，changedFiles 恰为上述七个文件。未观察到送审代码变化。由主 Agent 登记同一快照的 review-approve；本审查不写 clean、不批准其它快照。

## Stage 1：Spec Compliance — PASS

基准为 Product-Spec.md:3 的上线反馈修正、Product-Spec.md:13–15 的管理只读/撤权/迟到响应要求及 DEV-PLAN.md:3 的本次验收范围。以下覆盖本次增量全部条目，不将旧产品全部功能冒充重新验收。

| 条目 | 结论与代码证据 | 验证证据 |
| --- | --- | --- |
| 已加载任务列表、任务详情后台静默更新 | 完整实现。use-tasks.ts:31–67 区分 requesting 与 loading，后台已有快照时 loading=false；数据成功后仍赋值。TaskPage.vue:6、9 将 loading 连接按钮和 TaskList；TaskList.vue:6 的遮罩只消费 loading。 | domestic-tasks.test.ts:101–124 的个人/管理 × 列表/详情四组延迟 Promise 用例；独立复跑通过。浏览器实际列表请求两轮采样及改名更新通过。 |
| 已加载会话详情后台静默更新 | 完整实现。use-monitor.ts:21–57 后台保留详情和增量过程，原子提交完成后的快照；ManagedTaskWorkspace.vue:3–6 连接会话刷新按钮及详情。TaskPage.vue:15 的 key 固定为 actor/task，ManagedTaskWorkspace.vue:5 的 key 为 selectedId，周期数据变化不重建组件。 | workspace-sessions.test.ts:96–114；浏览器 `.wm-chat` DOM 引用不变且标题更新。 |
| 首载、筛选、手动刷新有反馈 | 完整实现。use-tasks.ts:36、67、99–108；use-monitor.ts:27、59–68。公开 refresh 无布尔事件参数歧义，显式执行前台刷新；无快照时后台首次重试仍 loading。 | 新单测断言首载/手动 loading=true，手动覆盖在途后台请求；domestic-tasks.test.ts:126–139 验证筛选反馈；浏览器 800ms 延迟下主动点击确有 is-loading。 |
| 刷新按钮几何稳定 | 完整实现。tasks.css:2–3 仅限定 tc-page 内 wm-sync，任务刷新 84px、会话刷新 112px，flex-shrink:0。无业务按钮/输入全局样式变更。 | report.json 的列表前后均 (1808,226.484375,84,36)，会话均 (1780,342.484375,112,36)；自动两轮各三次采样及手动加载期均严格相等。 |
| 保留 3 秒自动同步、可见页限制、暂停和在途去重 | 完整实现。use-tasks.ts:109 与 use-monitor.ts:70–72 保留 3000ms 和 visibilityState 判断；去重改为 requesting，避免静默后重复并发。任务写操作期间仍 busy 阻挡轮询。ManagedTaskWorkspace.vue:22 同步父级开关。 | 新增六组轮询单测在请求悬而未决时推进 6000ms，明确请求数不增长、旧 signal 不被 abort；暂停后不发请求。浏览器真实 interval 两轮更新。隐藏页分支为代码复核，本次未单独浏览器切后台测试。 |
| abort/epoch 防迟到响应、取消空选择 | 完整实现。use-tasks.ts:33–64；use-monitor.ts:23–42、60–63。迟到 detail 在启动 transcript 前检查 epoch；选空立即重置 loading/requesting，listEnabled=false 不产生空详情请求。dispose 后 alive 阻止 refresh。 | 两套测试均覆盖旧响应晚到、手动替换在途轮询；workspace-sessions.test.ts:116–124 验证最后会话移除后 transcriptCalls=0、无残留详情且取消 loading。 |
| 断线保留内容、恢复清错误、删除清详情、401/403清敏感内容 | 完整实现。use-tasks.ts:24–29、60–65；use-monitor.ts:14–19、50–57 保留原错误/撤权规则。ManagedTaskWorkspace.vue:24 把子级拒绝传播到父任务页，TaskPage.vue:3 撤权改显无权结果。 | domestic-tasks.test.ts:126–139、workspace-sessions.test.ts:49–93；浏览器断线恢复、源会话删除、管理员403已实走。401与403共用判断分支经静态核对，本次未单独注入401。 |
| 沿既有 UI、无新功能或死引导 | 完整实现。无模板文案、新页面、API、依赖/schema变化；package.json:3 仅版本到0.2.75。TaskPage.vue:7、ManagedTaskWorkspace.vue:7 的重试提示对应现有 refresh。 | git diff 七文件；查看真实渲染截图及邻居基准，见 Stage 2。 |

部分实现：无。未实现：无。Spec 漂移：无。Stage 1 无 HIGH，进入 Stage 2。

## Stage 2：Code Quality — PASS

- 结构与生命周期：两处请求状态分别属于自身 composable；公开 refresh 保持无参数调用合同，timer 独占 background=true。finally 仅当前 epoch 可复位请求状态，不会被过期请求解除新请求去重。证据：use-tasks.ts:16、31–67、109–111；use-monitor.ts:13、21–74。生产修改文件分别117/76/42行，未超过300行；生产新增代码无 any。
- 安全：对三个生产修改文件扫描 eval、innerHTML/dangerouslySetInnerHTML、VITE密钥前缀、常见API密钥、用户绝对路径及 any，均无匹配。未新增数据执行、SQL、凭据或写请求路径；读取权限清空和 abort 逻辑保留。证据：use-tasks.ts:25–29；use-monitor.ts:15–19；tasks.css:2–3。此为变更范围扫描，不宣称全仓无漏洞。
- 测试真实性：六组轮询用例在真实 composable 的 interval 回调中推进时间，故意保留 Promise 未完成，并让已 abort 的旧 Promise 仍 resolve，以检验 epoch 而非靠 mock 自动拒绝掩盖问题；断言数据确实变化。浏览器 tests/workspace-sessions.browser.mjs:87–118 等待实际请求/响应，在800ms慢响应中三次采样 loading/遮罩/DOM引用/按钮矩形，再等待修改后的服务端 mock 数据呈现。属于真实页面、隔离HTTP响应，不是生产数据验证。静态图片不能证明动态稳定，动态结论依据这些运行断言及 report.json。
- **LOW，非阻断建议**：新增测试沿用宽泛的延迟响应 helper，domestic-tasks.test.ts:104–105 的 deferred<any>、workspace-sessions.test.ts:98–99 的 Promise<any> 放宽了 fixture 类型约束。建议后续用任务/会话列表及详情的联合类型或泛型 helper 替代。当前测试仍明确断言状态、数据、取消和请求数，生产代码未增加 any，此项不改变本次功能通过结论。
- 视觉：独立打开 `output/playwright/task-polling/list-1920.png`、list-390.png、detail-1920.png、detail-1000.png、detail-390.png，对照既有 `output/playwright/task-manager/detail-1920.png` 和邻居“调用与执行”的 `output/playwright/task-product-review-neighbor.png` 实际渲染截图。蓝色描边按钮、灰白背景、卡片边框、文本密度及详情结构沿用既有UI；本次仅两个刷新按钮固定宽度。窄屏列表保持既有横向表格及固定操作列，详情按钮可见；截图包含滚动位置，不把页顶被固定导航遮住的部分当作完整首屏验证。未启动或停止用户预览服务；本轮视觉复核是已有真实截图对比，未宣称新开邻居页面复测。
- 测试完整性边界：独立复跑两个受影响测试文件22项及类型检查；全量592项、浏览器52个GET由主Agent提供的原始日志及报告佐证。未重新跑生产Vite打包、后端或部署验收，不能据本报告称这些新增验证完成。

## 原始验证输出

独立执行于 `hengxin-smart-image/frontend`：

```text
pnpm exec tsx --test tests/domestic-tasks.test.ts tests/workspace-sessions.test.ts
ℹ tests 22
ℹ suites 0
ℹ pass 22
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 972.7907
exit_code: 0
```

独立编译/类型检查原始完整输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.

> hengxin-smart-image-frontend@0.2.75 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit

exit_code: 0
```

既有 pnpm 字段告警仍在，本次无依赖修改，不将告警写成失败或声称已修。

主 Agent 的全量 `output/task-polling-unit.log` 原始末尾：

```text
ℹ tests 592
ℹ suites 0
ℹ pass 592
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 32447.3564
```

浏览器证据 `output/playwright/task-polling/report.json`：result=PASS；errors=[]；unexpected=[]；52次请求均GET。同目录 `failure.json` 为15:56:15初次脚本等待 `.el-loading-mask` 命中两个元素导致的 strict-mode 错误，成功 report.json 为15:59:20；最终脚本:123 已用 waitForFunction 等待遮罩移除。残留失败文件不代表最终运行失败，也不应删去后宣称从未失败。

最终快照核对原始关键输出：

```text
currentId: 52cec67ff9657598f7d84431c5142762699eec4ebdf1feaf77ccab731de69938
reviewedId: bdc78af52f5564caa852690e03d2626b14a94ce73ff07e295256dcc2bff51fe5
approved: false
```

approved=false 表示独立审查时主 Agent 尚未登记新凭据，非本报告失败。允许主 Agent 按本报告的两个 PASS 登记以上 candidate；登记后有任何代码变化须重新固定快照并复核。
