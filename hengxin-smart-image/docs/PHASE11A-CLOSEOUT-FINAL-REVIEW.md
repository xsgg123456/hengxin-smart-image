# Phase11A 收尾独立复审

日期：2026-09-11。**Stage 1：PASS；Stage 2：PASS。** 原报告 R2、R3、R4 已解决，本次范围未发现阻塞项。

## 快照与范围

- candidateId：`a6c7f9bd893f566d0e52f0c27506fec5e8ecec8dc272454e78fbe59df16d90c4`。
- 已批准业务基线：`bcda98015d46971bc9d1de4259ef4cc43b5e4e7ab89ecea5f82b7480f036b5cf`。开始、结束前的只读 `review-status` 均返回本候选；相对批准基线只差下列11文件。已逐文件核对候选完整 SHA256（CRLF→LF归一），不是以 Git HEAD 的全部脏文件作为复审范围。
- 按要求读取 code-review skill、根目录 `docs/HARNESS-REVIEW.md`、`Product-Spec.md:231–241`、`DEV-PLAN.md:351–382`、原 CLOSEOUT-REVIEW、CLOSEOUT-PLAN、CLOSEOUT-RESULTS。代码路径下文相对 `hengxin-smart-image/`，Spec/DEV-PLAN及 `output/` 路径相对仓库根目录。
- 只写本报告；未修代码、未操作服务、未启动模型、未重跑收费图像轮次、未 approve、未写 clean。Linux故障测试和全量回归来自主 Agent 执行的结果；reviewer 独立执行的是语法编译和内存反例，不混淆执行来源。
- 本结论仅批准范围内实现质量，不替代用户整阶段验收；范围外业务基线不重复审查。报告没有把旧真实业务报告改称新 supervisor 的收费运行结果。

| 文件 | 行数 | SHA256前12位（完整值已核对） |
| --- | ---: | --- |
| backend/tests/test_phase11a_checks.py | 98 | 955e67d4b254 |
| backend/tests/test_phase11a_environment.py | 219 | 849b7279d480 |
| backend/tests/test_phase11a_supervisor.py | 168 | b889ccbc8e34 |
| infra/phase11a_checks.py | 159 | 2bd454bd0502 |
| infra/phase11a_environment.py | 219 | 91ed3f75a330 |
| infra/phase11a_faults.py | 102 | 9a4f215e635b |
| infra/phase11a_inputs.py | 79 | 2904ab42496c |
| infra/phase11a_processes.py | 218 | 4a9ee9652b2e |
| infra/phase11a_regressions.py | 48 | c272f4f72d70 |
| infra/phase11a_supervisor.py | 82 | ea7ba198600f |
| infra/verify_phase11a_live.py | 216 | b9fd5f71e2a4 |

## Stage 1：Spec Compliance

以下逐项检查本轮验收基础设施的实现覆盖；既有CLI适配器、产品页面等仅承接已批准基线和既有实测，不声称本轮重新实现或浏览器复测。

