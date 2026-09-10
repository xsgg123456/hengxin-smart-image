# Phase 10 修复后独立复审

- 审查角色：fresh code-reviewer；使用 `.agents/skills/code-review/SKILL.md`，未修改业务代码、未提交、未登记批准。
- 最终 candidateId：`2883e1a85287956dbf032d967a3de6bb04ee513d0655912ad4848c8daa3bd60f`。
- 派发 candidateId：`bb3071bc763fb5ed01d966327d60a35af802bb1ef430fe07e67d7336cf7dcdac`。审查期间仅 `scripts/phase10/revisions.js:65` 改为点击 `.el-select` 可见外壳；已读该行及上下文，避免内部 input 被选中文案遮挡。结论仅绑定最终快照，不能使用前次失败报告批准代码。
- 中间集成快照为 `b4e994f5ead84d12ebe115904920f1920975c3a5e4818dbbff167472d1d036cf`。集成后 Reviewer 的 review-status 发现生成文件导致 currentId 暂变为 `403477e8e01ecd53da0aff89ac2a0843c39afd591b9113e17fd3f3848c2be371`，立即通知主 Agent，没有批准该快照。主 Agent 恢复 `frontend/src/types/import/components.d.ts` 完整声明（Reviewer 确认与 HEAD 无差异），把测试时生成 `.pnpm-store` 移入输出目录；另清掉 `frontend/src/api/hengxin/http.ts`、`frontend/src/api/revisions.ts`、`frontend/src/types/hengxin.ts` 各一个末尾空行。Reviewer 重新读这三文件差异，业务变更仍仅为已审稳定请求键/sourceRoundId，末尾空白不影响类型或运行；并重新执行只读 review-status，currentId 确认为最终 `2883e1…`。两阶段结论在复核这些收尾差异后绑定最终快照，测试和构建来自相同业务代码。
- 范围：完整 Phase 10，包括返工 API、幂等和资格、任务状态聚合、CLI 当前图材料/部分结果/恢复发布、Worker 执行器分流、前端请求会话和原详情、对应测试、Phase 8/10 验收脚本。Phase 9 已批准基线为前置；用户预存 `.agents/skills/dev-builder/SKILL.md`、`.codex/hooks.json` 不是本期产品改动，未回退。
- 依据：Product-Spec REQ-005、第 9.1–9.2 节、AC-006/007/010/011/015/016/021；DEV-PLAN Phase 10；Design-Brief；PHASE10-PLAN/VALIDATION/REVIEW。
- 最终结论：**Stage 1 PASS；Stage 2 PASS。** 本期范围内无未解决 HIGH/MEDIUM。主 Agent 可对上述最终 candidate 使用 review-approve 登记；本报告本身不写 clean、不代登记。

## Stage 1：Spec Compliance

