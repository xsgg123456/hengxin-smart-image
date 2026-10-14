# 海外删除修复 0.2.30 发布独立审查

- 送审 candidateId：`f7d82f59e8373d74ff49c76830870f1f86921f513814b0aabcb9aeb39b187d19`。
- **该候选 Stage 1：PASS；Stage 2：FAIL。1 项 MEDIUM，优化模式安全检查失效，修复前不登记发布批准。**
- 审查范围：前端版本、海外发布打包入口与对应测试、新增无迁移 hotfix 编排及测试，共 5 个代码/配置文件；复核相关复用 helper、发布计划及已批准功能证据。未执行任何生产写入、Git 提交或修复。
- 使用 `.agents/skills/code-review/SKILL.md` 两阶段流程。先核对快照与 Spec，再运行新增测试，最后检查实际部署调用链及失败路径。

## 快照与证据边界

审查开始独立 `review-status` 原始输出：

```json
{"currentId":"f7d82f59e8373d74ff49c76830870f1f86921f513814b0aabcb9aeb39b187d19","reviewedId":"db9678d135f34a887f940873784b81d1e0eff97d2cd45b2aeeb931cafb199647","changedFiles":["hengxin-smart-image/frontend/package.json","scripts/release/overseas-hotfix-deploy.py","scripts/release/overseas-hotfix-tests.py","scripts/release/package-overseas.py","scripts/release/test_package_overseas.py"],"approved":false}
```

因此业务后端、前端组件及既有功能测试与已批准功能快照完全一致；本次承接 [最终功能审查](OVERSEAS-DELETE-FINAL-20261013.md:1) 的独立 Linux 39 项、前端关键 7 项、视觉邻居对比，以及其中明确标注来源的 PG、完整前端与浏览器证据，没有将其声称为本轮重跑。

审查发现问题后主 Agent 修改了上述新编排和测试。收尾检测 currentId 已变为 `159d164b5c9f4250034089caf34b0feacbe5d559ec48f254a109864d7ae755b1`。本报告保留原快照 FAIL，不批准新快照；新快照须单独复核。以下问题行号为原送审快照，修复后的定位可能变化。

## Stage 1：Spec Compliance — PASS

### 功能条目逐项对应

以下 `backend/`、`frontend/` 路径相对仓库内 `hengxin-smart-image/`。所有条目均核对当前 Spec 原文和原独立报告；快照比较证明其业务实现未发生新变化。

| Product-Spec 行号 | 实现与验证证据 | 结论 |
| --- | --- | --- |
| 1026、1047：专用超级管理员权限 | `backend/app/overseas/permissions.py:24`、`tasks/deletion.py:33`；原报告非管理员拒绝及其他管理员删除测试 | 完整实现 |
| 1027：普通二次确认、取消和重试 | `frontend/src/views/overseas/OverseasTaskDelete.vue:5`、`:55`；`frontend/src/api/overseas/tasks.ts:74`，仅提交 version；原报告 SFC 与真实浏览器验证 | 完整实现 |
| 1028：双工作流、真实异步状态 | `backend/app/overseas/tasks/cleanup_files.py:61`、`tasks/queries.py:21`；`frontend/src/views/overseas/OverseasTasksPage.vue:97`，仅 deleted 移行 | 完整实现 |
| 1032、1048：任务数据、对象及 CLI 实际清理 | `backend/app/overseas/tasks/cleanup_records.py:12`、`cleanup_files.py:61`、`:131`；原报告无/部分/全部归档、legacy/studio 测试 | 完整实现 |
| 1033、1049：精确归档独立保留与访问 | `backend/app/overseas/archives/snapshot.py:27`、`archives/service.py:47`；原报告 ZIP 解压字节、SKU、数量和越权测试 | 完整实现 |
| 1034：改派与最后归属 | `backend/app/overseas/tasks/assignment.py:30`、`archives/service.py:75`；原报告改派竞争测试 | 完整实现 |
| 1035：共享资源与其他任务保留 | `backend/app/overseas/tasks/cleanup_files.py:75`、`:86`；当前代码仍严格限制工具名、6 层目录、arg0 后缀、精确 `/opt/codex` 叶子链接及安全 rmtree，原链接与硬链接拒绝测试保留 | 完整实现 |
| 1039：身份、版本、锁、重复归并 | `backend/app/overseas/tasks/deletion.py:32`；原报告并发、版本、CSRF 和重复请求测试 | 完整实现 |
| 1040、1050：先停止、迟到/并发/重启不复活 | `backend/app/overseas/tasks/cleanup_process.py:31`、`cleanup.py:35`、`:51`；原报告真实子进程与 PG 竞争测试 | 完整实现 |
| 1041：归档先保护后清理 | `backend/app/overseas/tasks/cleanup.py:38`；原报告保护失败及归档竞争测试 | 完整实现 |
| 1042、1051：可恢复失败、不伪报成功 | `backend/app/overseas/tasks/cleanup.py:42`、`:57`、`deletion.py:49`；原报告故障与断网浏览器验证 | 完整实现 |
| 1043：核实实际完成、归档权限保留 | `backend/app/overseas/tasks/cleanup_files.py:117`、`:138`、`cleanup.py:55`；原报告对象未消失故障与独立归档访问验证 | 完整实现 |

