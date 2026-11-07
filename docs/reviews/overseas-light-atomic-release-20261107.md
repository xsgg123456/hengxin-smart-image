# 海外轻量化发布原子恢复独立审查 · 2026-11-07

## 快照、范围与结论

- 主 Agent 提供的 candidateId：`c60a889e7f633d519d76d4b16770bb2d2e9f9c06edd0fa6de0c9a751ac033ccb`；HEAD：`0b9d68b8f402c3cc341909a6f416ffd1a55c2995`。起始、写报告前和写报告后的 `review-status.currentId` 均为该 candidateId，`approved: false`，受控代码未发生变化。
- 受控范围：`scripts/release/overseas-light-{deploy,package,runtime,frontend,guard}.py`、`scripts/release/test_overseas_light_{release,installer}.py`；另核对其调用的 `skill-reuse-gate.py`、`skill-platform-runtime.py`、`account-runtime.py`。基准为 `Product-Spec.md:1–27`、`DEV-PLAN.md:1–7`、`docs/OVERSEAS-LIGHT-RELEASE-20261107.md:3–7` 及此前两份发布审查。该七文件是相对已审业务快照的全部受控差异；只对相同业务提交的其他功能映射既有审查证据，不将旧审查直接批准本候选。
- **Stage 1：PASS（本次发布脚本范围，前述生产发布与验收仍未完成）。Stage 2：FAIL，2 项 MEDIUM；无已发现的 HIGH。** 不得将该 candidate 登记为两阶段 PASS；修复后重新固定快照，从 Stage 1 复审。
- 未访问生产、部署、提交或修改受控代码。主 Agent 转述线上只读观察：app 和 frontend 为 `root:root 777`，dist 及所有目标目录为 `root:root 755`；本审查未独立核验线上权限。以下测试均为本机或本地隔离容器，不是正式包或生产验收。

## Stage 1：上轮问题复核

| 旧问题 | 本候选结论和证据 |
| --- | --- |
| HIGH：写恢复完成收据时强制终止，遗留固定 `.new` 使恢复入口永久冲突 | 已修复所测情形。`overseas-light-guard.py:82–111` 为每次写入创建唯一私有临时文件，完整写入并 `fsync` 后才替换正式收据；`:150–170,222–229` 恢复模式、写恢复收据、清除 pending 的顺序保留恢复入口。`test_overseas_light_installer.py:358–394` 在真实 Linux 子进程的收据替换前发送 SIGKILL，确认旧临时文件存在时仍能恢复；本次独立容器运行通过。收据临时文件可能在 SIGKILL 后残留，本结论是其不阻碍恢复，不是残留自动清理。 |
| HIGH：回退保护资源校验失败时入口已经重开，且没有失败记录 | 已修复所测控制流。`overseas-light-deploy.py:244–262` 在尝试前端与旧 API 恢复后先调用 `r.unchanged`，失败加入 `errors` 并写 `ROLLBACK_ERRORS.json`，只有无错误才到 `:263–264` 重开；`skill-platform-runtime.py:61–67` 核对原生服务/源码、技能和其他容器。`test_overseas_light_release.py:290–321` 使用服务桩注入第二次保护校验失败，断言未重开且记录 `protected: RuntimeError`；此测试不证明真实代理切换。 |
| MEDIUM：锁状态部分写入后恢复与新发布均无法解析 | 已修复所测情形。`overseas-light-guard.py:82–99,114–136` 先完整写入并同步唯一文件，再用排他硬链接发布 pending；`test_overseas_light_installer.py:397–431` 在写入部分 JSON 后注入异常，断言 pending 不存在、目录原权限保留且另一工作目录可继续。该用例模拟部分写入后失败，并非真实底层系统调用短写。另见后文独立 SIGKILL 注入：发布 pending 的链接前、链接后均验证了实际状态和恢复。 |

## Stage 1：需求与范围逐项对照

业务前后端均为同一已审提交，此次未重跑其业务测试或重新打开页面；以下证据是之前针对该提交的独立检查，不能代替新正式包及生产验收。

