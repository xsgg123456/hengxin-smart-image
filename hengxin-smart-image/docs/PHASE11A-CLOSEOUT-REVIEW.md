# Phase11A 新增验收脚本独立审查

日期：2026-09-11。Stage 1：**PASS（本次新增脚本的实现范围）**。Stage 2：**FAIL**，发现 3 项 MEDIUM 缺陷；另有 1 项 LOW 证据标注建议。本结论不是 Phase11A 整阶段验收通过，也不授权登记两阶段 PASS。

## 快照、范围与执行边界

- 当前复核 candidateId：`30c7459d4cb23c19bfb4f9c050d76734b5099bc885a89fefc281f26b1e4f731a`。初审 candidateId：`1d14ee6937e8ffa0d956e19be201eb8c00d0d413e30500a0ad361ffde1357b43`；已对最新快照重新核对审查范围及基线差异，以下Stage结论适用于当前candidate。
- 既有已批准业务基线：`bcda98015d46971bc9d1de4259ef4cc43b5e4e7ab89ecea5f82b7480f036b5cf`；已只读核对 `.codex/review-state.json` 的 `approved.snapshot.id` 与之相同。该文件的 `baseline.id` 是另一历史初始化快照，不将其混作本次业务基线。
- 仅审查下表 9 个文件；正文路径均相对 `hengxin-smart-image/`。既有业务源码只作必要接口上下文读取，不重复全库审查。
- 9 个文件按 CRLF→LF 归一后的 SHA256 全部匹配 candidate 的对应文件。审查中未修改源码、未操作现有运行环境、未启动模型、未运行数据库测试或发信号；仅执行内存语法编译、读取既有结果以及纯内存反例模拟，写入本报告。不提交、不 approve、不写 clean。
- 主 Agent 已恢复 Vite 自动变更的 `frontend/src/types/import/components.d.ts` 并重新 prepare；只读核对该文件当前内容与HEAD完全一致。新candidate相对已批准业务基线的差异恰为表中9个文件，没有其它代码变化。后续源码变化必须重新固定快照并复核。

| 文件 | 行数 | SHA256 前12位（已核对完整值） |
| --- | ---: | --- |
| infra/phase11a_environment.py | 219 | 91ed3f75a330 |
| infra/phase11a_processes.py | 201 | 77e223995b031 |
| infra/phase11a_inputs.py | 79 | 2904ab42496c |
| infra/phase11a_checks.py | 153 | bc21144406cd |
| infra/phase11a_faults.py | 91 | fd1ffade2d93 |
| infra/phase11a_regressions.py | 48 | c272f4f72d70 |
| infra/verify_phase11a_live.py | 212 | 890f520a74f29 |
| backend/tests/test_phase11a_environment.py | 217 | b1bbf3f53ca0 |
| backend/tests/test_phase11a_checks.py | 43 | 8b38361f589e |

## Stage 1：Spec Compliance

