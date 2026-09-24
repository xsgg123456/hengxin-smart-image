# VPS 开发测试部署

当前生产发布（2026-09-24 10:48）`annotation-20260924-6b43b3c`：前端0.2.5，API/CLI单张修改的单画布框选、画笔、拖动、原尺寸标注导出、编号意见与冻结重试已上线；schema0017，无迁移。安装镜像187项专项测试通过，前端/四个后端服务/native文件哈希、队列心跳、健康和公网登录页通过。维护必须在此前完整overlay链末尾追加本发布的api-override.yaml。备份与详情见 [标注功能发布记录](INLINE-ANNOTATION-RELEASE-20260924.md)。下方版本均为历史记录。

当前生产发布（2026-09-23 21:11）`inputs-20260923-b2841c7`：前端0.2.4，原图/素材对照、全局图片拖拽粘贴、模板弹窗居中及API单张多图修正已上线，数据库0017。API、两个outbox及API worker使用本次镜像；native CLI同步两份提示词源码。安装镜像153项测试通过，线上文件哈希、健康与匿名登录页验收通过。后续维护必须使用本次完整Compose overlay链，备份和细节见 [本次发布记录](IMAGE-INPUTS-RELEASE-20260923.md)。以下“最新”标识均为历史记录。

最新 UI/API 查询发布 `ui-20260922-a215301`：前端0.2.1及HTTP API已更新，保留独立API换套图模块。数据库仍0015，CLI/API生成worker与outbox未重启。HTTP API维护须带本发布api-override.yaml，不能使用旧CLI源码覆盖；详见 [本轮发布记录](UI-OPTIMIZATION-RELEASE-20260922.md)。以下标识为历史记录。

最新发布 `api-image-20260922-57ce288`：前端0.2.0、API及独立API worker/outbox已上线，迁移0015。原生CLI worker、CLI outbox及原CLI源码/配置保持原部署。新API镜像的构建源位于该发布目录src，维护必须带API Compose叠加文件。验收与回退见 [API换套图发布记录](API-IMAGE-RELEASE-20260922.md)。下方旧版本记录保留历史背景。

最新前端热修为 `ui-20260922-b086a49`：图片处理菜单每次进入独立新任务表单；仅前端替换，线上399文件、公网首页、健康及登录页检查通过。见 [菜单修复发布记录](NEW-TASK-MENU-20260922.md)。下方前端整批发布为其基础版本。

## 当前前端 · 2026-09-22

前端0.1.0已部署为 `ui-20260922-c837abf`，正式共享UI承接图片预览、模板选择、生成动效和紧凑上传。仅前端更新；后端仍为 `light-skills-20260921-f02b1e0`、迁移0014。399个文件哈希、公网首页、API健康及匿名登录页检查通过；登录后业务视觉和收费生图未在本次线上验收。备份、回滚和证据见 [本轮发布记录](UI-RELEASE-20260922.md)。以下较早记录保留历史背景，以本段及对应发布记录为准。

当前并发试运行：2026-09-17 Worker池、API/Worker部署容量和后台并发均已调至5，真实池5个子进程及健康检查通过，用户五任务压测待进行。覆盖配置与回退见 [五并发配置记录](CONCURRENCY-5-20260917.md)。下文历史并发1不代表当前值。

最新播报补丁：`skill-name-20260917-79892f0`，完整显示本轮绑定Skill名称，模型/提示词/Skill保持不变；备份及核验见 [发布记录](SKILL-NAME-DISPLAY-DEPLOYMENT.md)。

当前发布：2026-09-17 `final-reply-20260917-59d22f5`，简洁提示词与最终回复收图已上线，模型保持 Astra/high，两个业务 Skill 原样保留。发布凭据、备份与验收边界见 [最终回复收图发布记录](FINAL-REPLY-DELIVERY-DEPLOYMENT.md)。以下旧发布标识为历史背景。

最新生产模型更新：`model-20260917-0bb0454`，新任务和返工固定 `gpt-6-astra / high`。备份、验证与边界见 [ASTRA-HIGH-DEPLOYMENT.md](ASTRA-HIGH-DEPLOYMENT.md)。

## 本地 Skill 来源升级 · 2026-09-17

