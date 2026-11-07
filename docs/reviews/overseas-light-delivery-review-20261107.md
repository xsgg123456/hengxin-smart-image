# 海外轻量化交付候选独立审查 · 2026-11-07

## 快照、范围与结论

- 主 Agent 指定 candidateId：`3523949e670527c493c73af6d08b2f95f9594937699575ad7e19dfb4c3e8ef95`。审查开始和写报告前 `review-status.currentId` 均为此值，`approved: false`。受控文件相对已审快照的差异为 6 个 `scripts/release/overseas-light-*.py` 和 5 个 `test_overseas_light_*.py`，清单见文末状态输出。
- 范围：`Product-Spec.md:1–27`、`DEV-PLAN.md:1–7`、`Design-Brief.md:1–3`、`hengxin-smart-image/frontend/preview-overseas-light/`，海外 management、tasks、archives 相关业务代码及测试，以及上述 11 个发布文件；另核对 `docs/OVERSEAS-LIGHT-RELEASE-20261107.md:3–7`。业务代码提交为 `0b9d68b`。`git diff --name-status HEAD -- hengxin-smart-image` 和对应 untracked 查询输出均为空，因此业务工作树与该提交一致；其原独立审查见 `docs/reviews/overseas-light-complete-20261107.md`。
- 上轮发布候选 `efa1def865fa3f9d5b74ec7b98f50eaf1ce9b8fe1deef6d478ac494e1dc0a63ef7e096f90d1ead70` 的逐文件内容和哈希清单本审无法取得，无法独立证明候选间只修改一项测试；本次重新阅读当前发布链、执行当前测试和验证变异，不将其 Stage 2 失败覆盖为 PASS。上轮具体问题及范围见 `docs/reviews/overseas-light-verified-release-20261107.md`。
- **Stage 1：PASS；Stage 2：PASS。** 以上结论仅限所列源码、模拟浏览器和隔离测试范围，没有发现 HIGH 或需阻断此候选的 MEDIUM。正式包及生产验收不在本结论内。主 Agent 应在确认结束状态仍为同一 candidateId 后按 `docs/HARNESS-REVIEW.md:8–10` 登记两阶段 PASS，不写 `.needs-review` 的 clean 代替凭据。
- 本审未修改代码或测试，未连接生产，未部署，未调用付费模型。报告是唯一新增的仓库文件；隔离测试的临时文件不在仓库。

## Stage 1：Spec 与发布约束

下表业务路径相对 `hengxin-smart-image/`；文档和 `scripts/` 相对仓库根目录。先前报告中的业务测试针对相同的 `0b9d68b` 业务内容，本次另重跑模拟浏览器，未把先前结果冒充本次实测。

