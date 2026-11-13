# 国内 Skills 管理独立审查 R8 · 2026-11-12

- 送审 candidateId：`f74448091468eb3b47d244b35addbee05bcc515584f9c4f27ce92dbc4c9de0e0`。
- 范围：国内 Skill 目录、文件夹上传及同名更新、ZIP 下载、启停和删除、五工作台绑定、管理权限、并发和恢复；复核 R7 的预览构建与目录视觉差异，以及共享抽取对海外原有导入和业务隔离的影响。依据 `Product-Spec.md:1-11`、`Design-Brief.md:1-3`、`DEV-PLAN.md:1-10`、`docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:13-24` 和 R7 报告。五工作台、真实发送和执行、成品库、部署及整体验收不在本次阶段范围。
- **Stage 1：FAIL（目录视觉存在 MEDIUM 差异）。Stage 2：未执行。** 未发现本阶段已核查路径的 HIGH；Stage 1 未通过，不能登记两阶段 PASS。
- 开始时 `review-status` 的 `currentId` 与候选一致。审查期间其他工作继续，最后一次快照比较的 `currentId` 为 `6c55a53ba876ac0ee7f117c6742a902e89f33beee86f528b950ce9a3b9bb58da`，与候选不同；差异列于文末。本报告结论只适用于上述候选和实际核查范围，不可覆盖当前或后续整体快照。未修改产品实现，未调用 `review-approve`。

## Stage 1 · 发现

### R8-1 · MEDIUM：正式目录的数据行、操作与控件密度仍与确认预览不一致

`Product-Spec.md:3` 和 `Design-Brief.md:3` 指定 `frontend/preview-domestic-studio/` 最终预览为视觉交互基准。`frontend/preview-domestic-studio/Skills.vue:7-9` 和 `skills.css:1` 中，数据单元格上下各 18px，操作按钮使用默认大小，说明区无 28px 最小高度，绑定标签允许自然高度和换行。候选的 `frontend/src/views/shared/skills/OverseasSkillCatalog.vue:10,18-24,73-95` 与 `SkillFolderActions.vue:2-6` 未完整继承这些数值：按钮使用 `size="small"`，通用说明区设有 `min-height:28px`，没有预览的表格单元格及标签样式。

本次用隔离 Playwright 浏览器、1920×1080、相同 Skill 名称、描述、绑定和四项操作，分别打开确认预览和真实正式 Vue 页面；正式页的网络回复由本地测试夹具拦截，**不是生产数据**。实际 `getBoundingClientRect` 和计算样式如下：

| 项目 | 确认预览 | 候选正式页面 |
| --- | --- | --- |
| 数据行高度 | 69px | 41px |
| 数据单元格上下 padding | 各 18px | 各 8px |
| 行操作按钮高度 / 字号 | 32px / 14px | 24px / 12px |
| 状态筛选高度 | 32px | 36px |
| 目录说明区高度 | 18px | 28px |
| 单元格行高 | 23.8px | 23px |
| 工作台绑定标签高度 | 约 21.2px | 20px |

预览示例额外带「示例」标签，正式页面无此演示标记；两侧操作按钮尺寸、padding 和 CSS 不同独立证明密度差异。截图：`output/playwright/.playwright-cli/page-2026-11-12T09-36-46-247Z.png`（预览）和 `output/playwright/.playwright-cli/page-2026-11-12T09-39-13-123Z.png`（正式组件、测试夹具）。两侧列宽实测均为 381 / 455 / 379 / 130 / 246px，名称字重均为 700，故 R7 指出的列宽、标题与字重差异在本次所测视口已修复。修复应重新对比确认预览并回归海外共享组件，不能只调整行高后假定其他差异已消失。

## Stage 1 · 逐项核查

