# 成员隔离发布迁移前恢复：独立增量审查

- 日期：2026-10-13；reviewer：独立 code-reviewer。
- 最终 candidateId：`394aceeb74d90fa47fbbf98ca87a71d1a2f5821a633435cfdfb28ceacc4e3f3a`。
- 基线 HEAD：`da722adb6c2a6d141f783fff6450a903d709b74c`。
- **Stage 1：PASS；Stage 2：PASS。** 最终候选未发现未解决的 HIGH / MEDIUM 问题。
- 结论限恢复控制器及关闭入口检查增量，不表示生产恢复、两库迁移、公开验收或四人清理已经完成。

## 范围、合同与版本变化

已读取 `AGENTS.md`、`.agents/skills/code-review/SKILL.md` 和 `docs/HARNESS-REVIEW.md`。源合同为 `Product-Spec.md:1081`、`DEV-PLAN.md:1`、`docs/BUSINESS-MEMBER-ISOLATION-RELEASE-20261013.md:30`。本次逐项审查后者的迁移前恢复要求；原成员隔离业务、迁移与发布主体没有变化，继续由 `docs/reviews/BUSINESS-MEMBER-ISOLATION-RELEASE-REVIEW-20261013.md:1` 和 `docs/reviews/BUSINESS-MEMBER-ISOLATION-MOUNT-REVIEW-20261013.md:1` 覆盖，不重新声称其全部功能、浏览器及生产测试已执行。

受控增量仅以下三份文件：

- `scripts/release/member-release-resume.py`：独立恢复入口。
- `scripts/release/member-release-resume-tests.py`：恢复边界与代理关闭轮询测试。
- `scripts/release/member-release-verify.py`：关闭入口的有界轮询。

审查过程收到两次源码更新，旧结论没有覆盖新版本：

1. 初始 `3306606f4e14fa2a8e401c49efd70bca711af18c2b9c6180afe4d553c17e18ff` 的91项通过。主Agent实查 API 正常 SIGTERM 停止后退出码为143，将允许状态改为0/143且非OOM，增加137/OOM拒绝；产生 `a8227f5045bfff2d7dd8217f48622dcc8a7358ec8b2945b350f679972148ee07`，reviewer独立93项通过。
2. reviewer发现原生配置仅检查已保存路径的摘要，未重查当前路径集合：新增drop-in/env引用可以漏检。独立合成实验实际进入 `check_baseline()` 并得到接受，且确认未查询三项路径属性。该 Stage 1 恢复前置条件缺口由主Agent修正：最终 `member-release-resume.py:47` 重新查询 FragmentPath/DropInPaths/EnvironmentFiles，精确比较集合后再比摘要，测试 `member-release-resume-tests.py:105` 覆盖新增和移除路径拒绝。对最终候选重新从 Stage 1 审查，独立95项通过后才进入 Stage 2。

审查开始、最终验证结束和报告落盘后均核对代码快照；本报告为普通Markdown，不改变候选。reviewer未修改实现、未提交、未连接或修改生产、未写 `.needs-review`、未登记 approval。

## Stage 1：Spec Compliance — PASS

以下 `resume`、`verify`、`runtime`、`deploy`、`tests` 分别指 `scripts/release/member-release-resume.py`、`member-release-verify.py`、`member-release-runtime.py`、`member-release-deploy.py`、`member-release-resume-tests.py`。

