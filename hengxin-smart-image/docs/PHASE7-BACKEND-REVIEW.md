# Phase 7 Task 1–3 后端独立审查

日期：2026-09-09。依据根 `Product-Spec.md:92`（REQ-002）、`:135`（REQ-007）、`DEV-PLAN.md:246`、`docs/PHASE7-PLAN.md:5`，使用 code-review skill。仅审后端及部署接线；没有修改代码、启动或操作其他 agent 的容器。

**结论：Stage 1 功能覆盖通过；Stage 2 未通过，发现 2 个已复现 MEDIUM 缺陷。当前不建议将后端标记为最终验收完成。** 没有发现 HIGH 核心缺失或已证实安全漏洞。完整阶段的前端、真实 Linux/PG/MinIO/Worker 集成验收由主 Agent 汇合，未以本报告替代。

下文代码路径以 `hengxin-smart-image/` 为根。功能覆盖通过只表示各条已有对应实现及列明的本地证据，不能推导为所有并发/部署行为均通过。

## Stage 1：Spec Compliance

| Spec/计划条目 | 结论与实现证据 | 验证证据 |
|---|---|---|
| 模板创建、名称/功能/有序图片/备注 | 完整实现；`backend/app/modules/templates/service.py:73` 校验名称、壁纸/商品类型、1–20 张与 ready 文件；`:114` 新建版本，`:122` 按 slot 保存；`models.py:40` 限制 slot | `backend/tests/test_templates.py:20` 验证真实文件元信息覆盖伪造名称/URL、图片反转后旧版本不变；非法输入/21 张/不可用文件用例通过 |
| 搜索、分页、筛选、排序 | 完整实现；`templates/service.py:52` 按当前非删除版本查询，搜索转义、名称/图片数/时间排序及分页；`:60` 可用筛选 | `test_templates.py:105` 覆盖名称、图片数、页大小、类型、百分号搜索与空结果；时间排序代码存在，未单独证明相同时间边界 |
| 专用优先、未指定解析模块默认、无可用默认草稿 | 完整实现；`skills/service.py:12`；`templates/service.py:96` 保存解析；`:114` 冻结实际 ID 与绑定策略；`:28` 结合当前 Skill 状态返回可用性 | `test_templates_skills.py:23`、`:50`、`:63` 证明默认切换不改旧版本、重存解析新默认、无可用草稿、跨类型/不存在拒绝、显式不可用不回退 |
| 保存直接可用、停用 | 完整实现；`templates/service.py:41` 以 enabled 且 Skill available 判定，无审批状态；`:114` 保存 enabled | `test_templates_skills.py:77` 证明可用 Skill 下主动停用仍不可用；`:23` 证明 Skill 禁用使模板不可用而不改变冻结引用 |
| 四角色共享查看/编辑/逻辑删除，实际操作者审计 | 完整实现；`templates/router.py:13` shared_resources；`templates/service.py:129` 锁定逻辑删除；`backend/app/modules/files/deletions.py:10` 写 operator_id；`auth/permissions.py:5` 四角色集合 | `test_templates.py:49` 四角色跨 owner 编辑删除，owner 不变、删除操作者正确、历史和原文件仍在；未授权/停用身份用例通过 |
| 版本不可变、并发编辑冲突 | 完整实现；`templates/service.py:106` 使用 expectedVersion CAS；`:114` 只追加新版本；`templates/models.py:21` 版本唯一约束 | 本地旧引用/图片顺序/409 回归通过；`test_templates_concurrency.py:20` 有真实 PG 双事务用例，但本次因 TEST_DATABASE_URL 缺失跳过 |
| 仅超管管理 Skill；其他人只读可用目录 | 完整实现；`skills/router.py:22` manage_system；`:28` 只返回 available；`:41/:84/:89/:62` 上传/安装/启停/默认接口受 Admin 依赖保护 | `test_skills.py:69` 三种非超管上传、安装、启停、管理读取均 403；`auth/dependencies.py:19` 每请求重读数据库身份。长请求期间撤权没有原子性测试，不声称已证明 |
| 原 ZIP 与哈希、上传/安装中/可用/失败区分 | 完整实现；`skills/service.py:36` 保存私有对象及 SHA；`:64` 原子建立 Job/Outbox 并标 installing；`worker/skill_install.py:63` 完成状态 | `test_skills.py:37` 完整上传安装，目录在安装前为空；`:80` 依赖失败保留旧 available 版本。上传存储失败的同版本恢复缺陷见 S2-02 |
| 包格式、路径、链接、重复、特殊设备、CRC | 完整实现；`skills/package_validator.py:40` 逐条读取；`:48` 路径保护；`:58` 文件类型；`:70` CRC；`:85` YAML 必填与 manifest 校验 | `test_skills_packages.py:19/:28/:33/:44` 根/顶层目录、越界、反斜杠、设备、链接、大小写重复、压缩炸弹、CRC 与声明错配用例通过 |
| 20 MiB ZIP / 100 MiB 解压 / 1000 条 / 20 MiB 单项 / 比例 100 | 完整实现；`package_validator.py:13` 常量；`:42` 条数；`:63` 单项/总量/比例；`skills/multipart.py:15` 流式总请求上限 | 压缩比拒绝用例通过；其余数值边界代码逐条对照吻合，但现有用例没有逐项跨边界验证，列入测试边界 |
| 仅检查预装依赖，不执行脚本或联网安装 | 完整实现；`worker/skill_install.py:20` which/find_spec；拒绝点分 Python 模块防父模块导入；`:49` 仅写包文件 | `test_skills.py:80` 缺失可执行依赖导致失败；限定目录检查无 subprocess/eval/exec/shell=True 调用 |
| 通用作业 kind、类型路由、终态 | 完整实现；`backend/app/models.py:22` 新字段；`worker/tasks.py:39` 分派 test/skill_install/未知类型；`worker/leases.py:58` 终态并结束 outbox | `test_skills.py:37/:101/:152` 成功/取消/永久失败停止再执行或重派；取消用例直接写取消状态，不代表已实现用户取消 API（当前未要求） |
| 有效租约/心跳/旧 token 屏障/恢复 | 完整实现；`worker/leases.py:18/:30/:40` 认领续租；`worker/outbox.py:24` 排除终态和有效租约；`worker/skill_install.py:85` 发布前检查 token/status/lease | `test_skills.py:101` 有效租约不认领不重派、旧 token 续租失败；`:124` 偷换 token 后旧目录清理、新 owner 恢复；`:152` Redis 失败回滚 dispatch_count，恢复重派 |
| 独立 attempt 临时目录、原子发布、不覆盖旧版本 | 完整实现；`worker/skill_install.py:44` mkdtemp；`:55` UUID+token 目标 rename；`:85` 所有权失效清理当前 attempt | `test_skills.py:37` 安装目录可读、重复执行计数 1；`:124` 旧 owner 不能发布；进程硬杀后遗留磁盘目录未单测 |
| 迁移及接线 | 完整实现；`migrations/versions/0003_skills_jobs.py:17`、`0004_templates.py:17`；`migrations/env.py:6` 注册；`app/main.py:33` 路由；`core/config.py:14` 安装目录/租约；`infra/Dockerfile.backend:8` 非 root 可写目录；`infra/compose.yaml:93` 持久卷 | `test_templates_migration.py:14` 重复升级、外键、降级保留上游通过；compileall 通过。真实 PG 迁移、镜像构建和卷重启交由独立集成证据，本次未执行 |

