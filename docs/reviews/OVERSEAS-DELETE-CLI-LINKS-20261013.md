# 海外任务删除 CLI 链接专项审查

- 审查日期：2026-10-13；执行者：独立 code-reviewer。
- 原 candidateId：`729ef657cd97a834e1792522298249848b33f0875d6597016a52af82090dd730`。
- 结论：**Stage 1 PASS；Stage 2 FAIL（1 个 MEDIUM 测试缺陷，必须修复后复审）**。
- 范围：仅 `hengxin-smart-image/backend/app/overseas/tasks/cleanup_files.py` 的链接兼容修改，以及新增 `hengxin-smart-image/backend/tests/test_overseas_task_deletion_cli_links.py`。不含后续删除确认交互变更。
- 依据：`docs/OVERSEAS-DELETE-LINK-FIX-20261013.md:5`、`:11`；审查开始时 `Product-Spec.md:1020-1051` 的删除合同。已读取 AGENTS、code-review skill、HARNESS-REVIEW 协议及 reviewer 角色文件。

## 快照与审查边界

开始时 `review-status` 的 currentId 等于原 candidateId，变化文件仅上述两项。为避免并行开发混入，使用 HEAD `4d2d07f506758790f2199a4a5c0fe753148876f1` 的 backend Git 归档，加两份固定候选文件，在临时 Linux 容器重建测试环境。未改业务代码、未提交、未操作生产。

| 固定文件 | 原始字节 SHA-256 |
| --- | --- |
| `hengxin-smart-image/backend/app/overseas/tasks/cleanup_files.py` | `4963200904f2a2de296f18512fe06bb2f2806c218d6370816184d3d767bb6ccd` |
| `hengxin-smart-image/backend/tests/test_overseas_task_deletion_cli_links.py` | `4ed603587eb0c05db6c57d8a56a1c1e2760c7ca284bedddd7f8231e52d423729` |

审查中主 Agent 通知用户增加“取消手输任务名，保留二次确认”的需求。随后只读状态实际变为 `07302fed7a272ec6ff432b0b32a6dcb62d157c76b4fa38e56286e08a9c61c6ef`，涉及 deletion.py、schemas.py、前端和其他测试；上述两个专项文件当次复核哈希仍相同。**本报告不批准新快照**；下表其他文件行号指原 HEAD 基线。最终合并快照必须另行审查，不能把本报告登记为两阶段 PASS。

报告收尾时，主 Agent 进一步通知新测试已改为 `archive_contents` 解包比较，并报告 9 项重跑通过。这属于原哈希之后的新版，未在本专项内重新审查；本报告保留原候选 Stage 2 FAIL 和原始复现，修复状态由最终 fresh reviewer 核查。

## Stage 1：Spec Compliance — PASS

### 本次修复约束

