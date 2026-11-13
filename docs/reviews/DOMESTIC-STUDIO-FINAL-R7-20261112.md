# 国内 AI 工作台及联合发布独立审查 R7 · 2026-11-12

## 结论、快照与边界

- **candidateId：`2e3cbe215738e0796b6acb6bb49e962729b7f5f0bf17c568610b91f7ec5940ed`；Stage 1：FAIL；Stage 2：未执行。** 成品库不能展示源会话中已有的公开中途消息；归档还没有保存失败、取消或部分完成的轮次状态与错误。前者是相关对话资料不可在成品库查看，后者在源会话删除后连状态和错误的归档副本都没有。两项均属核心归档资料 HIGH。
- 审查范围：`Product-Spec.md:1-13` 国内五工作台、用户与数据权限、资料、成品库、Skills 和国内外隔离；`DEV-PLAN.md:1-32` 的联合迁移、恢复、构建和发布准备；`Design-Brief.md:1-3` 和 `hengxin-smart-image/frontend/preview-domestic-studio/` 确认预览。重点复核 FINAL 至 FINAL-R6 的旧问题以及本次归档编辑映射。已读取 `AGENTS.md`、`.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、实现说明和 FINAL 至 FINAL-R6 报告。以下 `backend/`、`frontend/` 相对于 `hengxin-smart-image/`。
- 本次不修改候选业务代码，不提交、不批准、不连接或操作生产、不调用真实模型。PostgreSQL 为 `127.0.0.1:35439/hx_studio_test` 随机隔离 schema，真实 MinIO 为 `127.0.0.1:35441` 随机测试 bucket；其余存储替身和浏览器模拟 API 的边界逐项标明。真实 HTTP 指 FastAPI TestClient 经实际路由，不是外部网络服务器或真实登录会话。
- 审查开始、独立复现完成、通知主 Agent 可以开始修复前，`review-status` 均显示上述 `currentId`、`approved:false`。主 Agent 获通知后开始修改，之后只读状态显示 `currentId=9ca90e868ab643e68db40cc37972ae0baf1e547339e8701e1c8c4638c100d6ef`，与送审候选不同；该新快照及其之后版本没有被本报告审查，不得用旧结论覆盖。报告和 `output/` 里的审查探针不属于代码快照。

## Stage 1 · HIGH

### H1：成品库隐藏了已归档的 Codex 中途公开消息

**要求。** `Product-Spec.md:6,10` 要求沿用连续对话，归档当前会话的成品及相关对话资料，并允许所有已授权国内成员查看归档对话资料；源会话删除后归档独立保留。

**实际链路。** 源工作台 `frontend/src/views/shared/studio/StudioTurns.vue:6-8` 使用 `StudioProcess`，其中 `StudioProcess.vue:2-6` 通过 `StudioTranscript.vue:1-9` 提供可展开的执行过程及多条公开消息；`studio-process.ts:3-11` 保留最终答复以外的消息。服务端 `backend/app/modules/domestic_studio/transcript.py:13-21` 可以对一轮记录多条 message，最后一条更新 `turn.reply`。归档 `archive_service.py:167-175` 保存全部 transcript，`archive_queries.py:59-63` 把它返回；但 `frontend/src/views/hengxin/domestic-studio/library.vue:11` 只渲染 `turn.reply`，没有将 `turn.transcript` 接入任何可查看的组件。`frontend/src/api/hengxin/domestic-archives.ts:7` 的归档轮次类型也没有 transcript。源会话可见的中途消息、过程摘要及通知在成品库界面无入口查看。

**独立验证。** `output/review-r7-transcript-probe.py` 以隔离 PostgreSQL、存储替身执行真实归档、删除源会话和第二位国内成员经实际 HTTP 路由读取归档；这里的测试通过证明数据确实保存，并非证明产品界面通过：

```text
source_messages= ['中途说明-逐条保留', '最终答复-逐条保留']
shared_archive_reply= 最终答复-逐条保留
shared_archive_transcript= ['中途说明-逐条保留', '最终答复-逐条保留']
.
1 passed, 1 warning in 16.85s
```

再以 `output/playwright/review-r7-transcript-visibility.js` 在正式 Vue 页面注入同形状的**模拟 API**：源页展开后可见中途说明，成品库详情和“对话与资料”页签中该说明出现次数为 0、最终答复可见、没有执行过程入口。原始结果：

```json
{"source_visible":true,"archive_intermediate_count":0,"archive_final_visible":true,"archive_process_count":0,"api_transcript":["中途说明-逐条保留","最终答复-逐条保留"],"boundary":"模拟 API，仅验证正式组件渲染"}
```

截图为 `output/playwright/review-r7-source-transcript.png` 和 `output/playwright/review-r7-archive-transcript.png`。该缺陷是**界面不可见**，不应错误地说这些 transcript 字节未保存；也不是对真实模型执行的验收。

修复时需保留用户可见的多条公开消息和过程，同时避免复制源私有 ID/URL。特别注意源页 `frontend/src/views/shared/studio/studio-transcript.ts:3-11` 依据 `itemId` 合并同一事件的多次更新，而 `archive_service.py:175` 当前把 `item_id` 去掉：直接把每条快照当独立项目会重复显示更新。新归档需要归档本地的稳定关联或在冻结时正确合并；旧归档没有关联字段，不能臆造能证明原始事件身份的关联。

### H2：归档缺失真实终态与错误，删源后无法还原

**要求。** `Product-Spec.md:6-7,10` 要求保留异常处理与会话相关资料，部分收取须保留已有结果并明确未保存；归档资料在删源后独立保留。

源查询在 `backend/app/modules/domestic_studio/queries.py:79-92` 返回 `Job.status` 和 `turn.error or job.error`，源页面在 `frontend/src/views/shared/studio/StudioTurns.vue:7-10` 显示状态与错误；`backend/app/worker/leases.py:11` 将 `succeeded`、`partial`、`failed`、`cancelled` 都视为终态。`archive_service.py:130-135` 允许已终态且会话有答复的记录归档，但 `archive_service.py:171-175` 没有将每轮 status 或 error 保存进 snapshot；`archive_queries.py:62` 没有返回它们。`conversation_cleanup.py:116-124` 删除源 Turn 和 Job 后，归档中没有可恢复这些状态及错误的副本。此处不依赖假设数据必然能从最后一条 reply 推断。

独立隔离 PG 探针对一条已产生答复的轮次分别设置三种合法终态，再执行真实 `prepare/complete/detail`；本探针未实际执行源删除，删源后不可恢复是根据上述清理代码与归档缺字段推得。原始输出中 pytest PASS 表示缺陷被复现：

```text
status_probe= failed source_status= failed source_error= 测试中的原始失败说明 archive_status= <缺失> archive_error= <缺失>
status_probe= cancelled source_status= cancelled source_error= None archive_status= <缺失> archive_error= <缺失>
status_probe= partial source_status= partial source_error= 测试中的原始失败说明 archive_status= <缺失> archive_error= <缺失>
.
1 passed, 1 warning in 12.63s
```

修复应保存并展示可核验的真实终态和面向用户的错误/部分收取信息；历史归档缺少依据时标未知或提供兼容展示，不能统一伪造 succeeded。新增字段及关联必须经归档快照校验，不能暴露私有源标识。重新固定候选后需从 Stage 1 重审。

## Stage 1 · MEDIUM：确认预览与正式页的布局及窄屏操作不一致

`Design-Brief.md:1-3` 指定确认预览为视觉与交互基准。独立浏览器用相同 1920×911、1000×844、390×844 视口比较 `frontend/preview-domestic-studio/Workspace.vue:4-30` 和正式 `frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:3-27`；正式页数据为模拟 API：

- 1920 宽：预览工具栏 69px、正式 63px；预览输入框 148.56px，发送提示位于框外，正式输入框 168.5px，提示位于框内。代码位置分别为 `preview-domestic-studio/style.css:1` 和 `frontend/src/views/hengxin/domestic-studio/workspace.css:4,8`、`DomesticWorkspace.vue:27`。删除“交互预览”字样本身是正式接入要求，不是此问题。
- 1000 宽：预览 205px 会话栏正常参与布局，输入框从 x=494 开始；正式页将 220px 会话栏绝对定位于 x=260–480，覆盖输入框左侧，输入框 x=301 处的命中元素是会话列表。正式的断点见 `workspace.css:10`，预览见 `preview-domestic-studio/sessions.css:2`。
- 390 宽：预览默认隐藏会话栏，正式 `DomesticWorkspace.vue:71` 默认打开 220px 栏覆盖 304px 输入区的左侧。点击栏内“收起”超时，Playwright 日志为 `<span class="">取回文件</span> ... intercepts pointer events`；工具栏顶部“会话 · 1”可关闭，关闭后输入可填写，因此不是完全无操作路径。上传按钮中心命中测试仍落在按钮，不能断言该按钮完全不可操作。

截图 `output/playwright/review-r7-{preview,formal}-{1920,1000,390}.png`，量测及操作脚本为 `review-r7-visual-compare.js`、`review-r7-overlay-reload.js`。此外工具栏图标、状态点和会话卡片文字/间距也可见差异，但本次未对全部状态做数值验收。

## Stage 1 · 逐项状态

下列“部分”是明确列出的证据，不等于端到端通过；HIGH 出现后没有将尚未覆盖的情况标为完整。

| 条目 | 实现、证据与未验证边界 |
| --- | --- |
| 两个新品、三个替换、成品库一级、超管 Skills | 部分：`frontend/src/api/hengxin/domestic-workspaces.ts:3-8`、`frontend/src/router/modules/index.ts:12-30`；浏览器模拟 API 逐一打开五入口。全部角色真实登录未测。 |
| 直接聊天、空白、无示例/自动发送 | 部分：`DomesticWorkspace.vue:15-27`，模拟 API 下空输入、无空引导及无绑定禁发实测；窄屏遮挡见 MEDIUM，未穷尽所有导航与自动触发路径。 |
| 新建、切换、重命名、删除、仅创建者 | 部分：`backend/app/modules/domestic_studio/conversation_service.py:29-33,70-106`、`file_service.py:75-97`；隔离 PG/HTTP 与浏览器模拟分别覆盖跨用户拒绝、创建/重命名、切换草稿和删除。全部并发及五入口真实身份未测。 |
| 实际姓名、北京时间、左右消息 | 部分：`backend/app/modules/domestic_studio/queries.py:84-92`、`frontend/src/views/shared/studio/StudioTurns.vue:6-7`；模拟数据验证张三/Codex、北京时间和左右位置，非真实登录身份。 |
| 输入/附件/连续对话/停止/单图和批量修改 | 部分：`DomesticWorkspace.vue:15-36,81-100`、`turn_service.py:42-80,91-116`；正式组件使用模拟 API 实测单图参考材料、两图批量、切换草稿、手动发送，PG 测试覆盖附件关联。真实 Skill/模型和全部停止异常未测。 |
| 部分结果可取回、不确定进程不自动重生 | 部分：`backend/app/modules/domestic_studio/runner.py:66-83`、`recovery.py:38-76`、`recovery_files.py:113-187`；模拟浏览器可发起手动取回，真实 MinIO 迟到取回有定向测试，未覆盖所有原节点和进程故障。 |
| 上传/输出/手动取回/归档迟到写、分片与大文件有界 | 部分：`file_service.py:43-72`、`output_intents.py:13-61`、`archive_service.py:203-232`；本轮真实隔离 MinIO+PG 的 11 项涵盖迟到、分片、500 MB 上传、工作区、归档、ZIP 和大 PNG，具体测试及内存指标的边界见对应测试文件。`tracemalloc` 不等于生产并发 RSS。 |
| 五入口教程，未提供时待补充 | 部分：`DomesticWorkspace.vue:3,33` 以入口名作标题并显示待补充；本轮模拟浏览器操作相机入口，其他四入口同组件，未逐一展开验证。 |
| 两新品按产品名归档、替换不可归档 | 部分：`backend/app/modules/domestic_studio/policy.py:12-30`、`archive_service.py:104-105`；真实 HTTP 覆盖 product 绕过为 403，模拟浏览器检查三个替换入口无按钮；未穷尽其他绕过路径。 |
| 独立副本、国内共享、源私有、删源保留 | **不通过：H1、H2。** R6 图片修改映射由 `archive_edits.py:8-38`、`archive_service.py:152-160`、`verify_snapshot:72-101` 实现；真实 PG 与存储替身/HTTP 测试覆盖两图标注及参考图字节、用途、第二成员、删源和伪造引用；旧无字段归档及超长显示文本用例通过。测试未覆盖所有历史、重名及篡改组合；基础图原件读取不能用仅校验映射的断言代替。 |
| 成品搜索、来源、详情、删除、下载和图片保护 | 部分：`archive_queries.py:24-77`、`archive_router.py:36-98`；隔离测试覆盖搜索、ZIP 字节、第二成员和源文件拒绝；对话详情不完整见 H1/H2，未完成全部界面、角色和图片条件请求组合。 |
| 超管文件夹上传/校验、同名更新、启停/删除、ZIP，无版本管理 | 部分：`backend/app/modules/auth/permissions.py:7-8`、`domestic_studio/management_router.py:25-28,82-163`；本轮管理/撤权测试通过，未独立走完整浏览器上传更新和 ZIP 内容矩阵，也未完整盘点所有管理界面。 |
| 五入口绑定、空初始、未绑定/停用禁发、冻结、保护 | 部分：`backend/migrations/versions/0033_domestic_studio_bindings.py:5-26` 不插入绑定；`bindings.py:37-82`、`policy.py:33-51`、`turn_service.py:42-80` 限定与冻结。定向 PG 和模拟浏览器覆盖部分情况，未穷尽全部竞态。 |
| 国内外身份、DB、对象、队列隔离，旧业务保持 | 部分：`domestic_studio/router.py:28-29`、`recovery_transport.py:4-14`、`scripts/release/intranet/domestic_studio_wiring.py:42-114`；前端全量和双业务范围构建通过，未连接生产、未验证完整跨业务端到端与真实模型。 |
| R1 迁移进程/DB 屏障、旧台账重入、前向恢复 | 部分：`scripts/release/intranet/joint_studio_fence.py:26-60`、`joint_studio_release.py:160-198` 和 `backend/migrations/env.py:39-47`；本轮 Linux 发布工具测试及单独真实 UID/PG 屏障通过，备份恢复演练通过，另有跳过项及测试替身；并非实际生产 Docker 升级。 |
| 受保护目录、UID/GID、socket、已安装身份和联合发布 | 部分：`scripts/release/intranet/joint_studio_verify.py:36-86`、`domestic_studio_wiring.py:42-114`；隔离 Linux 发布器测试通过，未安装或切换生产，未验证实际 Docker/服务器状态。 |
| Spec 漂移、完整视觉及发布验收 | 未完成：发现 HIGH 后停止，未全量盘点新增 API/表/页面、所有预览状态，也未进行真实模型、真实安装、生产入口及上线验收。禁止依据本报告宣称通过或部署。 |

## 本 reviewer 独立测试与编译原始输出

- 前端 `pnpm run typecheck` 退出码 0：

```text
> hengxin-smart-image-frontend@0.2.69 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

