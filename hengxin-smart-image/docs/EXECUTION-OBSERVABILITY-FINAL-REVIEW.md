# 生图过程可观测增量最终复审

日期：2026-09-11。执行者：fresh code-reviewer。

**candidateId：`cf684d12aba467de7ab6d2569ecce26f53f48cc443ba2665e880fe5edbb6bb7c`。Stage 1：PASS。Stage 2：PASS。F-01、F-02均关闭；本增量无待修复的HIGH/MEDIUM问题。**

## 快照、范围与方法

已读取根AGENTS.md、`.agents/skills/code-review/SKILL.md`、Product-Spec.md:245–252、Design-Brief.md、docs/HARNESS-REVIEW.md、本文同目录EXECUTION-OBSERVABILITY.md与EXECUTION-OBSERVABILITY-REVIEW.md。按Stage 1、Stage 2顺序审查。路径除特别标注外相对于`hengxin-smart-image/`；根Spec和Brief相对于仓库根。

审查范围为以下文件的生图观测增量，不重新审查已批准的proxy/localcli行为：

| 范围 | 实际行数 |
| --- | --- |
| backend/app/execution/codex_runner.py、observation.py、diagnostics.py | 217、133、213 |
| backend/app/modules/tasks/attempts.py、observations.py、router.py | 55、39、42 |
| backend/app/contracts/execution.py；backend/migrations/versions/0008_execution_observation.py | 46、18 |
| backend/tests/test_observation.py、test_observed_runner.py、test_execution_diagnostics.py、test_contracts.py | 160、91、283、114 |
| frontend/src/api/hengxin/execution.ts、execution-data.ts | 9、59 |
| frontend/src/views/hengxin/components/ExecutionProgress.vue、TaskDetail.vue | 94、119 |
| 同目录execution-poller.ts、use-execution-progress.ts | 38、15 |
| frontend/tests/execution-progress.test.ts | 141 |
| frontend/src/types/import/components.d.ts（快照附带生成声明） | 151；与HEAD对比无差异 |

起始及收尾`review-status`均为上述candidate；审查期间未观察到代码变化。前审顶部关闭F-01的结论与当前实现相符；F-02以本次源码及独立回归重新判定，未用旧报告覆盖新版本。前次批准边界为`8ca7678d3a1ab9b4ce70eba69d5a7d7261e21d0ea2f3e81a3a98305430fb14e6`。

仅写本报告；未改实现、操作服务、spawn、commit、登记approval、写clean或额外调用真实模型。浏览器使用独立临时标签页，未操作主Agent标签页或写业务数据。

## Stage 1：Spec Compliance — PASS

以下覆盖本次Spec六条及实现文档五项任务，不把未开展的其它Phase11A验收纳入缺陷。

