# 生图过程可观测增量独立审查

## 当前候选最终结论

candidateId：`fba259bafd46616e416918c795c81624115eb0262dd21f11e8da903253fa8db2`（主侧已正式交接）。**Stage 1：FAIL，仅余F-02 MEDIUM；Stage 2：未执行。不得登记两阶段PASS。**

窄差异复核（2026-09-11）：主侧修改 observations.py 与 test_observed_runner.py 后，reviewer已读取当前内容并独立测试。observations.py:25–30仅精确匹配平台固定启动错误摘要，返回STARTUP_FAILED/starting；test_observed_runner.py:82–91实际走版本查询失败分支，并验证敏感stdout不进入API。独立重跑同一四文件命令，退出0，原始结果行 `163 passed, 2 warnings in 3.50s`，警告内容与下文一致。**F-01核心原因/阶段丢失已修复并关闭；F-02仍未关闭。** 无attempt时diagnosticId=null符合当前接口nullable约定，不要求为了本次修复虚构attempt或历史事件；legacy在此仅说明缺少详细事件。F-02定位仍为observation.py:123–128，空目录产生0张和“检测到生成图片”的实现未改变。

剩余审查范围：F-02补丁及回归验证，Stage1通过后再执行本次观测增量Stage2（代码质量、全面安全与测试真实性、邻居页面实际视觉对比）。不扩展此前已批准proxy/localcli范围。以下首轮报告保留原始证据；其中F-01的历史FAIL以本节关闭结论为准。

## 首轮审查记录（历史候选）

日期：2026-09-11。角色：fresh reviewer，仅审查与报告。

首轮结论：**Stage 1：FAIL（当时1 HIGH、1 MEDIUM）。Stage 2：未执行。当前结论见顶部。**

首轮审查 candidateId：`ba7f5f2a5e910e3b1c1ccbe0a79e3f35a4dc127e755500f36f6a2445b842f6e8`。

原派发 candidateId：`833699d9aa75a2396aedb123c490ca376c5b979fe97ba8ef54313f657334cc42`。初次执行 review-status 时实际内容已经是 ba7f5f2a…；主侧随后确认生产构建重生成 components.d.ts，并重新 prepare。reviewer 核对该声明文件全文及 `git diff --exit-code HEAD -- hengxin-smart-image/frontend/src/types/import/components.d.ts`，退出码0、输出为空，确实恢复 HEAD 内容。旧 candidate 内容没有留存在本次独立审查起点，不能独立声称已逐字比较 8336… 的全部旧内容；本报告直接针对 ba7f5f2a… 当前文件审查。

此前 proxy/localcli 候选 `8ca7678d3a1ab9b4ce70eba69d5a7d7261e21d0ea2f3e81a3a98305430fb14e6` 及 `docs/PHASE11A-PROXY-FINAL-REVIEW.md` 仅作为已批准边界，不重审、不开新 Phase11A 验收条件。

## 方法与范围

已读取根 AGENTS.md、code-review/SKILL.md、Product-Spec.md:245–252、本文相邻 EXECUTION-OBSERVABILITY.md、Design-Brief.md:11–15,51,55、根 docs/HARNESS-REVIEW.md，以及前轮报告。顺序：核对快照与范围；逐项对照需求、代码和测试；无真实生成的故障复现；只读真实 API；复核快照并写报告。每个结论以代码位置或实际输出为依据。

下列路径除特别说明外，相对于 `hengxin-smart-image/`。本轮全部20项范围均已读取；没有修改实现、操作服务、生成真实图、commit、spawn、登记 approval 或写 clean。

