# 国内工作台及权限独立审查 · 2026-11-19

最终 candidateId 为 `907f7815dd7473898e897e5b47904e54ae528cc309b2638dd1c2b36152292f5d`。Stage 1 **PASS**，Stage 2 **PASS**。审查对象包括本次国内业务前后端、角色验证与兼容入口、0046 迁移、国内专项发布事务及对应测试。需求依据为 `Product-Spec.md:3`、`Product-Spec.md:5`、`Product-Spec.md:7`、`Design-Brief.md:3` 与 `DEV-PLAN.md:3`。生产切换及切换后的验收由发布流程记录。

初次送审编号为 `9a49e083f64028be96b4af77fd399e5b95b567ed4a0556d48b04d573b6a8581c`。审查期间变更位于 `hengxin-smart-image/backend/tests/test_media_delivery_lifecycle.py:30`，API 媒体和 ZIP 的传输测试改用具有访问权的身份，普通文件仍用操作员。已复查该差异、独立核对最终 review-status，并核对最终媒体测试结果。下方路径中的 backend 和 frontend 均位于 hengxin-smart-image/。验证日志及浏览器报告均位于 output/domestic-general-20261119/。

## Stage 1 · 需求及交互

| 需求 | 结果与证据 |
| --- | --- |
| 通用新品独立且置首，沿用会话、逐轮 Skill、归档 | 完整。前端以 general 建立独立路径并说明支持任意品类，后端将其登记为新品归档来源。见 `frontend/src/api/shared/domestic-workspace-keys.ts:1`、`frontend/src/api/hengxin/domestic-workspaces.ts:4`、`backend/app/modules/domestic_studio/workspaces.py:5`。隔离库分入口验证任务、绑定、会话及归档，见 `backend/tests/test_domestic_workspaces_http_pg.py:34`。浏览器报告 `general-browser/report.json:3` 包含 general 连续两轮有、无 Skill 的请求。 |
| 原膜业务改名，通用改图置首，其他业务顺序延续 | 完整。film 路径和标识保留，标题更新，edit 在替换业务首位。见 `frontend/src/api/hengxin/domestic-workspaces.ts:7`、`frontend/src/api/shared/domestic-workspace-keys.ts:2`。菜单与路由标题取同一注册表，已有工作台标签会刷新标题，见 `frontend/src/router/modules/index.ts:15`、`frontend/src/store/modules/worktab.ts:446`。迁移只替换五个 CHECK，不更新历史行；已检查真实 PostgreSQL 迁移及有 general 记录时拒绝收窄约束的用例，见 `backend/migrations/versions/0046_general_workspace.py:15`、`backend/tests/test_domestic_workspaces_migration_pg.py:23`。 |
| 同业务全员任务、统计、搜索、状态、分页 | 完整。列表要求业务参数，成员范围由已激活的业务角色控制。计数和分页共享业务、搜索和删除过滤，并按状态求页总数。见 `backend/app/modules/domestic_studio/task_router.py:19`、`backend/app/modules/domestic_studio/task_queries.py:45`、`backend/app/modules/auth/permissions.py:5`。双成员、跨业务、不匹配名称、两页和状态计数断言见 `backend/tests/test_domestic_shared_tasks_pg.py:20`。 |
| 他人及超管从业务入口只读，创建人沿用原操作 | 完整。任务、业务、会话、创建人逐层核对；只读路由仅提供 GET/HEAD。附件由已提交轮次的附件 ID 白名单授权，生成文件按轮次、会话归属读取。见 `backend/app/modules/domestic_studio/shared_task_router.py:20`、`backend/app/modules/domestic_studio/admin_details.py:18`、`backend/app/modules/domestic_studio/admin_details.py:35`。任务写入口和兼容会话入口检查当前身份归属，发送、上传、恢复与归档沿用此边界，见 `backend/app/modules/domestic_studio/task_scope.py:13`、`backend/app/modules/domestic_studio/task_service.py:17`、`backend/app/modules/domestic_studio/router.py:148`、`backend/app/modules/domestic_studio/archive_router.py:24`。隔离库实验核对已提交附件和结果可取、暂存附件不可取、跨任务/跨业务拒绝、写入拒绝、超管亦受限、禁用后读操作拒绝，见 `backend/tests/test_domestic_shared_tasks_pg.py:42`。 |
| 阅读不写会话、草稿或选中态；管理任务中心权限延续 | 完整。业务页对其他人挂载只读组件，选中态在查看方组件内。所有者页面独立进入编辑组件。见 `frontend/src/views/hengxin/domestic-studio/TaskPage.vue:15`、`frontend/src/views/hengxin/admin/workspace-sessions/ManagedTaskWorkspace.vue:22`。读取前后比较业务表、任务和幂等回执，见 `backend/tests/test_domestic_shared_tasks_pg.py:69`、同文件第 102 行。管理列表与会话使用管理权限，业务只读详情不借用管理 URL。见 `backend/app/modules/domestic_studio/task_router.py:64`、`backend/app/modules/domestic_studio/shared_task_router.py:51`。 |
| API 换套图整组仅超管可用，覆盖历史入口及接口 | 完整。父子菜单都声明同一角色，路由、默认入口、旧标签执行权限判断；权限变化清除已加载的工作台状态。见 `frontend/src/router/modules/index.ts:5`、`frontend/src/router/business-route-access.ts:18`、`frontend/src/release/navigation.ts:2`、`frontend/src/store/modules/worktab.ts:441`、`frontend/src/domestic-main.ts:53`。服务端覆盖任务、文件 GET/HEAD、ZIP、会话、报表，SSE 在开始及轮询时复核角色。见 `backend/app/modules/api_image_edits/router.py:27`、`backend/app/modules/api_image_edits/conversation_router.py:46`、`backend/app/modules/management/api_usage.py:126`、`backend/tests/test_files.py:42`。浏览器四角色用例包含降权后回到新品通用页，见 `frontend/tests/api-only-menu.browser.mjs:72`。 |
| 已批准的国内专项发布能力 | 完整。旧版锁定为 3247094、国内 0045，候选限定国内 full。独立以旧发布包和当前源码重算 11 个后端发布文件差异，SHA-256 为 `ec075bf43af98fdc893a584a677cc35cd49a22374b2c56d3b19e95656a04a9ac`，迁移文件 SHA、唯一共用源码 dingtalk.py 的前后 SHA 均匹配。见 `scripts/release/intranet/domestic_general_policy.py:6`、`scripts/release/intranet/domestic_workspaces_policy.py:31`。工具先排空国内任务，核验停止、备份和历史行，再迁移；按实际 schema 选择迁移前回退或迁移后恢复原候选。海外、共享分别比对运行与资源状态，成功后推进台账。见 `scripts/release/intranet/engine.py:163`、`scripts/release/intranet/domestic_tasks_engine.py:83`、`scripts/release/intranet/domestic_tasks_release.py:91`、同文件第 164 行、`scripts/release/intranet/domestic_general_history.py:10`。 |

