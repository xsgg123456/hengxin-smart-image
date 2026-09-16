# Phase 11A 本轮接入基础设施独立审查

## 当前复审结论（2026-09-11，第二轮）

- candidateId：`409f6eef2092301682f8271999a04f0cdf032ac926b3b33135542673d49fd302`。
- **Stage 1：PASS；Stage 2：PASS。仅适用于本报告列明的本轮接入基础设施及新增端口测试。**
- F-01、F-02 均已关闭；本次差异复审未发现新的需修复缺陷。
- 完整 Phase 11A 业务验收仍为 **BLOCKED（WSL 模型网络）**。上述 PASS 不是整个阶段通过，也不批准范围外的既有变更。
- 本次只修改本报告，未修改代码或操作服务/网络，未执行 review-approve。主 Agent 登记凭据前仍须确认 currentId 等于本轮 candidateId。

### Stage 1：重新核对本轮功能与修复影响

复审从 Stage 1 起执行。读取当前控制器及相关测试，并重新读取 Worker、keeper、PowerShell 入口、Compose overlay、配置样例和两份联调说明；按上一轮同一 Spec 8.3 / Phase 11A 基础设施边界核对，不扩展到未完成的真实业务验收。

| 本轮功能 | 当前证据与结论 |
| --- | --- |
| 项目及连接目标归属 | `infra/local_codex_control.py:90–117` 在停服前检查已识别项目中唯一运行的 PostgreSQL、MinIO，要求内部 5432/9000 对应的发布绑定严格等于配置端口及 127.0.0.1。Redis 启动后 `:225–227` 重新 inspect，并检查 6379 的实际发布绑定。PASS。 |
| 非终态任务保护与安全切换 | `:19–23,123–126,206–222` 保留全非终态门禁、停 API 后二次检查和竞争提交恢复原 API 的逻辑；restart 在两次空闲检查、关闭入口与停止容器消费者之后。测试 `backend/tests/test_local_codex_control.py:60–69,132–155` 全部通过。PASS。 |
| Worker 重载及就绪后开放入口 | `:224–231` 按安装/核验 unit、Redis 归属检查、专属服务 restart、定向 pong、Outbox/API 的顺序执行；`infra/local_codex_worker.py:47–50,73–75` 在新进程中加载配置并设置执行槽。测试 `test_local_codex_control.py:157–163` 核对 restart 与就绪次序。PASS。 |
| 失败关闭与 fixture 恢复 | `:232–244` 保留先停 WSL 后启 fixture 消费者、失败关闭 API 的路径；状态机故障测试及下述端口拒绝补充验证通过。PASS。 |
| 认证、目录、进程隔离与 Windows 入口 | 复核 Worker、keeper、PowerShell、overlay 和配置样例未见相对上一轮的实质变化，沿用下方首轮逐项证据；本轮配置/keeper/拒绝路径回归通过，PowerShell Parser 解析 0 errors。PASS。 |

功能覆盖未因修复退化。没有新增 UI、API、表或产品范围，视觉审查不适用。尚未真实生成、返工、下载归档及双任务并行的事实保留为完整阶段 BLOCKED，不列本轮缺失实现。

### Stage 2：缺陷关闭与验证

**F-01 已关闭。** `local_codex_control.py:109–117` 将 Worker 读取的 PG/MinIO 端口与目标项目实际绑定相校验；缺少服务、非运行/非唯一服务、缺少或多余绑定、非 loopback、端口不同均不能满足检查。`backend/tests/test_local_codex_ports.py:31–51` 以相同项目标签及密码复现错误配置端口并断言拒绝，同时覆盖缺失/非 loopback 绑定；原来仅靠相同密码放行的路径不再成立。Redis 采用同一检查函数，且 `:226–229` 在 Worker 重启/就绪前核对。

**F-02 已关闭。** `local_codex_control.py:228` 改为 restart 已核验归属的专属服务，避免 active Worker 保留旧配置；前后仍有空闲门禁、消费者隔离及定向就绪检查。此修复不依赖 pong 证明配置重载，而由新 Worker 初始化加载配置。主 Agent 随后补充本候选真实验证：两次 start 均成功，第二次 MainPID **2512→2787**，节点 ping 通过。该现场证据确认重复 start 确实重启；reviewer 未直接操作服务。没有据此声称已实际修改并验证 1→2→1 并发参数或运行真实双任务。

reviewer 独立验证：

