# Phase 7 全阶段独立审查

日期：2026-09-09。使用 `.agents/skills/code-review/SKILL.md`，从 Stage 1 重新审查两项后端缺陷修复后的代码。依据根 `Product-Spec.md:92`、`:135`、`:426`，`DEV-PLAN.md:246`，`Design-Brief.md:13`、`:57`，以及 `docs/PHASE7-PLAN.md:5`。下文代码路径以 `hengxin-smart-image/` 为根；`scripts/`、`output/` 路径以仓库根为准。表中简写 `templates/`、`skills/` 分别指 `backend/app/modules/templates/`、`backend/app/modules/skills/`，`worker/` 指 `backend/app/worker/`，`test_*.py` 指 `backend/tests/`，组件简写指 `frontend/src/views/hengxin/components/`。

**最终结论：Stage 1 通过，Stage 2 通过；未发现尚未关闭的 HIGH/MEDIUM。前轮两项 MEDIUM 均已关闭，保留一项 LOW 可维护性建议及明确测试边界。** 修复后真实 Linux/PG/MinIO/Worker、浏览器、编译证据已经汇合；满足本次 Phase 7 验收范围。本报告独占文件；未修改产品代码、未 commit、未操作其他 agent 的运行环境。

## Stage 1：Spec Compliance

