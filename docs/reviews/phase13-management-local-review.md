# Phase 13.2 / 13.3 本机独立审查

## 当前最终复审：2026-09-16 · e5883dd7

- candidateId：`e5883dd7abd2cc03aaceab28b685fba32d1edb26edb3fedfc9328ad03bd8d74b`；开始时review-status完全匹配。
- 审查范围仍为本轮相对3baa541的业务差异及新增测试。相对此前cd19e114，派发说明仅health.py与monitor测试变化；已重新读取这两个文件，并继续完成其余Stage2源码检查。
- **Stage 1：PASS。Stage 2：PASS。** 本轮已补齐独立本地视觉比较；主Agent可对上述同一candidateId使用本报告登记review-approve。本节替代以下所有旧候选结论，历史失败用于追溯，不表示当前代码仍存在旧缺陷。

### Stage 1：最后差异复核

M3已解决：`hengxin-smart-image/backend/app/modules/management/health.py:87–100`将未截断总数构造成 `scalar_subquery()`，与active/recent候选和详情在同一个 `session.execute(query)` 中读取；不再独立执行COUNT。无结果时99行初始化 `task_count=0`。active与recent互斥，外层 `IN` 不会因候选重复制造重复详情，ORDER BY含稳定ID。该语句满足READ COMMITTED的一条语句快照边界。

`backend/tests/test_management_monitor.py:270–300`的SQL捕获已覆盖所有包含 `FROM task_records` 的SELECT，并断言只有一条且同时包含 `UNION ALL` 和 `AS total_count`；另外核对105条总数、104条展示、唯一ID、全部四类active和recent排序。空闲场景 `test_management_monitor.py:50–66`覆盖空任务总数。上述测试前提为真实ORM查询和隔离数据库，未用假返回值代替SQL执行。

H1/H2/M1/M2的修复结论沿用紧接下方cd19e114复审矩阵，并通过本候选独立回归复验。初审逐项Spec覆盖表中原有不匹配项现已闭合。权限、白名单脱敏、冻结与上传检查范围不变；没有扩展为真实模型、钉钉或VPS验收。

独立原始输出：

```text
python -m pytest tests/test_management_monitor.py tests/test_management_settings.py -q
........................................................                 [100%]
56 passed in 16.09s
```

### Stage 2：代码质量与测试真实性

| 审查项 | 结果与具体证据 |
| --- | --- |
| 文件大小 | 本轮业务/测试文件全部不超过300行。backend/app/modules/management/health.py为182行，settings.py129行；backend/tests/test_management_monitor.py恰为300行；frontend/tests/settings-monitor.test.ts254行；settings-editor.ts72行。逐文件统计完成。 |
| 命名、职责与类型 | 未发现新增TS any。frontend/src/types/management.ts、api/hengxin/validate-management.ts:34–46同步nullable计数、taskCount、timeoutCapacity；settings-editor.ts:20–72集中处理编辑状态与409；monitor-presentation.ts:3–11独立处理未知和覆盖提示。Python内部辅助方法仍沿用项目既有动态类型风格，契约输入的strict范围校验在backend/app/contracts/management.py:194–200。 |
| 事务与竞争 | management/settings.py:58–62获取singleton锁，98–100校验版本；65–84按固定顺序锁binding并重新读取可用Skill版本；116–118统一提交。backend/tests/test_settings_concurrency.py:10–33使用独立连接竞争且核对唯一audit；skills/service.py:27–33的锁读带populate_existing，既有skills竞争测试已接新入口。异常退出由db/session.py:23–25关闭会话，未提交修改不落库。 |
| 失败路径及交互测试 | backend/tests/test_management_monitor.py:237–268实际存储恶意observation.message并断言不回传；270–300验证真实SQL及超量列表。frontend/tests/settings-monitor.test.ts覆盖409重新读取成功/失败、禁止自动重提、重复点击、低于60只读、未知计数及截断文案。不是仅测试顺畅路径。 |
| 非阻断维护建议 | health.py:10,20–22直接引用diagnostics私有 `_FAILURES`；可后续提供公开的只读诊断映射接口，当前复用同一白名单不会引入错误或泄露。mock-management.ts:87–96仍在无字段变化保存时增加版本，真实settings.py:87–94无变更不增加版本；该mock行为原已存在，建议后续统一，不阻断当前真实HTTP交付。 |

