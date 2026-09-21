# Skill 轻量管理独立审查

审查日期：2026-09-21。使用 `.agents/skills/code-review/SKILL.md`。最终结论：**Stage 1 PASS，Stage 2 PASS**；无未解决 HIGH/MEDIUM，保留1项非阻断 LOW 建议。

## 快照与范围

- 初始 candidateId：`0df8d54c8702e6f6a229990e63a745f319d436c301e28fd7b414ba49e9bec77a`。
- 更新候选：`89e753706e8ae45c045e3240387197934abf867c0305c4bb10603d32d7cfc6ba`。主 Agent 说明仅补 PostgreSQL 独立测试模型导入，已核实。
- 范围：相对 HEAD `4b6e490` 的 Skill 目录管理、同步 Worker、自动快照、模板/默认/任务绑定、迁移0014、前端及专项测试；需求依据 Product-Spec 的 2026-09-21 确认段、DEV-PLAN 顶部、Design-Brief 新说明及 LIGHT-SKILLS/API-CONTRACT。
- 最终 candidateId：`ea3d522e40ef2c8a7800ede8ae208c1596fe98f0b5541990ca3182e0d28e7004`。审查中发生3项修复，已对新增差异、测试前提和原始输出重新审查；最后执行 `harness.py review-status` 确认 currentId 与此候选一致。以下 PASS 仅适用于该最终快照，主 Agent 另行 review-approve，不写 clean。

## Stage 1：PASS

### 先前发现的问题（均已修复，保留证据）

1. **HIGH：类型选择请求会被已扫过该目录的运行中同步吞掉。** 候选 `backend/app/modules/skills/catalog_router.py:56` 修改类型并设 syncing，`catalog_service.py:72` 合并任意 queued/running 作业，而 `worker/skill_sync.py:171` 仅单次顺序扫描。可达条件：aaa 未知类型已扫描完成、Worker 正在探测 zzz 时，另一管理员页面提交 aaa 类型。真实 API/Worker fixture 复现（Linux权限及probe由已有fixture替代）：`MODE 200 status=syncing`；随后 `JOB status=succeeded`；`ROWS [('aaa', 'text', 'syncing'), ('zzz', 'text', 'available')]`。不再有作业处理 aaa，与“选择类型后同步可用”不符。
2. **HIGH：编辑模板与提交任务锁序相反。** `backend/app/modules/templates/service.py:103` 经 resolve_binding 锁 Skill 后于 :114 UPDATE 模板；`backend/app/modules/tasks/snapshots.py:37` 先锁模板，再于 :49 锁 Skill；`backend/app/modules/skills/service.py:18` 为新增 FOR UPDATE。并发编辑和提交同模板可形成 Skill→Template / Template→Skill 循环，PG选择一个事务死锁失败，当前服务无该错误的业务转换。
3. **MEDIUM：历史 Skill 身份的模板 active 状态与 activeOnly 列表不一致。** `backend/app/modules/templates/service.py:34` 根据整个身份的 state 判断 active，但 :68 在 catalog_status=None 时只检查原绑定版本。历史同名身份含旧 disabled 和新 available 时，旧模板详情 active=true，却从新任务所用 activeOnly 列表消失。实际 HTTP fixture 输出：`DETAIL_ACTIVE True`；`ACTIVE_LIST {'items': [], 'page': 1, 'pageSize': 20, 'total': 0}`。

### 最终快照修复复核

1. 类型并发：`backend/app/modules/skills/catalog_router.py:59` 在 settings 单例锁下检查全局 queued/running 作业，返回409且不修改类型。`backend/tests/test_skill_catalog.py:217` 参数化覆盖排队、已扫过该Skill仍在运行两种情形，并验证原 needs_type 保持、作业结束重试可用。原复现得到的永久 syncing 不再发生。
2. 锁序：`backend/app/modules/templates/service.py:108` 编辑先锁 Template，再解析 Skill，和 `tasks/snapshots.py:37` 一致。`backend/tests/test_skill_catalog_template_concurrency.py:24` 使用真实PG、线程事件、SQL执行钩子，在任务已持有模板锁时让编辑进入；确认两者完成、任务仍冻结模板V1、编辑得到V2、过期编辑409。检查了测试前提，不使用SQLite替代PG行锁。
3. legacy activeOnly：`backend/app/modules/templates/service.py:68` 使用关联 EXISTS 判断同一身份任一 available 版本，与详情 state 口径一致。`backend/tests/test_templates_skills.py:89` 实际HTTP验证旧绑定disabled、新版本available时详情和列表完全一致。

