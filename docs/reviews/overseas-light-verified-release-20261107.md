# 海外轻量化发布测试隔离独立审查 · 2026-11-07

## 快照、范围与结论

- 主 Agent 指定 candidateId：`efa1def865fa3f9d5b74ec7b98f50eaf1ce9b8fe1deef6d018ca7f0528e417fc`；业务 HEAD：`0b9d68b8f402c3cc341909a6f416ffd1a55c2995`。起始、写报告前 `review-status.currentId` 均为该编号，`approved: false`；本审未修改代码或测试、未连接生产、未部署、未调用付费模型。报告 Markdown 不计入受控代码快照；报告写完后再执行一次 `review-status`。
- 审查范围：`Product-Spec.md:1–27`、`DEV-PLAN.md:1–7`、`Design-Brief.md:1–3`、确认预览、`docs/OVERSEAS-LIGHT-RELEASE-20261107.md:3–7`，以及当前快照中的 6 个 `scripts/release/overseas-light-*.py` 和 5 个 `test_overseas_light_*.py`。受控业务代码与已审 HEAD 的 tracked diff 和 untracked 查询均为空；业务功能证据参考同一 HEAD 的 `docs/reviews/overseas-light-complete-20261107.md:15–43`，本次重新运行隔离浏览器并独立审查发布、回退和测试。
- **Stage 1：PASS（指定源码和发布工具范围）；Stage 2：FAIL（1 项 MEDIUM 测试真实性问题）。未发现 HIGH。不得为本 candidateId 登记两阶段 PASS。** 原上轮 HIGH 和 MEDIUM 的具体症状已消除，但这不消除本次新发现的问题。
- 主 Agent 称上一候选仅改两份测试。上轮 `90d4803409920db3bb020dd1112276d478ac494e1dc0a63ef7e096f90d1ead70` 的源文件副本及逐文件哈希本审不可获得，无法独立证明完整候选间只有两份文件有差异；因此本审对当前发布链和测试独立核查，不把上轮 PASS 自动套到当前候选。
- 本报告不宣称最终正式包、生产安装或真实线上数据验收已通过。`Product-Spec.md:27` 和 `DEV-PLAN.md:7` 的正式构建、安装和生产只读验收仍待另行执行。

## Stage 1：Spec 和发布约束逐条核对

以下 `backend/` 和 `frontend/` 均相对 `hengxin-smart-image/`；其他路径相对仓库根目录。历史业务验证为同一 HEAD 的先前独立测试证据，并非本次连接真实生产。