| 逐项交付 | 结论、代码证据 | 行为证据 |
|---|---|---|
| 名称、适用功能、图片、备注创建保存 | 完整实现。`backend/app/modules/templates/service.py:73` 校验名称、壁纸/商品模式、1–20 张 ready 文件；`:114` 保存名称/备注/操作者；`frontend/src/views/hengxin/components/TemplateEditor.vue:8` 表单 | `backend/tests/test_templates.py:20` 实际上传后保存；`:79` 非法输入拒绝，`:105` 20/21 张边界。原图片 URL/名称从服务端记录取值，伪造值不被采用 |
| 搜索、分页、类型筛选、三种排序 | 完整实现。`templates/service.py:52` 当前未删除版本分页；`:60` 搜索转义；`:66` 名称/图片数/更新时间排序；`frontend/src/views/hengxin/components/Templates.vue:8` 筛选控件、`:59` 查询和过期响应丢弃 | `test_templates.py:105` 名称/数量排序、分页、类型、百分号搜索、空结果；更新时间排序已核对代码，未单独测试相同时间边界 |
| 专用优先、空选择解析模块默认 | 完整实现。`backend/app/modules/skills/service.py:13` 显式版本直接返回，默认只返回同类型 available；`TemplateEditor.vue:13` 清空表示默认；`:51` 显示保存将用的默认版本 | `backend/tests/test_templates_skills.py:23`、`:50`；`frontend/tests/template-versions.test.ts:10`、`:34` |
| 无可用 Skill 草稿；失效专用保留、不静默回退 | 完整实现。`templates/service.py:41` 依据 enabled 与当前 Skill available 返回可用性，`:118` 保留实际引用；`TemplateEditor.vue:14` 原绑定不可用选项、`:18` 草稿提示、`:96` 保留 ID | `test_templates_skills.py:50` 五种状态逐项断言；`:63` 不存在/错类型拒绝、禁用默认解析为空；未把草稿显示成已生成 |
| 保存直接可用，无审批发布 | 完整实现。`templates/service.py:114` 追加版本后直接返回；`:41` 无审批条件；`Templates.vue:29` 可用模板进入对应处理页 | `test_templates_skills.py:23`、`:77` available+enabled 可用，主动停用保持不可用。真实生成仍为 Phase 8 后续范围 |
| 冻结 Skill 与有序图、旧版不随默认变更、新保存重新解析 | 完整实现。`templates/service.py:96` 每次保存解析；`:117` 绑定策略；`:118` 冻结 ID；`:123` 保存 slot；`templates/models.py:22` 版本唯一约束 | `test_templates_skills.py:23` 默认切换前后旧 DTO 完全相同、新版引用新默认；`test_templates.py:20` 反转图片后历史顺序不变；真实集成也断言历史 API |
| 编辑并发冲突 | 完整实现。`templates/service.py:104` 必需 expectedVersion；`:106` CAS；`:111` 失败回滚并返回 409；`TemplateEditor.vue:100` 保留表单并展示错误 | `backend/tests/test_templates_concurrency.py:20` PG 两线程同版本编辑只得到一个 v2 与一个 409；本地该用例跳过，隔离 PG 全量测试已运行；浏览器注入 409 仅证明界面保留输入 |
| 四角色共享查看、编辑、停用、删除 | 完整实现。`templates/router.py:13` 所有接口共用 shared_resources；`backend/app/modules/auth/permissions.py:5` 四角色；`Templates.vue:30` 删除入口；`TemplateEditor.vue:23` 停用 | `test_templates.py:49` 四角色逐一跨 owner 读/改/删；`:123` 未授权/禁用状态拒绝；隔离 API 验证第二用户实际编辑和删除 |
| 实际删除操作者、历史及文件保留 | 完整实现。`templates/service.py:129` 逻辑删除；`backend/app/modules/files/deletions.py:15` 只记 deleted_at、operator_id；`templates/models.py:36` Skill 外键、`:45` 图片外键 | `test_templates.py:49` 数据库历史/文件数不变且操作者为第二用户。删除后模板公开历史接口 404，内部快照仍在；未将 404 误认作历史数据已删除 |
| 只读模板历史 UI | 完整实现。`templates/router.py:26` 历史 API；`templates/service.py:135` 倒序；`frontend/src/api/hengxin/http.ts:66`；`TemplateHistory.vue:7` 版本折叠、`:9` 冻结引用、`:12` 有序图片表、预览 | `frontend/tests/template-versions.test.ts:49` HTTP 路径/返回校验；`scripts/phase7/catalog-flow.js:65` 展开 v1/v2、断言历史接口，稳定截图已实际查看 |
| 仅超管上传/安装/更新/启停/模块默认 | 完整实现。`skills/router.py:22` Admin；`:41/:62/:84/:89` 管理入口；普通目录 `:28` 只返回 available；`frontend/src/views/hengxin/admin/SkillDefaults.vue:29` 仅列匹配可用版本 | `backend/tests/test_skills.py:69` 三个非超管角色 403；真实 API 逐角色验证上传、安装、启停、默认 403；`frontend/tests/template-versions.test.ts:34` 默认权限与类型回归 |
| 三类型版本/校验和/节点/状态/最近变更展示 | 完整实现。`skills/service.py:91` DTO；`frontend/src/views/hengxin/admin/skills.vue:5` ArtTable、`:18` 详情；`frontend/src/api/management.ts:13` 真实 HTTP | `test_skills.py:37` 上传/安装前后目录状态；真实 Linux Worker 结果检查。节点与时间在未安装时返回空，界面显示“尚未安装” |
| 私有原 ZIP、哈希、上传与安装区别 | 完整实现。`skills/service.py:47` 独立对象地址、SHA；`:66` 存储成功才 uploaded；`:74` 单独受理安装；`skills.vue:35` 状态映射、`:37` installing 轮询 | `test_skills.py:37` 上传不直接可用、安装完成后可用；`test_skills_upload_retry.py:10` 两种存储故障；真实 MinIO/Worker 链路已验证 |
| ZIP 格式、CRC、路径、链接与超限 | 完整实现。`skills/package_validator.py:28` 版本/本体；`:43` 1000 条；`:48` 路径；`:58` 文件类型；`:62` 20 MiB 单项/100 MiB 总量/100 倍；`:65` 实读 CRC；`:83` YAML/manifest | `backend/tests/test_skills_packages.py:19` 顶层目录、`:28` 路径矩阵、`:33` 链接/大小写重复/压缩炸弹、`:44` CRC/元数据。未把数值上限代码存在等同于每个上限的动态边界用例 |
| 受控解压、预装依赖检查、不执行包脚本 | 完整实现。`backend/app/worker/skill_install.py:20` which/find_spec，仅顶层 Python 模块；`:48` 写文件；`:52` 可读性；`:56` 原子 rename | `test_skills.py:80` 依赖缺失失败且旧版保持 available；真实 Worker 缺依赖包失败。该流程没有包脚本执行或在线安装命令 |
| Job kind、路由、成功/失败/取消停止重派 | 完整实现。`backend/app/models.py:23` 作业字段；`worker/tasks.py:39` 分派；`worker/leases.py:58` 终态；`worker/outbox.py:24` 仅未完成 queued/running | `test_skills.py:37/:101/:152` 重复执行、取消、永久失败；Phase 5 隔离回归仍通过，日志 `output/playwright/phase7-queue-regression.log:24` |
| 有效租约/心跳/失效 token/恢复 | 完整实现。`worker/leases.py:18` 认领、`:30` 续租、`:40` 心跳；`worker/outbox.py:27` 有效租约不补发；`worker/skill_install.py:83` 发布屏障 | `test_skills.py:101` 有效租约不重派、旧 token 失效；`:124` 旧 owner 不能发布、新 owner 恢复；真实 Redis 停止后安装恢复。持续长安装与硬杀恢复的测试边界见 Stage 2 |
| attempt 目录隔离、失败保留旧版、持久卷 | 完整实现。`skill_install.py:46` 独立临时目录、`:55` UUID+token 不覆盖；`infra/Dockerfile.backend:9` 非 root 可写；`infra/compose.yaml:94` Worker 持久卷 | `test_skills.py:80/:124` 失败及过期 attempt 回归；真实 API/Worker/PG/MinIO 重启后安装路径和 SKILL.md 保持可读 |
| 迁移、注册、运行配置 | 完整实现。`backend/migrations/versions/0003_skills_jobs.py:16`、`0004_templates.py:16`；`migrations/env.py:6`；`backend/app/main.py:33`；`core/config.py:14` 租约配置及 `:34` 比例校验 | `test_templates_migration.py:14` 重复 upgrade、外键、downgrade；本地 compileall exit 0；隔离 PG 空卷和重复迁移日志通过 |