已读取 `.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、根目录 `DEV-PLAN.md:351–382`、`Product-Spec.md:231–241` 和 `docs/PHASE11A-CLOSEOUT-PLAN.md:1–13`。此阶段核对实现入口和范围；断言能否真实证明行为在 Stage 2 单独审查。

| 需求条目 | 实现及结论 |
| --- | --- |
| Spec 8.3:235，真实壁纸生成、预览、同会话单张/整套返工、下载归档 | API 串行入口完整：`infra/verify_phase11a_live.py:61–153`，下载图片解码 `infra/phase11a_checks.py:127–143`。浏览器由主 Agent 验收；ZIP 由主 Agent 独立浏览器验收补齐，见 Stage 2 建议 R1。商品/文字 Skill 不在本轮范围，不虚报完成。 |
| Spec 8.3:236，CLI、认证、工具与 Linux 隔离前置 | 新 helper 检查非 root hengxin、既有运行时和三个配置文件路径：`infra/phase11a_environment.py:20–28,85–101`；实际任务沙箱双向探测 `infra/phase11a_checks.py:107–124`。完整 CLI/工具前置沿用已审基线，本轮不重审；每轮 CLI 版本采集位于 `infra/phase11a_checks.py:30–36`。 |
| Spec 8.3:237，独立数据、私有目录、凭据与 fixture 隔离 | 独立随机标记、临时根、独立 PG/Redis/MinIO、关闭 fixture/测试任务：`infra/phase11a_environment.py:29–36,69–83,102–116`。实际来源导出只读：`infra/phase11a_inputs.py:24–60`。清理异常覆盖问题见 R4。 |
| Spec 8.3:238，先串行后并行2，默认并发1/超时3600，无自动模型重跑，资源与恢复 | 执行顺序 `infra/verify_phase11a_live.py:189–193`；并行采样及恢复1 `:155–174`；默认设置 `infra/phase11a_environment.py:34–36,114`；失败直接抛出 `infra/verify_phase11a_live.py:51–59`；CPU/RSS采样 `infra/phase11a_checks.py:38–65`；异常恢复 `infra/phase11a_faults.py:10–57`。重复执行和异常终态断言问题见 R2/R3。 |
| Spec 8.3:239，真实 attempt/session/新生成图片和版本证据，不能只凭退出码 | `infra/verify_phase11a_live.py:117–153` 检查来源/session/版本；`infra/phase11a_checks.py:91–105` 对比会话生成路径与发布字节；`:127–143` 实际解码图片。报告中记录模型播报与真实 attempt。证明强度缺陷见 R2，不能把辅助校验等同工具调用证明。 |
| Spec 8.3:240，效果、未提供 Skill、钉钉、部署、容量边界 | 入口仅创建 wallpaper 测试对象：`infra/verify_phase11a_live.py:72–97`，没有新增商品/文字、钉钉或容量验收；不将并发2推断为生产容量。 |
| Spec 8.3:241，尺寸例外，不缩放伪造 | `infra/verify_phase11a_live.py:17–18,26` 显式声明豁免；`infra/phase11a_checks.py:134–143` 只解码、记原始尺寸并保存原字节，没有 resize。 |

DEV-PLAN Phase11A 五项交付均核对：前置检查映射 environment:85；可启停隔离环境映射 environment:41–54,176–190；实际素材闭环映射 inputs:17–65 / verify:61–153；实例与并行故障映射 verify:155–174 / faults:10–91；回归和可复验入口映射 regressions:14–44 / verify:177–208。对应收尾计划第1–5步，没有新增产品 API、业务表或页面；全部是验收基础设施，未发现 Spec 漂移。

DEV-PLAN 验收逐项：377（真实 CLI/attempt/图片）及378（会话/版本/归档）已看到串行结果；379（双任务重叠/幂等/归属）有实现，最终 parallel-acceptance 已通过；380（取消/超时/Worker恢复）Worker 出版前崩溃恢复、早期取消及超时已有最终结果；381（浏览器/资源/失败证据）浏览器属主 Agent 证据，资源采样在脚本中；382（默认1/数据保留/未提供Skill边界）有隔离及恢复实现，最终 cleanupComplete=true、cleanupErrors=[] 已读取。未把运行中尚无结果判作产品缺失。

UI 一致性及视觉邻居对比：本次 9 文件没有 UI 变更，不适用，未启动浏览器操作用户任务。主 Agent 已报告素材原图预览、Codex 播报、恢复后重试刷新、图片 v3/v2、点击下载整套；这些是主 Agent 提供的证据，不冒称 reviewer 独立浏览器验证。

Stage 1 未发现 HIGH 核心入口缺失，进入 Stage 2。上述 PASS 仅代表送审实现范围覆盖，不表示所有验收断言正确或运行全部通过。

## Stage 2：Code Quality / 测试真实性

### R1 · LOW · 脚本 ZIP 与产品实际下载证据须明确区分（非阻塞）

- 位置：`infra/phase11a_checks.py:127–148`；对应测试 `backend/tests/test_phase11a_checks.py:15–25`。
- 需求：根目录 `DEV-PLAN.md:361,381` 与收尾计划第2步要求实际单图/ZIP 下载及包内容一致。
- 实际：函数逐个 GET 图片后，用 Python `ZipFile` 自行构建 ZIP，再读回自己构建的 ZIP 校验。测试也只检查这个自制文件。产品下载按钮、选择图片列表、文件命名、下载打包流程即使损坏，该检查仍通过。
- 处理：保留其图片可解码证明；ZIP 证据必须来自产品实际下载链路，并核对真实下载包的文件数量/名称/图片字节。最新主 Agent 已核验实际 `C:/Users/EDY/Downloads/Phase11A-serial.zip`：两张可解码、CRC通过、逐张hash匹配API当前版本，记录于 `docs/PHASE11A-CLOSEOUT-RESULTS.md:26–30`。因此产品ZIP覆盖已由独立浏览器证据补齐，本项降为 LOW、不阻塞；仍不得将脚本 `initial.zip` 等自制包标为产品ZIP验收。

### R2 · MEDIUM · 串行/恢复的 attempt 唯一性断言可漏掉重复调用

- 位置：`infra/phase11a_checks.py:67–86`，调用处 `infra/verify_phase11a_live.py:151–153`；故障恢复前后检查 `infra/phase11a_faults.py:51–57`；测试 `backend/tests/test_phase11a_checks.py:36–43`。
- 需求：根目录 `DEV-PLAN.md:362,379`，每轮仅执行一次，恢复不重复调用可能已计费轮次。
- 实际：`execution_count == 1` 是 JOIN 得到的 Job 字段，不能替代按 `round_id` 验证 attempt 数量。恢复前只检查1条，恢复后的 `round_evidence()` 允许同轮多个 finished attempt，只要它们关联的 job execution_count 都为1；也不要求 PID/CLI版本非空。并行路径单独检查 len=1，不覆盖串行三轮。
- 纯内存反例提取原函数执行，无导入业务模块、无环境操作，原始输出：

```text
COUNTEREXAMPLE: round_evidence accepted 2 finished attempts for same round with execution_count=1; returned rows=2
COUNTEREXAMPLE: both attempts had process_id=None and cli_version=None; no rejection
```

- 处理：对期待的 round 集合逐一断言唯一 attempt、非空执行身份/CLI版本，并在恢复后对比原 attempt 身份；补充“同轮两条attempt但job计数1”的负例。真实本轮记录目前确实是三轮各一条，问题是脚本漏检能力，不是断言此次发生了重复收费。

### R3 · MEDIUM · 取消/超时可以在业务轮次未终结时提前写通过证据

- 位置：`infra/phase11a_faults.py:67–89`，`infra/phase11a_checks.py:67–86`。
- 需求：根目录 `DEV-PLAN.md:380`，停止对应执行进程组并完成可解释的取消/超时处理。
- 实际：等待循环的 break 同时要求 attempt finished 与 round failed/cancelled，但超出90秒后 `:83` 只检查 attempt finished。若 receipt 已记录 cancelled/timeout 且轮次持续 running/uncertain，`:87–89` 仍可写 `real-cli-*` 记录；辅助 `round_evidence()` 也不检查 round 终态。之后 restart 的 idle 检查可能使整轮失败，但此前生成的单项“成功”证据已不真实。
- 另：等待 PID 即停止采样 `:69–74`，PID可能只是监督进程；没有要求实际 Codex 子进程已出现，再发取消；elapsed_seconds 仅记录，不对10秒超时设置宽容但明确的区间断言。因此单凭该函数不能证明生图工具执行中取消，也不能自动发现偏离设定值的超时时长。最终实测取消0.235秒明确限定为启动后早期取消，属于有效的窄范围证据，不因没有等待图像工具而判产品缺失。
- 处理：截止后仍强制检查期待的 round/job 终态，按声称验证的阶段采集出生身份及退出证据；超时耗时采用包含调度容差的断言；为这些失败状态添加负例。最终本轮终态正确，但不消除截止分支漏检缺陷。

### R4 · MEDIUM · 轮询发现后代无法覆盖父进程在首次捕获前退出

- 位置：`infra/phase11a_processes.py:46–65,105–124,163–201`；测试 `backend/tests/test_phase11a_environment.py:137–152`。
- 需求：收尾计划第1/4步精确清理本轮资源及 Worker 失联保护。
- 实际：每0.1秒通过活进程的 PPID/session 发现后代。如果子进程新建 session 后，父进程在两次扫描之间退出，该子进程已被重新挂到 PID1（或其他 subreaper），不再属于已知 live PPID/session；它不会加入 births。后续 `_stop()` 看不到它，cleanup 可能删除工作目录并标 cleanupComplete，但子进程仍存活。
- 现有测试在杀父进程前显式调用 capture 并断言子进程已登记，故只证明“已捕获后代”可回收，避开上述窗口。PID birth/pidfd 能防止杀错已追踪进程，不能补回未发现的孤儿。
- 原函数纯内存 /proc 表反例（无实际进程创建/终止），原始输出：

```text
COUNTEREXAMPLE: child started a new session and parent exited before next capture; child tracked=False
SIMULATION ONLY: fake /proc table, no processes launched or signalled
```

- 处理：使用能覆盖父进程突死的归属机制，或结合本轮执行身份做遗漏进程核实；未核实完不得声明 cleanupComplete。补充不提前手动 capture 的父进程快速退出场景。不能以扩大进程名称匹配或批量 kill 代替所有权核实。此项为异常窗口缺陷，不声称本次运行已遗留进程。

### 其余质量与安全检查

- 命名/职责/体积：9文件均少于300行，环境、进程、素材、断言、故障、回归、入口分离；见范围行数表。Python方法多未标注参数/返回类型，例如 `infra/verify_phase11a_live.py:21–40`，记为 LOW 可维护性建议，不额外阻断。
- 凭据：随机临时服务凭据及严格应用环境在 `infra/phase11a_environment.py:102–116`；服务stdout/stderr丢弃、命令错误不输出参数在 `infra/phase11a_processes.py:67–95`；回归日志对临时密码替换在 `infra/phase11a_regressions.py:41–42`。范围内未发现硬编码真实密钥。认证只引用既定文件，不复制完整 CODEX_HOME（environment:88–91）。
- SQL/命令：任务ID经 UUID 转换且 SQL 参数化（inputs:18,47–49；checks:30–36），命令以 argv 执行（processes:67–71）；代码字符串只使用受控参数并 repr（environment:145–154；checks:115–123）。有意故障 `os._exit(71)` 仅注入专用 Worker（faults:12–21），没有修改磁盘业务源码。
- 环境/清理正向保护：私有端口及标签（environment:69–83）、删除前精确名称和标签检查（processes:149–161）、临时根 inode/属主/位置校验（processes:190–196）、pidfd及birth校验（processes:25–36）均存在；R4限制了异常清理完整性证明。
- 回归隔离：`infra/phase11a_regressions.py:19–40` 检查本轮容器标签和私有端口，在该容器建立随机 `_test` DB，finally删除该DB；无操作实际生图数据库的语句。审查未重复执行此脚本。
- 测试边界：现有测试确实覆盖并发设置竞态、外来资源拒删、出生身份不符不发信号、已知后代回收、目录拒删、超时隐藏凭据及非图片拒收（environment tests:28–217；checks tests:15–43）；未覆盖 R1–R4 的关键反例。

## 实测证据与编译

只读读取 `\\wsl.localhost\Ubuntu-24.04\home\hengxin\runtime\phase11a-closeout-results\report.json`。首次读取时 status=running；报告结束前再次只读读取，status=passed，已包含串行、并行、取消、超时及cleanup最终结果。

serial-acceptance：任务 `c003957f-f36e-4ef8-9b5e-20ac0f8f13cb`，session `01a09042-04cb-7272-bb39-a0d6522855bb`；三轮分别 PID 12624、14372、15834，CLI版本均0.153.4，finished/succeeded、exit_code=0、execution_count=1。worker-interruption-gate记录uncertain、返工拒绝与3次redelivery；正常Worker恢复后第三轮完成。对应读取链路见 verify:113–153 / faults:10–57。该结果支持已完成串行业务，不消除断言反例。

独立执行的9文件内存语法编译原始输出（exit code 0）：

```text
COMPILE PASS: 9/9 files (in-memory compile; no imports, no pyc, no environment operations)
```

既有完整PG回归产物 `phase11a-closeout-results/regression.txt` 末段原始输出：

```text
  /mnt/d/solveproblems/SOP/hengxin-smart-image/hengxin-smart-image/backend/app/modules/auth/dependencies.py:20: SAWarning: fully NULL primary key identity cannot load any object.  This condition may raise an error in a future release.
    user = session.get(UserRecord, identity_id)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
