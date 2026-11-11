# 内网独立发布审查 · 第三轮

- candidateId：`ec1d678644a57928bea32bea22a34aa705d8194cf98890ba14a7814d4e90d85a`。
- 范围：冻结候选全部 `git diff` 及未跟踪实现、测试文件，包括 frontend 三组入口/导航/构建与 `scripts/release/intranet` 的发布、迁移、作用域、快照、台账、GC、打包。依据 `docs/INTRANET-INDEPENDENT-RELEASE-20261111.md:5` 起七项合同及执行验收、`Product-Spec.md:1486`、`DEV-PLAN.md:1706`；不是整个产品历史功能的重新验收。
- 使用 `.agents/skills/code-review/SKILL.md`，从 Stage 1 重新检查。审查前及结束时 `review-status.currentId` 均为上述编号，受控代码没有变化。审查者仅写报告和忽略目录中的验证产物，未修实现、未提交、未登记批准。
- **Stage 1：PASS。Stage 2：PASS。没有剩余 HIGH / MEDIUM 阻塞项。** 原两轮的交错后端发布、兼容资源累积、回退旧 tab 资源问题均已复核修复。
- 这是候选实现及隔离验证通过；生产切换尚未执行。正式入口、17 个原容器和 7 个原生进程前后身份、运行任务只读状态及业务数据不变，须由主 Agent 在实际迁移后另记证据，不能用本报告冒充部署完成。

## Stage 1 · 七项合同逐条核对

以下短文件名均位于 `scripts/release/intranet/`。

| 合同 | 结论 | 代码与验证证据 |
| --- | --- | --- |
| 1 国内、海外、共享分别记录版本；单侧不影响另一侧；识别共享变化 | 完整实现 | `scope_catalog.py:30` 只推进目标组并对比其它组；`scope_engine.py:12` 从当下 compose 深拷贝后只改目标；`scope_changes.py:137` 校验依赖/schema/runtime，并对两版 Python 引用图的所有权取并集。其它业务独占变化可随完整 Git 包存在，未知/共享变化拒绝。`test_scope_flow.py:186` 用实际不同后端字节执行国内 A→海外 X→国内 C→国内回退 A，海外 X 保持；`test_scope_changes.py:60`、`:107`、`:114`、`:194` 覆盖跨域/共享/两图边界/依赖拒绝，本轮全测通过。 |
| 2 复用原 release/锁/engine/snapshot/GC | 完整实现 | `release_cli.py:25` 使用同一 Store 锁；`release.py:44`、`scope_release.py:31` 路由原事务 engine；`scope_engine.py:47` 用 context/finally 恢复临时适配；`full_cleanup.py:11` 仍组合原源码、镜像、文件 GC。`test_scope_engine.py:91`、`:116`、`:177` 执行真实 engine journal/apply/recover；Linux 本轮 292 项及真实 Docker GC 通过。 |
| 3 同源三组独立前端、旧链接、切换与退出、旧页面资源 | 完整实现 | `hengxin-smart-image/frontend/release-scope.config.ts:11` 选择单组 module graph 并拒绝串入另一侧实现；`src/release/navigation.ts:12` 保留 query/hash、识别旧地址；`src/views/auth/IdentityPortal.vue:160` 处理切换和退出。`split_config.py:11` 资产先当前目录，再只读 previous，缺失返回 404；`:22` 仍保留 API 路径并动态解析静态服务。三组产物隔离日志、七项真实构建浏览器 fixture、真实 nginx 三组及回退资源请求均通过；本轮实际 Chrome 三组对照见 Stage 2。 |
| 4 首次只增三 UI 后切入口；原业务/数据进程保持，可回退 | 完整实现，生产执行验收待主 Agent | `split_state.py:48` 拒绝首次包的任何 backend 差异；`split_config.py:41` 保持原全部服务字典；`migrate_split.py:101` 只 up 三 UI，`:102` 核对原进程与新增容器健康，`:105` 检查 nginx，`:109` 原 inode 写入后 reload。`:125` 和 `split_state.py:41` 再核对原身份；`:140` 校验备份、归属后仅删除新增 UI 并还原入口/compose/台账。`test_split_migration.py:173`、`:186`、`:220`、`:239`、`:270` 覆盖后端拒绝、成功、失败、原进程漂移和中断；没有迁移数据库或业务记录写入路径。 |
| 5 后续只排空/停止/启动目标侧；失败恢复；共享后端拒绝 | 完整实现 | `scopes.py:5`、`:12`、`:17` 显式划分应用、原生服务、队列；`scope_actions.py:27` 只传目标 workers，`:35` 国内/海外不关闭共享账号 socket，`:76` 只启动目标列表；`scope_engine.py:56` 明确拒绝 shared full。`test_scope_engine.py:75` 逐条断言命令作用域，`:136` 排空失败没有 systemctl stop 且恢复目标消费，`:220` 拒绝 shared full，`:228` shared frontend 只重建静态服务。本报告不声称提供共享后端联合热更。 |
| 6 每组两次成功；失败不推进；所有实时引用保护；资产不无限累积 | 完整实现 | `scope_catalog.py:30` 成功后更新目标 current/previous，`:51` 保留三组历史、staged、pending；`:65` 汇总镜像引用；`cleanup_refs.py:65`、`:144` 汇总台账及宿主全部容器挂载、进程、systemd。`release.py:164` 清理失败不回滚已成功业务。`operations.py:19`、`:28` 只复制前版自身 assets；`scope_engine.py:32` 每次更新 outgoing fallback，`scope_snapshot.py:70` 校验只读绑定与真实清单并记录 hash。`test_release.py:208` 证明 A/B/C 不递归复制，`test_scope_flow.py:291`、`:308`、`:323` 覆盖长期未发布侧与真实文件 GC，`:364` 证明 C→B→D 后 fallback 从 C 变 B，B 历史字节不变。Linux 真实 Docker GC 释放 9118 字节、测试对象剩余 0；不是生产净释放量。 |
| 7 从当前全站配置合成单侧回退；不回滚 DB；保留真实旧版 | 完整实现 | `scope_release.py:41` 用当下状态重新 prepare；`scope_engine.py:12` 不回放旧全站 compose；`release.py:115` schema/data 漂移时拒绝恢复，没有业务数据库回灌；`split_state.py:18`、`:28` 从真实旧 current 生成迁移 previous。`test_scope_flow.py:186`、`:364` 验证独立回退保留另一侧版本及 outgoing 资产，`test_split_migration.py:186` 验证迁移旧记录真实。 |

