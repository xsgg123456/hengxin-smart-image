# 海外轻量化发布与权限恢复独立审查 · 2026-11-07

## 快照、范围与结论

- 主 Agent 提供的 candidateId：`2cd1c30f5a34b7b5a646276e9e3328f6fc7a07b7040d91205bdc96696efd6cab`；HEAD：`0b9d68b8f402c3cc341909a6f416ffd1a55c2995`。审查开始、报告写入前和写入后的 `review-status` 的 `currentId` 均为该 candidateId、`approved: false`；受控差异是下列七个发布和测试文件，审查期间没有发生受控代码变化。
- 本次范围：`scripts/release/overseas-light-{deploy,package,runtime,frontend,guard}.py`、`scripts/release/test_overseas_light_{release,installer}.py`，以及它们所调用的恢复收据和入口控制代码。对照 `Product-Spec.md:1–27`、`DEV-PLAN.md:1–7`、`docs/OVERSEAS-LIGHT-RELEASE-20261107.md:3–7` 和前次审查问题；业务与 UI 仅映射此前对同一业务提交的独立审查，不将旧审查当作本候选的批准。
- **Stage 1：FAIL，2 项 HIGH、1 项 MEDIUM；Stage 2：未执行。** 不得登记本候选两阶段 PASS。修复后重新固定候选并从 Stage 1 开始复审；本报告不能覆盖后续代码版本。
- 未访问或修改生产，未部署、提交、修改受控代码或调用付费模型。主 Agent 转述线上只读观察：`/opt/hengxin-smart-image` 和 `frontend` 为 `root:root 777`，`dist` 及其全部 8 个子目录为 `root:root 755`，旧包所需目录存在；本审查未独立核验该生产信息，也未生成新正式包。

## Stage 1：发现的问题

### HIGH 1 · 强制终止可能让权限恢复入口卡在固定临时文件

**要求：** `docs/OVERSEAS-LIGHT-RELEASE-20261107.md:7` 要求强制终止后保留原始权限收据、阻止新发布，并能通过原工作目录的 `recover-permissions` 核验目录身份后恢复。

**实际：** `overseas-light-guard.py:183–190` 正常退出时先恢复模式，再通过 `r.private` 写 `FRONTEND_PERMISSIONS_RESTORED.json`，最后清空共享锁状态。`account-runtime.py:45–51` 的 `r.private` 使用固定的 `.new` 文件和独占创建；在 `.new` 创建后、替换正式文件前被 SIGKILL，`.new` 残留。`overseas-light-guard.py:111–131` 的恢复入口再次调用相同的 `r.private`，遇到残留文件直接抛 `FileExistsError`，不会清除 pending；`overseas-light-guard.py:145–148` 因此持续拒绝新发布。原始权限收据依然存在，无法用文档指定的恢复命令完成恢复闭环。实际注入位置与原始输出见后文验证 3。该复现中两目录模式已是 777，问题是恢复流程和后续发布卡住，不能据此说线上权限已损坏。

**测试盲区：** `test_overseas_light_installer.py:260–321` 在受保护代码块内部发送 SIGKILL，然后执行恢复；未覆盖写恢复完成收据时的中断。`test_overseas_light_installer.py:324–355` 只覆盖受保护代码块内部的 SIGQUIT。

### HIGH 2 · 回退保护状态未确认时已经重开入口

**要求：** `DEV-PLAN.md:7` 要求以保护、备份和回退方式发布；`docs/OVERSEAS-LIGHT-RELEASE-20261107.md:7` 要求未确认完整恢复前保持入口关闭并留下证据。

**实际：** `overseas-light-deploy.py:245–258` 对前端和旧 API 的回退异常保留关闭状态，但随后在 `:259` 先重开入口，直到 `:260` 才调用 `r.unchanged(data['protected'])`，它会核对原生服务、源码、技能及其他容器（`skill-platform-runtime.py:61–67`）。如果该保护核对失败，`:262–263` 仅输出需检查，入口已被重开，而且该路径没有生成 `ROLLBACK_ERRORS.json`。验证 4 在本地将公共验收失败和回退后的保护核对失败注入真实 `deploy_locked` 控制流，观察到“恢复前端 → 恢复旧 API → 重开入口 → 保护核对失败”。外部操作使用桩，不代表已在真实代理上复现。`test_overseas_light_release.py:190–246` 把 `r.unchanged` 恒设成功，未测此失败顺序。

### MEDIUM · 锁状态短写后故障会让恢复与新发布都无法解析