| 需求条目 | 结论与证据 |
| --- | --- |
| `Product-Spec.md:7` 合并入口、旧地址、权限 | 匹配。`frontend/src/identity-main.ts:21–23` 提供统一地址和旧地址重定向；`backend/app/overseas/management/router.py:13–35` 要求 `stats.read`，`management/facts.py:51–53` 先按权限限定任务。本次浏览器重新执行旧地址和下钻测试。 |
| `Product-Spec.md:8` 实际请求次数、幂等、取消/失败和北京时间 | 匹配。`backend/app/overseas/studio/service.py:60–101` 建立或复用请求，`management/usage.py:30–48` 聚合发起人，`management/facts.py:14–38` 处理时间范围；`backend/tests/test_overseas_lightweight.py:16–56` 覆盖重放、取消、重发、失败和边界，同一业务提交的独立后端结果见先前完整报告。 |
| `Product-Spec.md:9–10` 历史缺失、留存说明、图片数和停用人员 | 匹配。`management/facts.py:51–59` 与 `management/usage.py:34–48` 分别处理权限与实际操作者/输出；`frontend/src/views/overseas/admin/OverseasActivityPage.vue:3,27` 明示历史和删除数据的边界；`backend/tests/test_overseas_lightweight.py:33–69` 覆盖未知历史、停用人员和权限夹具。 |
| `Product-Spec.md:11` 四类概况、人员和状态下钻、筛选分页、详情 | 匹配。`management/usage.py:8–16`、`management/monitor.py:11–25`、`OverseasActivityPage.vue:23–30,59–87`；本次隔离浏览器重新执行人员/状态下钻、取消和错误重试。 |
| `Product-Spec.md:15` 实际归档人、组合搜索、先筛后分页 | 匹配。`backend/app/overseas/archives/service.py:63–87` 在计数和分页前使用实际归档事件及关键词筛选；`frontend/src/views/overseas/OverseasArchivePage.vue:4–5,17–19` 显示筛选与参与提示；`backend/tests/test_overseas_archive_audit.py:19–46` 覆盖多人和组合条件。 |
| `Product-Spec.md:16` 可见真实候选、历史缺失、源任务删除和原有操作 | 匹配。`archives/service.py:90–116`、`archives/audit.py:9–35`、`OverseasArchivePage.vue:21–26,46–50,64–67`；`backend/tests/test_overseas_archive_audit.py:47–70` 覆盖源任务删除和权限；本次浏览器用模拟 API 检查筛选与删除。 |
| `Product-Spec.md:20` 当前负责人、停用成员、改派和相关范围 | 匹配。`backend/app/overseas/tasks/queries.py:84–91,127–131` 与 `frontend/src/views/overseas/OverseasTasksPage.vue:98–102,146–156`；本次模拟 API 浏览器执行改派与删除。 |
| `Product-Spec.md:21` 20 条、顶部底部分页、服务端先过滤及返回 | 匹配。`tasks/queries.py:111–124`、`OverseasTasksPage.vue:37–40,153–158`；本次模拟浏览器覆盖分页范围和详情返回。 |
| `Product-Spec.md:22` 状态分组、旧 submitted、返工、删除异常 | 匹配。`tasks/queries.py:77–80,92–94`、`frontend/src/views/overseas/task-status.ts:7–30`、`backend/tests/test_overseas_lightweight.py:78–105`；本次模拟浏览器再次检查历史状态。 |
| `Product-Spec.md:23` 分批归档、显式完成和解冻 | 源码匹配：`backend/app/overseas/studio/service.py:123–191` 分开处理工作台归档、完成和解冻。本次未操作生产任务。 |
| `Product-Spec.md:27`、`Design-Brief.md:1–3` 预览、空错态和窄屏 | 已测源码范围匹配：`frontend/tests/overseas-lightweight.browser.mjs:24–36,87–172`，本次真实组件配模拟 API 重跑通过；1280×900 对照与 390px 横滚见下。前次同业务提交对确认预览的按钮颜色等数值检查见 `docs/reviews/overseas-light-complete-20261107.md` 的“确认预览复核”。正式构建、真实权限数据及生产验收仍待执行。 |
| `DEV-PLAN.md:7`、发布记录 `:7`：SVG、冲突和目标目录保护 | 匹配已测范围。`scripts/release/overseas-light-package.py:30–35,64–71` 只归一非哈希公共 SVG；`overseas-light-frontend.py:122–148,177–219` 检查同名冲突、仅复制本次资产；`overseas-light-guard.py:61–79,139–170,176–244` 管理锁、收据及权限。真实文件系统隔离安装/回退与竞态测试本次通过。 |
| 发布记录 `:7`：强制终止恢复、共享资源、回退和入口保护 | 匹配已测范围。`overseas-light-guard.py:150–170,176–244` 按设备和 inode 恢复权限；`overseas-light-frontend.py:65–97,222–240` 提供唯一临时文件与回退；`overseas-light-deploy.py:194–235` 在前端回退失败后尝试恢复旧 API，并在恢复或保护检查出错时不重开入口。隔离测试见 `test_overseas_light_guard_recovery.py:11–72,75–106`、`test_overseas_light_installer.py:87–152` 和 `test_overseas_light_rollback.py:24–155`。代理、容器和服务在顺序测试中为桩，不能证明真实主机回退。 |
| 包与合同 | 匹配已测范围。`scripts/release/overseas-light-runtime.py:23–27,30–66` 要求助手清单并验证哈希、范围和入口；`overseas-light-package.py:97–112` 将助手纳入审查身份绑定的包。`test_overseas_light_release.py:170–202` 本次通过包篡改和额外文件拒绝测试；前次报告对真实助手的合成包与合同 AST 比较是额外证据，非本次正式构建。 |

**部分实现／未实现：** 以上指定源码范围未发现其他缺失或部分实现。`Product-Spec.md:27`、`DEV-PLAN.md:7` 所要求的最终提交包、生产安装和线上只读数据验收仍属后续工作，不能据本报告声明已部署或完成交付。

**Spec 漂移：** 派发范围未发现额外产品页面、表或无需求依据的 API；`overseas-light-deploy.py:247–265` 的权限恢复入口对应发布记录 `:7`。本次不是全仓漂移审计。