### Stage 2：安全扫描

扫描仅覆盖本轮差异和新增业务源码/测试，不读取.env或输出真实凭据。检索eval/exec、shell=True、innerHTML/v-html、dangerouslySetInnerHTML、前端VITE密钥变量、常见硬编码密钥前缀及password/api_key/secret字面赋值，原始摘要：

```text
scan complete; matches reported by location only
```

无匹配危险项；Python内建any不是TS any。人工核对以下敏感路径：

- SQL使用SQLAlchemy表达式和绑定参数，management/health.py:77–108、settings.py:58–84未拼用户输入；既有竞争测试的schema字符串来自uuid4，非外部输入。
- worker/health.py:20–27仅列表参数执行受部署控制的CLI `--version`，有2秒超时，无shell，无生成调用。stdout仅接受版本正则后存储。
- management/health.py:37–53只按白名单code重建文案，不透传observation.message/action/slotErrors；105行会话仅超管可见，162行起详情仅超管。已有隔离测试验证主管无秘密字段及普通角色拒绝。
- settings.py:36–40只返回指定钉钉标识与配置检测；105–108拒绝网页修改部署标识。前端settings-editor.ts:5–17只构造允许字段；没有AppSecret/CLI凭据回传路径。
- files/multipart.py:24–46按实际流量限制整个上传请求，files/validation.py:35–43再限制图片大小，不仅相信Content-Length。

未发现本轮引入的可利用注入、凭据泄露或越权问题。该结论为本范围源码审查与隔离测试，不等同完整渗透测试。

### Stage 2：独立视觉比较已完成

2026-09-16 16:53起，获得明确授权后执行 `cua.createBrowserTab('iab','http://127.0.0.1:3008/#/management/monitor',{visible:false})` 成功，本审查会话返回 **browser2/tab1**，持续复用返回的 `visualTab` handle。之前误把其他会话的browser/tab编号当成本会话编号造成不可访问，现已解决；不是应用缺陷。

reviewer亲自通过CUA读取AX状态并获取1280×720视口截图，依次检查monitor顶部及滚动后的任务表、settings顶部及钉钉/审计区域、usage邻居基准页。以下是独立观察，不是主Agent转述，也不是mock：

| 对比项 | 实际结果与源码证据 |
| --- | --- |
| 页面骨架、导航与标题 | 三页使用相同侧栏、面包屑和标签导航；英文眉题、中文标题、说明文字左边缘一致，截图标题约x259。monitor.vue:3、settings.vue:2与usage.vue:3均对应共用hx-heading；prototype.css:3–5为28px标题及14px说明。 |
| 卡片、按钮与间距 | 白色圆角卡片/浅灰背景一致；usage查询与settings保存为同一蓝色主按钮，monitor刷新与settings重读为同一默认按钮。usage.vue:5,14、monitor.vue:11–18、settings.vue:8–16；prototype.css:8为23px卡片内边距，26为18px统计卡间隔。实际截图无新增遮挡或水平裁切。 |
| 监控实际内容 | 空闲；排队0、运行0；CLI0.153.4、Worker容量2、PG/Redis/MinIO连接正常；最后检查16:53:09、Worker心跳16:53:06。任务表“已显示13条/总数13条”，错误区能展示“输出清单缺失或不符合约定”，耗时为整数秒。证据：monitor.vue:11–18,33–36；monitor-presentation.ts:3–10。 |
| 表格可读性 | monitor任务、操作者、阶段、会话、耗时、业务错误列对齐；长会话标识按行换行，没有覆盖其他列。usage基准表同样使用浅色分隔线、灰色表头和蓝色操作文字；usage.vue:18–21与monitor.vue:18同源ArtTable。 |
| 配置实际内容 | v1，并发2且提示1–2，超时3600且提示60–3600，上传10MiB，三个默认Skill可见；两列表单正常换行。钉钉区域明确“未配置”“网页只读”，三个标识输入不标为可编辑；审计区显示最近100条及“尚无配置变更”。settings.vue:7–16；未修改输入或点击保存。 |