`overseas-light-guard.py:89–97` 原位截断锁状态并循环写入 JSON；`:164–167` 在改变目录模式前写该状态。验证 5 在隔离 Linux 容器中注入一次合法短写和随后 ENOSPC，锁文件只剩部分 JSON；原始收据存在，两个目录仍为 777，但 `read_pending`（`:82–86`）使恢复和新发布均抛 `JSONDecodeError`。修复存储故障本身不会自动修复该状态；文档给出的恢复入口无法完成。该路径尚未触碰生产目录权限或流量，影响是需要额外人工处理才能继续发布，不应描述为已经造成业务故障。

## Stage 1：需求逐项对照与既有问题

| 条目 | 结论与证据 |
| --- | --- |
| `Product-Spec.md:7–11` 调用与执行：入口兼容、权限、实际操作人、幂等、日期、未知历史、图片和状态下钻 | 同一业务提交的既有独立审查逐条证据见 `docs/reviews/overseas-light-complete-20261107.md:17–20`；本次候选只变更发布及测试文件，未重跑业务测试。 |
| `Product-Spec.md:15–16` 成品库实际归档人、候选、历史及权限 | 同一业务提交的既有审查证据见 `docs/reviews/overseas-light-complete-20261107.md:21–22`；本次未重新验证。 |
| `Product-Spec.md:20–23` 任务实际负责人、20 条分页、状态、分批归档与显式完成 | 同一业务提交的既有审查证据见 `docs/reviews/overseas-light-complete-20261107.md:23–26`；本次未操作生产或重跑业务测试。 |
| `Product-Spec.md:27`、`Design-Brief.md:1–3`、确认预览和 UI | 同一业务提交此前的浏览器、预览数值及邻页比较见 `docs/reviews/overseas-light-complete-20261107.md:27,31–35,42`。本次发布脚本范围无页面改动，未重新打开 UI；新包和生产页面未由本次验证。 |
| 发布范围、已审身份及完整性 | `overseas-light-package.py:76–86,90–113` 要求已提交和审查身份，按提交取源并在 manifest 记录 candidateId；`overseas-light-runtime.py:21–27,30–66` 固定基线、助手清单及包内哈希。`test_overseas_light_release.py:155–186` 验证篡改、未声明文件和入口缺失。新正式包未构建。 |
| 公共 SVG 字节和资源冲突 | `overseas-light-package.py:30–35,64–71` 仅对 `assets/` 外的 SVG 做换行归一；`test_overseas_light_release.py:18–25` 验证样本。`overseas-light-frontend.py:122–148,196–205` 预检并以 `:83–90` 的排他链接避免覆盖并发出现的共享资源；`test_overseas_light_installer.py:178–201` 在 Linux 注入碰撞，验证原文件保留。仅覆盖所测路径。 |
| 无关目录、已存在目录和文件系统身份 | `overseas-light-frontend.py:151–174,196–205` 要求目标目录已存在且逐级为安全目录，只处理本包目标；`overseas-light-guard.py:137–182` 在锁内限制 app 与 frontend 的非所有者写权限，核对目录身份；`overseas-light-deploy.py:201–213` 检查 dist 是否对应 web 挂载。`test_overseas_light_installer.py:10–50,70–125,128–175,204–226` 在隔离 Linux 验证无关目录、链接、拒绝缺失/可写目录及非 root 改名；主 Agent 转述的实际 777/755 模式与这些前提一致，但本次没有直接核验生产。共享锁只覆盖使用该锁的发布进程，不能阻止不遵循锁的 root 进程。 |
| 多工作目录并发和权限恢复 | `overseas-light-guard.py:61–79,137–190` 通过 app 父目录共享的 flock、pending 和唯一收据序列化；`overseas-light-deploy.py:267–273` 在锁内重验发布状态。`test_overseas_light_installer.py:229–257,260–321` 覆盖并发、受保护代码块内 SIGKILL、目录 inode 改变和原收据保留；恢复收据中断及锁状态短写仍存在上列问题，因此此项只部分实现。 |
| 备份、旧 API 回退与异常 | `overseas-light-frontend.py:177–195,222–240` 备份入口、验证备份与预期后回退；`overseas-light-deploy.py:235–258` 捕获前端回退异常后仍尝试旧 API，前端或 API 回退异常不重开入口；`test_overseas_light_release.py:220–265` 检查前端回退失败及未确认 API 停止的桩控制流。保护状态核对的顺序仍违反上列 HIGH 2，因此完整回退保护只部分实现。 |
| 生产发布与真实验收 | `Product-Spec.md:27`、`DEV-PLAN.md:7` 要求正式构建、隔离安装及生产验收。`docs/OVERSEAS-LIGHT-RELEASE-20261107.md:3–7` 记载首轮回退和新版本尚未成功部署；这是主 Agent 记录，本次未在线核查，不能宣称交付完成。 |