| Spec 8.3条目 | 结论及证据 |
| --- | --- |
| 235：真实壁纸生成、预览、同会话整套/单张返工、下载归档 | 完整覆盖本轮脚本职责。`infra/verify_phase11a_live.py:61–157` 导入实际包及素材、串行生成/返工/归档；`:117,130,140` 检查真实来源与同session；`:129,142–150` 检查版本、非目标图、旧版本及归档字节。`infra/phase11a_checks.py:133–155` 解码下载图片。产品预览与实际ZIP由既有浏览器证据覆盖，见 `docs/PHASE11A-CLOSEOUT-RESULTS.md:24–28`；不把辅助ZIP当产品ZIP。 |
| 236：CLI/认证/图像工具/Skill依赖及Linux隔离前置 | 本轮接入检查完整：`infra/phase11a_environment.py:20–28,85–101` 限非root既有WSL运行时，引用指定认证及CLI/bwrap文件；`infra/verify_phase11a_live.py:70–85` 校验包哈希并等待真实安装成功；`infra/phase11a_checks.py:30–36,113–130` 采集版本、执行实际沙箱读写探针。完整工具前置沿用已审基线；本轮没有宣称Windows原生适配。 |
| 237：独立数据、私有目录、fixture保留、来源cli、凭据隔离 | 完整实现：`infra/phase11a_environment.py:29–38,69–83,102–116` 随机环境、独立服务/卷/端口、私有目录及关闭fixture；`infra/phase11a_inputs.py:24–60` 原来源仅GET、只读SQL和对象读取。清理按本轮标签、根目录身份执行：`infra/phase11a_processes.py:166–218`。 |
| 238：串行后并行2、默认1/3600秒、失败不自动重跑、资源及异常恢复 | 完整实现：`infra/verify_phase11a_live.py:193–197` 明确顺序，`:51–59` 失败退出，`:159–178` 并发2/重叠/隔离/恢复1；`infra/phase11a_environment.py:34–36,114,183–190` 保持默认；`infra/phase11a_checks.py:38–65` 采样CPU/RSS；`infra/phase11a_faults.py:10–58,71–102` 恢复、取消、超时。修复后的唯一性及恢复身份详见R2。 |
| 239：真实attempt/session/新图片/返工版本/下载归档，不能只凭退出码 | 完整覆盖脚本职责：`infra/phase11a_checks.py:67–92` 唯一attempt、预期round集合和非空执行身份；`:97–111` 发布字节必须匹配所属session生成文件；`:133–155` 图片解码；`infra/verify_phase11a_live.py:117–157` 会话、版本与归档检查。实际业务证据读取自旧完整report，修复后无模型测试仅证明辅助机制，不伪装新图像调用。 |
| 240：其余Skill、美观、钉钉、部署、容量的范围边界 | 匹配：`infra/verify_phase11a_live.py:72–97` 只建wallpaper对象；`docs/PHASE11A-CLOSEOUT-PLAN.md:7–9`、`docs/PHASE11A-CLOSEOUT-RESULTS.md:48–50` 明确其它边界，不把并发2解释为生产容量。 |
| 241：原生尺寸例外，不缩放伪造 | 匹配：`infra/verify_phase11a_live.py:17–18,26` 明示例外；`infra/phase11a_checks.py:140–149` 原图解码、记录尺寸、原字节保存，没有resize。 |

DEV-PLAN交付及验收逐条对应：

| 条目 | 核对结果 |
| --- | --- |
| 359：执行条件检查 | 匹配，environment:85–101、checks:113–130、verify:70–85；真实CLI版本证据见旧report串行/并行attempt。 |
| 360：可启停隔离环境 | 匹配，environment:41–54,158–190；新smoke启动/并发切换/重启/清理结果见下节。 |
| 361：实际素材与完整业务闭环 | 匹配，inputs:17–65、verify:113–157；实际浏览器ZIP证据与辅助ZIP明确分开。未提供商品/文字Skill不列为已测。 |
| 362：实例、双任务并行、争用、重投、恢复、资源 | 匹配，verify:122–126,151–178、faults:10–102、checks:38–92；R2/R3/R4补强与实测证据分别列明。 |
| 363：可复验交付 | 匹配，regressions:14–44、verify:181–216；原实测/本次复审报告和最终日志分开留存。 |
| 377：异步受理、cli来源、session、attempt和新图片 | 匹配，verify:94–117、checks:67–111；旧report:473起三轮记录完整。 |
| 378：不同任务隔离、同任务续接、版本与归档 | 匹配，verify:127–157,164–174；旧report:473及885起记录同会话/独立session及归档保存。 |
| 379：并行重叠、唯一执行、竞争与重投、归属 | 匹配，verify:122–126,151–177、faults:43–58、checks:67–76,97–130；旧report:336,885起。 |
| 380：取消/超时回收及Worker核实保护 | 匹配，faults:40–58,61–100、processes:123–139、supervisor:19–74；新测试关闭capture仍证明收养和回收。取消证据限启动后早期取消。 |
| 381：页面预览/下载、日志、资源及失败证据 | 匹配本次范围，checks:38–65,133–155、verify:51–54,199–212；页面实际操作承接RESULTS的浏览器记录，不冒称本轮新测UI。 |
| 382：默认1、保留数据、不改生产配置、不虚报 | 匹配，environment:29–38,109–116、processes:166–218；新smoke cleanup完整且默认恢复1。源数据只读，未提供Skill仍明确未验证。 |