1. **R7 旧导入及预览构建：所测修复通过。** 原预览所用 `frontend/src/views/overseas/admin/skill-folder-{read,metadata,zip}.ts:1` 与 `OverseasSkillCatalog.vue:1-4` 现在转发共享实现；国内交互预览和海外平台预览 Vite 构建均退出 0，国内预览 `vue-tsc` 退出 0，原始输出见下。此结论针对仓库内已搜索到的预览调用，不声称所有历史内部文件路径均保留。
2. **超级管理员入口和服务端权限：所测通过。** 菜单限 `super_admin`（`frontend/src/router/modules/index.ts:13-20`）；管理 API 的 `manage_system` 依赖和写请求来源校验见 `backend/app/modules/domestic_studio/management_router.py:24-27,77-157`，发布写入还在权限锁下检查激活状态、角色和身份来源（`skill_publication.py:19-29`）。`backend/tests/test_domestic_studio_management.py:61-76,112-149` 核查非管理员、未登录及来源；`test_domestic_admin_permissions_pg.py:75-115` 核查 PostgreSQL 撤权与写入的两种先后顺序。未验证正式部署身份链。
3. **五项绑定、替换/解除和保护：所测通过。** `frontend/src/views/hengxin/admin/DomesticStudioBindings.vue:3-6,19-40` 展示五个入口，读取启用 Skill，保存原值与草稿并锁定保存中编辑；`backend/app/modules/domestic_studio/bindings.py:17-71` 在执行门和 READ COMMITTED 下验证全部原值并保护被绑定项，`skill_state.py:28-50` 和 `skill_publication.py:84-106` 约束停用/删除；迁移 `0033_domestic_studio_bindings.py:11-26` 不预置绑定。真实 PG 双连接测试位于 `backend/tests/test_domestic_studio_bindings_pg.py:56-112`。浏览器在拦截的 409 夹具下点击「停用」，页面显示「此 Skill 正被工作台使用，请先更换或解除绑定」且仍显示启用；点击「设置绑定」实际切到绑定页并显示五项。该浏览器测试没有访问生产后端。
4. **完整文件夹上传、同名差异确认、失败恢复：所测通过。** `frontend/src/views/shared/skills/SkillFolderUpload.vue:2-27,55-125` 读取目录、展示差异并要求更新确认、可查询和续传；国内传输 API 指向独立管理前缀（`frontend/src/api/hengxin/domestic-studio-skills.ts:5,15-20`，`backend/app/modules/domestic_studio/management_router.py:66-119`）。`frontend/tests/skill-folders-components.test.ts:63-103` 和 `backend/tests/test_domestic_skill_publisher.py:84-137,190-270` 验证组件及隔离发布器的更新、冲突与恢复。没有在真实浏览器中拖入实际 Skill 文件，也没有操作真实 Skill。
5. **启停、删除、ZIP：所测通过。** 正式行操作使用真实事件处理器（`frontend/src/views/shared/skills/OverseasSkillCatalog.vue:23-24`、`OverseasLiveSkills.vue:41-72`、`SkillFolderActions.vue:32-69`）；国内传入 `zip-only`，下载按固定清单校验路径、大小和摘要（`skill-folder-zip.ts:5-52`）。37 项前端专项包括真实 Vue 组件停用按钮、删除确认/取消、ZIP 解压、Unicode、空目录和内容不符拒绝，见 `frontend/tests/skill-folders-components.test.ts:63-103,141-178`、`skill-folder-zip.test.ts:14-82`。没有验证浏览器原生下载落盘或真实 Skill 操作。
6. **固定绑定与请求冻结：基础接口部分实现并受测；完整执行尚未验收。** `backend/app/modules/domestic_studio/bindings.py:74-83` 在同一执行门下读取绑定并拒绝请求自带 Skill；`skill_references.py:15-56` 保存冻结引用并校验历史包，`backend/tests/test_domestic_skill_references_pg.py:23-68` 使用独立 PostgreSQL 连接验证锁、在途删除拒绝及终态旧包可读。`docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:18,23` 明确真实发送、删除后引用清理及最终回收闭环尚未完成，本次不将基础接口通过扩展为最终执行通过。
7. **国内外资源和共享抽取：所测隔离通过，部署未验收。** 前端国内和海外传输前缀分别为 `frontend/src/api/hengxin/domestic-studio-skills.ts:5`、`frontend/src/api/overseas/skill-transfers.ts:4-5`；跨侧模块守卫在 `frontend/release-scope.config.ts:20-27`；国内受保护根和 socket 的限制见 `backend/app/modules/domestic_studio/installed_skills.py:16-36`、`management_router.py:66-74`。本轮独立重跑了两个交互预览构建和相关组件测试，未独立重跑国内/海外正式范围生产构建；R7 的正式范围构建证据仍只适用于 R7 隔离副本（`docs/reviews/DOMESTIC-STUDIO-SKILLS-R7-20261112.md:20-22`）。共享服务最终部署、Linux 权限和海外全链路不在本轮实测范围。
8. **初始化、崩溃和恢复：所测通过。** `backend/app/overseas/management/skill_initialization.py:29-77` 与 `backend/tests/test_skill_initialization_recovery.py:61-173` 覆盖真实子进程退出、重复恢复及未知暂存保留；`backend/tests/test_domestic_recovery_lock_pg.py:21-96` 覆盖锁顺序及恢复后撤权。只对所测故障点下结论，不推断全部断电时序均已覆盖。
9. **版本管理/在线编辑与预置：所测未见。** 国内目录选择 `domestic` 分支隐藏海外平台管理（`frontend/src/views/shared/skills/OverseasSkillCatalog.vue:3-12,26-28`），`frontend/src/views/shared/skills/SkillFolderUpload.vue:2-27` 提供文件夹传输和差异确认，没有在线编辑器或版本列表；绑定迁移不写初始数据（`backend/migrations/versions/0033_domestic_studio_bindings.py:11-26`）。上传状态恢复属于现有文件夹传输能力，不当作版本管理。

