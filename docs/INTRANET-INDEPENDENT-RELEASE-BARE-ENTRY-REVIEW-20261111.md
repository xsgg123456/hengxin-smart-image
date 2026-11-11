# 独立发布裸入口修复审查

- candidateId：`d3a967332ae14940e06e774849782af11917f8c7bc2e0902deee6d698edc3ce1`。
- 基线 HEAD：`2b7b28283a2fd024927751e9291cb522440686c5`。范围仅为 `hengxin-smart-image/frontend/src/release/navigation.ts` 与 `hengxin-smart-image/frontend/tests/release-navigation.browser.mjs` 相对该 HEAD 的差异；分别增加 6 行、增加 40 行删除 8 行。
- 依据：`.agents/skills/code-review/SKILL.md`、`Product-Spec.md:1486`、`DEV-PLAN.md:1706`、`docs/INTRANET-INDEPENDENT-RELEASE-20261111.md:5` 起七项合同。未变更部分沿用 `docs/INTRANET-INDEPENDENT-RELEASE-REVIEW3-20261111.md` 的已批准候选 `ec1d678644a57928bea32bea22a34aa705d8194cf98890ba14a7814d4e90d85a`；不是重新声称执行了 Python、Docker、GC 全部验收。
- **Stage 1：PASS。Stage 2：PASS。无 HIGH / MEDIUM 阻塞项。** 审查者独立复跑 31 项浏览器测试，退出码 0，并实际打开修复后三组裸入口与 generic 基准查看渲染。
- 审查前及结论形成时 `review-status.currentId` 均等于上述 candidate，`changedFiles` 仅列出两文件。没有修实现、提交或登记批准；普通 Markdown 报告不改变受控快照。
- **生产尚待重新部署验收。** 主 Agent 交接说明第一次迁移因裸入口白屏已回退；本报告不将第一次部署计为成功，也不把本地 fixture 验收当作生产认证、任务及进程保持的证明。

## Stage 1 · Spec Compliance

| 要求 | 结论与证据 |
| --- | --- |
| 合同 3：三组裸入口可用 | 完整实现。`src/release/navigation.ts:31` 将目标解析为 URL，`:32` 比较 pathname/search；仅 hash 规范化时 `:34` 使用 `history.replaceState(window.history.state, '', destination)`，`:35` 返回 false。`src/release/domestic-entry.ts:3`、`overseas-entry.ts:3`、`shared-entry.ts:3` 因而执行原动态 bootstrap。独立浏览器测试 `tests/release-navigation.browser.mjs:56` 至 `:84` 的 24 项全部通过。以上路径均相对 `hengxin-smart-image/frontend/`。 |
| 合同 3：同源、query/hash、旧链接、跨组切换与登出 | 完整实现。`navigation.ts:12` 至 `:23` 原目标选择/参数保留不变；`:37` 至 `:38` 对真正跨路径跳转仍 replace 并返回 true。测试 `:88` 至 `:161` 保留旧 callback、国内/海外深链、跨业务、退出、过期身份、撤权、重试及共享 404 共 7 项；独立复跑全部通过。24 项矩阵还核对认证后 query/hash 与只有 1 次文档请求，未认证到共享登录且不超过 2 次文档请求。 |
| 合同 3：复用 UI 与静态产物 | 完整实现，无新增页面/提示/组件。生产差异仅 `navigation.ts:31` 至 `:36`，没有 CSS、模板、依赖或构建配置改动。本轮在 1440×1000 浏览器实际打开 generic 三页和新产物三组裸入口；页面主体、按钮尺寸/位置/字体/圆角一致，见下方视觉证据。 |
| 合同 1：分组版本、单侧隔离、共享变化识别 | 本修未改变对应实现；`git diff --stat 2b7b282` 仅两前端文件。原实现及证据见前轮报告“七项合同”第 1 行；其 `scope_catalog.py:30`、`scope_engine.py:12`、`scope_changes.py:137` 无差异。本修位于三组公共导航，须重建三正式包，不能当作国内独占修改。 |
| 合同 2：复用锁/事务/snapshot/GC | 本修未改变 `release_cli.py:25`、`scope_engine.py:47`、`full_cleanup.py:11`；前轮第 2 行证据继续适用。本轮没有第二套发布或回退机制。 |
| 合同 4：首次只切静态入口，进程和数据不动，可回退 | 本修未改变 `split_state.py:48`、`migrate_split.py:101`、`:140`；沿用前轮第 4 行实现审查。此次正式重新部署后的原容器、原生进程和任务验收仍需主 Agent 执行。 |
| 合同 5：目标侧排空/恢复，共享后端拒绝 | 本修未改变 `scope_actions.py:27`、`:35`、`:76` 与 `scope_engine.py:56`；沿用前轮第 5 行，无新增后端动作。 |
| 合同 6：每组两成功版本、失败不推进、引用与资产保护 | 本修未改变 `scope_catalog.py:30`、`:51`、`operations.py:19`、`scope_snapshot.py:70`；沿用前轮第 6 行。本次本地通过不授权将已回退的失败迁移计入成功记录。 |
| 合同 7：从当下配置单侧回退，不回滚业务数据库 | 本修未改变 `scope_release.py:41`、`scope_engine.py:12`、`split_state.py:18`；沿用前轮第 7 行，无数据库路径变化。 |