**Spec 漂移：** 本次七个受控差异限于发布助手和对应测试；`overseas-light-deploy.py:276–296` 新增的 `recover-permissions` 对应发布记录第 7 行，未在本范围发现无需求依据的新业务页面、API 或表。未做全仓漂移审计。

## 本候选独立验证原始输出

1. Windows：`hengxin-smart-image/backend/.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider scripts/release/test_overseas_light_release.py scripts/release/test_overseas_light_installer.py`，exit 0：

```text
.....................                                                    [100%]
21 passed in 1.07s
```

Windows 上 POSIX/root 专用分支按测试中的条件直接返回；此结果不证明 Linux 的 fork、信号和权限路径。

2. 本地 `python:3.12.10-slim-bookworm` 容器，网络禁用、根文件系统与源码挂载只读、临时文件位于容器 `/tmp`；执行 `python -B /review/test_overseas_light_installer.py`，exit 0：

```text
ISOLATED_INSTALL_AND_ROLLBACK_PASS
```

安装测试使用本地 manifest 桩，是真实隔离文件系统上的静态安装、回退、锁、信号和权限操作，不是新正式包、真实代理或生产部署测试。

3. 同一隔离容器，在恢复完成收据的临时文件写完但 `os.replace` 前暂停子进程并发送真实 SIGKILL，再调用真实恢复入口并尝试另一工作目录发布，exit 0：

```text
original_receipt_exists: True
stale_recovery_temp_exists: True
modes_before_recover: 0o777 0o777
recover_result: FileExistsError [Errno 17] File exists: '/tmp/review-kill-window-hig3lh2l/work/FRONTEND_PERMISSIONS_RESTORED.json.new'
new_publication: RuntimeError Unfinished publication permissions require recovery
```

4. Windows 本地临时目录调用真实 `deploy_locked`，外部服务、入口和安装使用桩：公共验收故意失败，第一次保护核对成功、回退后保护核对失败，exit 0：

```text
ROLLBACK_REQUIRES_INSPECTION: C:\Users\82358\AppData\Local\Temp\review-rollback-order-ffi1bnzf
deployment_error: public check failed
events: gate_closed -> stop -> api-overlay.json -> protected_checked_1 -> frontend_installed -> gate_opened -> gate_closed -> frontend_restored -> old-overlay.json -> old_api_ready -> gate_opened -> protected_checked_2
rollback_errors_receipt_exists: False
```

5. 同一隔离 Linux 容器，锁状态写入时先真实写入 8 字节，再注入 ENOSPC；随后调用真实恢复入口和另一工作目录发布，exit 0：

```text
first_publication: OSError [Errno 28] injected storage failure after partial write
pending_bytes: b'{"id": "'
original_receipt_exists: True
modes_after_failure: 0o777 0o777
recover: JSONDecodeError Unterminated string starting at: line 1 column 8 (char 7)
new_publication: JSONDecodeError Unterminated string starting at: line 1 column 8 (char 7)
```

6. 对七个受控发布 Python 文件执行 `compile(path.read_bytes(), ..., 'exec')`，exit 0，原始输出：

```text
COMPILE_OK 7
```

7. `git diff --check`，exit 0，原始 stdout 为空；stderr 为三项 CRLF 将转换为 LF 的 Git 警告，分别指向 `overseas-light-deploy.py`、`overseas-light-runtime.py` 和 `test_overseas_light_release.py`。审查开始及写报告前的原始 `review-status` 均显示：

```text
{"currentId": "2cd1c30f5a34b7b5a646276e9e3328f6fc7a07b7040d91205bdc96696efd6cab", "reviewedId": "e5f6f10a2a368742bf9aca90c2bb2449fe63ba9fb616196bc49d68b8e47672d9", "changedFiles": ["scripts/release/overseas-light-deploy.py", "scripts/release/overseas-light-frontend.py", "scripts/release/overseas-light-guard.py", "scripts/release/overseas-light-package.py", "scripts/release/overseas-light-runtime.py", "scripts/release/test_overseas_light_installer.py", "scripts/release/test_overseas_light_release.py"], "approved": false}
```

## 未执行

Stage 1 有 HIGH，未执行 Stage 2 完整代码质量、安全扫描、测试真实性审查及邻页视觉复核。上述针对失败路径的测试证据不构成 Stage 2 PASS。未生成新的已审正式包，未测试真实新包动态资源、线上安装、真实代理切换或生产验收。