部分实现/未实现：本次 Phase 7 范围未发现整项缺失。REQ-007 中统计、用户维护、监控/系统配置其余部分属后续 Phase；Phase 8 实际任务、Phase 9 CLI、Phase 12 钉钉、Phase 14 图片效果不作为本轮缺失。`Product-Spec.md:290` 旧任务冻结在本轮审查的是不可变模板/Skill 基础，未声称真实任务已接入。

Spec 漂移：未发现无来源新增业务。默认 API、skillBinding、历史 API 与 expectedVersion 均有 `docs/PHASE7-PLAN.md:5`、`:12` 依据；审计表支撑 `Product-Spec.md:434`。Phase 6 文件/身份依赖及其未提交文件不计作 Phase 7 越界。

## Stage 2：Code Quality

### 前轮缺陷复验

- S2-01 已关闭：`skills/service.py:30` 的锁查询使用 populate_existing，强制覆盖 Session 内旧状态；`skills/router.py:72` 锁后检查 available。`test_skills_concurrency.py:19` SQLite 精确重现旧缓存；PG 在真实两个事务之间插入禁用提交，并执行真实 save_defaults，期望 422 且默认不落库。此用例证明该竞态时序，不声称测了阻塞等待或随机压测。
- S2-02 已关闭：`skills/service.py:11` 用 UPLOAD_INCOMPLETE 标记预留行；`:59` 仅相同校验和、failed+未上传完成可重传；`:62` 锁后重验；`:75` 未上传完成不能排安装。`test_skills_upload_retry.py:10` 参数化写前失败/写后响应失败，实际 HTTP 503→同包原 ID 原 object_key 201，异包/已成功包 409，恢复后才能受理安装。新增行为没有放开已成功包覆盖。

### 质量与安全

