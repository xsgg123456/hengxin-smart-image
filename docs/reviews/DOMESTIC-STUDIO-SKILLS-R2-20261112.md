# 国内 Skills 管理独立复审 R2 · 2026-11-12

- 送审 candidateId：`b4db6786bd6478359d56df9b5e600305d894fd55969e41dfa6f70e514468df9b`。范围为国内 Skills 管理、五入口绑定、文件包上传更新/删除、引用保护与恢复、0033–0036 迁移、共享海外管理代码及相关前端/测试。工作台、执行器、会话删除及其最终回收闭环不在本阶段完成范围。
- 基准：`Product-Spec.md:3-11`、`Design-Brief.md:1-3`、`DEV-PLAN.md:3-10`、`docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:13-19`、确认预览 `frontend/preview-domestic-studio/Skills.vue:3-11`；审查遵循 `.agents/skills/code-review/SKILL.md` 和 `docs/HARNESS-REVIEW.md`。
- **Stage 1：FAIL；Stage 2：未执行。** 发现权限撤销后的越权写入；本报告不能登记两阶段 PASS。
- 快照变化：审查开始时 `review-status` 的 `currentId` 等于送审 candidateId。期间主 Agent 启动隔离 Vite 时自动改写了 `frontend/src/types/import/components.d.ts`，`currentId` 一度变成 `5ba1fdedd4c7f431584fef1f97a1d3a18f6df9470b8ed014ea195b83ab4d48f4`；经主 Agent 仅恢复该生成文件后，本 reviewer 再次查询得到原 `b4db…`。该报告只针对原候选，不覆盖之后的修复。报告本身是普通 Markdown，不属于 harness 代码快照。

## Stage 1 阻断问题

### HIGH：撤销超级管理员权限已提交后，等待中的绑定和启停请求仍能写入

`Product-Spec.md:5,9` 只允许超级管理员操作。绑定 `backend/app/modules/domestic_studio/management_router.py:150-155` 和启停 `management_router.py:137-142` 只在依赖阶段通过 `require_permission` 读取一次角色，然后等待 `bindings.py:17-27` 的 execution gate；得到 gate 之后没有在写事务内刷新操作者权限。`backend/app/modules/auth/permissions.py:13-23` 只检查传入对象，`backend/app/modules/auth/dependencies.py:23-42` 的读不锁用户行。对照国内成员修改，`backend/app/modules/auth/management_router.py:90-92,110-111,126-127` 先取得 `member_policy.py:11-21` 的 permission advisory lock 并复核操作者，再修改并提交。国内发布器另有 `skill_publication.py:18-25` 的用户行锁及刷新；该保护没有用于直写绑定/启停。

**独立 PostgreSQL 复现，绑定和启停均实际发生：** 使用主 Agent 指定的 `127.0.0.1:35439/hx_studio_test`，每次新建并最终删除随机 schema；真实执行 FastAPI 路由、`get_current_user`、`require_permission`、`lock_admission` 及数据库事务。仅覆盖登录解析得到测试 UUID、测试数据库 session 与不访问文件系统的已启用目录 fixture；没有覆盖权限依赖。一个连接先持有 execution gate，请求线程经真实身份和权限依赖后在 gate 等待，另一连接按成员写入惯例先调用 `lock_permissions`，将用户从 `super_admin` 改为 `designer` 并提交；随后释放 gate。核心顺序如下，两次分别请求 PUT 绑定和 PATCH 停用：

```python
lock_admission(blocker)  # 连接 1 持有 execution gate
future = pool.submit(client.put, '/api/v1/management/domestic-studio/bindings',
    json={'bindings': empty | {'camera': skill_id}, 'expected': empty},
    headers={'X-HX-Request': '1'})
# 第二轮改为 client.patch(.../skills/{skill_id}/availability,
#                       json={'enabled': False, 'version': 1}, headers=...)
assert ready.wait(5)  # get_catalog fixture 被调用，权限依赖已经通过
with Session(engine) as revoker:
    lock_permissions(revoker)
    revoker.get(UserRecord, actor_id).role = 'designer'
    revoker.commit()  # 撤权先于 gate 释放完成
blocker.commit()
response = future.result(timeout=10)
```

原始关键输出：

```text
binding revocation committed before gate release; response_status: 200 database_role: designer result: 02a3d467-f780-4975-93b2-a64cb60d50ad
availability revocation committed before gate release; response_status: 200 database_role: designer result: False
```

