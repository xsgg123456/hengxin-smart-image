# 海外创作工具集正式应用审查

| 项目 | 结果 |
| --- | --- |
| 最终 candidateId | `f5d76b153267bf422c5a582b9cd0fe1361d114beb0ad2cbb8f81eb003cf756f0` |
| Stage 1 · 需求与设计 | PASS |
| Stage 2 · 代码质量 | PASS |
| 分支与范围 | main 工作区的海外 API、数据库迁移、海外及共享登录前端、相关测试。对照 Product-Spec.md:1629、Product-Spec.md:1639 和 DEV-PLAN.md:1877。本地 preview-creative-workflow 仅作设计基准。生产工具、提交和部署另行验收。 |

## 快照变化

首轮 `762df137a91e5e944a8a5f723077142254bc4b2190bfb63978141cb6fbd0bef3` 在 Stage 1 发现 HIGH。非设计人员查看他人成品时，列表封面、归档历史、详情图片带出了创作者可自由填写的私有会话名及会话 ID。即使任务直链返回 403，详情仍能显示会话名。原证据为后端 `archives/service.py:50`、`archives/audit.py:12` 和前端 `OverseasArchiveDetail.vue:28`。首轮停在 Stage 1。

对最终快照从 Stage 1 重新核对。列表按来源任务权限裁剪封面和最新事件；详情裁剪封面、每张图和全部历史，前端对无权访问者隐藏会话筛选和来源说明。精确路由清单已同步。额外的两账号验证见后文。审结前 review-status 返回的 currentId 与表中一致。

以下后端路径相对于 `hengxin-smart-image/backend/app/overseas/`，前端路径相对于 `hengxin-smart-image/frontend/src/`，测试路径分别相对于对应端的 `tests/`。

## Stage 1 逐项核对

| 需求与结论 | 实现与验证 |
| --- | --- |
| 八入口、三种表单与固定元数据，完整 | 前端 `api/overseas/creative-tools.ts:1`、`views/overseas/creative-tools/CreateCreativeTask.vue:19`、同文件第 66 行。复用平台和语言枚举，三项 Amazon 固定品牌，四项固定其他平台，自定义只显示一个字段。后端 `tasks/creative_tools.py:4`、`tasks/schemas.py:35`、`tasks/service.py:82` 从入口生成平台和品牌。后端测试 `test_overseas_creative_tools.py:31` 对八个创建结果逐项断言；第 51 行验证空值、非法字段与非法语言。 |
| 一次提交、一条本人任务，直接进入工作台，完整 | `tasks/service.py:90` 创建本人负责的独立任务、SKU 和会话；第 101 行按账号和操作区分幂等请求。前端 `CreateCreativeTask.vue:37` 和 `views/overseas/creative-tools/CreativeTools.vue:64` 连到实际任务路由。浏览器 `creative-workflow-real.browser.mjs:47` 丢失第一次响应后重试，复用同一任务；后端并发测试 `test_overseas_tasks_postgres.py:79`。 |
| 我的创作、品名或 SKU 检索、刷新续作，完整 | `tasks/queries.py:91` 在计数和分页前限制本人创建且属于八入口；前端 `views/overseas/creative-tools/MyCreations.vue:15`、`views/overseas/OverseasTasksPage.vue:4`。浏览器实测同 SKU 的他人任务不会进入本人结果，搜索空态、按 SKU 找回及刷新均通过。 |
| 真实会话、素材、草稿、生成结果及归档，完整 | `studio/service.py:59` 调用现有执行入队，`studio/execution.py:25` 关联任务与持久会话，第 94 行使用冻结 Skill，`studio/files.py:120` 收件，`studio/service.py:131` 按选中图片归档。独立测试让原有执行结果发布器写入两张测试图，只选一张归档，验证另一张可由本人再次引用。正式业务入口与既有执行器已连通。 |
| 角色分配、统一登录与本人工作台限制，完整 | `auth/models.py:11`、`members/schemas.py:7`、前端 `api/overseas/members.ts:4`、`api/identity/auth.ts:13`、`views/auth/IdentityPortal.vue:137`。真实业务 API 的测试身份登录后可进入工具集。 `permissions.py:33`、第 69、129 行限制非设计人员；`studio/queries.py:20`、`materials/service.py:28`、`execution/router.py:24` 校验任务。实际权限回归见下。 |
| 团队成品可读可下载；来源分别鉴权，完整 | `archives/service.py:64`、第 96、140、153、172 行分别限定列表、来源信息、图片及打包内容；`archives/audit.py:26` 对事件照片按字段筛选；前端 `views/overseas/OverseasArchiveDetail.vue:26`。 `test_overseas_archive_audit.py:152` 覆盖六个响应位置。独立通过双账号场景核对四种私有读取与本人继续创作。 |
| 创建时身份快照、旧数据未知与成品筛选，完整 | `tasks/service.py:120` 取实际单一岗位，设计与设计主管记录为设计人员，非设计人员独立记录；获管理员授权且岗位仍为设计的账号沿用实际岗位，单一超级管理员角色缺少岗位依据时留空。`archives/snapshot.py:13` 首次归档复制快照；`archives/service.py:70`、前端 `views/overseas/OverseasArchivePage.vue:12`、同文件第 61 行及 `api/overseas/archives.ts:5` 支持标签、全部与两项筛选。见 `test_overseas_creative_tools.py:62`、第 90 行及 `test_overseas_archive_audit.py:152`。 |
| 八项独立 Skill 设置、执行端复验与旧入口兼容，完整 | `management/tool_bindings.py:11` 返回初始空映射；第 18 行按管理员权限和预期旧集合更新；`management/skills.py:33`、第 45 行在工作台候选和发送时均校验已开启且绑定到任务的工具；`studio/service.py:61` 保留原自定义入口禁用 Skill；`studio/execution.py:30` 处理冻结作业及无 Skill 的执行参数。前端 `views/overseas/admin/WorkspaceSkills.vue:48`、第 69 行。测试 `test_overseas_tool_bindings.py:26`、第 71 行涵盖八组、多选、切换、不同品牌、删除绑定和旧作业重放。 |
| 图片工具、目录及弹窗与确认预览一致，完整 | `views/overseas/creative-tools/CreativeTools.vue:41` 排列爆款复刻、去掉产品、白底、改字、抠图、换色；每组 JPG、说明和动画场景保持绑定；模板第 90 行沿用原卡片。实开设计任务中心、确认预览和正式工具集。1440×900 时正式与预览均呈 14 卡、行数分布 4/4/4/2、卡片宽 267 px、图高 149 px、标题 17 px；OUTON 弹窗的五个字段同序。独立浏览器另在 390 px 宽通过自定义表单和续作。 |
| 0028→0029 与历史兼容，完整 | `../../migrations/overseas/versions/0029_creative_tools.py:9` 只调整海外角色约束、新增可空列、创建空绑定表，不回填历史身份。`test_overseas_creative_migration.py:11` 在含历史数据的 0028 上升级、比较新旧行及国内库快照；主 Agent 提供该 PostgreSQL 组及并发组通过的结果。迁移第 28 行显式拒绝降级；回退业务代码与数据库迁移须分别处理。 |