| 条目 | 证据与状态 |
| --- | --- |
| `Product-Spec.md:7` 合并入口、旧地址与权限 | 同一业务提交对应 `docs/reviews/overseas-light-complete-20261107.md:17`；本候选无业务 UI 或 API 差异。 |
| `Product-Spec.md:8` 实际发起、幂等、状态与北京时间 | 同一业务提交证据见该报告第 18 行。 |
| `Product-Spec.md:9–10` 历史未知、留存、图片与停用人员 | 同一业务提交证据见该报告第 19 行。 |
| `Product-Spec.md:11` 状态概况、下钻、筛选、分页与详情 | 同一业务提交证据见该报告第 20 行。 |
| `Product-Spec.md:15–16` 实际归档人、候选、历史与权限 | 同一业务提交证据见该报告第 21–22 行。 |
| `Product-Spec.md:20` 实际负责人、改派与范围 | 同一业务提交证据见该报告第 23 行。 |
| `Product-Spec.md:21` 先筛选再按 20 条分页、详情返回 | 同一业务提交证据见该报告第 24 行。 |
| `Product-Spec.md:22` 状态分组、旧状态和删除异常 | 同一业务提交证据见该报告第 25 行。 |
| `Product-Spec.md:23` 分批归档、显式完成及解冻 | 同一业务提交源码证据见该报告第 26 行；本次未操作生产。 |
| `Product-Spec.md:27`、`Design-Brief.md:1–3` 预览及窄屏 | 同一业务提交的预览和浏览器证据见该报告第 27、31–35 行；本候选没有页面差异，未重新做 UI 对照。新正式包及线上页面未由本次审查验证。 |
| 发布包范围与身份 | `overseas-light-package.py:76–86,90–112` 要求已提交源码与已审状态，按 commit 取源并记录 candidateId；`overseas-light-runtime.py:21–27,30–66` 固定基线、助手清单和包文件哈希。`test_overseas_light_release.py:155–187` 检查篡改、额外文件和入口资源。正式新包尚未构建。 |
| 公共 SVG 和共享资源冲突 | `overseas-light-package.py:30–35,64–71` 仅归一非 `assets/` 下公共 SVG；`test_overseas_light_release.py:18–25` 验证例子。`overseas-light-frontend.py:122–148,196–205` 预检与安装逐文件检查，`:83–90` 通过排他硬链接避免覆盖并发出现的目标；`test_overseas_light_installer.py:178–201` 在 Linux 模拟竞态，原目标保留。 |
| 不改变无关目录及安全目标目录 | `overseas-light-frontend.py:151–174,196–205` 要求目标目录已存在且逐级安全，只处理本包目标；`overseas-light-guard.py:176–221` 在共享锁内限制 app 和 frontend 的非所有者写权限。`test_overseas_light_installer.py:10–50,70–125,128–175,204–226` 在本地容器覆盖无关目录、符号链接、缺失/可写目录和非 root 重命名。锁不约束不遵循该锁的 root 进程。 |
| 跨工作目录保护、强制中断与恢复 | `overseas-light-guard.py:61–79,114–170,176–235` 使用跨进程锁、pending、原始收据和设备/inode 检查；`test_overseas_light_installer.py:229–321,324–355` 在 Linux 覆盖并发、SIGKILL、目录身份变化、SIGQUIT 和原模式恢复。本次额外覆盖 pending 发布链接前后 SIGKILL，见验证原始输出。 |
| 备份、旧 API 和入口回退 | `overseas-light-frontend.py:177–195,222–240` 备份并验证入口，`overseas-light-deploy.py:235–275` 捕获前端或旧 API 恢复失败、核对受保护资源并保持入口；`test_overseas_light_release.py:190–265,290–321` 检查相应桩控制流和错误记录。未测试真实生产代理和容器回退；外部关闭入口本身失败时仍需人工检查，不将日志视为外部状态保证。 |
| 正式发布与验收 | `Product-Spec.md:27`、`DEV-PLAN.md:7` 要求正式构建、安装及生产验收；`docs/OVERSEAS-LIGHT-RELEASE-20261107.md:3–7` 记载当前尚未完成。新候选的正式包、线上安装、正式入口与真实只读数据验收仍待执行。 |

**未实现 / 部分实现：** 本次发布脚本的所测要求未发现未实现或部分实现项；完整产品交付中的正式发布及生产验收未完成。**Spec 漂移：** 七个受控差异为发布助手和对应测试；`overseas-light-deploy.py:288–306` 的 `recover-permissions` 对应发布记录第 7 行。未在范围内发现额外业务页面、API 或表；未做全仓漂移审计。

## Stage 2：问题

### MEDIUM 1 · 三个审查范围文件超过 300 行

`.agents/skills/code-review/SKILL.md` 的 Stage 2 标准要求“文件不超 300 行”。本次逐文件计数：`scripts/release/overseas-light-deploy.py:313` 共 313 行、`scripts/release/test_overseas_light_release.py:321` 共 321 行、`scripts/release/test_overseas_light_installer.py:446` 共 446 行。它们均违反该明确质量标准；其余四个受控文件分别为 70–244 行。拆分后需确保打包白名单、Linux 直接运行测试入口及故障路径仍被覆盖，再对新候选完整复审。

### MEDIUM 2 · Windows 测试结果把未执行的 POSIX/root 用例显示为通过

`test_overseas_light_installer.py:86–88,128–130,204–206,229–231,260–262,324–326,358–360,397–399` 有 8 个依赖 POSIX 或 root 的测试，在条件不满足时直接 `return`，而非明确报告未执行。因此 Windows 上的 `24 passed` 不代表这 8 项执行；将来仅运行 Windows 套件时会把故障路径缺失伪装为已通过。本次在 Linux root 容器逐一实际运行了这些函数，故本次上述 Linux 证据不依赖 Windows 的误报。

## Stage 2：其他检查