| 合同条目 | 结论及证据 |
|---|---|
| reload存在生效延迟，关闭检查必须有时限 | ✅ `verify:99` 每轮重新读取三API及国内SSE共四入口，全部503才成功，否则至deadline抛出包含实际状态的错误；`tests:22` 真实运行两轮401→503路径，`:31` 验证超时拒绝。30秒为轮询预算，HTTP请求本身另有最长30秒限制（`verify:61`），不是严格总耗时30秒；仍为有界检查。 |
| 只恢复明确失败，拒绝已排空/已停executor/已迁移/已完成状态 | ✅ `resume:20` 拒绝两份drained记录、EXECUTORS_STOPPED、MIGRATION_STARTED和verification，`:23` 要求deploy.exit=1；`:74` 拒绝任何既有备份目标。五个进度标记分别由 `tests:77` 执行拒绝测试；原deploy/cutover未被绕过修改。 |
| 原包、已测镜像、PREPARED仍匹配 | ✅ `resume:11` 只从原release包导入已审控制器；`:63` 调用原 `runtime:90` 的manifest与逐文件摘要核验；`:64` 通过 `runtime:99` 比较实际image ID与INSTALL_TEST_IMAGE_ID；`:65` 再核PREPARED。不调用build，不改原包。 |
| 双库仍是迁移前版本 | ✅ `resume:66`、`:67` 在cutover前分别要求0027和overseas_0013，任一不符即失败；实际迁移继续调用 `deploy:23` 的原逻辑。版本检查位于所有恢复变更之前。 |
| 原入口文本可信，当前关闭配置完全一致，实际四入口503 | ✅ `resume:69` 核保存原文的SHA与topology.edgeHash；`:24` 要求当前EDGE全文等于原文生成的关闭配置；`:76` 调用原包closed核实际503。新恢复不reload关闭入口，所以原包的一次检查没有此次reload竞态。 |
| 三API仅处于预期停止状态，所有容器保持原ID与挂载 | ✅ `resume:30` 比较项目完整运行ID集合恰为原集合减API；`:35` 对每个原容器比ID、完整规范化Mounts、Running状态；`:39` 要求API exited、退出码0/143、非OOM，并检查旧image与项目/config/cwd/env标签。`tests:86` 覆盖替换、挂载权限、额外/缺失运行实例、异常退出及标签漂移。 |
| 原生服务active、工作目录/配置文件集合及内容保持 | ✅ `resume:48` 对每个unit核WorkingDirectory及active，`:50` 重取三种文件属性，`:54` 精确比路径集合，`:55` 比全部文件摘要；`tests:97`、`:105` 分别证明内容、新增/移除引用拒绝。集合提取沿用已审 `runtime:81` 的算法。 |
| 三套Compose配置与准备设置保持 | ✅ `resume:28` 比原Compose/env文件摘要；`:57` 使用原 `runtime:143` 重新渲染带overlay的配置并校验除已允许image/build之外的设置。当前93→95增量未改原包或prepared配置。 |
| 使用原包cutover继续排空、停已确认空闲执行者、备份、迁移及验收 | ✅ 唯一执行入口为 `resume:78` 的原 `deploy:18` cutover；后者按drain→backup COMPLETE→MIGRATION_STARTED→两库迁移→完整性验证→运行切换→源码/健康/挂载/Skill/前端验收顺序执行（`deploy:19`、`:21`、`:29`、`:37`、`:44`）。本次没有复制或改写这些业务步骤。既有故障/备份测试计入独立95项。 |
| 成功才恢复原入口并执行公开验证、写完成证据 | ✅ `resume:79` 恢复保存原文并reload，`:81` 执行原public健康及匿名鉴权验证，随后写三份发布记录和verification；独立编排实验验证cutover→reload→public→完成记录顺序，并核恢复commit、脚本SHA、historicalCleanup=False。 |
| 失败保持关闭，不回退数据库/旧业务代码，不强停未知执行者 | ✅ `resume:89` 捕获执行阶段异常，先close_edge，finally始终stop_apis；无downgrade、回旧源码、executor stop。独立故障实验覆盖cutover、reload、public、三份记录及verification失败；另注入close本身失败，仍尝试stop_apis。实际三API逐个停止及累计错误由原 `runtime:222` 实现。前置检查失败没有生产写操作。 |
| 恢复脚本单独固定Git与SHA，不重建已测产品包/镜像 | ✅ `resume:11` 的加载路径仍为原release src；`:87` 将recoveryCommit及实际__file__摘要写verification。附加调用器 `output/member-resume-control.py:8` 取已提交原字节，`:17`、`:20` 双次校验，固定原release执行，详见下节。 |
| 四条人员清理仍为后置授权范围 | ✅ `resume:86` 明确historicalCleanup=False，无成员DELETE或维护工具调用；合同 `docs/BUSINESS-MEMBER-ISOLATION-RELEASE-20261013.md:5` 的重新审核、模拟、恢复包和逐条清理仍须主Agent随后执行。 |
| UI一致性、引导真实性、Spec漂移 | ✅ 三个增量均为Python发布脚本；没有页面、文案、API或业务表新增，恢复控制器对应发布记录第30行。视觉及邻居页面对比不适用本增量；未声称本轮打开生产页面。 |