| Spec/验收项 | 结论与证据 |
| --- | --- |
| Spec:247，排队及实际执行阶段 | 完整实现本次阶段展示。backend/app/modules/tasks/observations.py:20–21返回排队/数据库终态；codex_runner.py:104–106、139–149、165–194在实际操作前后记录准备、启动、生成、校验、存储、发布、完成。独立浏览器展开成功任务时间线，七个执行阶段均有真实事件；排队使用数据库状态展示，不倒填不存在的历史排队事件。 |
| Spec:247，耗时、最后活动、图片数及真实性 | 完整实现。frontend/src/api/hengxin/execution-data.ts:47–59；ExecutionProgress.vue:22–26。真实成功详情2分9秒、1/1、最后活动16:44:12，当前v1；未新增推算百分比。检测计数明确“待校验”，与下面原结果进度分开。 |
| F-02，空目录/历史图/新增图/删除图 | 已关闭。backend/app/execution/observation.py:125–130始终更新变化后的计数，只有count大于previous_count才添加检测事件；初始None按0比较。test_observation.py:116–134使用真实临时目录、真实Observer和测试数据库，依次断言0/0/1/0及事件数量1/1/2/2。本次独立运行1 passed，见原始输出。 |
| Spec:248，无活动不直接失败 | 完整实现。execution-data.ts:53–55使用lastActivityAt优先及60秒阈值；ExecutionProgress.vue:27明确“不能据此判定失败”。tests/execution-progress.test.ts:78–87覆盖59999/60000毫秒边界和终态；无状态修改。 |
| Spec:248，持久化、重开、切任务/轮次 | 完整实现。attempts.py:26、41按轮次保存nullable JSON；observations.py:13–39仅数据库读取；ExecutionProgress.vue:69–75和execution-poller.ts:13–36使上下文变化失效旧响应；use-execution-progress.ts:9–13释放计时器。test_observation.py:60–71与前端测试:24–38、106–130验证真实接口重读及迟到响应隔离。服务重启由主侧执行，本reviewer在其后独立GET仍读取21事件。 |
| Spec:248，终态停轮询、未知恢复门禁 | 完整实现。execution-data.ts:39–45终态停止HTTP，uncertain为5秒；poller.ts:25–26调度，测试:89–104走生产controller。TaskDetail.vue:16–19、70–72未放开原taskActions资格。本地1秒计时器不是HTTP轮询。 |
| Spec:249，分类原因与失败阶段 | 完整实现本次诊断。diagnostics.py:13–59固定分类，104–118只在CLI失败后分类有限stderr；codex_runner.py:154–160、165–205把清单、图片/来源、存储、发布、未知错误接入实际分支；observations.py:23–30提供取消/待核实及安全后备。真实旧失败返回ALL_OUTPUTS_FAILED/validating及逐图尺寸分类。 |
| F-01，启动前无attempt失败 | 保持关闭。observations.py:26–30只精确接受平台固定安全摘要，返回STARTUP_FAILED/starting，不透传任意round.error。test_observed_runner.py:82–91真正令版本探测失败并从GET断言分类及敏感stdout不外泄。无attempt的diagnosticId=null符合contracts/execution.py:35与实现文档:13，不虚构attempt；legacy说明缺少详细事件。前审163 passed证据继续适用于此未变分支。 |
| Spec:249，逐图错误及建议不触发操作 | 完整实现。diagnostics.py:160–213仅返回固定摘要和有明确标签的受限尺寸，单图返工映射原slot；ExecutionProgress.vue:31–35展示原因/阶段/建议。:15–16的重试仅重读过程GET；已有业务重试仍经TaskDetail.vue:98–101。 |
| Spec:250，结构化公开摘要与关联编号 | 完整实现。observation.py:45–59只按事件类型生成固定消息；diagnostics.py:54–59、160–180不返回原文；observations.py:33–39按task/round/attempt关联；ExecutionProgress.vue:49–50、81–84显示并复制编号，复制失败有手动选择提示。正常真实attempt诊断编号与GET一致；无attempt依nullable契约显示未提供。 |
| Spec:251，历史缺失与尺寸豁免 | 完整实现。observations.py:25–39保留原状态、legacy与事件；test_observation.py:105–113验证历史回填不造事件。独立GET与页面均确认633a…仍failed、legacy=true、events=[]，两个slot均显示Skill输出1254×1254、目标800×800，并明确非平台验证结论。单任务尺寸豁免未抹去旧失败。 |
| Spec:252，既有组件/轮询、无额外集群 | 完整实现。ExecutionProgress.vue:2–55复用ElCard/Select/Alert/Collapse/Tag，TaskDetail.vue:16嵌入既有抽屉；execution.ts:5–8复用鉴权请求客户端。无新增监控集群、业务写接口或页面。 |
| 实现文档:5，claim隔离/2秒节流/100事件/尽力观测 | 完整实现。observation.py:73–109检查当前round及双claim token、保留终态并吞掉观测异常；:111–114限频，阶段:80–85立即保存，:77–78最多100条。test_observation.py:60–81、96–102验证旧claim、数据库终态及读取异常。观测不发布结果、不自行重试。 |
| 实现文档:7，权限、删除及跨任务限制 | 完整实现。router.py:15、40–42沿用shared_resources并使用UUID参数；observations.py:14–17通过find_task和round.task_id检查，函数没有Worker文件读取。test_observation.py:84–93、137–142覆盖404及pending/disabled的403。 |
| 实现文档:5、9，迁移、契约、验证 | 完整实现当前增量。0008_execution_observation.py:11–18与attempts.py:41一致；test_observation.py:145–160实际运行升级两次、保留原记录及NULL；test_contracts.py:28–40核对OpenAPI。编译与测试来源见下文，未以全绿替代行为检查。 |
| UI规范与引导真实性 | 符合Design-Brief.md:13–15、51。新增加载重试有真实处理，复制失败有明确回退，历史/模拟/缺失数据分别提示（ExecutionProgress.vue:12–16、28–30、81–84）。实际邻居页面对比见Stage 2。 |

