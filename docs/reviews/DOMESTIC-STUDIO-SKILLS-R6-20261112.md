# 国内 Skills 管理独立审查 R6 · 2026-11-12

- 送审 candidateId：`0e553be77f4e7563e01db368d9eafeaa040ac552f8f84c7e86ec90405e529aae`。审查范围限国内 Skills 目录、上传/更新/ZIP/删除、五工作台绑定、权限与并发、冻结引用及相关恢复，以及受改动的共享海外 Skill 代码。依据 `Product-Spec.md:3-11`、`Design-Brief.md:1-3`、`DEV-PLAN.md:1-10`、`docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:1-24` 和 R5 报告。
- **Stage 1：FAIL（1 HIGH、2 MEDIUM）。Stage 2：未执行。** 国内生产范围构建被现有跨业务模块门禁拒绝；视觉仍与确认预览不同。不得据此登记两阶段 PASS。
- 审查开始时 `review-status` 的 `currentId` 与送审编号一致。主 Agent 随后并行新增国内会话文件；中途按 harness 的 `review_files.snapshot/changes` 比对送审快照，`currentId` 已变化为 `6a7415ec0eda0b9f69fcbbc3a46c9ef8ceb03f265a6a01938731ab94474f2ace`，差异为新增的 `conversation_models.py`、`conversation_service.py`、`file_service.py`、`turn_models.py`、`turn_service.py`、迁移 `0037`/`0038` 和会话/文件/轮次 PG 测试。结束前再次比对为 `cf2f875c1e67ebcc09ff73d3fa24fd5136a47bee4a4f863db6ec13d2e4a09fdc`，在上述差异外新增 `frontend/src/api/shared/skill-types.ts` 和 `frontend/src/utils/attachment-size.ts`；已有受审文件当时未列为差异。这些后续新增文件不在本报告结论内。整体候选已变化，本报告不能作为新快照凭据。报告为普通 Markdown，reviewer 未修改产品代码、未批准 harness 凭据。

## Stage 1 · 发现

### R6-1 · HIGH：国内生产范围构建失败

`Product-Spec.md:11` 要求通过构建，`Product-Spec.md:10` 要求国内外隔离。国内正式页面直接导入海外视图 `frontend/src/views/hengxin/admin/skills.vue:18`，国内 API 客户端也导入海外 API 实现 `frontend/src/api/hengxin/domestic-studio-skills.ts:2-3`。项目既有 `frontend/release-scope.config.ts:20-27` 在国内构建时禁止把 `src/views/overseas/` 与 `src/api/overseas/` 模块打入包；内网打包工具也传入对应范围，见 `scripts/release/intranet/package_release.py:121-142`。

在隔离复制的前端源码上以 `VITE_RELEASE_SCOPE=domestic` 执行 Vite 生产构建，门禁列出海外 API、目录组件、上传/下载等模块并以退出码 1 失败，原始输出见下。此结果证明当前国内 Skills 实现无法通过现有国内范围构建；不应绕过该隔离门禁。`vue-tsc` 通过并不能证明生产包可构建。仅验证构建，未执行生产发布。

### R6-2 · MEDIUM：两个页签仍有额外卡片边框，绑定标题排版与预览不同

`Design-Brief.md:3` 规定最终预览为视觉与交互基准。预览把页签、目录和绑定内容放入一张卡片（`frontend/preview-domestic-studio/Skills.vue:4-12`）。正式页面有外卡片（`frontend/src/views/hengxin/admin/skills.vue:4-9`），两个子组件各自仍有 `art-card`（`frontend/src/views/overseas/admin/OverseasSkillCatalog.vue:2,75`、`frontend/src/views/hengxin/admin/DomesticStudioBindings.vue:2,43`）。其 `border:0` 被全局 `frontend/src/assets/styles/core/app.scss:89-93,105-112` 的 `!important` 覆盖。

独立浏览器在相同 1280×720 视口、隔离 mock 数据下实测：正式目录外/内卡片的计算边框均为 `1px solid rgba(0, 0, 0, 0.08)`，内卡片矩形为 `[280, 315.984375, 951, 219]`；绑定页内卡片也是同样的 1px 边框，矩形为 `[280, 315.984375, 951, 577.515625]`。确认预览两个页签均只有外卡片。可对照 `output/playwright/.playwright-cli/page-2026-11-12T08-52-39-939Z.png`、`page-2026-11-12T08-50-19-944Z.png`、`page-2026-11-12T08-54-30-411Z.png` 和 `page-2026-11-12T08-55-18-112Z.png`。主 Agent 提供的 `page-2026-11-12T08-44-27-943Z.png` 也显示目录内框。

