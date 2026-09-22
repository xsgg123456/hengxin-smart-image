# API 换套图正式优化独立审查

日期：2026-09-22。Stage 1 **PASS**；Stage 2 **PASS**。无未解决 HIGH / MEDIUM。最终 candidateId：`e01e12ead14cc83416ec66f98ce557132cb480f01967f9133f1ad5a5e21ce057`。Reviewer 独立执行 review-status，currentId 与该候选相同；两阶段结论仅适用此同一快照。主 Agent 负责 review-approve 登记，不写 clean。

审查范围：`hengxin-smart-image/backend/app/modules/api_image_edits/` 本轮 execution、claims、heartbeat、state、outcomes、control、relay、celery_app、models、versions、presentation、router、files、service、schemas、zip_download；迁移0016及新增/修改专项测试；正式前端 Real 页面、类型、client、validate、use-records、item-command、operations 测试。既有 Demo 承接 `docs/API-IMAGE-OPTIMIZATION-PREVIEW-REVIEW.md` 和 `docs/API-IMAGE-VERSION-PREVIEW-REVIEW.md`，不重复批准历史部署。

依据：Product-Spec.md:4、DEV-PLAN.md:4、Design-Brief.md:8 与 `docs/API-IMAGE-OPTIMIZATION-IMPLEMENTATION.md:7` 四项步骤和全部契约；视觉承接两份预览计划。B/表示 `hengxin-smart-image/backend/app/modules/api_image_edits/`，T/表示 `hengxin-smart-image/backend/tests/`，F/表示 `hengxin-smart-image/frontend/src/views/hengxin/api-image-edits/`，E/表示 `output/api-optimization-preview/`。

## Stage 1：Spec Compliance

