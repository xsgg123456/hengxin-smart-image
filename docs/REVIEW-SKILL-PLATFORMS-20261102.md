# Skill 平台分组与工作台优化独立审查

- 日期：2026-11-02；审查角色：独立 code-reviewer，按 `.agents/skills/code-review/SKILL.md` 执行。
- 最终 candidateId：`7f9ed634b94ebfe777f609e3201d7b3f24851826c0604d5bb143fdb472c0ed3d`。已用 `harness.py review-status` 核实当前编号相同。
- 初审 candidateId：`785a638d65a69911a71ef7fb59de1e7256136137c9a43891b145e82575c3fe30`。初审后复核了 configuration 路径断言及发布 deploy/package/runtime/test 四文件变化；installed_titles 字段修正已在初审读取。前后端生产实现未发生摘要变化。旧候选结论不直接批准新候选。
- 范围：相对 HEAD 的本轮海外 app、0023 迁移、前端 src/package、相关测试、八个发布脚本；预览代码与截图作为设计依据。需求依据为 `Product-Spec.md` 的 2026-11-02 条目及 `docs/SKILL-PLATFORMS-IMPLEMENTATION-20261102.md:5` 六项验收和实施顺序。
- 结论：**Stage 1 PASS（源码符合性）；Stage 2 PASS（本轮源码质量）**。未发现本轮 HIGH/MEDIUM 源码缺陷。此结论允许主 Agent 为同一快照登记源码审查凭据；不代表安装、PostgreSQL、完整 Linux 回归或生产部署已经验收通过。

## Stage 1：Spec Compliance

| 合同条目 | 结论与证据 |
|---|---|
| 1．既有布局、六平台、全部/未分组，无平台字典或品牌扩展 | 完整实现。`frontend/src/views/overseas/platforms.ts:1` 定义六平台；`frontend/src/views/overseas/admin/OverseasSkillCatalog.vue:4` 使用既有 ElTabs，`:48` 使用 ArtTable；无新增字典 CRUD 或品牌匹配接口。 |
| 2．多平台、名称/描述搜索、状态过滤、单项/批量覆盖、并集添加、仅删除当前关联 | 完整实现。`frontend/src/views/overseas/admin/OverseasSkillCatalog.vue:43` 过滤，`:56` 编辑，`:58` 确认移出；`OverseasSkillPlatformsDialog.vue:40` 生成完整更新数组，添加使用 Set 并集、编辑使用草稿数组。`frontend/tests/skill-platforms.test.ts:38` 起覆盖筛选、批量、添加/移出、取消和冲突；审查者复跑通过。 |
| 2．权限、原子批量、版本、审计、失败保留草稿 | 完整实现。`backend/app/overseas/management/router.py:44` 同时应用 browser_request 与 skills.manage；`management/skills.py:73` 再次 lock_actor、共用 execution gate、整批验版本后写入，审计与状态同事务提交。原开关独立校验仍在 `skills.py:46`；新增平台接口不能修改 enabled。`backend/tests/test_overseas_skill_platforms.py:29`、`:52`、`:72`、`:114` 验证普通设计拒绝、开关权限独立、冲突无部分写入、审计故障回滚及 CSRF。`frontend/src/views/overseas/admin/OverseasLiveSkills.vue:58` 失败读回/409更新版本，弹窗不关闭且草稿保留。 |
| 3．工作台已开启且匹配、新提交再次校验、无 Skill 可发、失效草稿、历史幂等/冻结不变 | 完整实现。`backend/app/overseas/management/skills.py:31` 与 `studio/queries.py:135` 过滤；`studio/service.py:66` 先返回历史请求，`:86` 才为新请求调用带 task.platform 的 freeze_selected；`management/settings.py:69` 共享锁并重新读取。`test_overseas_skill_platforms.py:126` 验证过滤、422拒绝、重放、字体包冻结及无 Skill 发送，`:167` 验证历史平台不改写。`frontend/src/views/overseas/studio/use-studio.ts:30` 失效提示/禁发，`frontend/tests/studio-draft-materials.test.ts:146` 验证文字、附件保留和清空后可发。 |
| 4．关联独立存储、十五项初始配置、保留开关、未知未分组、包内容不改 | 完整实现于源码。`backend/app/overseas/management/models.py:25` 增加数据库 JSON 字段；`migrations/overseas/versions/0023_skill_platforms.py:14` 固定十五项，Amazon 10、Wayfair 2、Walmart 2、未分组 1；`:52` 冲突仅更新 platforms，保留原 enabled/version；列存在则返回，避免重复清除用户后续修改。`management/skills.py:25` 未登记项默认关闭且未分组。迁移测试 `backend/tests/test_overseas_skill_platforms_migration.py:14` 覆盖预览种子逐项一致、开关/版本、未知项、重复迁移及国内隔离；**真实 PG 运行待安装阶段，未计通过**。无 Skill 包文件变更。 |
| 5．工作台下拉仅名称、可搜、主动说明；管理页完整描述 | 完整实现。`frontend/src/views/overseas/studio/StudioSkillSelect.vue:2` 保留 filterable，`:4` 仅名称，`:8` 主动说明入口；管理页 `OverseasSkillCatalog.vue:18`、`:19` 保留名称与描述，`:75` 换行显示。`frontend/tests/overseas-skill-availability.test.ts:103` 覆盖名称及说明。 |
| 6．取回名称/路径即时搜索、大小写、清空、结果数、空态、跨过滤勾选、隐藏计数、原约束 | 完整实现。`frontend/src/views/overseas/studio/StudioRecoveryDialog.vue:12` 搜索和结果，`:33` 仅计算可见列表，不修改 selected；`:35` 切换上下文清空搜索。原 `use-studio-recovery.ts:29` 从完整 items 提交已选，`:56` 会话切换取消旧请求并清空选择，100项限制与错误重试路径保留；500 MB 约束未改。`frontend/tests/studio-recovery-component.test.ts:93` 验证路径大写、空结果仍提交隐藏项、清空恢复、失败保留及会话隔离；前段既有测试覆盖忙碌、只读、超时、100项、部分失败重试。 |