| 需求 | 结论与代码证据 | 验证证据 |
|---|---|---|
| REQ-005 整套预览、单图查看、两种意见 | 完整实现。`frontend/src/views/hengxin/components/TaskDetail.vue:8`、`:20`、`:24`；`ResultCard.vue:3` 提供大图预览，`:6` 保留版本选择。 | 最终真实浏览器整套/单图意见、历史图可读和记录通过；截图实际查看，组件和调用链逐项核对。 |
| 指定 Skill、目标、素材、本轮意见 | 完整实现。`backend/app/execution/materials.py:23` 冻结原输入，`:43` 映射 taskSlot/currentPath/currentVersion，`:59` 检查冻结 Skill checksum；`codex_runner.py:139` 传本轮意见。 | `test_revision_execution.py:51` 检查新轮次目录当前图字节与 resume 参数。 |
| 单图不得更新其他位置；成功才切换，失败保留历史 | 完整实现。`backend/app/modules/tasks/results.py:16` 选择目标，`:20` 失败仅记 error，`:32` 成功才切当前版本。 | 独立 40 项通过；`test_revisions.py:36`、`test_partial_results.py:45`；真实 MinIO 对象键/hash验收见最终集成。 |
| 旧 HIGH：单轮成功不等于完整整套 | 已修复。`backend/app/modules/tasks/queries.py:47` 汇总所有 slot；`:90` ready/partial 共用整套完整性谓词，`:107` 状态筛选复用该谓词；轮次保留本轮事实。 | `test_partial_results.py:72` 从初始 partial，先返工成功位置仍 partial，再修缺图位置才 ready；详情、progress、部分失败/error/待查看筛选、ready 计数均断言。独立执行通过。 |
| 互斥覆盖首次、整套、单图、重试及跨用户 | 完整实现。`revisions/service.py:13` 检查所有 ACTIVE，`tasks/service.py:82` 按任务行锁，`:91` 锁内重新算资格；实际操作者在 `:27` 写入。 | `test_revisions.py:78` 覆盖 queued/running/collecting/cancelling/uncertain；`:105` 四角色跨 owner。PG 并发 `test_revisions_concurrency.py:36` 两用户新返工/重试只能一个 202。 |
| 重复请求原回执、同键异内容拒绝；先鉴权 | 完整实现。`tasks/service.py:74` authorize，`:78` replay，`:87` 行锁后再次 replay；`tasks/idempotency.py:16` PG advisory lock 与持久请求摘要。 | `test_revisions.py:36`、`:105`；PG 同键并发 `test_revisions_concurrency.py:59`；无鉴权与禁用身份不能利用回放访问。 |
| 重试冻结当前失败来源、范围与意见 | 完整实现。`tasks/service.py:94`–`:107` 要求 canRetry/sourceRoundId/原意见与范围；`contracts/business.py:211` UUID、非负严格整数和长度校验。 | `test_revisions.py:89` 过期来源/改内容/目标拒绝；`:140` 初始空意见合法重放；缺幂等键/错误slot用例通过。 |
| 9.1 同任务原会话、每轮新进程、无替代会话 | 完整实现。`codex_runner.py:86` 检查已存会话，`:107` 材料缺失拒绝，`:130` 明确原 ID resume，`:46` 拒绝完成事件换 ID。 | `test_revision_execution.py:51` 检查同 ID 和新目录；`:83` 验证已知未 spawn 失败的安全初始化重试。实际 AI 改图效果按 Phase 14，未冒充本期已验收。 |
| 安全初始 retry、原执行器保持 | 完整实现。`revisions/service.py:8` 所有历史 attempt finished 且 PID 空才允许缺 ID 重试；`:19` 检查原执行器可用性；`worker/tasks.py:47` 按任务冻结来源分流。 | `test_revisions.py:150` finished/starting/uncertain/PID 组合；`test_revision_execution.py:108` 全局配置变化仍走原 fixture。 |
| 9.2 失效执行、删除、取消不得发布 | 完整实现。`tasks/results.py:12` 使用统一发布屏障；`tasks/claims.py:76` 检查删除、当前轮次、取消、token、租约；恢复同样走 publish_results。 | 专项二次发布拒绝；最终 Linux 全量包含既有删除、旧 token、认领、恢复回归，287 passed。 |
| 部分结果严格位置和来源、恢复不重启 | 完整实现。`output_collector.py:65` 完整清单、互斥 file/error、slot 唯一；`:114` 历史不变和未映射文件拒绝；`codex_runner.py:148` 成功图 provenance；`worker/reconcile.py:130` 同规收集和发布。 | `test_partial_results.py:19`、`:37`；`test_revision_execution.py:19` 使用真实 provenance parser，部分恢复只发布一次、execution_count 保持 1。 |
| 异步 202、离页后台执行、无审批 | 完整实现。`revisions/router.py:11` 202；`tasks/service.py:112` 轮次/请求/Outbox 同事务；无主管审批路径。 | 最终隔离 API/浏览器通过异步回执、离页继续和两类返工；四角色共享路由与操作者记录已独立验证。 |
| 草稿按身份、任务、目标保留，冲突不丢意见 | 完整实现。`revision-session.ts:12` 身份/任务 map，`:24` slot 草稿；`TaskDetail.vue:82` 拒绝迟到响应污染新任务/身份。 | `frontend/tests/revision-session.test.ts:38` 双击、切任务与身份、迟到回执；`:81` 冲突保留。前端全套 56 passed。 |
| unknown/401 重挂只重放原键和原内容 | 完整实现。`revision-session.ts:46` 禁换 unknown 内容，`:50` 捕获请求快照，`:67` 原键重放；`TaskDetail.vue:51` 再检异步服务获取期间身份。 | `revision-session.test.ts:59` 使用 Vue mount/unmount 模拟 401 重挂；`:103` 不确定时改目标与 retry 来源仍冻结。 |
| 已受理回执直到终态、GET失败不二次POST | 完整实现。`revision-session.ts:27` observe终态，`:33` 显式 begin 清回执，`:44` 直接返回已受理结果；`TaskDetail.vue:86` 独立刷新详情。 | `revision-session.test.ts:81` 无 observe 时重复调用 posts 不增加，终态后显式开启才新 key。 |

部分实现/未实现：本期范围内未发现。归档真实接口及实际 Skill 图片效果明确分别属于 Phase 11/14，不计成本期缺陷。`TaskDetail.vue:9` 明示归档后续开放，`:11` fixture 警告不虚称 AI 生成。

## Stage 2：Code Quality