执行范围同时满足：`release_cli.py:9` 支持国内/海外 full 和三组 frontend；`scope_engine.py:56`、`scope_changes.py:171` 拒绝共享后端/跨域公共变更。前端复用原组件，没有新增业务页面、API、表或误导性占位功能。源 Spec/计划已更新；首次入口切换没有通过业务全量发布伪装完成。正式生产验收是后续执行项，不是本轮缺失的代码功能。

## 旧问题修复复核

1. 第一轮 HIGH：完整 Git 包带其它业务独占改动不再误拒绝。`scope_changes.py:158` 同时看 old/new 所有权，任一版本未知即拒绝，不以目录名猜归属。`test_scope_flow.py:186` 和 `:212` 使用真实后端内容变化验证交错 full/frontend 发布，不再依赖所有 backend 永远相同的前提。
2. 第一轮 MEDIUM：`operations.py:19` 使用 `frontend_current_files`，旧格式排除 `compatibility_files`；`test_release.py:208` 验证 C 只携带 B+C。
3. 第二轮 MEDIUM：`scope_engine.py:37` 将切换前 html 源只读挂到 previous，之后再改目标源；`release.py:85` 回退不改历史包；`split_config.py:14` 仅 assets 走 fallback，未知资产明确 404。`scope_snapshot.py:70` 拒绝 writable/non-bind/非法来源并核验 fallback 清单，`:103` 将来源与清单 hash 纳入全站快照。`test_scope_flow.py:364` 证明 C→B→D 的挂载及历史不变；`test_scope_snapshot.py:90` 拒绝可写 fallback；真实 nginx smoke 请求 outgoing-C.js 得到原字节、nonexistent.js 得到 404。

## Stage 2 · 质量、安全、测试与视觉

- **测试真实性通过**：`test_scope_flow.py:23` 使用完整生产服务清单、真实 manifest/台账/作用域配置；其宿主操作被模拟，因此没有把它称为真实 systemd 重启测试。`test_scope_engine.py:91` 补足真实 engine 日志/恢复与命令边界；`test_scope_snapshot.py:71` 补足真实快照逻辑。实际 Linux 文件/descriptor GC、Docker 与 nginx HTTP smoke 补足平台和配置边界。生产中的真实后端 full 发布未执行，不能宣称已做生产故障演练。
- **安全扫描通过（本次变更范围）**：对所有变更及未跟踪 Python/TS/Vue/MJS 搜索 eval、innerHTML、dangerouslySetInnerHTML、前端 KEY/SECRET/TOKEN、shell=True、常见密钥前缀。只有 `test_package_release.py:40`、`:176`、`:180` 的环境泄漏拒绝 fixture 命中。`scope_changes.py:30` 校验来源、路径、符号链接和 hash，`package_release.py:121` 使用构建环境允许名单；`split_config.py:79` 使用 O_NOFOLLOW 并核对 inode。没有发现新增密钥泄漏、shell 注入或任意路径删除。依赖锁文件未变；主 Agent 的既有审计为 critical 0 / high 39 / moderate 35 / low 5，此报告不是依赖零漏洞证明。
- **结构通过，保留 LOW 备注**：生产变更文件均不超过 300 行；唯一超出为 `test_scope_flow.py:23` 起共用 fixture/集成流程，整文件 384 行，职责集中，不为凑行数要求拆出第二套 fixture。`scope_actions.py:15` shared_idle 及 shared/full 分支受 `scope_engine.py:56` 拦截，仍有不可达冗余；可后续精简，不作为已实现共享后端能力宣传。
- **视觉通过**：审查者本轮实际启动 Chrome，在 1440×1000、同一身份 fixture 下打开 generic 基准与三组产物，等网络空闲后截图并查看六张图。共享业务选择页、国内新建换图完整表单及错误提示、海外现有无权限页保持原布局、图标、间距、字号、按钮和色彩。代码复用位置：`hengxin-smart-image/frontend/src/identity-bootstrap.ts:15`、`src/domestic-main.ts:2`、`src/identity-main.ts:1`。证据 `output/playwright/review3-visual.log:1` 至 `:7` 及 `review3-{generic,independent}-{identity,domestic,overseas}.png`。共享/海外截图文件字节一致；国内只有 4 个像素差异，框位于右侧装饰图标 x=1275、y=501..504，无组件位置/尺寸差异。三组按钮实测如下，均完全相同。