- 本轮后端 skills/templates/worker 文件均未超过 300 行，最长 `templates/service.py:1` 共 139 行；前端新组件 TemplateEditor 104 行、TemplateHistory 43 行、SkillDefaults 49 行，使用明确 TypeScript 类型。`frontend/src/types/hengxin.ts:34` 与 `backend/app/contracts/business.py:57` 字段一致，`frontend/src/api/hengxin/validate.ts:18` 校验返回结构。
- LOW：`skills/service.py:37`、`templates/service.py:93` 等服务参数/返回值未注解；`frontend/src/views/hengxin/admin/skills.vue:39` 多步异步逻辑压在单行，可读性有限。可后续补类型并展开，未发现因此产生的功能错误。
- 安全扫描：本次 skills/templates/worker 与五个前端组件未命中 eval/exec/shell=True/innerHTML/dangerouslySetInnerHTML/前端密钥变量或 API key 字面量。ORM 查询参数化；私有对象路径由 UUID 生成，用户 ZIP 路径只在校验后的新目录内写入；`package_validator.py:87` 使用 safe_load；`skill_install.py:26` 不导入点分依赖父模块。未发现已证实 HIGH 安全问题，结论仅限本轮范围。
- `infra/verify_phase7.py:35` 随机项目/凭据/端口，`:143` 独立测试数据库，`:257` 收尾只清理本项目；没有将随机测试 SQL、测试凭据或本地工具路径误认作业务注入/硬编码秘密。

### 测试真实性与边界

- 前端 41 个测试主要覆盖 mock/HTTP adapter，不冒充实际 Vue 组件测试。`frontend/tests/template-versions.test.ts:49` 为请求/响应桩；真实组件交互另看浏览器脚本。`scripts/phase7/catalog-flow.js:49` 注入 409 只证明保留草稿；生产 CAS 另由 PG 双线程测试证明。
- `backend/tests/files_helpers.py:64` 的 SQLite/内存对象存储不证明 MinIO、PG 锁或多进程。隔离 Linux 全量 108 个测试及 HTTP/真实 Worker/MinIO 是另外的证据；本地跳过 6 个 PG 条件用例已明确报告。
- `test_skills.py:101/:124` 手动改租约/token/取消状态，确实验证生产状态屏障；不代表用户取消 API、运行中杀死安装进程、磁盘写满或持续长安装心跳压力测试已做。Phase 5 的硬杀测试使用受控测试作业，不能外推为外部 CLI exactly-once。
- ZIP 当前用例实际触发压缩比、路径、链接、CRC/元数据错误；本体 20 MiB、单项 20 MiB、总量 100 MiB、1000 条上限尚无逐一跨界用例。代码数值匹配工程计划；这些是明确测试盲区，未发现已复现功能缺陷。
- 无真实业务 Skill、CLI、生成图片效果或钉钉测试。截图使用 2×2 白色 PNG 是文件链路 fixture，不是生成质量样本。

### 视觉对比

已两次使用 view_image 打开 `output/playwright/phase7-skills.png`、`phase7-history.png`、`phase7-neighbor.png`。初轮发现邻居加载中，要求重拍；最终 17:53 稳定截图已复核，模板/Skill 已加载、提示 toast 消失，邻居正确选中“浏览器版本冻结 · v2”并显示 v3.0.0 Skill。历史对话框左右边界约 x=172/852，即 680 px，与 `TemplateHistory.vue:2` 相符，在 1024 px 桌面视口可容纳；内容较高通过标准对话框滚动查看，浏览器已成功点击关闭并继续删除流程。`scripts/phase7/catalog-flow.js:72` 横向溢出断言通过。

Skill 默认卡片与邻居处理页使用相同浅灰背景、白色圆角卡片、蓝色按钮/选中态和 Art 侧栏，未发现风格不匹配。`frontend/src/views/hengxin/prototype.css:3` 标题/间距、`:8` 卡片 23 px、`:31` 窄桌面 17 px 内边距沿用邻居，主题 `frontend/src/config/index.ts:121` 包含 #5D87FF。Skill 截图是页面滚动后默认区与版本表末尾，不声称截图覆盖了整张版本表；表格上传/安装行交互由真实浏览器脚本 `:9` 至 `:25` 验证。白色图片 fixture 不用于视觉效果质量判断。

