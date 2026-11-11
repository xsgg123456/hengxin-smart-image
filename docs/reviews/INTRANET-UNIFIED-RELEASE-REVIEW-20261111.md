# 内网统一发布独立审查 · 2026-11-11

## 快照与范围

- candidateId：`4c672a8590bdc7be7703fefb52a44c227f21b9d328ef66d6777864b9f3a4e77d`。独立执行 `review-status`，currentId 与此一致。
- 范围：`hengxin-smart-image/backend/app/account_management/service.py` 的 UID 适配；`hengxin-smart-image/scripts/migration245/unify_release.py`、`test_unify_release.py`；对应 Product-Spec、DEV-PLAN 与 `docs/INTRANET-UNIFIED-RELEASE-20261111.md` 发布合同。下文脚本路径均相对此项目子目录。
- 脚本 SHA256：`d37bc032065b4138d4b2adf849c8486d44ebbdef3789203213458f0e4a44e311`；测试：`f5a2f62d40a2e4184b29338280015499748da644b4526284c81454c7c4af9a68`；账号服务：`311d925f0a6d6bb655085686868acc5e4654dce77e08c4651ac15f6fa7b2f791`。
- 初始候选 `eb2e9a0b518c206da2c14e139f0eeaf77beab3091b11638b6a3be003538b46b8` 未批准。审查中发现原候选父目录 `/opt/hengxin-lan` 为 root:root 0700，真实 UID 导入失败；已将源码发布目录改为 `/opt/hengxin-unified-releases/unified-20261111`，原私有目录权限保留。重新固定上述最终快照，并重新执行 19 项测试、编译和真实预检；旧结论未覆盖新版本。

## Stage 1 — PASS（发布前实现审查）

| 合同条目 | 结论及证据 |
|---|---|
| 1. 固定源码、构建清单和 UID 兼容 | 完整实现。`backend/app/account_management/service.py:129` 从既有环境读取海外 UID，默认 999；独立只读实查 accounts 环境值 1002、海外 worker 实际 UID 1002。`scripts/migration245/unify_release.py:166` 校验完整提交号、文件集合、逐文件 SHA256 和渲染器执行权限；`:509`、`:545`、`:556` 在切换前后拒绝内容漂移。最终 manifest 与提交的精确对应由提交后 prepare 前执行，不把未发生的步骤记为通过。 |
| 2. 保留依赖、账号、环境和数据；8 容器及 7 原生服务一致 | 完整实现。`:27`、`:36` 显式列举服务；`:199` 深拷贝 compose，仅替换代码与前端挂载；`:138`、`:160` 使用实际进程解释器、环境、UID/GID/附加组预检；`:315` 只覆盖 WorkingDirectory，保留原 ExecStart 与 venv。独立核对线上被移除挂载仅两 API 各两个只读 Python 补丁，无账号/数据挂载。`:107` 拒绝数据服务动作，up 使用 `--no-deps --pull never`；`:132`、`:511`、`:558` 检查数据容器 ID。测试 `test_unify_release.py:26`、`:55`、`:188` 验证保留与拒绝行为。 |
| 3. 备份、排空、切换失败恢复、不强杀 | 完整实现。`:276` 私有备份及摘要固定；`:535` 先关闭 web 和三个 API；`:390` 对国内 CLI、海外 CLI、API 图片消费者检查 active/reserved/scheduled、数据库和 broker 待办，暂停后复核竞争；`:411` 门禁账号 socket 并验证授权空闲。独立实查 accounts 为 4 线程/1 进程，auth 为 1 线程/1 进程，两域临时授权目录均空。`:439` 设置 `SendSIGKILL=no`，`:114` 使用无限等待停止容器。`:564` 回退再次关闭入口、排空部分启动 worker、恢复 compose/删除本次 drop-in；无法确认时明确失败，不强制杀执行进程。故障注入 `test_unify_release.py:161`、`:194`、`:202`、`:209`、`:219` 覆盖健康失败、排空失败、漂移和部分启动。 |
| 3. 限定 .245、不操作旧公网 | 完整实现。`:620` 校验 hostname 与 root，配置均指向内网本机；脚本无 SSH、旧公网地址或 transport 调用。审查只使用 `transport.connect()` 默认目标只读核验 .245，未接触旧公网。 |
| 4. 发布验收与如实记录 | 发布前检查实现。`:463` 验证原生服务、容器健康、双业务 ready、identity config、三消费者队列和前端 HTTP。最终真实预检通过 8 容器、7 原生导入及两 worker 运行时检查。运行进程逐文件摘要、前端实际构建、账号数据保存及真实 Codex 图片/PPT 的发布后验收尚未执行，必须继续按合同第 4 项记录；本报告不代表发布完成或全业务验收。 |