修复回归原文：`51 passed, 2 warnings in 9.73s`（output/light-skills-backend-review-fix.txt）；独立PG交错原文：`1 passed in 1.95s`（output/light-skills-template-concurrency.txt）。

### 已检查的需求覆盖（最终快照完整实现）

| 需求 | 代码证据与验证 |
|---|---|
| 固定 root/name/SKILL.md，读取名称和完整描述，无人工版本入口 | `backend/app/modules/skills/local_tree.py:41`、`:94`；`frontend/src/views/hengxin/admin/skills.vue:3`、`:11`；`test_skill_catalog.py:62` 验证长描述与完整文件快照 |
| manifest 明确类型，未知类型人工选择，不猜描述 | `local_tree.py:94`；`catalog_router.py:56`；`test_skill_catalog.py:103`；并发缺陷见问题1 |
| 一个稳定身份，首次成功自动可用，手动停用跨同步保持 | `worker/skill_sync.py:92`、`:154`；`catalog_service.py:96`；`test_skill_catalog.py:62` |
| 异常与缺失不伪装成功，单目录故障不覆盖正常目录 | `worker/skill_sync.py:121`、`:145`、`:180`；`test_skill_catalog.py:103`、`:122`、`:185` |
| 异步作业、持久化多请求合并、租约 fencing | `catalog_service.py:72`；`worker/skill_sync.py:61`、`:136`；`test_skill_catalog_database.py:43` 四并发 PG 测试；`test_skill_catalog.py:150` 失去租约拒绝发布；类型并发例外见问题1 |
| 新任务最新成功内容，模板及默认按稳定身份解析 | `skills/service.py:13`；`management/settings.py:65`；`templates/service.py:38`；`tasks/snapshots.py:49`；`test_skill_catalog_frozen.py:80`；历史筛选例外见问题3 |
| 已提交/排队任务与返工保留完整原字节 | `worker/skill_sync.py:37` 保存ZIP对象；`execution/materials.py:84` 按任务version/checksum读取；`tasks/service.py:51` 固定快照；`test_skill_catalog_frozen.py:20` 实际准备原/新/返工材料并逐字节断言 |
| 保存失败不发布、相同内容复用前先校验对象 | `worker/skill_sync.py:113`、`:121`；`test_skill_catalog.py:122`、`:185`（object_missing、drift等） |
| 软移除不删除磁盘/历史快照，当前模板及默认引用保护 | `catalog_service.py:40`、`:115`；`test_skill_catalog.py:122`；`test_skill_catalog_frozen.py:20`、`:80` |
| 旧 name/version 及 ZIP 兼容，原本地任务仍依赖原树 | `worker/skill_sync.py:100`；`execution/materials.py:90`；`migrations/versions/0014_skill_catalog.py:12`；`test_skill_catalog_database.py:62`；文档 LIGHT-SKILLS.md 明确不可删除历史目录 |
| 固定根、越界/软硬链接/特殊文件/大小/权限拒绝 | `local_tree.py:41`、`:48`、`:65`、`:71`、`:78`；`package_validator.py:43`；`test_skill_catalog_linux.py:58` 真实 Linux 专项 |
| 隔离只读probe，不执行Skill脚本/生图；保留可执行位 | `execution/local_skill_probe.py:12`、`:44`（可信Python -I probe）；`worker/skill_sync.py:43`；`execution/materials.py:109`；`test_skill_catalog_linux.py:43` |
| 新API鉴权、旧API不能绕过catalog停用/移除 | `catalog_router.py:21`、`:29`、`:74`；`skills/router.py:29`、`:82`；`local_service.py:24`、`:45`、`:64`；`skills/service.py:28`；`test_skill_catalog.py:150` |
| 描述全文/模板用途、无Skill版本操作/摘要 | `admin/skills.vue:11`、`:76`；`components/TemplateEditor.vue:14`、`:21`；`components/CreateTask.vue`、`components/TaskTemplate.vue`；前端119测试及主 Agent mock浏览器证据已读取，独立视觉阶段尚未执行 |
| 范围漂移 | 所有新增生产模块/API/迁移均对应本轮目录管理或内部快照；未见新增产品页面或无需求业务功能。内部随机快照version未暴露为管理员版本管理。 |

