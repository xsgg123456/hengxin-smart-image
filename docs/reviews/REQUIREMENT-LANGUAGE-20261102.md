# 图需语言及归档六字段独立审查

审查日期：2026-11-02。使用 `.agents/skills/code-review/SKILL.md`，只读审查实现，只写本报告；未修代码、未提交、未登记批准。

## 快照与范围

- 最终 candidateId：`7d1fa3d7af3d619fb6cb3d0f826f401df8bd70a29e98c583acfd6adf8e8d6ac6`。
- 首次交接 `8c745f8db4bc2fd6a571dbb543b413e02bad1eb018f37eb1a22596a5ac45b7ff`；审查中先变更为 `9c91c34e7eef98616e38364849acbf9d388f810ac17d1b510e2c99fc9506c7a2`，仅两处旧迁移测试追加新增列 NULL 预期；再变更为最终编号，仅修正两份前端测试的历史平台前提。已逐处复核，业务源码未随这两次修正变化。
- 范围：相对 HEAD 的本轮完整 diff 及未跟踪新增文件，包含前后端、迁移、受影响测试、7 个 language 发布工具和5个发布测试文件；需求依据 `Product-Spec.md:1388`、`DEV-PLAN.md:1604`、`docs/REQUIREMENT-LANGUAGE-20261102.md:1`。本轮合同所有行为和发布约束均列于下表；不是对既有整个产品重新验收。
- 设计依据：`Design-Brief.md:201`、`:212`、`:226` 的海外 Art/Element、既有表单与归档信息布局。此次无新专属设计稿，复用原组件，不另设视觉规范。

## Stage 1 — Spec Compliance：PASS

| 合同项 | 实现与验证证据 | 结论 |
|---|---|---|
| 语言必填、默认空、英语/德语/法语/西班牙语四值及顺序 | `frontend/src/views/overseas/languages.ts:1`、`OverseasCreate.vue:49`、`frontend/src/api/overseas/tasks.ts:88`；`backend/app/overseas/tasks/schemas.py:23` 的无默认 Literal 同时约束 CreateTask/ResubmitTask。HTTP 覆盖四值、缺省/null/空/非法，见 `backend/tests/test_overseas_requirement_language.py:12`。 | 完整实现 |
| 新建平台为空、“请选择目标平台”、必填，保留原选项/品牌/SKU/设计校验 | `frontend/src/api/overseas/tasks.ts:88`、`OverseasCreate.vue:44`、`:78`；`backend/app/overseas/tasks/schemas.py:21`；浏览器逐次新建断言默认空并验证平台及语言未填均无请求，见 `frontend/tests/requirement-language.browser.mjs:60`。 | 完整实现 |
| 重提保留现有平台及语言，历史缺语言必须补选 | `frontend/src/views/overseas/requirements.ts:5`、`OverseasCreate.vue:81`；`backend/app/overseas/tasks/requirements.py:93`；最终浏览器用后端允许、当前平台选项未列的 TikTok Shop 验证历史保留，`:86`，不再以任意非法值模拟成功。 | 完整实现 |
| 语言落库、列表/详情可查看、审核快照保存当时值 | `backend/app/overseas/tasks/models.py:18`、`service.py:58`、`queries.py:34`、`requirements.py:63`；`frontend/src/views/overseas/OverseasRequirementsReview.vue:50`、`OverseasTaskInfo.vue:17`、`OverseasTasksPage.vue:22`；HTTP 创建幂等回放/读库/详情及重提后旧审核记录不变。 | 完整实现 |
| 归档详情顶部六字段、标签一致，不另填表 | `frontend/src/views/overseas/OverseasArchiveFields.vue:9` 顺序 SKU/目标平台/品牌/任务名称/品名/语言；`backend/app/overseas/archives/service.py:55` 返回独立归档字段。浏览器逐项核对 dt/dd，`frontend/tests/requirement-language.browser.mjs:100`。 | 完整实现 |
| Archive 保存独立任务名称/语言，既有四字段保持；删除来源仍可读 | `backend/app/overseas/archives/models.py:13`、`snapshot.py:12` 初始化快照；`backend/tests/test_overseas_archive_cover.py:59` 验证归档后任务改名/改语言不覆盖，删除后 null 保持；`test_overseas_task_deletion.py:105` 验证六字段及归档图片保留。 | 完整实现 |
| 历史可空；未知显示未设置，不从 market/品名猜测 | `backend/app/overseas/tasks/models.py:18`、`archives/models.py:13`；`frontend/src/views/overseas/languages.ts:8`、`OverseasArchiveFields.vue:12`；`frontend/tests/overseas-archive-ui.test.ts:95` 验证 null/缺字段/未知语言及来源删除。 | 完整实现 |
| 历史任务继续读取、审核、设计和归档；重提才强制语言 | 读取/审核/归档不引入新语言校验；强校验位于创建/重提 schema。`backend/tests/test_overseas_requirement_language.py:39` 实测历史 null 审核/退回/补选重提；`test_overseas_archive_cover.py:59` 实测 null 归档。 | 完整实现 |
| overseas_0024→0025，只补真实关联归档、不得覆盖已有值 | `backend/migrations/overseas/versions/0025_requirement_language.py:9` 三个 nullable 列及关联 UPDATE/COALESCE；无关联记录不更新。`backend/tests/test_overseas_requirement_language_migration.py:16` 真实 PostgreSQL 验证既有数据、无关联 null、重复 DDL、已有快照保护及国内隔离。 | 完整实现 |
| 权限、幂等、版本控制及 market/remarks 兼容保持 | `backend/app/overseas/tasks/requirements.py:12` 既有权限/版本/请求摘要路径保持，语言自然纳入 model_dump 摘要；`:94` 仍仅对显式兼容字段赋值。`test_overseas_requirement_language.py:13` 同键改语言409；`test_overseas_requirements.py:70` 重提幂等；`test_overseas_market_optional.py:45` 历史 market 省略保留。 | 完整实现 |
| 版本0.2.59；10 API/8 native，native旧archives/service保留 | `frontend/package.json:3`、`scripts/release/language-runtime.py:22`、`:24`、`:29`；`test_language_native_baseline.py:92` 实际临时目录验证旧 service 字节不变且改动被 guard 拒绝。 | 完整实现 |
| Skill、五人授权、国内及原配置保持，无新增模型调用 | 产品 diff 无 Skill/执行调用变更；`scripts/release/language-deploy.py:18` 保护 Skill 全树、无关容器；`language-native.py:36` 保护源码及配置；`language-runtime.py:161` 比对 OVERSEAS_* 与 HX_BUSINESS_CONTEXT 摘要；`language-deploy.py:199` 核对 API 配置及环境。 | 完整实现 |
| 固定生产基线，审查/提交后打包，安装测试通过再停服务 | `language-package.py:50` 要求已提交、无未跟踪文件、批准快照及固定0.2.58/image/0024；`language-deploy.py:43` 实查源字节、配置、原生基线；`:106` 隔离镜像+PG测试，`:139` gate 必须持有效测试凭据。基线证据 `output/language-release/baseline.json`。 | 实现完整，实际安装属后续发布验收 |
| 排空、备份、恢复验证、迁移与切换可恢复 | `language-deploy.py:139` 停API前后检查idle并暂停消费者；`language-native.py:96` 禁止SIGKILL、限时等待且失败保留保护；`language-database.py:92` dump、隔离恢复、两次迁移及旧行/列核验；`:136` 正式迁移先核备份。`language-deploy.py:157` 迁移开始后禁止恢复旧服务；`language-frontend.py:72` 前端回退保留两代hash资源。 | 实现完整，生产执行尚未验收 |

