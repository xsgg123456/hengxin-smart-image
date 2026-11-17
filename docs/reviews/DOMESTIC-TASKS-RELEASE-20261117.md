# 国内 Task 0043→0044 专项发布审查

- candidateId：`c23cdb297170bc6348baf72114f1887bd1556417ff23e46c49aaeefc6f2d80ec`。
- 审查日期：2026-11-17。使用 `.agents/skills/code-review/SKILL.md`，并读取 release-builder、项目生产规则、专项维护合同及最新内网发布记录。
- 范围：`scripts/release/intranet/` 本次 4 个既有文件修改、5 个 `domestic_tasks_*.py`、3 个专项测试；0044 迁移与 `auth/dingtalk.py` 固定哈希例外；为核实调用链只读检查既有 engine、scope、锁、备份、台账和清理模块。产品前后端由另一 reviewer 负责。
- 实际发布基线来自交接材料：国内 `c79924625230275bad65fa778020d5b4a3b272e0`/0043，海外 `3b38a2c`/overseas_0026，共享 `2bc8acc7`，工具 `31249944c5fea417`。本 reviewer 未连接生产，未安装工具、迁移生产或修改生产数据。
- 结果：**Stage 1 FAIL：2 项 HIGH。Stage 2 未执行。不能登记两阶段 PASS。**
- 审查期间没有修改代码。结束前 `review-status` 的 `currentId` 仍等于上述 candidateId；报告只适用于此快照，后续修复必须重新固定快照并复审。

## Stage 1：需求符合性

### HIGH-1：迁移前恢复绕过强制重建，容器永久保留 restart=no

需求：维护合同第 3 项及恢复段要求迁移前失败恢复原国内代码、重启策略及接入（`docs/DOMESTIC-TASKS-MAINTENANCE-20261117.md:9`、`:21`）。

实际：`domestic_tasks_engine.freeze()` 把全部国内应用容器改为 `restart=no`，只保存原策略，没有独立恢复策略步骤（`scripts/release/intranet/domestic_tasks_engine.py:16`、`:35`）。`context()` 试图通过替换 `u.app_command` 为 `--force-recreate` 恢复（同文件 `:99`），但实际 `Actions.start_apps()` 调用 `self.app_command`，进入原始 compose 适配器，绕过此替换（`scripts/release/intranet/scope_actions.py:72`、`:82`、`:85`）。迁移前恢复使用相同 compose 内容，普通 `up` 不重建容器，故恢复后仍为 `restart=no`。现有快照/健康检查不比较 RestartPolicy，能够登记恢复成功；之后主机/容器重启时服务不能按原策略恢复。

证据一：直接调用真实 `scope_engine.context → domestic_tasks_engine.context → u.start_apps`，仅替换外部执行及健康探针，记录到后端和 UI 两次调用都走 ordinary，无 forced 调用：

```text
scoped start dispatch: [('ordinary', ('up', ('domestic-api', 'domestic-api-image-worker', 'domestic-api-image-outbox', 'domestic-image-variants', 'domestic-outbox', 'domestic-skill-publisher')), {'candidate': False}), ('ordinary', ('up', ('domestic-ui',)), {'candidate': False})]
```

证据二：真实本地 Docker/Compose 独立项目 `hx-task-review-restarts-20261117`，已有 redis:7 镜像、无生产挂载/数据库；执行初次 up、update restart=no、stop、普通 up，再 force-recreate：

```text
before {'id': 'b0a4cb7358c8', 'restart': 'unless-stopped', 'running': True}
after ordinary up {'id': 'b0a4cb7358c8', 'restart': 'no', 'running': True}
after forced recreate {'id': 'd809e485dbe8', 'restart': 'unless-stopped', 'running': True}
cleanup
```

该项目容器和网络已清理，按精确项目标签再次查询均为空。此验证证明 Compose 行为及实际调用分派，不冒称跑过整套生产恢复。

修复验收：让实际 scope 启动链调用专项恢复逻辑，或显式核实并恢复原策略；增加无 schema 提交的备份/迁移失败、部分 freeze 中断、恢复中断重入用例，最终检查所有国内容器的 ID/挂载/RestartPolicy。需要真实 Docker 用例，不能继续 mock `start_apps` 后仅断言源码恢复。

### HIGH-2：成功核验忽略海外/共享配置漂移

需求：仅国内切换，其他组保持不变；主 Agent 明确要求检查其他组配置变化。维护合同第 4 项与内网独立发布规则要求仅目标组变化（`docs/DOMESTIC-TASKS-MAINTENANCE-20261117.md:10`）。

实际：`Upgrade.verify_after()` 比较 runtime、非目标 group、fallback、进程/容器 census，却没有比较 `before['configs']` 与 `after['configs']`（`scripts/release/intranet/domestic_tasks_release.py:90`）。`scope_snapshot.group()` 不包含配置，`unchanged_other()` 只比较进程/容器身份（`scripts/release/intranet/scope_snapshot.py:116`、`:138`）。scope 中的 `engine._check()` 只覆盖本次国内原生配置及 compose，不能代替全量配置核验。全量 capture 明明采集了配置哈希（同文件 `:110`），但这些哈希可直接被纳入成功台账（`domestic_tasks_release.py:114` 至 `:125`）。

