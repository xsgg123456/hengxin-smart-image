# 工作台开放输出最终独立审查（2026-10-24）

## 结论、快照与边界

- **Stage 1：PASS。Stage 2：PASS。** 本次未发现阻断本候选提交的新增功能、安全或质量问题。
- candidateId：`16c34af9249fb8d4c8a6049d0009d62cad34427bf9ca1231d9adff97597540a1`。
- 范围：本轮 `git diff HEAD` 与未跟踪代码，包括后端自动输出、手动取回、Redis/native transport、清理、迁移及测试，前端卡片/原件下载/取回交互，以及五个新增发布模块和发布测试。用户既有 `AGENTS.md` 修改不属于本次产品提交批准范围。
- 依据：完整读取 `docs/STUDIO-OUTPUT-IMPLEMENTATION-20261024.md`、Product-Spec 最新覆盖条款、DEV-PLAN 最新步骤、Design-Brief 既有组件规范、code-review skill 和 HARNESS-REVIEW 协议。旧报告 `docs/STUDIO-OUTPUT-CODE-REVIEW-20261024.md` 的核验项作为补充证据，旧 FAIL 不直接转换为新 PASS。
- 先完成 Stage 1 逐条核对和独立行为测试，再做 Stage 2。独立重跑关键后端 **50 passed**（包含真实事故私有原始记录回放）及发布 **31 passed**；独立类型检查 exit 0。没有改业务代码、提交、调用生产模型或执行部署。
- 本结论是代码候选的审查批准，**不是已完成生产交付**。Linux 实际安装包全测、真实 PostgreSQL/Redis、备份恢复、切换及正式入口验证仍由主 Agent 按发布门禁执行；Windows 结果不替代这些验证。

下文 `B/` = `hengxin-smart-image/backend/`，`F/` = `hengxin-smart-image/frontend/`。行号为本候选源文件行号。

## Stage 1：合同逐条对照