| 需求 | 结论与证据 |
| --- | --- |
| `Product-Spec.md:7` 合并调用统计与执行监控、旧地址、权限 | 匹配：`frontend/src/identity-main.ts:21–23`、`backend/app/overseas/management/router.py:13–35`、`backend/app/overseas/management/facts.py:51–53`；旧地址及权限测试见既有报告第 17 行。 |
| `Product-Spec.md:8` 实际发起次数、幂等、排队/失败/取消和北京时间 | 匹配：`backend/app/overseas/studio/service.py:60–101`、`management/usage.py:30–48`、`management/facts.py:14–38`；请求、重放、取消及时间边界测试见 `backend/tests/test_overseas_lightweight.py:16–56`。 |
| `Product-Spec.md:9` 未记录历史、权限范围、留存边界 | 匹配：`management/facts.py:51–59`、`frontend/src/views/overseas/admin/OverseasActivityPage.vue:3,27`；历史缺失与权限夹具见 `backend/tests/test_overseas_lightweight.py:33–69`。 |
| `Product-Spec.md:10` 生成图片数、最近发起及停用人员 | 匹配：`management/usage.py:34–48`、`backend/tests/test_overseas_lightweight.py:33–69`；该测试是持久化夹具，不代表真实模型调用。 |
| `Product-Spec.md:11` 四类汇总、人员/状态下钻、筛选分页和详情 | 匹配：`management/usage.py:8–16`、`management/monitor.py:11–25`、`OverseasActivityPage.vue:23–30,59–87`；本次 `frontend/tests/overseas-lightweight.browser.mjs` 重跑下钻、取消与错误重试通过，见原始输出。 |
| `Product-Spec.md:15` 实际归档人、组合搜索、先筛选后分页 | 匹配：`backend/app/overseas/archives/service.py:63–87`、`frontend/src/views/overseas/OverseasArchivePage.vue:4–5,17–19`；`backend/tests/test_overseas_archive_audit.py:19–46` 覆盖多人及组合筛选，本次浏览器再次执行归档筛选。 |
| `Product-Spec.md:16` 可见真实候选、历史缺失、原任务删除和保留操作 | 匹配：`archives/service.py:90–116`、`archives/audit.py:9–35`、`OverseasArchivePage.vue:21–26,46–50,64–67`；源任务删除和权限夹具见 `test_overseas_archive_audit.py:47–70`。 |
| `Product-Spec.md:20` 当前负责人、停用成员、改派与原范围 | 匹配：`backend/app/overseas/tasks/queries.py:84–91,127–131`、`frontend/src/views/overseas/OverseasTasksPage.vue:98–102,146–156`；本次浏览器以模拟 API 执行改派和删除。 |
| `Product-Spec.md:21` 每页20条、上下分页、服务端先过滤、详情返回 | 匹配：`tasks/queries.py:111–124`、`OverseasTasksPage.vue:37–40,153–158`；本次浏览器覆盖分页范围，先前报告第 24 行记录详情返回。 |
| `Product-Spec.md:22` 三种状态分组、历史 submitted、返工和删除异常 | 匹配：`tasks/queries.py:77–80,92–94`、`frontend/src/views/overseas/task-status.ts:7–30`、`backend/tests/test_overseas_lightweight.py:78–105`；本次浏览器覆盖历史状态。 |
| `Product-Spec.md:23` 分批归档、显式完成和合法解冻 | 源码匹配：`backend/app/overseas/studio/service.py:123–191` 分别处理归档、完成与解冻；本次不操作线上任务。 |
| `Product-Spec.md:27` 与 `Design-Brief.md:1–3` 的确认预览、窄屏、空错态 | 范围内匹配：`frontend/tests/overseas-lightweight.browser.mjs:24–36,87–172`；本次模拟 API 浏览器运行通过且实看邻页，先前完整预览颜色和尺寸实测见 `docs/reviews/overseas-light-complete-20261107.md:31–35`。真实正式包和线上只读数据验收仍待执行。 |
| `DEV-PLAN.md:7` 与发布记录第 7 行：公共 SVG、冲突、目录保护、权限恢复 | `scripts/release/overseas-light-package.py:30–35,64–71` 仅归一非哈希公共 SVG；`overseas-light-frontend.py:122–148,177–240` 检查冲突并安装/回退目标文件；`overseas-light-guard.py:61–79,82–111,114–170,176–244` 提供锁、权限收据和 inode 核验恢复。隔离 Linux 全套真实运行 24 项，保护桩和真实保护上下文边界见 Stage 2。 |
| 发布记录第 7 行：回退与不可覆盖共享资源 | `overseas-light-deploy.py:194–235` 在前端回退失败后仍尝试旧 API，保护检查或回退报错后不重开入口；`test_overseas_light_rollback.py:24–155` 验证事件顺序与错误收据，`test_overseas_light_installer.py:11–68,129–152` 在临时目录执行真实安装、回退和共享资源竞争。服务和代理在顺序测试中为桩，不证明真实主机回退。 |
| 包完整性和合同 | `overseas-light-runtime.py:25–27,29–65` 要求并验证 13 个助手、包内哈希及入口；`overseas-light-package.py:100–102` 将助手纳入包。独立 AST 比较提取合同与 HEAD 原常量完全一致；合成包使用当前 13 个真实助手，包内 CLI 可启动，删除合同或篡改字节均被拒绝，原始输出见下。 |

