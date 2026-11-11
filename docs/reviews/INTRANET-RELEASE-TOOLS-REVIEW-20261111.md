# 内网专用发布工具独立审查

- 审查日期：2026-11-11。
- 最终 candidateId：`39ff5e2b95ef21a0a0000ab2679e534e779c21d6ab03e3ac612042f386019e54`。
- 原 candidateId：`a4bf76a486655b8c4ec543e3812a037b1500791868908bfebc91a022e777f660`，不予批准，原因见快照变化。
- 范围：`Product-Spec.md:1458`、`DEV-PLAN.md:1674` 引用的内网发布工具合同；`scripts/release/intranet/*.py`；旧 `hengxin-smart-image/scripts/migration245/unify_release.py` 的 REUSABLE/prepare 适配；相关使用文档及 README 链接。
- 方法：遵循 `.agents/skills/code-review/SKILL.md`，先逐项核对 Spec，再审查质量、安全和测试真实性。独立复跑本地测试；未连接服务器、未执行生产发布、未修改实现。
- Stage 1：**PASS（本次送审代码范围）**。
- Stage 2：**PASS（本次送审代码范围）**。
- 最终安装与生产不重启验收尚未由 reviewer 验证。上述 PASS 允许登记此代码快照，不等于 `docs/INTRANET-RELEASE-TOOLS.md:18`、`:19` 的生产验收已经完成。

## 快照变化与已修复问题

审查期间主 Agent 发现旧 `backend_inputs` 用 `'/requirements' in n` 筛选依赖，将 `frontend/assets/requirements-*.js` 也纳入依赖比较；正常前端变化会被误判为依赖升级并阻断。主 Agent 修改了 `snapshot.py` 和 `test_release.py`，重新提供最终 candidateId。

复核结果：`scripts/release/intranet/snapshot.py:34` 现仅匹配后端根 requirements 前缀，以及明确的依赖/迁移配置；`scripts/release/intranet/test_release.py:75` 用不同 requirements 前端 chunk 验证可正常兼容。最终快照重新执行全部 77 项测试通过。原快照的测试结果未用来批准新版本。

## Stage 1：逐条 Spec Compliance