上述 Python 短路径均位于 `scripts/release/intranet/`。本轮范围无部分实现、未实现项，也未发现 Spec 漂移或死引导；生产再验属于后续执行验收，不以本报告代替。

## Stage 2 · Code Quality

- 结构与类型：通过。`navigation.ts:26` 的 boolean 契约保持；新局部分支只处理 hash 规范化，现有 history state 保留，不引入 any、重复业务初始化或异常吞掉。文件共 39 行；浏览器测试 166 行，均小于 300 行。
- 测试真实性：通过。`release-navigation.browser.mjs:54` 每次先打开 `about:blank`，避免已挂载应用掩盖入口 bootstrap 缺陷；`:50` 仅统计本站主文档请求，过滤 about:blank 不影响真实重载计数。`:67` 等待真实可见业务/登录按钮，`:69` 至 `:79` 核验 URL 和文档次数，`:81`、`:160` 断言没有 pageerror。API 在 `:31` 至 `:45` 被内存 fixture 拦截，因此这里只证明真实产物的前端初始化与导航，不声称真实钉钉登录或付费业务执行已验证。
- 故障证据：`output/intranet-independent-release/fix-bare-entry/browser-before.log:1` 保留修前旧产物第一次裸国内入口等不到“切换业务”的 20000 ms 超时；`:67` 为测试等待点。本轮独立运行新产物全部 31 项通过，与 `browser-after.log:1` 至 `:31` 相符；没有只靠纯函数测试推定可用。
- 安全扫描：通过（本次两文件范围）。对 eval、innerHTML、dangerouslySetInnerHTML、前端 KEY/SECRET/TOKEN、密钥前缀、绝对用户目录与 any 的搜索无命中。`navigation.ts:22` 生成固定的同源 scope 前缀，`:31` 的 URL 解析不会引入外部跳转；`:34` 不写入 HTML、凭据或业务数据。测试的路径边界检查在 `release-navigation.browser.mjs:14`，服务只绑定 `127.0.0.1`（`:23`）。
- 视觉：通过。本轮实际查看六张截图 `output/playwright/bare-review-{generic,independent}-{identity,domestic,overseas}.png`。共享业务选择、国内新建换图表单/既有接口错误态、海外既有无权限态均实际渲染。三组按钮指标如下，基准与新入口数值相同。国内新包额外显示既有“系统升级公告”，版本文字为本地构建标识 bare-entry-fix，来源是未改的 `src/utils/sys/upgrade.ts:137`、`:154`；不是本修新增 UI，也不能声称两张国内截图逐像素一致。截图中主体布局一致，通知未改变按钮实测位置。浏览器最终输出 `pageerrors []`。既有正式页面视觉基准还见前轮报告 Stage 2。