设计对照使用业务只读页面与管理任务中心的实际 Chrome 渲染截图。两者均保留成员列、任务头、会话列、只读提示及原有结果面板。业务侧“只读查看”与本人“进入任务/更多”对应，见 `frontend/src/views/hengxin/domestic-studio/TaskList.vue:6`、`frontend/src/views/hengxin/admin/workspace-sessions/SessionDetail.vue:10`、`shared-browser/member-shared-task.png`、`shared-browser/detail-1920.png`、`shared-browser/report.json:4`。浏览器几何检查还覆盖 1000 和 390 像素。只读端新增 API 服务于已确认的数据范围；本次功能未发现偏离 Spec 的新页面、表或操作。

## Stage 2 · 质量、安全与验证

- 业务只读详情复用既有管理投影并传入独立文件根路径。响应对象逐字段生成，提交过的附件须在同会话且状态为 ready，文件响应标记 private/no-store。新增业务路由不接受写动词。见 `backend/app/modules/domestic_studio/admin_details.py:24`、`backend/app/modules/domestic_studio/shared_task_router.py:63`。已检查变更的生产和发布代码，新增行模式扫描未发现 eval、HTML 注入入口、暴露的前端密钥变量、对应密钥前缀或新增 as any。发布校验的 SQL 表名受正则及已知表集合约束，见 `scripts/release/intranet/domestic_workspaces_history.py:48`。
- 模块大小有既有偏差。工作标签 store 从 573 行增至 578 行，本次增量只有角色过滤和业务标题恢复，位置为 `frontend/src/store/modules/worktab.ts:437`。新增生产模块均在 300 行以内。
- 本次未调整依赖与锁文件。`dependency-audit.json:6` 的项目存量扫描汇总为 low 11、moderate 51、high 73、critical 0，报告未返回 advisory 明细。代码审查 PASS 的范围为本次变更。
- 浏览器测试运行真实前端并截获业务 API；真实数据库权限与写入不变性由 PostgreSQL HTTP 用例独立验证。`frontend/tests/workspace-sessions.browser.mjs:1`、`backend/tests/test_domestic_shared_tasks_pg.py:42`。general 浏览器目录中的 failure.json 时间为 11:19:37，随后 11:21:03 的成功重跑报告包含完整检查及空 errors/unexpected，采用后一次结果。

### 构建和测试原始输出摘录

```text
> hengxin-smart-image-frontend@0.2.79 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
✓ built in 1m 1s
ℹ tests 602
ℹ pass 602
ℹ fail 0
55 passed, 2 warnings in 23.62s
18 passed, 2 warnings in 30.47s
603 passed, 5 skipped, 21 subtests passed in 69.37s (0:01:09)
34 passed, 2 warnings in 17.20s
```

以上分别来自 `typecheck-final.log`、`domestic-build.log`、`frontend-final.log`、`workspaces.log`、`sharedtasks.log`、`release-final.log`、`media-final.log`。工具测试保留 5 项跳过记录。

初次候选的后端全套输出为 `17 failed, 3455 passed, 233 skipped, 10 warnings in 734.64s (0:12:14)`，17 项失败均在旧媒体夹具，见 `backend-full.log:208` 起。最终快照媒体复测记录为 34 项通过，涵盖原失败用例。此报告区分旧全套结果与最终局部复验，不将两次记录合算为最终快照的单次全量结果。