未实现/部分实现：本次送审代码无已确认缺失；发布后的操作验收待执行。无新增页面、API、表或产品功能，未发现 Spec 漂移。UI/引导一致性及邻居页面视觉比较不适用：本次没有 UI 源码变更，前端为既有 Git 构建；发布后的国内/海外页面仍须实测。

HIGH 问题已关闭：真实服务 UID 无法穿越旧候选父目录。最初预检在生产切换前拦截，最终版本 `unify_release.py:23` 改用独立源码目录，最终日志包含全部 15 个 `IMPORT_OK`、2 个 `RUNTIME_OK` 及 `PREFLIGHT_OK`。

## Stage 2 — PASS

- 代码质量：发布事务步骤、白名单、摘要与失败恢复职责明确，命令使用 argv 而非 shell 字符串。`unify_release.py:59` 只输出安全错误摘要；`:68`、`:85` 验证 root 所有权、禁止可写祖先/符号链接/硬链接并原子写入。没有发现需阻断发布的质量问题。
- 质量例外：`unify_release.py` 共 631 行，超过 skill 的 300 行标准。主 Agent 明确转达用户本次一次性发布要求最小流程；记录这一例外，不为形式拆分扩大本次改动。测试文件 231 行。
- 测试真实性：独立重跑 19 项，包含保留配置、数据容器动作拒绝、数据库非空阻断、暂停竞争、启动失败恢复、部分启动再次排空、并发配置保护；关键断言核对实际 compose 内容与 drop-in 状态，见 `test_unify_release.py:26`、`:85`、`:153`、`:161`、`:209`、`:219`。测试中的 OS/服务动作被 mock；真实预检补充实际 UID/venv/依赖前提。未在生产注入停服/回退故障，不宣称做过实际故障演练。
- 安全扫描：本次代码未发现硬编码秘密、eval、shell=True、旧公网连接、数据库迁移或删除数据动作。数据服务仅查询 ID，避免输出其 command/environment，见 `unify_release.py:132`；备份存于私有事务目录，见 `:294`、`:308`。发布目录绝对路径属于明确的本机部署边界。
- 非强杀语义核查：[Docker 官方 stop 文档](https://docs.docker.com/reference/cli/docker/container/stop/)明确 timeout=-1 等待退出而不设终止期限。脚本自身调用超时不等同于业务成功；无法恢复时 `:607` 返回 `RECOVERY_UNCONFIRMED`，需要主 Agent 检查私有事务记录，不能冒充已恢复。

## 原始验证输出

独立重跑最终脚本及测试：

```text
Ran 19 tests in 0.276s

OK
COMPILE_OK 3
```

编译使用 Python `compile` 对三份变更文件检查，不生成生产文件。`git diff --check` 无错误；只有现存 CRLF 转 LF 提示。

读取主 Agent 保存的真实 Linux 候选测试与前端构建原始日志，未把其声明代替日志：

```text
hengxin-vps-codex-worker TEST_RC 0
139 passed, 2 warnings in 11.53s
vite v7.1.7 building for production...
✓ 4830 modules transformed.
✓ built in 31.84s
```

证据：`output/unified-release-20261111/candidate-tests.log`、`frontend-build.log`。两项警告为第三方弃用；构建另有现存 pnpm 配置警告。本次没有更换运行依赖。

最终真实预检原始输出（`output/unified-release-20261111/preflight.log`）：

```text
IMPORT_OK domestic-api
IMPORT_OK overseas-api
IMPORT_OK identity-api
IMPORT_OK domestic-api-image-worker
IMPORT_OK domestic-api-image-outbox
IMPORT_OK domestic-image-variants
IMPORT_OK domestic-outbox
IMPORT_OK overseas-skill-publisher
IMPORT_OK hengxin-codex-accounts
IMPORT_OK hengxin-codex-auth
IMPORT_OK hengxin-domestic-deletions
IMPORT_OK hengxin-retention
IMPORT_OK hengxin-vps-codex-worker
IMPORT_OK hengxin-overseas-worker
IMPORT_OK hengxin-overseas-outbox
RUNTIME_OK hengxin-vps-codex-worker
RUNTIME_OK hengxin-overseas-worker
PREFLIGHT_OK; final manifest/prepare still required
```

结论仅批准上述快照的发布前实现。主 Agent 可按协议登记同一 candidateId 两阶段 PASS；随后固定准确 Git manifest、prepare、apply，并完成发布后实际验收。reviewer 未执行部署、未提交代码、未写 `.needs-review`。
