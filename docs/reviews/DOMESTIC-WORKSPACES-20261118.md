# 国内新增五个工作台代码审查

候选 `93458f8be4de1a35a752abd4b946d470f56e0e4cd757f449bd683442108d1087`。审查范围为 main 工作区本次国内工作台、登录、管理和归档、0045 迁移、国内专项发布及测试差异。需求依据为 Product-Spec.md:3、Design-Brief.md:3、DEV-PLAN.md:3 和 docs/DOMESTIC-WORKSPACES-20261118.md:5。下文应用路径以 hengxin-smart-image/ 为起点，发布工具路径以 scripts/release/intranet/ 为起点。

## Stage 1 · Spec Compliance · PASS

| 验收项 | 实现和验证 |
|---|---|
| 四项新品、一项产品替换、保留旧五项 | frontend/src/api/hengxin/domestic-workspaces.ts:3 按业务逐项核对，film 手机膜、cable 数据线、earbud 耳机保护套、accessory 创意配件、edit 通用修改。四类配件共用一个带完整括号说明的标题。frontend/src/router/modules/index.ts:15 用注册表生成正式路由。backend/app/modules/auth/dingtalk.py:20 与 frontend/src/api/hengxin/session.ts:25 接受对应登录回跳。后端五个回跳参数用例和浏览器十入口检查通过。 |
| 本人任务、会话、附件、对话和逐轮 Skill | frontend/src/views/hengxin/domestic-studio/TaskPage.vue:43、use-tasks.ts:49 将列表与创建绑定到当前业务，拒绝把其他业务的详情呈现在此入口。backend/app/modules/domestic_studio/task_service.py:18 检查用户，:38 检查会话业务，:63 保存真实业务。backend/tests/test_domestic_workspaces_http_pg.py:52 逐项创建任务、会话、上传及携带指定 Skill 的任务轮次。浏览器 report.json 的十组发送记录含有技能及下一轮空值。 |
| Skills 管理、任务中心、会话业务名 | frontend/src/views/hengxin/admin/DomesticStudioBindings.vue:6 逐项显示业务并存入对应键，backend/app/modules/domestic_studio/bindings.py:39 校验全量键，序列化绑定更新并校验旧值。frontend/src/views/hengxin/admin/workspace-sessions/presentation.ts:5 使用同一标题；backend/app/modules/domestic_studio/admin_router.py:32 接受统一业务类型。backend/tests/test_domestic_workspaces_http_pg.py:39 核对新旧绑定共存，:81 验证普通任务读取的用户隔离、管理员任务和会话筛选。 |
| 成品库归档权限、真实来源和展示 | backend/app/modules/domestic_studio/workspaces.py:5 区分六新品与四替换，policy.py:19 校验写权限，archive_queries.py:35 校验列表来源。frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:90 按组显示归档，library.vue:4、:8、:11 分别对应来源选项、卡片与详情。真实 HTTP 用例 backend/tests/test_domestic_workspaces_http_pg.py:70 证实四个新增新品各自归档并按来源取回；edit 创建归档返回 403，来源查询返回 422。 |
| 原 0044 数据和五表 CHECK | backend/migrations/versions/0045_domestic_workspaces.py:10 列明五表，:17 只替换工作台 CHECK；四表允许十项，归档表允许六项。backend/tests/test_domestic_workspaces_migration_pg.py:35 逐行对照前后数据，:48 验证非法值及有新业务记录时回降失败。审查者在 PG 18.6 上独立调用实际历史校验函数，五张表共 22 条历史记录的行数、摘要和新旧谓词均通过。 |
| 专项发布边界 | domestic_workspaces_policy.py:13、:27 固定 45b1280 后端基线、0044→0045、完整后端差异摘要和运行时输入，:23 仅豁免前后哈希相符的登录模块。domestic_tasks_policy.py:42 仅临时过滤已审迁移路径；scope_changes.py:154、:174 继续核验依赖、归属和未知改动。release_cli.py:39 单独分派专项命令，:48 保留普通维护门禁。domestic_tasks_marker.py:22 和 stage.py:71 避免切换途中交叉操作。专项测试拒绝混入旧迁移或额外后端变更。 |
| 排空、备份、失败恢复、跨组保持 | engine.py:162 在停工作进程前关闭入口、排空；:229 在排空失败路径恢复接入。domestic_tasks_engine.py:69 核对备份大小与 SHA，:83 校验源版本，:101 复核目标版本和历史。domestic_tasks_release.py:198 依据真实库版本分别恢复旧版或前向恢复，domestic_tasks_engine.py:169 在启动前校验候选摘要。domestic_tasks_release.py:91 核对配置、海外与共享组、资产回退、容器及原生服务，:145 成功后推进台账，:127 自动清理。生产切换与现场清理回执由发布阶段验收。 |
| 设计一致性、引导真实性、范围 | 对照 output/playwright/domestic-workspaces-20261118/creative-accessories-menu.png 和同目录 workspace-1920.png 的实际渲染。展开侧栏宽 230 px，创意配件名称分三行完整显示；工作区标题、控制条、方案栏和归档入口均复用相机配件页面。frontend/src/components/core/layouts/art-menus/art-sidebar-menu/theme.scss:134 处理长名称，frontend/tests/domestic-explicit-skill.browser.mjs:110 检查裁切与溢出。附件与逐轮技能引导有上述 HTTP 和浏览器行为对应。新增代码均落在此次菜单、数据契约和发布维护范围。 |

