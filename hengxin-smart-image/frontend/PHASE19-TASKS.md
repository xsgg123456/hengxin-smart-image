# Phase 19 前端任务接入验收

## 实施与边界

1. 续建原 OverseasCreate 的基本信息/SKU 表单，上传、示例与模拟执行移到预览包装器。正式提交固定为“保存图需”，只保存基础信息、SKU、负责设计。
2. 原 OverseasWorkspace 表格与筛选继续共用；正式接真实分页、搜索、状态、与我相关及当前页刷新，原预览保留其统计/删除/归档编排。
3. 原 OverseasTaskInfo 直接接真实 TaskDetail，显示提交人、负责设计、资格提示、SKU、备注、事件操作者/版本/改派前后标识。预览资料通过 slot 注入，正式静态依赖中没有 preview-adapter 或模拟 workflow。
4. DesignerPicker 异步搜索与分页，具备加载、空候选、失败重试。写操作携带 Idempotency-Key，相同未成功正文重试沿用原键，修改正文生成新键；保存中禁用输入与返回，迟到成功不劫持用户离开的路由。
5. Portal 从服务器能力建菜单。每次任务/候选请求前刷新海外身份；401/403清任务内容并刷新身份，身份刷新失败关闭业务入口；列表网络失败清旧数据与动作。改派409刷新详情后清空选择，重选才可继续。

继承 Art Shell、layout-content、data-box-mode、16px卡片及既有表格/表单。局部修正长名称的页头换行与真实UUID事件文本换行，未改公共CSS。

## 验证记录（2026-10-12）

- `pnpm test`：264 passed，0 failed（含一期身份请求回归与新增API合同/幂等键/字段校验测试）。日志：`../../output/phase19-frontend-tests.log`。
- `pnpm typecheck`：最终生成声明整理后执行，退出码0、零类型错误。
- `pnpm exec vite build --mode production`：正式构建成功；`pnpm exec vite build --config vite.overseas.config.ts --mode demo`：预览构建成功。日志分别为 `../../output/phase19-frontend-build.log`、`../../output/phase19-preview-build.log`。
- `node tests/overseas-tasks-faults.browser.mjs`：通过候选空/失败/分页、多SKU、保存断网后相同key重试、详情、409刷新重选、列表分页/搜索、网络清内容、加载/空/错误态祖先裁切、390px关键按钮、撤权与401。测试替身仅此故障脚本内API，不能替代真实联调。
- `node tests/overseas-tasks-real.browser.mjs`：真实身份/海外/国内HTTP和真实隔离PG，仅钉钉provider为测试替身；五角色与兼任菜单/直链、多SKU保存及刷新持久化、列表范围、主管改派/真实审计、原设计下一请求拒绝、新设计可读均通过。1366/390截图在 `../../output/playwright/phase19/`。脚本临时为dual增加设计角色，finally恢复原角色。
- `node tests/overseas-members-faults.browser.mjs`：Phase18多角色、冲突刷新、禁用确认、空/窄屏、断网、401/403、撤权与国内隔离回归PASS。
- `node tests/overseas-preview.browser.mjs`：原预览5项PASS（多SKU、失败重试、方案/逐图返工、整套归档、390/760/1440、零业务API、零页面异常）。主线程另验 `overseas-management.browser.mjs` 5/5、`overseas-shell.browser.mjs` 4/4 PASS。

浏览器使用现有外部Playwright安装，不新增依赖。3012原预览未重启；本任务3015 Vite代理真实harness身份64702、国内64703、海外64704，供独立审查复用。该隔离服务结束后端口不可当作长期配置。

## 本Phase提交候选（相对frontend）

首轮审查后的收尾：任务空态根据task.create能力显示“提交图需”或“联系运营”；新增无创建权限时的文案/无提交按钮/窄屏裁切浏览器断言。主线程重跑264项、typecheck和故障浏览器均通过，并在仅HEAD+正式候选的隔离目录再次`pnpm build`通过（31.72s，原始日志`../../output/phase19-clean-build-final.log`）。

- `src/api/identity/request.ts`
- `src/api/overseas/tasks.ts`
- `src/identity-main.ts`
- `src/types/import/components.d.ts`（只增加 ElStep / ElSteps 声明，恢复其他构建删改）
- `src/views/overseas/OverseasPortal.vue`
- `src/views/overseas/types.ts`（既有共享类型/状态常量；正式API复用状态文案）
- `src/views/overseas/OverseasCreate.vue`
- `src/views/overseas/OverseasWorkspace.vue`
- `src/views/overseas/OverseasTaskInfo.vue`
- `src/views/overseas/OverseasTasksPage.vue`
- `src/views/overseas/DesignerPicker.vue`
- `tests/overseas-tasks.test.ts`
- `tests/overseas-tasks-faults.browser.mjs`
- `tests/overseas-tasks-real.browser.mjs`
- `PHASE19-TASKS.md`

## 预览本地闭包边界

本次为维持已有预览而适配的 `src/overseas-preview/{CreatePage.vue,PreviewWorkspace.vue,WorkspacePage.vue}` 与 `src/views/overseas/OverseasDetail.vue` 留在本地，不纳入Phase19提交。它们继续依赖既存未跟踪的preview-adapter、workflow、Archive/Pictures/Annotation/MaterialPreview及预览入口；入口还连接此前未提交的预览管理页。主线程确认本Phase不把整套旧预览混入提交。正式提交候选无运行时依赖此闭包，干净checkout的正式入口可构建；本地预览回归结果不表示这套既有预览已被本Phase纳入版本控制。

既存 package.json、locales、技能修改均未回滚或纳入本次前端候选。独立review与提交由主线程控制，本执行子Agent未stage/commit。