绑定标题也未按预览数值实现：预览 `frontend/preview-domestic-studio/skills.css:1` 使用标题 18px、说明 13px 及标题区 `margin:18px 0 10px`；正式页使用 `frontend/src/views/hengxin/admin/DomesticStudioBindings.vue:3` 的通用标题类，其样式为 `frontend/src/views/hengxin/prototype.css:42-44` 的 17px/650、说明 12px 和不同外边距。这是具体设计差异，不以数据不同解释。

### R6-3 · MEDIUM：目录多出确认预览中没有的常驻刷新按钮

`Product-Spec.md:3` 明确不额外添加功能，确认预览的工具栏只有上传按钮（`frontend/preview-domestic-studio/Skills.vue:7`）。正式国内工具栏额外常驻“刷新 Skill”（`frontend/src/views/overseas/admin/OverseasSkillCatalog.vue:12`），上述两张目录截图可见按钮及位置差异。目录的真实加载/错误恢复需要保留，但当前新增入口与已确认预览不一致，也构成需处理的可能范围漂移。

## Stage 1 · 逐项核查与边界

1. **仅超级管理员管理：所测路径通过。** 国内菜单的 Skills 子项限超管（`frontend/src/router/modules/index.ts:13-19`），API 使用 `manage_system` 并对绑定/开关写入再次授权（`backend/app/modules/domestic_studio/management_router.py:24-27,138-157`）。`backend/tests/test_domestic_studio_management.py:60-76,112-149` 覆盖普通角色、未登录、缺少浏览器标记和文件下载权限；`backend/tests/test_domestic_admin_permissions_pg.py:75-115` 在真实 PG 独立连接覆盖撤权先提交和写入先持锁两种顺序。未验证正式部署身份链。
2. **无预设绑定与并发保护：所测路径通过。** 迁移仅建映射表（`backend/migrations/versions/0033_domestic_studio_bindings.py:11-26`）；`backend/app/modules/domestic_studio/bindings.py:17-27,36-62` 要求事务和 READ COMMITTED，在执行门内对全部五项的原值做比较后保存。`backend/tests/test_domestic_studio_bindings_pg.py:56-112` 验证双连接门锁、隔离级别及陈旧写入 409；停用/删除绑定中 Skill 的服务端保护见 `bindings.py:65-71`、`skill_state.py:33-42`、`skill_publication.py:84-102`。
3. **完整文件夹上传、差异确认及失败恢复：所测路径通过。** 真实组件扫描目录并对同名差异要求确认（`frontend/src/views/overseas/admin/SkillFolderUpload.vue:2-27,59-86,100-107`）；国内路由经独立 socket 进入复用的发布器（`backend/app/modules/domestic_studio/management_router.py:66-119`）。`backend/tests/test_domestic_skill_publisher.py:84-137,190-270` 走隔离 HTTP/存储，覆盖安装、更新、并发保护、提交故障与恢复；`frontend/tests/skill-folders-components.test.ts:63-103` 使用实际 SFC 和内存目录验证上传、差异确认、断线续传。没有在浏览器拖入实际 Skill 文件。
4. **国内导出 ZIP：所测路径通过。** `frontend/src/views/overseas/admin/OverseasSkillCatalog.vue:23` 向实际操作组件传 `zip-only=domestic`，`SkillFolderActions.vue:19-22,32-40` 国内只走 ZIP。`frontend/tests/skill-folder-zip.test.ts:14-46,68-82` 实际解压验证空目录、Unicode、原始字节，并验证即使浏览器支持目录选择也只提供 ZIP；国内服务端固定版本文件读取及越界拒绝见 `backend/tests/test_domestic_studio_management.py:97-109`。没有验证真实浏览器原生下载落盘。
5. **冻结与引用：基础接口所测通过，真实执行未接入。** `backend/app/modules/domestic_studio/skill_references.py:15-32,35-56` 在执行门下冻结绑定、保存引用并核对引用所属版本；`skill_publication.py:64-79,99-118` 更新或删除时保留引用对象并拒绝在途删除。真实 PG 测试 `backend/tests/test_domestic_skill_references_pg.py:23-68` 检查另一连接等待执行门、在途拒绝及结束后旧快照可读。真实发送、会话删除后的引用清理和最终回收尚未接入，见 `docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:17-18`，不能宣称执行闭环通过。
6. **R4 无损初始化恢复：所测路径通过。** `backend/app/overseas/management/skill_initialization.py:29-77` 只对可识别的空索引残留重建指针，保留已有暂存；`skill_objects.py:21-42,45-84` 正常退出时仅清理由该次调用创建的暂存。`backend/tests/test_skill_initialization_recovery.py:61-173` 使用真实子进程退出，覆盖首次初始化、恢复中再次退出、已有目录、硬链接及未知内容保留。不能外推为覆盖所有断电和文件系统故障。
7. **R4 权限锁与执行门顺序：所测路径通过。** 共享入口在恢复前授权，恢复可能提交后由国内 install/delete 重新授权（`backend/app/overseas/management/skill_publisher.py:75-126,128-157`，`backend/app/modules/domestic_studio/skill_publication.py:19-29,44-55,84-86`）。`backend/tests/test_domestic_recovery_lock_pg.py:21-59,64-96` 用真实 PG 连接验证 install/delete 等待权限锁时执行门可取得，及恢复提交释放锁后撤权造成 403。未穷举全部线程时序。
8. **目录按钮交互：隔离浏览器所测通过。** 打开正式 `skills.vue` 及真实嵌套目录组件，网络请求全部指向本机并对测试数据进行拦截；点击“停用”实际发出 `PATCH /api/v1/management/domestic-studio/skills/fixture/availability`，请求体为 `{"enabled":false,"version":1}`，收到 mock 响应后行显示“已停用/启用”；点击“设置绑定”进入含五项控件的绑定页；点击上传打开真实上传弹窗。mock 响应故意只测试前端事件传递，不代表绑定中的 Skill 可在真实后端停用；真实后端应拒绝并已由第 2 项测试。`frontend/tests/skill-folders-components.test.ts:32-61` 另对嵌套 SFC 启停事件及保存禁用作断言。没有操作真实 Skill 或生产。
9. **海外共享路径回归：所测子集通过，有环境边界。** 默认海外地址保持 `frontend/src/api/overseas/skill-transfers.ts:33`；`backend/app/overseas/management/skill_downloads.py:9-30` 保留默认海外目录 provider，`skill_publisher.py:21,159-170,212-219` 默认使用海外发布实现及 maintenance。下列 66 项通过包括海外传输、发布恢复、对象及物理清理；3 项 Linux 所有权/权限测试在 Windows 跳过，见 `backend/tests/test_overseas_installed_skills.py:188`、`test_skill_object_storage.py:207,226`。不等于海外全链路或生产权限已验证。
10. **无版本管理/在线编辑器：本范围静态检查未发现对应页面入口。** 国内目录仅呈现绑定、ZIP、启停、删除（`frontend/src/views/overseas/admin/OverseasSkillCatalog.vue:18-25`）；服务端文件读取供固定版本下载（`backend/app/modules/domestic_studio/management_router.py:122-135`）。R6-3 的刷新按钮另列为可能漂移。全产品未做漂移扫描。

