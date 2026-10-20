# 国内 API 简化整改验收记录

本轮范围见 [实施合同](API-RETRY-SIMPLIFICATION-20261020.md)。本轮仅本地代码与隔离验收，未提交或部署生产。既有版本 0.2.44 的线上状态不以本记录宣称改变。

## 实现

- 前端沿用真实记录页、详情抽屉、图片卡片及样式；整体一句进度，每图一个短状态。失败给“重试这张”，结束后给“重试未完成的 N 张”；处理中混合任务保持原后端资格，仅对已失败图单张重试。
- 删除国内 API 的管理员核实按钮、客户端方法、服务函数、路由与请求 schema。调用本地已结束的未知错误进入原退避/冷却；遗留过期执行在原通道锁内恢复，保留预算、截止、冻结输入和容量，并撤销旧 token。
- 有结果回执时只收图。有效租约仍受保护；恢复与迟到回执以锁内先后决定接纳；历史终态及旧 unknown 审计不重做。
- 原重试参数、全局发送/在途门槛、冷却单探测、停止、幂等、成功版本、CLI 与海外机制保持。原请求未决时由内部保留原幂等键，前端直接提供重试操作。

## 验证证据

| 验证 | 结果 | 日志/证据 |
|---|---|---|
| 前端全量 `pnpm test` | 初轮321/321通过；审查修复后最终322/322通过 | `output/api-retry-frontend-tests-20261020.log`、`output/api-retry-simple-20261020/frontend-tests-final.log` |
| 前端类型及正式构建 | 最终 `vue-tsc --noEmit` 与 `npm run build` 通过，构建40.83秒 | `output/api-retry-simple-20261020/frontend-build-final.log`、`frontend-typecheck-final.log` |
| 后端 API 专项及 PostgreSQL 并发 | 256 通过、16 条宿主条件跳过；compileall 通过 | worker 执行 `pytest tests -q -k 'api_image or api_retry or api_task_deletion'` |
| 仓库工具测试 | 96 通过、12 条条件跳过 | `output/api-retry-simple-20261020/backend-repository.log` |
| 容量模块修正后 Linux 复验 | 10/10 通过 | `output/api-retry-simple-20261020/capacity-final-linux.log` |
| Linux 后端全量 | 2201通过、25跳过、1条旧容量预期失败（见下文修复及10项复验），410.22秒 | `output/api-retry-simple-20261020/backend-full.log` |
| 正式构建 + 浏览器路由夹具 | 最终8组检查通过，无页面错误 | `output/api-retry-simple-20261020/browser-fixtures-final.log`、`output/playwright/api-retry/evidence.json` |
| 正式构建 + 真实 HTTP/PG 联调 | 3 组流程通过，无页面错误 | `output/api-retry-simple-20261020/browser-live.log`、`live-evidence.json` |
| 独立两阶段审查 | Stage 1/2 PASS，开放 HIGH/MEDIUM 0；harness 已登记批准 | `docs/reviews/API-RETRY-SIMPLIFICATION-20261020.md` |

浏览器夹具调用正式打包页面，模拟 API 状态用于故障注入。验证短状态、无核实/技术计数、390px 可见边界、停止防双击、停止响应丢失后刷新使用同一幂等键、在途停止与迟到成功、旧图保留、冷却期间合法重试、明确停止失败后的再次操作、新建页短说明。SFC 组件测试另覆盖重试提交未知/明确失败、通道暂停下恢复原操作、CLI 批量保护、下载失败不改变生成状态；轮询测试覆盖刷新失败保留上次数据。

真实联调使用 `scripts/api-retry/simple-live-app.py` 与 `simple-live-browser.mjs`：独立本地 PostgreSQL 临时 schema、普通 operator、真实身份/业务 HTTP 路由、真实前端 dist，只有上游换成 FakeClient、文件改用内存存储。没有请求收费上游。种子为成功一图、原20次额度耗尽的未知失败一图、未知错误自动等待一图；浏览器直接单张重试、停止、终态批量重试，直到全部成功，刷新后下载。成功图 fileId 不变，原成功图只发送一次，重试图新轮各一次。OpenAPI 无 resolve 路由，旧路径不再接受业务请求。

桌面/窄屏截图：`output/api-retry-simple-20261020/live-mixed.png`、`live-partial.png`、`live-narrow-stopped.png`、`live-completed.png`；已人工查看桌面混合状态与390px停止状态，沿用原组件，无横向溢出或按钮被抽屉底部遮挡。

Linux 全量在只读挂载整个仓库的现有 backend 镜像中运行，使用仅本任务的 Docker 内部网络与独立测试 PG，未连接生产。六个依赖仓库宿主环境的测试模块在 Windows 单独运行。条件跳过并非通过，最终计数以日志为准。

首轮全量的容量测试仍断言过期项停在 `uncertain`，与本轮取消永久核实门槛冲突。仅修正这一旧预期为 `retry_wait`/撤销旧 token，并加强原容量 cycle、held/60MiB 不变、attempt 审计保留、删除仍409的断言；整个容量模块在 Linux 复验10项通过，无后端源码改动。初轮失败证据保留在 `capacity-failure.log` 和全量日志。

独立审查还发现列表两个筛选选项同名“处理中”且处理中统计漏计旧 unknown。修复为不同短名称“处理中 / 等待结果”，统计包含 queued/running/uncertain；复用同一状态判定，并增加筛选名称唯一、等待结果计入处理中、CLI 独立状态不混入 API 统计的回归。

## 已知边界

当前上游没有取消/查询或幂等协议。可以验证本地有效租约不被重放、恢复后旧 token 不能提交、已有回执只收图；不能承诺超时后的远端计算已经停止，或远端不会重复计费。这是取消人工核实后沿用现有恢复机制的实际边界。

独立审查初始候选：`4d025fb87c0f1f3925d4a36d239c8deb80b0252df61a104c0528721a392a8b1b`；修复后最终候选：`19ff4eb28e6ef86981da5efa160f313380f4dcd1f20897d39c6998441d8d7eca`。最终批准以 harness review-status 匹配为准。

验收服务已停止；仅本任务创建的 `hx-api-simple-pg` 容器（包含临时 schema）与 `hx-api-simple-net` 网络已删除。保留截图和日志，未改动其他测试服务或生产服务。