视觉结论限定当前1280×720桌面视口和已读取状态；没有把本地开发身份视为真实钉钉认证，也没有宣称其他尺寸、真实模型或生产环境已验收。所有页面均为127.0.0.1:3008，未打开或操作VPS。截图已通过本审查会话工具输出呈现，未另存包含历史业务内容的图片到交付目录。

补齐视觉后再次使用门禁快照函数核对，结果仍为 `e5883dd7abd2cc03aaceab28b685fba32d1edb26edb3fedfc9328ad03bd8d74b`；本轮仅更新报告，无业务代码变更。review-approve由主Agent执行，reviewer没有登记批准或写clean。

#### 此前浏览器阻断记录（已解除）

按派发只允许现有本地tab1及127.0.0.1:3008。已实际调用CUA，先返回空surface，后连接出现但标签为空：

```text
cua.getState() -> {"apps":[],"browsers":[]}
cua.getTab('1', {browser:'iab'}) -> Tab not found: 1 in browser 1
cua.listBrowsers() -> [{id:'1', name:'Codex In-app Browser', type:'iab', ...}]
cua.getTab('1', {browser:'1'}) -> Tab not found: 1 in browser 1
cua.listTabs({browser:'1'}) -> []
```

此前在仅允许使用主会话既有tab的范围内，reviewer未能打开页面，因此当时没有批准视觉检查。后来新增授权允许建立独立本地临时tab，已按上文实际完成。

该浏览器访问缺口现已解除，Stage2更新为PASS，不要求修改业务代码。

### 最终已有构建与测试证据

读取主Agent最终原始日志：

```text
# output/phase13-full-backend.log
639 passed, 95 skipped, 12 warnings in 62.41s (0:01:02)
# output/phase13-frontend-tests.log
ℹ tests 100
ℹ pass 100
ℹ fail 0
ℹ skipped 0
# output/phase13-frontend-build.log
vite v7.1.7 building for production...
✓ 3336 modules transformed.
dist/assets/index-BeaBqZRJ.js                                                       1,612.36 kB │ gzip: 533.04 kB
✓ built in 32.27s
```

构建日志含既有dingtalk-login静态/动态导入提示，未导致失败。Node24.18.1、typecheck与隔离PG迁移流程由主Agent执行并记录于hengxin-smart-image/docs/PHASE13-MANAGEMENT-LOCAL-VALIDATION.md；本reviewer未重新运行这些全部步骤。95项skip不视为通过。git diff --check通过（仅CRLF归一化提示）。

---

## 最新复审：2026-09-16 · cd19e114

- 最终送审 candidateId：`cd19e1149acecb9df4b2d6c1381aaa7593e083ef0e7438ada95db4322344207c`。
- 范围沿用下方初审；增加 monitor-presentation.ts 和修复后的契约、mock、测试。开始复审核对 currentId 与 candidateId 一致。
- **Stage 1：FAIL（剩余1项MEDIUM）。Stage 2：未执行，不能登记PASS。** 四个初审问题已修复到下述范围，但总数与截断提示仍存在独立不一致问题。此节优先于下方保留的历史审查结果。

### 修复复核