| 文件与定位 | 本轮覆盖 |
| --- | --- |
| backend/app/execution/observation.py:12–131 | 阶段、事件增量、心跳节流、claim 校验、计数、容错；发现 F-02 |
| backend/app/execution/diagnostics.py:9–213 | 固定诊断、限长安全读取、Skill 错误摘要、槽位映射 |
| backend/app/execution/codex_runner.py:74–217 | 本次观测接入和错误映射；发现 F-01；未扩大旧代理实现 |
| backend/app/contracts/execution.py:5–46 | 阶段及公开 DTO |
| backend/app/modules/tasks/attempts.py:19–41 | 每轮唯一 attempt 和 nullable observation |
| backend/app/modules/tasks/observations.py:13–35 | 当前/历史轮次、终态覆盖、legacy、诊断返回；发现 F-01 |
| backend/app/modules/tasks/router.py:15,40–42 | shared_resources 权限依赖及新增 GET |
| backend/migrations/versions/0008_execution_observation.py:5–18 | nullable JSON 列、升级和降级 |
| backend/tests/test_observation.py:20–139 | 增量日志、旧claim、终态、权限、旧数据、迁移用例 |
| backend/tests/test_observed_runner.py:15–79 | 真实 runner 编排配模拟CLI的三条失败路径；未覆盖 F-01 |
| backend/tests/test_execution_diagnostics.py:23–283 | 固定映射、非法输入、尺寸摘要、文件边界、stderr 分类 |
| backend/tests/test_contracts.py:35–43 | 新增 API 的 OpenAPI 响应契约 |
| frontend/src/api/hengxin/execution.ts:5–8 | 现有鉴权 HTTP 客户端、参数编码、DTO 验证 |
| frontend/src/api/hengxin/execution-data.ts:1–59 | 契约、当前轮次哨兵、状态标签、耗时、无进展提示、轮询间隔 |
| frontend/src/views/hengxin/components/TaskDetail.vue:16–20,47–48 | 嵌入过程卡片；详细失败存在时隐藏旧 generic 错误；原操作门禁保留 |
| frontend/src/views/hengxin/components/ExecutionProgress.vue:1–94 | 当前/历史选择、计数、失败建议、时间线、诊断复制、样式 |
| frontend/src/views/hengxin/components/use-execution-progress.ts:5–14 | reactive 上下文、计时和作用域释放 |
| frontend/src/views/hengxin/components/execution-poller.ts:8–37 | generation 隔离、终态停HTTP、错误重试、dispose |
| frontend/tests/execution-progress.test.ts:1–141 | 已全文核对当前轮次、历史、身份切换、晚到响应和关闭用例；未独立执行前端套件 |
| frontend/src/types/import/components.d.ts:1–151 | 生成声明全文核对、与 HEAD 无差异；无业务功能增量 |

## Stage 1 缺陷

### F-01 · HIGH：本轮新发生的启动前失败被误报为历史缺失诊断

需求：Product-Spec.md:249 要求区分启动失败、展示原因与失败阶段；:250 要求诊断编号；:251 的历史标识应对应真实缺失的历史记录。EXECUTION-OBSERVABILITY.md:6 要求失败诊断分类。

定位：`backend/app/execution/codex_runner.py:78–104,195–205`；`backend/app/modules/tasks/observations.py:18–26,30–35`。

CLI 版本查询、版本一致性检查、prepare_workspace（包括认证材料准备）、部分会话恢复检查均发生在 attempt 持久化及 Observer 创建之前。这里失败后，异常处理虽然构造 STARTUP_FAILED，却因 observer 仍为 None 而没有持久化 failure；详情 API 只看 attempt.observation，最终回退 LEGACY_FAILURE，diagnosticId 为 null。TaskDetail 又会因收到这个 failure 隐藏已有 task.error（TaskDetail.vue:17；ExecutionProgress.vue:79–80），用户看不到新发生的启动原因。

这是本轮新增诊断能力缺口，不要求改变旧任务状态机、重试资格或 uncertain 恢复门禁。最小修复验收：启动前检查失败也能保留安全的原因、真实失败阶段及可关联诊断，不把刚执行失败的新任务当历史；对应失败不触发额外 CLI。

建议在版本/工作区检查之前建立受claim保护的诊断记录，或为启动前失败提供明确的结构化持久化后备记录；execution_view优先返回已知安全诊断，只有确实没有可用证据的旧记录才退回LEGACY_FAILURE。不要直接透传任意round.error，也不要依赖中文错误文本猜分类。可以保留当前failed/uncertain和恢复门禁，修复仅涉及本轮观测层。

独立复现使用现有 SQLite/MemoryStore fixture 和真实 run_generation，不连接真实业务数据库、不调用CLI。在已送审 test_observed_runner.observed_run 基础上分别使版本查询、prepare_workspace 抛 FileNotFoundError。原始输出：

