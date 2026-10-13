# 成员隔离历史核查工具

本轮仅开发与隔离测试；没有连接生产，没有执行生产名单清理。

实施顺序和验收：

1. 反射数据库外键及身份列，输出只读报告；验收是两业务分别报告、数据库零写入、报告不带会话凭据。
2. 固定人工审核名单，默认模拟；验收是状态、身份、完整快照不一致或任何授权/申请/业务引用出现时跳过。
3. 明确 `--apply` 后逐 ID 锁定、复查、保存恢复包再删除空壳；验收是无级联业务删除、重复执行幂等、恢复后原记录完整一致。
4. SQLite 临时库和可用的隔离 PostgreSQL 执行测试；生产核对与名单执行另需授权。

沿用后端 `.venv` 的 SQLAlchemy，不导入应用配置，不自动读取 `.env`，不升级依赖。数据库 URL 必须通过显式命名的环境变量提供，URL 不出现在报告或错误输出中。只支持 SQLite/PostgreSQL。使用 `--schema` 选择 PostgreSQL 的目标 schema；引用检查覆盖全部非系统 schema，权限不足即失败，不降级成“没有引用”。

```powershell
$env:MEMBER_AUDIT_DB = 'sqlite:///D:/isolated/member-test.sqlite'
& hengxin-smart-image/backend/.venv/Scripts/python.exe scripts/maintenance/audit-business-members.py --business overseas --database-url-env MEMBER_AUDIT_DB --output audit.json
& hengxin-smart-image/backend/.venv/Scripts/python.exe scripts/maintenance/reconcile-business-members.py --business overseas --database-url-env MEMBER_AUDIT_DB --approved-list reviewed.json --output dry-run.json
# 仅在审核及执行授权都已具备时使用：
& hengxin-smart-image/backend/.venv/Scripts/python.exe scripts/maintenance/reconcile-business-members.py --business overseas --database-url-env MEMBER_AUDIT_DB --approved-list reviewed.json --apply --recovery-dir recovery --output result.json
```

审核名单不是报告的自动导出。逐条人工核查后创建以下 JSON；`expected` 完整复制该条报告的 `expected`，不得按 pending 批量筛选生成。报告里的 `cleanupEligible` 仅代表技术条件允许核查，不能证明误建。姓名和另一个业务是否存在该人不参与判断。

```json
{
  "formatVersion": 1,
  "business": "overseas",
  "sourceFingerprint": "复制报告值",
  "reviewedBy": "审核者",
  "reason": "已逐条确认误建空壳；填写实际核查依据",
  "members": [
    {
      "id": "复制报告成员ID",
      "expected": {
        "status": "pending",
        "directoryState": "legacy_unconfirmed",
        "version": 1,
        "identities": [{"provider": "dingtalk", "corpId": "企业ID", "providerUserId": "钉钉成员ID"}],
        "snapshotSha256": "复制报告值"
      }
    }
  ]
}
```

国内旧 `users` 无数值 version 时明确填写 `null`，完整成员/身份行快照摘要仍是必填版本条件。缺少归属迁移或申请表时可以报告，但不允许清理。只清理 pending + legacy_unconfirmed + 无角色 + 无历史会话 + 无申请 + 无审计/业务引用的记录；停用、已授权、正常申请和真实双业务成员均保留。国内身份映射仅在自身没有入边引用时允许作为叶子删除，其完整行进入恢复包。归档的无外键 created_by/designer_id 以及其他约定的身份列同样检查。模拟结果包含 `recoveryPreview` 完整类型化原始行，可在执行前审核恢复资料。

SQLite 写入采用 `BEGIN IMMEDIATE`，PostgreSQL 对成员、身份、申请及所有相关引用表加 `SHARE ROW EXCLUSIVE` 锁，锁后重新扫描，再逐条检查。事务使用有限锁等待；锁失败报告跳过，不强杀连接。清理过程中会短暂阻塞相关业务写入，实际执行应安排维护窗口。只读报告使用数据库只读事务。

恢复目录是敏感的人员数据材料，须用操作系统权限限制访问，不进入 Git。每条删除前先持久化完整原始成员与身份行（含类型、全部列、摘要、审核者、原因、引用检查），然后提交删除；提交后另写收据。进程意外终止时 `prepared` 包不代表已经删除，应先重新只读核查。恢复不会恢复任何会话/密钥，也不会提升权限。

```powershell
# 默认先模拟恢复；加 --apply 才写数据库，要求同业务、同数据源。
& hengxin-smart-image/backend/.venv/Scripts/python.exe scripts/maintenance/reconcile-business-members.py --business overseas --database-url-env MEMBER_AUDIT_DB --restore recovery/某条.prepared.json --output restore-check.json
```

恢复只插入同一份原始 legacy 空壳和身份映射；存在完全相同记录返回 already_restored，有变化或身份被占用则跳过，绝不覆盖。保留原 ID、时间、版本及身份字段。每次运行输出 JSON 作为纠正/恢复审计；不要把“删除成功”当作历史核对全部完成，名单外记录不动。

验证命令：

```powershell
& hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/maintenance/tests -q
```

可选 PostgreSQL 测试只读取 `TEST_MEMBER_MAINTENANCE_DATABASE_URL`，数据库名必须以 `_test` 结尾，测试创建随机 schema 并在结束删除。没有显式测试 URL 时跳过 PostgreSQL，不借用生产配置。

2026-10-13 本轮验证：上述 pytest 命令在临时 SQLite 和独占 PostgreSQL `membership_audit_test` 上得到 **60 passed, 1 skipped**（28.27 秒）。PostgreSQL 10 项全部执行通过；唯一跳过是“海外无独立身份映射表”的不适用分支。覆盖两边现有完整模型、CLI完整流程、未迁移拒绝、状态/身份/版本变化、所有类型引用、真实锁等待、跨 schema 外键、凭据脱敏、恢复一致性和幂等。`python -m compileall -q scripts/maintenance` 通过；清理后临时 PostgreSQL schema 数为 0。以上是隔离工具验证，不是生产名单整改证据；整轮独立代码审查由主 Agent 统一完成。