完整实现项如上。范围内未发现部分实现或未实现项。无新增业务页面/API/表，11文件均为既定收尾验收基础设施，未发现Spec漂移。UI一致性、引导真实性与邻居视觉对比：本次无UI文件或页面变化，不适用；不启动浏览器扩审已批准业务基线。

Stage 1 未发现HIGH问题，进入Stage 2。

## Stage 2：原阻塞项复核

### R2：唯一attempt、完整执行身份、恢复身份——已解决

- `infra/phase11a_checks.py:69–76` 同时检查job execution_count、attempt finished、round不重复、期待round集合准确，以及PID/process_start/CLI版本非空。原反例“两attempt各count=1”现在被独立的round唯一性断言拒绝。
- `infra/phase11a_faults.py:51–58` 重投后要求单attempt，返回故障前attempt ID；`infra/verify_phase11a_live.py:151–154` 恢复完成后检查三轮集合并比对原attempt ID，不允许用替换attempt掩盖重新执行。
- 新负例 `backend/tests/test_phase11a_checks.py:51–74` 直接构造原漏洞条件，没有把execution_count改成2来绕开关键问题。独立内存验证另检查了空集合及额外/缺失round，7个负例全部拒绝；旧真实串行记录通过新唯一性和身份断言。恢复ID分支本轮通过代码核对，未重新发起收费整套返工。

### R3：截止后的终态与超时容差——已解决

- `infra/phase11a_faults.py:61–68` 强制一条attempt，attempt finished、round/job均为与原因匹配的终态，receipt原因匹配且exit非0；timeout要求9–30秒。
- `:94–100` 在写入单项证据前无条件调用此校验，即使等待循环已到截止，也不能只因attempt结束而放过running/uncertain业务轮次。
- 新测试 `backend/tests/test_phase11a_checks.py:77–98` 覆盖三层状态逐一未终结、过短/过长超时、正常取消/超时。reviewer独立增加重复行、错误原因、exit0等内存输入，共8个负例被拒；9/30秒边界、10.189秒与早期取消正例通过。
- 取消仍是启动后早期取消（faults:79–87），不是图像工具长时间执行中取消；这一范围已在RESULTS明确。旧report没有job_status字段，不能声称旧记录完整重放通过新终态校验；新校验的正确性由代码与负例/回归证明。

### R4：首次捕获前退出的setsid孤儿——已解决