| 要求 | 判定及证据 |
|---|---|
| 每批最多10张、10+1、当前批结束后下一批 | 修复后完整实现。B/claims.py:42 全通道读取待处理项，:54 有效租约上限10，:60 固定在途任务与批次；B/execution.py:94 独立Session线程池。T/test_api_image_parallel_pg.py:38、:55 实际PG竞争16个领取者及10个同步调用屏障；:85、:102 覆盖较早图片/较老任务修改不得插入在途批次。 |
| 初调外3次1/2/4退避、失败单图手动继续 | 完整实现。B/outcomes.py:27–35，B/versions.py:97 单项重试，B/service.py:61 整任务仅重试失败项；T/test_api_image_parallel.py:37 实际逐次计算等待时间和四次调用。返回未知网络异常按用户授权有限重试，B/execution.py:118–126；密钥/额度错误暂停通道，B/relay.py:129、B/outcomes.py:36。 |
| 租约、心跳、进程丢失核实、迟到隔离 | 完整实现。B/claims.py:47、:86–95 到期标 uncertain 并拒旧token，B/heartbeat.py:11 独立续租，B/control.py:21 明确确认旧执行停止。T/test_api_image_execution_pg.py:93 覆盖到期阻塞及迟到结果；T/test_api_image_execution.py:140 覆盖管理权限与人工确认。B/service.py:89 检查实际running/uncertain子项，防父状态失准绕过。 |
| 返回结果后只重收图，不重复付费生成 | 完整实现。B/execution.py:39、:103、:128，B/outcomes.py:42 保存私有响应及 collecting 状态；T/test_api_image_execution.py:118、:181 验证下载/存储失败和手动重试始终只调用上游一次。 |
| 记录页紧凑52px缩略图、操作人、静默刷新 | 完整实现。F/RealRecords.vue:10、:13、:59，F/use-records.ts:25–44 静默请求不启动loading、不清旧数据；B/presentation.py:45 创建人。E/real-flow.cjs 实际HTTP浏览器等待轮询后断言输入、滚动位置保持、无loading mask。 |
| 当前结果+可选一张标注+文字，至少一种，无内置提示词 | 完整实现。B/schemas.py:26–36；B/versions.py:24–29 冻结输入、:82 CAS、:84 后端JPG/PNG10MiB验证；B/relay.py:97 省略空附件。F/RealRevisionDialog.vue:4、:59–89 预览/移除/校验/提交。T/test_api_image_revision_guards.py:39、:51 验证格式限制及纯标注。 |
| 修改失败保留旧结果、重试沿用基础图、只影响单图 | 完整实现。B/versions.py:89–94 保存基础图，B/outcomes.py:18 不覆盖result_id；T/test_api_image_revision_execution.py:13 用实际JPEG结果区别原PNG，四次失败断言旧结果、完整历史及邻居保持，再重试验证冻结图片字节和基础版本。 |
| 不可变历史、递增编号、当前指针、恢复与下载 | 完整实现。B/versions.py:12 兼容旧V1，:32 最大编号+1，:110 恢复不生成；B/models.py:113 ApiVersion及唯一约束。F/RealVersionDialog.vue:7、:16、:67–90 列表/对比/选中版下载/恢复确认；F/RealTaskDetail.vue:27 当前Vn。T/test_api_image_versions.py:33 覆盖恢复V1后再修改V3及历史引用。 |
| 修改中/失败待重试/打包中不可切当前版 | 完整实现。B/versions.py:117 要求 succeeded；F/RealVersionDialog.vue:61、:77、:84 确认前后检查；F/RealTaskDetail.vue:40–41 传打包锁。T/test_api_image_versions.py:47、:62 拒绝进行中/失败恢复。 |
| 整套成功ZIP，按顺序使用选定当前版、错误不交付残缺包 | 完整实现。B/zip_download.py:16–25 短事务捕获全部当前结果、:28–40 完整构建后响应；B/files.py:64–75 核验字节数量和SHA256；T/test_api_image_versions.py:114、:151 验证权限、存储失败503、真实解包字节及读取中切换版本仍使用原快照。 |
| 幂等、权限、引用保护、旧数据迁移 | 完整实现。B/state.py:16 通道锁，B/versions.py:75/99/111 原键查询先于状态校验，B/service.py:27 负载冲突409；B/router.py:23 shared_resources、:24管理权限；B/files.py:49–59 当前/历史/标注引用保护。migration0016:13 升级、:64 兼容在途租约；T/test_api_image_versions_pg.py:32 双次真实PG迁移、:71 四并发CAS。锁顺序为通道→任务/项→文件，删除文件不逆向获取任务锁。 |
| 前端不确定请求恢复、防重复提交、真实契约 | 完整实现。F/item-command.ts:7–34 原键与冻结输入持久化、busy保护；F/use-records.ts:5–16 任务重试同样保留；frontend/tests/api-image-operations.test.ts:27 覆盖断网、重挂载、409后仍保留原未知请求。E/real-flow.cjs 在服务端已受理后丢响应，浏览器再次提交同键，断言只新增一版。 |
| UI沿用预览与现有框架、双宽度 | 完整实现。已亲自查看 E/real-revision-1440.png、real-revision-1280.png、real-history-1280.png；按钮和完整对比区未裁切。F/RealTaskDetail.vue:99 三列，F/RealVersionDialog.vue:96 为190px侧栏/24px间距，:109 双图/16px间距，:111 图高320px，与批准预览一致。 |

部分实现/未实现：修复复核后未发现。Spec漂移：未发现本轮额外页面或业务能力；本地fakeRelay仅验证系统链路，不代表真实上游生成效果。

### 本轮发现并修复

初始 candidateId `3285e8dcc1483939e57faf3c066f20d8cb6b0ba7b15915e2f072d2a0a1d617cc` Stage 1 FAIL，未进入 Stage 2：

1. HIGH：原 claims.py:57 只按最早活跃位置选批次。第二批10项在途时修改第一批成功项，可领第11项。跨任务同样会绕过容量。独立最小复现 E/reviewer-repro.py 原始输出 `CAP revise= 202 extra_claim= True running= 11`。修复全通道租约容量并固定在途任务/批次后，E/reviewer-recheck.py 输出 `CAP revise= 202 extra_claim= False running= 10`。
2. HIGH：原 versions.py:58 无条件设父任务queued，service.py:88 仅看父状态。修改成功兄弟项后可删除仍running/uncertain的任务，绕过旧执行核实。原始独立输出 `DELETE revise= 202 task= queued items= ['queued', 'running'] delete= 200`。修复按全部项汇总且删除检查真实子状态，复核输出 `DELETE revise= 202 task= running items= ['queued', 'running'] delete= 409`。