R5 的卡片结构修正把外层页签与内容收进共同容器，目录搜索宽度由 255px 调为 300px、筛选由 140px 调为 150px，绑定行由 20px 调为 22px；对应 `frontend/src/views/hengxin/admin/skills.vue:4-9`、`frontend/src/views/overseas/admin/OverseasSkillCatalog.vue:10,77-79`、`frontend/src/views/hengxin/admin/DomesticStudioBindings.vue:45`。但 R6-2/R6-3 仍存在，因此不能把 R5 结论视作已全部修复。

## 独立验证结果与原始输出

后端测试使用 `HX_BUSINESS_CONTEXT=domestic`、`APP_ENV=test`、临时 `127.0.0.1:35439/hx_studio_test` 和测试 MinIO 凭据；PG fixture 在该测试库下创建并删除随机 schema（`backend/tests/test_domestic_studio_bindings_pg.py:17-41`）。未连接生产。运行 13 个国内恢复、权限、引用、绑定、状态、迁移、发布和管理测试文件：

```text
99 passed, 2 warnings in 51.06s
```

另运行 `test_overseas_skill_transfers.py`、`test_overseas_skill_transfers_failures.py`、`test_skill_publisher_recovery.py`、`test_skill_object_storage.py`、`test_skill_physical_cleanup.py`、`test_overseas_installed_skills.py` 和 `test_overseas_skill_packages.py`：

```text
66 passed, 3 skipped, 2 warnings in 68.35s (0:01:08)
```

前端运行 `pnpm exec tsx --test`，目标为 `domestic-studio-skills.test.ts`、`skill-folder-zip.test.ts`、`skill-folders-components.test.ts`、`skill-folders.test.ts`、`business-route-access.test.ts`、`roles-integration.test.ts`；原始汇总：

```text
ℹ tests 38
ℹ suites 0
ℹ pass 38
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1872.7237
```