完整实现：本次源码范围上述条目均匹配。部分实现、未实现：无。原生路径集合缺口已修复并重新验证；无待解决Stage 1问题。

## Stage 2：Code Quality — PASS

| 维度 | 结论及证据 |
|---|---|
| 职责、规模、命名 | ✅ 恢复代码分为load/check_baseline/resume，分别16/57/95行结束；新增运行文件104行、测试113行、verify121行，均小于300行。发布主体继续复用旧控制器（`resume:78`），未复制drain/backup/migrate。 |
| 测试真实性 | ✅ 最终95项独立通过，包含23项新增关闭轮询及恢复边界用例。fixture通过deepcopy隔离原挂载和live挂载（`tests:47`），避免篡改对照本身导致假阳性；143成功与1/137/OOM失败分别可达。恢复编排本身不由这些新增单测覆盖，因此reviewer另调用真实resume/check_baseline、仅模拟外部IO，覆盖成功和11种失败；原始输出见下。 |
| 安全扫描 | ✅ 对三份增量扫描eval、innerHTML、危险前端secret变量、硬编码sk密钥、shell=True及可疑password赋值无命中。Docker/systemctl采用参数序列（`resume:30`、`:49`），版本SQL为固定查询（`:66`）；不读取用户生成命令，不导出环境或人员名单。 |
| 错误处理 | ✅ 所有生产写操作处于try内（`resume:77`）；finally停止三API，不把恢复失败吞成成功（`:89`）。不以resume测试成功代替真实Docker/systemd操作成功；真实上线效果尚待主Agent执行。 |
| 隐私与运行边界 | ✅ CLI使用umask077（`resume:99`），固定/opt发布路径和release/commit格式（`:102`）；一次性调用器独占创建脚本及日志，继承私有权限（`output/member-resume-control.py:13`、`:19`、`:23`）。未发现本增量引入的凭据或人员信息泄漏。 |
| 编译与UI | ✅ 三份增量及一次性控制器/渲染后的远端脚本均编译通过。此增量无前端代码及依赖变化，不重复执行前端build/视觉检查；原构建与视觉证据维持旧报告范围。 |

