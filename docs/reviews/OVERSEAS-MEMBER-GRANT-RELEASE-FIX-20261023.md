# 海外指定成员授权发布事务修复：独立复审

- 日期：2026-10-23。
- candidateId：`3e3178873ff8f25a41c8c5b3cebf719a6fd341a667442f932e4f23f67fc38818`。
- Stage 1：**PASS（部署前代码范围）**。
- Stage 2：**PASS（部署前代码范围）**。
- 范围：原报告 `docs/reviews/OVERSEAS-MEMBER-GRANT-20261023.md` 的完整授权约束，以及 `scripts/release/overseas-member-grant.py:119` 的事务对象修复和 `:120` 的锁注释修正。原候选为 `2140ac2e1517102388899757131c61a3426b39100353f7158b218208e10a9978`。
- 独立 review-status 开始及结束均确认当前候选为上述新编号，相对原批准快照仅发布脚本变化。四个后端业务文件、新增授权测试与 probe 未变化；未直接把旧编号批准结论套用到新快照。
- 本轮 reviewer 只写本报告，未修改实现、未操作生产、未提交或登记凭据。本报告不代表生产部署完成。

## Stage 1：Spec Compliance

源要求：`Product-Spec.md:1318`、`:1320`，`docs/OVERSEAS-MEMBER-GRANT-20261023.md:3` 至 `:11`。以下 `app/`、`tests/` 相对路径以 `hengxin-smart-image/backend/` 为根。未变化业务的动态证据沿用原报告中的独立 128 项通过记录，本轮重新阅读实现及测试约束，没有重跑业务全套。

| 完整约束 | 结论及证据 |
| --- | --- |
| 回滚预览，不新增正式权限页面 | 完整实现。候选及 git status 无前端改动；`frontend/src/views/overseas/OverseasPortal.vue:5` 展示真实角色，`:43` 消费 capabilities。撤回预览和停止 3027 的操作记录见实施文档 `:17`；本轮未重新操作服务。 |
| 唯一成员 ID 授权，不按姓名或扩大到其他主管 | 完整实现。`app/overseas/config.py:30` 为 UUID 集合，`permissions.py:54` 按 ID 判断；`tests/test_overseas_full_access_grant.py:21` 验证同名同角色不同 ID 不扩权，`:128` 验证非法 UUID 拒绝。 |
| 全部 9 项权限、所有任务范围和特殊运营操作 | 完整实现。`permissions.py:14`、`:30`、`:60` 统一完整策略；新增测试 `:34` 遍历能力，`:41` 访问成员和配置，`:107` 验证非本人任务重提。原报告列明任务查询、素材及特殊重提路径证据；这些文件在候选之间未变化。 |
| 真实 design_manager 角色、成员 ID 和操作者不变 | 完整实现。`auth/router.py:27` 区分真实 roles 和 capabilities，`permissions.py:64` 保留原 ID；测试 `:28`、`:40`、`:46` 验证接口/数据库角色和创建者，`:101` 核对 Skill 审计 actor。 |
| 启用、正式成员、唯一合法角色优先，旧会话重新检查 | 完整实现。`permissions.py:62` 先调用 `auth/dependencies.py:13`；后者 `:33` 在每次会话访问时复验。测试 `:49` 覆盖停用、待加入、未确认成员、无角色。 |
| 撤销恢复原角色；原所有者权限保留 | 完整实现。`permissions.py:63` 撤销后采用原角色；`management/skills.py:15` 保留原 owner 分支；测试 `:70` 覆盖既有会话撤销。进程配置变更须重建 API 生效，未声称只编辑环境文件即可即时生效。 |
| Skill 状态/配置不改变，授权仍受接口权限和审计限制 | 完整实现。`management/skills.py:43` 先执行 lock_actor 权限校验；probe `scripts/release/overseas-member-grant-probe.py:42` 保存状态及版本，发布脚本 `:144` 比较保护状态；没有调用 Skill 写接口。 |
| 状态机、并发、最后管理员保护保持 | 完整实现。业务修改范围与原批准快照相同；测试 `:102` 验证最后管理员保护，`:124` 验证不合法重提状态拒绝。发布 gate 使用真实 `execution/queue.py:14` 行锁 helper，本次修正没有改变 worker 状态机。 |
| 国内权限不变 | 完整实现。新增设置仅在 OverseasSettings，`config.py:9`、`:30`；发布 overlay `scripts/release/overseas-member-grant.py:99` 仅作用海外 API。 |
| 备份、仅 API 切换、原配置/其他进程保护及审计 | 完整实现。发布脚本 `:101` 核对配置差异，`:125` 备份数据库，`:131` 验证归档，`:133` 仅重建 api，`:142` 至 `:148` 验证状态并恢复 gate；probe `:68` 记录实际 actor/target 授权审计。发布前真实 HTTP 验收、回退/撤销说明仍属主 Agent 的部署交付步骤。 |
| pause/resume 能正确取得 Session 并提交 | 完整实现。发布脚本 `:119` 使用 `session_factory().begin()`；`app/db/session.py:64` 返回 sessionmaker。独立提取原字符串并执行真实 helper，暂停和恢复均成功提交，异常路径回滚通过，见下方原始输出。恢复 `:147` 使用同一字符串替换布尔值，获得相同修复。 |

