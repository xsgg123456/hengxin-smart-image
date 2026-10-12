# Phase20 独立两阶段审查

- 日期：2026-10-12；审查角色：code-reviewer；执行 `.agents/skills/code-review/SKILL.md`。
- candidateId：`6da26831e9068bf6fdfa1d4930cff787ee8ac49899453b82c33dbcd1b4782f50`；提交基线：`814b2d0`。
- 上次批准快照：`f8ee28817724abffbbb55bbb9d5bbf107b65407a1e6abfe37a5b008be3269117`。本次以 review-status 列出的 46 个差异文件为代码范围，不重复批准旧实现。已有技能、gitignore、package/locales、独立预览闭包不是本轮新增风险。
- 范围：海外 materials 全包、任务创建/补交/能力、公共 multipart 参数、入口/schema/冻结0005迁移及依赖；正式资料API、身份请求超时、Portal/TasksPage/MaterialsPanel/MaterialPreview；资料测试与Phase19适配；identity-test Phase20环境/检查。以下路径以 `hengxin-smart-image/` 为代码根，文档与 output 以仓库根为准。
- 依据：`Product-Spec.md:971`、`DEV-PLAN.md:116`、`docs/OVERSEAS-PHASE20-CONTRACT.md:1`、验收记录、`Design-Brief.md:167`。DOC拒绝和submitted不执行AI以明确的Phase20合同为准。

## Stage 1 — Spec Compliance：PASS

| 条目 | 结论、代码证据与验证 |
|---|---|
| 20.1 独立原件/版本/所有权 | PASS。`backend/app/overseas/materials/models.py:9` 两张海外表、原件checksum/owner/task/版本；`files.py:16` 使用海外配置与既有store；`backend/migrations/overseas/versions/0005_materials.py:12` 冻结表定义。迁移测试 `backend/tests/test_overseas_materials_migration.py:9` 对0004数据及重复升级逐表比较；resources日志确认双向隔离。 |
| 文件类型、非空、大小、签名 | PASS。`materials/parsers.py:31` 限PDF/DOCX/XLS/XLSX/CSV及20MiB，DOC明确另存提示；`router.py:21` 显式扩大海外multipart；`backend/app/modules/files/multipart.py:19` 默认仍取原10MiB。`test_overseas_material_parsers.py:68`、`test_overseas_materials.py:81` 及真实HTTP覆盖空、超限、类型。 |
| 20.2 五种真实解析 | PASS。`document_formats.py:61` DOCX段落/表格/页眉脚注；`:82` PDF文字；`:94` XLSX；`:117` XLS；`:138` CSV。实际文档断言在 `test_overseas_material_parsers.py:83,97,117,127,184`，独立Linux复跑通过；没有用文件名或固定示例冒充内容。 |
| 不支持、资源上限及执行隔离 | PASS。`document_formats.py:38` ZIP总量/条目/压缩比例/XML实体限制；`:85` 加密/页数；`:107` 单元格限制；`parsers.py:59` 子进程、15秒超时、2MiB文本；`parser_worker.py:9` Linux512MiB/12秒CPU。测试 `test_overseas_material_parsers.py:92,112,138,152,166` 真申请600MiB、真进程超时回收。无OCR；不运行Office、宏或计算公式，XLSX data_only/keep_links=False。 |
| 原件保存、失败可重试、版本留存 | PASS。`files.py:16` 先保存原件；`service.py:52` ready/failed解析版本；`files.py:46` 重试核对大小/checksum并追加；`service.py:40` DTO含版本且无桶/key。`test_overseas_materials.py:58,89` 比较旧版本及原始字节；真实浏览器切换失败版本。 |
| 所有权和实时任务访问范围 | PASS。`service.py:28` 未绑定要求当前task.create与本人，绑定重新查询任务及当前权限；`:105` 列表先授权；`files.py:47,71` 写前权限锁。`test_overseas_materials.py:134,151`、真实浏览器七身份及改派验证：旧设计403、新设计200；真实国内fileID读取/关联404，国内表与对象快照不变（`infra/identity-test/phase20_checks.py:95`）。 |
| 安全私有原件交付 | PASS。`files.py:84` 复用FileDelivery/OwnedStreamResponse，PDF inline、其他attachment、no-store/nosniff，无公开URL/缩略图旁路；`router.py:45` 所有content都经过同一授权。真实HTTP验证字节、header、匿名和另一业务凭据拒绝（`phase20_checks.py:59,136`）。 |
| 删除墓碑及引用保护 | PASS。`files.py:70` 锁→验证未绑定→墓碑commit→物理删除；提交结果未知不删除原件。`service.py:16,21` 墓碑不可读、已绑定不可修改；`test_overseas_materials.py:170` 清理失败再次删除，`:184` 回滚；故障测试 `test_overseas_materials_faults.py:26,47` 未知commit保留原件。 |
| 一或两份、原子绑定、并发 | PASS。`tasks/schemas.py:26` 数量和重复UUID；`materials/schemas.py:6` 严格补交体；`service.py:65` 排序资料锁、本人未绑定、种类不同、成功版本；`tasks/service.py:40` 创建事务；`materials/service.py:80` 补交/事件/outbox同事务。真实PG竞争 `test_overseas_materials_postgres.py:32` delete/retry/双任务bind三类并发独立复跑通过；故障回滚`:134`通过。 |
| Phase19兼容与记录级补交 | PASS。`tasks/service.py:43` exclude_none维持旧hash；`materials/service.py:81` 权限锁→幂等→任务→资料，补交仅创建者/运营主管且文件归操作者。`tasks/queries.py:37` 能力仅created合资格任务；`test_overseas_materials_faults.py:15,109` 实际旧hash和主管/普通运营验证通过。 |
| 20.3 实际上传进度、取消、重试/删除 | PASS。`frontend/src/api/overseas/materials.ts:61` XHR progress事件；`OverseasMaterialsPanel.vue:45` abort及generation屏蔽迟到结果、`:59`重试、`:66`删除确认；`OverseasTasksPage.vue:67` 只提交成功资料。真实故障浏览器覆盖错误响应、网络失败、取消/路由迟到、冲突、撤权、窄屏；进度回调数值由 `frontend/tests/overseas-materials.test.ts:59` 断言。 |
| 解析与PDF真实预览/下载 | PASS。`OverseasMaterialPreview.vue:8` 版本选择，`:13`文本插值，`:48`关闭/撤销blob，`:54`独立窗口且opener=null，`:60`读取原件。独立复跑 `overseas-materials-real.browser.mjs:37` 检查PDF原生viewer真实1页，截图实际显示“Actual requirements for browser PDF preview”；关闭后窗口确已关闭，CSV下载文件名正确。 |
| UI一致性及引导真实性 | PASS。`OverseasMaterialsPanel.vue:2,81` Art白卡/16px节标题/14px子标题，`OverseasMaterialPreview.vue:2` 880px且最大94vw；`OverseasTasksPage.vue:3,12` 复用现有Create/TaskInfo。目视1366px任务邻居和390px资料页：蓝色操作、白卡、边框、间距同源，文字和按钮不裁切。`frontend/src/api/overseas/tasks.ts:3` submitted仅“图需已提交”，没有虚构AI进行中或入口。 |