| 合同要求 | 结论 | 实现与证据 |
| --- | --- | --- |
| 1：只自动接收最终回复本地文件链接，不强制 JSON/固定措辞 | 完整实现 | `B/app/overseas/studio/delivery.py:19-38,60-96` 解析 final_text、排除外链、校验路径；旧文件链接专项及本次混合原件测试。 |
| 1：原生附件必须有最终呈现和本会话真实文件证据；ImageView 不是输出 | 完整实现 | `B/app/overseas/studio/native_images.py:70-76,98-107,241-269`；本次 `B/tests/test_studio_open_outputs.py:59-120` 精确事故回放和素材查看路径均通过；旧报告原生呈现专项保留。 |
| 1：普通文字回复可正常结束，下一轮可提交 | 完整实现 | `B/app/overseas/studio/delivery_job.py:68-93`；`B/tests/test_studio_open_outputs.py:59-82,110-120`，实际 API 断言下一轮 200、activeTurnId 为空、执行次数为 1。 |
| 2：保存原件字节，格式不决定整轮成败，普通文件独立存储 | 完整实现 | `B/app/overseas/studio/output_files.py:23-35`、`output_store.py:14-22`、`models.py:88-100`；`test_studio_open_outputs.py:35-56` PNG/ZIP/未知/0 B/坏图混合接收及字节下载通过。 |
| 2：图片保持预览、修改、归档；其他文件只有名称、大小、下载 | 完整实现 | `F/src/views/overseas/studio/StudioTurns.vue:10-20`、`StudioOutputs.vue:2-7`；图片选择仍仅迭代 pictures；`B/tests/test_studio_open_outputs.py:132-138` 普通输出不能替代归档条件。 |
| 2：预览失败仍可下载原件 | 完整实现 | `F/src/views/overseas/studio/StudioAssetImage.vue:4,24-30`、`F/src/api/overseas/attachment-download.ts:9-27`；HEAD 预检与缩略图解码独立，实际下载交给浏览器；复用旧报告浏览器下载事件和 `studio-preview-download.test.ts:9`。 |
| 3：单次自动收取，逐项成功保留、失败明确显示 | 完整实现 | `B/app/overseas/studio/delivery_job.py:129-165`、`output_store.py:25-60`；`F/src/views/overseas/studio/StudioTurns.vue:34-36` 展示 partial 终态和取回入口文案。本次 continuation、手动部分失败测试通过。 |
| 3：确认模型正常结束后，收文件失败不变 uncertain、不无限重试 | 完整实现 | `B/app/overseas/execution/runner.py:187-199`、`delivery_job.py:80-86` 移除重试字段并以 succeeded 结束；`B/tests/test_studio_receipt_continuation.py:13-52` 走真实 runner/API。 |
| 3：重启先核实原执行，只恢复已有副本、不重跑模型；真正异常保留 | 完整实现 | `B/app/overseas/studio/delivery_recovery.py:21-67`、`delivery_job.py:105-106,132-134`；`runner.py:139-149,200-208` 保留实际异常分支；复用旧报告 WorkerInterrupted 回归，复核本轮 diff。 |
| 4：已识别输出先留本轮副本，再允许后续轮；上传失败仍可取旧字节 | 完整实现 | `B/app/overseas/studio/delivery_snapshot.py:58-91`、`delivery_job.py:129-150`；本次 continuation 测试实际覆盖同名工作文件后取回旧版。 |
| 4：无副本不承诺恢复，不增加全目录版本系统 | 完整实现 | `B/app/overseas/studio/delivery_job.py:133-147`；`F/src/views/overseas/studio/StudioRecoveryDialog.vue:11` 明示未生成/已删/覆盖无副本不可恢复。只有自动识别清单进入冻结 manifest。 |
| 5：普通设计师列举本会话 work、关联 generated_images、已有副本 | 完整实现 | `B/app/overseas/studio/recovery_listing.py:117-155`、`recovery_files.py:13-35`；本次 `test_overseas_studio_file_recovery.py:31-45,70-94,119-149` 通过，使用普通 designer。 |
| 5：用户选择直接保存，绕过自动识别、不调用模型、不要求全局暂停 | 完整实现 | `B/app/overseas/studio/recovery_files.py:48-81` 直接 read/save；`recovery_transport.py:91-105` 无模型入口；本次 RPC 测试检查执行次数不变、Job 数不增。 |
| 5：当前会话在写入时等待，其他会话及已存文件可用 | 完整实现 | `B/app/overseas/studio/recovery_files.py:23-27`、`recovery_listing.py:48-52`；`B/tests/test_overseas_studio_file_recovery.py:171-206` 通过，busy 按 conversation 过滤。 |
| 6：重复同版本返回同一结果，包括 work 与 snapshot 两种顺序 | 完整实现；旧 HIGH 已关闭 | `B/app/overseas/studio/recovery_files.py:65-76` 使用同 job、target、checksum 的捕获 pictureId；新 `B/tests/test_studio_recovery_versions.py:25-38` 对图片/文件 × 两种顺序共四项 HTTP 测试全部通过，检查 ID 与数据库数量均一致。 |
| 6：同名新字节是新版，后续正式轮次保留独立关系 | 完整实现 | `recovery_files.py:66-76` 同 job 匹配，非副本 UUID 含 turnId/target/checksum；`delivery_snapshot_fs.py:46-48` 捕获身份含 job；新 `test_studio_recovery_versions.py:41-59` 后续轮同字节两个 ID、两条记录通过，既有同名异字节测试也通过。 |
| 6：手动新增不改旧轮冻结输出清单 | 完整实现 | `B/app/overseas/studio/recovery_files.py:75-80` 只保存独立结果；`output_store.py:63-84` 仅更新原有 deliveryOrder 对应已保存数量，不写 manifest/selection。 |
| 6：500 MB、0 B、取消旧10 MiB图片门槛、解码失败仍下载 | 完整实现 | `B/app/overseas/studio/output_files.py:26-35`、`files.py:26-51`、`recovery_listing.py:158-173`；本次 `test_studio_open_outputs.py:141-154` 用实际 >10 MiB PNG 验证仍是 picture 且字节不变；0 B 与坏图下载通过。 |
| 6：权限、会话隔离、受保护路径、不可读系统配置 | 完整实现 | `B/app/overseas/studio/recovery_router.py:19-27`、`recovery_files.py:13-27`、`recovery_listing.py:18,64-80,146-154`；复用 `context_fs.py:24-49,68-99` 无链接读取；本次权限撤销、跨会话、配置目录测试通过。 |
| 6：新增记录/对象参加任务及会话删除；删除受理后拒绝迟到发布 | 完整实现 | `B/app/overseas/studio/conversation_cleanup.py:46-51,99-108`、`tasks/cleanup_files.py:19-24,35-50`、`tasks/cleanup_records.py:24`；`output_store.py:29-59` 外部 IO 前后均 guard；本次 lifecycle 与迟到删除测试通过。 |
| 6：完成只读，已保存可下载，解冻后恢复取回；不增加普通文件完成条件 | 完整实现 | `B/app/overseas/studio/recovery_files.py:23-24`、`files.py:115-122`；`F/src/views/overseas/studio/OverseasStudio.vue:42`；本次完成拒绝/解冻取回及无图片不能完成测试通过。 |
| 生产补充：API/native 根不同，复用 Redis/outbox，不挂载原件、不传字节 | 完整实现 | `B/app/overseas/studio/recovery_router.py:19-27`、`recovery_transport.py:60-105`、`execution/outbox.py:32-38`；本次 transport fixture 确实分离 API/native 根并禁止 API 枚举文件，检查 Redis 写入不含原文件字节。 |
| 生产补充：短时请求、超时明确、二次鉴权、失败隔离 | 完整实现 | `recovery_transport.py:19-28,69-88,94-134`：30 秒 TTL、25 秒 deadline、队列上限 32、每次消费一条；`recovery_router.py:25-27` 先释放事务；本次权限变化、丢响应重试、过期、畸形、连接失败、队列满测试通过。 |
| UI 引导真实、继承既有设计 | 完整实现 | `StudioRecoveryDialog.vue:4-19,30-40` 的 100 个/500 MB/忙/失败/只读/空态文案有服务端与交互实现；沿用 Element 组件与变量。目视复核桌面、390px 及邻居基准截图，见 Stage 2。 |
| 执行计划 1–4：源文档、独立表、迁移、前端接线 | 完整实现 | Product-Spec 末节与本合同一致；`B/migrations/overseas/versions/0022_studio_output_files.py:10-31` 仅新增 output 表；前述 API、组件、清理路径齐全。 |
| 执行计划 5：真实事故/混合文件/失败路径/独立审查 | 本候选代码审查通过 | 本次独立 50 + 31 项测试、类型检查及旧完整回归/构建证据见下；私有 fixture 不在源代码或包允许清单。 |
| 执行计划 6：继承发布、排空备份、迁移切换、正式验证 | 发布实现匹配；实际执行待验收 | `scripts/release/studio-output-deploy.py:72-101` 要求已恢复核验备份、排空停止和原数据指纹不变才增表；继承安装与权限/Skill保护。31项发布测试通过，但未执行生产切换。 |

