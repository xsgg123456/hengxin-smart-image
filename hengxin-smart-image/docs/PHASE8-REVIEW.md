# Phase 8 最终独立审查

2026-09-09。依据根目录 Product-Spec.md REQ-003/004、第 9.2 节、DEV-PLAN.md Phase 8、docs/PHASE8-PLAN.md 与 API-CONTRACT.md。执行 code-review skill；只审查，不修业务代码、不提交。路径除特别注明外相对 hengxin-smart-image/。

**最终结论：Stage 1、Stage 2 均通过；0 个未关闭 HIGH / MEDIUM。** F8-001 已由真实浏览器双401恢复链路关闭；后端三项 MEDIUM 已修复并独立复核。最终144项PG测试、真实双Worker/Redis/MinIO故障链路、hard-kill待核实及测试卷清理全部完成。此前故障场景等待running超时源于验证前置未清空前序活跃任务；脚本补终态前置后重验通过，没有通过释放uncertain占用掩盖问题。详见 docs/PHASE8-BACKEND-REVIEW.md 与 PHASE8-INTEGRATION.md。

## Stage 1：逐项 Spec Compliance

| 条目 | 判定、代码与验证证据 |
|---|---|
| REQ-003 三入口、名称必填/SKU可选、文字有意见且无需模板 | 实现匹配。backend/app/modules/tasks/snapshots.py:9、28、37；frontend/src/views/hengxin/use-create-task.ts:28、79、86；CreateTask.vue:7、26。三模式 API 及边界用例纳入最终 144 项 PG pytest，浏览器三入口真实POST202已通过（output/phase8-integration.log）。 |
| 素材及模板每组1–20个ready图片 | 实现匹配。snapshots.py:14、18、44 服务端读取可信 fileId；frontend/src/views/hengxin/use-image-upload.ts:64、87 校验解码、类型、10MiB及20张，未上传完成阻止提交（use-create-task.ts:29）。已保存 Picture 才进入草稿，不保存需继续上传的临时 URL。 |
| 冻结模板/Skill/素材/意见与输出槽数量 | 实现匹配。backend/app/modules/tasks/service.py:45、53、55、57；snapshots.py:38、53；tests/test_task_snapshots_results.py:13 真实 PUT/DELETE 模板后重放、执行，完整旧 snapshot/version/两槽仍在；test_tasks.py:49 禁用 Skill 后原回执重放。 |
| 9.2.2 先鉴权，同操作者同键同内容原202、异内容409 | 实现匹配。backend/app/modules/tasks/service.py:38–45；idempotency.py:15–28 参数化 PG advisory 事务锁；tests/test_tasks_concurrency.py:74 独立连接争用；集成并发 HTTP 断言一组 task/round/request/outbox。 |
| 原子202/outbox，不等待Worker或Redis | 实现匹配。service.py:21–35、46–60 单事务最终 commit；router.py:17 返回202。集成在受控作业仍运行时取得202，Redis停机受理后恢复，无丢任务。 |
| 9.2.1 同任务最多一个未结束轮次 | 实现匹配。models.py:29 活跃状态部分唯一索引包含 uncertain；service.py:77–96 任务行锁下检查，内部轮次服务测试不同操作者争用。用户返工HTTP按Phase10边界未开放。 |
| 9.2.3 多Worker单次认领、终态不重启 | 实现匹配。claims.py:10–24 锁序、52–73 短事务；outbox.py:25 排除非queued生成重派。集成独立双Worker在限额2下重复消息 execution_count=1，另一个任务同时运行，未用全局1掩盖竞争。 |
| 全局并发默认1、可配置1–10 | 实现匹配。backend/app/core/config.py:15；claims.py:63–73 计数与更新在同一 gate 锁内，uncertain计占用。真实 limit1 排队释放、limit2 并行证据已读取。 |
| 9.2.4 旧token/旧轮次/过期/取消不发布，版本原子切换 | 实现匹配。claims.py:76–79；results.py:9–31 每次发布复核权属、当前轮次、取消及租约；tests/test_task_snapshots_results.py:38 有效第一输出已flush、第二输出不存在，全部 ImageVersion/current 指针回滚，Job/Round仍running且outbox未完成。 |
| 9.2.5 失联/租约过期先待核实、不接管 | 实现匹配，最终hard-kill已验证。claims.py:35–49、57–66；queries.py:72；test_tasks.py:112、156 覆盖失效token与占用。不得把租约过期当作CLI退出证明。 |
| 9.2.6 持久删除取消、排队不启动、运行/上传后不复活 | 实现匹配。cancellations.py:10–28、claims.py:82–97；test_tasks.py:91 上传后回调删除；集成运行/排队删除、Worker重启不复活。fixture无外部CLI进程，真实停止及核实留Phase9。 |
| REQ-004 全员列表/详情/删除、实际操作者审计 | 实现匹配。queries.py:23、30、84；cancellations.py:27；tests/test_tasks.py:138 四角色参数化及容器第二可信身份跨owner GET/DELETE。历史文件保留，不将页面关闭等同DELETE。 |
| 名称/编号/SKU搜索、类型/状态分页、全工作区统计 | 修复匹配。queries.py:87–111 在搜索之前取stats，再OR搜索名称/SKU/规范化编号，排序分页；tests/test_task_queries.py:6 覆盖各搜索、过滤、空结果不缩统计及逻辑删除。原后端两项MEDIUM关闭。 |
| 状态独立查询、3/10秒轮询、离页停止 | 实现匹配。frontend/src/views/hengxin/task-state.ts:3；components/use-task-list.ts:11、28、35；components/use-task-detail.ts:10、25、29、34；测试验证延迟策略，静态复核离页清timer并使迟到请求失效。真实离页后台继续另由浏览器集成验证。 |
| 图片结果实际可读、版本及下载 | 实现匹配。backend/app/execution/fixture_runner.py:65–78 读取冻结原图、上传独立结果；scripts/phase8/api_checks.py:102 检查独立fileId、HTTP原bytes与解码。frontend/components/ResultCard.vue:3、TaskDetail.vue:89 使用当前版本下载，不能仅以URL存在证明可读。浏览器ZIP已解包核对原始fixture bytes，日志为 PASS browser ZIP contains exact readable fixture image。 |
| required executionControl、fixture标记、真实引导 | 实现匹配。frontend/src/types/hengxin.ts:138、api/hengxin/validate.ts:65 强制字段；task-state.ts:4–10、components/TaskDetail.vue:8–16、50–60 服务端能力与原因共同禁用；归档第80行再次阻断。fixture告警截图已独立查看。 |
| test专用fixture、dev新请求503、无伪造CLI/usage | 实现匹配。backend/app/core/config.py:14、36；service.py:14–17、41–45 原回执优先重放；queries.py:44 返回sessionId=null、49来源fixture；test_foundation.py:89、test_tasks.py:76 覆盖默认关闭及生产拒绝。 |
| 前端原键/原快照、401卸载重建、异用户隔离 | 代码及51项前端测试匹配；F8-001真实浏览器双401链路已通过。详见下一节。 |
| 已受理读取失败保留回执，显式另建才释放 | 代码与组件测试匹配。task-submission.ts:16–29 捕获原状态保存回执；40–43只有accepted且不pending才另建；CreateTask.vue:39–41明确查看/另建。真实GET401恢复已通过；scripts/phase8/auth-recovery.js:56、66–72检查原键原体、无额外POST、数据库仅1任务。 |

