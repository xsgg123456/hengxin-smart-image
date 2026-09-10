# Phase 9 最终独立审查

- 日期：2026-09-10；使用 `.agents/skills/code-review/SKILL.md`。
- 初始 candidateId：`b0b26421b40d8986f494f904eac69bf7c647c29c626add3bb306a445407fe607`。
- 最终 candidateId：`1afc11a1fbc02d0bbf195c7f137a2fef497320bed83af540bc57ab814465162b`。审查中主 Agent 增加了 `infra/verify_phase9_live.py` 的真实 Worker 故障注入验证并恢复自动生成的前端声明到原内容；已重新读取脚本并复核差异。
- 范围：Phase9 的 execution/{codex_runner,workspace,process,events,output_collector,provenance,materials}，worker/{reconcile,health,tasks,celery_app}，tasks/{attempts,service,queries}、配置、迁移、测试与 infra。下文路径除注明仓库根外，均相对 `hengxin-smart-image/`。
- 依据：Product-Spec 第9.1/9.2、AC-015、021–025，DEV-PLAN Phase9，docs/PHASE9-PLAN.md。用户原有技能/hook改动保持不动；不把未来 Phase10 返工入口、Phase11 归档完整流程、Phase13 展示及 Phase14 图像效果算作现有缺陷。
- **Stage 1：PASS；Stage 2：PASS。** 无未关闭 HIGH/MEDIUM。最终独立快照检查 candidate=current=`1afc11a1fbc02d0bbf195c7f137a2fef497320bed83af540bc57ab814465162b`，changed=[]，可由主Agent登记同一candidate。

## Stage 1：需求逐项核对

“匹配”只覆盖表中明确列出的当前阶段责任；实际测试与静态推断分开列出。