| 合同 | 核查结果及证据 |
| --- | --- |
| legacy Job 和 studio 会话的正常 CLI 临时链接应可清理 | 完整实现。`hengxin-smart-image/backend/app/overseas/tasks/cleanup_files.py:61` 仍从 Job/Conversation 的数据库归属生成目录；`:75` 新增工具链接判断。新测试 `hengxin-smart-image/backend/tests/test_overseas_task_deletion_cli_links.py:33` 两分支经过 HTTP 删除及 cleanup_once，断言目录消失、404、deleted；独立冻结运行通过。 |
| 固定层级、临时目录前缀、四个固定名称、精确目标 | 完整实现。`hengxin-smart-image/backend/app/overseas/tasks/cleanup_files.py:78` 检查六段相对路径、固定前四段、完整正则、四个名称及 readlink 精确 `/opt/codex`。`hengxin-smart-image/backend/app/execution/workspace.py:105` 确认沙箱 CLI 的实际固定挂载。 |
| 只允许非目录叶子符号链接且 rmtree 抗链接攻击 | 完整实现。`hengxin-smart-image/backend/app/overseas/tasks/cleanup_files.py:79`、`:83` 同时要求能力标志、is_symlink 和非目录。新增测试 `hengxin-smart-image/backend/tests/test_overseas_task_deletion_cli_links.py:105` 覆盖能力标志为 false；reviewer 在 uid 999 容器补测精确目标为真实目录时拒绝。 |
| 其他链接、硬链接、根及父目录链接、越界路径仍拒绝 | 完整实现。`hengxin-smart-image/backend/app/overseas/tasks/cleanup_files.py:90`、`:95`、`:101`、`:103`、`:111` 保留防护；新增测试 `hengxin-smart-image/backend/tests/test_overseas_task_deletion_cli_links.py:65` 覆盖六种伪装。reviewer 另测 root/workspace/home 链接、`../`、`/opt/../opt/codex` 均拒绝。 |
| 仅删任务内链接，保留共享目标和归档 | 完整实现。`hengxin-smart-image/backend/app/overseas/tasks/cleanup_files.py:131` 重新验证后调用 rmtree；真实 `/opt/codex` 在 uid 999 测试中删除前后 SHA-256 相同。新增测试 `hengxin-smart-image/backend/tests/test_overseas_task_deletion_cli_links.py:54` 验证共享文件保留；归档真实成员内容由既有 `hengxin-smart-image/backend/tests/test_overseas_task_deletion.py:101` 和 assignment 测试覆盖。新增 ZIP 整体字节断言存在 Stage 2 测试问题，见下文。 |
| 失败可重试、保护失败不开始对象清理 | 完整实现。新增测试 `hengxin-smart-image/backend/tests/test_overseas_task_deletion_cli_links.py:91` 比较整个 store.data，验证失败回执；`:97` 修正目标后重试成功。`hengxin-smart-image/backend/app/overseas/tasks/cleanup.py:38` 先保护归档、生成清单后才 erasing。 |
| 只读验证、隔离验证，不自动部署或操作生产 | 符合此次审查操作。所有执行均为本地临时容器；`output/overseas-delete-candidate-readonly.json:1` 是主 Agent 提供的生产只读证据，显示 uid 999、inventory PASS、1 个对象和 1 个 Job 目录，以及原 delete_failed 回执。reviewer 读取了该证据，未重新连接生产，不能将此表述为已在生产完成删除。 |

### 原 Product-Spec 删除合同逐条影响核查

以下是本次链接改动对完整删除合同的影响核查。对未改 UI 与并发架构只做原基线代码关联，不把未重跑的浏览器/真实 PostgreSQL 并发场景写为本轮实测通过。

