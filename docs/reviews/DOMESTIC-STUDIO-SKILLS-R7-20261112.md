# 国内 Skills 管理独立审查 R7 · 2026-11-12

- 送审 candidateId：`7132dba9f25f6d6045ecdf95c2c2dc31b79395f3156cc7897099e8233fa906e5`。范围：国内 Skills 目录、文件夹上传/更新、ZIP、开关/删除、五工作台绑定、权限与并发、冻结引用及恢复；检查本轮共享抽取对海外代码、已确认预览及生产构建范围的影响。依据 `Product-Spec.md:1-11`、`Design-Brief.md:1-3`、`DEV-PLAN.md:1-10`、`docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:1-30` 和 R6 报告。
- **Stage 1：FAIL（2 项 MEDIUM）。Stage 2：未执行。** 已确认交互预览无法构建，正式目录的表格与预览存在具体设计差异；不能登记两阶段 PASS。没有发现本范围的 HIGH，但 Stage 1 尚未通过，按先通过 Stage 1 再进入 Stage 2 的门禁停止。下文安全和权限项目仅为 Stage 1 功能/隔离核查，不是 Stage 2 全面安全扫描。
- 审查开始时 `review-status` 的 `currentId` 与送审编号一致。审查期间并行工作改变总快照；结束前使用 harness 的 `review_files.snapshot/changes` 取得 `currentId=d048fb4c38d2988d7e8a5869f393c112784ad7f854146580c8165309325dc0db`，相对候选变化为：`backend/app/execution/cli_capacity.py`、`backend/app/modules/api_image_edits/conversation_runtime.py`、`backend/app/modules/domestic_studio/runtime.py`、`skill_material.py`、`turn_models.py`、`backend/app/overseas/execution/skill_cache.py`、`backend/app/worker/leases.py`、迁移 `0039_domestic_studio_outputs.py` 及 `test_api_cli_conversation.py`、`test_domestic_runtime_pg.py`、`test_domestic_skill_material.py`、`test_worker_lease_timezone.py`。其中 `skill_references.py:7` 引用并行变动的 `worker/leases.py`，后端测试运行期间的依赖不应冒称全都固定在候选版本。结论仅针对上述审查范围及时点，不覆盖当前或后续总快照。前端隔离构建副本的 675 个候选 `src` 和主要构建配置文件与送审候选逐文件摘要一致。未修改产品代码，未批准 harness 凭据。

## Stage 1 · 发现

### R7-1 · MEDIUM：共享抽取破坏已确认的国内交互预览

`Product-Spec.md:3` 和 `Design-Brief.md:3` 把 `frontend/preview-domestic-studio/` 当前交互预览作为已确认依据。但 `frontend/preview-domestic-studio/skills-state.ts:3`、`skills-export.ts:1-2`、`SkillUpload.vue:18` 仍导入 `src/views/overseas/admin/skill-folder-{metadata,read,zip}`；本候选已删除这些原路径，将实现放到 `src/views/shared/skills/`。实际执行预览 Vite 构建退出 1，首个错误为找不到 `skill-folder-metadata`；预览自己的 `vue-tsc` 也报 4 个模块找不到和 1 个派生类型错误，原始输出见下。此问题使已确认的交互基准无法重新启动或构建，生产范围构建通过不能覆盖它。

另，`frontend/preview-skill-platforms/App.vue:20` 仍导入本轮已删除的 `src/views/overseas/admin/OverseasSkillCatalog.vue`，同样存在静态缺失引用；本轮没有运行该旧海外预览构建，不宣称其他海外预览状态。

### R7-2 · MEDIUM：正式目录表格与确认预览不一致

