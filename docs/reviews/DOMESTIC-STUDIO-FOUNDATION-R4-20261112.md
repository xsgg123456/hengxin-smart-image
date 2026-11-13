# 国内工作台基础任务第四轮审查

- 候选 `candidateId`：`368767100a1484abe622ea39bcd61f7cd883e1d767b141d1b1f3bf2bc02a3c8b`。
- 范围：`hengxin-smart-image/backend/app/modules/domestic_studio/{policy,models,bindings}.py`、`backend/migrations/versions/0033_domestic_studio_bindings.py`、`backend/migrations/env.py` 的模型导入、`backend/tests/test_domestic_studio_{policy,bindings,bindings_pg,migration}.py`，以及 `frontend/src/views/overseas/studio/StudioTurns.vue` 和 `frontend/tests/studio-message-metadata.test.ts` 的两项可选显示开关。对照 `Product-Spec.md:1-11`、`docs/reviews/DOMESTIC-STUDIO-BINDING-{20261112,R2-20261112,R3-20261112}.md`。
- **Stage 1：PASS，仅限上述基础策略、绑定锁原语、迁移及两个组件开关。**未接线的正式业务不能由本结论推定完成。
- **Stage 2：PASS，仅限上述审查范围。**本 reviewer 未独立运行四项 PostgreSQL 集成测试；主 Agent 提供的运行结果与独立运行边界见下。
- **快照变化：**审查开始 `review-status.currentId` 等于候选。撰写报告时按 `.codex/hooks/review_files.py` 比较候选与工作树，当前 ID 为 `f2df03014917a504db3982452eeca99e962b5654f09eeabe1ec91888cb0d2e1a`。范围内 `backend/migrations/env.py` 新增 `skill_state` 模型导入，属于主 Agent 后续开发；本报告只审原候选中的 `domestic_studio_models` 导入，不覆盖新导入。范围外还变化 `backend/app/main.py`，新增 `backend/app/modules/domestic_studio/{installed_skills,management_router,skill_state}.py`、`backend/migrations/versions/0034_domestic_studio_skill_states.py`、`backend/tests/{test_domestic_installed_skills,test_domestic_skill_state,test_domestic_skill_state_migration}.py`（前缀均为 `hengxin-smart-image/`）。其他本次审查文件在该次核对时哈希未变。主 Agent 还在继续开发，后续 ID 可能再变；本报告不批准新增内容，也不能用旧候选结论登记新快照。组件渲染时 Vite 一度自动改写 `frontend/.auto-import.json` 和 `frontend/src/types/import/components.d.ts`；reviewer 已核验 HEAD 内容的哈希与候选一致，并仅将这两个本人造成的生成副作用恢复至候选内容。文中涉及候选的行号以原候选为准，新导入可能使后续行号偏移。

## Stage 1：逐项对照

以下“基础层完整”仅指候选交付的原语或组件开关，**不代表该项完整产品行为已接通**。