`pnpm exec vue-tsc --noEmit` 退出码 0，原始输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
```

为避免构建生成文件修改共享工作区，将当前前端 `src`、`public` 和构建配置复制到临时目录，链接既有依赖，在该副本执行 `VITE_RELEASE_SCOPE=domestic`、`vite build --mode production --logLevel warn`。构建时受审前端文件相对候选未变；原始输出：

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
[plugin vite:reporter]
(!) C:/Users/82358/AppData/Local/Temp/hx-skill-review-r6-536974cde15a4cf0b0d56e5b2b97987b/src/views/auth/dingtalk-login.vue is dynamically imported by C:/Users/82358/AppData/Local/Temp/hx-skill-review-r6-536974cde15a4cf0b0d56e5b2b97987b/src/router/core/ComponentLoader.ts, C:/Users/82358/AppData/Local/Temp/hx-skill-review-r6-536974cde15a4cf0b0d56e5b2b97987b/src/router/core/ComponentLoader.ts, C:/Users/82358/AppData/Local/Temp/hx-skill-review-r6-536974cde15a4cf0b0d56e5b2b97987b/src/router/routes/staticRoutes.ts but also statically imported by C:/Users/82358/AppData/Local/Temp/hx-skill-review-r6-536974cde15a4cf0b0d56e5b2b97987b/src/App.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.

✗ Build failed in 32.68s
error during build:
[hengxin-release-scope] [plugin hengxin-release-scope] domestic release includes other business implementation: src/api/overseas/attachment-download.ts, src/api/overseas/management.ts, src/api/overseas/skill-transfers.ts, src/views/overseas/admin/OverseasLiveSkills.vue?vue&type=script&setup=true&lang.ts, src/views/overseas/admin/OverseasSkillCatalog.vue, src/views/overseas/admin/OverseasSkillCatalog.vue?vue&type=script&setup=true&lang.ts, src/views/overseas/admin/OverseasSkillCatalog.vue?vue&type=style&index=0&scoped=9a4a7eeb&lang.css, src/views/overseas/admin/OverseasSkillPlatformsDialog.vue, src/views/overseas/admin/OverseasSkillPlatformsDialog.vue?vue&type=script&setup=true&lang.ts, src/views/overseas/admin/OverseasSkillPlatformsDialog.vue?vue&type=style&index=0&scoped=17322a5b&lang.css, src/views/overseas/admin/SkillFolderActions.vue, src/views/overseas/admin/SkillFolderActions.vue?vue&type=script&setup=true&lang.ts, src/views/overseas/admin/SkillFolderActions.vue?vue&type=style&index=0&scoped=4dc3e156&lang.css, src/views/overseas/admin/SkillFolderUpload.vue, src/views/overseas/admin/SkillFolderUpload.vue?vue&type=script&setup=true&lang.ts, src/views/overseas/admin/SkillFolderUpload.vue?vue&type=style&index=0&scoped=1fd89514&lang.css, src/views/overseas/admin/skill-folder-metadata.ts, src/views/overseas/admin/skill-folder-read.ts, src/views/overseas/admin/skill-folder-save.ts, src/views/overseas/admin/skill-folder-zip.ts, src/views/overseas/platforms.ts
    at getRollupError (file:///D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/node_modules/.pnpm/rollup@4.52.3/node_modules/rollup/dist/es/shared/parseAst.js:401:41)
    at error (file:///D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/node_modules/.pnpm/rollup@4.52.3/node_modules/rollup/dist/es/shared/parseAst.js:397:42)
    at Object.error (file:///D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/node_modules/.pnpm/rollup@4.52.3/node_modules/rollup/dist/es/shared/node-entry.js:22103:20)
    at Object.generateBundle (file:///D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/node_modules/.vite-temp/vite.config.ts.timestamp-1794473927222-9494e1ef4bab5.mjs:24:34)
    at Object.handler (file:///D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/node_modules/.pnpm/vite@7.1.7_@types+node@24.8_a31ceeca6a88d70e3e28508edf9fb53a/node_modules/vite/dist/node/chunks/dep-Bm2ujbhY.js:34064:13)
    at file:///D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/node_modules/.pnpm/rollup@4.52.3/node_modules/rollup/dist/es/shared/node-entry.js:22425:40
BUILD_EXIT_CODE=1
BUILD_COPY=C:\Users\82358\AppData\Local\Temp\hx-skill-review-r6-536974cde15a4cf0b0d56e5b2b97987b
```

Stage 2 的通用安全扫描、代码质量及邻居基准页面对照未执行。五工作台、真实消息与执行、成品库、生产部署及全产品验收不在本次结论内；最终完整功能应固定新快照，从 Stage 1 重新审查。