| Spec 原行 | 实现、验证与范围判断 |
| --- | --- |
| 1022：不授权删除现有生产任务 | 本轮未执行生产删除；原 candidate 与本地测试范围见本报告快照说明及 `docs/OVERSEAS-DELETE-LINK-FIX-20261013.md:14`。 |
| 1026：有效海外超级管理员专用权限；不改国内角色 | 原实现保留。`hengxin-smart-image/backend/app/overseas/tasks/deletion.py:33`；`hengxin-smart-image/backend/app/overseas/permissions.py:24`；`hengxin-smart-image/frontend/src/views/overseas/OverseasTaskDelete.vue:23`。既有测试 `hengxin-smart-image/backend/tests/test_overseas_task_deletion.py:55` 四类非管理员均 403，本轮通过。 |
| 1027：名称、范围、输入确认、取消无清理 | 原候选未改。原 `hengxin-smart-image/frontend/src/views/overseas/OverseasTaskDelete.vue:5`、`:8`、`:10`、`:55`；服务端 `hengxin-smart-image/backend/app/overseas/tasks/deletion.py:43`。本轮未重验 UI。后续用户取消输入的新需求不属于此候选。 |
| 1028：两种工作流、删除状态、失败原因及重试 | `hengxin-smart-image/backend/app/overseas/tasks/cleanup.py:55`、`:57` 只在实清理后完成，异常持久化失败。`hengxin-smart-image/backend/tests/test_overseas_task_deletion_cli_links.py:33`、`:65` 两分支成功/失败/重试均实测。原 UI 状态及轮询在 `hengxin-smart-image/frontend/src/views/overseas/OverseasTaskDelete.vue:3`、`:31`，未重做视觉测试。 |
| 1032：任务业务、对象和 CLI 全部实际清理 | `hengxin-smart-image/backend/app/overseas/tasks/cleanup_records.py:12` 明确删除依赖；`hengxin-smart-image/backend/app/overseas/tasks/cleanup_files.py:28`、`:131`。`hengxin-smart-image/backend/tests/test_overseas_task_deletion.py:67` 与 `hengxin-smart-image/backend/tests/test_overseas_task_deletion_legacy.py:26` 检查 DB、对象、多个执行目录；本轮通过。 |
| 1033：独立归档版本、信息、检索和下载 | `hengxin-smart-image/backend/app/overseas/archives/snapshot.py:12`、`:27`，`hengxin-smart-image/backend/app/overseas/archives/service.py:40`、`:65`；`hengxin-smart-image/backend/tests/test_overseas_task_deletion.py:101` 实测 sourceDeleted、SKU、图片 SHA-256、ZIP 成员与越权下载。 |
| 1034：合法改派同事务更新，删除后保留最终权限 | `hengxin-smart-image/backend/app/overseas/tasks/assignment.py:28`；`hengxin-smart-image/backend/app/overseas/tasks/cleanup_records.py:13` 仅脱离 task_id。`hengxin-smart-image/backend/tests/test_overseas_archive_assignment.py:47`、`:79` 本轮通过。 |
| 1035：共享资源保留、明确归属、覆盖两类目录 | `hengxin-smart-image/backend/app/overseas/tasks/cleanup_files.py:45`、`:61`、`:86`；新链接用例和 uid 999 实体目标验证通过。公共配置不在候选目录清单内。 |
| 1039：身份、版本、锁定状态、重复归并 | 原 `hengxin-smart-image/backend/app/overseas/tasks/deletion.py:32`；`hengxin-smart-image/backend/tests/test_overseas_task_deletion.py:117` 旧确认、版本及重复保护本轮通过。后续确认协议另审。 |
| 1040：撤销排队、核实进程及子进程退出 | `hengxin-smart-image/backend/app/overseas/tasks/deletion.py:17`；`hengxin-smart-image/backend/app/overseas/tasks/cleanup_process.py:31`。`hengxin-smart-image/backend/tests/test_overseas_task_deletion_process.py:17` 实际派生子进程验证，本轮通过。 |
| 1041：先保护归档，失败禁止破坏性清理 | `hengxin-smart-image/backend/app/overseas/tasks/cleanup.py:38`；`hengxin-smart-image/backend/app/overseas/archives/snapshot.py:32`、`:65`；`hengxin-smart-image/backend/tests/test_overseas_task_deletion_faults.py:19` 验证损坏后源对象不变及恢复。 |
| 1042：确定清单、持久进度、可重试不复活 | `hengxin-smart-image/backend/app/overseas/tasks/cleanup.py:42`、`:47`；`hengxin-smart-image/backend/tests/test_overseas_task_deletion_faults.py:44` 验证第二次对象删除故障后重放清单，新测试 `hengxin-smart-image/backend/tests/test_overseas_task_deletion_cli_links.py:97` 验证链接修正重试。 |
| 1043：核实完成、归档原权限继续访问 | `hengxin-smart-image/backend/app/overseas/tasks/cleanup_files.py:117`、`:138`；`hengxin-smart-image/backend/app/overseas/tasks/cleanup.py:55`；`hengxin-smart-image/backend/tests/test_overseas_archive_assignment.py:68` 本轮通过。 |
| 1047：拒绝非管理员，管理员可删他人任务 | `hengxin-smart-image/backend/tests/test_overseas_task_deletion.py:55`；`hengxin-smart-image/backend/tests/test_overseas_archive_assignment.py:47`、`:68`；本轮 HTTP 验证通过，未重跑 UI。 |
| 1048：无/部分/全部归档，两工作流，隔离其他任务 | `hengxin-smart-image/backend/tests/test_overseas_task_deletion.py:67`；`hengxin-smart-image/backend/tests/test_overseas_task_deletion_legacy.py:26`；新增 `hengxin-smart-image/backend/tests/test_overseas_task_deletion_cli_links.py:33`，本轮通过。 |
| 1049：真实内容校验、独立访问、下载可打开、越权拒绝 | `hengxin-smart-image/backend/tests/test_overseas_task_deletion.py:101` 解开真实 ZIP 并对成员取 SHA-256；`hengxin-smart-image/backend/tests/test_overseas_archive_assignment.py:26`、`:40`，本轮通过。 |
| 1050：先停止、归档顺序、迟到/重复/重启不复活 | `hengxin-smart-image/backend/app/overseas/tasks/cleanup.py:19`、`:51`；`hengxin-smart-image/backend/tests/test_overseas_task_deletion.py:130` 和 `hengxin-smart-image/backend/tests/test_overseas_task_deletion_legacy.py:105` 验证迟到结果/写入拒绝；`:117` 验证重复请求，faults.py:44 验证新 session 恢复。真实 PostgreSQL 并发本轮未重跑，锁协议未修改。 |
| 1051：保护/清理/状态不明故障不误报，恢复可继续 | `hengxin-smart-image/backend/tests/test_overseas_task_deletion_faults.py:19`、`:44`、`:68`、`:112`；`hengxin-smart-image/backend/tests/test_overseas_task_deletion_cli_links.py:93`，本轮全部通过。 |