| 合同条目 | 结论 | 代码及验证证据 |
| --- | --- | --- |
| 固定内网目标，不操作旧公网（合同第 5 行） | 完整实现 | `release.py:171`、`stage.py:62` 在打开状态目录前验证 hostname/root；`test_release.py:149` 验证错误主机不会打开 Store。命令没有远程主机选项。 |
| 明确 Git 提交、工作区隔离、内网前端和文件摘要（第 7 行） | 完整实现 | `package_release.py:63` 解析完整提交；`:72` 对照 Git blob 核验 archive 字节；`:121` 隔离环境；`:141` 固定工具链、冻结锁文件、typecheck 和 Vite build；`:184` 写摘要。`test_package_release.py:85` 验证脏工作区、环境文件及旧 dist 不进入制品。真实构建日志见下文。 |
| 独立候选目录、预检时业务继续运行（第 7 行） | 完整实现 | `stage.py:15` 拒绝已有目录、非普通文件及越界路径，先校验完整清单再写入；`release.py:51` 做当前实查与兼容检查后 prepare；旧 `unify_release.py:243` 使用候选导入与运行环境探针，`:277` 仅保存候选和原配置。`test_engine.py:76` 断言 prepare 未调用 stop/app_command。 |
| 共用旧发布锁、原子保存 current/previous/pending（第 8 行） | 完整实现 | `release.py:15` 直接加载旧 Store，`:176` 在整个命令持锁；`release-retention-state.py:91` 提供跨进程锁、`:119` 原子替换并 fsync；`release.py:46` 初始化 previous=None，`:116` 仅验证后推进台账。`test_release.py:49` 真实争锁，`:80` 验证推进顺序。 |
| 不能仅凭镜像，记录并核验真实源文件、前端、解释器、数据库（第 8 行） | 完整实现，生产证据待安装阶段 | `snapshot.py:77` 比较容器挂载及实际容器内 app 文件摘要、7 个原生进程实际 cwd、解释器身份与安装依赖摘要；`:104` 核对实际 HTTP index；`:107` 以原进程 UID/GID/env 执行两侧 runtime_check；`:112` 核对 CLI/bwrap 二进制；`:58` 读取两库 Alembic revision。服务清单复用旧 `unify_release.py:28`、`:37`，共 8 个 Python 容器与 7 个原生服务。 |
| 普通发布先备份数据库及账号配置（第 9、52 行） | 完整实现 | `release.py:106` 在 deploying/切换前执行备份；`operations.py:39` 对两侧 PostgreSQL 执行 custom-format pg_dump 并 pg_restore --list 校验，随后保存账号、认证和内网配置归档。未执行任何数据库还原命令。真实生产备份未在本次审查中执行。 |
| 关闭接纳、排空、统一切换、健康与两侧运行环境验证（第 9 行） | 完整实现 | `engine.py:159` 先持久化事务，再关闭入口；`:162` 排空；`:173` 才写候选；`:177` 启动与核验。复用旧 `unify_release.py:397` 的 broker/数据库/active/reserved/scheduled 排空和 `:470` 健康检查。`release.py:112` 再做真实 runtime 快照及运行时不变校验。 |
| 失败恢复原入口；进程中断可从持久事务恢复（第 9、10 行） | 完整实现 | `engine.py:104` 在暂停消费者和改 socket 权限前写 journal；`:116` 在停机/切换/启动前写阶段；`:212` 恢复原配置并保留可重入状态；`release.py:86` 完整复核 before 后才允许清理 pending。`test_engine.py:141` 注入切换中断后从磁盘恢复，`:209` 验证恢复中断不能冒充已应用，`:221` 验证 socket journal。 |
| 状态不明保持阻断，不强杀任务，不覆盖 venv，不倒灌数据库（第 10 行） | 完整实现 | `engine.py:58` 校验原配置/候选/备份/目录清单；`:193` 对部分启动或忙碌状态拒绝停止；`release.py:88` 遇 schema/data drift 拒绝自动恢复。旧 `unify_release.py:108` 使用无限优雅停止，`:53` 禁止 SIGKILL 升级。`test_engine.py:172`、`:184`、`:192` 与 `test_release.py:128` 覆盖忙任务/部分凭据启动/外来配置/schema 漂移。 |
| 依赖/迁移变化阻断，另行升级（第 10、54 行） | 完整实现 | `snapshot.py:34`、`:41` 比较后端锁文件、迁移、运行时输入；`:45` 纯前端还比较全部 backend/app。`test_release.py:63`、`:69`、`:75` 覆盖变更阻断及前端 chunk 不误判。本次按合同兼容已有无 runtime_inputs 的历史清单，不声称自动升级依赖。 |
| 纯前端仅切 web（第 9、38 行） | 完整实现 | `operations.py:70` 仅替换 web 的静态目录挂载；`:111` 和 `:102` 仅调用 `app_command('up', ('domestic-web',))`；`test_stage_web.py:82` 与 `:96` 验证正常/失败恢复均只操作 web。 |
| 保留当前/上一成功/在用/未完成引用，不自动删除旧源码、依赖、镜像或备份（第 11、50 行） | 完整实现 | `release.py:116`、`:126`、`:141` 保存 current/previous/last/pending；无清理旧发布入口。`operations.py:12` 额外保留旧前端 hash assets，`:26` 拒绝同名异内容。唯一运行时 unlink 为 `engine.py:247` 恢复本事务新增 drop-in；打包 `package_release.py:38` 删除本次 mkdtemp 临时目录，与生产源目录无关。 |
| status/verify/init/cancel/recover/rollback 使用说明真实（第 42 至 47 行） | 完整实现 | `release.py:41` 重复 init 只核对；`:126` recover 复核后清 pending；`:141` rollback 使用最近成功事务的原配置；`:136` 清 previous/last 防止翻转；`:151` 阻止取消已开始事务；`:164` 命令参数均实际注册。`test_release.py:42`、`:106`、`:113`、`:121`、`:137` 覆盖这些门禁。 |
| 此次安装只读登记、不重启、不调用模型，最终路径与真实 UID 验收（第 13、18、19 行） | 实现支持；部署验收待执行 | `release.py:41` init 仅 capture/save；`snapshot.py:77` capture 为只读核验和本地 runtime_check，无发布/模型调用；`:171` 主机门禁已实现。安装及初始化前后 PID/容器身份比对须由主 Agent 在安装阶段补证，本 reviewer 未连接服务器，不作生产成功声明。 |

完整实现项如上；本次送审代码范围内无剩余部分实现、未实现或 HIGH 问题。UI 一致性、邻居页面视觉对比不适用：本次新增的是命令行发布工具，没有新增产品页面或视觉变更。Spec 漂移未发现：命令与合同日常使用逐项对应，无新增业务接口、表或用户功能。

## Stage 2：Code Quality、安全和测试真实性