## Stage 2：质量、测试真实性、安全及视觉

- **上轮 MEDIUM 已修复并经变异验证。** `scripts/release/test_overseas_light_release.py:138–164` 对该测试的无关 `private` 目录记录事前设备、inode 和模式，拦截 `Path.chmod` 及 `os.fchmod`，通过 `os.fstat` 把文件描述符对应到目录身份；它同时比较事后身份和模式。现有生产路径分别通过 `overseas-light-frontend.py:78–82` 和 `overseas-light-guard.py:139–147,209–216` 使用 `os.fchmod`。本审无网络的只读源码 Linux root 容器内，先验证未注入时原测试通过，再在测试自己的真实安装后对 `private` 的文件描述符注入持久及瞬时 `fchmod`；两种情况都在测试第 163 行断言失败，即使瞬时变更已恢复原模式也能捕获。原始结果见下。此验证覆盖当前 Python 调用路径，不声称拦截所有可能的原生系统调用或其他 chmod API。
- **测试隔离：PASS（下述边界内）。** `test_overseas_light_rollback.py:17–20` 将 APP 指向每个 `tmp_path` 并替换保护上下文；`:24–155` 对网络门禁、容器与服务操作采用桩。真实目录及权限测试分别在 `test_overseas_light_installer.py:15–47`、`test_overseas_light_guard.py:11–58`、`test_overseas_light_guard_recovery.py:11–72,75–182` 的临时目录执行。重跑 Linux 全套时使用无网络、容器根和源码只读、`/tmp` 与 `/opt` 临时文件系统，仅挂载本地发布脚本只读；假 `/opt` 的设备、inode、模式、ctime 未变，锁文件不存在，所列 Python 层路径/权限钩子未发现 `/opt` 调用。该钩子不是完整系统调用跟踪；无生产路径挂载，不代表真实生产部署测试。
- **代码质量：PASS（派发的 11 个发布文件）。** 全部可执行 Python 语法编译，44–272 行，未超过 300 行；`overseas-light-deploy.py:23–35` 将发布、前端及保护职责拆分，失败处理见 `:194–235`。代码行数和原始编译输出见下。该结论不涵盖全仓。
- **静态安全扫描：PASS（有界扫描）。** 对 11 个发布文件扫描 `eval`、`exec`、`dangerouslySetInnerHTML`、`innerHTML`、`shell=True`、前端密钥变量、明文密码模式、常见密钥前缀及 `/Users/`，`rg` 退出 1 且无匹配。业务权限和参数化查询证据分别见 `management/facts.py:45–53`、`archives/service.py:63–78`、`tasks/queries.py:84–119`；此扫描不覆盖密钥历史或完整渗透测试。
- **实际邻页视觉：PASS（隔离模拟 API，1280×900）。** 本次启动无 API 代理的本地 Vite，浏览器阻断或模拟所有外部及 API 请求，实际打开“系统配置”和“调用与执行”并查看两页实时渲染；均继承海外 Shell、白底卡片、蓝色操作和 Element 控件，符合 `Design-Brief.md:1–3`。截图仅在内存中查看，没有新增截图文件；同一业务提交的既有截图为 `output/playwright/review-light-final-neighbor.png` 和 `output/playwright/review-light-final-activity.png`。本次测得日期控件右界 621px，重置按钮左界 635px；390px 任务表局部横滚 762px。模拟数据及开发源码不能证明正式包或线上视觉。

## 本次独立验证原始输出

### Linux root 隔离全套

镜像 `hengxin-smart-image-backend:phase25`，`--network=none --read-only --user 0`，只读挂载 `scripts/release`，独立 `/tmp` 和 `/opt` tmpfs。先前一次自编钩子包装在测试通过后因自身读取被监视的锁路径而报错；下列为纠正自检后重新完整执行的结果，退出 0：

```text
........................                                                 [100%]
24 passed in 4.50s
PYTEST_EXIT 0
PYTHON_LEVEL_OPT_HITS []
SENTINEL_METADATA_UNCHANGED True
LOCK_ABSENT True
```

### `fchmod` 变异试验

只在测试进程内包装安装调用，不改代码文件；对测试创建的真实临时目录打开文件描述符，执行后输出，退出 0：