**未实现、部分实现：** 本审指定源码范围未发现其他未实现或部分实现的功能。最终正式发布和生产验收仍未执行，不能据此宣布产品交付完成。**Spec 漂移：** 在派发范围未见多余产品页面、API 或表；`overseas-light-deploy.py:247–265` 的 `recover-permissions` 对应发布记录第 7 行，合同拆分及隔离测试为发布辅助内容。本项不是全仓漂移审计。

## Stage 2：问题

### MEDIUM · 无关目录权限测试无法捕获生产代码使用的 `os.fchmod`

- 需求：`docs/OVERSEAS-LIGHT-RELEASE-20261107.md:7` 要求安装仅处理本次目标、不得修改无关目录。
- 事实：`scripts/release/test_overseas_light_release.py:138–145,151–155` 建立无关 `private` 目录，单独拦截 `Path.chmod`，并只断言该路径未出现在 `chmodded`。实际发布代码通过文件描述符调用 `os.fchmod`（`overseas-light-frontend.py:78–82`、`overseas-light-guard.py:139–147,209–216`），而这条路径不会被该测试的 `Path.chmod` 钩子观察。该测试没有断言 `private` 的实际 inode 或权限值。
- 实证：本审在无网络、只读源码的 Linux root 容器内，仅在内存中包装 `install_frontend`，执行真实安装后对该无关目录的文件描述符注入 `os.fchmod(fd, 0o700)`；目录实际从 `0755` 变成 `0700`，原测试仍正常通过，见下方原始输出。未修改源文件、未访问生产。当前安装实现静态核对未见实际遍历或修改该 `private` 目录；本问题是测试不能证明其所声称的保护，并非断言线上已损坏。
- 应补充对无关目录真实身份与权限变化的验证；若继续声称“从未修改权限”，还应观察实际文件描述符改权限路径，单靠结束前后的 mode/inode 对比不能发现改后又恢复的瞬时修改。修复后重新固定快照并从 Stage 1 起复审。

## Stage 2：其他核查

- **上轮 HIGH 已消除，限本次隔离条件。** `test_overseas_light_rollback.py:17–20` 将 `r.a.APP` 指向各自的 `tmp_path/isolated-app` 并将保护上下文替换为无副作用桩；五个相关用例统一通过该入口（`:24–25,54–55,83–84,102–104,124–125`）。Linux 全套使用无网络、只读根和源码、无生产挂载的容器通过；额外 Python 级路径拦截和假 `/opt` 检查未观察到该路径访问、权限/ctime 变化或锁文件创建。该钩子不是对全部原生系统调用的追踪；它不等于真实主机测试。
- **上轮安装测试前置条件失败已消除。** `test_overseas_light_release.py:149–152` 在 `tmp_path` 中建立 work 并进入真实保护上下文；Linux 全套通过。此结论不消除上面的断言盲区。`test_overseas_light_installer.py:15–17,35–47` 另在真实临时目录执行保护、安装与回退。
- **测试真实性范围。** 回退顺序测试故意 mock 代理、容器及保护上下文，仅证明控制流；`test_overseas_light_guard.py:11–58,86–113` 和 `test_overseas_light_guard_recovery.py:11–72,75–106,109–182` 在隔离 Linux root 运行目录权限、进程竞争、SIGKILL、SIGQUIT 与 inode 核验。Windows 上对应 8 项明确 skipped，不能将 Windows 输出当作 POSIX 验证。
- **代码质量和静态安全扫描。** 11 个受控 Python 文件逐字节 `compile` 成功，44–272 行，均不超过 300 行，原始结果见下；`rg` 扫描指定文件的 `eval`、`exec`、`innerHTML`、`shell=True`、明文密码模式、前端敏感变量、常见密钥前缀和 `/Users/`、`/opt/`，退出 1 且无匹配。`scripts/release/account-runtime.py:18` 的真实固定 APP 常量由回退测试替换。此扫描不覆盖 Git 历史或渗透测试。
- **邻页视觉。** 本次使用开发源码、127.0.0.1、无 Vite API 代理和浏览器模拟 API，在 1280×900 实际打开“系统配置”和“调用与执行”并查看截图 `output/playwright/review-light-final-neighbor.png`、`output/playwright/review-light-final-activity.png`；同为海外 Shell、白底卡片、蓝色动作和 Element 控件。日期控件右界 621px、重置左界 635px；390px 任务表可横滚 762px。模拟数据和开发源码不代表已验证的最终正式包或线上视觉。