- 结构与类型：核对文件长度，新增/本期核心文件 14–227 行，`infra/verify_phase8.py` 210 行；`TaskDetail.vue` 113 行，`revision-session.ts` 71 行。职责分为资格、事务、查询、输出校验、请求状态；新增前端未使用 any。证据：`revisions/service.py:1`、`tasks/service.py:72`、`revision-session.ts:3`。
- 测试真实性：不仅纯函数。`test_revisions_concurrency.py:36` 使用独立 PG 连接、HTTP 和两个身份；`test_partial_results.py:72` 从真实受理/认领/发布链制造初始缺图并检查列表；`test_revision_execution.py:19` 没有替换来源验证函数；前端 `revision-session.test.ts:59` 实际 Vue 挂卸载。CLI execute 为受控替身，不能据此承诺实际生成质量。
- 安全扫描：对返工、执行、任务、详情、请求会话与 Phase10 脚本搜索 eval、dangerouslySetInnerHTML、innerHTML、前端 KEY/SECRET/TOKEN、sk-ant/sk-proj、用户目录及硬编码 password，未命中新增问题。`tasks/idempotency.py:21` 参数化 SQL；`TaskDetail.vue:22` Vue 文本插值呈现用户意见；`output_collector.py:19` 路径/链接检查、`:114` 历史保护；`codex_runner.py:134` argv 数组而非拼接 shell。
- Spec 漂移：新增 rounds API 为 REQ-005 必需；没有新增审批、业务页面、模型选择、会话切换或本期归档后端。`revisions/router.py:11`、`TaskDetail.vue:8`。
- 视觉 PASS：实际打开查看 `output/playwright/phase10-revisions.png`，与 `phase8-detail.png`、`phase8-tasks.png` 邻居渲染比对；蓝色描边操作、灰文字、白卡片、版本下拉和警示条一致。新图为 1024px 宽、已滚动的抽屉，顶部元信息因滚动裁切，不能误判为固定遮挡；两张图卡及 v2/v3 当前版本可见。白色图片来自明确标记的 2px fixture，脚本已验证 naturalWidth 与历史文件 ID，不当作真实 AI 成图。代码数值核对：`TaskDetail.vue:2` 82% 抽屉，`:24` 520px 原意见框；`prototype.css:26` 原 18px 控件间距，`:30` 四列结果网格/18px间距/10px内边距/12px图片标题，`:31` 1200px 以下三列。未加新样式体系。

## 原始验证输出

Reviewer 独立运行三份专项测试，使用输出专用临时目录与 `-p no:cacheprovider`，exit 0：

```text
........................................                                 [100%]
40 passed, 6 warnings in 4.99s
```

修复后 Linux `output/phase10-final-integration.log`（不是旧失败日志）：

```text
PASS fresh Linux PG/Redis/MinIO/API/Worker
PASS fresh and repeated migration
287 passed, 6 warnings in 16.51s
```

`output/phase10-frontend-tests.log` 原始结尾：

```text
ℹ tests 56
ℹ suites 0
ℹ pass 56
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1940.1345
```

`output/phase10-typecheck.log` 为 `vue-tsc --noEmit` 空 stdout，主 Agent 记录退出码 0。`output/phase10-frontend-build.log` 构建原始结尾：

```text
dist/assets/index-C3gms9Ly.js                                                       1,609.42 kB │ gzip: 534.15 kB
✓ built in 37.56s
```

六条后端警告为 FastAPI/httpx、AnyIO 弃用和匿名鉴权用例 SQLAlchemy NULL 主键提示，测试退出码 0；不等于测试跳过。完整日志保留在上述 output 路径，不用旧快照通过片段替代最终集成。

最终隔离集成已完整结束，Reviewer 直接读取 `output/phase10-final-integration.log` 原始结果，并打开新截图验证视觉：

```text
PHASE10 API PASS: asynchronous revision, queued/running barriers, stable replay, competing new requests, unchanged other slot IDs/object/hash, historical bytes and feedback
"PHASE10 BROWSER PASS: real single/whole revisions, 409 draft retained, stable key, unknown accepted response replay, background completion, readable historical image, feedback history; pageerrors=0"
PASS all previous browser and API tasks terminal before worker fault scenario
PASS long fixture configured for hard worker loss
PASS worker entered execution before hard kill
PASS hard killed worker lease transitions to uncertain
PASS hard SIGKILL plus expired lease remains uncertain, duplicate messages do not restart, slot retained
PHASE8 INTEGRATION PASS (four isolated volumes)
PASS isolated Compose volumes cleaned
```

浏览器故障注入脚本证据：`scripts/phase10/revisions.js:44` 标准 409 错误体、`:55` 关闭重开保留意见、`:65` 可见 Select 外壳选择历史版本、`:78` 已受理后断响应及原键重放、`:108` 截图；API 指纹与历史文件验证在 `scripts/phase10/revision_checks.py:34`、`:64`，Outbox 连接 `:93` 使用真实主键 `o.id`。先前失败运行不计通过；以上为修正后的最终运行。