- **安全静态扫描：通过（受控七文件，非全面渗透测试）。** 对 `eval(`、`exec(`、`dangerouslySetInnerHTML`、`innerHTML`、`shell=True`、前端密钥变量、常见密钥前缀和用户绝对路径执行 `rg`，无匹配，exit 1。发布操作中的固定容器和挂载路径是已声明目标，例如 `overseas-light-deploy.py:147–164,201–208`；源码中的固定 read-only SQL 和无 shell 参数调用分别见 `:37–76,147–168`，不把这次扫描当作线上权限核验。
- **测试真实性：所测路径有证据，存在上述报告误导。** Linux 测试通过真实目录、`fork`、权限、信号及锁调用；`test_overseas_light_installer.py:33,36–46` 使用本地 manifest 桩，故不证明正式包验签或生产文件系统；`:411–427` 模拟部分写入后异常，不是实际 ENOSPC 或内核短写；`test_overseas_light_release.py:300–321` 对服务和入口使用桩，不是真实代理。额外链接时序注入详见下方。Windows 假通过见 MEDIUM 2。
- **视觉对比：本次不适用页面差异。** 所有受控变化均为发布脚本和测试；同一业务提交的实际预览与邻页浏览器比较见 `docs/reviews/overseas-light-complete-20261107.md:31–35,42`，本次未重新打开页面，不据此声称新包或线上视觉已验收。

## 本候选独立验证原始输出

1. Windows：`hengxin-smart-image/backend/.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider scripts/release/test_overseas_light_release.py scripts/release/test_overseas_light_installer.py`，exit 0：

```text
........................                                                 [100%]
24 passed in 0.93s
```

其中 8 个 POSIX/root 测试直接返回，详见 MEDIUM 2。

2. 本地 `python:3.12.10-slim-bookworm` 容器，网络禁用、容器根与源码挂载只读，临时文件在容器 `/tmp`；`python -B /review/test_overseas_light_installer.py`，exit 0：

```text
ISOLATED_INSTALL_AND_ROLLBACK_PASS
```

该文件的 `:434–445` 直接调用 11 个测试函数；本容器以 root 执行真实 POSIX 条件分支，未连接生产。

同一镜像以相同默认用户运行身份核验，exit 0：

```text
linux_uid= 0 linux_euid= 0
```

3. 同一隔离容器独立注入：在 pending 的 `os.link` 前或刚成功后暂停真实子进程并发送 SIGKILL；核对原收据和目录原模式。链接前 pending 不存在；链接后真实恢复清除 pending；随后另一工作目录均可取得锁并完成保护，exit 0：

```text
before_link: pending_before_recovery=False original_modes=['0o777', '0o777'] new_work_succeeded=True
after_link: pending_before_recovery=True original_modes=['0o777', '0o777'] new_work_succeeded=True
```

这覆盖进程终止时序，不是断电或文件系统崩溃持久性验证；生产操作仍应按发布记录检查原发布状态。

4. 对七个受控 Python 文件以 `compile(path.read_bytes(), str(path), 'exec')` 编译，exit 0，原始输出：

```text
scripts\release\overseas-light-deploy.py
scripts\release\overseas-light-frontend.py
scripts\release\overseas-light-guard.py
scripts\release\overseas-light-package.py
scripts\release\overseas-light-runtime.py
scripts\release\test_overseas_light_release.py
scripts\release\test_overseas_light_installer.py
COMPILE_OK 7
```

5. 七文件行数，exit 0：

```text
overseas-light-deploy.py 313
overseas-light-package.py 123
overseas-light-runtime.py 70
overseas-light-frontend.py 243
overseas-light-guard.py 244
test_overseas_light_release.py 321
test_overseas_light_installer.py 446
```

6. `git diff --check`，exit 0，原始 stderr：

```text
warning: in the working copy of 'scripts/release/overseas-light-deploy.py', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'scripts/release/overseas-light-runtime.py', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'scripts/release/test_overseas_light_release.py', CRLF will be replaced by LF the next time Git touches it
```

7. 审查开始、报告写入前和报告写入后 `review-status` 原始输出一致：

```json
{"currentId": "c60a889e7f633d519d76d4b16770bb2d2e9f9c06edd0fa6de0c9a751ac033ccb", "reviewedId": "e5f6f10a2a368742bf9aca90c2bb2449fe63ba9fb616196bc49d68b8e47672d9", "changedFiles": ["scripts/release/overseas-light-deploy.py", "scripts/release/overseas-light-frontend.py", "scripts/release/overseas-light-guard.py", "scripts/release/overseas-light-package.py", "scripts/release/overseas-light-runtime.py", "scripts/release/test_overseas_light_installer.py", "scripts/release/test_overseas_light_release.py"], "approved": false}
```

## 未测范围与门禁

未生成新正式包，未验证包内全部动态资源，未测试真实代理失败/回退、生产权限、线上安装、正式入口或真实数据；业务 UI 及邻页本次未重测。审查只约束本 candidate，任何受控代码变化都使本报告结论不能直接套用新快照；修复两项 MEDIUM 后重新准备并从 Stage 1 审查。两阶段通过时由主 Agent 依 `docs/HARNESS-REVIEW.md` 登记同一候选，不向 `.needs-review` 写 clean 代替凭据。