部分实现：无本次待修复项。未实现：无本次待修复项。Spec漂移：未发现；新增JSON、GET、轮次选择和展示组件均在EXECUTION-OBSERVABILITY.md:5–8授权范围。

## Stage 2：Code Quality — PASS

| 维度 | 结论与证据 |
| --- | --- |
| 命名、类型、规模、职责 | 全部20文件小于300行，最大test_execution_diagnostics.py为283行。contracts/execution.py:5–46提供公开结构，execution-data.ts:12–37使用unknown及运行时校验，前端扫描无any。Observer、诊断解析、查询及轮询控制器职责分离（observation.py:23、65；diagnostics.py:54、183；observations.py:13；execution-poller.ts:8）。Python内部动态dict沿用项目方式，公开边界有Pydantic契约。 |
| 安全扫描 | 未发现本增量硬编码密钥、eval、危险HTML、暴露前端密钥或新增shell字符串执行。扫描唯一password命中为test_observed_runner.py:67的故障哨兵。observations.py:18、31为SQLAlchemy参数表达式；diagnostics.py:71–101使用逐级no-follow目录描述符、普通文件/单链接/长度与读取前后元数据检查，拒绝不支持安全打开的平台；:129–152拒绝非法slot、重复文件及歧义清单。Vue采用文本插值，公开错误不返回原始日志。 |
| 故障测试真实性 | F-02新增测试:116–134没有mock计数函数，真实文件增删和baseline可达；b'old'/b'new'只用于“发现文件”而非图片校验，契合待校验语义。test_observed_runner.py:32–41实际调用run_generation并GET，只替换外部CLI；:45–79实际进入Skill全失败、清单失败、存储抛异常分支；:82–91覆盖启动前分支。diagnostics测试:191–206创建真实symlink/hardlink/FIFO，:268–283在open前换链，POSIX执行证据来自前审与主侧。 |
| 前端交互与故障 | tests/execution-progress.test.ts:16–22注入时钟与受控Promise，但被测为生产poller；:106–141实际resolve/reject迟到响应、切身份、关闭、重试和错轮次，不只测试字符串格式。与use-execution-progress.ts:7、ExecutionProgress.vue:74一致。已有用例不等于挂载整个Vue组件后的所有DOM交互，浏览器核心显示另行实测。 |
| 邻居实际视觉对比 | 独立CUA临时标签页实际打开`http://localhost:3008/#/templates/index`、`#/tasks/index`，再打开成功及失败详情，观察1280×720截图。模板库/任务中心为浅灰底、白色卡片、蓝色主操作、细边框；过程卡片使用现有ElCard/ElSelect/ElCollapse，无新视觉体系。成功详情显示已完成、2分9秒、1/1、诊断编号及v1；展开时间线显示七阶段。失败详情用原ElAlert展示阶段、建议和两条尺寸原因，文本在内容区内完整换行。实现定位ExecutionProgress.vue:2–55、88–94，TaskDetail.vue:2、16；基准为Design-Brief.md:13–15、51。 |
| 尺寸及布局 | 新卡片flex-wrap、gap12px、选择器280px且max-width100%、长编号overflow-wrap:anywhere、折叠头min-height48px（ExecutionProgress.vue:88–94），符合现有组件使用方式；本reviewer桌面实渲染无溢出。390×844与约967px结果采用主侧EXECUTION-OBSERVABILITY.md:30证据；本次未更改共享viewport或冒充窄屏独立实测。 |