## Stage 2 · Code Quality · PASS

- 前端由 frontend/src/api/shared/domestic-workspace-keys.ts:1 统一键和类型，后端由 backend/app/modules/domestic_studio/workspaces.py:5 统一请求、权限和 ORM 的取值域。历史迁移保留独立常量，避免后续业务增长改变已经发布的 0045。
- 文件交付和 SQL 构造已检查。frontend/src/api/shared/attachment-download.ts:7 限定同源内容端点、资源结构与工作台枚举，:15 禁止跟随重定向。domestic_workspaces_history.py:48 在表名参与 SQL 前用完整匹配限制标识符，:51 只返回计数和摘要。变更代码中未发现新增明文密钥、动态执行或未限制的外部下载地址。
- 测试证据分层。浏览器脚本使用真实前端并拦截 API，见 frontend/tests/domestic-explicit-skill.browser.mjs:74。独立 PG/HTTP 用例使用真实路由和数据库，归档传输替换成本地同步调用，模型任务完成状态由测试构造，见 backend/tests/test_domestic_workspaces_http_pg.py:48、:66。发布故障注入见 test_domestic_workspaces_release.py:19；不据此推断生产实际执行过切换或恢复。
- **LOW** 深色侧栏在 frontend/src/components/core/layouts/art-menus/art-sidebar-menu/theme.scss:265 重复 :134 的长标题规则，两个选择器声明相同，常规主题规则已覆盖深色侧栏。可在后续样式整理时合并。

### 实测与构建原始输出

审查者重跑 `vue-tsc --noEmit` 退出码 0，无标准输出。Windows 发布工具专项与配置验证、WSL PostgreSQL 上五个登录回跳及两个数据库/HTTP 用例、真实约束及历史摘要探针分别输出如下。

```text
.....................                                                    [100%]
21 passed in 1.09s
7 passed, 2 warnings in 7.90s
reviewed migration and login digest match
PostgreSQL 180006 tables 5 historical rows 22 checks/hashes PASS
```

前端原始记录来自临时目录 hx-front-20261118-workspace-tests-final.log、hx-front-20261118-build.log 和 hx-front-20261118-overseas-build.log，国内与海外各自的 dist 产物在 output/workspace-build-20261118/。

```text
ℹ tests 601
ℹ pass 601
ℹ fail 0
ℹ skipped 0
✓ built in 1m 10s
✓ built in 52.63s
```

后端执行者另实测 66 项国内专项及 0001→0044→0045 历史行验证。Windows 后端全量收集受既有 Unix 套接字依赖限制，其错误为 `AttributeError: module 'socketserver' has no attribute 'UnixStreamServer'`，位置为 backend/app/execution/credential_broker.py:49。审查者核对了临时目录 hx-menu-0045-backend-20261118/ 的 full-linux.log、retry-all3.log 和 targeted.log。Linux 全量首轮有三项测试环境失败，调整子进程的环境后在相同候选上逐项重跑通过，233 项仍为跳过。专项中独立 Redis 未配置的一项保持跳过。

```text
3 failed, 3460 passed, 233 skipped, 10 warnings in 564.67s (0:09:24)
3 passed in 12.83s
46 passed, 1 skipped, 2 warnings in 31.16s
```

审查结束时 review-status 的 currentId 仍与上述候选完全相同。生产发布实绩另由主 Agent 验收。
