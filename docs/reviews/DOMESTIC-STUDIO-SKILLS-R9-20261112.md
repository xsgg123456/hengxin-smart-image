# 国内 Skills 管理独立审查 R9 · 2026-11-12

- **送审 candidateId：** `592b731bc3ef4c9492147255e37cff46f58a8e63627219fc404a691bffb8c4c0`。审查开始时 `review-status` 的 `currentId` 与此一致。
- **范围：** 国内 Skill 目录、完整文件夹上传及同名更新、ZIP、启停与删除、五工作台绑定、管理权限、并发和恢复；复核 R8 的视觉差异以及共享抽取对海外预览和发布范围的影响。依据 `Product-Spec.md:1-11`、`Design-Brief.md:1-3`、`DEV-PLAN.md:1-10`、`docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:13-29` 和 R8 报告。五个工作台、会话删除、成品库、真实模型执行和部署不属于本次阶段验收，完整产品必须重新固定快照审核。
- **Stage 1：FAIL（3 项 MEDIUM，均为视觉不一致）。Stage 2：未完成、未判定。** 未发现本次已核查路径的 HIGH。曾提前做过安全关键词检索，但没有完成 Stage 2 的系统安全、质量和邻居页面实际对比，不能登记两阶段 PASS。
- **浏览器方法：** 在隔离临时副本运行 Vite，使用真实 Vue 页面；正式页的超级管理员身份为本地模拟，Skill 和绑定由浏览器请求拦截夹具提供，未连接生产或真实 Skill。浏览器检查前核验该副本的 882 个候选前端源文件及相关配置摘要，均与候选相同。比较时均用同一浏览器和视口。

## Stage 1 · 发现

### R9-1 · MEDIUM：工作台绑定页的标题、说明、下拉及行密度与确认预览不一致

`Product-Spec.md:3` 和 `Design-Brief.md:3` 指定 `frontend/preview-domestic-studio/` 为视觉与交互基准。预览的绑定样式在 `frontend/preview-domestic-studio/Skills.vue:11`、`skills.css:1`；正式页在 `frontend/src/views/hengxin/admin/DomesticStudioBindings.vue:3-7,43-54`。同一隔离浏览器 1920×1080 实测：

| 项目 | 确认预览 | 正式组件 |
| --- | --- | --- |
| 标题字号 / 字重 | 18px / 400 | 18px / 650 |
| 标题区高度 | 54.5px | 57.09375px |
| 说明字号 / 行高 | 13px / 19.5px | 13px / 22.1px |
| 首行分组名字号 / 行高 | 12px / 18px | 12.8px / 19.2px |
| 首行下拉宽 / 高 | 460px / 32px | 460px / 36px |
| 首行高度 / 上下 padding | 92px / 各 22px | 93.1875px / 各 22px |
| 底部说明字号 / 行高 | 12px / 21.6px | 11px / 18.7px |

两侧均使用「相机配件生成」作为首行标签；正式页其余绑定为空是测试夹具，预览为演示绑定，数据差异不影响上述计算样式。截图：`output/playwright/r9-review-preview-bindings.png`、`output/playwright/r9-review-formal-bindings.png`。不能用目录页的下拉尺寸通过替代绑定页验证。

### R9-2 · MEDIUM：上传弹窗初始拖放区外观与确认预览不一致

预览 `frontend/preview-domestic-studio/SkillUpload.vue:2-5`、`skills.css:2`；正式共享弹窗 `frontend/src/views/shared/skills/SkillFolderUpload.vue:2-5,128-130`。同一隔离浏览器 1920×1080，预览/正式拖放区分别为：高度 **81.5 / 71px**，padding **30px 16px / 24px 12px**，虚线颜色 **rgb(220, 223, 230) / rgb(93, 135, 255)**，文字 **13 / 14px**，行高 **19.5 / 21px**。截图：`output/playwright/r9-review-preview-upload.png`、`output/playwright/r9-review-formal-upload.png`。此项只指出拖放区样式；正式实现的服务器上传状态与错误恢复内容不作为差异缺陷。