以上 `frontend/`、`backend/` 相对路径以 `hengxin-smart-image/` 为根。

未实现/部分实现：本轮代码合同内未发现。正式安装、生产迁移、入口视觉/健康/版本/哈希及不触发生产任务的验收属于主Agent后续发布步骤，本报告不将代码审查 PASS 写成已部署。

UI一致性：`OverseasCreate.vue:90` 保留两列/minmax与18px gap，600px以下一列；语言复用原 ElFormItem/ElSelect。`OverseasArchiveFields.vue:27` 两列、12px×24px间距、14px正文，标签56px容纳四字标签，compact仍42px，600px下一列。已实际打开渲染截图 `output/playwright/requirement-language/create-desktop.png`、`archive-1366.png`、`archive-390.png`、`resubmit-390.png`，并与邻居 `output/playwright/designer-only/create-fields.png`、`returned.png` 比较，白色卡片、蓝色操作、标签与表单间距匹配；六项窄屏完整换行。最终截图的 TikTok Shop 已目检。浏览器还执行逐元素裁切/横向溢出断言，不只依赖截图。旧 failure.png 未用作最终证据。

Spec漂移：新增 language 工具为合同明确发布范围；无额外业务页面、表、API、模型调用。DTO增加字段和兼容演示数据属于该需求必要联动。

## Stage 2 — Code Quality：PASS