| 项目 | 结果 | 当前代码与证据（路径均相对 hengxin-smart-image） |
| --- | --- | --- |
| H1 真实诊断来源 | 已修复 | backend/app/modules/management/health.py:20–22,37–53 根据 observation.failure.code 重建白名单文案，旧内部码和固定中文文案可回退；任务行及最近结果共用。tests/test_management_monitor.py:237–269 覆盖输出清单、认证、限流、畸形结构、旧记录及恶意message，主管无detail。 |
| H2 运行任务被100条新任务挤掉 | 已修复 | health.py:88–108 将全部active及recent100候选放入同一SQL的UNION ALL子查询，外层IN避免重复；active与recent谓词互斥；tests/test_management_monitor.py:270起覆盖四种active、101个较新任务及仅一条详情SQL。 |
| M1 未知数量显示0 | 已修复 | health.py:133–138 返回null计数；frontend/src/views/hengxin/admin/monitor-presentation.ts:3、monitor.vue:11–13显示未知及真实issue。 |
| M2 部署超时范围 | 已修复 | backend/app/modules/management/settings.py:47 返回timeoutCapacity；frontend/src/views/hengxin/admin/settings.vue:7–15、settings-editor.ts:34–43展示/限制实际上限，低于60只读。Product-Spec.md:485和DEV-PLAN.md:10已同步。 |

前次逐项覆盖中的配置权限、409、审计、共享默认Skill、冻结轮次及上传实际限制仍保留；本次重跑相关56项全部通过。没有把暂未同步新后端的浏览器契约错误作为产品缺陷：主Agent已说明本地重建尚在进行，尚未通知可验收。

### M3 · MEDIUM · taskCount 与列表仍是不同语句快照

需求：Product-Spec.md:485要求最近100条之外提示总数和截断；当前 frontend/src/views/hengxin/admin/monitor-presentation.ts:6–10 直接用 `tasks.length < taskCount` 决定是否展示截断提示，并显示“已显示 N 条 / 总数 M 条”。

backend/app/modules/management/health.py:87 的 `session.scalar(count...)` 在候选/详情语句（88–108）之前单独执行。UNION ALL已消除了active/recent列表内的迁移漏项，但没有让total与列表同快照。两语句间提交新增/完成/删除，会导致总数小于已显示条数，或错误判断是否截断。

独立确定性交错复现：复用现有SQLite内存fixture和MemoryStore，先经HTTP提交1个任务；包装session.scalar，在真实COUNT返回后、真实详情SELECT前，经同一个隔离HTTP客户端再提交1个任务。没有外部数据库、执行器或模型调用。实际输出：

```text
{'taskCount': 1, 'visibleTasks': 2, 'uniqueTasks': 2}
```