```json
{"scenario": "version_missing", "status": "failed", "stage": "failed", "legacy": true, "diagnosticId": null, "failure": {"code": "LEGACY_FAILURE", "message": "本轮处理失败，历史记录未保留详细诊断", "action": "请核对输入与要求后重试", "stage": "failed", "slotErrors": []}}
{"scenario": "workspace_auth_missing", "status": "failed", "stage": "failed", "legacy": true, "diagnosticId": null, "failure": {"code": "LEGACY_FAILURE", "message": "本轮处理失败，历史记录未保留详细诊断", "action": "请核对输入与要求后重试", "stage": "failed", "slotErrors": []}}
```

从 backend 目录，将以下脚本通过 stdin 交给测试环境 Python 可复现；不必写进实现或测试目录：

```python
import sys, tempfile, json
from pathlib import Path
sys.path.insert(0, 'tests')
import conftest
from pytest import MonkeyPatch
from files_helpers import files_env
from test_tasks import task_env
from test_observed_runner import observed_run, runner
for scenario in ('version_missing', 'workspace_auth_missing'):
    with MonkeyPatch.context() as mp, tempfile.TemporaryDirectory() as root:
        fg = files_env.__wrapped__(); env = next(fg)
        tg = task_env.__wrapped__(env, mp); next(tg)
        try:
            invoke, _, _, _ = observed_run.__wrapped__(env, Path(root), mp)
            def broken(*args, **kwargs):
                raise FileNotFoundError('private startup path')
            mp.setattr(runner.subprocess if scenario == 'version_missing' else runner,
                       'run' if scenario == 'version_missing' else 'prepare_workspace', broken)
            data = invoke()
            print(json.dumps(dict(scenario=scenario, **{k: data[k] for k in
                ('status', 'stage', 'legacy', 'diagnosticId', 'failure')}), ensure_ascii=False))
        finally:
            tg.close(); fg.close()
```

现有用例为何未阻断：`test_observed_runner.py:18–19,30–31` 始终准备有效认证文件、强制版本查询成功；三条故障分别位于 Skill 清单、结果收集和存储阶段（:45,63,73），均晚于 Observer 创建。固定码单测（test_execution_diagnostics.py:23–43）证明有 STARTUP_FAILED 映射，不能证明上述实际分支将其送入 API。

### F-02 · MEDIUM：零新增图片也记录“检测到生成图片”

需求：Product-Spec.md:247 的真实过程与检测数量；过程提示应对应实际发生的行为。

定位：`backend/app/execution/observation.py:70–71,123–128`；续接基线入口 `backend/app/execution/codex_runner.py:116–117`。

初始 detectedImages 为 None。只要 generated_images/session 目录存在，即使为空，或全部图片均在上轮 baseline 中，count=0 与 None 不等，便更新 lastActivityAt 并追加“检测到生成图片，尚待结果校验”。此时没有新图，时间线陈述不真实。删除新增文件导致计数降低也会使用相同措辞。

最小复现：构造 Workspace，创建空的 `home/.codex/generated_images/session`，构造 Observer(total=1)，仅将 save 替换为无操作以隔离数据库，调用 `tick('session', force=True)`。实际输出：

```json
{"detectedImages": 0, "messages": ["检测到生成图片，尚待结果校验"]}
```

修复验收：初次确认0、基线内旧图、计数降低不能声称发现新图片；新增图时仍正确更新计数与事件，不把发现当校验成功。现有 test_observation.py:20–139 没有生成目录计数场景用例。

## Stage 1 逐项需求对照

