# 海外轻量化发布收尾独立审查 · 2026-11-07

## 快照与结论

- 主 Agent 指定 candidateId：`90d4803409920db3bb020dd1112276d478ac494e1dc0a63ef7e096f90d1ead70`；HEAD：`0b9d68b8f402c3cc341909a6f416ffd1a55c2995`。审查范围为 `Product-Spec.md:1–27`、`Design-Brief.md:1–3`、`DEV-PLAN.md:1–7`、`docs/OVERSEAS-LIGHT-RELEASE-20261107.md:3–7`，以及受控差异中的 6 个 `scripts/release/overseas-light-*.py` 和 5 个 `test_overseas_light_*.py`；必要时查看其调用的共享助手。业务代码以当前 HEAD 和既有独立业务审查交叉核对。
- **Stage 1：PASS（本次发布实现和同一业务提交范围）。Stage 2：FAIL：1 项 HIGH、1 项 MEDIUM。不得对本 candidate 登记两阶段 PASS。** 正式发布、安装、线上数据和入口验收尚未完成，不属于本报告通过范围。
- 起始和写报告前 `review-status.currentId` 都是指定 candidateId，`approved: false`，11 个受控差异文件列表一致；审查中未修改代码或测试、未访问生产、未部署。报告 Markdown 不属于受控代码快照。
- 上轮 `c60a889e7f633d519d76d4b16770bb2d2e9f9c06edd0fa6de0c9a751ac033ccb` 的源文件副本及清单不可用，主 Agent 也确认未保存，**无法证明该版本到本版本的逐字差异，也不能断言回退代码完全未变**。本次重新审阅当前完整发布/恢复流程和拆分测试；旧报告 `docs/reviews/overseas-light-atomic-release-20261107.md:8–38` 仅用于定位原审项目，不把其 PASS 自动套用本候选。当前 `git diff --name-only HEAD -- hengxin-smart-image/` 与对应未跟踪文件查询均为空；本候选业务前后端与已审 HEAD 一致。

## Stage 1：需求与发布约束

表中以 `backend/`、`frontend/` 开头的路径均相对于 `hengxin-smart-image/`；其他路径相对于仓库根目录。