第一个 `result` 是实际写入 camera 的 Skill UUID；第二个 `False` 是写入后的启用状态。测试目录为隔离 fixture，不证明真实生产目录。应在同一写事务内与成员权限变更按一致的锁顺序同步并重新检查当前操作者；修复后须用真实 PG 覆盖撤权先提交与写入先完成两种顺序，避免只刷新 ORM 对象却未串行化。

### MEDIUM：保存绑定进行中仍可修改其他下拉框，成功响应会清空该草稿

`frontend/src/views/hengxin/admin/DomesticStudioBindings.vue:6` 没有在 `saving` 时禁用下拉框；`:32-36` 在发请求前复制草稿，但响应后无条件用服务端快照覆盖整个 `draft` 并提示成功。用户点击保存 camera 后、首个请求未返回时再选择 case，该次选择不在提交快照中，返回时却被清除。这是本机草稿丢失，不是两个管理员之间已提交绑定的覆盖。

独立运行真实 Vue SFC 的组件 harness：延迟 `setBindings` 响应，先选 camera 并点击保存，再在请求等待期间选 case，最后返回首次提交快照。原始输出：

```text
save_pending: second_selector.disabled = undefined
save_pending: second_selector.modelValue = a
response_received: second_selector.modelValue = null ; submitted.case = null
```

现有 `frontend/tests/domestic-studio-skills.test.ts:39-55,62-74` 覆盖正常保存与服务端 409，未覆盖请求中继续编辑。

### MEDIUM：目录刷新未刷新绑定标签

已确认预览将每个 Skill 的绑定工作台作为目录信息（`frontend/preview-domestic-studio/Skills.vue:9`）。正式目录绑定来自父组件 `frontend/src/views/hengxin/admin/skills.vue:18-29`，只在挂载和切回目录页时请求；目录的“刷新 Skill”在 `frontend/src/views/overseas/admin/OverseasSkillCatalog.vue:3` 触发，`OverseasLiveSkills.vue:2,25-28` 仅刷新 Skill 列表，不通知父组件刷新绑定。若另一管理员同时修改绑定，留在目录页的管理员点击刷新后仍会看到旧绑定或“未绑定”；后端保护仍会拒绝非法停用/删除，但展示不是最新事实。本项为代码路径对照，未单独进行双浏览器交互复验。

## Stage 1 逐项核对