未实现项：本次 Task 1–3 范围内未发现整项缺失。REQ-007 的用户配置、调用统计/执行监控属于后续 Phase；Phase 8 的真实生成提交与 Phase 14 的业务 Skill 效果不作为本轮缺陷。模板历史通过数据库保留，删除模板后历史 API 为 404；不等于物理删除历史数据，未来任务读取冻结版本需走内部引用。

Spec 漂移：未发现无来源业务功能。skill_audits 是默认/启停操作者审计，模块默认 API 与 skillBinding/expectedVersion 均在 `docs/PHASE7-PLAN.md:14` 有约定。沿用 Phase 6 文件/身份模块仅作依赖审阅，不将既有未提交内容全部认作 Phase 7 新增。

## Stage 2：Code Quality

### S2-01 / MEDIUM：锁定默认版本时返回过期 ORM 状态

位置：`backend/app/modules/skills/router.py:70`，`backend/app/modules/skills/service.py:26`。

`save_defaults` 先用 resolve_binding 将 available 版本载入 Session，再 get_version(lock=True)。另一事务在两步之间禁用并提交后，SQL 锁查询读到了新行，但 identity map 仍返回原对象，status 校验使用旧 available。结果是已禁用版本仍可被此次配置操作设为默认。模板后续会成为草稿；不会因此绕过 available 检查生成，但管理操作违反“默认必须可用”的校验。

