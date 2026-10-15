# 海外管理统计与成品搜索审查 R1

- candidateId：`c373106a839b4fda7a2df3ba2284407ed76dce1faea4a346c40e2f1da907cf98`
- 范围：相对 `6022d1a` 的全部已跟踪改动和新增 0016 migration、操作者/迁移/浏览器测试；依据 Product-Spec.md:898、docs/OVERSEAS-ADMIN-SIMPLIFY-20261015.md:1、既有 Design-Brief.md。6022d1a 工作台修复仅复核本次触及的 recovery 兼容，不把旧审查扩展为全仓重新验收。
- 方式：读取 AGENTS、code-review skill、HARNESS-REVIEW 协议；逐项代码核查、日志核查、实际截图目视比较，独立运行发布专项测试。未修改产品代码，未执行生产动作。
- 快照：主体审查时 `review-status` 的 currentId 与上述 candidateId 一致。报告落盘后主 Agent 已重构发布脚本；最终实查 currentId 为 `b180b482bd6cc678b70fd25dc98af277dfcc9c5d93ecee30896e60d42def5d94`。本报告的结论和行号仅适用于旧 candidate，不覆盖新快照；主 Agent 将派 fresh reviewer 复核。
- **Stage 1：PASS。Stage 2：FAIL（1 项 MEDIUM 质量规范不符）。不得登记两阶段 PASS。**

## Stage 1：Spec Compliance

