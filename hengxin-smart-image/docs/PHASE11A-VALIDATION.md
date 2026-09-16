# Phase 11A 开发机真实 CLI 联调记录

日期：2026-09-11。最新状态：真实串行、同会话返工、归档、双任务并行及故障恢复验收已通过，独立收尾审查 Stage 1 / Stage 2 均 PASS，待用户验收。最新证据见 [PHASE11A-CLOSEOUT-RESULTS.md](PHASE11A-CLOSEOUT-RESULTS.md)。下文为此前网络与首次失败的历史记录，其中“尚未通过”描述当时状态。

## 本轮网络修复

- 用户同意后在 Windows `.wslconfig` 启用 networkingMode=mirrored、autoProxy=true、dnsTunneling=true，并重启 WSL。Docker Desktop stop 命令超时，但随后启动成功；核对重启前运行清单，缺失容器数为 0，业务 API HTTP 200。
- 沙箱只接收显式开发配置的 loopback HTTP(S) 代理，拒绝生产环境、远端代理、代理认证信息及额外路径/查询；不继承宿主其它变量。
- 使用实际 prepare_workspace / sandbox_command 运行 Linux CLI exec，请求模型回复 NETWORK_OK，验证结果 modelReplyVerified=true、exitCode=0。网络、认证、沙箱内模型调用均已成功。
- 首轮代理针对性测试22 passed；独立审查发现裸配置键可能继承宿主代理，已改为空值也显式清除继承，并新增缺失/裸键/空值3个回归用例。前端 typecheck 退出0、60 tests passed。
- 修复后 WSL 后端完整 `python -m pytest -q -p no:cacheprovider`：389 passed、39 skipped、10 warnings；跳过项和既有警告的限制同下文。
- 专用双图真实任务 `c26ce47c-bc48-42dd-81b6-ae312f8ddf86`，轮次 `94a7d4eb-6180-4650-ad19-e19eb655f87a`，session `01a08f61-30b5-7d00-b9e7-0f4f8afea599`，执行来源cli。
- 模型实际调用原生图像工具并生成文件。首次两张均1254×1254；重试后仍未满足模板800×800。绑定Skill禁止通过缩放、裁切或补边修正尺寸，因此CLI明确将两项写为失败。平台最终状态失败，未发布图片。网络与真实图像工具链路已验证，业务图片验收未通过，不能用这些图片冒充成功。
- 用户随后确认跳过尺寸问题：本阶段将其记录为已知限制，后续专用测试明确不验收尺寸一致性，使用原生输出继续验证返工、归档和并行，不再以解决尺寸问题为前置条件。已有失败记录不改写，上传Skill与生产规则不变；未完成的其他验收仍保持未验证。
- 收尾重启真实 Worker 加载最终配置，controller start PASS、status 为 active；前端开发服务重新启动，页面与后端 API 均 HTTP 200。当前保持真实 CLI 模式，未切回 fixture。
- 最终完整14项代码候选经独立审查 Stage 1 PASS / Stage 2 PASS，报告见 [PHASE11A-PROXY-FINAL-REVIEW.md](PHASE11A-PROXY-FINAL-REVIEW.md)。网络修复验收通过，完整Phase11A业务验收仍未通过。

## 已得到的真实证据

| 项目 | 结果 |
| --- | --- |
| WSL 非 root 执行环境 | Ubuntu 24.04.4、Python 3.12.3、bubblewrap 0.9.0 |
| 官方 Linux CLI | 0.153.4，下载包 SHA512 与 npm registry 一致 |
| 登录状态 | 独立 auth.json 下 `login status` 成功；不等于联网生成通过 |
| 任务沙箱 | 通过现有 prepare_workspace / sandbox_command 实际运行 `codex --version` |
| 后端任务派发 | API/Outbox 切换 cli 模式，WSL Celery Worker 消费专用任务 |
| 会话创建 | 下列真实任务已返回 Codex session ID |
| 取消与进程回收 | 通过 API 取消专用测试任务，round/job=cancelled，attempt=finished、exit_code=-15；检查无残留 CLI 进程 |

## 真实任务

- Skill：`ecommerce-wallpaper-swap` 1.0.0，绑定版本 ID `4ba74790-3563-4e33-8696-dede2ce31a9b`，API 目录状态 available。
- 从用户「换壁纸」模板取前两张图建立专用模板「Phase11A 真实CLI双图测试」，使用同一张原始素材。
- 任务：`1cf398ac-7dfd-459b-8933-e52af564346e`。
- 轮次：`980aa92c-926c-4cbf-92a7-a6b9a9ede987`。
- session：`01a08ea0-174f-75e3-8d8e-10eb37bd7d3d`。
- 执行来源：cli；记录的 Linux PID：568。
- stderr 显示连接 `wss://chatgpt.com/backend-api/codex/responses` 被重置，另有 MCP 请求失败。没有生成成品，不能计为生成通过。
- Windows 使用 `127.0.0.1:7890` 本机代理，WSL 无法连接该端点。创建本机转发的操作被自动审批拒绝，返回 `blocked by policy`；未创建转发，等待用户提供可用网络配置。

## 尚未通过的阶段验收

真实生成及图片有效性、单图和整套返工、同会话 resume、下载和归档、两个真实任务并行及资源隔离、完整故障回归。上述项目均不以 fixture 结果替代。原有用户任务与已生成文件保持保留。

## 本轮自动化回归

- WSL 后端执行 `python -m pytest -q -p no:cacheprovider`：374 passed、39 skipped。跳过项包括需要独立 PostgreSQL 等环境的集成测试，不能算为已通过。10 条警告为已有依赖弃用和 SQLAlchemy 空主键提示。
- Windows 执行三个 `test_local_codex*.py` 测试文件：64 passed（审查修复后，含错误项目端口拒绝用例）。
- 前端固定 Node 24.18.1 / pnpm 10.33.4，`pnpm typecheck` 退出 0；`pnpm test`：60 passed、0 failed。
- 控制脚本真实 `check`：`PASS local configuration, ownership, CLI sandbox/auth preflight and idle database; no model call`。
- 控制脚本真实 `fixture`：`PASS fixture; existing task records and data volumes retained`；随后 `status` 显示 WSL Worker inactive、API/Outbox/容器 Worker 运行，前端 HTTP 200。演示服务已恢复。
- 模块拆分后真实 `start`：`PASS start; existing task records and data volumes retained`，包括 WSL Celery 节点定向 ping 就绪检查；随后再次执行 `fixture` 恢复演示服务。
- 审查修复后再次执行两次真实 `start`，重复启动时 MainPID 从 2512 变为 2787，证实 Worker 重启而非沿用旧进程。审查指出的连接端口归属问题已增加 PostgreSQL/MinIO/Redis 实际发布端口检查；独立复审结论见 [PHASE11A-INFRA-REVIEW.md](PHASE11A-INFRA-REVIEW.md)。
- 最终复审：本轮基础设施 Stage 1 PASS、Stage 2 PASS；完整阶段仍因模型网络 BLOCKED。最终 `fixture` 返回 PASS，`status` 确认 WSL Worker inactive、六个 Compose 服务运行，Skill 目录 API 与前端均 HTTP 200。