| 条目 | 结论及代码证据 | 验证证据 |
|---|---|---|
| 9.1 新任务先持久入队，无预造会话 | 匹配；backend/app/modules/tasks/service.py:20 写 Job、Round、Outbox；backend/app/execution/codex_runner.py:84 后才建 ExecutionSession | backend/tests/test_execution_records.py:28 验证未启动ID可空；仓库根 output/phase9-live/report.json 有真实任务/轮次/会话各1 |
| 9.1 首次执行唯一绑定会话 | 匹配；codex_runner.py:113 在 thread.started 后持久化；attempts.py:16 session_id 唯一 | test_execution_records.py:28 拒绝跨任务复用；真实 report 的 sessionId 非空 |
| 9.1 每轮结束退出并保留材料，人工查看不挂CLI | 匹配；process.py:59 finally stop；workspace.py:19 持久任务home，无人工等待分支 | infra/verify_phase9_sandbox.py:40 实际 kill namespace 后 detached 子树停止；真实单轮结束后返回图片 |
| 9.1 单张/整套返工新进程续接原ID | 代码匹配；codex_runner.py:124 显式 resume previous，无 --last；materials.py:29 选择目标；results.py:18 对应真实slot | sandbox脚本:69 在新轮次目录按首会话续接；test_tasks.py:167 内部轮次服务覆盖真实操作者和目标，用户入口留Phase10 |
| 9.1 新任务B独立会话和执行环境 | 匹配；workspace.py:21 按task UUID分home；:68 仅bind本任务home及本轮work，独立proc/tmp | sandbox真实双会话ID不同；跨任务读取和修改、control可见性与detached树检查均由脚本断言 |
| 9.1 归档不启动CLI、不销毁可返工会话 | 本期边界匹配；worker/tasks.py:46 仅generation调用runner；workspace.py:19 无会话删除 | 未新增归档执行或清理入口，完整归档留DEV-PLAN.md:312指定的Phase11 |
| 9.1 删除先失效执行/发布，不破坏引用 | 匹配；tasks/cancellations.py:17 持久取消；tasks/results.py:12 短事务重新核验；runner.py:80 启动前取消收敛 | test_tasks.py:92；test_execution_reconcile.py:108 上传及发布时取消；独立preflight删除测试通过 |
| 9.1 重建后续接，缺材料失败保旧图 | 代码匹配；workspace.py:19 home独立于round；runner.py:88 不建替代会话，:106 缺材料报错；results.py:12 未发布不改旧版本 | 新CLI进程、新round同home续接的真实传输证据；没有宣称重新容器化部署，当前架构为原生Worker |
| 9.2.1 同任务全阶段互斥，跨操作者生效 | 匹配；tasks/service.py:91 ACTIVE冲突，tasks/models.py 的未结束轮次唯一约束；claims.py:48 数据库锁认领 | test_tasks_concurrency.py:87 两用户整套/单张争用一受理一409；:132 直接写第二未结束轮次被DB拒绝；Linux全套无skip |
| 9.2.2 幂等、同键异内容拒绝，先授权 | 匹配；service.py:39 授权先于重放，:80/88 内部轮次同样处理 | test_tasks_concurrency.py:61；仓库根 output/phase9-final-regression.log:25 并发同键202/异内容409；真实任务幂等重放计数仍1 |
| 9.2.3 重复消息单次启动、短事务、不重跑终态 | 匹配；claims.py:57 仅queued认领；attempts.py:28 round唯一；runner.py:99 离开业务锁后下载执行 | output/phase9-final-regression.log:28–31 两独立Worker、并发上限2下重复认领只一次；test_codex_runner.py:101 重投不启动第二次 |
| 9.2.4 失效/旧轮次/取消迟到不发布 | 匹配；results.py:12–15 重新锁定核验；reconcile.py:44 轮换token并在:140用同一发布屏障 | test_tasks.py:156 旧token和过期租约；test_execution_reconcile.py:77 恢复后旧token拒绝；:108 三取消窗口 |
| 9.2.5 不确定先核实，能恢复则继续收集 | 匹配；reconcile.py:98–111 先核实精确PID/boot/start；:24 CAS轮换所有权；:118–140 读取真实事件、来源证明、图片并发布；:78 证据不足仍uncertain | 本地恢复fixture mock了provenance，未独自采信；最终无mock实机证据见output/phase9-live-recovery-summary.json:3–19，恢复成功且执行计数仍1 |
| 9.2.6 删除持久取消并确认停止，退出页面不取消 | 匹配；cancellations.py:17；runner.py:25/113 监测；process.py:46 停止执行树 | output/phase9-final-regression.log:35 queued/running删除及重启；:39 离页后后台完成；独立preflight测试 |
| AC-015 | 当前阶段会话/进程接入匹配，完整单张/整套UI验收按计划留Phase10；代码见上述9.1各行 | 实际双会话和新round同ID续接；无 --last/ephemeral，无归档调用路径 |
| AC-021 | 内部轮次互斥匹配，UI入口按计划未开放 | test_tasks_concurrency.py:87 真PG独立连接、两操作者、整套/单张；queries.py:78 各忙碌态及uncertain均给阻止原因 |
| AC-022 | 匹配，不以上限1冒充并发证明 | output/phase9-final-regression.log:28–31；test_tasks_concurrency.py:61 在上限2竞领后独立查询并写取消 |
| AC-023 | 匹配本期执行与发布责任；归档完整回归留Phase11 | test_tasks.py:92/156；test_execution_reconcile.py:108；preflight独立回归；Linux持久删除实测 |
| AC-024 | 任务隔离与持久会话路径匹配；采用已确认原生Worker方案 | infra/verify_phase9_sandbox.py:25–83 系统边界读写、新round续接、双会话检查；workspace目录持久测试 |
| AC-025 | 匹配；真实图片上传后Worker子进程硬退出，经历待核实后恢复，不另启CLI | reconcile.py:88–145；output/phase9-live-recovery-summary.json:14–18 单次执行、recoveredAfterWorkerExit及observedUncertain均符合预期 |
| Phase9 冻结素材与Skill下载 | 匹配；materials.py:11 校验对象hash，:46–49 再核对冻结Skill checksum和包内容 | test_codex_runner.py:165 损坏Skill不启动；真实MinIO/Skill/图片链report通过 |
| Phase9 argv+stdin、固定版本及限制 | 匹配；process.py:42 参数数组+stdin；runner.py:74 版本精确匹配；service.py:29 冻结timeout/retries；config.py:45 visibility余量 | 真实report config=concurrency1、timeoutSeconds3600、automaticRetries0；CLI 0.153.4 |
| Phase9 图片解码、数量、slot、路径、来源 | 匹配；output_collector.py:19 路径/链接、:77 slot、:102 新图集合、:132 解码；provenance.py:84 native generation关联，:153 内容hash | test_execution_provenance.py:59 仅复制无原生事件拒绝；:74 历史turn不能授权；:89 历史prefix不可修改；真实910×1728 PNG上传成功 |
| Phase9 timeout、退出、不确定对账 | 匹配；process.py:25/49 整组终止与超时；sandbox PID namespace覆盖detached；reconcile.py:98 精确进程核实 | POSIX专项在Linux全套通过；output/phase9-sandbox.log:4 真实namespace停止；真实恢复summary:16–19 |
| Phase9 attempt/操作者/耗时/usage | 匹配；attempts.py:28–42 关联与起止时间，:52 usage主键和NULL；events.py:47 terminal去重；runner.py:38 持久化 | test_execution_records.py:45 去重及SQL NULL；test_codex_runner.py:101 usage实际持久化。启动前意图有process_id=None，Phase13统计须按实际启动事实选取 |
| Phase9 Worker心跳/依赖检查时间 | 本期基础采集匹配；health.py:14 记录CLI/隔离/认证文件存在性及checked_at，:27 五秒循环 | 这里证明配置文件可用性，不等于在线认证有效或Phase13整套健康展示；WorkerHeartbeat记录迁移测试通过 |
| Phase9 迁移和部署边界 | 匹配；migrations/versions/0006_execution.py:15 建4表；config.py:45 执行器互斥；service.example:9 专用身份，:13 control-group终止 | output/phase9-final-regression.log:1–2 Linux PG新建及重复迁移通过；真实原生Worker+Compose数据服务完成单图链 |

