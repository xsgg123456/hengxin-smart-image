# 国内 AI 工作台与联合发布独立审查 R10

## 结论、快照与范围

- **candidateId：`7fbc36effc12dbfe9eca65e57d766184c723791f25e9a2edbe0f7e5c3c6939f8`；Stage 1：FAIL；Stage 2：未执行。** R9 的输入区和会话头高度问题本轮复测已匹配，但同一确认预览仍存在下列工具栏和输入操作的 MEDIUM 视觉差异。按 `Design-Brief.md:1-3` 对确认预览的要求，本候选不能登记两阶段 PASS。未发现新的 HIGH 不等于证明所有故障均已覆盖。
- 范围：`Product-Spec.md:1-13` 国内五工作台、会话、附件与恢复、归档、Skills、国内外隔离和交付；`DEV-PLAN.md:1-36` 联合迁移、恢复、大文件及响应式；`Design-Brief.md:1-3` 和已确认 `hengxin-smart-image/frontend/preview-domestic-studio/`。另按派发要求只读核查候选外 `output/domestic-studio-release-bin/`。下文 `backend/`、`frontend/` 相对于 `hengxin-smart-image/`。
- 已读取 `AGENTS.md`、`.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、本轮 Spec、计划、设计规范、实现记录、预览与 FINAL 至 FINAL-R9 报告；旧报告只用于定位风险，不替代当前验证。本轮开始及测试后只读 `review-status` 均为以上 `currentId`、`approved:false`；未观察到受控代码变化。未修改业务代码、提交、批准、写 clean、连接生产或调用真实模型。主 Agent 修复后应重新固定快照并从 Stage 1 审查。

## Stage 1 · 视觉不匹配

### M1：移动宽度工具栏对齐、字号、状态和按钮高度与预览不一致

`frontend/preview-domestic-studio/style.css:3` 在不超过 700px 时隐藏状态、将工具按钮组右对齐、把工作台标题设为 14px。`frontend/src/views/hengxin/domestic-studio/workspace.css:5,14` 未作对应调整，并统一把工具栏所有按钮设为 36px。相同浏览器和数据条件下独立测得：

| 视口 | 确认预览 | 正式页面 |
| --- | --- | --- |
| 390×844 | 工具按钮组左边 x=124.96875px，状态隐藏，工作台标题 14px | 按钮组 x=36px，显示“准备就绪”，标题 15px |
| 700×844 | 状态隐藏，标题 14px；“展开”按钮 24px 高 | 显示状态，标题 15px；“展开”按钮 36px 高 |

700px 的页面主标题双方均 24px、工具栏均 61px 高，按钮组均从 x=429.96875px 开始；390px 的工具栏均 105px 高。上述数据来自 `output/playwright/review-r10-mobile-compare.js` 与 `output/playwright/review-r10-mobile-compare.json`，截图为 `output/playwright/review-r10-{preview,formal}-{390,700}.png`。正式版必须保留真实状态逻辑；是否显示及布局须符合已确认的窄屏样式。

### M2：窄屏输入操作字号、发送图标与预览不一致

`frontend/preview-domestic-studio/style.css:3` 在不超过 700px 时将输入区按钮文字设为 12px；`frontend/preview-domestic-studio/Workspace.vue:24` 的发送按钮使用 `Promotion` 图标。正式页 `frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:27` 未给发送按钮配置图标，`workspace.css:10,14` 也未覆盖 700px 以下输入按钮的 14px 默认字号。390px 和 700px 实测预览三个操作文字均为 12px，正式均为 14px；发送按钮预览宽 74px 且有图标，正式宽 60px 且无图标。701px、1000px 的正式发送按钮同样无图标，数值见上述 JSON。标题文字、附件和展开编辑入口本身存在；未把预览中的演示身份、示例 placeholder 或“交互预览”提示作为正式需求。

### R9 两项与窄屏操作复测

浏览器直接打开当前 Vite 正式页及确认预览，按相同视口和模拟 API 量测：

| 视口 | 两者 textarea 高度 | 两者输入容器高度 | 两者会话头高度 |
| --- | --- | --- | --- |
| 1920×911 | 85.5625px | 148.5625px | 54px |
| 1000×844 | 85.5625px | 148.5625px | 54px |
| 390×844 | 85.5625px | 142.5625px | 81px |

正式 390px 在模拟已完成回复条件下，“取回文件”“归档到成品库”“查看成品库”的中心点均命中按钮，分别实际打开取回对话框、归档对话框并导航到成品库；证据 `output/playwright/review-r10-mobile-buttons.js`。这仅说明所测状态可操作，不证明所有数据和视口组合。预览移除演示脚注后正式输入区纵坐标不同有明确产品要求，不计上述缺陷。

## Stage 1 · 需求逐项与边界

下列“部分”仅表示列出的代码和特定测试，并非真实生产端到端全部通过。

| 需求 | 本轮证据及状态 |
| --- | --- |
| 新品两入口、替换三入口、成品库一级、超管 Skills 二级 | 部分：`frontend/src/api/hengxin/domestic-workspaces.ts:3-8`、`frontend/src/router/modules/index.ts:12-30`；本轮模拟 API 浏览器打开五条正式路由；管理接口 `backend/app/modules/domestic_studio/management_router.py:26` 依赖 `manage_system`，权限定向测试通过。未用真实身份登录。 |
| 默认留白、无预填提示词和自动发送 | 部分：`frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:15-27` 隐藏空态引导、绑定空输入和手动发送；浏览器空会话、无绑定时禁发及五路由可达。模拟数据不证明真实登录全链。 |
| 会话各自独立，新建、切换、重命名、删除及私有文件 | 部分：`backend/app/modules/domestic_studio/conversation_service.py:29-33,70-105`、`file_service.py:75-81`；隔离 PostgreSQL 会话和 HTTP 测试通过；模拟浏览器测试新建、切换、草稿隔离、删除。未穷尽所有角色和并发时序。 |
| 实名及北京时间，用户在右、Codex 在左 | 部分：`backend/app/modules/domestic_studio/queries.py:22-25,74-92`、`frontend/src/views/shared/studio/StudioTurns.vue:6-7`；模拟张三及 `2026-11-12T09:30:00Z` 显示北京时间 17:30，右侧消息 x=1722.6、左侧 x=506。未用真实用户验证。 |
| 附件、连续对话、结果、单图/批量修改、停止、异常 | 部分：`DomesticWorkspace.vue:15-36,81-105` 复用共享图片/修改组件，`backend/app/modules/domestic_studio/turn_service.py:42-116` 处理发送和停止；本轮定向后端测试与模拟浏览器发送通过，没有独立重新执行真实 Skill、模型、全部标注和停止故障链。 |
| 部分文件保留和手动取回，未知进程保留占用且原节点核实 | 部分：`backend/app/modules/domestic_studio/runner.py:23-38,66-83`、`recovery.py:39-65`；模拟浏览器手动取回成功。未独立穷尽实际节点故障与真实模型运行。 |
| 上传/输出/归档未确认写入凭据、迟到写保护及有界附件 | 部分：`file_service.py:29-70`、`output_intents.py:13-61`、`archive_service.py:214-260`；隔离真实 MinIO 定向迟到写、大图、128 MiB 归档测试通过。未测试实际 500 MB 下载、多并发生产 RSS 或所有远端故障时序。 |
| 五个入口教程且没有正式教程时待补充 | 部分：`DomesticWorkspace.vue:3,33` 用当前入口名和待补充显示；浏览器展开相机入口，未逐一展开其余四个。 |
| 新品按产品名归档，替换服务端拒绝 | 所测路径通过：`backend/app/modules/domestic_studio/policy.py:12-30`、`archive_service.py:124-125`；隔离 HTTP 定向测试及三个替换页面无归档按钮的模拟浏览器检查通过。未枚举全部畸形请求。 |
| 归档独立副本、国内成员共享、源会话私人且删除源后副本仍在 | 部分：`archive_service.py:38-53,164-207`、`conversation_cleanup.py:44-56`；隔离 PG/HTTP 的跨成员与删源后副本测试通过，浏览器归档和删除使用模拟 API。未穷尽并发及真实生产存储故障。 |
| 逐图修改资料、公开过程、真实终态/错误、旧归档 | 部分：`archive_service.py:172-207`、`archive_edits.py:8-38`、`frontend/src/views/hengxin/domestic-studio/library.vue:11,37-46`；本轮隔离 PG 编辑和归档测试通过，未将直接设置数据库状态当成真实失败或取消执行链。 |
| 成品搜索、来源、详情、删除、ZIP 和图片保护 | 部分：`archive_queries.py:33-54`、`archive_router.py:36-98`；本轮隔离归档组覆盖正常及损坏记录，未独立浏览器逐角色测试所有下载/删除故障。ZIP 图片上限和对象校验见源码，不能据此证明全部存储故障可恢复。 |
| 仅超管完整 Skill 文件夹上传、校验、同名确认更新、启停、删除及 ZIP；无版本管理/在线编辑器 | 部分：`management_router.py:26,77-163`、`frontend/src/views/shared/skills/SkillFolderUpload.vue:2-27`、`SkillFolderActions.vue:3-6,38-39` 和国内管理页 `frontend/src/views/hengxin/admin/skills.vue:3-7`。本轮未独立浏览器实操文件夹拖入、同名更新和 ZIP 落盘，也未完整盘点全部页面/API 的漂移。 |
| 五入口固定 Skill、初始空绑定、服务端防绕过/冻结、绑定保护 | 部分：`backend/migrations/versions/0033_domestic_studio_bindings.py:10-26` 未插入初始绑定，`bindings.py:36-82`、`policy.py:33-51`、`turn_service.py:42-80` 有锁、验证和冻结；本轮 PG 绑定与权限组通过。未用真实 Skill 跑模型。 |
| 国内身份、数据库、对象、队列与海外隔离，旧 API/海外行为保持 | 部分：`domestic_studio/router.py:28-29`、`recovery_transport.py:4-14`、`scripts/release/intranet/domestic_studio_wiring.py:42-114`；本轮海外附件定向回归及两业务范围构建通过。未执行全部旧业务、跨业务真实部署和身份测试。 |
| 联合迁移、进程/事务屏障、排空、备份、前向恢复、安装身份和发布台账 | 部分静态核查：`scripts/release/intranet/joint_studio_fence.py:26-60`、`joint_studio_engine.py:33-52,141-157`、`joint_studio_release.py:160-198`、`backend/migrations/env.py:39-47`；本轮没有独立重跑完整真实 Docker 安装及故障矩阵。候选外脚本边界见下。 |
| 确认预览、构建测试、独立双阶段、中文提交和生产验收 | **不通过：M1、M2。** 本轮只完成列明的视觉和定向测试，Stage 2 未执行，尚未提交、联合部署或正式入口验收。 |

## R9 归档附件完整性复核

`backend/app/modules/domestic_studio/archive_router.py:59-67` 对国内归档调用 `deliver(..., verify_content=True)`；`backend/app/overseas/attachment_delivery.py:8-29` 让 HEAD 只核对存储大小并返回元数据，GET 在返回前调用 `image_delivery.original_file`。`backend/app/overseas/image_delivery.py:36-53` 以 8 MiB 内存阈值的临时文件和 `backend/app/execution/bounded_read.py:20-35` 分块校验长度、SHA-256，失败关闭临时文件与存储连接；`backend/app/modules/files/streaming.py:4-24` 在响应结束或断连时关闭响应流。海外调用默认 `verify_content=False`；本轮 `test_overseas_attachment_downloads.py` 覆盖其 HEAD 不打开对象、GET 64 KiB 读取、权限与断连关闭，不能推断海外附件已新增摘要校验。

`backend/tests/test_domestic_archive_integrity_pg.py:88-113` 使用真实 FastAPI 路由、隔离 PG 和存储替身，先读正常附件，再将对象换成同长度字节，断言 GET 503；是人为模拟存储损坏，不表示普通用户可写存储。`backend/tests/test_domestic_archive_large_real_minio_pg.py:32-86` 对隔离真实 MinIO 的 128 MiB 附件测复制与下载摘要，并在响应构造时断言 Python 堆峰值低于 32 MiB；实际消费响应迭代在停止 `tracemalloc` 之后，因此该阈值不是整个下载过程或多并发 RSS 的测量。`backend/tests/test_downloads.py:33-76` 覆盖通用响应在开始前和中途断连关闭；本轮没有复现所有网络故障。

## 本 reviewer 独立测试和编译原始输出

后端在指定 `127.0.0.1:35439/hx_studio_test` 使用随机 schema、`127.0.0.1:35441` 随机 MinIO bucket、`127.0.0.1:35440/15` 隔离 Redis；使用 `/tmp/hengxin-domestic-studio-python/bin/pytest`。`test_domestic_archive_integrity_pg.py`、`test_domestic_archive_large_real_minio_pg.py`、`test_domestic_archive_pg.py`、`test_domestic_archive_edits_pg.py`、`test_domestic_studio_http_pg.py`、`test_overseas_attachment_downloads.py`、`test_downloads.py`：

```text
.............................................                            [100%]
=============================== warnings summary ===============================
../../../../../../tmp/hengxin-domestic-studio-python/lib/python3.14/site-packages/fastapi/testclient.py:1
  /tmp/hengxin-domestic-studio-python/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