独立内存数据库、双 Session 重现（未改项目代码）：先 resolve_binding，另一 Session 更新 disabled 并提交，再调用真实 get_version(lock=True)，另用 scalar column 查询数据库值。原始输出：

```text
database_status= disabled locked_orm_status= available default_validation_accepts= True
```

这证明 ORM 缓存问题；SQLite 不提供 PG 行锁，因此仍须补真实 PG 的阻塞/竞争回归。SQLAlchemy 官方明确说明已在 identity map 中的对象不会默认被新查询覆盖，需要 [populate_existing](https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#populate-existing)。建议锁查询强制刷新，或直接用一次锁查询加载并验证版本/类型。

### S2-02 / MEDIUM：对象写入失败永久占用同名版本，原包不能重传恢复

位置：`backend/app/modules/skills/service.py:46`（先提交 failed 版本），`:54`（put），`:51`（重复唯一键返回 409），`:64`（安装重试只读旧对象）。

MinIO 在写任何字节前失败时，上传返回 503，但 (skill_id, version) 已永久占位。恢复存储后原 ZIP 以原版本重传会 409；点击安装也只能反复读取不存在的 object_key。管理端没有删除或补传入口，必须无理由升级版本才能恢复该包。

使用真实 service、内存数据库、写前失败存储桩复现，原始输出：

```text
upload_attempt= 1 http= 503
upload_attempt= 2 http= 409
reserved_version= 1.0.0 status= failed object_written=False
```

建议区分“上传未完成”和“已上传但安装失败”，仅前者允许受控幂等重传，验证同包 checksum，并保留已成功上传/安装版本不可变；补写前失败、写后响应失败及同版本不同内容的故障测试。

### 质量、安全与测试边界

- 文件大小通过：本次 templates/skills/worker 新实现文件最长 `templates/service.py:1` 为 139 行，均未超过 300 行；数据模型有 Mapped 类型。服务函数大量参数/返回值未注解，例如 `skills/service.py:36`、`templates/service.py:93`；属低优先级可维护性建议，不阻止核心功能。
- 安全扫描在 templates/skills/worker 范围未命中 eval/exec/shell=True/硬编码 API Key。SQL 使用 ORM 参数；ZIP 路径不使用用户绝对路径；依赖检查不执行包文件。`storage/minio_store.py:21` 拒绝匿名桶策略。结论限本轮代码和已列测试，不宣称全面安全认证。
- 真实测试边界：`tests/files_helpers.py:64` 使用 SQLite StaticPool；`test_skills.py:101/:124` 人工更新 token/状态。它们证明状态屏障，不能证明真实多 Worker 竞争、持续心跳和进程硬杀恢复。生产 Compose `infra/compose.yaml:94` concurrency=1，也不能作为多 Worker 并发证据。
- ZIP 测试未分别触发本体/单项/总量/1000 条数边界；安装目录磁盘故障、运行中取消、授权在长上传中变化均缺独立回归。不能把尚未执行验证标成通过。
- 新后端无可直接比对的视觉页面；邻居渲染与 UI 一致性由前端最终审查负责，本次标“不适用”，未执行浏览器视觉对比。

## 本次执行证据

工作目录 `hengxin-smart-image/backend`；显式 `.venv/Scripts/python.exe -m pytest -q`，退出码 0，原始输出：

```text
................................................ssss.................... [ 69%]
..................s.............                                         [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
99 passed, 5 skipped, 2 warnings in 5.37s
```

`.venv/Scripts/python.exe -m compileall -q app migrations`，退出码 0，原始标准输出为空（`-q`）。5 个跳过分别为 `test_queue_integration.py:26` 的 4 个真实 PG 用例及 `test_templates_concurrency.py:23` 的 1 个 PG CAS 用例。本轮没有复跑其他 agent 的 Compose；`infra/verify_phase7.py:116` 之后的真实安装/迁移/重启/权限脚本已读，但没有把脚本存在当作执行成功。

修复路由：两项 Stage 2 缺陷交主 Agent 通过 bug-fixer 修复，补相应用例后从 Stage 1 重审，并合并真实集成报告。