- 前端 `pnpm test` 退出码 0，原始汇总：

```text
ℹ tests 563
ℹ suites 0
ℹ pass 563
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 15714.6225
```

- 国内和海外生产范围 Vite 构建均退出 0；原始起止片段（完整日志分别在 `output/review-r7-domestic-build.log`、`output/review-r7-overseas-build.log`）：

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 4911 modules transformed.
(!) outDir .../output/review-r7-domestic-dist is not inside project root and will not be emptied.
✓ built in 40.92s
```

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 4700 modules transformed.
(!) outDir .../output/review-r7-overseas-dist is not inside project root and will not be emptied.
✓ built in 36.90s
```

这是当前候选工作树构建，不是 Git 提交后的正式包。日志中的 `...` 仅为路径/中间文件清单省略，未把片段称为完整输出。

- WSL 隔离 PG 的归档/图片/HTTP 定向组原始汇总 `22 passed, 1 skipped, 1 warning in 14.88s`；国内角色、绑定、会话、执行、恢复等定向组 `71 passed, 1 warning in 48.06s`。跳过项不计通过。真实 MinIO/PG 大文件和迟到写组 `11 passed, 1 warning in 32.35s`。归档前端两文件定向 `8 passed, 0 failed`。所有均是本 reviewer 在送审快照上独立运行。
- 发布工具隔离组 `73 passed, 5 skipped in 8.40s`。另启用隔离 PG 跑真实 Linux 迁移/进程/发布器组，首次 `1 failed, 4 passed in 14.45s`：仅 UID 1001 子进程缺测试环境 `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY` 导致 Settings 初始化失败；单独设置假的测试凭据后该用例 `1 passed in 3.73s`。这不是一次 5 项全通过的输出，也不是产品生产故障。测试警告为 FastAPI TestClient 的 StarletteDeprecationWarning。
- `frontend/package.json:3` 的版本仍为 `0.2.69`，与 HEAD 一致；`.agents/skills/release-builder/SKILL.md:27` 的发布准备清单要求 `package.json version 已更新`。这是已知发布准备缺项，不代表当前候选可审查通过或可发布。