45 passed, 1 warning in 41.46s
```

`test_domestic_studio_bindings_pg.py`、`test_domestic_conversations_pg.py`、`test_domestic_turns_pg.py`、`test_domestic_admin_permissions_pg.py`、`test_domestic_late_outputs_real_minio_pg.py`、`test_domestic_image_stream_real_minio_pg.py`：

```text
.....................                                                    [100%]
=============================== warnings summary ===============================
../../../../../../tmp/hengxin-domestic-studio-python/lib/python3.14/site-packages/fastapi/testclient.py:1
  /tmp/hengxin-domestic-studio-python/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
21 passed, 1 warning in 29.48s
```

这些是指定组而非当前快照后端全量；部分测试有存储替身、模拟 CLI 或直接构造状态。测试 fixture 自行清理其随机 schema 和 bucket，不计真实生产验收。

使用 `output/domestic-studio-release-bin/pnpm.cmd` 所指定 pnpm `10.33.4`、Node `v24.18.1`，在 frontend 执行 `run typecheck`，退出码 0，原始输出：

```text
> hengxin-smart-image-frontend@0.2.70 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

分别设置 `VITE_RELEASE_SCOPE=domestic` / `overseas`，执行 `pnpm exec vite build --mode production --outDir ../../output/review-r10-pinned-{domestic,overseas}-dist --logLevel warn`；均退出码 0，原始输出：

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1