| 需求 | 结论与证据 |
|---|---|
| 管理员默认海外全员，不把单条数据当权限 bug | 完整实现。backend/app/overseas/permissions.py:26、:34 既有三管理角色 stats.read=all；本次未改权限。frontend/src/views/overseas/OverseasPortal.vue:8、admin/OverseasLiveActivity.vue:42 明确默认全员提示。专项计划:13 记录生产只读结果 2 成员、1 作业；这是主 Agent 采集证据，本 reviewer 未另行访问生产。 |
| 实际执行操作者，不用创建人/设计师替代 | 完整实现。backend/app/overseas/management/facts.py:24、:34、:39 用 Turn.actor_id；studio/models.py:22 的 job_id 唯一约束避免 join 重复计数；monitor.py:13、:21 输出真实姓名，旧作业 LEFT JOIN 保留 null；前端 OverseasLiveActivity.vue:20、:27 显示未记录。 |
| 汇总、分页、详情一致，普通不扩权 | 完整实现。facts.py:34 在筛选/计数前应用 stats.read scope；usage.py:9、:16 和 monitor.py:10 共享 scoped；router.py:10、:15、:26 均 stats.read。前端详情仅取已授权列表行（OverseasLiveActivity.vue:21、:27）。tests/test_overseas_management_operators.py:26 覆盖三管理角色、停用历史操作者、未知 UUID、422、普通运营/设计范围交集。 |
| 人员筛选同时影响汇总/列表，回第一页 | 完整实现。OverseasLiveActivity.vue:8、:52、:56，同一 query 并发读取两接口；api/overseas/management.ts:23 人员读取不依赖 members.manage。frontend/tests/overseas-admin-simplify.browser.mjs:24 起覆盖分页后选择/清除、monitor、人员失败重试与普通角色提示；后端 tests/test_overseas_management_operators.py:46 验证图片数量与列表一致。 |
| 删除海外 Token/费用 UI、类型、聚合、专用存储和写入 | 完整实现。frontend/src/api/overseas/management.ts:8、:9 与 OverseasLiveActivity.vue:46、:58 不再含废弃字段；预览 OverseasActivity.vue:24、:87 同步。backend/app/overseas/execution/models.py:23、runner.py:135、studio/recovery.py:103 去掉持久化读写；management/usage.py:7、monitor.py:10 不聚合/输出字段。搜索海外运行源码未发现 inputTokens/outputTokens/input_tokens/output_tokens/cost 残留。tests/test_overseas_management.py:91 断言接口字段不存在。 |
| 存量迁移、业务数据/原始 CLI 日志/国内保留 | 完整实现。migrations/overseas/versions/0016_remove_job_usage.py:11 仅 DROP overseas_jobs.usage，:18 拒绝降级；backend/app/overseas/db.py 的 schema head 升至 0016。tests/test_overseas_studio_migration.py:43 写入真实历史 usage、:52 起剔除目标列后比较全部业务行/长回复及国内快照；真实 PG 测试日志 15 passed。runner.py:135 仍解析原始 events，recovery.py:86、:98 保留原始日志校验、:106 保留恢复发布/审计。国内迁移与模型无改动。 |
| 成品统一搜索，OR 品名/品牌/SKU，保留业务数据 | 完整实现。frontend/src/views/overseas/OverseasArchivePage.vue:4、:23、:28 与 api/overseas/archives.ts:6 仅保留 search/page/pageSize；backend/app/overseas/archives/service.py:47、:56 使用三个字段 OR 和 autoescape。原始 Archive 业务字段仍在 archives.ts:3。预览 OverseasArchive.vue:93 同步逐字段 some，不拼接跨字段误匹配。 |
| 重置、刷新、分页、加载、空态、失败和移动端 | 完整实现。OverseasArchivePage.vue:4、:6、:25、:33、:34、:42：重置第一页、250ms 防抖期间显示加载、代次阻止旧响应回写、错误清空旧卡片、窄屏输入 100%。浏览器脚本:31 起覆盖三字段、页二后筛选回第一页、重置、空态、500 重试及控件裁切检查。已目视 desktop/mobile 截图，无遮挡和横向页面溢出。 |
| 备份排空后迁移、迁移后启新代码、失败关入口不可自动回旧版 | 完整实现于发布工具，尚未执行生产。scripts/release/overseas-upload-deploy.py:229 起按关入口/停 API→排空停执行器→验证完整备份→before_switch→新指针/API/执行器；overseas-attachments-deploy.py:83 验备份/排空标记、旧 schema/usage 列、owner migrate 服务设置、固定镜像，迁移后同时验 0016/列缺失；:18 明确 forward recovery。upload-deploy.py:283 失败关闭入口/停 API，不恢复旧代码或自动还原 DB。 |
| 镜像、源文件、schema 与范围防漂移 | 完整实现。scripts/release/member-release-runtime.py:99 检查测试镜像 ID，:112 仅允许 migrate image/build 改变；overseas-attachments-deploy.py:98 验 Compose 不变，:102 检查 exact image；overseas-upload-deploy.py:172 起验运行镜像、源文件 hash、native hash、国内/身份拓扑；package-overseas.py:56、:192 收录 0016 且 manifest 固定国内 0028/海外 0016。 |

表中 backend/frontend 路径均相对 `hengxin-smart-image/`。无部分实现/未实现条目。生产部署与生产复核是后续操作，不能用本报告声明已完成。

## Stage 2：Code Quality

### MEDIUM：发布主脚本继续超过 300 行质量上限

- 位置：`scripts/release/overseas-upload-deploy.py:48`、`:208`、`:316`。
- 证据：当前 `Get-Content ... | Measure-Object` 等价行计数为 **316**；相对 6022d1a diff 为 **+19/-7**，基线为 **304**。这不是新产生的首次越界，但本次迁移扩展继续把基线超限扩大了 12 行。
- 标准：`.agents/skills/code-review/SKILL.md:29` 要求“文件不超 300 行、单一职责”。当前文件同时承担 schema 钩子、prepare、部署、恢复文本及 CLI 分派；不能判为匹配。
- 修复建议：提取一个完整、可测试职责（例如恢复说明/版本钩子或部署状态处理）到独立发布模块，保持调用顺序与失败关闭行为，并重跑发布专项。不要仅删除空行规避标准。修复后重新 review-prepare，本报告不批准新快照。

### 其它检查