## 候选外上线辅助脚本 · 补充审查

以下 `output/domestic-studio-release-bin/` 文件不属于 candidateId，不是候选 Stage 2 或生产运行的通过证明。审查时主 Agent 修改 `server_publisher_smoke.py`，在两个容器内 Python 健康探针加 `-E`；以下按最终给定版本和下列哈希记录，之后更改须重审。

- `build_committed.py:12-14`、`install_committed.py:12-17`、`run_server_helper.py:8-10`、`upload_and_stage.py:9-11` 在调用工作树打包器或 SSH transport 前检查相对 HEAD 的变更；安装器 `install_committed.py:21-51` 将 Git blob 与归档逐项核对并计算 manifest 哈希。辅助脚本及本地 `packages.json`/`installation.json` 自身不在候选中，本地元数据和最终运行脚本须由操作者按已审版本与本次构建产物独立核对。
- `run_server_helper.py:32-41` 在导入安装工具前拼接 `server_verify_tools.py:10-37`，以本地预期 manifest 哈希、root 所有权、祖先权限、清单及文件内容校验拒绝链接和额外文件；publisher 冒烟前同样以 `server_verify_candidate.py:10-39` 校验包内可信 manifest 的国内 backend/app 树。`python3 -E -B` 避免环境优化变量跳过这些 assert。两个隔离 WSL 防篡改脚本由本 reviewer 执行，原始输出：