## Stage 2：代码质量、安全、测试真实性与视觉

| 项目 | 结论与证据 |
| --- | --- |
| 模块边界与重复代码 | PASS。`output_store.py:25-60` 统一自动/手动保存和对象台账；listing、router、transport 分工独立。`tasks/cleanup_records.py:7,24` 旧报告重复 import/DELETE 已消除。本轮受审源文件检查未发现超过 300 行的新增大模块；前端新增类型无 `any`。 |
| 去重修复真实性 | PASS。四个双来源顺序用例使用真实 SQL 会话、真实磁盘、普通设计师 HTTP，只有存储/模型边界为替身；不是仅测 UUID 纯函数。第五项实际提交第二轮，断言两个记录而不是错误跨轮合并。`B/tests/test_studio_recovery_versions.py:25-59`。 |
| RPC 测试真实性 | PASS（隔离证据范围）。`B/tests/test_studio_recovery_transport.py:59-86,102-138,160-175` 确实设置不同根目录、权限变更发生于另一事务、丢响应发生在文件已保存后。Redis 为 MemoryRedis；未声称真实 Redis Lua/网络已验证。生产通道仍须实测。 |
| 错误与并发处理 | PASS。`output_store.py:29-59` 持久台账先于 IO，发布再取任务锁；`recovery_files.py:81-90` 分文件返回安全错误；`use-studio-recovery.ts:17-49,56-60` 取消/会话切换过滤迟到响应、失败保留选择。 |
| 安全扫描 | PASS（新增代码）。检查受审 Python/TS/Vue/mjs 的密钥、eval、HTML注入、暴露前缀、绝对路径和类型绕过。`recovery_transport.py:69` 命中的是固定 Lua 脚本及独立参数，不执行用户代码；发布固定绝对路径用于基线校验。没有新增硬编码凭据、动态 SQL 用户拼接或任意路径接口。 |
| 原件下载 | PASS。`F/src/api/overseas/attachment-download.ts:9-27` 固定同源端点、带身份 HEAD、禁重定向；`B/app/overseas/studio/files.py:115-122` 后端再次 task 授权，`B/app/overseas/attachment_delivery.py:8-28` attachment/nosniff/private-no-store。10 秒超时只用于 HEAD，不套在大文件实际下载上。 |
| 发布跨层保护 | PASS。`package-studio-output.py:11-29` 显式包含 transport/迁移/测试和发布 helpers；`studio-output-deploy.py:20-43,72-101` 固定 0.2.51→0.2.52、0021→0022 和 Compose 授权链；`studio-output-data.py:15-25` 比对全部旧列/行；失败保持关闭、不降级/还原生产库。 |
| 事故结算范围 | PASS。`studio-output-settle.py:13-31,44-77` 固定 job 和事件哈希、私有请求、prepare pin、关闭 API/接纳后单次结算；`studio-output-settle-runtime.py:38-81` 校验同 worker、已退出、进程及进程组消失、一次执行、无删除、原成功事件与会话一致，原模型及原收图不重跑，留 Audit。`test_studio_output_release.py:186-249` 成功及16种危险漂移测试通过。 |
| 原始事故证据 | PASS。`B/tests/test_studio_open_outputs.py:85-120` 校验完整原始 rollout SHA，重放保全事件和工作文件，断言完整原回复/文档字节/只执行一次/可续聊。本次设置私有 fixture 环境变量运行，故该项没有 skip。客户内容未写入本报告。 |
| 视觉对比 | PASS（复用已执行浏览器记录并独立目视复核）。查看 `output/playwright/studio-outputs/desktop-partial.png`、`mobile-dialog.png` 与邻居基准 `output/playwright/studio-delivery-status/desktop-baseline-complete.png`：蓝色主操作、白底圆角、灰色辅助文案、边框/按钮密度一致；390px 弹窗按钮折行且在可见区域，错误项可读。`StudioRecoveryDialog.vue:30-40` 对应滚动、换行与变量；本次没有重启 Vite 或改变 components.d.ts。旧 reviewer 实际浏览器脚本结果见下。 |