部分实现、未实现：本轮代码范围内无。Spec 漂移：无新增页面、业务接口、表或角色。新改动仅修复发布事务对象与同步注释。

## Stage 2：Code Quality

- 质量：PASS。发布脚本 161 行，新增事务表达式与 `app/db/session.py:64` 返回类型相符；未新增重复逻辑。`scripts/release/overseas-member-grant.py:120` 现在准确区分暂停事务持锁与后续 probe 读已提交状态，关闭原报告 LOW 注释问题。
- 根因核实：`Session.begin()` 的上下文对象是 SessionTransaction，不能传给需要 `.scalar()` 的 `lock_gate`；sessionmaker 的 `.begin()` 提供 Session，并负责提交/回滚/关闭。本地 SQLAlchemy 2.0.51 复现旧错误及验证修复，与 [SQLAlchemy 官方事务文档](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html) 一致。代码位置：发布脚本 `:119`、`execution/queue.py:15`。
- 测试真实性：PASS。本轮不是只编译或 mock 返回值。读取脚本 AST 中的 pause 字符串，只省略 application main 启动，替换数据库引擎为隔离 SQLite，使用真实 session_factory、ExecutionGate 和 lock_gate；验证暂停/恢复的提交结果及故意异常后的回滚。SQLite 不证明 PostgreSQL 行锁并发行为；锁 helper 未变化。原 128 项业务回归与 Linux 548 项通过/67 跳过沿用原报告证据，未声称本轮重新运行。
- 安全：PASS。发布脚本 `:119`、`:147` 为固定代码字符串，不含外部插值；`:121`、`:148` 仍通过参数数组/stdin 执行。指定脚本及 permissions 扫描 eval、HTML 注入、VITE 密钥变量和常见密钥前缀无匹配；未新增凭据、SQL 拼接或业务环境泄漏。私有权限和镜像隔离保持原报告结论。
- 视觉对比：不适用，本次无前端改动；`OverseasPortal.vue:5`、`:43` 仍按真实角色和能力渲染。未打开浏览器，不声明做过生产视觉或目标账号本人登录验收。
- 问题分级：未发现新的 HIGH/MEDIUM/LOW 问题。原报告提醒继续适用：普通 Python 执行而非 `-O`；暂停限制认领而不禁止持久入队；失败后按现场状态处理，不能盲目重跑部署（发布脚本 `:113`、`:151`）。

## 本轮独立验证原始输出

在 backend 中使用 `.venv/Scripts/python.exe -`，从源码 AST 提取 pause，运行项目真实事务工厂和 gate helper，输出：

```text
extracted pause/resume committed: True
extracted pause/resume committed: False
old expression reproduced: 'SessionTransaction' object has no attribute 'scalar'
exception rollback: PASS
SQLAlchemy: 2.0.51
exit_code: 0
```

仓库根目录执行六个模块编译：

```text
python -m py_compile scripts/release/overseas-member-grant.py scripts/release/overseas-member-grant-probe.py hengxin-smart-image/backend/app/overseas/config.py hengxin-smart-image/backend/app/overseas/permissions.py hengxin-smart-image/backend/app/overseas/auth/router.py hengxin-smart-image/backend/app/overseas/management/skills.py
stdout: [空]
stderr: [空]
exit_code: 0
```

独立快照检查原始输出：

```json
{"currentId": "3e3178873ff8f25a41c8c5b3cebf719a6fd341a667442f932e4f23f67fc38818", "reviewedId": "2140ac2e1517102388899757131c61a3426b39100353f7158b218208e10a9978", "changedFiles": ["scripts/release/overseas-member-grant.py"], "approved": false}
```

主 Agent 本轮另提供生产容器验证，reviewer 未亲自执行：从上传脚本 AST 提取 pause，True/False 各运行一次，事务结尾显式 rollback，两次 returncode 0；probe 与 prepared.initial 严格相等，gate.paused 为 False。上传脚本 SHA256 为 `e10677f011378ea7d9a0dea71ae4e6b9c3d129399bbbd89449e3d705d2c78318`。此证据证明真实环境下事务/helper 可执行且回滚后状态不变，不证明已正式部署或提交过 gate 状态。

由主 Agent 对本 candidateId 登记两阶段 PASS；后续代码变化需重新固定快照复核。