## 独立验证原始输出

### Linux root 全套 pytest

镜像 `hengxin-smart-image-backend:phase25`，无网络、只读容器根和源码、临时 `/tmp`；仅挂载发布脚本目录，不挂载生产路径：

```powershell
docker run --rm --pull=never --network=none --read-only --user 0 --tmpfs /tmp:rw,nosuid --mount 'type=bind,src=D:/Work_Project/hengxin-smart-image/scripts/release,dst=/review,readonly' --workdir /review --entrypoint python hengxin-smart-image-backend:phase25 -B -m pytest -q -ra -p no:cacheprovider test_overseas_light_release.py test_overseas_light_rollback.py test_overseas_light_installer.py test_overseas_light_guard.py test_overseas_light_guard_recovery.py
```

退出 0，原始输出：

```text
........................                                                 [100%]
24 passed in 5.52s
```

同一套测试另在容器临时 `/opt` 建立假 app，并拦截 Python 层 `open`、`stat/lstat` 和常见文件操作中的 `/opt` 路径；测试结束使用预先打开的文件描述符检查假 app、frontend 和 `/opt` 的 mode/ctime，确认锁文件不存在。退出 0，完整摘要：

```text
........ROLLBACK_COMPLETE_WORKERS_AND_DATABASE_RETAINED
.ROLLBACK_REQUIRES_INSPECTION: /tmp/pytest-of-root/pytest-0/test_failed_frontend_rollback_0
.ROLLBACK_REQUIRES_INSPECTION: /tmp/pytest-of-root/pytest-0/test_unconfirmed_stop_does_not0
..ROLLBACK_REQUIRES_INSPECTION: /tmp/pytest-of-root/pytest-0/test_rollback_checks_protected0
............
24 passed in 5.10s
PYTHON_LEVEL_OPT_ACCESSES 0
ISOLATED_OPT_MODES_CTIME_AND_LOCK UNCHANGED
```

### Windows 全套 pytest

`hengxin-smart-image/backend/.venv/Scripts/python.exe -B -m pytest -q -ra -p no:cacheprovider` 加同一五个文件，退出 0：

```text
...............s.sssssss                                                 [100%]
=========================== short test summary info ===========================
SKIPPED [1] hengxin-smart-image\backend\.venv\Lib\site-packages\_pytest\unittest.py:523: Requires POSIX filesystem semantics
SKIPPED [7] hengxin-smart-image\backend\.venv\Lib\site-packages\_pytest\unittest.py:523: Requires POSIX root execution
16 passed, 8 skipped in 1.14s
```

### MEDIUM 断言变异实验

在无网络、只读根与源码、`/tmp` 临时文件系统容器内直接调用原测试；只在 Python 进程内包装安装函数，追加对测试自己创建的 `private` 目录执行 `os.fchmod`。退出 0：

```text
PRIVATE_MODE_BEFORE 0o755
PRIVATE_MODE_AFTER 0o700
ORIGINAL_TEST_STILL_PASSED True
```

### 合同与合成包

合成包中的 API、测试及前端为夹具，13 个助手字节来自本候选真实文件；未生成正式包，也未执行部署。包和 manifest 同时删除合同，以及合同存在但字节被篡改，均被拒绝。退出 0：