## 编译原始输出与测试结果

以下为本审查独立执行。两次 Vite 使用 `--logLevel warn` 和独立临时输出目录，因此没有成功模块清单；均以进程退出码判定。

```text
pnpm exec vite build --config preview-domestic-studio/vite.config.ts --mode demo --outDir <系统临时目录>/hx-review-r8-domestic-preview --logLevel warn
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
(!) outDir C:\Users\82358\AppData\Local\Temp\hx-review-r8-domestic-preview is not inside project root and will not be emptied.
Use --emptyOutDir to override.
exit code: 0

pnpm exec vite build --config preview-skill-platforms/vite.config.ts --mode demo --outDir <系统临时目录>/hx-review-r8-overseas-preview --logLevel warn
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
(!) outDir C:\Users\82358\AppData\Local\Temp\hx-review-r8-overseas-preview is not inside project root and will not be emptied.
Use --emptyOutDir to override.
exit code: 0

pnpm exec vue-tsc --noEmit -p preview-domestic-studio/tsconfig.json
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
exit code: 0
```

```text
pnpm exec tsx --test tests/domestic-studio-skills.test.ts tests/skill-folders-components.test.ts tests/skill-folder-zip.test.ts tests/skill-platforms.test.ts tests/skill-folders-save-conflicts.test.ts
（以下为测试输出末尾汇总）
ℹ tests 37
ℹ suites 0
ℹ pass 37
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 2349.1375
exit code: 0

.venv/Scripts/python.exe -m pytest -q tests/test_domestic_studio_bindings_pg.py tests/test_domestic_admin_permissions_pg.py tests/test_domestic_recovery_lock_pg.py tests/test_domestic_skill_references_pg.py tests/test_domestic_studio_management.py tests/test_domestic_skill_publisher.py tests/test_skill_initialization_recovery.py
...............................................                          [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
47 passed, 2 warnings in 67.93s (0:01:07)
exit code: 0
```

系统 Python 首次执行提示 `No module named pytest`、退出 1，随后改用项目 `.venv` 得到上面的结果。PostgreSQL 测试使用 `127.0.0.1:35439/hx_studio_test`，各测试创建独立临时 schema；并非生产数据库。

## 快照变化与未执行项

最后一次比较相对候选的变化：`backend/app/execution/verified_stop.py`、`backend/app/modules/api_image_edits/conversation_stop.py`、`backend/app/modules/domestic_studio/{delivery_context,output_store,recovery,runner,turn_models,turn_service}.py`、`backend/app/worker/{outbox,tasks}.py`、`backend/migrations/versions/0040_domestic_delivery_retry.py`、`backend/tests/{test_domestic_delivery_context,test_domestic_output_store_pg,test_domestic_runner_pg,test_queue_integration,test_verified_stop}.py`。这些并行工作不由本报告批准；后续需重新固定整体快照，独立复核差异。审查启动的本地 Vite 自动改写过 `frontend/src/types/import/components.d.ts`，已停止该进程并将这项由本次审查产生的改写恢复至与候选一致的 HEAD 内容；最终比较中该文件不再变化。

Stage 2 的代码质量、全面安全扫描、测试真实性系统审计和邻居页面实际视觉对比均未执行。未运行正式范围生产构建、真实拖入文件、浏览器 ZIP 落盘、正式部署或模型执行；这些均不能因本报告而视为通过。