- `infra/phase11a_supervisor.py:19–32` 设置TERM/INT处理器和SIGCHLD默认处置，先成功设置subreaper再fork；prctl失败不会执行目标命令。孤儿由内核重新挂到最近仍存活的祖先subreaper，而非依赖PPID轮询及时捕获；已核对 [Linux PR_SET_CHILD_SUBREAPER文档](https://man7.org/linux/man-pages/man2/PR_SET_CHILD_SUBREAPER.2const.html)。
- `:43–74` 单线程waitpid回收、检测根退出后清理，只对自身直接子进程发信号；TERM后继续处理新收养后代，8秒后KILL顽固子进程。重复TERM只设置停止标记，不会终止监督循环。
- `:48–54` 仅在ECHILD时写D；SIGCHLD未忽略，也未设置NOCLDWAIT。该前提下ECHILD与WNOHANG返回0含义不同，代码正确区分，见 [Linux waitpid文档](https://man7.org/linux/man-pages/man2/waitpid.2.html)。`infra/phase11a_processes.py:123–139` 等监督进程退出并要求D，未收到D就拒绝_cleaned；`:184–218` 留下错误并阻止删除执行根、拒绝cleanupComplete。
- 清理所用信号不基于进程名或原session扫描。`infra/phase11a_processes.py:26–40` 用pidfd并核对出生时间/uid；supervisor:66–73还核对直接父进程。`capture_descendants`现仅作诊断，不能控制清理通过条件。
- 新测试 `backend/tests/test_phase11a_supervisor.py:26–39` **完全关闭capture**；`:51–74` 构造父进程立即退出和TERM时再fork，孩子真实setsid并忽略TERM；`:92–104` 确认父进程已回收、孤儿PPID等于supervisor且controller尚未发现孩子，随后cleanup回收孩子。`:87–89` 不接受僵尸代替回收。
- 八个收集用例（含app参数两种）覆盖无capture孤儿、两类command超时、TERM后新生后代、重复TERM、缺失D、错误birth不误杀、stdout/退出码保留：`:92–168`。外部进程fixture与托管树独立，并在关键清理后断言存活（`:43–48,104,117,127,140,159`）。缺失D测试在**断言cleanup失败且目录保留后**才手工设置_cleaned作fixture收尾（`:143–153`），不是用该赋值伪造被测通过。
- 最终Linux全量回归无skip及新环境smoke证据已读取。supervisor本身崩溃/强杀导致证明丢失时，控制器拒绝清理通过；不将此机制描述成监督进程死亡后仍保证自动回收所有后代。

## 其它质量、安全与测试真实性

- 结构/体积：11文件全部小于300行，具体见快照表；职责分为素材、环境、进程控制、内核监督、证据、故障、回归、入口与测试。`infra/phase11a_supervisor.py:12–74` 与 `infra/phase11a_processes.py:70–139` 分离监督端和控制端，未发现新增阻塞性结构问题。
- 错误路径：命令成功也必须在finally通过_stop，`infra/phase11a_processes.py:98–112`；缺失完成标记、清理超时均抛错，`:123–139`；最终真实入口以cleanupComplete决定最终failed，`infra/verify_phase11a_live.py:207–212`，未发现清理失败仍宣告总通过的路径。
- **安全扫描：未发现范围内真实硬编码密钥、shell=True、eval执行、不受控SQL或前端密钥暴露。** 已扫描全部11文件。命中项逐一核实：environment:98是ast.literal_eval常量读取；faults:18与supervisor测试:64,74是明确的专用故障注入；supervisor:41是exec失败的受控退出；processes:36,213分别受pidfd/birth/uid及临时目录身份检查保护。
- 命令argv执行、不导出错误参数/stderr：processes:73–78,103–106，supervisor:38–41,77–82；测试 `backend/tests/test_phase11a_environment.py:204–216` 验证凭据fixture不出现在异常文本。随机凭据及单独环境：environment:102–116；只读源素材SQL：inputs:47–49；回归临时DB/标签/端口/密码脱敏：regressions:19–42。
- 资源拒删测试保持有效：environment测试:77–105核对外来标签/名称拒绝及私有端口；:181–201核对目录替换和失败创建不误删；并发切换停服务前后均检查idle，environment:176–190与测试:28–63对应。
- 原R1（LOW）不扩成新阻塞：`infra/phase11a_checks.py:135–154` 仍是辅助自制ZIP；实际产品下载证据另见RESULTS浏览器章节。Python参数/返回类型未全面标注（例如supervisor:12、processes:70）仍只是非阻塞维护建议，本轮不要求扩范围重构。

## 验证记录与原始输出

reviewer独立读取候选并对11文件进行内存语法编译，无业务导入、无pyc、无服务操作。原始输出：

```text
COMPILE PASS: 11/11 files (in-memory; no imports; no pyc)
```

使用AST抽取当前require/Evidence/validate_stop运行纯内存输入；没有修改源码。原始输出：

```text
R2 NEGATIVE CASES REJECTED: 7
R3 NEGATIVE CASES REJECTED: 8
POSITIVE CASES PASS: timeout boundaries 9/30, 10.189s, early cancellation, historical serial three unique attempts
LIMIT: historical report has no job_status; not replayed as new strict stop validation
```

主 Agent 最终全量日志只读路径：`\\wsl.localhost\Ubuntu-24.04\home\hengxin\runtime\phase11a-closeout-results\regression-final.txt`；仓库忽略输出副本为 `output/playwright/phase11a-closeout/regression-final.txt`。不是reviewer重跑。末段原始输出：

```text
  /mnt/d/solveproblems/SOP/hengxin-smart-image/hengxin-smart-image/backend/app/modules/auth/dependencies.py:20: SAWarning: fully NULL primary key identity cannot load any object.  This condition may raise an error in a future release.
    user = session.get(UserRecord, identity_id)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
656 passed, 10 warnings in 91.21s (0:01:31)
```

日志656个测试全通过，0 skipped；10个warning为既有依赖弃用及SQLAlchemy提示。主 Agent 的针对性结果为41 passed/49.09秒；该数量由三份测试中的参数化用例构成，独立阅读了测试前提/断言，最终全量日志提供其纳入后的通过证据。前端不在11文件范围，本轮未新跑前端构建，沿用既有基线而不伪造输出。

修复后无模型环境报告 `output/playwright/phase11a-closeout/supervisor-smoke.json:1–15` 已直接读取：

```json
{
  "run": "hx-p11a-f27a57f15ed37d44",
  "status": "ready",
  "concurrency": 1,
  "modelCallsSubmittedByHelper": 0,
  "defaultConcurrencyRestored": true,
  "baseUrl": "http://127.0.0.1:46293",
  "docker": "docker.exe",
  "fullRegression": "passed",
  "restarts": 1,
  "smoke": "passed",
  "cleanupErrors": [],
  "cleanupComplete": true
}
```

其ready是环境生命周期字段，成功依据smoke/fullRegression及cleanup字段联合判断。Docker标签查询无容器残留为主 Agent 补充结果，本轮未操作Docker，不声称reviewer独立查询。上述helper计数0只指无模型环境辅助流程，不用于否认旧完整真实运行已发生模型调用。

## 旧真实证据与新机制证据的边界

原 `output/playwright/phase11a-closeout/report.json` 保持原字节，SHA256：`43f66dc9e560ab11d51be773f988887d58f1a12ce9e44438603e3bce2441a0d3`。已直接读取status=passed、296个资源采样与以下阶段：

- `:473` 串行三轮session `01a09042-04cb-7272-bb39-a0d6522855bb`，各一attempt，PID12624/14372/15834、birth及CLI0.153.4非空，execution_count=1、exit0；记录单张隔离及归档字节保持。
- `:336` Worker出版前中断、uncertain门禁、返工拒绝、3次重投count1；`:885` 两任务独立session/PID，各一attempt，simultaneousCliObserved与实际沙箱读写隔离为true。
- `:951,979` 早期cancelled 0.235秒及timeout 10.189秒，attempt finished、对应round cancelled/failed、exit -15。
- `:12657–12658` cleanupErrors=[]、cleanupComplete=true，默认并发恢复1。

这些证明此前真实业务运行，不回填原report缺少的新字段、不虚报新supervisor再次跑过收费图片。新supervisor由真实Linux孤儿故障测试、最终656项无模型回归及新隔离环境smoke补足；本次仅在此组合证据和指定修复范围内给出两阶段PASS。

审查期间11个源码文件未变化。最终报告交主 Agent；如后续改源码须重新固定快照并复核，只有主 Agent 可按协议登记同一candidate的两阶段PASS，本报告未执行该登记。