```text
REAL_HELPERS_SYNTHETIC_PACKAGE_OK 13
PACKAGED_DEPLOY_HELP_EXIT 0
MISSING_CONTRACT_REJECTED Incomplete package
TAMPERED_CONTRACT_REJECTED Package checksum mismatch: scripts/release/overseas-light-contract.py
```

AST 提取 `git show HEAD:scripts/release/overseas-light-deploy.py` 的旧常量，与当前合同逐字比较，退出 0：

```text
HEAD_CONTRACT_EQUALS_EXTRACTED True
HEAD_CONTRACT_CHARS 2238 EXTRACTED_CHARS 2238
```

### 浏览器

本地 Vite 无 API 代理；`output/playwright/review-light-final-neighbor.mjs` 对外来源及 API 请求使用阻断/模拟，退出 0：

```text
390px task table horizontal scroll {"width":308,"full":1070,"left":762}
neighbor settings rendered
activity geometry {".activity-filters .date-filter":{"x":321,"y":420.671875,"right":621,"width":300,"minWidth":"auto","maxWidth":"none"},".activity-filters .el-date-editor":{"x":321,"y":448.171875,"right":621,"width":300,"minWidth":"auto","maxWidth":"100%"},".activity-filters > .el-button":{"x":635,"y":452.171875,"right":723,"width":88,"minWidth":"auto","maxWidth":"none"}}
PASS: 邻居页面及任务状态横滚
```

同样的隔离模式运行 `frontend/tests/overseas-lightweight.browser.mjs`，退出 0：

```text
PASS: 调用下钻、排队取消、负责人改派/删除、历史状态、分页范围、归档筛选/删除、错误重试、三页390px控件及资源请求
```

临时 Vite 进程已停止。浏览器请求、删除和改派均是模拟 API，未接触生产数据。

### Python 编译

对当前 11 个文件执行 `compile(path.read_bytes(), str(path), 'exec')`，退出 0，原始输出：

```text
scripts/release/overseas-light-contract.py 44 lines
scripts/release/overseas-light-deploy.py 272 lines
scripts/release/overseas-light-frontend.py 243 lines
scripts/release/overseas-light-guard.py 244 lines
scripts/release/overseas-light-package.py 123 lines
scripts/release/overseas-light-runtime.py 70 lines
scripts/release/test_overseas_light_guard.py 120 lines
scripts/release/test_overseas_light_guard_recovery.py 189 lines
scripts/release/test_overseas_light_installer.py 159 lines
scripts/release/test_overseas_light_release.py 190 lines
scripts/release/test_overseas_light_rollback.py 155 lines
COMPILE_OK 11
```

本项是语法编译，不是最终正式包构建。`git diff --check` 退出 0，仅提示 deploy、runtime 和 test_release 在 Git 接触时 CRLF 转 LF。

### 写报告前快照状态

```json
{"currentId": "efa1def865fa3f9d5b74ec7b98f50eaf1ce9b8fe1deef6d018ca7f0528e417fc", "reviewedId": "e5f6f10a2a368742bf9aca90c2bb2449fe63ba9fb616196bc49d68b8e47672d9", "changedFiles": ["scripts/release/overseas-light-contract.py", "scripts/release/overseas-light-deploy.py", "scripts/release/overseas-light-frontend.py", "scripts/release/overseas-light-guard.py", "scripts/release/overseas-light-package.py", "scripts/release/overseas-light-runtime.py", "scripts/release/test_overseas_light_guard.py", "scripts/release/test_overseas_light_guard_recovery.py", "scripts/release/test_overseas_light_installer.py", "scripts/release/test_overseas_light_release.py", "scripts/release/test_overseas_light_rollback.py"], "approved": false}
```
报告写入后再次执行 `review-status`，`currentId` 仍为 `efa1def865fa3f9d5b74ec7b98f50eaf1ce9b8fe1deef6d018ca7f0528e417fc`，`reviewedId`、11 项受控差异和 `approved: false` 均与上面的原始状态一致；审查期间没有受控代码变化。
