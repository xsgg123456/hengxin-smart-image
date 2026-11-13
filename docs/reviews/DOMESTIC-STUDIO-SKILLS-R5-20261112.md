# 国内 Skills 管理独立复审 R5 · 2026-11-12

- 送审 candidateId：`f4f2bd7527e42e1a5df6148e06cc9b03c32366f0cb2e1813f163d1c19dd43da9`。
- 范围：国内 Skills 管理、五工作台初始绑定与并发保护、超级管理员授权与撤权、文件夹上传/更新/ZIP/删除、引用保护、发布日志与故障恢复，以及共享海外发布器的相关变更。依据 `Product-Spec.md:3-11`、`Design-Brief.md:1-3`、`DEV-PLAN.md:1-10`、`docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:1-24`、确认预览 `hengxin-smart-image/frontend/preview-domestic-studio/Skills.vue:1-12` 和上轮 `docs/reviews/DOMESTIC-STUDIO-SKILLS-R4-20261112.md`。
- **Stage 1：FAIL（已发现 MEDIUM 设计差异，未发现确定 HIGH）；Stage 2：未执行。** 设计稿一致性未达标且实际页面对照未由本 reviewer 完成，不能登记两阶段 PASS。主 Agent 要求立即交回，以下为当前已核查证据，不是全量审查完成的证明。
- 快照：审查开始及独立测试后执行 `python .codex/hooks/harness.py review-status`，最近一次 `currentId` 与送审 candidateId 一致，`approved` 为 `false`。报告撰写后核对文件时已观察到主 Agent 开始修改：`frontend/src/views/hengxin/admin/DomesticStudioBindings.vue` 的绑定行内边距由送审版本 `20px` 改为 `22px`，行号也发生变化；未对这一新版本做完整复审或重新固定候选。本报告仅对应上述原候选，不能覆盖后续代码。报告本身为普通 Markdown，不属于 harness 代码快照。本 reviewer 未修改产品代码。

## Stage 1 发现

### MEDIUM：Skills 页卡片结构及部分设计数值不匹配确认预览

`Design-Brief.md:3` 指定最终预览为视觉与交互基准。预览把「Skill 目录 / 工作台绑定」页签和两个页签内容放在同一张卡片内，见 `hengxin-smart-image/frontend/preview-domestic-studio/Skills.vue:4-12`；正式页的页签位于 `hengxin-smart-image/frontend/src/views/hengxin/admin/skills.vue:4-7`，目录和绑定分别在各自组件内再创建卡片，见 `frontend/src/views/overseas/admin/OverseasSkillCatalog.vue:2-3`、`frontend/src/views/hengxin/admin/DomesticStudioBindings.vue:2-3`。正式目录还在卡片内新增了「国内 Skill 目录」标题区，并将上传按钮放在该区；预览中上传按钮与搜索、状态筛选同属工具栏（`frontend/preview-domestic-studio/Skills.vue:7`）。这不是数据替换或移除预览标记所必需的变化。

可直接比较的数值也不同：预览绑定行上下内边距为 `22px`、搜索框宽 `300px`、状态筛选宽 `150px`（`frontend/preview-domestic-studio/skills.css:1`）；送审版本绑定行为 `20px`（当时 `frontend/src/views/hengxin/admin/DomesticStudioBindings.vue:43`），目录搜索为 `255px`、状态筛选为 `140px`（`frontend/src/views/overseas/admin/OverseasSkillCatalog.vue:10,78`）。主 Agent 已开始修改绑定行，现有代码已不同，见上方快照说明。本项是模板与 CSS 静态比较，未由本 reviewer 在相同视口打开实际页面做像素或交互对照；主 Agent 另告知已在隔离 mock 数据下查看页面，该口头信息不替代本 reviewer 的实测。

## 上轮 HIGH 复核及本阶段功能状态

