# Phase22 独立两阶段审查

- 最终 candidateId：`35588976b7e92a1d2732d2687872e952b42157c4dde6149fa26139ebf938e47d`
- Stage 1：**PASS**。Stage 2：**PASS**。当前无未解决 HIGH/MEDIUM 项。
- 基线：Phase21 `0f68773`。依据：Product-Spec.md 海外段、DEV-PLAN.md Phase22、docs/OVERSEAS-PHASE22-CONTRACT.md 全文、既有海外页面。
- 范围：`hengxin-smart-image/` 下海外 plans 六模块、0007迁移及注册、资料提交/任务查询和事件适配、方案 API/Vue/任务及执行接入、方案测试、identity-test Phase22 与必要旧用例适配。下表路径均相对该目录。
- 排除用户既有技能、gitignore、Design-Brief、frontend package/locales、专用 overseas-preview、workflow/preview-adapter、Detail/Annotation/Pictures/Archive/admin 预览及预览测试。Phase23/24 合同只作为未来范围，不当成本期缺陷。

## 快照与已关闭问题

初次候选为 `5d4a086cd2867eec7929a712c05fab562df8c5ae46bd1a7bc84a536f8e6e5bd5`。全量回归发现 **MEDIUM：测试路由白名单未同步**，`backend/tests/test_overseas_configuration.py:156` 精确路由集合缺少本期三条 API，导致一个失败。主 Agent 在该文件第170行补齐三项，没有放宽断言。审查者复核 diff 并独立复跑31项全部通过。

审查构建临时生成预览组件类型声明，主 Agent 恢复 `frontend/src/types/import/components.d.ts` 至原 HEAD；已检查该文件相对 HEAD 无差异。中间候选 `82e69b70a9b4376b823218505a3d54e8d8085bb35c043f0d3789e92da055c17d` 不批准。最终候选仅在初次候选上增加上述测试白名单修复；已用 review-status 确认最终编号。普通计划/验收 Markdown 的更新不改变代码快照。

## Stage 1：Spec Compliance