```text
Tool verification: trusted tree passes; content, extra file, symlink, manifest and unsafe permissions rejected
Staged backend verification: valid tree passes; content, extra file, symlink, manifest and unsafe permissions rejected
```

  这是临时目录、模拟 hostname 的定向验证；不等于实际安装目录及其最终状态已验证。校验与后续导入/执行之间仍依赖受保护路径和不被其他 root 进程并发修改的运行前提。
- `server_publisher_smoke.py:22-35,62-101` 使用随机临时目录/标记、无网络且只读根的测试容器，初始化位于 `try/finally` 内、健康检查轮询，两个容器内探针已用 `python -E`。强制终止仍可能遗留已知临时目录或容器；不能据此执行批量清理。
- `server_installed_checks.py:24-43` 使用精简环境；其部分真实数据库与身份用例在无显式测试 DB 时会跳过（`scripts/release/intranet/test_joint_studio_migration_linux.py:14-20`、`test_domestic_publisher_linux.py:17-24`），跳过不可记作通过。`server_activate_tools.py:26-59` 仅在受锁且台账空闲时切换工具链接，异常恢复该链接不等于回滚业务或数据库。
- `upload_and_stage.py:38-61` 独占上传、校验再 stage，但上传、解包、台账登记不是一个原子操作；本轮没有执行这些生产操作。任何上传、stage、工具安装、冒烟或发布中断后，须先只读确认具体已知路径、哈希、容器标记、台账与引用，再决定对自身资源的恢复；不得按名称批量清理或覆盖未知资源。