### 发布计划与范围

- **版本与构建输入一致**：`frontend/package.json:3`、`scripts/release/package-overseas.py:16`、`:36`、`:178` 与 `overseas-hotfix-deploy.py:24` 固定 0.2.30、20261014 发布名，必带新 hotfix 入口；打包独立 25 项通过。
- **无迁移、范围只限海外服务及共享前端**：`overseas-hotfix-deploy.py:34` 只读检查 0028/overseas_0014，`:217`、`:229`、`:230`、`:232` 只停止/切换海外 API 和两个原生 unit。覆盖层 `:79` 只准许 API image/build 变化；独立成功路径测试验证不调用 migrate、restore、Skills 安装。
- **关入口后排空，再停止执行器**：`:121` 只替换海外 location，`:133` 轮询两条公开路由为 503；`:55` 连续两次 DB 与 broker 空闲；`:70` 停 outbox 后再两次检查才停 worker。`member-release-drain.py:15` 读取 active/reserved/scheduled、队列及 unacked；未知状态不被视为空。独立 busy/unknown、稳定采样及晚到发布用例通过。
- **备份在切换前**：`:223` 调用 `overseas-update-runtime.py:107`，保存 Compose/env、前端入口、原生配置/指针和数据库 dump；pg_restore --list 成功后写 COMPLETE，`:224` 验证标记。没有自动数据库恢复。
- **安装校验和未授权资源保护**：`:162` 校验 API 镜像、全部后端文件、挂载及原生 PID/cwd，`:144` 校验国内、identity 容器与原生进程不变；`:181` 调用只读 Skills 验证。`:237` 仅 reload 共享 web，`:243` 发布前端；`:244`、`:250` 验证正式资源与匿名权限。
- **失败关闭且不误杀执行器**：`:260` 关闭入口、停止海外 API、记录失败阶段；没有回滚数据库或强停未知 worker。独立阶段注入覆盖 close、closed、drain、backup、switch、installed、proxy、publish、frontend、open、public、resources。
- **未授权真实删除不发生**：脚本没有业务 DELETE 或重试调用；`backend/app/overseas/tasks/cleanup.py:71` 仅调度 deleting，旧 delete_failed 不会因重启自动重试。本轮生产 inventory、正式 Chrome 验收属于发布后的主 Agent 步骤，尚未声称完成。
- **UI 与引导**：符合 `Design-Brief.md:182`；`OverseasTaskDelete.vue:5` 无名称输入框，`:6` 显示任务名，`:7` 明示删除范围和归档保留，`:9` 提供取消/确认。新 delta 不改变视觉；承接原报告实际打开删除/归档邻居及 390px 视觉证据，不虚称本轮另开页面。
- 部分实现：无。未实现：无。Spec 漂移：无新增业务页面/API/表/依赖；5 个 delta 均为当前发布计划所需。

## Stage 2：Code Quality — FAIL

### MEDIUM：优化模式保护本身被优化删除