| 页面与按钮 | 两版共同数值 |
| --- | --- |
| 共享“海外业务” | x=932，y=312.234375，440×64；18px；圆角 6px；文字 rgb(93,135,255)，背景 rgb(238,243,255) |
| 海外“切换业务” | x=1246，y=14，86×32；14px；圆角 6px；文字 rgb(93,135,255)，透明背景 |
| 国内“切换业务” | x=1246，y=12，86×36；14px；圆角 6px；文字 rgb(96,98,102)，透明背景 |

本轮最初复用同一 generic 页面仅变 hash，仍处于 identity 应用，国内截图等待超时。每个场景先到 about:blank 再打开目标真实入口后完成全部对照；只修正审查脚本，没有修改产品，也不把错误测试前提记成产品缺陷。最终 `pageerrors []`。fixture 不调用付费模型、不写业务记录；正式入口认证联调仍由主 Agent 部署后验证。

## 原始测试和编译输出

审查者本轮独立运行 Windows intranet 全套（72 项为 POSIX 专用跳过，不能算通过）：

```text
201 passed, 72 skipped, 9 subtests passed in 27.30s
```

独立语法编译与 frontend typecheck：

```text
PASS Python syntax compilation: 42 files
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.

> hengxin-smart-image-frontend@0.2.69 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

typecheck 进程退出码 0；上述 pnpm 配置警告真实存在，本次未改依赖配置。

本轮 Linux `output/intranet-independent-release/checks-210827f3bf7b164c.log:6`，执行器 `run_checks.py:8` 先核对部署工具 manifest 并逐文件 compile：

```text
292 passed, 9 subtests passed in 10.82s
{"status": "PASS", "old_deleted": true, "previous_kept": true, "stopped_container_kept": true, "unknown_kept": true, "released_layer_bytes": 9118, "test_objects_remaining": 0, "production_images": 9, "production_containers": 17}
```

审查初读同名日志时看到第一次 GC smoke 的全容器全集一致断言失败；主 Agent 确认当时并行 nginx smoke 在创建/回收自己的临时容器。停止并发 Docker 测试后，串行重跑得到上述结果。初次失败不算 PASS，最终日志为重跑；此处明确保留失败事实，避免覆盖日志掩盖测试编排竞态。

本轮真实 nginx `output/intranet-independent-release/nginx-smoke.log:1`：

```text
PASS real isolated nginx: 3 scopes/assets, rollback outgoing-C assets fallback, missing assets 404, legacy assets, 4 API paths/query, independent static replacement without gateway restart
PASS isolated smoke resources removed; production gateway identity unchanged
```

前端代码在两轮之间未改，本轮复读原始构建/测试日志并实际重开产物，未重复全部构建。`output/independent-frontend/unit-tests.log`：

```text
ℹ tests 546
ℹ suites 0
ℹ pass 546
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
```

`build-domestic.log`、`build-overseas.log`、`build-shared.log`、`build-generic.log`、`build-demo.log` 原始末行依次：

```text
✓ built in 44.61s
✓ built in 41.27s
✓ built in 20.84s
✓ built in 36.29s
✓ built in 37.94s
```

`artifacts.log:1`：

```text
PASS domestic: 1117 source modules, isolated graph and prefixed assets
PASS overseas: 738 source modules, isolated graph and prefixed assets
PASS shared: 355 source modules, isolated graph and prefixed assets
```

`browser.log:1` 至 `:7` 覆盖旧 callback query/hash、跨业务切换和统一退出、国内旧深链、过期不循环、海外身份失效、撤权、连接重试和共享 404；`generic-entry-css.log:1` 至 `:6` 覆盖六个 generic 入口 CSS 依赖。上述日志已实际读取，不以测试文件存在代替执行结果。

两阶段 PASS 仅适用于本报告 candidateId。主 Agent 可按 `docs/HARNESS-REVIEW.md:7` 登记同一候选的 review-approve 后继续已授权部署；若受控代码再变，必须重新固定候选及复核，不能沿用本报告批准另一快照。