上表中 `frontend/`、`backend/` 均相对仓库内 `hengxin-smart-image/`。

**UI 一致性与引导真实性。** 已独立查看 `output/skill-platform-preview/management.png`、`recovery-search.png`、用户原始取回弹窗截图，以及 `output/skill-platforms/formal-management.png`、`formal-conflict.png`、`formal-skill-names.png`、`formal-recovery-search.png`、`formal-recovery-mobile.png`、`formal-invalid-skill.png`。管理页同样使用既有卡片、表格、浅蓝操作；保留完整描述和多平台标签。样式数值核对：平台标签间距 6px、工具栏 12px、搜索宽 255px、上下文 12px 字体/14px 外距、复选框高 46px、弹窗两列/640px下单列，分别见 `OverseasSkillCatalog.vue:69`、`OverseasSkillPlatformsDialog.vue:55`，与预览 `preview-skill-platforms/Catalog.vue` 样式一致。取回弹窗宽 `min(680px,94vw)` 和底部操作保持原组件，390px截图无搜索框或按钮裁切。冲突截图显示草稿与告警并存，失效截图显示原输入与禁发提示。未发现指向不存在功能的引导。

按照主 Agent 禁止审查者操作浏览器的交接限制，本轮采用主 Agent 的真实 Vue + 隔离 HTTP 页面操作记录和渲染截图进行视觉对照；并非审查者独立浏览器重跑，也不冒充生产接口实测。

**Spec 漂移：未发现。** 新 PATCH、数据库关联列、编辑弹窗和发布脚本均对应合同；`backend/app/overseas/tasks/schemas.py:21` 补足既有六目标平台，同时保留历史合法值。独立预览和测试 fixture 未被正式 src 引入。

**发布代码合同：实现，执行待验。** `scripts/release/skill-platform-package.py:15` 要求已审且已提交、核对提交字节与工作树；`skill-platform-runtime.py:19` 统一14个安装回归模块，打包器递归收集本地测试依赖。`skill-platform-deploy.py:83` 保存失败/超时原始输出，拒绝失败及 skipped，只有通过才写绑定 manifest/image 的凭据；`:133` 先查空闲、停止海外 API、再次查空闲、暂停原消费，保留原生进程。`skill-platform-database.py:70` 备份并隔离恢复，`:89` 核验恢复证据与数据库未漂移后附加迁移。`skill-platform-deploy.py:16` 核对原生 PID/配置/源码、其他容器及 Skill tree 摘要；`skill-platform-frontend.py:24` 保留旧哈希资源，`:70` 明确回退入口。尚未实际安装或执行数据库迁移，不能把上述代码存在当作发布已完成。

## Stage 2：Code Quality

