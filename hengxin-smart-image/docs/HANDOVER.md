# 开发交接 · 2026-09-16

## 先读与基线

仓库根目录是 Git 根；业务代码在 `hengxin-smart-image/`。先读根目录 [DEV-PLAN](../../DEV-PLAN.md) 当前交接状态，再读 [Product-Spec](../../Product-Spec.md)、[Design-Brief](../../Design-Brief.md)。历史 PHASE/REVIEW 文档只证明当时范围，不等于全部产品完成。

- 已推送 main：`d2e5076`。本次交接文档是该代码基线之后的文档修订，是否已推送请以 Git 为准。
- VPS：<https://zhitu.qhhengxin.top/>，业务代码已更新至 d2e5076；这是开发测试环境，不是完成生产验收。
- 前端、API/Outbox 和原生 Worker 已更新；数据库迁移 `0010`。后端跟踪文件已逐一校验与该提交一致。
- 此次交接只修订文档，不修改业务代码、运行配置或创建收费生图任务。

## 已有能力与缺口

| 范围 | 当前事实 | 接手验收边界 |
|---|---|---|
| Phase 1–11 | 文件、模板/Skill、异步任务、返工、下载归档已按历史范围验收 | 不是三种真实 Skill 的效果验收 |
| 11A | 开发机 WSL 真实 CLI；用户已确认双任务并发 2 | VPS 当前并发 1，未做同等并发/容量验收 |
| 12.1 | 服务端会话、退出、角色/成员管理已实现 | 新成员待授权，不按首个登录者自动授予管理员 |
| 12.2 | 浏览器 OAuth 与 PC 入口已实现、已部署；state 浏览器绑定与失败防重放在线验证通过 | 真实双端登录及业务闭环仍未完成 |
| 13.1 | `/management/usage` 真实接口、相关测试及集成审查通过，已部署 | 用真实主管/普通成员联调权限、筛选与统计 |
| 13.2/13.3 | 前端和契约已有；`/management/monitor`、`/management/settings` 后端返回 501 | 实现真实监控、参数校验/持久化/审计；不能把页面存在当作后端完成 |
| 14 | VPS、HTTPS、专用 CLI Worker 已部署 | 三类 Skill、双端、备份恢复/日志告警、20/100 用户容量验收尚缺 |

后端 `app/contracts/router.py` 还有 `/workspace` 等契约占位；`app/main.py` 先注册真实模块再注册契约，判断接口状态需同时看注册顺序。任务详情执行进度已经实现，与尚未实现的管理中心全局监控是两件事。

## 当前优先级

1. **解决张帅授权范围**：两名初始管理员吴永杰、张帅的企业 userId 已写入 VPS；2026-09-16 实际 API 查询，吴永杰返回 0，张帅返回 `50002：请求的员工userid不在授权范围内`。企业管理员需补通讯录授权范围，并确认应用可见范围。不要改角色、关闭企业校验或开启开发身份来绕过。
2. **完成 12.2 实机验收**：Chrome/Edge 与钉钉 PC，同一用户映射、首次/再次登录、退出/过期、待授权/禁用、四角色、上传/任务/返工/下载/归档；记录结果。当前没有完整通过证据。
3. **完成 13.1 真实角色联调，然后实现 13.2、13.3**：按 Spec 第 13 节，分别实现真实监控和系统配置审计，沿用现有 Art 组件，不重写业务页面。
4. **完成 Phase 14**：治理 Skill 输出尺寸/清单问题，验证三类真实 Skill、会话恢复、备份恢复与负载。既有壁纸失败不能直接归因成平台或 Skill 的某一处代码 bug，需保留输入、提示词、候选图、清单和验证证据逐项对照。

任务工作区 Skill 自动安装阶段已按用户要求撤销，不要擅自恢复该方案。保持当前冻结包/版本及隔离规则，方案变化先更新需求与计划。

## 接手运行

前端工具版本由 `frontend/package.json` 固定：Node 24.18.1、pnpm 10.33.4。不要依赖原开发者全局工具或 node_modules。仓库不包含模板/素材/Skill 业务包、数据库、认证和 `.env`，另行通过受控渠道交接。