(!) outDir D:\Work_Project\hengxin-smart-image\output\review-r10-pinned-domestic-dist is not inside project root and will not be emptied.
Use --emptyOutDir to override.

[plugin vite:reporter]
(!) D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/views/auth/dingtalk-login.vue is dynamically imported by D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/core/ComponentLoader.ts, D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/core/ComponentLoader.ts, D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/routes/staticRoutes.ts but also statically imported by D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/App.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
```

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1

(!) outDir D:\Work_Project\hengxin-smart-image\output\review-r10-pinned-overseas-dist is not inside project root and will not be emptied.
Use --emptyOutDir to override.

[plugin vite:reporter]
(!) D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/views/overseas/OverseasTasksPage.vue is dynamically imported by D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/core/ComponentLoader.ts, D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/views/overseas/OverseasPortal.vue?vue&type=script&setup=true&lang.ts but also statically imported by D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/views/overseas/OverseasPortal.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
```

这是当前工作树构建，输出目录位于项目外且未自动清空，不是提交后固定 Git 包。最初使用全局 pnpm 时提示忽略 package.json 内 `pnpm.overrides` 等；上面列出的是指定 10.33.4 重跑结果。浏览器 `review-r10-desktop-workspaces.js` 在隔离模拟 API 下完成五路由、空输入、禁发、会话草稿、署名时间、取回、归档、删源后模拟资料保留及替换隐藏归档；首次复用已有浏览器会话时因持久草稿断言初始为空失败，清除该隔离浏览器数据并新开后通过。最初把桌面测试直接改成 390px 时等待默认收起的会话栏失败，随后使用专门的 `review-r10-mobile-buttons.js` 完成三按钮实点；这两次夹具失败不计为产品通过证据。