### R9-3 · MEDIUM：窄屏目录未继承预览的说明隐藏规则

`frontend/preview-domestic-studio/skills.css:3` 在视口不大于 800px 时隐藏「完整文件夹上传 · 同名 Skill 更新」；正式国内目录 `frontend/src/views/shared/skills/OverseasSkillCatalog.vue:14,90-94` 没有对应国内窄屏规则。同一隔离浏览器 760×900 实测，预览该说明 `display:none`，正式组件 `display:block`。截图：`output/playwright/r9-review-preview-mobile.png`、`output/playwright/r9-review-formal-mobile.png`。共享组件中海外行为也需要保留和回归。

## Stage 1 · 逐项核查及边界

1. **R8 目录密度修复：所测项通过。** 同一浏览器 1920×1080、同名 Skill 和绑定，预览与正式目录数据行均为 69px，单元格上下各 18px，操作按钮 32px / 14px，状态筛选 32px，目录说明区 18px，单元格行高 23.8px，绑定标签 21.1875px，五列均为 381 / 455 / 379 / 130 / 246px；对应 `frontend/preview-domestic-studio/Skills.vue:7-9`、`skills.css:1` 和 `frontend/src/views/shared/skills/OverseasSkillCatalog.vue:10,18-24,53-59,75-85`、`SkillFolderActions.vue:2-6`。截图为 `output/playwright/r9-review-preview.png`、`output/playwright/r9-review-formal.png`。不把该结论扩展至绑定页和上传弹窗，见 R9-1、R9-2。
2. **超级管理员入口及服务端权限：所测通过。** 菜单仅授予 `super_admin`（`frontend/src/router/modules/index.ts:13-20`），国内管理路由要求 `manage_system`、写入附浏览器来源校验（`backend/app/modules/domestic_studio/management_router.py:24-27,77-157`），写入发布前再次在权限锁下核验激活状态、角色和身份来源（`skill_publication.py:19-29`）。`backend/tests/test_domestic_studio_management.py:61-76,112-149` 覆盖非超管、未登录与来源；`test_domestic_admin_permissions_pg.py:75-115` 覆盖真实 PostgreSQL 撤权先后。正式部署的身份链未实测。
3. **五项绑定、替换/解除、无预置与保护：所测通过。** 前端五个入口和启用项选择见 `frontend/src/api/hengxin/domestic-workspaces.ts:3-8`、`frontend/src/views/hengxin/admin/DomesticStudioBindings.vue:3-6,19-40`；服务端在同一执行门内比较全部原值、验证启用项并阻止被绑定 Skill 停用/删除（`backend/app/modules/domestic_studio/bindings.py:17-71`、`skill_state.py:28-50`、`skill_publication.py:84-106`）。迁移 `backend/migrations/versions/0033_domestic_studio_bindings.py:11-26` 不插入默认绑定。真实 PG 双连接与并发冲突测试见 `backend/tests/test_domestic_studio_bindings_pg.py:56-112`；组件测试见 `frontend/tests/domestic-studio-skills.test.ts:39-94`。
4. **完整文件夹、同名差异、续传：所测通过。** 国内弹窗扫描完整目录，更新须明确确认，可查询及恢复上传（`frontend/src/views/shared/skills/SkillFolderUpload.vue:2-27,55-85,100-125`）；独立管理接口和发布 socket 见 `backend/app/modules/domestic_studio/management_router.py:66-119`。真实组件测试覆盖更新确认和续传（`frontend/tests/skill-folders-components.test.ts:86-119`），隔离发布器测试覆盖安装、冲突和失败恢复（`backend/tests/test_domestic_skill_publisher.py:84-137,190-270`）。没有在原生浏览器拖入真实 Skill 文件。
5. **启停、删除、ZIP：所测通过。** 行操作与二次确认见 `frontend/src/views/shared/skills/OverseasSkillCatalog.vue:23-24`、`SkillFolderActions.vue:32-69`；国内固定 ZIP，按清单、大小及摘要校验文件（`SkillFolderActions.vue:19-22,32-40`、`skill-folder-zip.ts:5-52`）。组件及 ZIP 测试分别见 `frontend/tests/skill-folders-components.test.ts:38-83,121-188`、`skill-folder-zip.test.ts:22-82`。浏览器原生下载落盘未验证。
6. **固定绑定及冻结：基础接口所测通过，完整执行与清理闭环未验收。** 发送使用可信绑定并拒绝客户端 Skill（`backend/app/modules/domestic_studio/bindings.py:74-82`、`policy.py:33-52`）；冻结引用核对包及运行中引用（`skill_references.py:15-56`），真实 PG 双连接测试见 `backend/tests/test_domestic_skill_references_pg.py:23-68`。`docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:18,26` 明示完整工作台、会话删除后的引用清理及回收未完成，不据此宣布完整发送链通过。
7. **国内外隔离及海外回归：所测子集通过。** 国内管理前缀 `frontend/src/api/hengxin/domestic-studio-skills.ts:5,15-20`，海外传输仍使用原海外根（`frontend/src/api/overseas/skill-transfers.ts:1-5`）；国内固定根和生产 socket 的约束见 `backend/app/modules/domestic_studio/installed_skills.py:16-36`、`management_router.py:66-74`、`skill_publisher.py:13-32`。本轮独立生产范围构建的 `release-scope.json`：国内 1147 模块、海外目录 0；海外 741 模块、非共享国内页面 0；禁止跨侧模块的守卫位于 `frontend/release-scope.config.ts:20-27`。两个旧预览构建和前端相关 70 项回归均通过；未实际部署或运行海外生产全链路，不外推 Linux 文件权限。
8. **初始化和恢复：所测路径通过。** 初始化恢复实现见 `backend/app/overseas/management/skill_initialization.py:29-77`；`backend/tests/test_skill_initialization_recovery.py:61-173` 包含真实子进程退出、重试和未知暂存保留；`test_domestic_recovery_lock_pg.py:22-96` 覆盖权限与执行锁顺序。不能外推所有故障时序。
9. **本范围漂移：未发现版本管理或在线编辑入口。** 国内目录分支隐藏海外平台功能（`frontend/src/views/shared/skills/OverseasSkillCatalog.vue:3-14,26-28`），上传状态恢复见 `SkillFolderUpload.vue:20,116-125`，是文件夹传输恢复，不是版本管理。未对整个产品做漂移扫描。