确认预览 `frontend/preview-domestic-studio/Skills.vue:9` 首列表头为「Skill 名称」，名称使用 `<strong>`；五列表格最小宽/固定宽依次为 200/240/200/130/246px。正式目录 `frontend/src/views/shared/skills/OverseasSkillCatalog.vue:19,53-59` 首列表头是「名称」，使用普通 `<span>`，国内配置依次为 135/170/145/95/310px。相同 1280×720 截图中，预览的描述、绑定和状态列起点与正式页明显不同，正式页的操作出现第二行：`output/playwright/.playwright-cli/page-2026-11-12T08-50-19-944Z.png` 对比 `output/playwright/domestic-skills-r7-catalog.png`。两图的示例 Skill 数据不同，但列宽、表头和字重差异由上述代码确定，不能由数据差异解释。

## Stage 1 · 逐项核查与边界

1. **R6 的国内生产范围构建阻断：已修复并独立复验。** 正式国内入口现在引用共享目录（`frontend/src/views/hengxin/admin/skills.vue:16-19`），国内 API 显式传 `/api/v1/management/domestic-studio`（`frontend/src/api/hengxin/domestic-studio-skills.ts:5,15-20`）；海外调用仍由 `frontend/src/api/overseas/skill-transfers.ts:4-5` 指向海外管理根。隔离副本的国内、海外 `vite build --mode production` 均退出 0，生成清单中分别为海外目录 0、非共享国内页面 0。`frontend/release-scope.config.ts:20-27` 的禁止跨侧模块守卫仍在，内网打包环境 `scripts/release/intranet/package_release.py:121-142` 会设置构建范围。本轮没有执行完整 Git 归档打包或部署，不能据此推断最终联合发布方案通过。
2. **R6 的双层边框、绑定标题及常驻刷新：所检查项已修。** `frontend/src/views/shared/skills/OverseasSkillCatalog.vue:3,16,75-76` 仅海外显示常驻刷新，国内错误区保留重试并以 `!important` 去除内卡边框；`frontend/src/views/hengxin/admin/DomesticStudioBindings.vue:43-47` 去除内框并按预览设置标题 18px、说明 13px。已查看主 Agent 提供的隔离页面截图 `output/playwright/domestic-skills-r7-catalog.png` 和 `domestic-skills-r7-bindings.png`，未见 R6 内框和常驻刷新；本轮没有另行实测截图的计算样式。其他表格差异见 R7-2。
3. **仅超管管理：所测路径通过。** 菜单 `frontend/src/router/modules/index.ts:13-19` 仅超管显示 Skills 子项；`backend/app/modules/auth/permissions.py:6-8`、`backend/app/modules/domestic_studio/management_router.py:24-27,122-157` 限制 API；写入时 `skill_publication.py:19-29` 在权限锁下再次校验。`backend/tests/test_domestic_studio_management.py:60-76,112-149` 验证普通角色、未登录、来源标记及下载拒绝；`test_domestic_admin_permissions_pg.py:75-115` 测试真实 PG 撤权并发。未验证正式部署身份链。
4. **五个绑定、无预置和保护：所测路径通过。** `backend/migrations/versions/0033_domestic_studio_bindings.py:11-26` 只建映射表；`backend/app/modules/domestic_studio/bindings.py:17-27,36-71` 用事务、READ COMMITTED、执行门和全量 expected 值阻止陈旧覆盖并保护绑定中的 Skill；`skill_state.py:28-50` 和 `skill_publication.py:84-106` 分别限制停用和删除。真实 PG 双连接和冲突测试见 `backend/tests/test_domestic_studio_bindings_pg.py:56-112`。普通用户不选择 Skill、发送无绑定拒绝的最终执行链尚未接入，见第 7 项。
5. **完整文件夹、差异确认、断线恢复：所测路径通过。** `frontend/src/views/shared/skills/SkillFolderUpload.vue:2-27,55-85,100-125` 扫描、校验、确认更新及按持久状态恢复；国内管理 API 使用独立发布 socket（`backend/app/modules/domestic_studio/management_router.py:66-119`）。`frontend/tests/skill-folders-components.test.ts:63-103` 与 `backend/tests/test_domestic_skill_publisher.py:84-137,190-270` 覆盖真实组件的确认/续传及隔离发布器故障/并发；没有在浏览器拖入实际 Skill 文件或操作真实 Skill。
6. **ZIP 导出：所测路径通过。** `frontend/src/views/shared/skills/OverseasSkillCatalog.vue:24` 为国内传入 `zip-only`；`SkillFolderActions.vue:19-22,32-40` 固定走 ZIP；`skill-folder-zip.ts:5-22,37-52` 校验路径、大小和每个文件摘要。`frontend/tests/skill-folder-zip.test.ts:14-46,68-82` 解压检查空目录、Unicode 和原字节，并检查浏览器支持目录保存时国内仍选 ZIP；未验证原生浏览器下载落盘。
7. **冻结与历史保护：仅基础接口所测通过，真实发送未接通。** `backend/app/modules/domestic_studio/skill_references.py:15-32,35-56` 冻结并核对引用，`test_domestic_skill_references_pg.py:23-68` 验证双连接锁、在途拒绝和结束后旧版本可读。`docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:18,21` 明确真实执行、会话删除后的引用清理及最终回收未完成；本报告不把这些尚未实施的环节判为全流程通过。
8. **初始化和恢复：所测路径通过。** `backend/app/overseas/management/skill_initialization.py:29-77` 对可识别的空索引状态恢复并保留未知暂存；`backend/tests/test_skill_initialization_recovery.py:61-173` 含真实子进程退出和再次恢复测试。`backend/tests/test_domestic_recovery_lock_pg.py:21-96` 覆盖恢复与权限锁顺序及撤权；不外推到全部断电或并发时序。
9. **国内外隔离和海外回归：所测子集通过。** `backend/app/main.py:4-7,27,57-58` 将管理路由注册到国内入口；`backend/app/modules/domestic_studio/installed_skills.py:16-36` 在生产要求固定国内受保护根，`management_router.py:66-74` 限定国内发布 socket。海外发布器参数默认值和维护能力保留（`backend/app/overseas/management/skill_publisher.py:21,159-170,212-219`）。下列 66 项海外专项通过，3 项 Windows 跳过；不代表海外完整生产链和 Linux 权限验证。客户端共享传输地址有白名单（`frontend/src/api/shared/skill-transfers.ts:33-34`），服务端身份和业务边界仍须在最终部署复验。
10. **不展示版本管理或在线编辑：本范围静态检查未发现入口。** 国内目录仅显示绑定、ZIP、启停、删除（`frontend/src/views/shared/skills/OverseasSkillCatalog.vue:18-25`）；固定版本文件 API 供导出使用（`backend/app/modules/domestic_studio/management_router.py:127-135`）。R6 额外常驻刷新已移除。未做全产品漂移扫描。