- 位置：原 `scripts/release/overseas-hotfix-deploy.py:276`。
- 实际代码：`assert not sys.flags.optimize, 'Python -O disables release safety assertions'`。
- 触发：使用 `python -O`，或运行环境配置 `PYTHONOPTIMIZE=1`。Python 会移除 assert，包括该防护本身；随后版本、快照、拓扑、schema、文件 hash、已排空状态等断言均不再执行。此入口明确尝试禁止优化模式，实际未阻断。
- 独立复现：在本地 `python -O` 中导入原候选，mock `validate`、构建模块和 umask，以合法 build 参数调用 main；没有连接服务器或构建真实镜像。原始输出：

```text
optimize=1
validate_called=True
build_called=True
```

- 依据：[Python 官方命令行文档，-O](https://docs.python.org/3/using/cmdline.html#cmdoption-O) 明确说明该模式删除 assert，且 `PYTHONOPTIMIZE` 具有相同作用。原 12 项测试只调用内部函数和普通解释器，没有证明优化模式门禁有效。
- 必要修复：在 main 中使用不会被优化移除的 `if sys.flags.optimize: raise RuntimeError(...)`，增加真实 `-O` 和环境变量优化子进程回归，证明在进入任何生产调用前终止。主 Agent 已告知完成修复，但属于另一候选，本报告不越过独立复核批准它。

### 其余质量与安全检查

- 原送审新增编排、测试及两个打包文件均未超过 300 行；编排通过已有 helper 复用拓扑、排空、备份、发布和验证，职责清晰。证据：`overseas-hotfix-deploy.py:14`、`:49`、`:79`、`:144`、`:189`。
- 新 delta 无 TypeScript any；命令以参数列表执行，未引入 shell 字符串求值、拼接业务 SQL 或前端秘密。扫描 eval/innerHTML/dangerouslySetInnerHTML/密钥及秘密环境变量模式无命中；固定 `/opt/`、systemd 与容器路径属于已核对生产拓扑。证据：`overseas-hotfix-deploy.py:20`、`:21`、`:230`；`member-release-runtime.py:45`。
- 测试使用隔离目录和明确事件断言，确实验证调用顺序、故障后关闭、资源漂移、未知队列拒绝；未把 mock 当成真实服务器安装或业务删除证明。证据：原 `overseas-hotfix-tests.py:95`、`:117`、`:155`、`:263`。优化模式原有盲区单列上述问题。
- 依赖未改。读取当前构建与审计记录：critical=0、high=70、moderate=48、low=5 属既有告警，未声称依赖零漏洞。证据：`docs/OVERSEAS-DELETE-RELEASE-20261014.md:24` 及 `output/overseas-delete-release-audit.json`。

## 独立测试、编译与原始输出

原候选独立执行 `python scripts/release/overseas-hotfix-tests.py`，退出 0：

```text
..........OVERSEAS_HOTFIX_COMPLETE fixture
..
----------------------------------------------------------------------
Ran 12 tests in 0.399s

OK
```

原候选独立执行 `hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_package_overseas.py -q`，退出 0：

```text
.........................                                                [100%]
25 passed in 1.74s
```

以上实际加载了原 Python 源码，未出现语法/导入错误。前端不重复构建以避免生成文件改变快照；独立读取主 Agent 的 `output/overseas-delete-release-build.log`，原始关键输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
> hengxin-smart-image-frontend@0.2.30 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4708 modules transformed.
✓ built in 50.20s
```

收尾 `git diff --check` 退出 0，仅 CRLF/LF 既有提示；同时检测到主 Agent 的修复已改变快照，因此收尾内存编译结果不用于批准原候选或新候选。

## 交接

原候选为 Stage 1 PASS / Stage 2 FAIL；主 Agent 应对新候选 `159d164b5c9f4250034089caf34b0feacbe5d559ec48f254a109864d7ae755b1` 安排独立差异复核后，依据新报告登记 review-approve。不得以本报告批准原快照，不写 clean。正式安装、生产只读 inventory、Chrome 弹框验收与真实发布状态仍由主 Agent 执行并记录。