完整实现：上述本阶段条目全部匹配。部分实现/未实现：无。后续CLI调度/分析、OCR与旧DOC不属于本阶段承诺。Spec漂移：未发现；新增路由/表/组件均可对应合同。独立预览示例仅在非真实Material分支展示（`OverseasMaterialPreview.vue:17`），正式文件按真实DTO进入解析分支。

## Stage 2 — Code Quality：PASS

- 结构/类型：PASS。46个差异文件逐个统计，除生成锁文件外无超过300行；业务职责分离到files/service/parsers/worker/formats。新增前端接口使用Material/ParseVersion、unknown运行时guard（`api/overseas/materials.ts:3,14`），无新增TypeScript any。公共文件/身份/权限/任务设施直接复用（`materials/files.py:7`、`router.py:5`）。
- 安全：PASS。新增范围扫描未见密钥、eval、HTML注入、拼接用户SQL或前端秘密；扫描的any命中仅Python内建any和AbortSignal.any。文本插值不执行输入；defusedxml拒绝实体，文件名复用safe_name；异常仅安全描述（`parser_worker.py:23`、`files.py:28,89`）；私有桶与跨凭据由真实资源验证支持。测试环境显式测试口令不视为生产密钥（`infra/identity-test/phase20_checks.py:16`）。
- 测试真实性：PASS。已区分MemoryStore单测与真实MinIO HTTP；PG竞争使用独立schema/真实行锁（`test_overseas_materials_postgres.py:32`），不是SQLite模拟锁；解析fixture包含真实PDF/OOXML/OLE，恶意XML/超时/内存都实际执行。独立浏览器使用正式3015入口、真实后端/PG/MinIO，只有钉钉provider替身。前端故障通过真实界面交互触发拦截网络响应，不把该测试宣称真实存储。
- 旧测试调整：PASS。Phase19能力断言增加记录级补交；路由白名单仅新增资料端点及四个允许复用的公共文件模块；迁移头改0005仍保留旧数据比较（`test_overseas_configuration.py:147`、`test_overseas_tasks.py:54`、`test_overseas_tasks_migration.py:35`）。没有通过删掉授权/隔离断言掩盖回归。
- 视觉对比：PASS。审查者独立运行真实资料页及邻居任务页浏览器脚本，并打开 `output/playwright/phase19/task-real.png`、`output/playwright/phase20/materials-real-mobile.png`、`output/playwright/phase20/pdf-preview.png` 检查实际渲染；PDF有真实文字，390px长任务信息换行，资料/原任务卡片、按钮保持同一Art/Element先例。未以iframe存在作为可预览证据。
- HIGH/MEDIUM/LOW发现：无。测试工具弃用warning属于既有环境；Windows仅墙钟限制、Linux另有内存/CPU限制是已声明执行边界。

