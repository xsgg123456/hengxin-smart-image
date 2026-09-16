# VPS 开发测试部署

## 当前范围

当前文件描述 Phase 14.1 的 VPS 开发测试环境。目标主机为 Ubuntu 24.04 x86_64，主机名 `racknerd-058889d`。环境使用独立 Compose 项目 `hengxin-vps-staging`、独立数据库/Redis/MinIO 数据卷和独立运行目录，复用 VPS 上的 1Panel 但不接管 80/443。

该环境关闭 fixture，使用 VPS 上 `codex` 用户运行原生 Codex Worker。当前继续作为开发测试环境，已开始接入 `zhitu.qhhengxin.top` 域名和 HTTPS，钉钉真实登录仍需开放平台配置后联调。

## 目录与服务

- 应用目录：`/opt/hengxin-smart-image`
- API：Compose 内部服务，宿主机仅绑定 `127.0.0.1:18008`
- 前端：Compose 内 Nginx，宿主机绑定 `0.0.0.0:18080`，通过 VPS 公网 IP 访问
- PostgreSQL：宿主机 `127.0.0.1:15433`
- Redis：宿主机 `127.0.0.1:16388`
- MinIO API/Console：宿主机 `127.0.0.1:15900/15901`
- Codex Worker：`hengxin-vps-codex-worker.service`
- Skill：`/opt/hengxin-smart-image/infra/runtime/skills`
- 会话与执行材料：`/opt/hengxin-smart-image/infra/runtime/execution`
- Codex 认证：`/home/codex/auth/auth.json`，只允许 `codex` 读取

## 域名入口

- 域名：`zhitu.qhhengxin.top`
- DNS：A 记录指向 `107.172.161.139`
- 应用入口：OpenResty 反向代理到 `127.0.0.1:18080`
- HTTPS 证书：由 VPS 上的 acme.sh 申请并安装到 1Panel OpenResty
- 钉钉首页：`https://zhitu.qhhengxin.top/`
- 钉钉回调：`https://zhitu.qhhengxin.top/api/v1/auth/dingtalk/callback`

## 首次部署

在项目根目录先构建正式前端：

```powershell
cd hengxin-smart-image/frontend
pnpm install --frozen-lockfile
pnpm build
```

将当前项目代码、`frontend/dist` 和 `infra` 发布配置同步到 VPS；不要同步 `.env`、认证文件、`node_modules`、测试输出和本地数据库。

在 VPS 的 `infra/.env` 写入随机数据库/MinIO 密钥。开发测试环境使用：

```text
APP_ENV=development
ENABLE_FIXTURE_EXECUTOR=false
ENABLE_CODEX_EXECUTOR=true
ENABLE_DEV_IDENTITY=false
GENERATION_CONCURRENCY=1
```

准备运行目录后启动基础服务：

```bash
cd /opt/hengxin-smart-image/infra
mkdir -p runtime/skills runtime/execution
docker compose -f compose.yaml -f compose.vps.yaml build api
docker compose -f compose.yaml -f compose.vps.yaml run --rm --no-deps migrate
docker compose -f compose.yaml -f compose.vps.yaml up -d postgres redis minio api outbox web
```

原生 Worker 使用后端锁文件安装依赖，安装后再启用服务：

```bash
cd /opt/hengxin-smart-image/backend
uv sync --locked --no-dev --no-install-project
install -o root -g root -m 0644 ../infra/hengxin-worker.vps.service /etc/systemd/system/hengxin-vps-codex-worker.service
systemctl daemon-reload
systemctl enable --now hengxin-vps-codex-worker.service
```

## 检查与回滚

```bash
curl -fsS http://127.0.0.1:18008/api/v1/health/ready
curl -fsS http://127.0.0.1:18080/
docker compose -f compose.yaml -f compose.vps.yaml ps
systemctl status hengxin-vps-codex-worker.service --no-pager
```

公网及钉钉联调必须保持 `ENABLE_DEV_IDENTITY=false`（2026-09-16 已关闭并验证匿名请求返回 401）。仅限本机开发的测试身份环境还应把 `.env` 的 `WEB_BIND` 改成 `127.0.0.1`，再通过 SSH 隧道访问。Windows PowerShell 示例：

```powershell
ssh -N -L 18080:127.0.0.1:18080 -i <部署密钥路径> codex@107.172.161.139
```

保持隧道窗口运行后可打开 `http://127.0.0.1:18080/`。钉钉联调使用 `https://zhitu.qhhengxin.top/`；无会话先进入登录页，不再自动使用 VPS 测试身份。

停止或回滚本项目时只操作本 Compose 项目和 Worker：

```bash
systemctl disable --now hengxin-vps-codex-worker.service
docker compose -f compose.yaml -f compose.vps.yaml down
```

不要使用 `docker compose down -v`，以免删除该环境的数据库、对象存储和队列数据。VPS 上已有的 1Panel、Affine、Zentao、MaxKB、ZAI 等项目不属于本部署范围。

## 当前限制

- 18080 仍是内部开发测试入口；公网访问统一使用 `https://zhitu.qhhengxin.top/`。
- 开发身份用于继续联调，Phase 12.2 的钉钉真实登录仍未完成。
- VPS 初始没有 Codex CLI、认证和业务 Skill，需要安装并验证后才能执行真实生图。
- 本任务只建立可回滚的开发测试环境；备份恢复、日志轮转、失败告警、三个真实 Skill 全量验收和 20/100 用户容量测试仍需后续 Phase 14 任务完成。

## 2026-09-15 部署记录

- VPS 基础部署成功；API readiness 返回 200，公网前端入口返回 200。当前前端通过 `0.0.0.0:18080` 暴露，便于跨设备开发测试；开发测试超管身份只适用于内测。
- 迁移已到 `0009`；原生 Worker `hx-vps-codex` 的 Celery ping 为 OK，心跳依赖 `cli/isolation/authenticationConfigured` 均为 true。
- 壁纸 Skill `jd-main-image-wallpaper-camera-swap` 1.0.1 已通过系统上传、安装并设为默认。
- 真实冒烟任务已完成排队、执行和结果校验链路，检测到 1 张新图后由 Skill 以 `SKILL_DIMENSION_MISMATCH` 失败；该结果与此前本地已知尺寸限制一致，不能将该 Skill 冒烟记为业务成功。
- `zhitu.qhhengxin.top` DNS 已解析到 `107.172.161.139`；1Panel OpenResty 已配置反向代理和 Let’s Encrypt 证书，HTTP 自动跳转 HTTPS，公网首页和 API readiness 均返回 200。
