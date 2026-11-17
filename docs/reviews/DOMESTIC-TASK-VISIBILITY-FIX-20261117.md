# 国内任务切页误判权限修复 · 独立审查

- 日期：2026-11-17
- 最终 candidateId：`0600502e17ef5b37c4a5b0b0672f634483d8cab3353d1b1acaddfd344c4ba224`
- 初始 candidateId：`7a0995b3735e1ed362b5d89bd0bb2e7df091df6db29d654d94a3a7f254d5376b`
- Stage 1：**PASS**；Stage 2：**PASS**。本范围没有待修 HIGH / MEDIUM 问题。
- 范围：Product-Spec.md:5 的切页故障修正、DEV-PLAN.md:1 的三步计划；两处身份订阅、两份单元测试和浏览器回归。不是全仓历史功能审计，也不是生产发布验收。
- 下文 `src/`、`tests/` 均相对于 `hengxin-smart-image/frontend/`；`output/` 相对于仓库根。

## 快照与审查期间变化

起始 `review-status` 与初始候选一致。审查期间主 Agent 调整了浏览器测试：等待对应业务列表到达、等待路由动画后采样几何、补齐身份失效后登录页配置接口夹具；两处生产修复未再改变。开发服务曾重写 `src/types/import/components.d.ts`，停服务后已还原，最终 `git diff` 确认该文件无差异。

已重新阅读最终浏览器测试 diff，并用 `review-status` 确认当前编号等于最终 candidateId。上述变更已纳入本报告；不批准初始快照或中间快照。登记批准由主 Agent 使用 `review-approve` 完成，reviewer 未写 `.needs-review`、未修改实现、未提交。

## Stage 1 · Spec Compliance

| 验收条目 | 结论与证据 |
| --- | --- |
| 暂时隐藏不能被当成撤权 | 完整实现。`src/views/hengxin/domestic-studio/use-tasks.ts:110` 与 `src/views/hengxin/admin/workspace-sessions/use-monitor.ts:73` 只跳过 `suspended`，其他身份事件继续调用原 failure。`tests/domestic-tasks.test.ts:94` 覆盖个人/管理 × 列表/详情，`tests/workspace-sessions.test.ts:16` 覆盖管理会话。修改前日志 `output/task-visibility-red.log:32` 为 5 个新例失败；修改后全部通过。 |
| 国内五业务入口、管理列表/会话返回恢复 | 完整实现。`tests/workspace-sessions.browser.mjs:123` 驱动正式应用 hidden/visible 事件并检查内容恢复、无错误权限页、同步开关保持；`:149` 覆盖五业务，`:162`、`:180` 覆盖管理暂停同步列表和自动同步详情。浏览器 `output/playwright/task-visibility/report.json:2` 为 PASS。 |
| 隐藏时遮蔽，返回重验成功才解锁 | 完整实现。`src/api/hengxin/identity-lifecycle.ts:10` 先锁再发送 suspended；`:14` 返回调用重验。`src/domestic-main.ts:50` 同步设置 DOM 锁，`:97` 比较身份/角色，`:120` 校验代次后解锁；`src/App.vue:11` 保留组件、`:60` 遮蔽内容及传送层。浏览器测试 `:132` 延迟身份响应 800ms，`:138` 检查遮蔽，`:140` 确认实际重新请求身份。 |
| 原页面、筛选和同步设置保留 | 完整实现。suspended 分支不再调用清空函数；`tests/domestic-tasks.test.ts:99`、`:106` 检查筛选和开关，`tests/workspace-sessions.test.ts:22` 检查详情/公开过程与开关；浏览器 `:142` 检查原内容、`:143` 检查开关。 |
| 真正退出、换号、身份失效与 HTTP 401/403 继续清除 | 完整实现。`use-tasks.ts:25`、`use-monitor.ts:15` 保留 401/403 的取消、清空和禁止同步；`src/domestic-main.ts:54`、`:80` 保留全局身份清理；`identity-lifecycle.ts:22`、`:37` 保留跨标签退出与退出广播。单元测试 `domestic-tasks.test.ts:110`、`:117` 与 `workspace-sessions.test.ts:27` 验证 invalid/changed；浏览器 `:218` 检查实际管理接口 403，`:224` 至 `:228` 检查隐藏后身份重验 401 清空。 |
| 迟到读取不能回填，管理子组件撤权上报保留 | 完整实现。`use-tasks.ts:27` 增加 epoch 并 abort，`:41`、`:50`、`:56` 拒绝旧读取；`use-monitor.ts:17`、`:31`、`:36`、`:42` 同样隔离。`ManagedTaskWorkspace.vue:21`、`:24` 向父级上报 failure/denied；`TaskPage.vue:15` 接收并清父级任务。测试 `domestic-tasks.test.ts:55`、`workspace-sessions.test.ts:45` 与浏览器 `:211` 至 `:219` 覆盖迟到响应及子会话撤权后任务界面清空。 |
| UI、引导真实性与范围 | 匹配。生产 diff 只有两处订阅分支，无新文案、模板、样式、API、表或入口；没有新增死引导或 Spec 外功能。`Product-Spec.md:7` 的上线歧义已修正，明确本次切页修复尚未发布；`Product-Spec-CHANGELOG.md:3` 同样区分本地与生产。 |