### F8-001 修复核对

- 可信身份来源：frontend/src/api/auth.ts:7–11 从 `/auth/me` 取得active身份，main.ts:72–82成功后写user store；use-create-task.ts:14要求isLogin及userId。URL role不参与真实会话索引。
- 跨卸载状态：task-creation-session.ts:11–20 模块Map按userId/mode/templateQuery隔离；身份为空只访问空状态，不能重放原用户请求。task-submission.ts:16捕获原会话，迟到响应只写该会话，不能写进另一用户。
- 请求保护：task-submission.ts:18阻止同会话pending并行；21–24不确定时禁止新内容替换原快照/键；31使首次401仍为uncertain；use-create-task.ts:17–19在await获取服务后复核身份，90在存活、身份、会话与路由均一致时才导航。
- 实际卸载路径：main.ts:43–51清登录并让App.vue:10移除RouterView；auth/dingtalk-login.vue:92–95重连后router.replace保留内存和业务入口。真实钉钉跳转、浏览器硬刷新后的持久草稿不属于本阶段交付，不能据此宣称跨整页恢复。
- 新增 tests/task-creation-session.test.ts:25、53、70、94 使用真实Vue renderer setup/unmount，覆盖首次401、同用户草稿、同键原体、已受理跨重建、显式另建换键、身份/入口隔离与迟到回执。它不是浏览器401事件测试，故额外要求 scripts/phase8/auth-recovery.js 真实POST落库后遮蔽为401、重连、原键原体重放、GET401回执恢复。