| 条目 | 结论和证据 |
| --- | --- |
| `Product-Spec.md:7` 合并调用入口、旧地址兼容、既有权限 | 匹配同一业务提交：`hengxin-smart-image/frontend/src/identity-main.ts:21–23`、`backend/app/overseas/management/router.py:13–35`；完整业务测试和权限证据见 `docs/reviews/overseas-light-complete-20261107.md:17`。 |
| `Product-Spec.md:8` 实际用户发起次数、幂等、排队/失败/取消、北京时间 | 匹配同一业务提交：`backend/app/overseas/studio/service.py:60–101`、`backend/app/overseas/management/facts.py:14–38`；业务测试证据见既有报告第 18 行。 |
| `Product-Spec.md:9` 未记录历史、权限与留存边界 | 匹配同一业务提交：`backend/app/overseas/management/facts.py:51–59`、`frontend/src/views/overseas/admin/OverseasActivityPage.vue:3`；业务测试证据见既有报告第 19 行。 |
| `Product-Spec.md:10` 图片数、最近发起、停用人员 | 匹配同一业务提交：`backend/app/overseas/management/usage.py:34–48`、`backend/tests/test_overseas_lightweight.py:33–69`；既有报告第 19 行记录历史和权限测试。 |
| `Product-Spec.md:11` 状态汇总、人员和状态下钻、筛选分页、详情 | 匹配同一业务提交：`backend/app/overseas/management/monitor.py:11–25`、`frontend/src/views/overseas/admin/OverseasActivityPage.vue:23–30,59–87`；既有报告第 20 行有浏览器证据。 |
| `Product-Spec.md:15` 实际归档人、组合搜索、先筛后分页 | 匹配同一业务提交：`backend/app/overseas/archives/service.py:63–87`、`backend/tests/test_overseas_archive_audit.py:19–46`；既有报告第 21 行。 |
| `Product-Spec.md:16` 候选、历史缺失、源任务删除后的记录及保留操作 | 匹配同一业务提交：`backend/app/overseas/archives/service.py:90–116`、`frontend/src/views/overseas/OverseasArchivePage.vue:21–26,46–50`；既有报告第 22 行。 |
| `Product-Spec.md:20` 当前负责人、停用成员、范围和改派 | 匹配同一业务提交：`backend/app/overseas/tasks/queries.py:84–91,127–131`、`frontend/src/views/overseas/OverseasTasksPage.vue:146–156`；既有报告第 23 行。 |
| `Product-Spec.md:21` 20 条、双分页、先筛后分页及详情返回 | 匹配同一业务提交：`backend/app/overseas/tasks/queries.py:111–124`、`frontend/src/views/overseas/OverseasTasksPage.vue:37–40,153–158`；既有报告第 24 行。 |
| `Product-Spec.md:22` 状态分组、历史 submitted 和删除异常 | 匹配同一业务提交：`backend/app/overseas/tasks/queries.py:77–80,92–94`、`frontend/src/views/overseas/task-status.ts:7–30`；既有报告第 25 行。 |
| `Product-Spec.md:23` 分批归档、显式完成和解冻 | 源码匹配同一业务提交：`backend/app/overseas/studio/service.py:123–191`；未操作生产。 |
| `Product-Spec.md:27`、`Design-Brief.md:1–3` 确认预览、窄屏和视觉 | 已审业务提交的完整预览对照见既有报告第 27、31–35 行。本次以本地模拟接口重新打开调用与执行及系统配置邻页，亦实际测量 390px 横滚，结果见 Stage 2。真实数据和新正式包不在本次证据内。 |
| `DEV-PLAN.md:7` 正式构建、安装、原有服务与数据保护 | `scripts/release/overseas-light-package.py:76–112` 限定已审提交并打包；`overseas-light-deploy.py:58–97,100–132,170–244` 检查基线、隔离安装测试、切换与恢复；`skill-platform-runtime.py:61–67` 校验受保护资源。正式新包和线上验收仍待后续完成。 |
| 发布记录第 7 行：SVG、目录保护、故障恢复 | `overseas-light-package.py:30–35,64–71` 归一非哈希公共 SVG；`overseas-light-frontend.py:122–148,177–240` 检查冲突、安装和回退；`overseas-light-guard.py:61–79,82–111,114–170,176–244` 实施锁、收据和目录身份检查。下述 Linux 隔离用例覆盖实际目录、信号及恢复。 |
| 旧 API 和入口回退 | `overseas-light-deploy.py:194–235` 尝试前端和旧 API 恢复，受保护资源异常记入 `ROLLBACK_ERRORS.json`，无错误后才重开入口；`test_overseas_light_rollback.py:16–91,116–147` 在 Windows 服务桩中验证顺序和失败控制流。此证据不证明真实代理或生产回退，且 Linux 全套存在后述测试缺陷。 |
| 新合同与发布包完整性 | `overseas-light-contract.py:3–44` 从部署脚本抽出只读 SQL 和接口合同；独立 AST 比较它与 HEAD 中原 `CONTRACT`，字符串完全相同（2,238 字符）；`overseas-light-deploy.py:37,135–141` 加载并执行合同，`overseas-light-runtime.py:25–27,39–50` 要求新助手并校验哈希，`overseas-light-package.py:100–102` 打包助手。合成包使用本候选 13 个真实助手字节，通过验包及包内 CLI 启动；删除或篡改合同均被拒绝。 |

未实现／部分实现：在当前发布脚本所检查的要求中未发现未实现项；正式新包、安装和生产验收未完成。Spec 漂移：`overseas-light-deploy.py:247–265` 的权限恢复入口对应发布记录第 7 行；抽出的合同和测试是发布辅助文件，本审范围未见新增产品页面、API 或表。此结论不是全仓漂移审计。

## Stage 2：问题

### HIGH · 回退测试在 POSIX root 环境触及固定生产路径

`scripts/release/test_overseas_light_rollback.py:16–43,46–72,75–91,116–147` 调用 `deploy.deploy(tmp_path)` 时未将 `deploy.r.a.APP` 指向隔离临时目录。`account-runtime.py:18` 固定为 `/opt/hengxin-smart-image`，`overseas-light-deploy.py:238–240` 将其传入保护上下文，`overseas-light-guard.py:61–74,194–216,226–229` 会在其父目录创建发布锁，并临时修改 app 和 frontend 的目录权限。Windows 分支在 `overseas-light-guard.py:179–181` 直接 yield，因此 Windows 桩测试通过并未运行这条生产平台路径。

本次无网络、只读 root Linux 容器运行完整 24 项时，上述 4 项在试图向 `/opt/.hengxin-overseas-light.lock` 写入时失败。进一步在**容器自己的临时 `/opt`** 建立同名目录，单独运行第一项测试：测试通过后锁文件从不存在变为存在，见下方原始输出。可推知在真实主机以 root 运行这些标称无生产访问的测试，满足目录条件时会写入真实锁并临时更改真实目录权限；若进程被强杀，可能留下待恢复状态。这是测试隔离和安全问题，并非本次实际访问生产。应将 APP 和全部写入目标限定到临时目录，在 POSIX/root 和非 root 条件明确执行或跳过，重新准备快照并重审。