| 需求及验收点 | 结论、定位与证据 |
| --- | --- |
| 真实阶段、耗时、最后活动、图片数量；不估计百分比，不把发现当成功（Spec:247） | **部分实现**。runner:104–194 将准备/启动/执行/校验/存储/发布/完成接入实际调用；真实成功API验证七阶段。observations:20 提供当前排队状态，但 events 从 preparing 开始，未独立验证历史排队时间线。ExecutionProgress:22–27 明示待校验、不新增百分比；elapsedSeconds 位于 execution-data:47–51。计数事件真实性因 F-02 不通过。 |
| 无新事件只提示，不能认定失败（Spec:248） | **实现**。execution-data:53–55 以最后活动判断60秒；ExecutionProgress:27 明示不能判失败，无状态写操作。前端用例覆盖59999/60000ms边界；未将读取心跳 updatedAt 当作有新活动覆盖 lastActivityAt。 |
| 持久化、刷新/重开/切换任务与轮次读取（Spec:248；实现任务1、3、4） | **实现主要路径**。attempts:26,41 每轮独立JSON；observations:13–35按round读取；poller:13–26,34–36拒绝旧响应；组件:71–75在task/身份/active变化时重置选择，current哨兵在execution-data:7–10解析。测试观察值来自新API请求；服务重启持久性由主侧现场记录支持，reviewer未重启服务。 |
| 终态停止轮询，未知保留恢复门禁（Spec:248） | **实现**。execution-data:39–45 对完成/失败/取消/部分失败停止HTTP，uncertain每5秒继续读；poller:25–26按状态调度。TaskDetail只增加展示，不放开原taskActions资格。use-execution-progress:11的本地1秒时钟仍运行，不等同HTTP轮询。 |
| 启动/认证/网络/超时、Skill、清单/来源/图片校验、存储、执行权与未知错误（Spec:249；实现任务2） | **部分实现，F-01阻断**。diagnostics:13–59有固定分类，104–118只从失败CLI的stderr取分类，183–213区分Skill报告；runner:154–205接入处理。启动前无attempt路径缺诊断；不能以映射表有条目宣称全链路分类完整。 |
| 逐图原因、阶段、建议，不自动重试或改操作资格（Spec:249） | **实现已覆盖分支**。diagnostics:160–213固定摘要、单图target回映原槽；ExecutionProgress:31–35展示；“重试加载过程”仅poller重读GET(:15–16)，不生成。两个真实历史槽位均读到尺寸错误与建议。 |
| 公开结构化摘要，不泄露思维链/命令/提示词/凭据/stderr/路径（Spec:250） | **已核对本项实现**。observation:45–59只输出固定活动消息；diagnostics:54–59,160–180不透传异常或Skill原文；runner:195–199只允许指定内部异常码；poller:27–30固定网络错误。POSIX诊断用例及敏感文本测试实际通过。此为Stage1公开数据需求核查，不代表已完成Stage2全面安全扫描。 |
| 每轮诊断编号（Spec:250） | **部分实现**。正常attempt UUID在observations:30返回；F-01路径为null且无attempt，未满足启动失败可诊断要求。 |
| 历史缺失标注、真实证据补诊断、不编造历史进度或改状态（Spec:251） | **旧任务路径实现，新任务误标见F-01**。observations:35使用legacy和events；真实633a…响应failed、legacy=true、events=[]、逐图Skill尺寸诊断。补写动作不属于本增量API代码，reviewer只核对其结果，不声称执行过历史回填。 |
| 复用现有详情与组件，不增加监控集群（Spec:252；Design-Brief:13–15,51） | **代码符合**。TaskDetail:16与ExecutionProgress:2–55复用ElCard/Select/Alert/Tag/Collapse；:88–94使用换行及宽度限制，无新增集群配置。本轮为额外的详情GET轮询，沿用现有HTTP/权限。主侧提供967px与390×844视觉结论；reviewer未独立浏览，不冒充视觉实测。 |
| 当前claim保护、2秒节流、阶段立即保存、事件最多100、观测不重复执行（实现任务1） | **代码具备主要保护；故障覆盖有边界**。observation:77–78限100；:89–100锁定task/round/job，检查当前round及双token，非终态检查valid；:111–114心跳节流；:80–85阶段立即保存；:101–109容错。test_observation:60–81实际验证旧token拒绝与数据库取消态覆盖；:96–102测试读取异常不抛。没有独立验证PG锁竞争、数据库长时间阻塞或完整runner在观测落库失败后的发布行为，不能将其说成已实测。 |
| GET权限、删除检查、跨任务round拒绝；API不读Worker目录（实现任务3） | **实现**。router:15,40–42沿用shared_resources；observations:14–17调用find_task并核对round.task_id，函数仅数据库读取。test_observation:84–93,116–121实际验证跨任务/删除404、pending/disabled403；授权operator成功读到200。 |
| nullable迁移与旧数据（实现任务1、5） | **实现**。migration:11–13与attempts:41一致；test_observation:124–139实际运行升级两次且保留原行、observation=NULL。这是SQLite迁移用例，PG迁移成功来自主侧记录。 |
| 测试、契约、编译与浏览器证据（实现任务5） | **部分满足**。独立162项后端测试通过、12文件语法编译通过；前端typecheck/69测试/build及真实页面由主侧提供。F-01、F-02无既有故障用例，已补独立复现，不能因测试全绿判通过。 |