这是两查询间可见数据改变的确定性复现，不冒充PG双连接实测。PG READ COMMITTED允许连续语句看到不同已提交快照，依据[PostgreSQL事务隔离文档](https://www.postgresql.org/docs/17/transaction-iso.html)。不仅顶部指标发生瞬时延迟，该total直接控制是否诚实告知截断。

修复验收：把未截断总数与候选/详情放进同一条SQL（标量子查询、CTE或窗口均可，注意空结果返回0）；或使用明确的一致性读取事务覆盖两者。不要通过 `max(taskCount, len(tasks))` 掩盖错误，这不能检测已截断数据。增加交错回归或明确检查总数也在同一条SQL中。

### 本候选验证证据

独立运行原始输出：

```text
python -m pytest tests/test_management_monitor.py tests/test_management_settings.py -q
........................................................                 [100%]
56 passed in 7.20s
```

读取主Agent最新日志原始摘要：

```text
# output/phase13-full-backend.log
639 passed, 95 skipped, 12 warnings in 48.46s
# output/phase13-frontend-tests.log
ℹ tests 100
ℹ suites 0
ℹ pass 100
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 2712.6179
```

Node24.18.1、typecheck/build及PG迁移验证汇总见 hengxin-smart-image/docs/PHASE13-MANAGEMENT-LOCAL-VALIDATION.md:27–34。skip不计通过；本次不重复运行业务库迁移、不执行模型调用、不接触VPS。Stage1尚未通过，不执行Stage2代码质量/安全扫描/实际邻居视觉对比；等待修复并重新prepare。

---

## 历史初审（以下不是最新候选结论）

- 日期：2026-09-16。
- candidateId：`a0b84327edb9b50f82b8238be354dcf6d0574bda8dab592f4277a1e482373933`。
- 分支：`codex/management-monitor-settings`；base：`3baa541`。
- 范围：相对 base 的本轮差异及新增 management settings/monitor、迁移、业务测试、前端 settings-editor；需求为 Product-Spec.md:459–487、DEV-PLAN.md:3–10、493–504；设计参考 Design-Brief.md:24–30、77。
- 排除：已有 `.codegraph/`、`.cursor/`、`output/` 临时目录不属于交付；output 内日志仅作为验证证据读取。不部署、不提交、不建 PR、不调用模型、不写业务数据库。
- **Stage 1：FAIL。Stage 2：未执行（Stage 1 存在 HIGH，不是 PASS）。**
- 此报告不构成批准；不得使用 review-approve 登记此候选两阶段 PASS。

## 快照与证据边界

首次 `review-status` 返回 currentId `7c8219232d11a9a0f5b8a33fa32999bb71ff515a9455466a7315035997a0495a`，与提供的 candidateId 不同。之后使用门禁自身的 `review_files.snapshot/identity/changes` 重新核对，得到：

```text
currentId a0b84327edb9b50f82b8238be354dcf6d0574bda8dab592f4277a1e482373933
delta []
```

因此记录审查期间曾观察到瞬时变化，不能推断首次不同快照已通过。下列源文件行号、独立回归和复现针对再次匹配 candidateId 时读取的实现。主 Agent 随后明确已派修监控诊断；这些后续修改尚不属于本候选结论，必须重新 prepare 并复审差异。

报告落盘后最后一次核对发现修复已写入：currentId `ce3ff29f956376222565a188c7a9103ead9131f1d30ce10a40d30cca5aa3f065`，相对原候选变化为 `backend/app/contracts/router.py`、`backend/app/modules/management/health.py`、`backend/tests/test_management_monitor.py`（均在 hengxin-smart-image 下）。本报告不声称这些新内容仍有同样缺陷，也不批准这些新内容；需要主Agent提供新的candidateId做差异复审。

## Stage 1 阻断项

### H1 · HIGH · 监控没有消费真实执行的结构化诊断

需求原文：Product-Spec.md:463「Worker 失联、依赖不可达、认证拒绝、限流、超时分别表达」；461 要求显示最近错误及脱敏错误。

本轮 `hengxin-smart-image/backend/app/modules/management/health.py:30` 将输入直接交给只接受内部固定码的 `failure_for`；69 优先取 `attempt.error`、其次取 `round.error`；135 的最近结果只消费 `attempt.error`，未读结构化 observation。

真实生产链路的证据：

1. `backend/app/execution/codex_runner.py:41–46` 先保存 receipt reason / event summary.error。
2. 同文件153–160 随后根据 stderr 做进一步分类，通过 `observer.phase('failed', failure)` 保存诊断，并把中文 `failure['message']` 写入 round.error。这意味着 attempt.error 可能是较泛化的码、空值；round.error 是展示文案，并非内部码。
3. `backend/app/execution/observation.py:88–93,95–109` 将结构化 failure 保存到 `ExecutionAttempt.observation`。
4. `backend/app/execution/diagnostics.py:54–59` 不认识中文文案，也不把公开大写 code 自动当内部小写 code 接受；未匹配时统一返回 UNKNOWN。

因此监控可丢失已经采集的认证/限流/输出清单等分类。主 Agent 实机补充：同一任务监控显示未知，而详情具有输出清单诊断；该现象与上述静态链路一致。此实机观察由主 Agent 提供，并非本 reviewer 自行浏览所得。

测试盲点：`backend/tests/test_management_monitor.py:153–168` 把 `authentication_failed/rate_limited/timeout` 直接写入 attempt.error，未覆盖“attempt 泛化码或空值 + observation.failure 已分类 + round.error 中文”这个生产前提。既有测试通过不能证明真实诊断正确。

修复验收：优先复用经过验证、白名单脱敏的 observation/progress failure 分类；同时修任务行及最近结果。不要直接透传任意数据库 message，也不要简单把公开 code 传入仅支持内部码的函数。覆盖无 observation 的历史记录、恶意 message、认证/限流、输出清单、部分失败，以及主管脱敏响应。

### H2 · HIGH · 100 条混合列表会隐藏仍在运行的任务

需求原文：Product-Spec.md:461「表格列运行任务、操作者、会话标识、阶段、已运行时间和脱敏错误」；465「设计主管看到全员队列与失败任务」。

`backend/app/modules/management/health.py:55–64` 将 queued、所有运行状态、failed、partial 按更新时间倒序后统一 `limit(100)`。既无运行任务优先保留，也无分页/截断信息。`frontend/src/views/hengxin/admin/monitor.vue:18` 又禁用了分页。

独立复现：使用现有 files_env 的 SQLite 内存数据库和 MemoryStore，经任务 HTTP 接口创建任务；将首个任务设为运行且更新时间较早，再创建100个较新排队任务；调用真实 build_monitor，只把外部依赖探测替换为 up。未运行任何执行器或模型，未写真实业务数据。原始结果：

```text
{'queueSize': 100, 'runningCount': 1, 'visibleTasks': 100, 'visibleRunning': 0, 'activeTaskVisible': False}
```

影响：当前执行和卡住任务恰恰可能最久未更新，监控数字显示正在执行，但表格完全找不到该任务；管理员和主管均受影响。

修复验收：让所有当前运行/待核实任务可见；排队与历史异常可采用明确分页或独立有界列表，返回截断/总数并在 UI 提示。增加上述101任务回归，验证不是仅修改排序却仍静默丢失队列。

## Stage 1 逐项覆盖

下表路径以 `hengxin-smart-image/` 为前缀；“已实现”仅指列出的代码/隔离验证范围，不代表生产验收。

| 需求条目 | 结论 | 证据与验证方式 |
| --- | --- | --- |
| 真实接口挂载，移除占位 | 已实现 | backend/app/main.py:41–45；contracts/router.py:22–33 已移除 monitor/settings 占位；settings HTTP 回归45项组合通过。 |
| PG 队列数、运行数 | 已实现 | backend/app/modules/management/health.py:85–96 按 Job/Round 查询；tests/test_management_monitor.py:117–129 校验1运行、1排队。列表完整性另见 H2。 |
| Worker 心跳和最后检查 | 已实现 | backend/app/worker/health.py:42–57 持久化当前节点采样；management/health.py:26–27,109–114 按30秒判断，测试67–78覆盖过期/未来/缺失。 |
| 空闲不报离线 | 已实现 | management/health.py:45–52,115–122；测试50–64。无活动执行但新鲜就绪心跳为 idle。 |
| 配置目标与实际容量不混淆 | 已实现 | management/health.py:112–114,144–148；worker/health.py:39–40,56 采样 pool.limit；测试232–237覆盖目标低于/高于容量。 |
| CLI版本、配置就绪 | 已实现 | worker/health.py:20–42 仅 `--version`，检查指定版本、隔离器、认证文件可读性；测试184–215。表示配置就绪，不声称真实认证成功。 |
| 临时目录空间取 Worker 而非 API 主机 | 已实现 | worker/health.py:29–32；management/health.py:131,140；测试203–215,218–229 验证目录采样及未知。 |
| PG/Redis/MinIO 当前健康，不以历史成功替代 | 已实现 | management/health.py:108,116–122,141–143，复用 app/health.py:14–41；测试81–94、240–247。 |
| 过期结果未知、停止 Worker 可反映失联 | 已实现 | management/health.py:26–27,45–47,126–128,131；测试67–78。前端 monitor.vue:12 对 unknown 有提示。 |
| 健康检查不调用模型 | 已实现 | worker/health.py:22 仅CLI版本子命令；management/health.py:108 仅依赖探测；测试196–201断言子命令。 |
| 操作者、会话、阶段、时间 | 部分实现 | management/health.py:55–76，测试117–135证明操作者来自 attempt、管理员可见会话；H2 导致运行任务可能消失。 |
| 认证/限流/超时及最近调用诊断 | 不匹配 | H1；固定码测试不能代替真实 observation 诊断读取。 |
| 主管可读全员业务状态，不能见服务器详情/会话 | 已实现（除 H1/H2） | management/health.py:72,81–82,124,129；测试130–150、157–168。detail/sessionId 为 null，不含原始路径或秘密文本。 |
| 普通角色/匿名不能读取管理监控 | 已实现 | monitor_router.py:13 使用 CurrentUser；management/health.py:81–82；测试138–150、250–257。 |
| 系统配置仅超管可读写 | 已实现 | settings_router.py:12,16–23 require_permission('manage_system')；tests/test_management_settings.py:48–55 覆盖其余三角色403。 |
| singleton 持久化、版本409 | 已实现 | models.py:10–15，settings.py:57–61,96–99；settings测试29–45。tests/test_settings_concurrency.py:10–32 用两个PG连接断言仅一方成功。 |
| 并发不超过部署容量 | 已实现 | settings.py:24,101–102；tasks/claims.py:64–68；settings测试70–75,97–114。不扩大Celery pool。 |
| 超时60–3600、上传1–10MiB，越界拒绝 | 已实现，但有额外部署超时限制 | contracts/management.py:193–199、settings.py:103–104；settings测试58–67。下方 M2 记录前后端上限不一致。 |
| 所有实际变更有操作者、版本、前后值审计 | 已实现 | models.py:18–26；settings.py:86–93,108–116,120–128；settings测试29–45,80–94；前端settings.vue:15展示版本、操作者、时间、字段。 |
| 默认Skill共享绑定与审计、事务校验 | 已实现 | settings.py:64–83,112–126；skills/router.py:60–63 调用共同服务；settings测试80–94、既有 skills并发测试改用新共享入口。 |
| 后续轮次冻结配置，旧轮次不追溯 | 已实现 | tasks/service.py:21–34；settings测试97–114 校验旧值、新版本、新超时和准入。实际执行读取冻结timeout见 execution/codex_runner.py:101。 |
| 上传限制实际执行 | 已实现 | files/router.py:30–35；multipart.py:19–48限制请求实际字节；validation.py:35–43限制图片读取；settings测试115–117确认新1MiB限制返回413。 |
| 钉钉标识/检测只读，无AppSecret/CLI凭据回传 | 已实现 | settings.py:36–40,105–107；settings.vue:12–13；settings-editor.ts:5–17,43–48 构造白名单字段。 |
| 前端capacity、409重新拉取 | 已实现 | settings.vue:9–14；settings-editor.ts:34–65；frontend/tests/settings-monitor.test.ts:72起覆盖越界、409成功/失败、禁止自动重提和重复点击。 |
| 加载/错误/空态、既有视觉风格 | 源码已覆盖；实际视觉未由本reviewer验收 | monitor.vue:5–18，settings.vue:3–15，复用既有ElCard/ArtTable/类名；主Agent称已浏览真实页面，但本报告不据转述签署独立视觉PASS。 |

## 其他 Stage 1 差异（不扩大修复范围）

### M1 · MEDIUM · 监控查询失败时把未知数量显示成0

`backend/app/modules/management/health.py:102–106` 返回 queueSize/runningCount=0，issue.message 明确说明“数量未知”；但 `frontend/src/views/hengxin/admin/monitor.vue:11–13` 无条件显示两个0，unknown 分支又只显示固定心跳提示，没有展示这个 issue。数据库查询失败与真实空队列在数字上无法区分。应针对 MONITOR_UNAVAILABLE 显示未知数量及真实 issue，不能把缺少数据解释为零。测试171–181只断言后端state/issue及脱敏，未验证最终UI数字。

### M2 · MEDIUM · 配置超时有未展示的额外上限

Product-Spec.md:487 与前端 settings.vue:9–11 宣告60–3600秒；后端 settings.py:25,103–104 另把环境 codex_timeout_seconds 当上限。当该部署值低于3600时，前端允许填写的值被422拒绝，却未告知实际可用上限。当前本机默认3600时不触发；属于允许的部署配置下的契约差异，不是当前本机已复现的故障。应明确该限制并返回/展示有效上限，或按需求统一行为。没有建议解除底层执行安全限制。

### Spec 漂移检查

本轮新增 settings表/audit表、monitor/settings API、共享默认绑定、配置冻结及前端编辑器均对应 Phase13范围，未发现新业务页面或任意终端。证据：migrations/versions/0011_management_settings.py:11–18、settings_router.py:16–23、monitor_router.py:12–14、DEV-PLAN.md:493–502。M2是需对齐的额外约束。既有临时目录按派发要求不作为scope creep。

## 验证与构建原始输出

独立执行（全为内存SQLite/Mock Store，无真实外部依赖）：

```text
python -m pytest tests/test_management_settings.py tests/test_management_monitor.py -q
.............................................                            [100%]
45 passed in 23.29s
```

H2复现最初未载入测试环境配置，因 database_url / minio 测试配置缺失退出，未连接外部数据库。载入现有 tests/conftest.py 后在内存数据库成功复现，输出见 H2。

读取主Agent日志 `output/phase13-settings-tests.log:1`：

```text
................................................................         [100%]
64 passed in 5.07s
```

读取主Agent `output/phase13-full-backend.log` 末尾原始摘要：

```text
628 passed, 95 skipped, 12 warnings in 42.20s
```

95项skip不视为验证通过。该日志包含auth空主键SAWarning与TestClient cookie DeprecationWarning；并非本轮新增功能失败。独立PG迁移和竞争由主Agent执行；读取其 `output/verify-phase13-db.py:7–19` 确认使用唯一测试库、upgrade/downgrade0010/upgrade及pytest流程。没有为了审查重复操作本机业务库。

前端构建日志 `output/phase13-frontend-build.log` 的末尾原始输出：

```text
dist/assets/index-6Uy4y6V8.js                                                       1,612.24 kB │ gzip: 533.02 kB
✓ built in 29.61s
```

本地后端镜像构建日志 `output/phase13-local-build.log` 末尾原始输出：

```text
#14 naming to docker.io/library/hengxin-smart-image-backend:phase8 done
#14 unpacking to docker.io/library/hengxin-smart-image-backend:phase8
#14 unpacking to docker.io/library/hengxin-smart-image-backend:phase8 1.6s done
#14 DONE 8.1s
```

主Agent另提供 frontend97tests、typecheck成功、真实HTTP200/健康依赖up/CLI0.153.4/容量2和浏览器渲染通过的结果；本reviewer未获得这些全部检查的独立原始输出，不把转述冒充独立运行证据。

## Stage 2

**未执行。** H1/H2属于Stage1功能与需求阻断，按skill不得进入完整代码质量、安全扫描和邻居页面实际视觉比较。Stage1已做权限与脱敏功能核对，但不等于Stage2安全扫描通过。

主Agent完成修复并重新prepare后，先复审本报告H1/H2及其他差异；Stage1通过后再执行Stage2。本报告不写 `.needs-review`、不登记批准、不修业务代码。
