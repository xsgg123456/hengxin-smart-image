# 开发交接 · 2026-09-16

最新前端热修 `ui-20260922-b086a49` 已上线：三类图片处理菜单每次新建，旧任务在任务中心查看。源码`b086a49`，验证与回滚见 [菜单修复发布记录](NEW-TASK-MENU-20260922.md)。后端、Worker及数据库保持不变。

## 最新交接 · 2026-09-22

前端发布 `ui-20260922-c837abf`（源码提交`c837abf`），后端基线 `light-skills-20260921-f02b1e0`、迁移0014。正式前端是 `frontend/`；旧独立原型已清理，显式Demo保留在同一源码供本机验证。125项前端单测、类型、生产构建和隔离浏览器交互通过，线上文件哈希/健康/匿名登录页通过；登录后真实业务本轮未复测。发布、备份和回滚见 [UI发布记录](UI-RELEASE-20260922.md)。下面历史“当前生产”段落按其日期阅读，不能覆盖本段。

当前并发已按用户授权改为5：Worker实测5子进程、API容量5、后台配置版本3并发5。尚待用户提交五个新任务压测，见 [配置记录](CONCURRENCY-5-20260917.md)。

最新生产补丁：`skill-name-20260917-79892f0`，新任务播报完整显示绑定Skill名称，其他敏感信息继续过滤。66项测试、两阶段审查及线上核验通过，历史脱敏记录不回填。见 [发布记录](SKILL-NAME-DISPLAY-DEPLOYMENT.md)。

当前生产：2026-09-17 `final-reply-20260917-59d22f5`。两个业务 Skill 原样保留；简洁 `$Skill名称` 提示词、任务私有发现目录、修复成品收取及新旧执行恢复协议已上线。全量后端711项和Linux专项76项通过，独立两阶段复审 PASS；生产哈希、健康、Skill隔离探针和四张真实成品收取核验通过。网页新任务完整生成尚待验收，见 [发布记录](FINAL-REPLY-DELIVERY-DEPLOYMENT.md) 和 [验证记录](FINAL-REPLY-DELIVERY-VALIDATION.md)。下文发布标识为历史记录。

最新生产模型更新：`model-20260917-0bb0454`，新任务和返工固定 `gpt-6-astra / high`。备份、验证与边界见 [ASTRA-HIGH-DEPLOYMENT.md](ASTRA-HIGH-DEPLOYMENT.md)。

## 2026-09-17 当前部署

人工维护本地 Skill、后台登记及自然语言提示词已部署。发布 `skills-20260917-1d611e9`、迁移0012，完整 Skill 在任务内 `/work/skills/{标识}/`。两个壁纸 Skill 均启用，普通版1.0.2为默认，优化版1.0.0可绑定。用户授权的旧测试历史及旧版本已备份并清理，需重新创建测试模板。

生产检查通过，尚未进行真实收费换图；依赖审计 critical 已修复，其他级别告警保留。详情与备份见 [发布记录](RELEASE-LOCAL-SKILLS-20260917.md)。本轮按用户授权提交 Git，精确提交号记录到服务器 RELEASE.json。用户确认张帅登录正常，下面50002记录仅为历史，不再作为当前阻塞。

## 先读与历史基线（2026-09-16）

仓库根目录是 Git 根；业务代码在 `hengxin-smart-image/`。先读根目录 [DEV-PLAN](../../DEV-PLAN.md) 当前交接状态，再读 [Product-Spec](../../Product-Spec.md)、[Design-Brief](../../Design-Brief.md)。历史 PHASE/REVIEW 文档只证明当时范围，不等于全部产品完成。

- 已推送 main：`d2e5076`。当前业务分支 `codex/management-monitor-settings` 基线 `99ff375`，是否已推送请以 Git 为准。
- VPS：<https://zhitu.qhhengxin.top/>，业务代码已更新至 `99ff375`；这是开发测试环境，不是完成生产验收。
- 前端、API/Outbox 和原生 Worker 已更新；数据库迁移 `0011`。
- 本轮已提交并部署 13.2/13.3 与钉钉容器免登修复。未创建收费生图任务。未开启开发身份。

## 已有能力与缺口