- **超级管理员权限：FAIL。** 菜单仅对 `super_admin`（`frontend/src/router/modules/index.ts:13-19`），后端入口依赖 `manage_system`（`management_router.py:23-26`），非管理员和未登录拒绝由 `backend/tests/test_domestic_studio_management.py:60-76,142-149` 覆盖；撤权与写事务竞态见 HIGH，不能判通过。
- **五入口绑定及禁止静默覆盖其他管理员：后端修复已复验，前端草稿仍有缺陷。** 请求必须携带全量 `expected`（`management_router.py:31-43,150-155`）；`bindings.py:36-44` 在 gate 内读当前值后比较，冲突返回 409；`frontend/src/api/hengxin/domestic-studio-skills.ts:26-27` 与 `DomesticStudioBindings.vue:25-37` 传入读取时快照。独立执行的 PG 测试 `backend/tests/test_domestic_studio_bindings_pg.py:102-112` 覆盖两连接陈旧草稿；另见上述同一浏览器保存期间草稿丢失。
- **初始无预置、绑定启用 Skill、绑定中的禁停/禁删：代码与所跑测试覆盖。** `0033_domestic_studio_bindings.py:11-26` 只建表，`bindings.py:30-33,45-60,65-71` 验证并保护绑定；`skill_state.py:28-49` 停用前检查；`skill_publication.py:80-102` 删除前检查。`test_domestic_studio_management.py:44-57,86-94` 和 `test_domestic_skill_publisher.py:81-117` 覆盖正常与拒绝路径；权限撤销缺陷仍阻断该管理阶段。
- **完整目录上传、校验、同名差异确认、ZIP：实现接入且相关隔离测试通过。** `management_router.py:76-118,121-134` 接国内 socket 和目录下载；`OverseasLiveSkills.vue:2-3` 复用上传组件，`SkillFolderActions.vue:18-21,31-38` 国内固定 ZIP；`test_domestic_skill_publisher.py:57-73,81-113` 验证上传、同名更新；`frontend/tests/skill-folder-zip.test.ts` 独立运行覆盖 ZIP 解压与字节/空目录。实际浏览器多层目录上传与原生下载未由本 reviewer 验证。
- **引用保护及无引用删除：相应基础行为已复验，不等于后续执行闭环完成。** `models.py:30-36` 和 `0036_domestic_skill_references.py:11-24` 按 Job 保存引用；`skill_references.py:15-32,35-56` 锁内冻结、缺引用拒绝清理、核对 manifest/包、识别非终态；`skill_publication.py:60-64,95-107` 更新/删除时保留引用的对象、运行中拒绝删除。`test_domestic_skill_publisher.py:99-148,151-162` 验证已引用旧包可读、无引用包净减少及未知引用拒绝；`test_domestic_skill_references_pg.py:23-68` 使用独立 PG 连接验证 gate 和运行任务阻止删除。原上轮“全部旧包永久保留”在以上受测路径已改善。测试于 Windows，未实测 Linux 文件系统块分配和服务账号权限。
- **文件与 DB 发布恢复：部分已验证，不能视为全故障穷举。** `backend/app/overseas/management/skill_publication.py:35-73,91-109` 以 pending 日志和 audit 选择恢复指针、重试清理；`installed_catalog.py:138-156` 在 pending 时阻止目录读取。国内指定自身 audit 和 gate（`domestic_studio/skill_publication.py:28-37,72-75,110-113`）。`test_domestic_skill_publisher.py:177-211,226-270` 覆盖模拟未提交、提交失败、状态持久化失败和提交后的清理重试；没有独立执行真实进程掉电和所有崩溃边界。
- **国内外隔离及共享海外行为：有代码边界和局部回归，生产配置未验。** `installed_skills.py:16-36` 限定国内业务上下文和受保护生产根目录；`management_router.py:52-73` 使用国内目录及国内 socket；`skill_publisher.py:13-32` 单独 transfer root 并关闭海外 maintenance。共享默认参数见 `overseas/management/skill_publication.py:47,76,82,91`、`skill_publisher.py:21,153-157`；本次独立运行相关海外恢复/传输及前端组件回归，未跑海外完整生产链路，也未检查真实部署目录的属主、挂载和套接字权限。
- **不展示版本管理/在线编辑器：范围内代码对照符合。** 国内管理页为目录/绑定两页签（`frontend/src/views/hengxin/admin/skills.vue:2-7`）；`OverseasSkillCatalog.vue:4,20-25,52-58` 国内隐藏平台分组并显示绑定入口。目录行内单文件读取 API（`management_router.py:131-134`）为完整 ZIP 下载取文件所需，未发现与其对应的在线编辑 UI；未作全仓库漂移穷举。
- **后续功能：未完成，不能验收为通过。** `docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:15-18` 明确执行器尚未接入，未来发送须在同一事务调用 `skill_references.freeze_and_pin` 并持久化快照；会话删除后清理引用并触发回收也未完成。本次未验证真实发送防绕过、已运行请求历史冻结、五工作台、会话、成品库或最终回收闭环。

## 本 reviewer 独立执行的验证

- 后端：用指定临时 PG 数据库运行国内绑定/引用 PG、管理、发布、状态、安装、策略、迁移单测及海外发布恢复/传输测试；命令包含 `tests/test_domestic_studio_bindings_pg.py tests/test_domestic_skill_references_pg.py tests/test_domestic_studio_bindings.py tests/test_domestic_studio_management.py tests/test_domestic_skill_publisher.py tests/test_domestic_skill_state.py tests/test_domestic_installed_skills.py tests/test_domestic_studio_policy.py tests/test_domestic_studio_migration.py tests/test_domestic_skill_state_migration.py tests/test_skill_publisher_recovery.py tests/test_overseas_skill_transfers.py tests/test_overseas_skill_transfers_failures.py`。原始结果末尾：`108 passed, 2 warnings in 70.17s (0:01:10)`；两项为 FastAPI/Starlette 测试客户端弃用警告。PG 测试通过随机 schema 隔离；没有访问生产。
- 前端：`pnpm exec tsx --test tests/domestic-studio-skills.test.ts tests/skill-folder-zip.test.ts tests/skill-folders-components.test.ts tests/skill-folders.test.ts tests/business-route-access.test.ts tests/roles-integration.test.ts`，原始汇总：`tests 35`、`pass 35`、`fail 0`、`skipped 0`。
- 编译检查实际命令 `pnpm exec vue-tsc --noEmit`，退出码 0，原始输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
```

类型检查执行期间，主 Agent 的隔离 Vite 可能临时改写过上述生成声明文件；不能把这一次的结果作为对最终恢复快照的严格编译证明，应在恢复后重跑。

Stage 1 已有 HIGH，遵守 skill 停止规则，未执行 Stage 2 代码质量、安全扫描、真实页面与邻居页面视觉对比。0033–0036 临时 PG 全量升级是主 Agent 转交结果，本 reviewer 本次仅独立运行上述迁移单测及 PG 连接测试，未独立重跑 Alembic 完整升级或验证正式回退/部署方案。