## 独立验证与原始输出

后端使用 `HX_BUSINESS_CONTEXT=domestic`、`APP_ENV=test`、临时 PostgreSQL `127.0.0.1:35439/hx_studio_test` 和测试 MinIO 凭据；未连接生产。国内 13 个恢复、权限、引用、绑定、状态、迁移和管理测试文件，以及海外 7 个传输、恢复、对象和清理测试文件的原始汇总：

```text
99 passed, 2 warnings in 56.69s
66 passed, 3 skipped, 2 warnings in 73.27s (0:01:13)
```

前端独立执行 10 个相关测试文件，原始汇总：

```text
ℹ tests 70
ℹ suites 0
ℹ pass 70
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 4532.3991
```

正式前端 `pnpm exec vue-tsc --noEmit` 退出 0，原始输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
```

隔离副本执行国内和海外 Vite 生产范围构建，原始输出：

```text
REVIEW_COPY=C:\Users\82358\AppData\Local\Temp\hx-review-r7-2ea0eab18d7d4db99bd803b81d210e0b
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
[plugin vite:reporter]
(!) C:/Users/82358/AppData/Local/Temp/hx-review-r7-2ea0eab18d7d4db99bd803b81d210e0b/src/views/auth/dingtalk-login.vue is dynamically imported by C:/Users/82358/AppData/Local/Temp/hx-review-r7-2ea0eab18d7d4db99bd803b81d210e0b/src/router/core/ComponentLoader.ts, C:/Users/82358/AppData/Local/Temp/hx-review-r7-2ea0eab18d7d4db99bd803b81d210e0b/src/router/core/ComponentLoader.ts, C:/Users/82358/AppData/Local/Temp/hx-review-r7-2ea0eab18d7d4db99bd803b81d210e0b/src/router/routes/staticRoutes.ts but also statically imported by C:/Users/82358/AppData/Local/Temp/hx-review-r7-2ea0eab18d7d4db99bd803b81d210e0b/src/App.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
DOMESTIC_EXIT=0
DOMESTIC_OVERSEAS_MODULES=0
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
[plugin vite:reporter]
(!) C:/Users/82358/AppData/Local/Temp/hx-review-r7-2ea0eab18d7d4db99bd803b81d210e0b/src/views/overseas/OverseasTasksPage.vue is dynamically imported by C:/Users/82358/AppData/Local/Temp/hx-review-r7-2ea0eab18d7d4db99bd803b81d210e0b/src/router/core/ComponentLoader.ts, C:/Users/82358/AppData/Local/Temp/hx-review-r7-2ea0eab18d7d4db99bd803b81d210e0b/src/views/overseas/OverseasPortal.vue?vue&type=script&setup=true&lang.ts but also statically imported by C:/Users/82358/AppData/Local/Temp/hx-review-r7-2ea0eab18d7d4db99bd803b81d210e0b/src/views/overseas/OverseasPortal.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
OVERSEAS_EXIT=0
OVERSEAS_DOMESTIC_VIEW_MODULES=0
```

国内确认预览的 Vite 构建原始输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
✗ Build failed in 1.00s
error during build:
[vite:load-fallback] Could not load D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend\src/views/overseas/admin/skill-folder-metadata (imported by preview-domestic-studio/skills-state.ts): ENOENT: no such file or directory, open 'D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend\src\views\overseas\admin\skill-folder-metadata'
    at async open (node:internal/fs/promises:640:25)
    at async Object.readFile (node:internal/fs/promises:1290:14)
    at async Object.handler (file:///D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/node_modules/.pnpm/vite@7.1.7_@types+node@24.8_a31ceeca6a88d70e3e28508edf9fb53a/node_modules/vite/dist/node/chunks/dep-Bm2ujbhY.js:33589:21)
    at async PluginDriver.hookFirstAndGetPlugin (file:///D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/node_modules/.pnpm/rollup@4.52.3/node_modules/rollup/dist/es/shared/node-entry.js:22307:28)
    at async file:///D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/node_modules/.pnpm/rollup@4.52.3/node_modules/rollup/dist/es/shared/node-entry.js:21307:33
    at async Queue.work (file:///D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/node_modules/.pnpm/rollup@4.52.3/node_modules/rollup/dist/es/shared/node-entry.js:22535:32)
PREVIEW_EXIT=1
```

`pnpm exec vue-tsc --noEmit -p preview-domestic-studio/tsconfig.json` 退出 1，原始输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
preview-domestic-studio/skills-export.ts(1,24): error TS2307: Cannot find module '@/views/overseas/admin/skill-folder-read' or its corresponding type declarations.
preview-domestic-studio/skills-export.ts(2,34): error TS2307: Cannot find module '@/views/overseas/admin/skill-folder-zip' or its corresponding type declarations.
preview-domestic-studio/skills-state.ts(3,38): error TS2307: Cannot find module '@/views/overseas/admin/skill-folder-metadata' or its corresponding type declarations.
preview-domestic-studio/SkillUpload.vue(18,81): error TS2307: Cannot find module '@/views/overseas/admin/skill-folder-read' or its corresponding type declarations.
preview-domestic-studio/SkillUpload.vue(36,30): error TS18046: 'entry' is of type 'unknown'.
```

Stage 2 的代码质量、全面安全扫描、测试真实性审计和实际邻居页面对照均未执行。五工作台、真实会话和执行器、成品库、生产发布与全产品验收不在本轮结论内；修复后应重新固定快照，从 Stage 1 起复审。