```text
CONTROL PASSED {}
PERSISTENT ASSERTION_FAILED {'target_identity': (170, 45), 'before': '0o755', 'during': '0o745', 'after': '0o745', 'failed_line': 163}
TRANSIENT ASSERTION_FAILED {'target_identity': (170, 75), 'before': '0o755', 'during': '0o745', 'after': '0o755', 'failed_line': 163}
MUTATION_CHECK_OK
```

### Windows 全套

项目 backend `.venv` 的 Python，`-B -m pytest -q -ra -p no:cacheprovider` 加上述五个测试文件；退出 0：

```text
...............s.sssssss                                                 [100%]
=========================== short test summary info ===========================
SKIPPED [1] hengxin-smart-image\backend\.venv\Lib\site-packages\_pytest\unittest.py:523: Requires POSIX filesystem semantics
SKIPPED [7] hengxin-smart-image\backend\.venv\Lib\site-packages\_pytest\unittest.py:523: Requires POSIX root execution
16 passed, 8 skipped in 0.97s
```

### 隔离浏览器

直接执行现有 `frontend/tests/overseas-lightweight.browser.mjs` 的内存副本，只去掉截图及创建截图目录语句；退出 0：

```text
PASS: 调用下钻、排队取消、负责人改派/删除、历史状态、分页范围、归档筛选/删除、错误重试、三页390px控件及资源请求
```

同样执行 `output/playwright/review-light-final-neighbor.mjs` 的内存副本，截图传入审查会话而非写入文件；退出 0：

```text
390px task table horizontal scroll {"width":308,"full":1070,"left":762}
neighbor settings rendered
activity geometry {".activity-filters .date-filter":{"x":321,"y":420.671875,"right":621,"width":300,"minWidth":"auto","maxWidth":"none"},".activity-filters .el-date-editor":{"x":321,"y":448.171875,"right":621,"width":300,"minWidth":"auto","maxWidth":"100%"},".activity-filters > .el-button":{"x":635,"y":452.171875,"right":723,"width":88,"minWidth":"auto","maxWidth":"none"}}
PASS: 邻居页面及任务状态横滚
```

隔离浏览器及 Vite 已停止。自动审批拦截了对临时缓存 `C:\Users\82358\AppData\Local\Temp\hx-review-vite-Q8vUBJ` 的递归删除，工具给出的原因仅为 `blocked by policy`；缓存不在仓库，也不属于候选代码。

### Python 语法编译

对当前 11 个文件以 `compile(path.read_bytes(), str(path), 'exec')` 执行，退出 0；这是语法编译，不是正式包构建：

```text
scripts\release\overseas-light-contract.py 44 lines
scripts\release\overseas-light-deploy.py 272 lines
scripts\release\overseas-light-frontend.py 243 lines
scripts\release\overseas-light-guard.py 244 lines
scripts\release\overseas-light-package.py 123 lines
scripts\release\overseas-light-runtime.py 70 lines
scripts\release\test_overseas_light_guard.py 120 lines
scripts\release\test_overseas_light_guard_recovery.py 189 lines
scripts\release\test_overseas_light_installer.py 159 lines
scripts\release\test_overseas_light_release.py 202 lines
scripts\release\test_overseas_light_rollback.py 155 lines
COMPILE_OK 11
```

`git diff --check` 退出 0；原始输出仅为 deploy、runtime、test_release 的 CRLF 将转 LF 警告。

### 审查期间状态

开始与写报告前的 `review-status` 输出相同：

```json
{"currentId": "3523949e670527c493c73af6d08b2f95f9594937699575ad7e19dfb4c3e8ef95", "reviewedId": "e5f6f10a2a368742bf9aca90c2bb2449fe63ba9fb616196bc49d68b8e47672d9", "changedFiles": ["scripts/release/overseas-light-contract.py", "scripts/release/overseas-light-deploy.py", "scripts/release/overseas-light-frontend.py", "scripts/release/overseas-light-guard.py", "scripts/release/overseas-light-package.py", "scripts/release/overseas-light-runtime.py", "scripts/release/test_overseas_light_guard.py", "scripts/release/test_overseas_light_guard_recovery.py", "scripts/release/test_overseas_light_installer.py", "scripts/release/test_overseas_light_release.py", "scripts/release/test_overseas_light_rollback.py"], "approved": false}
```

报告写入后再次执行 `review-status`，输出与上面完全一致：`currentId` 仍为 `3523949e670527c493c73af6d08b2f95f9594937699575ad7e19dfb4c3e8ef95`、`approved: false`。审查期间未观察到受控代码变化；若之后内容变化，本报告不覆盖新快照。