已部署 `skills-20260917-1d611e9`，迁移0012、API/Outbox/原生Worker/前端已同步，两个本地壁纸 Skill 已启用，普通版默认。实际验证、清理授权和依赖审计未通过项见 [发布记录](RELEASE-LOCAL-SKILLS-20260917.md)。原生Worker已配置 `LOCAL_SKILL_ROOT=/opt/hengxin-skills`。发布树由管理员维护且执行用户不可写；API无需挂载该目录。具体格式、检查、历史ZIP兼容和回滚限制见 [LOCAL-SKILL-RELEASES.md](LOCAL-SKILL-RELEASES.md)。下文现有VPS配置与历史ZIP安装根保留。

## 当前范围

当前文件描述 Phase 14.1 的 VPS 开发测试环境。目标主机为 Ubuntu 24.04 x86_64，主机名 `racknerd-058889d`。环境使用独立 Compose 项目 `hengxin-vps-staging`、独立数据库/Redis/MinIO 数据卷和独立运行目录，复用 VPS 上的 1Panel 但不接管 80/443。

该环境关闭 fixture，使用 VPS 上 `codex` 用户运行原生 Codex Worker。当前继续作为开发测试环境，已接入域名和 HTTPS，当前发布 `skills-20260917-1d611e9` / 迁移 `0012`；前端入口 `index-Bru91n64.js`（npm `dingtalk-jsapi`）。钉钉真实双端登录待验收。

## 目录与服务

- 应用目录：`/opt/hengxin-smart-image`
- API：Compose 内部服务，宿主机仅绑定 `127.0.0.1:18008`
- 前端：Compose 内 Nginx，宿主机绑定 `0.0.0.0:18080`，通过 VPS 公网 IP 访问
- PostgreSQL：宿主机 `127.0.0.1:15433`
- Redis：宿主机 `127.0.0.1:16388`
- MinIO API/Console：宿主机 `127.0.0.1:15900/15901`
- Codex Worker：`hengxin-vps-codex-worker.service`
- 本地 Skill：`/opt/hengxin-skills`；历史 ZIP 缓存：`/opt/hengxin-smart-image/infra/runtime/skills`
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

钉钉 PC 容器原先走 CDN `dingtalk-jsapi/2.15.15`，该地址 404。当时只覆盖 `frontend/dist`，入口脚本改为 `index-DePrnCPO.js`。后续 `99ff375` 已把 13.2/13.3 和迁移 0011 一并部署，本节只保留当时热修记录。

旧前端备份：`/opt/hengxin-smart-image/frontend/backups/dist.bak-20260916-180845.tar.gz`。回滚只解该包覆盖 `frontend/dist`，不要动 `.env` 和后端。公网首页与 JS 资源已 200；普通浏览器仍走网页授权，钉钉工作台需关掉重开后再点「重新授权」。

## 2026-09-16 提交 99ff375 部署（13.2/13.3 + 容器免登）

业务源码 `99ff375`；API/Outbox 镜像 `hengxin-smart-image-backend:99ff375`，迁移 `0011`，原生 Worker 同步源码并重启。前端正式构建入口仍为 `index-DePrnCPO.js`。匿名 auth/me、monitor、settings 返回 401；钉钉配置 200。未开启开发身份。真实双端登录和真实角色联调未验收。

回滚先确认无未结束任务，再停止本项目 outbox、API 和原生 Worker；恢复 `/opt/hengxin-backups/99ff375/` 中的后端源码和前端备份，镜像可退到 `container-auth-20260916` 或 `d2e5076`（d2e5076 不含容器免登换码，且迁移 0011 已执行，回退镜像前必须评估表结构，不能只换镜像当成完整回滚）。旧配置备份权限 600，保留数据卷。

## 2026-09-16 容器免登换码热修

钉钉 PC 容器 JSAPI 已能拿到免登码后，后端仍用网页 OAuth 的 `userAccessToken` 换码，钉钉拒绝后返回「钉钉认证服务暂不可用」。已改为 `topapi/v2/user/getuserinfo`。该换码随后并入 `99ff375` 镜像。API 镜像备份标签 `hengxin-smart-image-backend:container-auth-20260916`。