Spec 漂移：本增量API、JSON字段、组件和轮次选择均在实现任务1–4授权范围内；未发现新增无需求的业务页面或操作。未重新审查既有proxy/localcli功能，也未把尚未开展的其它Phase11A验收列为本轮缺陷。

## 验证原始输出与来源

reviewer执行的命令（Ubuntu-24.04 / hengxin，工作目录 backend；无真实生成）：

```text
/home/hengxin/runtime/venv/bin/python -B -m pytest tests/test_observation.py tests/test_observed_runner.py tests/test_execution_diagnostics.py tests/test_contracts.py -q -p no:cacheprovider
........................................................................ [ 44%]
........................................................................ [ 88%]
..................                                                       [100%]
=============================== warnings summary ===============================
../../../../../../../home/hengxin/runtime/venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  /home/hengxin/runtime/venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

../../../../../../../home/hengxin/runtime/venv/lib/python3.12/site-packages/starlette/testclient.py:53
  /home/hengxin/runtime/venv/lib/python3.12/site-packages/starlette/testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
162 passed, 2 warnings in 3.07s
```

退出码0。没有skip；这162项不是全后端套件。Python编译为内存compile，不生成pyc，覆盖本轮12个Python文件。原始输出：

```text
currentId: ba7f5f2a5e910e3b1c1ccbe0a79e3f35a4dc127e755500f36f6a2445b842f6e8
preparedId: ba7f5f2a5e910e3b1c1ccbe0a79e3f35a4dc127e755500f36f6a2445b842f6e8
deltaFromPrepared: []
Python syntax compile: 12 files PASS (memory only)
```

真实API由reviewer通过 `GET http://localhost:8008/api/v1/tasks/{id}/execution` 只读取得：

| 任务 | 实际响应关键字段 |
| --- | --- |
| 95216b25-fd45-4b5c-a5d8-f248e2378b1b | source=cli、status=succeeded、stage=completed、legacy=false、failure=null；diagnosticId=a16cdd8a-3d90-43a1-a7ad-e84f668dc1c1；detectedImages=1,totalImages=1；21事件；startedAt=2026-09-11T16:42:02.514186+08:00，finishedAt=2026-09-11T16:44:12.116132+08:00；七阶段preparing/starting/generating/validating/storing/publishing/completed均出现。 |
| 633a1c0b-b480-497b-b4fe-7939511e15e4 | status=failed、stage=failed、legacy=true、events=[]、detectedImages=null；failure.code=ALL_OUTPUTS_FAILED，failure.stage=validating；slot0和slot1均为SKILL_DIMENSION_MISMATCH，文字“输出1254×1254，目标800×800”，明确“非平台验证结论”。 |

上述是真实GET结果，不是fixture测试输出；自动页面更新、当前v1、窄屏正常为主侧观察，本reviewer没有争用浏览器或重做真实生成。尺寸豁免仅属于指定测试任务，未解释为Skill或系统验收规则豁免。

主侧 `EXECUTION-OBSERVABILITY.md:25–33` 记录后端全量546 passed/39 skipped、固定Node24.18.1/pnpm10.33.4前端typecheck退出0、69测试通过、pnpm build退出0（3311模块，Vite32.05秒），以及迁移/部署/页面验证。reviewer没有独立重跑这些全量步骤，也未收到其完整原始构建日志，故这些为主侧证据，不伪造构建stdout。当前审查缺陷不由构建通过抵消。

## Stage 2 与交接

Stage 1存在HIGH，依code-review/SKILL.md停止，**Stage 2未执行**：不声明代码质量、全面安全扫描或新旧邻居页面视觉对比PASS。用户要求的安全边界和测试内容中，与Stage1需求直接相关的核查已如实列在上表；不将这些检查改称完整Stage2。

主Agent按Stage1失败回开发修复F-01/F-02，补实际分支回归，然后重新review-prepare并从Stage1复审。新快照不得沿用本报告登记两阶段PASS。旧proxy/localcli批准范围不受本报告否定；本次观测增量未通过。