- 结构与类型通过：新增生产组件/模块均低于300行，复用原 API、权限、表格和取回 composable。`frontend/src/api/overseas/management.ts:13` 为关联更新和响应定义类型及校验；本轮新增前端生产实现无 any。平台 dialog 独立保存草稿，LiveSkills 负责网络状态，数据库函数负责事务，职责可辨。
- 测试真实性通过：后端测试使用隔离真实安装包及真实服务/API调用；审计中途故障不是仅断言输入，实际检查目录与 Audit 均无变更（`backend/tests/test_overseas_skill_platforms.py:72`）。前端测试编译真实 SFC，故障409/503/403和读回失败均走交互入口（`frontend/tests/skill-platforms.test.ts`）；取回提交断言完整隐藏选择而非只断言过滤函数。PG并发用例验证不同成员、共享版本与等待后重验（`backend/tests/test_overseas_skill_platforms_postgres.py:21`、`:52`、`:81`），运行仍待安装阶段。
- 新代码安全扫描未发现硬编码真实凭据、eval、innerHTML、客户端密钥或用户字符串拼 SQL。平台输入受 Literal/UUID/严格版本/重复项校验（`backend/app/overseas/management/schemas.py:63`）；发布 SQL 的动态表名先经过白名单字符正则（`scripts/release/skill-platform-runtime.py:72`），命令使用参数数组。测试用隔离凭据不属于生产秘密。
- 视觉质量通过本轮截图对照；证据和浏览器实测边界见 Stage 1。未把组件复用数量当作视觉验收。
- LOW，既有测试桩噪声：独立前端复跑出现 `Duplicate keys found during update: 0`；`frontend/tests/membership-test-harness.ts:18` 将多行 slot 展平，重复局部 key。当前19条行为断言通过，正式 ArtTable 有 row-key，截图无对应异常；此项未证明生产缺陷。
- 既有依赖风险单列：`output/skill-platforms-audit.json` 为 critical 0 / high 39 / moderate 38 / low 5。`frontend/package.json:3` 本轮仅版本变更，依赖与锁文件未改；本次源码 PASS 不代表这些既有依赖漏洞已经消除。

## 验证原始结果及边界

前端完整日志 `output/skill-platforms-tests.log`：

```text
ℹ tests 435
ℹ suites 0
ℹ pass 435
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 10263.268
```

类型检查原始命令输出 `output/skill-platforms-typecheck.log`（主 Agent 执行退出0）：

```text
> hengxin-smart-image-frontend@0.2.57 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

生产构建 `output/skill-platforms-build.log`（退出0）最后输出：

```text
✓ built in 59.49s
```

日志含 pnpm 既有配置字段忽略提示；审查未把无输出或告警隐藏当作成功凭据。

审查者独立执行、退出均为0：

```text
pnpm exec tsx --test tests/skill-platforms.test.ts tests/studio-recovery-component.test.ts tests/overseas-skill-availability.test.ts
ℹ tests 19
ℹ pass 19
ℹ fail 0
ℹ skipped 0

.venv/Scripts/python.exe -m pytest -q tests/test_overseas_skill_platforms.py tests/test_overseas_installed_skills.py
31 passed, 1 skipped, 2 warnings in 23.85s

.venv/Scripts/python.exe -m pytest -q tests/test_overseas_configuration.py tests/test_overseas_installed_titles.py
42 passed, 2 warnings in 4.32s

python scripts/release/test_skill_platform_release.py
..............
----------------------------------------------------------------------
Ran 14 tests in 0.135s

OK
```

31条后端测试中的1项跳过明确是 `backend/tests/test_overseas_installed_skills.py:187` 的生产归属权限检查需要Linux；未计为通过。Python告警为既有 Starlette/httpx 和 AnyIO 弃用提示。

Windows全套初跑的原始结尾见 `output/skill-platforms/backend-full-windows.log`：

```text
10 failed, 2533 passed, 409 skipped, 6 warnings in 505.35s (0:08:25)
```

其中 configuration 新API路由断言和 installed_titles 新字段断言已修正，审查者复跑对应文件42条通过。其余8条实际堆栈为 Windows 缺少安全目录读取能力或符号链接权限，涉及 management_freeze、pictures、pictures_protocol；未改生产安全逻辑以迎合Windows。它们已加入 `scripts/release/skill-platform-runtime.py:19` 的Linux安装回归集合。不能声称后端全套已经全绿。

**仍必须完成的发布验收**：从上述已审提交制品运行Linux/真实PostgreSQL安装测试且无 skipped；真实备份隔离恢复、迁移种子与开关保留；生产 API/前端安装摘要、原生与其他服务及全部Skill摘要保持；正式权限、平台筛选和取回入口复验。主 Agent 在此之前不得宣称发布完成。安装失败若需改源码，重新 review-prepare 并审查新 candidate。登记凭据由主 Agent 使用 review-approve 完成，本审查未写 `.needs-review`。