637 passed, 10 warnings in 44.78s
```

这是读取既有日志，不是 reviewer 重跑测试。前端79 pass、build/typecheck通过、独立环境smoke并发1→2→1及cleanup成功为主 Agent 提供信息，本轮未拿到相应完整原始输出，不伪造编译记录。前端不属于本次源码范围。主 Agent 另行更新最终实测文档；本报告已读取机器最终结果，见下节。

## 最终实测增补与快照复核

- `parallel-acceptance`：任务 `f2f5d46f-781d-4502-8ac4-da19ae8c47af` / `c171e142-94b4-4a90-ab1a-bea3efb55158`，PID17073/16825，session分别 `01a0904a-69ed-7803-8f94-5ea81f199ac6` / `01a0904a-683d-7a80-a3cb-b002034f56df`。各1 attempt/count1/exit0；运行区间分别11:46:29.277–11:48:14.473 UTC、11:46:28.896–11:48:31.911 UTC，明确重叠；记录 simultaneousCliObserved=true、actualSandboxReadWriteIsolation=true，输出归属校验完成。检查实现见 verify:155–174 / checks:91–124。
- `real-cli-cancelled`：PID18837，exit -15，elapsed0.235秒，round_status=cancelled、attempt finished；仅表述启动后早期取消，不能表述图像工具执行中取消。`real-cli-timeout`：PID19013，exit -15，elapsed10.189秒，round_status=failed、attempt finished。对应 faults:60–91。
- `environment`：run=hx-p11a-e3d7cadd6e59bdf7，restarts=3，cleanupComplete=true，cleanupErrors=[]，concurrency=1，defaultConcurrencyRestored=true。这是当前运行实际结果，不覆盖R4未测试竞态。
- 主 Agent 已将 report.json、regression.txt 复制至 `output/playwright/phase11a-closeout/`，并报告退出码0、3009 Vite已结束、正常controller仍active。reviewer未对运行服务作任何操作。
- 结束前9个范围文件再次比较候选完整SHA256，原始输出：

```text
END-REVIEW SCOPE MATCH: True FILES: 9
```

最新candidate已固定为 `30c7459d4cb23c19bfb4f9c050d76734b5099bc885a89fefc281f26b1e4f731a`。已重新读取review-state：对比approved业务基线，仅有本次9文件差异；9文件当前内容均匹配新candidate的完整hash，并与初审记录一致。components.d.ts当前内容与HEAD一致，因此基线外自动生成变化已排除。最新实测文档已补并行/故障/cleanup；这些证据更新未改变R2–R4代码及反例，Stage 2仍FAIL。

## 交回主 Agent

Stage 1 PASS；Stage 2 FAIL：阻塞项为 R2同轮attempt唯一性、R3截止后的终态漏检、R4首次捕获前孤儿进程窗口。R1已由实际浏览器ZIP证据补齐，降为LOW建议。三个阻塞项均为脚本/验证机制实际缺陷，不是对本轮产品运行失败的推断。应先修复并补负例，再 prepare 新candidate，从 Stage 1 起复核；本报告不支持 review-approve 的两阶段PASS登记。