|合同条目|结论与代码证据|验证证据|
|---|---|---|
|持久方案、独立0007迁移|完整实现。`backend/app/overseas/plans/models.py:8`，`backend/migrations/overseas/versions/0007_plans.py:12`；独立元数据、task/version唯一、job唯一及状态约束。|`backend/tests/test_overseas_plans_migration.py:11`；审查者 Linux/PG 专项包含空元数据、0006升级重复执行及国内库不变。|
|有效首次/补交资料自动分析，旧submitted任务可启动|完整实现。`backend/app/overseas/materials/service.py:64` 同事务绑定并调用 enqueue_analysis；`backend/app/overseas/plans/service.py:89` 接收旧任务；没有资料则拒绝。|`backend/tests/test_overseas_plans.py:47`、`:119`、`:136`；故障注入证明任务/Plan/Job/outbox 全部回滚。既有资料测试验证重复提交。|
|全量SKU、原件和完整解析/Skill冻结|完整实现。`backend/app/overseas/plans/snapshot.py:18` 冻结任务字段、全部SKU、原件对象标识/checksum、完整文本与解析版本，`backend/app/overseas/execution/queue.py:25` JSON复制后持久化。|`backend/tests/test_overseas_plans.py:47` 使用完整长文本断言，并验证生成作业继承冻结资料和完整方案。|
|CLI严格plan.json与安全边界|完整实现。`backend/app/overseas/plans/analysis.py:12` 固定协议不拼入资料指令；`:24` 检查完成回执、安全读取和重复JSON键；`schemas.py:17`、`:30`、`:42` 强制字段、精确SKU集合/无重复、正整数≤8192、最多100图及文本限制。|`backend/tests/test_overseas_plans_protocol.py:14`、`:34`、`:57` 覆盖缺字段/空/错SKU/重复/boolean尺寸/超限、缺产物、链接、目录、超大文件及不完整回执；Linux实测通过。|
|事务发布，失败不伪造方案|完整实现。`backend/app/overseas/plans/analysis.py:32` 校验当前Plan/job/任务状态并发布；复用 `backend/app/overseas/execution/claims.py:116` 的锁与事务。|`backend/tests/test_overseas_plans.py:154` 发布后注入异常，Plan/Task/Job均保持原状；真实HTTP离线子进程产物错误进入失败态。|
|五角色与数据范围|完整实现。`backend/app/overseas/plans/service.py:36` 读取按任务授权；`:67` 每次写操作锁成员权限及任务，复用 `backend/app/overseas/permissions.py:25` 统一矩阵。设计负责人/设计主管可写，超管需兼任设计业务角色。|`backend/tests/test_overseas_plans.py:97`、`:154`，`backend/tests/test_overseas_plans_postgres.py:24`；真实HTTP验证未分配设计403、纯超管403，真实浏览器验证运营只读。|
|版本/幂等、意见重分析、保留历史|完整实现。`backend/app/overseas/plans/service.py:45`、`:67`、`:89` 校验版本和请求指纹，ready方案必须非空意见，创建新Plan而不覆盖旧Plan。|`backend/tests/test_overseas_plans.py:75`；`backend/tests/test_overseas_plans_postgres.py:69` 两竞争请求只有一个新版本。|
|失败/取消可显式重试，活跃/uncertain禁止|完整实现。`backend/app/overseas/plans/service.py:21` 派生失败状态；`:45` 只允许终态重新分析，uncertain不属于终态。`frontend/src/views/overseas/OverseasPlans.vue:53` 同步限制操作。|`backend/tests/test_overseas_plans.py:106`；浏览器覆盖失败、uncertain和错误态。|
|只确认当前完整方案，一次按SKU入队|完整实现。`backend/app/overseas/plans/service.py:102` 要求ready/plan/succeeded，再校验内容；在同一事务冻结完整方案并按SKU enqueue，写请求记录。|`backend/tests/test_overseas_plans.py:47`、`:75`；PG同键竞争200/200、异键200/409、第二个SKU入队故障全回滚，`backend/tests/test_overseas_plans_postgres.py:49`、`:69`。|
|API合同与正式前端|完整实现。`backend/app/overseas/plans/router.py:12` 三路由符合合同；`frontend/src/api/overseas/plans.ts:29` 真实请求、禁缓存、任务绑定校验与版本/幂等键；`frontend/src/views/overseas/OverseasTasksPage.vue:23` 正式挂载组件。无模拟adapter导入。|方案前端2单测及真实身份/API浏览器独立复跑通过。|
|方案历史、SKU/完整图片建议、修改确认布局|完整实现。`frontend/src/views/overseas/OverseasPlans.vue:7` 版本选择/历史只读、`:18` SKU标签及完整说明/尺寸/提示词、`:26` 意见及按钮。|浏览器实际切SKU、选择历史版本、查看确认状态；1366px真实截图与390px交互截屏。|
|加载/空/错误/冲突刷新、未知请求保持原键|完整实现。`frontend/src/views/overseas/OverseasPlans.vue:60`、`:71`、`:76`；409刷新且保留意见，网络未知保留原请求键，撤权清理内容。|`frontend/tests/overseas-plans.browser.mjs:42` 起覆盖409、网络中断、历史、只读、撤权、空态、服务错误及窄屏裁切。|
|真实执行状态刷新、不显示假百分比|完整实现。`frontend/src/views/overseas/OverseasExecution.vue:39` 比较作业/事件后触发changed；`OverseasTasksPage.vue:72` 刷新详情；`OverseasPlans.vue:94` 跟随版本刷新且不清空意见。|浏览器事件刷新证明方案状态更新且编辑保留；真实页面仅展示事实排队/成功/失败。|
|阶段边界|无Spec漂移。`backend/app/overseas/plans/service.py:116` 只创建generation作业，图片交付协议属于Phase23；固定Skill属于本期快照，管理配置属于Phase24。无新增非合同业务页面/API/表。|真实页面显示生成等待，未伪称图片交付；`infra/identity-test/local_cli_fixture.py:10` 明确离线子进程替身。|

部分实现/未实现：本期条目无。真实收费Codex端到端、图片交付和生产部署未验证，属于明确排除范围。

## Stage 2：Code Quality