| 按钮 | 两版共同指标 |
| --- | --- |
| 共享“海外业务” | x=932，y=312.234375，440×64，18px，圆角 6px |
| 海外“切换业务” | x=1246，y=14，86×32，14px，圆角 6px |
| 国内“切换业务” | x=1246，y=12，86×36，14px，圆角 6px |

## 实际测试与编译原始输出

审查者独立执行：使用已安装 Playwright 模块 `file:///C:/Users/82358/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs`，`RELEASE_BUILD_ROOT` 指向 `output/intranet-independent-release/fix-bare-entry`，运行 `node hengxin-smart-image/frontend/tests/release-navigation.browser.mjs`，退出码 0：

```text
PASS fresh domestic/(bare) authenticated=true
PASS fresh domestic/(bare) authenticated=false
PASS fresh domestic/?entry=bare authenticated=true
PASS fresh domestic/?entry=bare authenticated=false
PASS fresh domestic/?entry=bare#/ authenticated=true
PASS fresh domestic/?entry=bare#/ authenticated=false
PASS fresh domestic/#/api-image-edits/create authenticated=true
PASS fresh domestic/#/api-image-edits/create authenticated=false
PASS fresh overseas/(bare) authenticated=true
PASS fresh overseas/(bare) authenticated=false
PASS fresh overseas/?entry=bare authenticated=true
PASS fresh overseas/?entry=bare authenticated=false
PASS fresh overseas/?entry=bare#/ authenticated=true
PASS fresh overseas/?entry=bare#/ authenticated=false
PASS fresh overseas/#/overseas/tasks authenticated=true
PASS fresh overseas/#/overseas/tasks authenticated=false
PASS fresh shared/(bare) authenticated=true
PASS fresh shared/(bare) authenticated=false
PASS fresh shared/?entry=bare authenticated=true
PASS fresh shared/?entry=bare authenticated=false
PASS fresh shared/?entry=bare#/ authenticated=true
PASS fresh shared/?entry=bare#/ authenticated=false
PASS fresh shared/#/auth/business authenticated=true
PASS fresh shared/#/auth/business authenticated=false
PASS legacy callback query/hash; shared → overseas → domestic → overseas; unified logout
PASS legacy domestic deep link and domestic logout
PASS domestic expired session redirects once to shared identity
PASS overseas deep link and active-page identity invalidation
PASS active overseas permission revocation returns to shared business selection
PASS shared connection failure/retry, no page errors; all APIs remain /api
PASS missing shared identity service stays retryable, no domestic/shared loop
```

以下是本轮实际读取的主 Agent 原始日志，不冒充审查者重跑。目录均为 `output/intranet-independent-release/fix-bare-entry/`。`typecheck.log:1`：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.

> hengxin-smart-image-frontend@0.2.69 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

`unit.log:874` 起：

```text
ℹ tests 546
ℹ suites 0
ℹ pass 546
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 15138.7876
```

三产物编译成功末行依次为 `build-domestic.log:434`、`build-overseas.log:70`、`build-shared.log:78`：

```text
✓ built in 33.88s
✓ built in 28.31s
✓ built in 20.96s
```

三日志同有上述 pnpm 配置警告；依赖和配置未改，本报告不将其隐去或宣称依赖审计零告警。真实浏览器已加载这些构建产物，不仅检查构建日志。

两阶段 PASS 仅适用于本 candidate。主 Agent 应按 `docs/HARNESS-REVIEW.md:7` 登记同一快照，随后重建三正式发布包、重新部署并核验正式裸入口/登录/切换、原业务进程与任务状态。若受控代码变化，须重新固定候选并复核。
