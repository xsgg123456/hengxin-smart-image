# 旧公网发布工具退役独立审查

- 日期：2026-11-13；审查技能：`.agents/skills/code-review/SKILL.md`。
- candidateId：`b0f9735c3dd142a82f63b217a9481abf396c4a1d6592dde2cd580f84032ec9cf`；基线 HEAD：`e59a484`。
- 范围：365 个旧公网专用文件删除、11 个保留根模块的依赖闭包、transport/unify_release/worker 入口封闭、两份新增回归测试及内网默认规则/指南。需求为 `Product-Spec.md:1503`、`DEV-PLAN.md:1762` 和退役合同，不重审全产品历史功能。
- **Stage 1：PASS；Stage 2：PASS。未发现本次新增 HIGH/MEDIUM 问题。**
- 开始及结束的 `harness.py review-status` 均返回上述 currentId。期间主 Agent 只补充普通 Markdown 验证记录与 README 完成措辞，已复读；代码快照没有漂移。未操作 `.needs-review`，凭据由主 Agent 登记。

## Stage 1 · Spec Compliance

| 合同条目 | 结论与证据 |
|---|---|
| 默认内网，本地测试隔离 | 完整实现。`AGENTS.md:185` 固定生产目标并明确本地测试边界；`README.md:3` 指向当前内网指南。独立回归使用 `--network none`、只读测试输入挂载、`--rm`，未连接服务器。 |
| 国内/海外独立发布、回退及保留策略继续复用 | 完整实现。内网既有实现未改：`scripts/release/intranet/release.py:18` 继续动态加载保留的台账模块；`scripts/release/intranet/engine.py:12` 继续加载 unify 原语。独立重跑内网测试集通过，包含 scope/清理/故障恢复用例。规则见 `AGENTS.md:187`。 |
| 专用文件删除，静态/动态引用闭包保留 | 完整实现。`docs/PUBLIC-RELEASE-RETIRED-FILES-20261113.json:2` 清单与 `git diff --diff-filter=D` 的 365 个路径集合完全相等，全部不存在，11 个保留模块均存在。对 Git 跟踪及新增活动代码/配置扫描全部删除文件名，零引用。动态链：`retirement-backup.py:9` → `domestic-backup.py:8` → `member-release-backup.py:11` → `member-release-runtime.py:18` 的三个运行模块；`overseas-runtime.py:19` 再加载 management-runtime。上述均位于 `scripts/release/`。`member-release-drain.py:102` 引用的 worker 文件保留。`hengxin-smart-image/backend/tests/test_domestic_retirement.py:112` 仍可加载备份模块；新增 `scripts/release/intranet/test_retired_public_tools.py:11` 实际导入整个链并调用合同/投影函数通过。 |
| 公网连接和迁移传输入口关闭，兼容内网 connect | 完整实现。`hengxin-smart-image/scripts/migration245/transport.py:5` 对所有非 False 参数在导入 SSH 库前拒绝，仅固定内网主机与密钥，保留 RejectPolicy 与 hostname 校验；transfer/destination_path 已删除。`test_retired_entrypoints.py:30`、`:41`、`:60`、`:71` 分别验证旧参数、内网兼容、错误主机关闭和不可信密钥拒绝，全部实际执行通过（文件同目录）。 |
| unify 原语保留，直接整站命令拒绝；跨业务升级仍需联合维护 | 完整实现。`hengxin-smart-image/scripts/migration245/unify_release.py:625` 的 main 无条件拒绝；`scripts/release/image-inputs-worker.py:74` 旧 CLI 同样拒绝。`test_retired_entrypoints.py:95` 覆盖无参数、旧参数、help、三个旧动作且副作用 mock 均未调用，`:134` 实际导入内网引擎。`scripts/release/intranet/scope_changes.py:148`、`:178` 保留依赖及共享变更拒绝；本次没有修改该检查。 |
| 当前文档明确内网，历史仅追溯；不宣称清空服务器 | 完整实现。`hengxin-smart-image/docs/DEPLOYMENT.md:1`、`HANDOVER.md:1`、`scripts/migration245/README.md:3`（后两者同项目子目录）和 `docs/INTRANET-RELEASE-TOOLS.md:3` 明确历史边界；`scripts/release/README.md:5` 说明保留模块用途，`:9` 明确未删除服务器文件。退役合同 `docs/PUBLIC-RELEASE-RETIREMENT-20261113.md:23` 起区分源码字节数、测试和服务器状态。 |