本次功能完整实现，无未实现的专项条目；UI 引导及视觉：原候选无 UI 修改，按派发范围不重验；Spec 漂移：两个候选文件未添加 API、页面、表或依赖，未发现 scope creep。

## Stage 2：Code Quality — FAIL

### MEDIUM：新归档断言把 ZIP 封装时间戳当成图片内容

- 位置：`hengxin-smart-image/backend/tests/test_overseas_task_deletion_cli_links.py:49`、`:62`。
- 实际问题：对删除前后两次下载的 ZIP 整体 bytes 做相等断言。`hengxin-smart-image/backend/app/overseas/archives/service.py:114` 使用文件名字符串调用 `ZipFile.writestr`，每次写入当前时间；两次下载跨 ZIP 时间刻度即可不同，与图片是否保留无关。[Python 3.12 官方 writestr 文档](https://docs.python.org/3.12/library/zipfile.html#zipfile.ZipFile.writestr) 明确说明字符串名称会使用当前日期时间。
- 实证：只在临时 pytest 插件里包装测试模块的 `cleanup_once`，真实清理返回后 `time.sleep(2.1)`，不修改业务模块。原候选 studio 用例在第 62 行失败，ZIP 第 10 字节不同；删除目录及 deleted/404 断言已经先通过。
- 影响：正常运行也可能因 CPU、I/O 或时钟边界导致 CI 随机失败；“38 passed”仅证明这次未跨边界，不能消除缺陷。
- 修复要求：验证两次响应 200，使用 `ZipFile(BytesIO(...))` 比较成员文件名与成员内容/校验值，并确认数量；可继承 `hengxin-smart-image/backend/tests/test_overseas_task_deletion.py:106` 的成员级校验。修复后以慢清理/跨时间刻度重验。不应修改生产 ZIP 行为迁就该测试。

### 其他质量与安全结论

- 命名、结构：`hengxin-smart-image/backend/app/overseas/tasks/cleanup_files.py:75` 的 helper 只负责识别允许的 CLI 链接；原文件 139 行、新测试 112 行，均小于 300。延续既有 Python 风格，无新增 any、重复业务实现或异常吞没。
- 安全：`hengxin-smart-image/backend/app/overseas/tasks/cleanup_files.py:79` 的能力门槛与 `:137` 的 rmtree 配合；[Python 3.12 官方 rmtree 文档](https://docs.python.org/3.12/library/shutil.html#shutil.rmtree)说明支持 fd 操作的平台使用抗符号链接攻击实现。候选的精确 `/opt/codex` 是既有沙箱合同，不是用户可控执行命令。真实 Linux 测试证明链接目标内容不变，目录目标和父链被拒绝。
- 安全扫描：对两份候选运行 rg 搜索 eval、innerHTML、dangerouslySetInnerHTML、VITE 密钥变量、/Users/、常见密钥前缀/API_KEY/password 赋值，无匹配。新增代码未构造 SQL、shell、网络请求或密钥。未发现本次引入的 HIGH 安全问题。
- 测试真实性：`hengxin-smart-image/backend/tests/test_overseas_task_deletion_cli_links.py:25` 创建真实 symlink；`:90` 创建真实 hardlink；`:56` 发 HTTP 并调用真正维护流程，未 mock rmtree。旧模块运行出现 3 个预期失败，证明确实检测原缺陷。对象存储仍为隔离字节夹具，不能声称已做生产 S3 删除验证。
- UI 视觉：两份候选无 UI 变更，不适用邻居页面渲染比较。

## 独立验证原始输出

镜像：`hx-overseas-delete-skills-test:local`，image ID `sha256:f166b6cc7abd92c018069a0df334e69e6d924c65827105ed624769c49a47e84c`。所有容器 `--rm --network none`；冻结输入只读挂载 `/review-input`，解包到 `/tmp/review`。实体目标测试额外使用 `--user 999:999 --tmpfs /opt:rw,mode=1777`，不接触宿主机 `/opt`。

冻结候选运行：

```text
python -m pytest tests/test_overseas_task_deletion_cli_links.py tests/test_overseas_task_deletion.py tests/test_overseas_task_deletion_faults.py tests/test_overseas_task_deletion_legacy.py tests/test_overseas_task_deletion_process.py tests/test_overseas_archive_assignment.py -q -p no:cacheprovider
FROZEN_CANDIDATE_BACKEND: HEAD 4d2d07f + two review files
3.12.10 (main, May 21 2025, 23:34:56) [GCC 12.2.0]
rmtree.avoids_symlink_attacks=True
......................................                                   [100%]
=============================== warnings summary ===============================
../../../../app/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  /app/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

../../../../app/.venv/lib/python3.12/site-packages/starlette/testclient.py:53
  /app/.venv/lib/python3.12/site-packages/starlette/testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
38 passed, 2 warnings in 11.63s
```

旧 HEAD 模块加新测试，`-q --tb=no -p no:cacheprovider` 的失败摘要（同上两条警告省略）：

```text
FFF......                                                                [100%]
=========================== short test summary info ============================
FAILED tests/test_overseas_task_deletion_cli_links.py::test_cli_shims_allow_real_cleanup_and_archive_survives[legacy]
FAILED tests/test_overseas_task_deletion_cli_links.py::test_cli_shims_allow_real_cleanup_and_archive_survives[studio]
FAILED tests/test_overseas_task_deletion_cli_links.py::test_cli_lookalikes_block_before_any_object_erasure[target]
3 failed, 6 passed, 2 warnings in 3.74s
EXPECTED_OLD_CODE_EXIT=1
```

uid 999 链接边界与编译结果，进程退出 0：

```text
uid=999 resistant=True
PASS dangling exact-target shims removed
PASS real /opt/codex bytes unchanged after workspace erasure: c1bfc350d914157fa9afeb62e829faff93b10a776f544cab7ae4e8d9d79e4ffb
PASS exact-target directory symlink rejected before erasure
PASS root_link rejected
PASS workspace_link rejected
PASS parent_link rejected
PASS traversal rejected
PASS relative_target rejected
Compiling '/tmp/review/hengxin-smart-image/backend/app/overseas/tasks/cleanup_files.py'...
Compiling '/tmp/review/hengxin-smart-image/backend/tests/test_overseas_task_deletion_cli_links.py'...
compileall exit=0
```

新增测试时序缺陷，`-k studio --tb=short`，真实 pytest 退出 1（测试夹具包装器记录预期失败；同上两条警告省略）：

```text
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_cli_shims_allow_real_cleanup_and_archive_survives[studio] ________
tests/test_overseas_task_deletion_cli_links.py:62: in test_cli_shims_allow_real_cleanup_and_archive_survives
    assert client.get(ROOT + '/archives/' + archive['id'] + '/download').content == original
E   AssertionError: assert b'PK\x03\x04\...0\x00\x00\x00' == b'PK\x03\x04\...0\x00\x00\x00'
E     
E     At index 10 diff: b'\xf7' != b'\xf6'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED tests/test_overseas_task_deletion_cli_links.py::test_cli_shims_allow_real_cleanup_and_archive_survives[studio]
1 failed, 8 deselected, 2 warnings in 4.52s
SLOW_CLEANUP_EXIT=1
```

候选两文件 `git diff --check` 退出 0、无输出。前端 typecheck 是主 Agent 提供的先前证据，本轮专项没有重复执行，也没有把它冒充 reviewer 实测。

## 交接

原候选功能及链接安全专项通过；新增测试有可复现的时序缺陷，Stage 2 未通过。修正测试后重新固定最终候选，连同删除确认新需求交 fresh reviewer；由主 Agent 按实际两阶段结果登记。不得向 `.needs-review` 写 clean，不得使用本报告批准新快照或生产删除。