## 候选外发布辅助脚本 · 只读检查

`output/domestic-studio-release-bin/` 不纳入 candidateId。`build_committed.py:12-18,22-59` 检查打包脚本未相对 HEAD 修改，以 HEAD 和三种 scope 打包并校验清单/摘要；`scripts/release/intranet/package_release.py:63-115,213-243` 根据 Git blob 构造来源，非当前脏工作树。当前 HEAD 实测为 `979e099b63cba11cad4bd5c2f057e263a4ef8193`，`git cat-file -e HEAD:hengxin-smart-image/backend/app/modules/domestic_studio/archive_router.py` 报路径不在 HEAD；**目前运行该打包器不会包含本次尚未提交的候选**。脚本不会自行将 Git HEAD 与两阶段批准的 candidateId 绑定，提交并获批后仍须检查 `review-status`、提交树、工具文件和包的实际摘要一致。

`install_committed.py:21-51` 从 HEAD 对工具树逐项比 Git blob；`upload_and_stage.py:38-61` 独占上传、校验再 stage；`run_server_helper.py:32-41` 在运行前拼接 `server_verify_tools.py:10-37` 或 `server_verify_candidate.py:10-39` 检查 manifest、所有权、链接与内容；`server_activate_tools.py:26-59` 在发布锁和空闲台账下切换工具链接。上传、stage、安装和激活不是一个原子步骤，失败须按实际已知资源及台账检查，不可据此假称业务或数据库已回退。本轮只读代码及哈希，未运行生产脚本、未在真实 Docker 安装或切换，亦未独立运行这两个校验器的 Linux 防篡改测试；`packages.json`、`installation.json`、辅助脚本均不受本候选快照保护。

本轮 11 个 `.py` 的 SHA-256 与 R7 报告记录相同；`pnpm.cmd` 为 `B873B4296853A898463093B3176F9ECD891838F67A3A63A5A2375B707D165700`。哈希一致不是生产安装安全或候选批准证明。未验证真实部署中间态、当前包、安装树及服务状态。

## Stage 2 与真实局限

**Stage 2 未执行。** Stage 1 未通过，因此未系统执行代码质量、完整安全扫描、测试真实性全面审计及正式页与邻居基准页的视觉对比。上述局部源码、测试和候选外脚本检查不能称为 Stage 2 PASS。没有完成真实钉钉身份、真实 Skill/模型、全部后端全量、真实生产 Docker 安装或正式入口验收；主 Agent 先修复并重新 `review-prepare`，不得用此报告 `review-approve` 或将旧结论套到新快照。