隔离复现：构造合法的 before/after scope 快照，仅按预期切换国内源码和 schema，同时把 `after.configs['/etc/hengxin-lan/hengxin-overseas-worker.env']` 改成未授权摘要；海外源码、镜像、schema、fallback、PID/容器身份全部保持，真实 `verify_after()` 返回成功。外部 census 读取用固定值隔离，比较函数未 mock。

```text
verify_after accepted unauthorized overseas config change
```

这会把维护期间发生的非目标组落盘配置变化错误认定为已验证状态；下一次海外服务启动可能加载未经本次授权的配置。

修复验收：建立精确允许变更路径/摘要清单，只允许国内候选 compose 及国内 source drop-in 的已准备摘要变化；其余配置路径集合与内容摘要必须完全一致。测试海外/shared env、unit/drop-in、nginx 配置修改/新增/删除均拒绝，拒绝时不得推进成功台账。

### 逐项覆盖清单

| 合同条目/边界 | 结论与代码证据 | 验证限制 |
|---|---|---|
| 1. 固定国内基线、单入口、full、唯一新增迁移 | 实现路径匹配。`domestic_tasks_release.py:53`、`:197`；`domestic_tasks_policy.py:7`、`:19`；`release_cli.py:23` 保留主机/root/全局锁约束。 | 未安装到生产路径。 |
| 普通发布仍拒绝 schema/依赖变化 | 实现路径匹配。`scope_changes.py:154` 调普通 compatible；专项仅在临时 manifest 视图移除固定哈希0044，`domestic_tasks_policy.py:31`。 | 专项 policy 测试覆盖摘要/依赖/其它迁移拒绝；实际完整候选包尚未构建。 |
| 共同代码例外只允许两个国内返回路径 | 匹配。`auth/dingtalk.py:24` 仅增加 task-center/workspace-sessions；`domestic_tasks_policy.py:11`、`:15` 固定路径及前后摘要；`scope_changes.py:170` 仍拒绝未知归属和其他共享变更。 | `test_domestic_tasks_policy.py:50` 使用普通检查 stub，尚需真实完整候选包 ownership 拒绝用例。 |
| LF/CRLF 与固定 Git 打包 | 匹配。0044 原始及 LF SHA 均为 `c6a9fb63e97f4b9460ebc37667a4116ae72bd380574f7baa0770093534bf0d01`；dingtalk 工作区 CRLF 原始 SHA 不同，LF SHA 为固定 `ef7cbbbffd754d9e552117e15487a896b088927261847524edf8ca1e9b6a29a1`。`package_release.py:72` 使用固定 Git archive，而非工作区。 | 正式打包后仍需验证归档清单实际哈希。 |
| 2. pending、持久 marker、准备中断可恢复 | 实现路径匹配。`domestic_tasks_release.py:66`、`:136`；`domestic_tasks_marker.py:19`；`release_cli.py:40`、`full_cleanup.py:14` 阻断普通命令/清理。`test_domestic_tasks_state.py:49`、`:78`、`:88` 覆盖恢复台账中断和准备窗口。 | 专项成功 ledger-writing 的完整故障注入未见于新增测试。 |
| 3. 关闭仅国内入口、两类队列排空、禁止强杀 | 实现路径匹配。`scope_engine.py:138` 绑定国内 APPS/ENTRIES；`scopes.py:20` 定义国内两类 worker；`scope_actions.py:27` 复用 drain；既有 `unify_release.py:107` 使用 stop timeout=-1，`:444` 禁止 native SIGKILL。共享 release-gate 未被专项关闭。 | 未跑实际专项全链路排空/超时恢复。 |
| 原生持久启动围栏、国内容器禁自动重启 | 围栏设置有实现，恢复不符合，见 HIGH-1。`domestic_tasks_engine.py:97` 写入持久 ConditionPathExists；`:38` 校验停止；`:35` 修改容器策略。 | 尚无真实 systemd 主机重启故障演练。 |
| 仅国内 pg_dump、归档校验、大小/SHA回执 | 实现路径匹配。`domestic_tasks_engine.py:46`；`operations.py:52` 调 pg_dump -Fc 和 pg_restore --list、核验退出码，专项复核大小/SHA。`test_domestic_tasks_engine.py:62` 证明备份失败不调用迁移。 | 专项测试的归档内容是 stub，不代表真实 pg_dump/restore 演练。 |
| 迁移单事务、进程子锁、数据库锁 | 实现路径匹配。`domestic_tasks_engine.py:60` 在停止后备份/捕获历史，传递 descriptor 和 fence 环境；`joint_studio_fence.py:26` 不显式解锁，`:54` 等待 DB 锁；`backend/migrations/env.py:39` 包裹事务。 | Linux 真实文件锁子进程测试通过；3 个真实 DB fence 用例被环境安全检查拒绝，见下文。 |
| 0044历史归属和原字段保留 | 实现路径匹配。`0044_domestic_tasks.py:48` 按 owner/workspace 建任务和回填；`:64` NOT NULL、复合FK及删除回执FK；`domestic_tasks_history.py:17` 对全部既有 Studio 表逐行 JSON 排序摘要，只剔除新增 task_id；`:37` 校验归属和组数量。 | reviewer 未重复另一 reviewer 的真实 PostgreSQL 迁移验证。生产在线预采样不作为最终基线。 |
| 4. 新schema后仅前向恢复、不旧worker复活、不倒灌DB | 实现路径匹配。`domestic_tasks_engine.py:112` 先等待迁移锁/核schema，拒绝已提交时旧恢复；`:128` 只装候选；`domestic_tasks_release.py:172` 未知schema拒绝；`scope_release.py:52` 禁跨schema rollback。 | 新增测试以模拟schema/服务替换验证分支，未完成真实全链路中断演练。 |
| 其他组源码/schema/PID/容器/数据/镜像/依赖不变 | 对这些字段有明确核验，`domestic_tasks_release.py:90`、`scope_snapshot.py:138`；但配置漂移遗漏，见 HIGH-2。 | 未运行生产后验。 |
| 成功落账、每组两版、cleanup保留真实引用 | 接线匹配。`domestic_tasks_release.py:117` 至 `:133` 先核验/advance/落账再 cleanup；`scope_catalog.py:35` 仅推进国内组；`:59` 保留每组current/previous及pending/staged引用。 | 未新增专项完整成功/cleanup故障真实资源演练；既有套件通过不能消除两个HIGH。 |
| 5. 故障覆盖及真实性 | 部分完成。新增测试覆盖备份失败、提交后父进程中断、历史不符、未知schema、恢复/取消中断和前向分支（`test_domestic_tasks_engine.py:62`、`:71`、`:86`；`test_domestic_tasks_state.py:49`、`:65`、`:97`）。 | 容器策略恢复、非目标配置漂移和成功落账中断缺少有效测试；前两项已实际暴露缺陷。 |
| UI一致性、邻居页面 | 本专项发布工具无UI，N/A。 | 产品UI属于另一份审查，不能据本报告批准。 |

