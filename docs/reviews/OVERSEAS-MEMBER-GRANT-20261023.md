# 海外指定成员完整授权：独立代码审查

- 日期：2026-10-23。
- candidateId：`2140ac2e1517102388899757131c61a3426b39100353f7158b218208e10a9978`。
- Stage 1：**PASS（部署前代码范围）**。
- Stage 2：**PASS（部署前代码范围）**。
- 范围：四个后端业务文件、`tests/test_overseas_full_access_grant.py`、两份 `scripts/release/overseas-member-grant*.py`；源要求为 `Product-Spec.md:1318` 和 `docs/OVERSEAS-MEMBER-GRANT-20261023.md:3`。
- 初始交接候选为 a2600e8f…；主 Agent 随后明确更新到上述候选，修正本地镜像引用、COPY 权限及构建上下文。审查读取的是更新后源码；独立 `review-status` 开始及结束均为上述候选。旧候选结论不被沿用。
- 本报告批准代码审查范围，不证明生产已部署。reviewer 未操作生产、未修改实现、未提交、未登记批准凭据。

## Stage 1：Spec Compliance

以下后端相对路径统一以 `hengxin-smart-image/backend/` 为根。

| 要求 | 结论与证据 |
| --- | --- |
| 撤回配置页方案，正式前端不新增页面 | 完整实现。`git status --short` 及候选 changedFiles 均无前端改动；既有 `hengxin-smart-image/frontend/src/views/overseas/OverseasPortal.vue:43` 按 capabilities 生成菜单，`:5` 仍显示真实 roles。本轮不存在需要比对的新页面、文案或设计稿。 |
| 仅唯一成员 ID 追加授权，同名及其他主管不扩权 | 完整实现。`app/overseas/config.py:30` 使用 UUID 集合，`permissions.py:54` 按成员 ID 匹配；`tests/test_overseas_full_access_grant.py:21` 使用同名、同角色不同 UUID 验证不扩权，`:128` 验证 UUID 环境配置与非法输入拒绝。 |
| 全部 9 项权限、所有业务数据及特殊运营路径 | 完整实现。`permissions.py:15` 列出 9 项，`:30` 完整管理员策略覆盖全部 scope，`:60` 统一构建 principal；`tasks/queries.py:60`、`:79` 和 `materials/service.py:22` 使用该 principal。`tasks/requirements.py:17` 特殊非本人修改路径同样消费它。专项测试 `:34` 遍历所有能力，`:107` 实际 HTTP 测试非本人图需退回后重提。 |
| 保持 design_manager 实际角色及真实操作者 | 完整实现。`auth/router.py:27` 将真实 roles 和策略 capabilities 分开输出，`permissions.py:64` 保留原成员 ID，没有角色写入。测试 `:28`、`:40`、`:46` 同时验证接口角色、数据库角色及新任务 createdBy；`:101` 验证 Skill 审计的真实 actor。 |
| 启用、正式成员、唯一合法角色优先，禁用立即失效 | 完整实现。`permissions.py:62` 先调用 `auth/dependencies.py:13` 校验；旧会话每请求在 `auth/dependencies.py:33` 重新校验。测试 `:49` 覆盖 disabled、pending、legacy_unconfirmed、无角色后的旧会话拒绝；既有单角色测试纳入此次 128 项复跑。 |
| 撤销绑定恢复原角色，张帅原权保留 | 完整实现。`permissions.py:63` 无绑定时退回真实角色；`management/skills.py:15` 保留原 owner 分支。测试 `:70` 验证旧会话撤销及原 owner 继续具备 Skill 开关。配置由进程加载，实际撤销需修改环境并重建 API，不能只修改宿主环境文件后声称立即生效。 |
| Skill 开关和原配置不改变 | 完整实现。`management/skills.py:14` 仅放宽明确授权成员；`:44` 写操作仍先 `lock_actor(..., 'skills.manage')`，`:58` 保留版本控制与审计。发布脚本不调用 Skill 更新接口；probe `:42` 保存 Skill enabled/version，发布脚本 `:144` 比较。 |
| 任务状态、并发和最后管理员保护保持 | 完整实现。未改变既有 mutation/锁路径；`tasks/service.py:9` 刷新 actor 并重检权限，`members/service.py:65` 与 `:99` 按真实超级管理员计数。测试 `:102` 验证最后管理员降权返回 409，`:124` 验证非法重提状态返回 409。 |
| 国内权限不变 | 完整实现。业务变更全在 overseas 包；`app/core/config.py:101` 及 `:108` 按上下文选择配置，新增键仅在 OverseasSettings 内。发布 overlay `scripts/release/overseas-member-grant.py:99` 仅覆盖海外 API。 |
| 审计、API 独立部署、保护原配置/其他进程 | 发布实现匹配。probe `:68` 写指定 actor/target 的授权审计；发布脚本 `:68` 检查源 hash，`:99`–`:105` 核对 Compose 仅 image/新增环境键差异，`:125` 备份数据库并检查归档目录，`:133` 仅 `--no-deps ... api`，`:142`–`:148` 核对镜像、成员/Skill/迁移和其他容器状态后恢复 gate。保留 `before.private.json` 与本地基础镜像 tag，版本关联在 `prepared.private.json`/DEPLOY_STARTED。 |