- 执行 `python -m pytest hengxin-smart-image/backend/tests/test_local_codex.py hengxin-smart-image/backend/tests/test_local_codex_control.py hengxin-smart-image/backend/tests/test_local_codex_ports.py -q -p no:cacheprovider`，禁用字节码写入：**64 passed in 2.57s**。
- PowerShell `Parser.ParseFile`：**0 errors**，未执行启停脚本。
- 使用实际 `published_port` 的额外内存验证：缺少 MinIO、Redis 缺少/空绑定、非 loopback、错误端口均拒绝；在实际 execute 状态机注入 Redis 端口拒绝，确认 API 保持关闭且尚未 restart/ping。**PASS**，没有服务或网络调用，也未增加代码文件。

新增控制器 278 行、控制测试 286 行、端口测试 51 行，仍在 300 行限制内。修复采用已有归属校验及专属服务生命周期，没有新增凭据输出、动态 shell 字符串或数据删除。测试新增 9 个用例，确实运行实际端口校验，未用替换校验函数的方式虚构端口检查通过。状态机测试仍模拟 Docker/WSL；本轮补充了 Redis 校验失败不开放入口的内存证据。首轮注明的 Win32 真实进程竞态、PostgreSQL 事务竞争及真实模型业务验证边界保持不变。

主 Agent 提供本候选 WSL 后端全套回归：**374 passed、39 skipped、10 warnings**；reviewer 未重跑 WSL 全套，跳过项不计通过。先前的 365 passed / 39 skipped 及前端 typecheck / 60 tests 保留为历史证据。真实两次 start 和 PID 变化已收到；截至本次更新，最终 fixture 恢复仍在主 Agent 执行中，不提前记为完成。联调验证文档在 reviewer 最近读取时仍为旧 55 tests，最新独立 64 tests 及本候选主侧补充证据以本节为准。

### 当前交接

新候选在本轮基础设施范围内两阶段通过。主 Agent 可在快照仍匹配且范围外变更另有有效审查依据的前提下，按 HARNESS 协议登记本报告；不得把它解释为批准既有 `frontend/src/types/import/components.d.ts`、`.codegraph/` 或 `.cursor/`。实际重复 start 的 PID 证据已补齐，最终 fixture 恢复记录待主 Agent 完成后补充；整个 Phase 11A 仍为 BLOCKED。

## 首轮历史记录（以下结论仅针对旧 candidate，已由上方复审结论更新）

日期：2026-09-11。

- candidateId：`a8d5bbe4c67f571fc047e03517143d78090fc8560669a84e39c5d95b014472f6`。
- Stage 1：**PASS（仅本轮基础设施功能覆盖）**。
- Stage 2：**FAIL（1 项 HIGH 安全隔离缺陷、1 项 MEDIUM 配置一致性缺陷）**。
- 基础设施交付：**暂不批准**；不得登记两阶段 PASS。
- 完整 Phase 11A 业务验收：**BLOCKED（WSL 模型网络）**。真实生成、返工、并行等未实测内容是阶段验收缺口，不记为本轮缺失实现，也不冒充 PASS。

## 范围、方法与快照