| 维度 | 结论及证据 |
| --- | --- |
| 模块职责和行数 | PASS。`package_release.py` 261 行、`stage.py` 74、`snapshot.py` 135、`operations.py` 126、`engine.py` 256、`release.py` 199；四个测试文件分别 236/199/180/115 行，全部低于 300 行。旧 one-shot 为既有基线，仅审查 `unify_release.py:25`、`:286`、`:306` 的复用适配，不要求本轮重构旧文件。 |
| 旧策略复用 | PASS。`engine.py:11` 加载旧发布模块，复用 probe/drain/gate/health；`release.py:15` 复用既有 Store，未另造公网部署或清理流程。`test_engine.py:86` 验证旧 one-shot 仍拒绝已有 drop-in。 |
| 故障处理 | PASS。`engine.py:135` 与 `:212` 分开 apply/recover；`release.py:99` 验证失败先恢复并保留 pending，未知状态不记成功。`operations.py:91` 前端恢复拒绝外来 compose。测试明确检查恢复状态与配置字节，不仅断言函数调用成功。 |
| 密钥、命令注入 | PASS。本轮扫描无 eval、shell=True、SQL 字符串拼接或真实硬编码密钥。`package_release.py:121` 白名单构建环境、`:49` 排除敏感文件；`:109` 检查私钥头。测试中的 SECRET/NPM_TOKEN 是隔离的字面量夹具（`test_package_release.py:165`），不是凭据。命令采用 argv 数组，目标入口固定。 |
| 私有事务与错误输出 | PASS。`release.py:63` 建 0700 事务父目录；旧 `unify_release.py:86`、`:295` 使用 0600 文件/0700 工作目录；Store 的 mkstemp 原子文件默认私有。`unify_release.py:60` 抑制子进程 stdout/stderr 异常泄露；`release.py:189` 仅输出版本/阶段，不输出环境；`:196` 隐藏第三方异常细节。 |
| 路径与权限 | PASS。`stage.py:28` 拒绝非普通成员、路径越界、重复及超限包；旧 `unify_release.py:69` 校验 root 所有权、链接与组/全局可写权限；`:167` 校验完整 manifest 及 renderer 0755。`test_stage_web.py:58`、`:68` 验证路径穿越/符号链接在写入前被拒绝。 |
| 测试真实性与边界 | PASS（已声明隔离边界）。Git 打包用真实临时仓库，争锁用真实 Store；engine 使用真实临时配置和持久 journal，但将 Docker/systemd/进程控制 mock，足以验证事务控制，不能替代真实 Linux 部署。`test_engine.py:13`、`test_release.py:15`、`test_stage_web.py:31` 清楚显示 mock 范围。备份执行、snapshot.capture 和真实 UID runtime 成功仍需安装阶段证据，不将 77 项通过表述为生产恢复演练。 |

没有需要修复的已证实 HIGH/MEDIUM 问题。未进行超出用户批准范围的生产故障注入、依赖升级或旧源清理。

## 独立验证与原始输出

实际可用解释器在 `hengxin-smart-image/backend/.venv/Scripts/python.exe`；主 Agent 交接文字中的根 `.venv/Scripts/python.exe` 不存在，定位后使用项目已有解释器执行，未安装额外依赖。

最终候选独立复跑：

```text
.\hengxin-smart-image\backend\.venv\Scripts\python.exe -m pytest scripts/release/intranet hengxin-smart-image/scripts/migration245/test_unify_release.py -q
................................................................. [ 84%]
............                                                             [100%]
77 passed, 7 subtests passed in 13.24s
```

注：进度点在终端分两次返回；汇总行以上为两次输出拼接。对新增 10 个 Python 文件和适配的旧脚本调用 `compile()` 验证语法，原始输出：

```text
PYTHON_COMPILE_OK 11 files
```

真实前端打包证据来自主 Agent 已执行并保存的 `output/intranet-tools/package/build-verified.log:110`、`:716`，reviewer 读取核对，未重复下载/构建。原始关键输出：

```text
> hengxin-smart-image-frontend@0.2.67 typecheck C:\Users\82358\AppData\Local\Temp\hx-release-t8foz9zp\source\frontend
> vue-tsc --noEmit
✓ built in 52.80s
{"commit": "ca186c8de0412206493eba6f31f2e11da5b66b00", "output": "D:\\Work_Project\\hengxin-smart-image\\output\\intranet-tools\\package\\release-ca186c8-verified.tar.gz", "files": 1116}
```

日志第 1、2、108、113 行含 pnpm 现有 package.json 字段被忽略的警告；日志仍完成冻结依赖安装、类型检查和构建。本次工具代码未修改这些前端依赖字段，不将该警告描述为零警告构建。

## 交接

由主 Agent 先核对当前内容仍为最终 candidateId，再按 `docs/HARNESS-REVIEW.md` 用本报告登记两阶段 PASS。不得向 `.needs-review` 写 clean。如后续代码变化，重新固定快照并审查差异；安装后的只读核验、真实 UID/runtime 与无重启证据应单独归档，不能由本报告代替。