部分实现、未实现：本次修复范围内无。验证边界：浏览器运行正式应用，通过派发 `visibilitychange` / `pagehide` / `pageshow` 和隔离 HTTP 响应验证生产事件处理链。没有证据证明操作系统实际切换标签或最小化已通过；该物理交互不得在交付中宣称已实测。隐藏期间身份失效并非仅成功路径模拟，已实际走重验 401 与内容清空。

## Stage 2 · Code Quality

- **代码质量 PASS**：`use-tasks.ts:110` 与 `use-monitor.ts:73` 使用现有严格事件联合类型（`src/api/hengxin/identity.ts:7`），没有新增 any、依赖或分散的权限状态；实现文件分别 120、79 行。局部注释解释 suspended 依赖全局锁的原因。
- **测试真实性 PASS**：新增 5 项直接击中旧逻辑，存在修改前失败证据。浏览器测试进入真实路由和组件，由生产生命周期调用身份重验，没有直接改 denied 或直接调用 identity。路由等待修正 `tests/workspace-sessions.browser.mjs:152` 避免断言旧业务列表；`:92` 的 500ms 只稳定入场动画，未取消轮询期间几何断言。`:37` 的登录配置夹具仅供失效后的真实登录页读取，未吞掉其他未知请求。最终报告 `:156`、`:157` 的 errors/unexpected 均为空。
- **安全扫描 PASS**：对两处生产变更文件扫描 eval、innerHTML、dangerouslySetInnerHTML、密钥前缀、VITE 敏感变量、绝对用户路径及 any，无命中。`use-tasks.ts:112`、`use-monitor.ts:75` 未跳过 changed/invalid 或 HTTP 错误路径；全局锁不因本次修复被旁路。
- **视觉对比 PASS（本次无视觉改动）**：实际打开 `output/playwright/task-visibility/list-1920.png`、`detail-390.png`，与既有 `output/playwright/task-polling/list-1920.png` 对照。列表控件、行间距、配色保持；多出的顶部页签来自本轮访问五业务的状态。轮询实测列表刷新按钮前后均为 `(1808, 226.484375, 84, 36)`，会话刷新按钮前后均为 `(1780, 342.484375, 112, 36)`，各两次真实 3 秒 tick、每次三次采样。证据 `output/playwright/task-visibility/report.json:22`、`:82`；布局断言见浏览器测试 `:77`、`:94`。本报告不宣称重新打开并审查了全站所有邻居页面。
- **Spec 漂移 PASS**：无新增业务能力；两处修复直接对应 `Product-Spec.md:5`。

## 测试与编译原始结果

主 Agent 全套单元日志 `output/task-visibility-unit.log:631`：

```text
ℹ tests 597
ℹ suites 0
ℹ pass 597
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 30223.0894
```

reviewer 独立执行 `pnpm exec tsx --test tests/domestic-tasks.test.ts tests/workspace-sessions.test.ts tests/identity-safety.test.ts`，退出码 0：

```text
ℹ tests 34
ℹ suites 0
ℹ pass 34
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1501.4672
```