## 独立编译原始输出

以下构建在隔离前端副本执行，`--logLevel warn` 抑制成功模块清单；退出码是进程实际结果。国内/海外生产范围输出目录互相独立。构建日志中的路径为本机临时副本。

```text
VITE_RELEASE_SCOPE=domestic pnpm exec vite build --mode production --outDir dist-r9-domestic --logLevel warn
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
[plugin vite:reporter]
(!) C:/Users/82358/AppData/Local/Temp/hx-skill-r9-review-0604a0596cf3471c9b3361193c19e3f4/src/views/auth/dingtalk-login.vue is dynamically imported by C:/Users/82358/AppData/Local/Temp/hx-skill-r9-review-0604a0596cf3471c9b3361193c19e3f4/src/router/core/ComponentLoader.ts, C:/Users/82358/AppData/Local/Temp/hx-skill-r9-review-0604a0596cf3471c9b3361193c19e3f4/src/router/core/ComponentLoader.ts, C:/Users/82358/AppData/Local/Temp/hx-skill-r9-review-0604a0596cf3471c9b3361193c19e3f4/src/router/routes/staticRoutes.ts but also statically imported by C:/Users/82358/AppData/Local/Temp/hx-skill-r9-review-0604a0596cf3471c9b3361193c19e3f4/src/App.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
exit code: 0

VITE_RELEASE_SCOPE=overseas pnpm exec vite build --mode production --outDir dist-r9-overseas --logLevel warn
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
[plugin vite:reporter]
(!) C:/Users/82358/AppData/Local/Temp/hx-skill-r9-review-0604a0596cf3471c9b3361193c19e3f4/src/views/overseas/OverseasTasksPage.vue is dynamically imported by C:/Users/82358/AppData/Local/Temp/hx-skill-r9-review-0604a0596cf3471c9b3361193c19e3f4/src/router/core/ComponentLoader.ts, C:/Users/82358/AppData/Local/Temp/hx-skill-r9-review-0604a0596cf3471c9b3361193c19e3f4/src/views/overseas/OverseasPortal.vue?vue&type=script&setup=true&lang.ts but also statically imported by C:/Users/82358/AppData/Local/Temp/hx-skill-r9-review-0604a0596cf3471c9b3361193c19e3f4/src/views/overseas/OverseasPortal.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
exit code: 0

pnpm exec vite build --config preview-domestic-studio/vite.config.ts --mode demo --outDir dist-r9-preview-domestic --logLevel warn
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
exit code: 0

pnpm exec vite build --config preview-skill-platforms/vite.config.ts --mode demo --outDir dist-r9-preview-overseas --logLevel warn
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
exit code: 0

pnpm exec vue-tsc --noEmit
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
exit code: 0
```