辅助脚本最终 SHA-256：

```text
CB1047492A1E1B58C00A73A0A8756B4FBAF3FD38E8BA5C999A919D7E7C85E322 build_committed.py
7BC3BE91CB2975113CEA5ECC71E50D13BC3579D50871D36CC2DDB866968684EB install_committed.py
E9D5D4E8DEE7F6656442F46E190B477B43172B2F318670DBFAA486A05DC2E46C run_server_helper.py
C6C7EC61BC87BB3F17F47712E518F3484BA4F526E754091AADE4FDA511226C6A server_activate_tools.py
AD9546ACDA72BAF31A7296E52F7D59428DA7F3F7AFB1A8571C07FA9ACBC25B9F server_installed_checks.py
02EA7BA52243EB1ED623A4049DCB9A6BFC93D14F1AD5F0AF193BF76AB2F91FED server_publisher_smoke.py
E9D72386C57B04B3C80CBAF1EFE8B75D1F4DF31086C2F668F2B22B26537C998B server_verify_candidate.py
8A440E7D732CC5EC63B4F04F1DDE70DEAB8A4D57AB9759CA2133D4D5D80C8375 server_verify_tools.py
B058BC2F15385E5AAA1F597E0FC719182D696476D6E118137E13B54AD443ECCC test_server_verify_candidate.py
332C3D6E85EB7EBA91543913ECFB36BF606F21759C74CBF8EDF4510E6649FEB6 test_server_verify_tools.py
335371C929DDD0BA2BA005AD2B5E1BC755A0D0D39865384D4D0ED30FDC91FBB4 upload_and_stage.py
```

## Stage 2

**未执行。** Stage 1 存在 HIGH；没有系统执行代码质量、安全扫描、测试真实性全面审查或正式页与邻居基准页面实际对比。上面的确认预览对照属于 Stage 1，候选外辅助工具只读专项不构成 Stage 2。修复后由主 Agent 重新固定快照并派独立 reviewer 从 Stage 1 起审查；不得以本报告登记两阶段 PASS 或写 clean。

报告写成后的只读快照状态（主 Agent 已开始修复；不代表审查过新内容）：

```json
{"currentId":"31ef5b83fbf8ab697a85edf81faaba962443d0cbc7dbef7ca67f3f7f906644d4","reviewedId":"d3a967332ae14940e06e774849782af11917f8c7bc2e0902deee6d698edc3ce1","approved":false}
```