### MEDIUM · 一个安装单测在 Linux 保护前置条件下必然失败

`scripts/release/test_overseas_light_release.py:130–152` 直接调用 `install_frontend`；该函数在 `overseas-light-frontend.py:177–178` 强制 `guard.require_protected(app)`。POSIX 上 `overseas-light-guard.py:238–244` 要求活动的真实保护上下文，故测试在执行断言前失败；Windows 不做该检查。下方 Linux 全套原始摘要显示该项失败。`test_overseas_light_installer.py:11–52` 已在隔离临时目录中使用保护上下文，是不同的真实安装/回退证据，不能让失败的 pytest 用例被计为通过。

## Stage 2：其他核查

- **上轮 300 行限制已修复。** 11 个受控文件独立逐字节编译并计数为 44–272 行，原始输出见下方；例如 `overseas-light-deploy.py:1–272`、`test_overseas_light_release.py:1–187`、`test_overseas_light_installer.py:1–159`。
- **上轮虚假通过问题的指定 8 项已显式跳过。** `test_overseas_light_installer.py:87–89`、`test_overseas_light_guard.py:11–13,61–63,86–88`、`test_overseas_light_guard_recovery.py:11–13,75–77,109–111,148–150` 使用 `SkipTest`；本次 Windows 输出 16 passed、8 skipped。Linux 三个直接入口 `installer.py:154–159`、`guard.py:116–120`、`guard_recovery.py:184–189` 在 root 容器各自确实执行并通过。但这不覆盖上述另外 5 个 Linux pytest 失败，不能把直接入口输出等同于全套通过。
- **安全静态扫描：受限通过。** 对 11 个受控文件使用 skill 指定的 `eval(`、`exec(`、`dangerouslySetInnerHTML`、`innerHTML`、`shell=True`、前端密钥变量、常见密钥前缀和用户绝对路径模式执行 `rg`，exit 1、无匹配；这不覆盖 Git 历史或全面渗透测试。上面 HIGH 为测试的实际文件系统写入风险。
- **视觉：已实际对照邻页。** 本次从当前业务源码启动本地 Vite，浏览器阻断外部来源并模拟 API，在 1280×900 打开“系统配置”和“调用与执行”。两页沿用相同海外 Shell、白底卡片、蓝色动作与 Element 控件；调用页日期控件实测宽 300px、右界 621px，重置按钮左界 635px；390×844 任务表 `width=308, full=1070, left=762`。依据 `output/playwright/review-light-final-neighbor.mjs:73–81` 运行；模拟数据不代表新正式包或线上视觉。

## 独立验证原始输出

### Windows 全套 pytest

`hengxin-smart-image/backend/.venv/Scripts/python.exe -B -m pytest -q -ra -p no:cacheprovider scripts/release/test_overseas_light_release.py scripts/release/test_overseas_light_rollback.py scripts/release/test_overseas_light_installer.py scripts/release/test_overseas_light_guard.py scripts/release/test_overseas_light_guard_recovery.py`，exit 0：

```text
...............s.sssssss                                                 [100%]
=========================== short test summary info ===========================
SKIPPED [1] hengxin-smart-image\backend\.venv\Lib\site-packages\_pytest\unittest.py:523: Requires POSIX filesystem semantics
SKIPPED [7] hengxin-smart-image\backend\.venv\Lib\site-packages\_pytest\unittest.py:523: Requires POSIX root execution
16 passed, 8 skipped in 1.09s
```

### Linux root 全套 pytest：失败

固定本地镜像 `hengxin-smart-image-backend:phase25`（Python 3.12、pytest 9.1.1），`--pull=never`、无网络、容器根与源码只读、`/tmp` 为临时文件系统。原始命令（PowerShell，仓库根目录）：

```powershell
docker run --rm --pull=never --network=none --read-only --user 0 --tmpfs /tmp:rw,nosuid --mount 'type=bind,src=D:/Work_Project/hengxin-smart-image/scripts/release,dst=/review,readonly' --workdir /review --entrypoint python hengxin-smart-image-backend:phase25 -B -m pytest -q -ra -p no:cacheprovider test_overseas_light_release.py test_overseas_light_rollback.py test_overseas_light_installer.py test_overseas_light_guard.py test_overseas_light_guard_recovery.py
```

exit 1，原始失败摘要：