| Spec 条目 | 结论与证据 |
| --- | --- |
| 五工作台及菜单（`Product-Spec.md:5`） | **基础层完整、菜单未实现。** `policy.py:12-24` 定义且只承认 `camera/case/product/scene/phone`，预览名称对应 `frontend/preview-domestic-studio/workspaces.ts:11,21,31,41,51`；`test_domestic_studio_policy.py:21-25` 检查未知入口。正式菜单、直达和超级管理员可见性属于后续范围。 |
| 默认空白、无欢迎/示例、会话及消息（`Product-Spec.md:6`） | **组件开关完整，正式工作台未实现。** `StudioTurns.vue:3,35` 的 `hideEmptyGuide` 隐藏现有空态；海外调用 `OverseasStudio.vue:23` 未传该属性，维持原样。`studio-message-metadata.test.ts:18-30` 实测有/无开关。真实国内会话、推荐卡片、输入内容、切换、发送、身份和时间链路尚未接入或审查。 |
| 使用教程（`Product-Spec.md:7`） | **本次范围未实现和验证。**目前原语及消息组件没有教程接线；后续正式入口需如实显示待补充。 |
| 仅新品归档、成品库（`Product-Spec.md:8`） | **归档策略完整，业务链未实现。** `policy.py:12-18,27-30` 仅允许 `camera/case`，另外三项返回 403，`test_domestic_studio_policy.py:9-18` 覆盖。HTTP 路由是否调用该策略、保存归档、源会话删除后留存以及成品库查询/下载均未验证。 |
| 固定启用 Skill、不接受客户端覆盖、无默认（`Product-Spec.md:9`） | **绑定/冻结原语完整，真实 catalog 和发送链未接线。** `bindings.py:36-59,71-79` 验证整批绑定并在门锁下读取发送时绑定；`policy.py:33-53` 拒绝客户端指定、空绑定和冻结身份不匹配；`test_domestic_studio_policy.py:28-72`、`test_domestic_studio_bindings.py:35-61` 覆盖对应分支。`0033_domestic_studio_bindings.py:19-26` 只建表不预置记录，`test_domestic_studio_migration.py:13-24` 验证空表。启用状态由注入的 `verify_enabled` / freezer 提供，测试使用替身，不能证明真实国内 Skill 包可用性或文件快照。 |
| 禁止停用/删除已绑定 Skill（`Product-Spec.md:9`） | **保护原语完整，业务端点未接线。** `bindings.py:62-68` 同一门锁下检查绑定并返回 409；`test_domestic_studio_bindings.py:64-71` 验证同步调用。停用/删除实现未来必须在同一事务、同一门锁下实际调用；本报告未验证最终防绕过。 |
| 已有请求不受后续绑定变动影响（`Product-Spec.md:9`） | **本次仅定义委托边界，完整行为未验证。** `policy.py:39-43`、`bindings.py:71-73` 要求调用方保存冻结快照；国内执行记录、文件包快照和真实请求后的换绑不在本范围，不能将返回映射等同于已持久化不可变快照。 |
| Skill 文件夹上传、差异确认、ZIP 和超级管理员授权（`Product-Spec.md:9`） | **本次范围未实现和验证。**`bindings.py:36-47` 只接受外部校验回调，不是上传、导出或授权端点；范围外新增模块另行审查。 |
| 国内身份、会话、执行、图片、对象、队列及隔离（`Product-Spec.md:10`） | **本次只审查国内绑定模型基础隔离。**`models.py:5-14` 使用国内 `Base`；`migrations/env.py:4-7,25,34-36` 注册模型并拒绝海外上下文/标记。实际身份、权限、队列、对象存储、执行器及既有 API/海外回归不在本次范围，不能据此声称端到端隔离通过。 |
| 综合验收和部署（`Product-Spec.md:11`） | **未实施最终验收。**上述会话、附件/失败恢复、归档、ZIP、未登录/跨业务以及发布均须后续独立验证；本报告不是上线或整体项目完成的证据。 |
| 上轮陈旧读、隔离级别和新 guard | **当前原语满足审查边界。**`bindings.py:17-27,49-50,75-77` 拒绝非事务或非 READ COMMITTED 的 PostgreSQL 连接，并强制 ORM 刷新；`test_domestic_studio_bindings_pg.py:52-62,77-95` 分别设计了两个物理连接读新值、已有 RR 快照拒绝和 AUTOCOMMIT 拒绝。锁保护依赖调用方将操作和提交保持在同一事务内。 |
| 可选隐藏 Skill 标签 | **组件开关完整，国内应用尚未接入。**`StudioTurns.vue:6,35` 只在 `hideSkillLabels` 为真时隐藏标签；海外调用未设置开关（`OverseasStudio.vue:23`）；测试断言默认和隐藏两种情况以及消息头不变（`studio-message-metadata.test.ts:18-30`）。 |

范围内新增绑定表、五入口策略及组件开关可追溯到 `Product-Spec.md:5-9`；没有发现范围内多出生产页面或 API。完整产品的漂移须后续整体审查。

## Stage 2：质量、安全、视觉和测试真实性