## Stage 2：PASS

初次发现 HIGH 后停在 Stage 1；3项修复并固定最终快照后才执行本阶段。

| 检查 | 结论与证据 |
|---|---|
| 文件大小、类型及职责 | 对全部变更及新增 .py/.ts/.vue 计数，无超过300行文件；前端无新增 TypeScript any。`catalog_router.py:16`负责HTTP、`catalog_service.py:12`负责身份状态/绑定、`worker/skill_sync.py:163`负责作业执行；前端API响应由`validate-skill-catalog.ts:4`检查。 |
| 错误处理与并发 | `worker/skill_sync.py:123` 存储/探针失败不发布；`:136` 发布前复核租约；`catalog_service.py:72` 持久化合并；上列真实PG测试覆盖请求合并与编辑/提交锁序。同步异常清理失败只留下不可达对象（`:81`），不对外发布。 |
| 测试真实性 | `test_skill_catalog_frozen.py:20` 调用真实prepare_materials并核对字节，含移除后返工；`test_skill_catalog.py:150` 真正更改claim_token验证不能发布；Linux专测`:43`、`:58`切换nobody身份并跑bubblewrap，Windows fixture 明确不声称验证Linux权限。PG新增测试使用真实两线程SQL交错。 |
| 安全扫描 | 扫全部变更源文件的eval、dangerouslySetInnerHTML、innerHTML、VITE凭据变量、sk-ant/sk-proj无命中。`package_validator.py:43`拒绝危险路径；`local_tree.py:26`校验管理员拥有和Worker不可写；SQL使用SQLAlchemy绑定条件；迁移DDL为固定语句，测试schema仅服务端生成UUID。`local_skill_probe.py:54`使用参数数组与可信内置probe，不执行Skill脚本。 |
| UI实际视觉对照 | 审查员独立打开IAB本机3010显式mock页，在1280×720实际截图比较Skill管理和邻居模板库：白色卡片、浅灰背景、蓝色主按钮、相同侧栏/标签及圆角；Skill长描述点击“展开全文”后全文换行可见，没有横向裁切。再打开模板配置，处理Skill下方完整用途文字可见。对应`admin/skills.vue:8`、`:11`、`:76`和`components/TemplateEditor.vue:21`。没有新增专用设计稿，按Design-Brief继承现有组件验收。 |
| 引导及范围 | 同步、停用、选择类型、解除绑定后移除等引导均有后端实现；模板说明与稳定身份解析一致。主Agent已完成额外mock交互，见验证文档；本审查实际浏览器补验仅证明渲染与用途展示，不替代后端或付费生成验证。 |

**LOW（非阻断）：** `frontend/src/api/hengxin/mock-skill-catalog.ts:56` 的 setCatalogMode 尚未完整模拟生产API的全局在途409与已有类型不可更改；真实页面 `admin/skills.vue:12`、`:47` 已通过不可变显示和blocked禁止该交互，生产API及其回归独立验证，所以不影响本轮生产验收。后续扩展mock测试时建议统一，避免直接调用mock服务的测试误以为这些操作允许。

## 已读取的验证原始输出

以下是主 Agent 保存输出的原文摘录，审查员未重跑全量，不把条件跳过算通过。

```text
# output/light-skills-backend-tests.txt
801 passed, 112 skipped, 15 warnings in 88.05s (0:01:28)
# output/light-skills-backend-focused.txt
17 passed, 2 warnings in 5.10s
# output/light-skills-backend-postgres.txt
test_sync_request_concurrency_coalesces_durable_job PASSED
test_0014_idempotent_migration_preserves_legacy_binding_and_payload PASSED
============================== 2 passed in 1.31s ==============================
# output/light-skills-frontend-typecheck.txt
ExitCode=0
# output/light-skills-frontend-build.txt
✓ built in 1m 21s
# output/light-skills-frontend-tests.txt
ℹ pass 119
ℹ fail 0
ℹ skipped 0
```

Linux 16 passed / 可执行位补充7 passed 为主 Agent 实机记录，见 LIGHT-SKILLS-VALIDATION.md；本审查只读取测试与记录，未再次启动Linux隔离。未部署生产、未调用付费生图。