审查中还新增服务端标注格式/大小防线和真实修改失败回归。中间快照 f46a871ce9ee200604de7494bc0d28373000a3872b23f304051e0ff0b1a44163 因新增测试再次变化；原编号不可作为最终批准凭据。

## Stage 2：Code Quality

在上述HIGH修复并独立复核后执行。

| 检查 | 结论及证据 |
|---|---|
| 职责、类型、文件大小 | 通过。版本/ZIP/执行状态独立模块，新增及本轮正式实现文件均不超过300行；前端显式ApiVersion/ApiRevision/ItemCommand类型，限定正式实现扫描无any。独立vue-tsc退出0。 |
| 错误处理与资源释放 | 通过。B/zip_download.py:32 失败关闭缓冲区，B/files.py:77 流finally释放；B/execution.py:56 先staging再外部写、最后租约校验发布，失败仅留下不可见staging；F/item-command.ts:17 保留未知请求，前后端不直接展示上游私有异常。 |
| 测试真实性 | 通过。PG并发使用真实数据库行锁和Barrier，不以SQLite模拟并发；版本执行回归使用不同原图/结果字节；ZIP检查实际内容；浏览器真实HTTP仅替换付费Relay并故意丢失受理响应，不能把fakeRelay当真实模型验收。初版测试未覆盖的两个并发组合已新增回归。 |
| 安全扫描 | 通过。限定模块扫描无eval/innerHTML/前端SECRET或KEY/硬编码sk密钥/用户绝对路径。B/router.py:23–24统一权限，B/versions.py:84文件锁与类型限制，B/files.py:56历史引用保护；B/presentation.py:43–65不返回私有result_url/result_bytes。沿用B/downloads.py:16 HTTPS允许域+公网IP固定，无凭证与重定向。 |
| 真实视觉对比 | 通过。亲自打开邻居基准E/baseline.png与三张正式截图，蓝色按钮、白色圆角卡片/弹框、灰色说明、图片查看器、侧栏页头均保持既有风格。查看的是主Agent实测截图，不声明本人操作浏览器。 |

## 验证原始输出与边界

Reviewer独立：`node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`，exit_code=0，stdout/stderr为空。专项pytest原始末尾：

```text
14 passed, 2 warnings in 3.62s
```

主Agent日志已实际读取：

```text
# E/backend-full.log（修复前Windows全套）
820 passed, 158 skipped, 15 warnings in 54.35s
# E/backend-execution.log
42 passed, 2 warnings in 5.23s
# E/concurrency-fix.log（修复后，含真实PG）
23 passed, 2 warnings in 6.75s
# E/formal-frontend-tests.log
ℹ tests 153
ℹ pass 153
ℹ fail 0
ℹ skipped 0
# E/formal-build.log
✓ built in 39.22s
```

E/real-evidence.json 为真实HTTP、隔离DB、fakeRelay，断言同键重放/仅新增一版/标注保存/历史恢复/ZIP/静默轮询均true，pageErrors=[]。未测试真实付费上游效果或生产发布。

Linux首轮 `1 failed, 922 passed, 64 skipped, 15 warnings in 91.44s`，失败为 T/test_contracts.py:95 缺少 `/contracts-types` 前端源文件挂载，不能记全套通过。随后补齐挂载，Reviewer 已读取重跑日志 E/backend-linux.log，原始输出如下；最终新增修改执行回归 E/revision-execution.log 为 `1 passed, 2 warnings in 1.70s`。最终快照新增测试只推进目标项等待时间、不修改邻居，已复核。`90db79fc...` 中间快照及 `f46a871c...` 均不承接最终批准。

```text
924 passed, 64 skipped, 15 warnings in 89.70s (0:01:29)
```

跳过项是旧模块独立环境/平台条件用例，本次API专项PG证据见 concurrency-fix.log；不宣称跳过项已验证。


Reviewer 最终独立打开实际浏览器下载的 E/real-restored.zip，验证11文件及所有条目CRC，原始输出：REAL_RESTORED_ZIP_11_CRC_PASS。