### 原三项 HIGH 的复核

1. 历史/输入复制冒充：runner.py:145 和 reconcile.py:132 均强制调用 provenance 校验；只复制新文件名已经不够。独立执行来源专项通过，原 HIGH-1 不再复现。来源记录是CLI日志，验证本轮session/turn/call及实际bytes，不使用最终自然语言自述作为成功依据。
2. 恢复无条件失败：reconcile.py:130–140 已有上传发布路径；:78 在无法证实时维持uncertain。原 HIGH-2 的代码原因已移除；真实来源与恢复组合已由服务器故障注入完成验证，执行计数1、状态待查看。
3. 启动前删除永久占用：runner.py:80–83 已显式end cancelled；独立将DELETE注入版本检查，结果cancelled、attempt=None；原 HIGH-3 不再复现。

## Stage 2：质量与验证真实性检查

- 文件结构：execution新增文件52–167行，reconcile145行、health43行、两个主要烟测脚本147/237行（故障注入后行数略增），均低于300行。职责分离到材料、沙箱、进程、事件、输出、来源与恢复；见各文件模块入口。
- 错误处理：runner.py:153 在进程可能已启动时进入uncertain；reconcile.py:142 捕获失败保留证据而非盲重试。异常文案对外收敛；events.py:70 不持久化上游原始错误到业务字段。
- 安全扫描：对新增执行/worker/attempt文件检索 eval、shell=True、dangerouslySetInnerHTML、innerHTML、前端密钥前缀及常见API key前缀，无匹配。process.py:42 不拼shell；workspace.py:56 clearenv并只挂本任务工作材料；materials.py:46 使用冻结包校验；output_collector.py:19、provenance.py:22 拒绝链接/越界材料。
- 测试真实性：test_execution_reconcile.py:46 将 verify_provenance mock为空，因此该组只可证明事务、取消、幂等、续租与未知状态，不算真实日志恢复证据。主Agent已追加真实CLI→上传→Worker硬退出→未mock恢复并通过。test_codex_runner.py:68 的执行器替身会写session/turn/generation/payload/hash，来源本身另有真实图片链证明，不把合成测试称作实际AI调用。
- UI：本期没有新增页面或布局，frontend最终无diff。独立打开查看本轮真实浏览器截图：仓库根 output/playwright/phase8-tasks.png、phase8-templates-index.png、phase8-detail.png。任务与模板邻居均为同一蓝色主按钮、浅灰背景、白卡片和相同侧栏/标题层级；详情仍明确标注fixture及未开放返工/归档。查询新增sessionId见queries.py:44，未造成新视觉分支。浏览器交互原始日志见output/phase9-final-regression.log:39–44，pageerrors=0；这是截图复核，不宣称reviewer重新启动浏览器跑过全链。
- Spec漂移：四张表、runner、来源校验、恢复和infra均在本期交付范围；未发现额外业务API/页面。文档中“尚未接入执行器”的旧状态应由主Agent在完成证据后同步，不能用旧文档状态代表代码缺失。
- 用户预存改动：`.agents/skills/dev-builder/SKILL.md:53` 增强裁切边界检查；`.codex/hooks.json` 删除Stop注册。只记录，不擅自还原；审查协议仍通过candidate凭据执行。