| 范围 | 当前事实 | 接手验收边界 |
|---|---|---|
| Phase 1–11 | 文件、模板/Skill、异步任务、返工、下载归档已按历史范围验收 | 不是三种真实 Skill 的效果验收 |
| 11A | 开发机 WSL 真实 CLI；用户已确认双任务并发 2 | VPS 当前并发 1，未做同等并发/容量验收 |
| 12.1 | 服务端会话、退出、角色/成员管理已实现 | 新成员待授权，不按首个登录者自动授予管理员 |
| 12.2 | 浏览器 OAuth 与 PC 容器免登已部署；JSAPI 改为 npm 包，免登码走 `getuserinfo`；state 浏览器绑定与失败防重放在线验证通过 | 真实双端登录及业务闭环仍未完成 |
| 13.1 | `/management/usage` 真实接口、相关测试及集成审查通过，已部署 | 用真实主管/普通成员联调权限、筛选与统计 |
| 13.2/13.3 | `/management/monitor`、`/management/settings` 真实接口已部署，迁移 `0011` | 用真实角色联调监控与配置；不把页面存在或 401 当成业务验收 |
| 14 | VPS、HTTPS、专用 CLI Worker 已部署 | 三类 Skill、双端、备份恢复/日志告警、20/100 用户容量验收尚缺 |

后端 `app/contracts/router.py` 还有 `/workspace` 等契约占位；`app/main.py` 先注册真实模块再注册契约，判断接口状态需同时看注册顺序。任务详情执行进度已经实现，与管理中心全局监控是两件事。

## 当前优先级

1. **历史已解除的张帅授权阻塞**（用户已确认正常登录）：两名初始管理员吴永杰、张帅的企业 userId 已写入 VPS；2026-09-16 实际 API 查询，吴永杰返回 0，张帅返回 `50002：请求的员工userid不在授权范围内`。企业管理员需补通讯录授权范围，并确认应用可见范围。不要改角色、关闭企业校验或开启开发身份来绕过。
2. **完成 12.2 实机验收**：Chrome/Edge 与钉钉 PC，同一用户映射、首次/再次登录、退出/过期、待授权/禁用、四角色、上传/任务/返工/下载/归档；记录结果。当前没有完整通过证据。
3. **完成 13.1–13.3 真实角色联调**：按 Spec 第 13 节，用真实主管/普通成员验证统计、监控和系统配置，沿用现有 Art 组件，不重写业务页面。
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
- 当前 API/Outbox 镜像 `hengxin-smart-image-backend:99ff375`；服务端 `.env` 的 APP_IMAGE 已同步。VPS 生成并发 1、fixture 关闭、开发身份关闭。
- 本次部署备份 `/opt/hengxin-backups/99ff375/`（root 受限目录）及前端 `frontend/backups/`。旧镜像标签保留 `d2e5076`、`container-auth-20260916`。备份不是数据库/MinIO/会话全量备份。完整恢复演练仍待做。
- Git push 不自动部署。此次通过归档上传、镜像构建和切换完成，不能假定 VPS 工作目录是 Git checkout 后直接 git pull。
- 申请自己的 SSH 公钥访问和 sudo 权限，不依赖原开发者 Windows 私钥路径。操作仅限本项目，不改动 VPS 上其他应用。

详细命令、回滚和 Nginx 重载见 [DEPLOYMENT](DEPLOYMENT.md)；钉钉字段与验收矩阵见 [DINGTALK-SETUP](DINGTALK-SETUP.md)。

## 验证证据与开发流程

- 本机 13.2/13.3 最终候选：后端639 passed/95 skipped、前端100 tests、Node24.18.1类型检查及构建通过；独立两阶段审查通过。[本机验证记录](PHASE13-MANAGEMENT-LOCAL-VALIDATION.md)区分了隔离测试、本机实际服务和未做的真实业务验收。
- d2e5076 提交前全量后端：540 passed、133 skipped；最终 state 修复后认证专项 16 passed。不能合并数字称最终全量全部通过；跳过项包含 Linux/数据库环境要求。
- 前端 89 tests、类型检查通过；部署时正式 Vite build 成功。真实双端登录未据此验收。
- 独立审查：[PUSH-INTEGRATION-REVIEW](PUSH-INTEGRATION-REVIEW.md)、[DINGTALK-CALLBACK-REVIEW](DINGTALK-CALLBACK-REVIEW.md)、[LOGOUT-REVIEW](LOGOUT-REVIEW.md)。
- 线上：readiness 200、匿名 auth/me / monitor / settings 401、钉钉配置 200；无浏览器绑定回调被拒绝、失败 state 重放被拒绝；Worker active；Alembic `0011`。尚未在本次发布后重新跑真实生图。
- `output/` 原始日志及部分旧报告未跟踪，换机器不会随克隆获得；不要为补链接把含业务素材/凭据的整个目录提交。当前关键集成报告在 docs 中。

常规自检：后端 `uv sync --locked`、`uv run pytest -q`；前端 `pnpm test`、`pnpm typecheck`、`pnpm build`。需要数据库集成时按 BACKEND-DEVELOPMENT 建独立测试数据库，不对线上数据运行测试。

遵守根 AGENTS.md：先更新对应需求/计划，代码变更通过独立两阶段审查与快照凭据再提交；提交信息用中文。文档修订不等于业务阶段验收通过。