1. **R4 未知暂存误删：所核查的恢复路径已移除按目录名清理。** `backend/app/overseas/management/skill_publication.py:47-55` 无 pending 时仅尝试首次空索引恢复；`skill_initialization.py:29-62,65-77` 校验可识别的空索引残留，并明确保留既有暂存。正常函数调用中仅清理本次 `mkdtemp` 创建的目录（`skill_objects.py:21-42,45-84`），不能据此推断异常退出留下的目录会回收。`backend/tests/test_skill_initialization_recovery.py:60-78,91-109,112-173` 以真实子进程退出检查首次初始化、再次中断及已安装目录的 release/package 暂存，另检查硬链接和未知数据保留；测试没有穷举所有文件系统故障及断电时序。
2. **R4 权限锁反序：所核查的国内路由及 PG 用例通过。** 共享发布路由在 install/delete 恢复前调用鉴权（`backend/app/overseas/management/skill_publisher.py:128-157`），国内 install/delete 自身在恢复之后再次调用 `authorize`（`backend/app/modules/domestic_studio/skill_publication.py:19-29,44-55,84-86`）；其他 transfer 入口在恢复前后均鉴权（`skill_publisher.py:75-126`）。恢复 pending 可提交事务释放锁（`skill_publication.py:47-77`）。`backend/tests/test_domestic_recovery_lock_pg.py:21-59,64-96` 用真实 PostgreSQL 连接覆盖 install/delete 等待权限锁时 admission 可获取，以及恢复提交后撤权导致 transfer 返回 403。定向测试独立运行 `16 passed`，没有穷举所有并发顺序。
3. **五个空绑定及 CAS：所测行为通过。** `backend/migrations/versions/0033_domestic_studio_bindings.py:11-26` 不预置绑定；`backend/app/modules/domestic_studio/bindings.py:30-60` 在 admission gate 下对全量 expected 比较并验证启用状态，`tests/test_domestic_studio_bindings_pg.py:102-112` 以 PG 测试陈旧写入。绑定保存期间禁用下拉及切回目录见 `frontend/src/views/hengxin/admin/DomesticStudioBindings.vue:6,32-38`、`frontend/src/views/hengxin/admin/skills.vue:4`。
4. **权限及撤权：所测行为通过。** 菜单只对超管可见（`frontend/src/router/modules/index.ts:13-19`）；API 依赖 `manage_system`（`backend/app/modules/domestic_studio/management_router.py:24-26`，`backend/app/modules/auth/permissions.py:5-18`），绑定与启停写入在事务内重新授权（`management_router.py:138-157`）。`backend/tests/test_domestic_admin_permissions_pg.py:74-115` 覆盖撤权先提交与写入先持锁两种顺序；未验真实部署身份链路。
5. **上传、校验、同名差异、ZIP、启停、删除：已有实现及自动测试证据，浏览器端到端未由本 reviewer 验证。** 国内 API 使用独立路由和 socket（`management_router.py:52-134`）；上传及更新差异 UI 为 `frontend/src/views/overseas/admin/SkillFolderUpload.vue:2-16,65-104`；国内下载限定 ZIP（`frontend/src/views/overseas/admin/OverseasSkillCatalog.vue:23`、`SkillFolderActions.vue:3,31-38`）。后端 `tests/test_domestic_skill_publisher.py:84-152,227-255`、前端 `tests/skill-folder-zip.test.ts` 和 `tests/skill-folders-components.test.ts` 在本轮所跑集合中通过；没有独立做真实浏览器文件夹上传和原生下载。
6. **引用与回收：基础接口和隔离测试通过，执行闭环未完成。** `backend/app/modules/domestic_studio/skill_references.py:15-32,35-56` 冻结/核对引用，`skill_publication.py:64-79,84-118` 在更新和删除时保护引用并规划回收；`tests/test_domestic_skill_publisher.py:84-162` 与 `tests/test_domestic_skill_references_pg.py:23-68` 覆盖已引用包保护、未知引用拒绝及 PG 锁。真实执行发送尚未接入该接口，会话删除后的引用清理与最终回收未实现（`docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:17-18`）。
7. **发布持久日志及提交失败：所测故障通过，未覆盖全部中断。** `backend/app/overseas/management/skill_publication.py:35-77,95-112` 根据 pending/audit 恢复指针并继续清理；`backend/tests/test_domestic_skill_publisher.py:190-225,239-270` 覆盖未提交、数据库提交失败、已提交后状态保存失败及清理重试。首次初始化和已安装目录的进程退出另见第 1 项；未模拟真实断电或所有系统调用故障。
8. **国内外隔离及漂移：局部代码符合，未完成全量扫描。** 国内目录/业务上下文限制见 `backend/app/modules/domestic_studio/installed_skills.py:16-36`，独立 transfer 根及禁用海外 maintenance 见 `skill_publisher.py:13-31`。国内界面隐藏海外平台分组并使用绑定列（`frontend/src/views/overseas/admin/OverseasSkillCatalog.vue:4,20-25,53-58`），未发现版本管理或在线编辑 UI；单文件读取接口服务 ZIP 下载（`backend/app/modules/domestic_studio/management_router.py:127-134`）。共享海外完整回归本 reviewer 本轮未完成，不能据此认定海外全链路通过。

## 独立验证原始结果

在 `hengxin-smart-image/backend` 使用 `.venv/Scripts/python.exe`，设置 `TEST_DOMESTIC_STUDIO_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:35439/hx_studio_test`。PG fixture 仅创建并删除随机 schema（`tests/test_domestic_studio_bindings_pg.py:17-41`）。先运行 `tests/test_domestic_recovery_lock_pg.py tests/test_skill_initialization_recovery.py`：

```text
16 passed, 2 warnings in 10.93s
```

随后运行上述两文件以及 `tests/test_domestic_admin_permissions_pg.py tests/test_domestic_installed_skills.py tests/test_domestic_skill_publisher.py tests/test_domestic_skill_references_pg.py tests/test_domestic_skill_state.py tests/test_domestic_skill_state_migration.py tests/test_domestic_studio_bindings.py tests/test_domestic_studio_bindings_pg.py tests/test_domestic_studio_management.py tests/test_domestic_studio_migration.py tests/test_domestic_studio_policy.py`：

```text
99 passed, 2 warnings in 44.68s
```

两条警告分别是 Starlette TestClient/httpx 和 anyio BlockingPortal 弃用提示。共享海外恢复、传输、故障和物理回收测试因主 Agent 要求立即交回而中断，未形成完整结果，不计为通过；主 Agent 另提供的 `53 passed` 为交接信息，非本 reviewer 独立结果。

前端运行 `pnpm exec tsx --test tests/domestic-studio-skills.test.ts tests/skill-folder-zip.test.ts tests/skill-folders-components.test.ts tests/skill-folders.test.ts tests/business-route-access.test.ts tests/roles-integration.test.ts`，原始汇总：

```text
ℹ tests 37
ℹ suites 0
ℹ pass 37
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 2032.9331
```

编译类型检查 `pnpm exec vue-tsc --noEmit` 退出码 0，原始输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
```

本轮没有执行 Vite 生产构建。Stage 2 代码质量、安全扫描和邻居页面实际视觉对照未执行；也未独立重跑 0033–0036 在 PG 的完整升级、生产文件权限或正式部署。五工作台、真实发送/执行、会话删除回收、成品库和部署仍属后续工作；用户确认的「源会话仅创建人可见、归档副本对所有国内成员可见」尚未实现，不计作本阶段通过。