最终快照及声明文件还原后，reviewer 独立执行 `pnpm exec vue-tsc --noEmit`，退出码 0，原始输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
```

国内生产构建日志 `output/task-visibility-build.log:522` 原始结束输出：

```text
✓ built in 42.12s
```

浏览器最终日志 `output/task-visibility-browser.log:1` 及完整报告 `output/playwright/task-visibility/report.json:2`：`result: PASS`，15 项检查，60 个记录的隔离业务请求，`errors: []`、`unexpected: []`。先前失败来自测试等待竞争、路由动画基线和缺失的登录配置夹具；已检查修正后的 diff 和最终结果，没有把失败运行当作通过。

发布边界：本报告批准上述本地修复快照；未执行部署，不证明生产已经修复。

## 发布前增量审查 · 2026-11-17

- 本轮 candidateId：`1246362d88ba2d31b949b0bafc4c480ca5d7c958700b39d122deb87d6b6fd7bc`。
- 已批准基准：`0600502e17ef5b37c4a5b0b0672f634483d8cab3353d1b1acaddfd344c4ba224`。
- 范围：前端发布版本 `0.2.75 → 0.2.76`、发布授权及计划文档；以上已审修复和测试按快照一致性复核。不是重新审计全仓，也不是生产发布验收。
- **Stage 1：PASS；Stage 2：PASS。** 无新增 HIGH / MEDIUM 问题。由主 Agent 对本轮 candidate 使用 `review-approve` 登记；本 reviewer 不改实现、不提交、不写 `.needs-review`。

### 快照核验

独立运行 `python .codex/hooks/harness.py review-status` 原始输出：

```json
{"currentId": "1246362d88ba2d31b949b0bafc4c480ca5d7c958700b39d122deb87d6b6fd7bc", "reviewedId": "0600502e17ef5b37c4a5b0b0672f634483d8cab3353d1b1acaddfd344c4ba224", "changedFiles": ["hengxin-smart-image/frontend/package.json"], "approved": false}
```

额外读取 `.codex/review-state.json` 比对 approved/candidate 全部文件摘要，唯一差异仍为 package.json。将当前文件中的版本精确替回 `0.2.75`，按协议归一换行计算 SHA256，与已批准摘要相等；JSON 结构比较唯一变化键为 `version`。原始输出：

```text
changed: ['hengxin-smart-image/frontend/package.json']
version-only reconstructs approved bytes: True
JSON changed keys: ['version']
```

因此两处修复、三份测试、构建配置和锁文件均与上一轮已审内容一致，无未审实现混入。普通 Markdown 不进入代码摘要，本轮另行阅读源文档 diff，未用代码摘要替代文档审查。

### Stage 1 · Spec Compliance

| 条目 | 结论与证据 |
| --- | --- |
| 版本及发布范围 | 完整匹配。`hengxin-smart-image/frontend/package.json:3` 为 `0.2.76`；`DEV-PLAN.md:3`、`Product-Spec-CHANGELOG.md:3` 限定国内前端普通发布，固定提交打包、stage/prepare/deploy/verify、正式入口与保持性核验均有明确完成标准。 |
| 修复功能与授权文档 | 完整匹配。`Product-Spec.md:5` 的 suspended/changed/invalid、遮蔽、返回重验、状态保留、真实失效及迟到响应条目均沿用上文逐项审查；`src/views/hengxin/domestic-studio/use-tasks.ts:110`、`src/views/hengxin/admin/workspace-sessions/use-monitor.ts:73` 及测试摘要不变。没有扩大后端、数据库或海外范围。 |
| 状态真实性、UI 与引导 | 匹配。`Product-Spec.md:7` 与 `DEV-PLAN.md:5` 明确尚未生产发布，且说明浏览器事件链验证不等同 OS 切页。新受控差异仅 package 版本，没有模板、样式、文案或入口变化；复用上文实际页面视觉对比证据。 |
| Spec 漂移 | 无。`package.json:3` 只更新发布元数据；没有新增功能、依赖、API 或数据结构。 |

本增量范围无部分实现或未实现；部署及生产验收属于下一步，未列作本地代码已完成能力。

### Stage 2 · Code Quality

- **质量与安全 PASS**：`package.json:3` 的唯一变化是有效版本字符串；JSON 可正常解析。摘要及 JSON 键比较证实脚本、依赖、锁文件和安全相关实现不变，没有新增密钥、执行入口或权限分支。复用上文两处实现的质量和安全扫描结论。
- **测试真实性 PASS**：本轮重新读取 `output/task-visibility-unit.log:631`、`output/task-visibility-typecheck.log:1`、`output/task-visibility-build.log:522` 和浏览器 JSON；其结果与上文相符。浏览器解析结果为 `result=PASS`、15 项 checks、errors/unexpected 为空。测试和实现摘要均未改变，因此复用既有行为、故障路径及视觉证据，不重复全套回归。
- **编译证据复用边界**：以下是此前已审实现的原始输出，本轮没有重新执行编译；发布包须由主 Agent 按固定提交构建并验证实际产物，不能把旧构建产物视为新版本发布验收。

```text
ℹ tests 597
ℹ suites 0
ℹ pass 597
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 30223.0894
```

类型检查日志原始输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
```

国内生产构建结束输出：

```text
✓ built in 42.12s
```

本轮只追加报告，未观察到审查期间受控代码变化；批准对象仅为本节明确的新 candidate。生产版本生效、实际切页恢复、非目标组保持、保留版本及清理结果仍由发布验收记录证明。