## 测试结果

独立运行前端 `pnpm exec tsx --test`，范围为 `tests/domestic-studio-skills.test.ts`、`skill-folders-components.test.ts`、`skill-folder-zip.test.ts`、`skill-platforms.test.ts`、`skill-folders-save-conflicts.test.ts`、`skill-folders.test.ts`、`overseas-delete-component.test.ts`、`overseas-skill-availability.test.ts`、`business-route-access.test.ts`、`roles-integration.test.ts`。原始末尾汇总：

```text
ℹ tests 70
ℹ suites 0
ℹ pass 70
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 6180.65
exit code: 0
```

后端 `.venv/Scripts/python.exe -m pytest -q` 对 `tests/test_domestic_studio_bindings_pg.py`、`test_domestic_admin_permissions_pg.py`、`test_domestic_recovery_lock_pg.py`、`test_domestic_skill_references_pg.py`、`test_domestic_studio_management.py`、`test_domestic_skill_publisher.py`、`test_skill_initialization_recovery.py` 的输出：

```text
...............................................                          [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
47 passed, 2 warnings in 50.52s
exit code: 0
```

PostgreSQL 指向 `127.0.0.1:35439/hx_studio_test`，使用测试 MinIO 凭据及临时 schema；未访问生产。测试结果只覆盖所列用例和测试数据。

## 快照变化与未执行项

审查期间并行代码发生变化；报告写成后一次比较相对送审候选的 `currentId` 为 `9a02ad73b086a0e6932ffe8eff9d9c36233a5cf69efd532795bda5c60cb681f0`。差异为 `backend/app/main.py`、`backend/app/modules/domestic_studio/{archive_models,archive_queries,archive_router,archive_service,conversation_cleanup,conversation_deletion,conversation_models,conversation_service,file_service,queries,router}.py`、`backend/app/overseas/tasks/cleanup_files.py`、`backend/app/worker/outbox.py`、`backend/migrations/env.py`、`backend/migrations/versions/{0041_domestic_studio_archives,0042_domestic_archive_copy_plan,0043_domestic_conversation_deletions}.py`、`backend/tests/{test_domestic_archive_pg,test_domestic_conversations_pg,test_domestic_files_pg,test_domestic_turns_pg}.py`、`frontend/src/views/hengxin/admin/DomesticStudioBindings.vue`、`frontend/src/views/shared/skills/{OverseasSkillCatalog,SkillFolderUpload}.vue`。其中三处 Skill 前端文件已发生修复性变化；本报告的视觉数据来自核验过的候选副本，不代表后来版本。主要 Skill 管理后端模块及其直接引用的 `worker/leases.py` 先前比较时仍与候选相同；迁移环境有并行改动，不扩展为新总快照验收。

审查未修改产品代码、未调用 `review-approve`。Stage 2 系统质量与安全审计、邻居页面实际对比、原生文件夹拖入及 ZIP 落盘、真实模型、生产发布未完成；修复后须重新固定快照，从 Stage 1 开始复审差异及相关功能。