## 编译与执行原始证据

本 reviewer 独立执行，后端 cwd `hengxin-smart-image/backend`：`.venv/Scripts/python.exe -m pytest -q`，exit 0。原始输出：

```text
................................................ssss.........s.......... [ 66%]
......................s.............                                     [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
102 passed, 6 skipped, 2 warnings in 6.75s
```

`.venv/Scripts/python.exe -m compileall -q app migrations`：exit 0，stdout 为空。前端 cwd `hengxin-smart-image/frontend`，显式 `D:/Apps/nodejs/node.exe node_modules/vue-tsc/bin/vue-tsc.js --noEmit`：exit 0，stdout 为空。

独立前端测试命令 `D:/Apps/nodejs/node.exe node_modules/tsx/dist/cli.mjs --test tests/*.test.ts`，exit 0；原始汇总：

```text
ℹ tests 41
ℹ suites 0
ℹ pass 41
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 2042.8554
```

独立构建 `D:/Apps/nodejs/node.exe node_modules/vite/bin/vite.js build`，exit 0；原始关键输出（省略逐个 bundle 大小）：

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 3300 modules transformed.
rendering chunks...
[plugin vite:reporter]
(!) D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/views/auth/dingtalk-login.vue is dynamically imported by D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/core/ComponentLoader.ts, D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/routes/staticRoutes.ts but also statically imported by D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/App.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
computing gzip size...
✓ built in 37.55s
```

上述警告来自既有登录模块动静态双引用，未阻断构建。主 Agent 另一轮原始构建日志 `output/playwright/phase7-build.log:3`、`:8`、`:338`（66 秒）提供可落盘交叉证据，未混淆为本 reviewer 的 37.55 秒执行。

隔离 Phase 5 回归原始日志已读取：`output/playwright/phase7-queue-regression.log:1` 至 `:8` 包含真实队列、重复消息、Redis 中断、Worker 硬杀恢复；`:21` 为 `108 passed, 2 warnings in 6.77s`；`:24` 为 `PHASE5 INTEGRATION PASS`。这是主 Agent 执行证据，本 reviewer 没有再次操作其容器。

最终 Phase 7 日志已读取：`scripts/phase7/integration.log:15` 全量 108 passed，无 skipped；`:17` 至 `:25` 真实 Worker/Redis 故障恢复/历史冻结/重启/非超管403/跨 owner 删除；`:27` 浏览器；`:29` 总验收；`:30` 四卷清理。`docs/PHASE7-INTEGRATION.md:3` 记录进程 exit 0。原始输出：

```text
108 passed, 2 warnings in 5.82s
PASS real Worker install 1.0.0
PASS real Worker install 1.0.1
PASS real Redis outage install recovery
PASS real Worker install 2.0.0
PASS draft, explicit precedence, defaults freeze, image order, conflict and type validation
PASS restart persistence
PASS installed files and frozen bindings survive restart; disabled explicit never falls back
PASS second isolated user
PASS non-admin 403, shared edit/disable/delete, actual operator audit and retained history
PASS isolated Vite browser frontend
"PHASE7 BROWSER PASS: upload/install/default/template/edit conflict retained/order/history/narrow/delete; pageerrors=0"

PHASE7 INTEGRATION PASS (four isolated volumes)
PASS isolated Compose volumes cleaned
```

集成脚本最初未 return 浏览器结果导致空返回断言失败，修正 `scripts/phase7/catalog-flow.js:87` 显式返回标记，并在 `:5/:76` 等待稳定状态后完整重跑通过；未删除任何业务断言。期间产品代码没有再修改。修复前 104 pass 和首轮后端报告 99 pass 均不当作修复后的最终全阶段结论。下一阶段可按 DEV-PLAN 进入 Phase 8；本报告不外推真实生成和登录能力。