## 编译与验证原始输出

审查者独立运行Linux镜像中解析、真实PG竞争、故障专项（挂载本候选代码只读）：

```text
docker run --rm --network hx-p20-suite-9d22bcba -v D:/Work_Project/hengxin-smart-image/hengxin-smart-image:/workspace:ro -w /workspace/backend -e TEST_OVERSEAS_MEMBERS_DATABASE_URL=postgresql+psycopg://postgres:phase20-only@pg/phase20_test hengxin-smart-image-backend:phase20 /app/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_overseas_material_parsers.py tests/test_overseas_materials_postgres.py tests/test_overseas_materials_faults.py
40 passed, 2 warnings in 13.10s
```

审查者独立运行3个浏览器脚本，均退出0，原始输出：

```text
PASS real materials: DOC refusal; failed PDF/retry versions; delete confirmation; actual PDF native viewer/no opener/close cleanup; CSV parse/text-safe/download; metadata supplement; frozen binding; five-role and reassignment authorization; narrow UI
PASS material browser faults: size/type/empty; real XHR progress; cancel and route late response; network/malformed; parse retry; safe text; deletion conflict/cancel; no ready no submit; narrow clipping; revoked content clears state
PASS real HTTP/DB browser: five roles+dual menus/direct links; multi-SKU create/reload; list scope; manager reassignment/audit; old designer immediate denied; new designer readable; 1366/390 screenshots
```

已读取主Agent完整原始日志，未声称独立重跑全量：

```text
output/phase20-backend-final.log:
1926 passed, 17 skipped, 15 warnings in 268.21s (0:04:28)
output/phase20-frontend-tests-final.log:
ℹ tests 270
ℹ pass 270
ℹ fail 0
ℹ skipped 0
output/phase20-typecheck-final.log:
> vue-tsc --noEmit
output/phase20-frontend-build-final.log:
✓ built in 34.98s
output/phase20-clean-build.log:
✓ built in 34.59s
output/phase20-preview-build.log:
✓ built in 44.55s
output/phase20-http-final.log:
PASS ALL Phase 17 real HTTP integration
PASS ALL Phase 18 real HTTP integration
PASS ALL Phase 19 real HTTP integration
PASS ALL Phase 20 real HTTP integration
CLEANED hx-p20-d6c771cce3b8
output/phase20-resources.log:
PASS: bidirectional PostgreSQL/MinIO/Redis credential isolation; DML allowed, DDL denied; private buckets
PASS: redis failure => ready 503, live 200; recovery => ready 200
PASS: minio failure => ready 503, live 200; recovery => ready 200
PASS: postgresql failure => ready 503, live 200; recovery => ready 200
```

clean-build为主Agent从HEAD导出并加入正式候选所做独立构建，核对其原始完成输出；不把既有未提交预览依赖当正式代码前提。17项跳过是主Agent记录的既有宿主条件项，不将skip计作功能通过。未执行生产部署、真实钉钉认证或收费模型调用。

## 快照结论

Stage 1 PASS；Stage 2 PASS。审查开始及收尾核对当前candidate一致；没有发现审查期间受控代码变化。本报告只适用于上述candidate及范围。由主Agent使用同一candidate登记review-approve；审查者未写clean、未修代码、未提交。