## 编译与测试原始输出

独立运行Codex runtime Python：`-m compileall -q app migrations`。原始stdout/stderr为空，进程退出码 **0**。

新增三个infra脚本独立编译，进程退出码0，原始输出：

```text
Phase9 infra compile PASS: 3
```

独立运行7组Phase9关键测试（专用output basetemp）：

```text
...................................................s.................... [ 71%]
.s.......................ssss                                            [100%]
95 passed, 6 skipped, 3 warnings in 5.16s
```

6个skip为Windows无法执行的POSIX测试；warning为现有Starlette/httpx弃用两条及本地pytest缓存不可写一条，不是代码编译失败。

独立启动前取消复测，`-p no:cacheprovider`：

```text
delete_preflight_job= cancelled attempt= None
.
1 passed, 2 warnings in 1.19s
```

主Agent提供且本次实际读取的Linux完整回归原始输出（仓库根output/phase9-final-regression.log:1、17、51）：

```text
PASS fresh Linux PG/Redis/MinIO/API/Worker
PASS fresh and repeated migration
245 passed, 2 warnings in 12.85s
PHASE8 INTEGRATION PASS (four isolated volumes)
PASS isolated Compose volumes cleaned
```

前端构建原始输出（output/phase9-frontend-build.log末行）：

```text
✓ built in 41.68s
```

日志同时保留既有login模块动态/静态混合导入的Vite提示；本期未修改该模块。

真实故障恢复的服务器最小字段证据已独立读取，来源为仓库根 `output/phase9-live-recovery-summary.json:3`：

```json
{"status":"passed","imageSize":[910,1728],"execution_attempts":1,"execution_count":1,"image_versions":1,"recoveredAfterWorkerExit":true,"observedUncertain":true,"faultMarkerPresent":true,"cleanupErrors":[]}
```

task为26c97577-8d9a-4cc5-8690-d9cc0b9241ac，round为b70e089e-2357-4a90-a8e4-2e0dbb0fec91，session为01a08901-f78c-7502-a595-78d5e600d258。已复核故障脚本先完成真实CLI与来源校验及上传，再在publish入口os._exit(71)；生产reconcile未mock，恢复后的单次计数与图像下载由脚本断言。第一轮烟测因为旧轮询将uncertain误判终态失败退出，修正验证脚本后第二轮通过；未把第一次失败隐藏为通过。

证据边界：自动审批拒绝原始Worker日志跨环境下载，主Agent采用服务器内只读提取无凭据统计与故障标记布尔值的获准替代方式。reviewer读取的是最小字段转录和验证代码，没有读取被拒绝导出的原始Worker日志，也没有绕过该限制。

## 快照交接

初始candidate之后已知变化为验证脚本加入故障注入，components.d.ts自动生成差异恢复为无diff；业务代码未收到变动通知。已复核新candidate `1afc11a1fbc02d0bbf195c7f137a2fef497320bed83af540bc57ab814465162b` 的脚本：新增分支只在烟测Worker进程替换publish为os._exit(71)，不改实际reconcile；初版completed轮询将公开“失败”态一律退出，会误杀预期uncertain，审查指出后已改为精确识别blockedReason并继续poll。此修正只改变烟测等候逻辑，正常成功与明确失败判定保留。

最终检查曾发现reviewer可见的120个既有临时JSON/PNG不在主Agent快照中；独立比较确认它们全部位于backend/.pytest-tmp-reconcile与backend/.pytest-tmp-reconcile-final，非临时代码差异0。按主Agent明确授权，reviewer验证源父目录backend及目标父目录output后，用原生PowerShell将两个测试产物目录移至仓库根output/phase9-reviewer-test-cleanup。未修改业务代码或门禁规则。随后只读快照检查原始输出：

```json
{"candidate":"1afc11a1fbc02d0bbf195c7f137a2fef497320bed83af540bc57ab814465162b","current":"1afc11a1fbc02d0bbf195c7f137a2fef497320bed83af540bc57ab814465162b","changed":[]}
```

本报告两阶段PASS只适用于上述最终快照及明确的Phase9范围。由主Agent使用review-approve登记；本reviewer未向.needs-review写clean、未自行批准、未提交代码。