本次范围未发现维护合同之外新增发布能力；唯一共享文件例外有路径和双摘要约束。此结论仅针对发布工具范围，不是整产品 Spec 漂移结论。

## 原始验证输出

首次按交接命令运行，容器现有 TEST_DOMESTIC_STUDIO_DATABASE_URL 不满足旧测试要求的 localhost/127.0.0.1 与 *_test 数据库名，未执行这些测试的数据库操作：

```text
docker exec -u root -w /workspace hx-task-20261117-python python -m pytest scripts/release/intranet -q
FAILED scripts/release/intranet/test_joint_studio_fence_linux.py::test_database_fence_waits_for_the_prior_transaction
FAILED scripts/release/intranet/test_joint_studio_fence_linux.py::test_real_native_identity_waits_for_database_fence
FAILED scripts/release/intranet/test_joint_studio_release.py::test_real_recovery_waits_for_prior_database_transaction
E   Failed: Only a disposable local *_test database is allowed
3 failed, 451 passed, 2 skipped, 15 subtests passed in 16.07s
```

显式去除该数据库测试变量后，与作者给出的无数据库条件一致：

```text
docker exec -u root -w /workspace hx-task-20261117-python env -u TEST_DOMESTIC_STUDIO_DATABASE_URL python -m pytest scripts/release/intranet -q
451 passed, 5 skipped, 15 subtests passed in 16.91s
```

去除变量只用于确认已有可运行套件；3个DB锁测试仍未验证，不能把 skip 计为通过。

编译与空白检查原始结果：

```text
docker exec -u root -w /workspace hx-task-20261117-python python -m compileall -q scripts/release/intranet hengxin-smart-image/backend/migrations/versions/0044_domestic_tasks.py
stdout: <empty>
exit_code: 0

git diff --check -- scripts/release/intranet hengxin-smart-image/backend/migrations/versions/0044_domestic_tasks.py
warning: in the working copy of 'scripts/release/intranet/scope_release.py', CRLF will be replaced by LF the next time Git touches it
exit_code: 0
```

## 重新送审前的具体验证

1. 修复两个HIGH，补真实 scoped 调用链与独立 Docker 重启策略测试；其他组配置修改/增加/删除均保持 pending 并拒绝成功落账。
2. 给独立 Linux 测试环境提供符合 localhost/127.0.0.1、*_test 限制的可丢弃 PostgreSQL，再跑上述3个DB锁测试，不削弱安全检查。
3. 在独立 Linux/systemd/Docker 环境，从最终工具安装目录、真实服务 UID 执行一次 prepare→停止→备份→0044→切换→finish；分别注入迁移父进程中断、子进程仍存活、启动前重启、成功台账写入中断。确认旧worker不复活、恢复只指向候选、两版/其他组/清理引用正确。现有 mock 测试不可替代这一证据。
4. 重新 review-prepare，并从 Stage 1 复审；本报告未授权发布或审查批准。

## Stage 2

**未执行。** Stage 1 存在 HIGH，依 code-review skill 停止；未给代码质量、安全扫描或视觉审查 PASS。