### 未实现与范围漂移

本期范围内未发现缺失的业务代码，必需集成证据已取得。9.2.1/6涉及真实CLI执行环境隔离、进程退出核实，9.1会话恢复及AC-004/015/024按DEV-PLAN Phase9实测；用户返工/重试HTTP为Phase10，归档为Phase11，钉钉认证为Phase12。前端明确禁用后续功能。未发现本期新增越界业务页面/API；此前Phase7模板历史与Skill默认绑定不是本期scope creep。

## Stage 2：Code Quality

Stage1修复与必需集成证据均通过，Stage2结果如下。

- 结构与类型：本期任务后端文件1–111行，前端task-creation-session 30行、task-submission 46行、task-state 11行、use-create-task 97行；职责按受理状态、会话、UI请求及服务端锁/发布拆分。frontend DTO字段必需并有运行期guard，独立vue-tsc通过。未将既有大型框架文件当作本期新增问题。
- 安全：针对上述任务模块及fixture扫描eval、dangerouslySetInnerHTML、innerHTML、前端KEY/SECRET/TOKEN、硬编码服务密钥、shell=True及any，未命中。backend/idempotency.py:21使用绑定SQL参数；queries.py:95使用autoescape；fixture_runner.py:55从可信FileRecord读取存储对象，无客户端URL任意请求。
- 测试真实性：真实PG并发证据来自独立连接和两个Worker；低层锁测试手建ready文件不代表可读图片，实际原bytes另有MinIO/HTTP断言。冻结/输出失败回滚新增测试直接触发API与事务异常，不只断言纯函数。前端renderer确实卸载组件，真实401事件另由集成补足。
- 视觉：已独立读取真实渲染截图 `../../output/playwright/phase7-neighbor.png` 与 `phase8-detail.png`，沿用浅卡片、蓝色操作、圆角与侧栏；详情fixture橙色告警、灰色禁用理由和下载按钮没有重叠。对应 Design-Brief.md:13 的继承准则与 frontend/src/views/hengxin/prototype.css:7、22–26。已另行独立检查本轮 phase8-wallpaper/product/text、phase8-templates-index、phase8-tasks、phase8-auth-accepted.png：1024px视口下60字名称、80字SKU、意见及分行任务ID均在卡片内，查看/另建按钮无重叠；不声称所有视口均验证。

## 独立测试与编译原始输出

最终前端全量测试命令：`D:/Apps/nodejs/node.exe node_modules/tsx/dist/cli.mjs --test tests/*.test.ts`。沙箱首次Node读取系统用户信息失败，正常权限重跑成功；这属于执行环境失败，不是代码测试失败。

```text
SystemError [ERR_SYSTEM_ERROR]: A system error occurred: uv_os_get_passwd returned ENOMEM (not enough memory)

ℹ tests 51
ℹ suites 0
ℹ pass 51
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1721.8898
exit_code: 0
```

独立类型检查命令：`D:/Apps/nodejs/node.exe node_modules/vue-tsc/bin/vue-tsc.js --noEmit`。