安全问题：未发现本次需修复项。代码质量问题：未发现本次需修复项。测试边界：没有把SQLite旧claim测试声称为真实PG并发压力测试；没有独立注入数据库长时间阻塞或证明全部Vue复制/网络错误DOM路径。对应代码为observation.py:87–109、test_observation.py:60–102、ExecutionProgress.vue:81–84。这些是覆盖边界，不是已经复现的产品缺陷，也不扩大本次增量验收范围。

## 原始输出及证据来源

本reviewer仅重跑发生变化的F-02测试，Ubuntu-24.04 / hengxin、backend目录；不重复未变全量套件。命令：

```text
/home/hengxin/runtime/venv/bin/python -B -m pytest tests/test_observation.py::test_zero_or_historical_images_do_not_claim_new_generation -q -p no:cacheprovider
```

退出码0，原始输出：

```text
.                                                                        [100%]
=============================== warnings summary ===============================
../../../../../../../home/hengxin/runtime/venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  /home/hengxin/runtime/venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

../../../../../../../home/hengxin/runtime/venv/lib/python3.12/site-packages/starlette/testclient.py:53
  /home/hengxin/runtime/venv/lib/python3.12/site-packages/starlette/testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1 passed, 2 warnings in 1.69s
```

本reviewer对候选12个Python文件执行内存compile，不生成pyc；退出码0，原始输出：

```text
Python syntax compile: 12 files PASS (memory only)
currentId: cf684d12aba467de7ab6d2569ecce26f53f48cc443ba2665e880fe5edbb6bb7c
all files under 300 lines: True
```

前端扫描原始输出：

```text
Frontend any / unsafe-render scan: no matches
```

主侧证据（不是本reviewer重新执行或原始stdout）：EXECUTION-OBSERVABILITY.md:23–32记录固定Node24.18.1/pnpm10.33.4，typecheck退出0、69测试通过、build退出0（3311模块、Vite32.05秒），既有登录组件静态/动态导入提示；四文件专项164通过；最终后端548 passed、39 skipped、无失败、19.51秒。主Agent补充镜像tag phase8、id2bcb29dcf7b3构建与controller start成功。未提供完整构建stdout，故不拼造原始构建日志。前审EXECUTION-OBSERVABILITY-REVIEW.md:7、140–180保留独立163项及原始编译/测试证据；本次未重跑无变化检查。

本reviewer部署后真实只读GET关键字段（非fixture）：

```json
{"task":"95216b25-fd45-4b5c-a5d8-f248e2378b1b","status":"succeeded","stage":"completed","legacy":false,"events":21,"detected":1,"total":1,"failure":null,"diagnostic":"a16cdd8a-3d90-43a1-a7ad-e84f668dc1c1"}
{"task":"633a1c0b-b480-497b-b4fe-7939511e15e4","status":"failed","stage":"failed","legacy":true,"events":0,"detected":null,"total":2,"failure":{"code":"ALL_OUTPUTS_FAILED","message":"Skill 报告本轮所有图片处理失败（非平台验证结论）","action":"请核对输入与要求后重试","stage":"validating","slotErrors":[{"slot":0,"code":"SKILL_DIMENSION_MISMATCH","message":"Skill 报告该图尺寸或分辨率不符合要求（输出 1254×1254，目标 800×800）；非平台验证结论"},{"slot":1,"code":"SKILL_DIMENSION_MISMATCH","message":"Skill 报告该图尺寸或分辨率不符合要求（输出 1254×1254，目标 800×800）；非平台验证结论"}]},"diagnostic":"5a5ec375-156f-41f2-b98e-64e4cfcf0f25"}
```

## 交接

主Agent可依据本报告对**同一candidateId**执行review-approve，登记stage1=PASS、stage2=PASS及本报告路径；登记前再次核对当前快照。批准权由主Agent执行，本reviewer未登记。此次通过仅代表生图过程观测增量，真实单图与用户授权的单任务尺寸豁免不代表整个Phase11A已完成。