部分实现、未实现、Spec 漂移：无。本次没有页面、API、数据库表或业务功能新增。UI/设计/邻居页面视觉对比不适用：改动范围为发布工具与文档，前端源码没有变化。

## Stage 2 · Code Quality

- 测试真实性：`hengxin-smart-image/scripts/migration245/test_retired_entrypoints.py:90` 在入口执行期间拦截网络、进程和写入能力，`:113` 检查没有调用；测试没有把已关闭入口替换成假实现。系统 Python 的实际 paramiko 被 mock SSHClient，9 项均运行、无跳过。`scripts/release/intranet/test_retired_public_tools.py:21` 以真实子进程执行 worker 并检查非零退出和新入口提示。
- 安全：对三个修改模块和两份新增测试检查硬编码密钥、危险 eval、前端秘密变量、密码字面量等模式，零命中；`transport.py:12` 保留拒绝未知主机密钥策略。仅存密钥文件名，不包含密钥内容。拒绝分支先于 SSHClient 创建，无公网连接回退。
- 结构：本次入口函数为直接拒绝，新增测试分别 149/26 行，transport 32 行、worker 79 行。`hengxin-smart-image/scripts/migration245/unify_release.py:1` 仍为 634 行，超过技能 300 行建议，是原有复用模块，本次由 644 行缩短；记录为既有结构债，不要求为退役任务扩大重构。
- 错误处理：拒绝均非零退出且包含新入口；主机不匹配关闭客户端（`transport.py:21`）。无新增捕获后静默成功逻辑。
- 语法/格式：109 个保留 Python 文件 AST 编译通过；`git diff --check` 返回 0，仅 Git 的 CRLF→LF 提示。此次没有业务编译产物变化，未重新构建前端或业务镜像。

## 独立验证原始输出与边界

测试输入 `output/public-retirement/source.tar` 的 590 个文件逐个与当前工作树字节比较：

```text
tar files: 590 drift: []
AST compile: 109 passed
```

Linux 命令：`docker run --rm --network none --user 0 --mount type=bind,source=D:\Work_Project\hengxin-smart-image\output\public-retirement,target=/input,readonly hx-retirement-test:local python /input/linux_check.py`。镜像 ID：`94e55f28612d1db16f4039a8945ef0b309f25b3e2a26aeaf31c1e742ad90cd02`。退出码 0，原始输出：

```text
........................................................................ [ 14%]
............s........................................................... [ 29%]
...................................ss..........s........................ [ 44%]
....s................................................................... [ 58%]
...................................................................... [ 73%]
.............................................s..... [ 83%]
...........sssssssssssss................. [ 91%]
............s..ss.......................                  [100%]
468 passed, 22 skipped, 69 subtests passed in 7.63s
```

Windows：backend venv 执行 `pytest scripts/release/intranet/test_package_release.py scripts/release/intranet/test_retired_public_tools.py -q`，退出码 0：

```text
15 passed, 7 subtests passed in 12.77s
```

系统 Python：`python -m unittest discover -s hengxin-smart-image/scripts/migration245 -p test_retired_entrypoints.py -v`，9 个具名用例均 `ok`，退出码 0：

```text
----------------------------------------------------------------------
Ran 9 tests in 0.051s

OK
```

Linux 的 22 个 skipped 不算通过，条件来源包括 PostgreSQL 显式启用/连接、systemd、bwrap 和 paramiko（例如 `data_copy_test.py:66`、`build_native_test.py:98`、`test_retired_entrypoints.py:40`，位于 migration245；以及 `scripts/release/intranet/test_joint_studio_migration_linux.py:14`）。paramiko 分支已由系统 Python 单独覆盖。没有验证真实 PostgreSQL 迁移、真实 SSH 或服务器安装状态；本次也未请求执行这些生产操作。业务数据库迁移测试仅验证导入依赖保留，不能据此宣称数据库迁移全量通过。

最终结论只适用于上述 candidate 的仓库退役变更；主 Agent 可登记同一快照的两阶段 PASS，再按既定授权处理提交。