```text
exit_code: 0
output: ""
```

独立最终构建命令：`D:/Apps/nodejs/node.exe node_modules/vite/bin/vite.js build`。完整原始输出在 `../../output/phase8-frontend-final-build.log`；不是此前47项版本的phase8-build.log。

```text
vite v7.1.7 building for production...
✓ 3303 modules transformed.
(!) D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/views/auth/dingtalk-login.vue is dynamically imported by D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/core/ComponentLoader.ts, D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/routes/staticRoutes.ts but also statically imported by D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/App.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
✓ built in 35.73s
exit_code: 0
```

该警告只说明登录页同时静态/动态引用，构建仍成功；未发现由此导致的功能失败。后端独立编译及3项定向复核原始输出见 docs/PHASE8-BACKEND-REVIEW.md；最终144项PG与Phase7回归及浏览器/故障原始证据见下。

## 最终集成与回归证据

读取最终 `../../output/phase8-integration.log:15`、37–50；不是本审查者再次启动容器。该轮代码已包含后端搜索/统计及冻结/回滚测试，`infra/verify_phase8.py:121–126` 对144项pytest明确禁止skip并执行后端compileall。独立查看日志及故障脚本，不仅采信PASS字符串：`scripts/phase8/api_checks.py:161–189` 先等前序轮次终态，确认lost作业running后SIGKILL两个Worker，再使该真实认领租约到期；恢复Worker及重投6次后，execution_count仍1、版本0、uncertain持续占用、第二任务排队，两操作能力均false。

```text
144 passed, 2 warnings in 10.02s
PASS concurrent same-key 202, different-content 409, limit=1, repeated messages single start/results
PASS Redis outage accepted task recovered
PASS three entry API snapshots, real MinIO bytes, fixture provenance and no fake CLI session
PASS independent duplicate claim check with global limit 2
PASS two distinct tasks running concurrently across two workers
PASS duplicate execution claim under global limit2, distinct peer concurrently running
PASS durable queued/running deletion, no late versions, restart no resurrection
PASS cross-owner read/delete with second trusted identity and actual operator audit
"PHASE8 BROWSER PASS: three real submissions, idempotency headers, background completion after leaving page, fixture label, executionControl, download, delete; pageerrors=0"
PASS browser ZIP contains exact readable fixture image
"PHASE8 AUTH RECOVERY PASS: real accepted POST masked by401, same identity reconnect retains60char draft, same key/body replay, accepted GET401 retains receipt, view original creates no extra task"
"PHASE8 RECOVERY VISUAL PASS: long draft fields and accepted action scrolled into viewport"
PASS all previous browser and API tasks terminal before worker fault scenario
PASS worker entered execution before hard kill
PASS hard killed worker lease transitions to uncertain
PASS hard SIGKILL plus expired lease remains uncertain, duplicate messages do not restart, slot retained
PHASE8 INTEGRATION PASS (four isolated volumes)
PASS isolated Compose volumes cleaned
```

Phase7既有业务回归读取 `../../output/phase8-phase7-regression.log`；141项pytest版本先于后续新增3项测试，不能替代最终144项证据。Skill安装、模板版本/默认绑定/权限及持久重启通过，原始尾段：

```text
PASS restart persistence
PASS installed files and frozen bindings survive restart; disabled explicit never falls back
PASS second isolated user
PASS non-admin 403, shared edit/disable/delete, actual operator audit and retained history
PHASE7 INTEGRATION PASS (four isolated volumes)
PASS isolated Compose volumes cleaned
```

审查范围结论为Phase8工程实现与验证通过；真实CLI、会话隔离、实际生成能力及用户业务验收不由fixture替代。已核对 Product-Spec.md:7、DEV-PLAN.md:4、123、Design-Brief.md:7 及 VALIDATION/INTEGRATION均为技术验证通过、待用户验收；Product-Spec.md:341的重复旧状态已通知主Agent在交付收尾统一，不属于代码缺陷。