部分实现或未实现的代码要求：无。Spec 漂移：无新增页面、接口、业务表或角色，使用明确获准的服务端成员绑定。

生产操作验收仍待主 Agent 完成：真实 HTTP API 读取双方权限与资源、真实角色核对、授权审计、运行状态/恢复 gate、明确记录回退和撤销操作方法。`scripts/release/overseas-member-grant-probe.py:33` 是进程内调用 describe，不能把它表述为已完成真实 HTTP 验证。此为尚未发布阶段的交付步骤，不作为已完成事实。

## Stage 2：Code Quality

- 质量：PASS。四个业务文件均低于 300 行；新增测试 139 行、发布脚本 161 行、probe 78 行。授权判断集中于 `permissions.py:54`/`:60`，未复制权限矩阵；UUID 类型配置明确；发布 subprocess 使用参数列表且设置超时（发布脚本 `:19`）。未发现需修复的 HIGH/MEDIUM 问题。
- 安全：PASS。指定文件扫描 eval、HTML 注入、前端密钥变量、常见密钥前缀无匹配；源码不含生产账号 UUID 或密钥。发布脚本 `:23` 写私有文件为 0600，`:158`–`:159` 限定 root 私有工作目录，`:89` 构建上下文仅放行源码，`:92` 测试容器 network none 且没有生产 env/挂载。SQL 使用 ORM 条件；probe 唯一显式 SQL 为固定只读事务及固定迁移查询（probe `:28`、`:47`）。
- 测试真实性：PASS。独立复跑 128 项通过；新增测试通过真实 TestClient 路由访问、成员停用/撤销后的既有会话、实际数据库角色/审计记录及状态拒绝验证行为，未把策略函数成功当作所有 HTTP 操作已遍历。SQLite 测试不证明 PostgreSQL 并发锁本身；既有锁代码未修改（`members/service.py:18`）。
- 视觉对比：不适用。候选没有 UI 变更，新权限沿用既有菜单。未打开浏览器，不声明已完成生产页面视觉验收。依据 `OverseasPortal.vue:34`、`:43` 的动态权限和 `:5` 的真实角色展示核对兼容性。
- 发布边界：脚本为一次性 root 运维流程，使用普通 `python` 执行，不能使用禁用 assert 的 `python -O`。`gate.paused` 阻止新认领（`execution/claims.py:79`），不拒绝持久入队（`execution/queue.py:35`）；空闲检查后新 queued 作业可以出现，API 更换不重启 worker，保留队列/数据库。脚本 `:120` 关于 probe 锁的注释不精确：pause 事务持有 gate 锁，probe 自身仅普通读取，不构成同一事务。属于 LOW 文档表述，不改变本次代码审查结论。

## 独立验证原始输出

在 `hengxin-smart-image/backend` 执行：

```text
.venv/Scripts/python.exe -m pytest tests/test_overseas_full_access_grant.py tests/test_overseas_permissions.py tests/test_overseas_single_role.py tests/test_overseas_skill_availability.py tests/test_overseas_members.py tests/test_overseas_configuration.py -q
........................................................................ [ 56%]
........................................................                 [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
128 passed, 2 warnings in 22.84s
```

在仓库根目录编译六个变更/新增 Python 模块：

```text
python -m py_compile scripts/release/overseas-member-grant.py scripts/release/overseas-member-grant-probe.py hengxin-smart-image/backend/app/overseas/config.py hengxin-smart-image/backend/app/overseas/permissions.py hengxin-smart-image/backend/app/overseas/auth/router.py hengxin-smart-image/backend/app/overseas/management/skills.py
stdout: [空]
stderr: [空]
exit_code: 0
```

主 Agent 提供但 reviewer 未独立运行的证据：实际待发布 Linux 镜像专项 128 passed；随后收到广泛 Linux 海外回归完成结果 `548 passed, 67 skipped, 2 warnings in 215s`，命令为 `docker run --rm --network=none --entrypoint sh <已准备镜像> -c 'python -m pytest -q tests/test_overseas*.py'`。Windows 广泛回归非全通过（522 passed/103 skipped/8 failed），不得以本报告掩盖其平台限制。生产发布证据由主 Agent 补录，应区分本人已登录页面只读冒烟、目标账号服务/数据库验证、隔离 HTTP 测试，不得声称完成未经执行的目标本人登录测试。不改变源码时无需重新固定代码候选；代码若变化必须重新 prepare 和复核。