```powershell
# 仓库根目录
cd hengxin-smart-image/frontend
pnpm install --frozen-lockfile
pnpm dev       # 纯 mock，刷新重置，不调用真实后端
# 停止上一个前端进程后再运行：
pnpm dev:api   # 真实 HTTP，默认 API 127.0.0.1:8008
```

两种前端共用 3008，不能同时占用。新机器 fixture 后端见 [BACKEND-DEVELOPMENT](BACKEND-DEVELOPMENT.md)；注意只有显式 test 配置才运行 fixture。Windows + WSL 真实生图按 [LOCAL-CODEX-DEVELOPMENT](LOCAL-CODEX-DEVELOPMENT.md) 配置依赖后，在根目录执行：

```powershell
./hengxin-smart-image/infra/start_local_codex.ps1 -Action check
./hengxin-smart-image/infra/start_local_codex.ps1 -Action start
./hengxin-smart-image/infra/start_local_codex.ps1 -Action status
# 需要恢复本地 fixture 时：
./hengxin-smart-image/infra/start_local_codex.ps1 -Action fixture
```

这些脚本面向配置完成的 Windows/WSL，不能直接在 VPS 运行。切换前要求没有非终态任务；不得强行中断未知任务。

## VPS 与凭据交接

- 主机 `107.172.161.139`，应用 `/opt/hengxin-smart-image`；Compose 工作目录 `infra`，项目 `hengxin-vps-staging`。
- 运行配置 `infra/.env`；原生 Worker 环境 `/etc/hengxin-smart-image/worker.env`；CLI 认证 `/home/codex/auth/auth.json`。通过有权限的管理员交接，不提交 Git、不复制到文档或聊天。
- systemd 单元 **`hengxin-vps-codex-worker.service`**，执行用户 codex。不是 `hengxin-worker.service`。
- 当前 API/Outbox 镜像 `hengxin-smart-image-backend:d2e5076`；服务端 `.env` 的 APP_IMAGE 已同步。VPS 生成并发 1、fixture 关闭、开发身份关闭。
- 本次部署备份 `/opt/hengxin-backups/d2e5076/`（root 受限目录），包含旧源码/前端和旧环境配置，不是数据库/MinIO/会话全量备份。完整恢复演练仍待做。
- Git push 不自动部署。此次通过归档上传、镜像构建和切换完成，不能假定 VPS 工作目录是 Git checkout 后直接 git pull。
- 申请自己的 SSH 公钥访问和 sudo 权限，不依赖原开发者 Windows 私钥路径。操作仅限本项目，不改动 VPS 上其他应用。

详细命令、回滚和 Nginx 重载见 [DEPLOYMENT](DEPLOYMENT.md)；钉钉字段与验收矩阵见 [DINGTALK-SETUP](DINGTALK-SETUP.md)。

## 验证证据与开发流程

- d2e5076 提交前全量后端：540 passed、133 skipped；最终 state 修复后认证专项 16 passed。不能合并数字称最终全量全部通过；跳过项包含 Linux/数据库环境要求。
- 前端 89 tests、类型检查通过；部署时正式 Vite build 成功。真实双端登录未据此验收。
- 独立审查：[PUSH-INTEGRATION-REVIEW](PUSH-INTEGRATION-REVIEW.md)、[DINGTALK-CALLBACK-REVIEW](DINGTALK-CALLBACK-REVIEW.md)、[LOGOUT-REVIEW](LOGOUT-REVIEW.md)。
- 线上：readiness 200、匿名 auth/me 401、钉钉配置 200；无浏览器绑定回调被拒绝、失败 state 重放被拒绝；Worker ready。尚未在本次发布后重新跑真实生图。
- `output/` 原始日志及部分旧报告未跟踪，换机器不会随克隆获得；不要为补链接把含业务素材/凭据的整个目录提交。当前关键集成报告在 docs 中。

常规自检：后端 `uv sync --locked`、`uv run pytest -q`；前端 `pnpm test`、`pnpm typecheck`、`pnpm build`。需要数据库集成时按 BACKEND-DEVELOPMENT 建独立测试数据库，不对线上数据运行测试。

遵守根 AGENTS.md：先更新对应需求/计划，代码变更通过独立两阶段审查与快照凭据再提交；提交信息用中文。文档修订不等于业务阶段验收通过。