## Stage 2 代码质量、安全与测试

- 幂等请求在权限收窄之后仍验证当前访问权。任务、会话、事件和回执同事务提交。Skill 绑定修改与执行准入共享数据库锁，并发管理员修改使用预期集合检查。证据为 `tasks/service.py:101`、`management/tool_bindings.py:23`、`management/settings.py:69`、`test_overseas_tool_bindings_postgres.py:17`。
- 范围内正式源码检查了硬编码密钥、前端密钥前缀、动态执行、直接写 HTML 和本机路径；未发现新增命中。新接口在路由层或服务层鉴权，写请求校验浏览器来源。迁移内插的表名为固定二元组。证据为 `management/router.py:56`、`tasks/router.py:45`、`../../migrations/overseas/versions/0029_creative_tools.py:17`。
- 新增业务源码均在 300 行以内。范围内的任务入口、绑定、归档身份和角色定义均有对应需求。前端生产构建的海外模块图与独立预览入口分开，见 `hengxin-smart-image/frontend/release-scope.config.ts:14`。未发现新增独立产品页面或与本次需求无关的表。
- 与真实执行有关的断言到达持久 Job、冻结包准备及工作台重新入队，见 `test_overseas_tool_bindings.py:71`。两账号补充测试使用独立海外数据库、内存对象仓库、真实业务 HTTP 与回执发布器。测试图片代替模型输出，本次审查没有调用收费模型。浏览器身份提供方也是本地夹具，线上企业身份与部署结果应以对应发布验收为准。

## 运行证据

审查人实跑后端创作、Skill、归档、路由清单回归以及独立两账号成品读写。后端 compileall 无标准输出，退出 0。前端 vue-tsc 无诊断，退出 0。以下为关键原始输出。

```text
54 passed, 2 warnings in 10.89s
team archive read=200 download=200 foreign studio/transcript/upload/draft=[403, 403, 403, 403] own material/draft/resume=200
1 passed, 2 warnings in 2.32s
✓ built in 30.50s
PASS eight forms, real idempotency replay, owned search/resume, scoped navigation, private URL, desktop/mobile; no model invoked
```

修复后归档回归日志记录 `15 passed, 2 warnings in 11.95s`，归档 UI 记录 `pass 11`、`fail 0`。Windows 全量初跑的 9 项失败中，路由白名单缺少新增的三个路由，另外 8 项使用 POSIX 安全文件打开或符号链接。路由清单修复后在上述 54 项中通过，Linux 相关组记录 `52 passed, 2 warnings in 14.69s`。这些结果未计作 Windows 全量全通过。日志在 `output/overseas-creative-20261121/`，审查构建与独立双账号用例在 `output/creative-workflow-1121/`。