```text
......F.FFF.F...........                                                 [100%]
FAILED test_overseas_light_release.py::test_install_never_chmods_unrelated_old_directory
FAILED test_overseas_light_rollback.py::test_failed_frontend_switch_restores_api_before_reopening
FAILED test_overseas_light_rollback.py::test_failed_frontend_rollback_does_not_prevent_old_api_restore
FAILED test_overseas_light_rollback.py::test_unconfirmed_stop_does_not_replace_or_reopen
FAILED test_overseas_light_rollback.py::test_rollback_checks_protected_services_before_reopening
5 failed, 19 passed in 5.35s
```

原始错误分别为 `RuntimeError: Publication directories are not protected`（`overseas-light-frontend.py:178`）以及 `OSError: [Errno 30] Read-only file system: '.hengxin-overseas-light.lock'`（`overseas-light-guard.py:69`，调用时 app 为 `PosixPath('/opt/hengxin-smart-image')`）。

### Linux 隔离路径副作用复现

同一镜像、同样无网络与只读源码，额外挂载 `--tmpfs /opt:rw,nosuid,mode=755`；容器内建立 `/opt/hengxin-smart-image/frontend`，app 和 frontend 均置为 0777，运行 `test_overseas_light_rollback.py::test_failed_frontend_switch_restores_api_before_reopening`。exit 0，原始输出：

```text
ISOLATED_TEST_APP /opt/hengxin-smart-image
BEFORE 0o777 0o777 lock= False
ROLLBACK_COMPLETE_WORKERS_AND_DATABASE_RETAINED
.
1 passed in 0.72s
AFTER 0o777 0o777 lock= True
ISOLATED_HOST_PATH_WRITTEN
```

### Linux 分拆直接入口

`python:3.12.10-slim-bookworm` 本地镜像，分别使用 `--pull=never --network=none --read-only --tmpfs /tmp:rw,nosuid`，只读挂载 `scripts/release` 到 `/review`，以 root 执行 `python -B /review/test_overseas_light_installer.py`、`test_overseas_light_guard.py`、`test_overseas_light_guard_recovery.py`，三次 exit 0，各输出：

```text
ISOLATED_RELEASE_CHECKS_PASS
```

### 发布合同、合成包和编译

AST 提取 HEAD 原常量和当前合同，exit 0：

```text
HEAD_CONTRACT_EQUALS_EXTRACTED True
HEAD_CONTRACT_CHARS 2238 EXTRACTED_CHARS 2238
```

合成清单中 API、业务测试及前端为夹具，13 个助手为本候选真实文件；包内部署脚本 `--help` 可启动并包含 `recover-permissions`。该试验不生成正式包、不执行实际部署。原始摘要：

```text
REAL_HELPERS_SYNTHETIC_PACKAGE_OK 13
PACKAGED_DEPLOY_HELP_EXIT 0
MISSING_CONTRACT_REJECTED Incomplete package
TAMPERED_CONTRACT_REJECTED Package checksum mismatch: scripts/release/overseas-light-contract.py
```

对每个文件 `compile(path.read_bytes(), str(path), 'exec')`，exit 0，完整原始输出：

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
scripts/release/test_overseas_light_release.py 187 lines
scripts/release/test_overseas_light_rollback.py 147 lines
COMPILE_OK 11
```

`git diff --check` exit 0，仅提示 deploy、runtime 和 test_release 的 CRLF 将在 Git 接触时转换为 LF。`review-status` 起始、写报告前和写报告后结果一致：

```json
{"currentId": "90d4803409920db3bb020dd1112276d478ac494e1dc0a63ef7e096f90d1ead70", "reviewedId": "e5f6f10a2a368742bf9aca90c2bb2449fe63ba9fb616196bc49d68b8e47672d9", "changedFiles": ["scripts/release/overseas-light-contract.py", "scripts/release/overseas-light-deploy.py", "scripts/release/overseas-light-frontend.py", "scripts/release/overseas-light-guard.py", "scripts/release/overseas-light-package.py", "scripts/release/overseas-light-runtime.py", "scripts/release/test_overseas_light_guard.py", "scripts/release/test_overseas_light_guard_recovery.py", "scripts/release/test_overseas_light_installer.py", "scripts/release/test_overseas_light_release.py", "scripts/release/test_overseas_light_rollback.py"], "approved": false}
```

修复后应先重新固定快照，从 Stage 1 起复审；完整 Linux pytest 应在隔离、无网络、只读源码环境通过，任何实际部署和生产验收须另行进行。报告不授权使用 `.needs-review` 的 clean 状态替代同一快照的审查凭据。