- 结构/类型：新增语言标签与校验集中在 `frontend/src/views/overseas/languages.ts:1`；后端沿用 schema→service→DTO 与 archive snapshot 分层，没有旁路持久化。所有本轮修改/新增 `.py/.ts/.vue/.mjs` 文件均不超过300行；新增生产代码未引入 any。`git diff --check` 无输出。
- 测试真实性：抽查真实 TestClient+数据库、真实PG迁移、实际SFC和生产dist浏览器四层证据。浏览器API使用隔离mock，明确不冒充真实后端联调；后端独立HTTP/PG测试补证。发布单测mock生产命令，仅证明安全分支，不冒充线上安装执行。
- 已修 MEDIUM：初版 `frontend/tests/requirement-language.browser.mjs:86`、`overseas-requirements-component.test.ts:132` 用 schema 不允许的“历史平台”模拟重提成功。已改为 schema 可达的 TikTok Shop，最终全测448及生产dist浏览器通过；当前快照不保留该问题。
- 迁移测试修正：`backend/tests/test_overseas_management_migration.py:49`、`test_overseas_materials_migration.py:39` 给新 language 列增加 None；`test_overseas_designer_roles_migration.py:58` 将旧角色迁移自身的比较固定到0024，0025另由新增迁移测试独立覆盖。没有删除数据保持断言或忽略失败。
- 新增代码安全扫描：无新增硬编码生产凭据、eval、危险HTML注入、前端秘钥暴露。`language-runtime.py:66` 检查清单、路径/符号链接及hash；`:129` SQL标识符来自经正则限制的库表名；`language-native.py:20` 路径守卫与原子替换。`language-database.py:33` 的 isolated 凭据仅用于无外网临时测试容器。
- 安全边界：`output/language-release/dependency-audit.json:1` 既有依赖审计摘要为 high39/moderate38/low5；本轮没有依赖/锁文件变更，未在此复核各漏洞适用性。因此不能声称全项目依赖审计无问题。
- 发布故障路径：独立复跑132个 language+outon 单测，覆盖漂移拒绝、测试失败不给凭据、隔离恢复失败清理、竞争提交、停止超时保留保护、原生不相关文件保留、前端部分切换回退等。证据 `scripts/release/test_language_safety.py:141`、`test_language_release.py:17`、`test_language_native_baseline.py:92`。

未解决 HIGH/MEDIUM：无。低优先级新增建议：无。

## 编译与测试原始证据

前端 `hengxin-smart-image/frontend/language-typecheck.log`（主Agent运行、审查者读取）：

```text
> hengxin-smart-image-frontend@0.2.59 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

前端 `output/language-release/frontend-build.log` 原始末行（正式 build 含 vue-tsc）：

```text
> hengxin-smart-image-frontend@0.2.59 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4709 modules transformed.
✓ built in 34.82s
```

前端 `hengxin-smart-image/frontend/language-tests.log`（最终修正后）：

```text
ℹ tests 448
ℹ suites 0
ℹ pass 448
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9498.7379
```

生产dist隔离浏览器 `output/language-release/browser-final.log`：

```text
PASS empty platform/language required; four languages create/resubmit/details; null/absent legacy requires selection; historical platform retained; archive six independent snapshot fields and unknowns; 1366/390 visible clipping checks
```

审查者独立运行 `backend/.venv/Scripts/python.exe -m pytest -q`，选择 `test_overseas_requirement_language.py test_overseas_archive_cover.py test_overseas_requirements.py test_overseas_task_deletion.py test_overseas_market_optional.py`：

```text
..............................................                           [100%]
46 passed, 2 warnings in 13.81s
```

审查者独立运行全部 `scripts/release/test_language*.py` 与 `test_outon*.py`：

```text
........................................................................ [ 54%]
............................................................             [100%]
132 passed in 6.53s
```

后端Windows全量历史运行 `hengxin-smart-image/backend/language-regression.log`：

```text
8 failed, 2615 passed, 416 skipped, 6 warnings in 476.71s (0:07:56)
```

该结果不是全量通过。失败为 safe-open平台能力与Windows符号链接权限相关；主Agent随后在Linux/PG执行相关模块。Linux A批原始 `output/language-release/batch_a.stdout`：

```text
FAILED tests/test_overseas_management_migration.py::test_0008_upgrade_removes_usage_and_domestic_unchanged
FAILED tests/test_overseas_materials_migration.py::test_upgrade_0004_preserves_existing_tasks
2 failed, 530 passed, 2 warnings in 351.93s (0:05:51)
```

上述两项旧断言已经修正并重新固定候选。Linux B批及两项重跑结果待主Agent回传追加；不得把A批这次结果写成全部通过。

## 交接结论

Stage 1 PASS；Stage 2 PASS，仅对上列最终 candidateId 的代码实现及已列证据有效。代码审查不替代剩余Linux回归、提交后实际安装包测试、生产发布和正式入口验收。主Agent应先核回归结果，再依据本报告用 review-approve 登记同一快照；禁止向 .needs-review 写 clean 代替凭据。