Docker退出处理与[官方docker stop说明](https://docs.docker.com/reference/cli/docker/container/stop/)核对：默认先发送SIGTERM，超时后才SIGKILL。0/143且非OOM的恢复限定，与本次实查停止证据和测试一致；137仍拒绝（`resume:40`、`tests:104`）。没有据此认定任意143退出均可恢复，其余快照/进度/版本门禁仍必须全部通过。

## 独立验证原始输出

使用项目虚拟环境，命令：

```text
hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/member-release-tests.py scripts/release/member-release-topology-tests.py scripts/release/member-release-resume-tests.py scripts/release/test_package_overseas.py -q --tb=short
........................................................................ [ 75%]
.......................                                                  [100%]
95 passed in 1.78s
```

exit 0。首次使用系统Python时提示 `No module named pytest`，已切换至项目虚拟环境复跑；不是产品测试失败，也未安装或修改依赖。

reviewer另外通过Python stdin、临时目录及内存外部IO替身调用真实resume/check_baseline；测试成功、validate/image/closed前置失败、cutover/reload/public失败、三份release记录及verification写失败、关闭入口自身失败。针对最终候选重跑，exit 0：

```text
RESUME_SUCCESS_AND_11_FAILURE_PATHS_PASS
PREFLIGHT_FAILURES_NO_MUTATION; POST_CUTOVER_FAILURES_CLOSE_THEN_STOP_APIS; CLOSE_FAILURE_STILL_STOPS_APIS
RECOVERY_COMMIT_SHA_AND_NO_HISTORICAL_CLEANUP_RECORD_PASS
EXTERNAL_IO_MOCKED_NO_PRODUCTION_CONNECTION_OR_MUTATION
LIVE_READONLY_PROBE_EMBEDDED_SOURCE_MATCHES_FINAL_CANDIDATE
```

编译使用Python `compile()`，额外提取调用器生成表达式、编译最终远端脚本，并确认其base64解码字节等于当前恢复脚本；没有执行dispatcher或SSH。exit 0：

```text
COMPILE_PASS scripts/release/member-release-resume.py (104 lines)
COMPILE_PASS scripts/release/member-release-resume-tests.py (113 lines)
COMPILE_PASS scripts/release/member-release-verify.py (121 lines)
CONTROL_AND_RENDERED_DISPATCH_COMPILE_PAYLOAD_PASS
SHA256 output/member-resume-control.py 8bea79e24520a674e83fcef558735e97dd863945fb227890be5ae270a29ff2af
SHA256 output/member-release-remote.py 98b3358341b9c6ac46b64b89aea27ed0605869d6ea29e4047a22507b1c33a590
```

`git diff --check` 无输出，exit 0；上述安全模式扫描无匹配。

## 主Agent真实只读证据与附加调用器

读取 `output/member-edge-diagnose.log:1`：原失败栈位于关闭入口即时检查，保护路径已停三API，随后三API入口503。读取 `output/member-resume-readonly-driver.py:5` 和生成的server脚本：只加载新模块定义、原包validate/image_id/check_baseline/closed，不调用resume/cutover。reviewer独立解码嵌入脚本，确认字节与最终候选一致。对应日志 `output/member-resume-readonly.log:1`：

```text
active
active
active
LIVE_RECOVERY_BASELINE_AND_FOUR_CLOSED_ENDPOINTS_PASS
```

这是主Agent真实只读检查输出，不是reviewer自行连接生产的结果。该探针没有执行两库迁移、完整resume或清理；实际恢复仍会重新检查双库旧版本、edge原文摘要、备份目录及所有前置条件（`resume:63`至`:76`）。本报告不把该日志误写为恢复完成。

额外只读审阅忽略目录调用器，固定字节如下，不由candidate快照授权其以后改动：

| 文件 | SHA256 |
|---|---|
| `output/member-resume-control.py` | `8bea79e24520a674e83fcef558735e97dd863945fb227890be5ae270a29ff2af` |
| `output/member-release-remote.py` | `98b3358341b9c6ac46b64b89aea27ed0605869d6ea29e4047a22507b1c33a590` |

- ✅ `member-resume-control.py:4` 取完整HEAD，`:8` 从该提交读取脚本，要求工作区换行归一字节相同后使用提交原字节；独占创建远端脚本与日志（`:19`、`:23`）且双次核SHA；固定原release，参数序列调用python3并记录exit（`:21`、`:22`）。没有额外业务动作或镜像重建。
- ✅ `member-release-remote.py` 与先前完整发布审查已固定摘要相同；其SSH/host key行为沿用原报告附加调用器审阅，不重新执行网络访问。
- ✅ 主Agent须先登记最终候选、提交恢复脚本，再调用该传输器，最终verification记录独立恢复commit和脚本SHA；不得修改已测da722ad产品包来“应用”本地verify改动。

## 快照交接

最终验证结束的原始状态：

```json
{"currentId": "394aceeb74d90fa47fbbf98ca87a71d1a2f5821a633435cfdfb28ceacc4e3f3a", "reviewedId": "46c769d9e1b1c8f340a8d713c0406a2526334201306e3991751d8d325035f044", "changedFiles": ["scripts/release/member-release-resume-tests.py", "scripts/release/member-release-resume.py", "scripts/release/member-release-verify.py"], "approved": false}
```

主Agent可登记本最终candidate、本报告和两阶段PASS；初始3306606f及中间a8227候选不予批准。实际恢复、备份/迁移/安装/公开验收及四条逐人处理结果须由后续真实执行补入发布记录。