### 非阻断说明与待执行验证

- **既有依赖风险，不能称“依赖无漏洞”**：读取 `output/studio-output-dependency-audit.json`，生产依赖 high 37 / moderate 37 / low 3 / critical 0；本轮锁文件没有 diff，未引入依赖升级。该扫描不等于逐条漏洞可利用性判断，作为既有依赖治理待办，不混成本候选新增漏洞结论。
- 安装/生产验证仍未完成：本次独立测试使用 Windows、SQLite、内存对象存储/Redis 替身；旧全测存在 Linux 专属文件行为的环境边界。主 Agent 必须继续真实 Linux 安装包全测、PostgreSQL迁移/并发、Redis transport、正式页面及原件下载验证；不得拿此报告宣称已部署或跳过发布门禁。
- 发布代码继承链较深，已核对函数接线与实际安装只读挂载用例（`scripts/release/test_studio_output_release.py:39-57,141-152`），本次没有把离线发布测试表述为真实排空/备份测试。
- 未发现超合同新增页面、归档功能或模型调用；OutputFile、取回接口、metadata transport、限定事故结算分别由实施合同及授权范围支撑。没有未实现的本轮代码要求；剩余工作是已明确列出的实际发布验收。

## 原始验证输出

本 reviewer 独立执行，工作目录 `B/`，设置 `STUDIO_INCIDENT_FIXTURE` 指向忽略目录中的私有保全文件：

```text
.venv/Scripts/python.exe -m pytest tests/test_studio_recovery_versions.py tests/test_studio_recovery_transport.py tests/test_studio_open_outputs.py tests/test_overseas_studio_file_recovery.py tests/test_studio_output_lifecycle.py tests/test_studio_receipt_continuation.py -q
50 passed, 2 warnings in 32.38s
```

仓库根目录独立发布测试：

```text
hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_studio_output_release.py -q
31 passed, 2 warnings in 14.98s
```

两处 warnings 为 Starlette httpx 和 anyio BlockingPortal 弃用提醒。初次使用系统 Python 时输出 `No module named pytest`；随后使用项目 venv 完成上述有效测试，没有将初次环境失败计作测试通过。

独立类型检查：

```text
pnpm exec vue-tsc --noEmit
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
exit_code: 0
```

读取既有构建日志 `output/studio-output-production-build.log` 原始输出（构建不是本 reviewer 重跑）：

```text
> hengxin-smart-image-frontend@0.2.52 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
dist/assets/index-7p9zuagU.js  963.71 kB │ gzip: 307.80 kB
✓ built in 30.53s
```

读取主 Agent 既有完整相关回归日志，证据级别为复用：

```text
# output/studio-output-final-backend.log
885 passed, 43 skipped, 1881 deselected, 2 warnings in 236.07s (0:03:56)
# output/studio-output-final-unit.log
ℹ tests 396
ℹ suites 0
ℹ pass 396
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9052.599
```

旧独立 reviewer 已执行的浏览器证据（其报告记录，当前再次目视对应截图）：

```text
node tests/studio-outputs.browser.mjs
PASS: mixed outputs, partial terminal/send enabled, output download, failed preview original download, recovery partial/retry/empty, desktop/mobile clipping; no model calls
node tests/studio-delivery-status.browser.mjs
PASS: capturing, partial image, saving/waiting counts, completion, desktop/mobile clipping; no model calls
```

## 快照交接

审查开始 `review-status.currentId` 与给定 candidateId 一致；本 reviewer 只新增本报告。旧 HIGH 修复、新 transport 与发布 helpers 均纳入本次独立审查，不用旧报告批准它们。主 Agent 应再次运行 review-status 确认内容未漂移，再对同一 candidateId 用 review-approve 登记两阶段 PASS。本报告不写 `.needs-review`、不授权任何未经审查的后续代码变更。
