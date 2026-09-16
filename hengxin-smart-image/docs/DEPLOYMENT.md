# VPS 开发测试部署

## 当前范围

当前文件描述 Phase 14.1 的 VPS 开发测试环境。目标主机为 Ubuntu 24.04 x86_64，主机名 `racknerd-058889d`。环境使用独立 Compose 项目 `hengxin-vps-staging`、独立数据库/Redis/MinIO 数据卷和独立运行目录，复用 VPS 上的 1Panel 但不接管 80/443。

该环境关闭 fixture，使用 VPS 上 `codex` 用户运行原生 Codex Worker。当前继续作为开发测试环境，已接入域名和 HTTPS，后端基线仍为 d2e5076 / 迁移 0010；前端已热修钉钉 JSAPI（入口 `index-DePrnCPO.js`）。钉钉真实双端登录待验收。

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
docker compose -f compose.yaml -f compose.vps.yaml up -d --wait postgres redis minio
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
- VPS 开发身份已关闭；张帅通讯录范围返回 50002，双端实测未完成。
- VPS 已安装 Codex CLI、专用认证和壁纸 Skill，真实执行已触发；该次 Skill 尺寸失败不能记为业务成功。
- 本任务只建立可回滚的开发测试环境；备份恢复、日志轮转、失败告警、三个真实 Skill 全量验收和 20/100 用户容量测试仍需后续 Phase 14 任务完成。

## 2026-09-15 部署记录（历史，以后续更新为准）

- VPS 基础部署成功；API readiness 返回 200，公网前端入口返回 200。当前前端通过 `0.0.0.0:18080` 暴露，便于跨设备开发测试；开发测试超管身份只适用于内测。
- 迁移已到 `0009`；原生 Worker `hx-vps-codex` 的 Celery ping 为 OK，心跳依赖 `cli/isolation/authenticationConfigured` 均为 true。
- 壁纸 Skill `jd-main-image-wallpaper-camera-swap` 1.0.1 已通过系统上传、安装并设为默认。
- 真实冒烟任务已完成排队、执行和结果校验链路，检测到 1 张新图后由 Skill 以 `SKILL_DIMENSION_MISMATCH` 失败；该结果与此前本地已知尺寸限制一致，不能将该 Skill 冒烟记为业务成功。
- `zhitu.qhhengxin.top` DNS 已解析到 `107.172.161.139`；1Panel OpenResty 已配置反向代理和 Let’s Encrypt 证书，HTTP 自动跳转 HTTPS，公网首页和 API readiness 均返回 200。

## 2026-09-16 更新与可回滚操作

业务源码基线 `d2e5076`；API 和 Outbox 镜像 `hengxin-smart-image-backend:d2e5076`，原生 Worker 同步源码并重启，前端正式构建已覆盖部署，迁移为 `0010`。APP_IMAGE 已写入 infra/.env。服务健康、匿名 auth/me 401、配置接口 200；浏览器 state 绑定和失败防重放在线验证通过。真实双端授权和本次更新后生图未验收。

此次源码归档上传部署，不假定服务器目录是 Git checkout。下次更新应先构建明确提交的产物，检查无凭据/数据文件，确认没有非终态任务，备份旧源码、前端和配置，再暂停本项目 outbox/Worker，替换源码并构建新标签镜像；依赖锁变化时还要同步原生 Worker 的 venv。不要覆盖线上 .env 或认证。

在 infra/.env 中设置已构建的新 APP_IMAGE 后，执行：

```bash
cd /opt/hengxin-smart-image/infra
docker compose -f compose.yaml -f compose.vps.yaml run --rm --no-deps migrate
docker compose -f compose.yaml -f compose.vps.yaml up -d --no-deps api outbox
systemctl restart hengxin-vps-codex-worker.service
# 等待 API healthy，再重载 Nginx，避免继续连接重建前的 API 容器地址：
docker inspect --format '{{.State.Health.Status}}' hengxin-vps-staging-api-1
docker exec hengxin-vps-staging-web-1 nginx -s reload
curl -fsS https://zhitu.qhhengxin.top/api/v1/health/ready
```

本次备份在 `/opt/hengxin-backups/d2e5076/`：before.tar.gz 是切换前后端源码/前端/Dockerfile，infra.env 是切换前受限配置；build.log 是构建记录。备份不包含数据库、MinIO 和 CLI 会话材料，不能据此宣称灾难恢复验证完成。

本次没有新增数据库迁移，回滚时先确认无未结束任务，再停止本项目 outbox、API 和原生 Worker；恢复该备份中的源码和前端及 infra.env（权限 600），保留数据卷，重新启动 api/outbox 和 Worker，API healthy 后重载 web Nginx。旧 API 标签为 callback-fix-20260916。未来有新迁移时必须先评估数据兼容性，不能机械照搬此次回滚。

执行 `down` 只是停止服务，不是版本回滚；禁止用 `down -v` 清空数据。运维权限由管理员给接手同事单独授权，不共享原开发者私钥。

## 2026-09-16 JSAPI 前端热修（仅 dist）

钉钉 PC 容器原先走 CDN `dingtalk-jsapi/2.15.15`，该地址 404。本次只覆盖 `/opt/hengxin-smart-image/frontend/dist`，入口脚本改为 `index-DePrnCPO.js`，随包带 npm `dingtalk-jsapi` 3.2.9；未部署 13.2/13.3、未跑迁移 0011、未改 API 镜像、未开开发身份。

旧前端备份：`/opt/hengxin-smart-image/frontend/backups/dist.bak-20260916-180845.tar.gz`。回滚只解该包覆盖 `frontend/dist`，不要动 `.env` 和后端。公网首页与 JS 资源已 200；普通浏览器仍走网页授权，钉钉工作台需关掉重开后再点「重新授权」。

## 2026-09-16 容器免登换码热修

钉钉 PC 容器 JSAPI 已能拿到免登码后，后端仍用网页 OAuth 的 `userAccessToken` 换码，钉钉拒绝后返回「钉钉认证服务暂不可用」。已改为 `topapi/v2/user/getuserinfo`。宿主机与镜像内 `dingtalk.py`/`router.py` 已更新；API 镜像备份标签 `hengxin-smart-image-backend:d2e5076-pre-container`。未跑迁移 0011，未部署 13.2/13.3。