- 安全：本次差异未发现硬编码凭据、eval/HTML 执行/拼接用户 SQL；facts.py:14 使用 UUID/Literal/date 参数类型，:24 绑定 SQLAlchemy 条件；archives/service.py:53 使用 autoescape；新增 /operators 仍有 stats.read 且只在 scope 内列人。发布命令使用参数列表和经校验的 release/镜像，不拼 shell。
- 类型/错误处理：management.ts:7 起使用具体 TS 类型与运行时响应校验，没有新增 TS any；OverseasLiveActivity.vue:48、:59 保留加载、错误重试和卸载保护；OverseasArchivePage.vue:25 保留 epoch 隔离。
- 测试真实性：操作者后端用两个不同任务/实际 Turn.actor_id，与任务创建者不同；包含停用历史用户和普通权限交集，未用创建者冒充操作者。迁移测试在 PG 历史表填入非空 usage 后比对保留业务行。发布测试 scripts/release/test_overseas_attachments.py:36、:47、:232 注入迁移失败/漂移/缺备份/残留列并验证不切换、不开放。
- 测试限制：新浏览器脚本使用 API mock，统计列表 total=41 而只返回 2 行（:18），用于翻页交互，不能作为真实统计一致性的证据；真实一致性由后端多用户用例负责。截图数字因此不能当生产数据。Linux 完整后端仍在执行（审查时日志到 73%），不计入通过。
- 视觉：已打开并比较 `output/playwright/admin-simplify/stats-desktop.png`、`archive-desktop.png`、`archive-mobile.png` 和邻居基准 `output/playwright/local-skills-neighbor-settings.png`。相同 Art 侧栏、浅灰画布、白色圆角卡片与蓝色按钮；成品搜索 320px/移动 100% 与代码一致，无额外视觉系统。统计截图可见 Select 收起动画残影，不据此判定永久遮挡；浏览器功能检查已完成选择/清除。
- Spec 漂移：新增 /operators 是授权人员筛选的必要 API；0016 和发布钩子对应明确需求。`.agents/skills/bug-fixer/SKILL.md:33` 仅增加用户已采纳的实际支持输入/分支范围核查原则，无额外业务功能。

## 验证原始输出与边界

独立执行：`.\\hengxin-smart-image\\backend\\.venv\\Scripts\\python.exe -m pytest scripts/release/test_overseas_attachments.py scripts/release/test_package_overseas.py -q`

```text
................................................ [ 73%]
.................                                                        [100%]
65 passed, 24 subtests passed in 2.87s
```

前端构建原始输出（`output/frontend-admin-build.log:3` 及末行；读取已有完整日志）：

```text
> hengxin-smart-image-frontend@0.2.35 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ built in 40.34s
```

单测日志末尾（`output/frontend-admin-test.log`）：

```text
ℹ tests 364
ℹ suites 0
ℹ pass 364
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9267.5175
```

后端已有实测记录（`output/admin-backend-pg.log:5`、`:9`）：

```text
15 passed in 43.58s
57 passed, 2 warnings in 16.76s
```

全发布 Linux 套件原始结尾（`output/admin-release-linux.log:215`）：

```text
2 failed, 394 passed, 1 skipped, 165 subtests passed in 15.29s
```

其失败为既有 test_release_native 最后 overlay 断言与容器缺 git 的 package_delivery；相关测试/实现不在本轮差异。不能写成全发布 suite 通过。本 reviewer 的 65 项发布针对性复跑通过。完整 backend 在运行，尚无最终 exit/result。生产验证尚未执行。

## 交接

落盘后补充：完整后端日志已结束，实读 `output/admin-backend-linux.log` 最终原始输出：

```text
2348 passed, 188 skipped, 15 warnings in 290.31s (0:04:50)
```

上述“仍在执行”是主体审查时状态；本补充替代其未完成状态。主 Agent 已将资源不变检查迁往既有 overseas-upload-resources.py，并产生新 candidate；该重构未纳入本轮结论。不得把旧失败报告或旧 Stage 1 PASS 当作新快照审批。

主 Agent 按 Stage 2 质量问题路由重构；重新固定 candidateId 后从 Stage 1 复核差异，再运行 review-approve。当前报告不允许登记两阶段 PASS，不写 `.needs-review`。