依据 `.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、根目录 `DEV-PLAN.md:351–380` 和 `Product-Spec.md:231–240`，先核对功能覆盖，再检查质量、安全与测试真实性。

审查范围（下文代码路径相对嵌套 `hengxin-smart-image/`）：

- `infra/local_codex_worker.py`、`infra/local_codex_control.py`、拆分模块 `infra/local_codex_keeper.py`。
- `infra/start_local_codex.ps1`、`infra/compose.local-codex.yaml`、`infra/.env.local-codex.example`。
- `backend/tests/test_local_codex.py`、`backend/tests/test_local_codex_control.py`。
- 配套说明 `docs/LOCAL-CODEX-DEVELOPMENT.md`、`docs/PHASE11A-VALIDATION.md`。

只读参考既有 Compose、Settings、任务状态及沙箱实现。结构查询使用 CodeGraph。没有修改代码，没有启动/停止服务、操作网络、调用模型或 spawn；只新增本报告。未读取实际认证文件内容。

审查开始及报告前的 `review-status` 均返回上述 currentId，reviewedId=null、approved=false。主 Agent 在审查期间补充了验证文档中的 Skill 版本及真实切换证据，未见受控代码快照变化。快照还包含既有 `frontend/src/types/import/components.d.ts`、`.codegraph/.gitignore`、`.cursor/rules/codegraph.mdc`，这些不属于本轮审查，未修改、未批准。

## Stage 1：本轮基础设施功能覆盖

| 要求 | 结论及证据 |
| --- | --- |
| Windows 控制入口及显式非生产环境 | 已实现：`start_local_codex.ps1:1–15` 以参数数组调用控制器；`local_codex_control.py:26–48,90–108` 校验项目、配置文件、用户与容器归属。Windows PowerShell 语法解析错误数为 0；真实入口证据见下节。连接归属的充分性另见 Stage 2 F-01。 |
| Linux 非 root、固定 CLI、认证与实际沙箱预检 | 已实现：`local_codex_worker.py:42–70` 检查系统/UID、运行文件、版本、login status，并使用实际任务沙箱执行版本命令。该检查不调用模型，也不证明真实 Skill 图像生成成功。 |
| 真实与 fixture 消费者切换 | 已实现：`local_codex_control.py:197–228` 校验恢复模式，停 API 后再次检查空闲，再停旧消费者；真实 Worker 定向 ping 后才启动 Outbox/API；fixture 先停 WSL 再启容器消费者。`compose.local-codex.yaml:4–15` 明确启用真实执行并关闭 fixture。 |
| 非终态任务保护 | 已实现：`local_codex_control.py:19–23,114–117,201–211` 同时查询 jobs/rounds；包括 queued、uncertain、未知值与 NULL；二次检查发现竞争提交则仅恢复原 API，不切消费者。测试 `test_local_codex_control.py:60–69,128–143` 验证这些条件。 |
| 切换失败、停止和数据保留 | 已实现：`local_codex_control.py:221–233` 停止后保持入口关闭；消费者切换失败重新检查并关闭 API，不猜测回滚。没有 down、卷删除或历史来源改写。`test_local_codex_control.py:145–170` 覆盖失败关闭及 stop；真实 fixture 恢复由主 Agent 提供证据。 |
| 独立凭据和任务运行目录 | 已实现接入：`local_codex_worker.py:19–30,58–70` 引用独立认证文件和根目录；复用既有 `backend/app/execution/workspace.py:17–44,48–70` 的任务私有 home、认证复制及清理环境的沙箱，不挂载桌面完整 CODEX_HOME。跨真实任务运行隔离仍待完整阶段实测。 |
| WSL 进程归属与保活 | 已实现：`local_codex_keeper.py:20–51,54–93` 检查 PID、创建时间、可执行路径及完整参数；终止前持有进程句柄并二次核对；仅结束本项目拥有的 keeper；手工 keeper 复用但不接管终止权。相关自动测试见 `test_local_codex_control.py:207–231,271–281`。 |
| 分阶段交付说明 | 已实现：两份联调文档及源计划明确真实模型网络阻塞，不以 fixture、登录成功、session ID 或版本命令代替新生成图片。 |

没有新增 UI，本轮视觉对比不适用。未发现本轮新增页面、API、表或未经要求的产品范围扩张。源计划 11A 第 3–4 项完整业务与双任务验收，以及第 5 项中的完整业务浏览器验收，均留在 BLOCKED 范围。

## Stage 2：具体缺陷

### F-01 · HIGH / P1：未将 Worker 连接目标绑定到已检查空闲的项目

位置：`infra/local_codex_control.py:106–108,114–117`；`infra/local_codex_worker.py:26–29`。

控制器按 Compose 标签找到项目 A，并在 A 的 PostgreSQL 容器内执行空闲查询；归属检查只对比数据库密码，没有核对 PostgreSQL、MinIO 实际发布端口与配置端口。Worker 独立采用 `.env` 的 `POSTGRES_PORT`、`MINIO_PORT` 连接 WSL 可达的 loopback 端点。`start` 只重建 Redis/Outbox/API，不重建数据库或 MinIO，因此不会自动纠正这些端口差异。

触发：复制或修改本地环境配置后，POSTGRES_PORT 指向另一套本地项目 B；A、B 使用相同开发数据库凭据时，配置和 A 的空闲检查仍可通过。若 B 有相应 job ID 的待执行/重投消息，Worker 可能对 B 处理任务，而控制器保护的只是 A；MinIO 错指还可能造成对象不存在或业务数据写入错误环境。没有目标服务时也不会在目前的 `check` 中可靠发现，后续启动才失败。这里没有声称本开发机已发生数据串用。

独立无副作用复现：用实际 `Controller.inspect()` / `idle()`，仅替换命令执行器为内存响应；A 容器实际绑定 `127.0.0.1:55433`，配置为 `55434`，标签、目录、密码均匹配且 A 空闲。检查通过；实际 `local_codex_worker.configuration()` 随后构造连接 `55434` 的 URL。输出：

```text
REPRO: ownership + idle accepted PostgreSQL bound to 55433 while worker configuration selects 55434; no Docker/WSL/network calls
```

对应要求：Spec 8.3 的独立测试数据及真实/fixture 隔离，计划 11A 第 2 项的连接地址与专用环境。该安全问题在 Stage 2 检出。

建议：切换前要求唯一且运行中的项目 PostgreSQL、MinIO；核对实际发布 IP/端口与 Worker 配置一致，不匹配即在任何停服前拒绝。核对 WSL 可达端点确为该项目服务；Redis 新绑定也要核对。补充端口错配、缺少 MinIO、外部同凭据数据库等拒绝路径测试。不能只用数据库密码或 Celery pong 证明连接归属。

### F-02 · MEDIUM / P2：重复 start 可报告成功，但现有 WSL Worker 没有应用新配置

位置：`infra/local_codex_control.py:214–220`；`infra/local_codex_worker.py:47–50,73–75`。

触发：真实模式已运行且无非终态任务，将基础配置的 GENERATION_CONCURRENCY 从 1 改为 2，再执行 start。控制器重建 API/Outbox，却对已经 active 的 WSL 服务只发 `systemctl start`；Worker 只在进程初始化时读取配置，已有进程仍是 concurrency=1。针对节点名的 pong 检查不检查配置或执行槽，仍会开放 API 并输出 PASS。其他不改变 unit 文本的认证引用、运行目录配置也存在新旧配置并存风险。

现有测试 `test_local_codex_control.py:153–158` 只断言 start 命令和调用次序，模拟器没有已有 active 服务及旧配置语义，不能证明重载成功。主 Agent 提供的 fixture→start→fixture 成功同样没有覆盖该路径。

建议：完成入口关闭与二次空闲检查后，安全地重启本项目专属 Worker，或明确识别配置指纹并拒绝 active Worker 的配置变更，给出 stop→start 操作提示。就绪验证应核对实际 worker 配置/槽位，补充 1→2→1 的无模型测试。该问题不把尚未执行的真实双任务验收算作缺失功能。

## 测试真实性、质量和证据边界

| 验证 | 结果与来源 |
| --- | --- |
| 本轮两份新增测试 | reviewer 独立执行 `python -m pytest hengxin-smart-image/backend/tests/test_local_codex.py hengxin-smart-image/backend/tests/test_local_codex_control.py -q -p no:cacheprovider`，禁用字节码写入：**55 passed in 0.96s**。 |
| Windows 入口语法 | reviewer 用 PowerShell Parser.ParseFile 解析：**0 errors**；没有执行启停脚本。 |
| F-01 配置错配 | reviewer 内存复现通过，未调用 Docker、WSL 或网络。 |
| WSL 后端回归 | 主 Agent / 验证文档：**365 passed、39 skipped**；reviewer 未重跑，skip 不计 PASS。 |
| 前端 | 主 Agent / 验证文档：typecheck 退出 0，**60 tests passed**；reviewer 未重跑。 |
| 真实控制器 check / fixture / start | 主 Agent 补充及更新后的验证文档：check 成功；fixture 后 WSL inactive、容器 Worker 运行；最终模块拆分后的 start 成功且包含 WSL 节点定向 ping；随后再次 fixture 恢复演示。reviewer 未操作服务或独立复核现场。 |
| Skill 与模型任务 | 主 Agent 经 API 核实 `ecommerce-wallpaper-swap` **1.0.0**；本轮未新增真实模型任务。既有专用任务因模型网络失败已取消；session ID 不作为生成成功证据。 |

新增三个 Python 模块分别 84、267、94 行，两份测试分别 46、281 行，符合技能的 300 行限制。控制、Worker、keeper 职责已拆开。范围内静态检查未见硬编码真实密钥、eval、动态 SQL 拼接业务输入、把密钥传给前端；数据库密码做 URL 编码，子进程输出对用户隐藏。固定 SQL 中的状态集合不是用户输入。绝对路径用于明确运行时归属，配置样例不含凭据。

测试确实执行了状态机、空闲 SQL、unit 独占创建及拒绝外部 keeper 等逻辑；但 Docker/WSL 生命周期大部分被模拟，SQLite 空闲查询不证明 PostgreSQL 事务竞争。Win32 keeper 的真实创建/拥有者终止路径没有独立自动化覆盖，不宣称已验证所有 PID 竞态。上述限制与 F-01/F-02 一同解释为什么 55 tests 通过不足以批准安全切换全部场景。

## 交接

请主 Agent 修复 F-01/F-02，补充对应回归后重新 review-prepare；代码若变化，旧 candidate 结论不能批准新快照。修复后重新从 Stage 1 复核，再完成 Stage 2。不要登记当前 candidate 的两阶段 PASS，不写 clean。

即使后续基础设施两阶段通过，完整 Phase 11A 仍为 **BLOCKED**，直到真实新生成图片、单图/整套返工、同 session resume、下载归档、双真实任务隔离及故障恢复取得各自证据。