- **上轮 `Any`：已移除。** `policy.py:33-38` 和 `bindings.py:71-72` 改用 `Mapping[str, object]`；运行时只验证 `skill` 为映射且 ID 匹配（`policy.py:49-52`）。这不是对真实文件快照全部字段或不可变性的类型/运行时证明，接线时仍需针对真实 freezer 验证。
- **上轮锁竞争测试：已收紧。** `test_domestic_studio_bindings_pg.py:65-74` 要求 `OperationalError.orig.sqlstate == '55P03'`，回滚/释放锁后还再次取锁；不再接受任意 `OperationalError` 作为锁超时。主 Agent 报告已在 PostgreSQL 18 实跑；本 reviewer 本轮没有独立复跑。
- **AUTOCOMMIT guard：已加入。** `bindings.py:20-25` 读取 psycopg 驱动连接的 `autocommit`，不是严格 `False` 即拒绝，并检查服务器事务隔离级别；单元替身和真实 PG 测试分别位于 `test_domestic_studio_bindings.py:131-143`、`test_domestic_studio_bindings_pg.py:91-95`。项目实际配置限定 `postgresql+psycopg`（`app/core/config.py:115-116`）。
- **测试盲区：**`test_domestic_studio_bindings.py:15-23,88-112` 的 SQLite 单线程两个 Session 不能证明不同 PostgreSQL 物理事务；真实 PG 代码另用不同 driver connection（`test_domestic_studio_bindings_pg.py:52-62`）。该文件默认无测试 URL 即跳过（`test_domestic_studio_bindings_pg.py:17-24`），CI/最终验收不能把 SQLite 通过当作数据库锁验证。真实 catalog、锁内写入执行记录、路由授权、已有 Job 文件快照等尚未实现，未来必须做端到端和故障路径回归。
- **安全扫描：**对范围内生产代码、迁移、四个后端测试和两个前端文件搜索密钥、`eval`、`innerHTML`、`dangerouslySetInnerHTML`、`VITE_*KEY/SECRET/TOKEN`、用户目录及硬编码密码模式，未发现命中。PG 测试中的动态 schema SQL（`test_domestic_studio_bindings_pg.py:25-30,38-40`）只使用固定前缀和 `uuid4().hex`，非用户输入。此为关键词和代码审查，不是完整渗透测试。
- **质量与规模：**生产 `policy.py` 53 行、`bindings.py` 79 行、`models.py` 14 行、迁移 30 行、`StudioTurns.vue` 65 行；本次范围未发现超过 300 行、显式 `Any` 或 `any` 类型。`bindings.py:38` 中英文自然语言单词 `any` 不是类型。
- **实际渲染：**reviewer 使用本地隔离 fixture 在浏览器并排挂载实际 `StudioTurns.vue` 与项目 `studio.css`、Element Plus：海外默认空会话显示“从你的设计需求开始”，隐藏开关为真时为空；带消息时默认显示“原有 Skill”，隐藏开关为真时标签消失，消息署名、正文、左右布局和回复仍存在。该对照只验证组件，fixture 不接生产 API，不是国内正式页面或完整邻居页面的视觉验收。正式国内页面尚不存在，设计稿整页对照留待后续接入时执行。

## 验证与原始输出

后端工作目录 `hengxin-smart-image/backend`，以下为 reviewer 独立执行：

```text
> .venv/Scripts/python.exe -m pytest tests/test_domestic_studio_policy.py tests/test_domestic_studio_bindings.py tests/test_domestic_studio_migration.py tests/test_domestic_studio_bindings_pg.py -q
.......................................ssss                              [100%]
39 passed, 4 skipped in 2.77s

> .venv/Scripts/python.exe -m alembic heads
0033 (head)

> .venv/Scripts/python.exe -m compileall -q app/modules/domestic_studio migrations/versions/0033_domestic_studio_bindings.py migrations/env.py tests/test_domestic_studio_policy.py tests/test_domestic_studio_bindings.py tests/test_domestic_studio_bindings_pg.py tests/test_domestic_studio_migration.py
（无输出，退出码 0）
```

其中 4 项跳过是未设置 `TEST_DOMESTIC_STUDIO_DATABASE_URL` 的 PG 用例；`0033 (head)` 是新增 0034 之前执行的结果，不代表报告撰写时的最新迁移头。`compileall` 仅验证 Python 语法，不是完整后端构建。

主 Agent 转述其隔离 PG 18 上完整命令的原始末尾（同一候选四个后端测试文件；reviewer 未亲自观察运行）：

```text
........................................... [100%]
43 passed in 2.03s
```

前端工作目录 `hengxin-smart-image/frontend`，以下为 reviewer 独立执行：

```text
> pnpm exec tsx --test tests/studio-message-metadata.test.ts tests/studio-sessions.test.ts
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
✔ 国内复用消息组件可隐藏空态引导与 Skill 名称，海外默认不变
...（其余已通过用例省略）
ℹ tests 15
ℹ suites 0
ℹ pass 15
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1377.4276

> pnpm exec vue-tsc --noEmit
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
（退出码 0）
```

`vue-tsc --noEmit` 是类型编译检查，不等同 Vite 完整生产构建。