- **PASS，结构与类型**：plans 文件18–122行，分模型/Schema/快照/服务/协议/路由；前端 plans API 35行、Vue107行，无新增 any。证据：`backend/app/overseas/plans/service.py:17`、`frontend/src/api/overseas/plans.ts:5`、`frontend/src/views/overseas/OverseasPlans.vue:37`。复用幂等、权限、队列、进程、安全读取，未复制整套一期实现。
- **PASS，测试真实性**：PG测试以两个线程+Barrier真实竞争，不是模拟锁；事务注入异常后重新开session核对存储；POSIX安全文件用真实符号链接/硬链接。证据：`backend/tests/test_overseas_plans_postgres.py:49`、`:69`，`backend/tests/test_overseas_plans_protocol.py:34`。浏览器故障路径实际点击组件；HTTP真实子进程与真实模型验收分开记录。
- **PASS，安全扫描**：审查范围无eval、innerHTML、dangerouslySetInnerHTML、前端秘密变量或硬编码模型密钥；模板文本按Vue插值，SQL使用ORM表达式。证据：`frontend/src/views/overseas/OverseasPlans.vue:20`、`backend/app/overseas/plans/service.py:36`、`backend/app/overseas/plans/analysis.py:24`。读取授权、写操作CSRF、成员锁、版本和原幂等键均存在。
- **PASS，实际视觉比较**：审查者打开真实方案页、执行状态与邻居任务列表，比较同一Art卡片、边框圆角、蓝色按钮、间距和文字层级；方案行维持既有14px间距、18px垂直padding、13px正文与1.8行高。证据：`frontend/src/views/overseas/OverseasPlans.vue:100`、既有 `OverseasDetail.vue:269`。截图：`output/playwright/phase22/review-plan-panel.png`、`review-execution-panel.png`、`review-neighbor-tasks.png`；窄屏 `plans-mobile.png`。独立浏览器验证按钮及意见框不受祖先裁切。
- **已关闭 MEDIUM**：精确路由白名单漏三条；最终代码 `backend/tests/test_overseas_configuration.py:170` 与 `backend/app/overseas/plans/router.py:12` 一致，31项专项复验通过。

## 原始验证输出及限制

审查者独立运行 Linux 隔离PG/Redis，四个方案测试模块：

```text
34 passed, 2 warnings in 16.10s
CLEANED hx-overseas-regression-49a65b4b8ad6
```

完整日志：`output/phase22-review-linux.log`。本机另跑方案API/协议：`21 passed, 8 skipped, 2 warnings in 3.00s`；8个POSIX安全读在Windows跳过，但上述Linux实测全部覆盖。

修复后审查者本机configuration专项：

```text
31 passed, 2 warnings in 1.44s
```

主 Agent Linux同专项原始日志 `output/phase22-configuration-final.log`：

```text
31 passed, 2 warnings in 4.07s
CLEANED hx-overseas-regression-1d8c7169d6da
```

审查者独立类型检查/构建（退出0；日志 `output/phase22-review-typecheck.log`、`output/phase22-review-build.log`）：

```text
> hengxin-smart-image-frontend@0.2.21 typecheck
> vue-tsc --noEmit
✓ built in 33.95s
```

构建保留既有pnpm配置迁移提示，未在审查中升级或修改依赖。自动生成的预览声明已由主 Agent 恢复并复核。

独立前端测试和浏览器：

```text
ℹ tests 2
ℹ pass 2
ℹ fail 0
PASS real plans browser: real identity/API, confirmed full SKU plan, reload persistence, read-only confirmed state, no page errors
PASS plans: history; SKU; feedback; conflict refresh; unknown same-key retry; execution refresh preserves edits; confirm; failed retry; uncertain; empty; read failure; narrow clipping; readonly; revoke
PASS reviewer real plan/execution/tasks visual capture
```

首次浏览器命令缺本地playwright包，指定现有bundled PLAYWRIGHT_MODULE 后重跑成功，没有安装依赖。主 Agent 已有前端275项与真实HTTP Phase17–22证据，审查者读过 `output/phase22-http.log` 并核对 `infra/identity-test/phase22_checks.py:18` 的断言；这些不冒充审查者独立重跑全部用例。

全量回归原始结果必须保留：`output/phase22-backend-final.log` 为

```text
FAILED tests/test_overseas_configuration.py::test_overseas_liveness_routes_and_sanitized_errors
1 failed, 1986 passed, 17 skipped, 15 warnings in 320.60s (0:05:20)
```

失败仅为已关闭的精确路由白名单漏项，修后没有重新跑完整全集；采用同一业务实现的完整结果加修后31项专项作为验收证据，不写成一次1987项全通过。17个既有跳过项不算已验证。

结论仅适用于最终 candidateId 及上述范围。由主 Agent 对此候选执行 review-approve 登记 Stage1/Stage2 PASS；审查者未批准凭据、未写clean、未提交、未修改业务代码。
