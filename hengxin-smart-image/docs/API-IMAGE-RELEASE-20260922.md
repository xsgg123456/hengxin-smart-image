# 独立 API 换套图生产发布 · 2026-09-22

用户已授权提交 Git、打包并部署到现有 `https://zhitu.qhhengxin.top/`。本条替代开发阶段“不自动部署”的范围限制，不包含改造原 CLI 业务或移除历史数据。

## 发布计划与验收

1. 核对已审代码快照，前端版本更新0.2.0，独立worker使用部署的APP_IMAGE标签；审查发布增量后提交中文Git信息。
2. 构建正式前端，白名单归档后端代码/迁移/锁文件、正式静态文件和部署配置；排除密钥、环境文件、测试数据、缓存、Demo样图，核对文件哈希与依赖审计。
3. 服务器先构建新镜像，检查CLI无在途任务；短暂停止API接纳，二次确认任务为空，备份数据库、应用和受限配置。新增0015迁移只创建API独立表；不执行删表降级。
4. 服务端受限配置注入中转凭据，启动新版API和独立API worker/outbox，原CLI worker、CLI outbox、模型及五并发保持原运行配置。前端保留旧哈希资源，最后替换首页并重载Nginx。
5. 核对服务/队列、API路由鉴权、数据库版本、静态文件哈希、公开首页和浏览器登录入口。未取得真实登录态时，不绕过认证、不声称完成线上付费生成验收。

## 回退

保留旧API镜像、应用/前端/配置备份和数据库dump。失败时停止新API worker/outbox，恢复旧API配置/镜像和旧首页，重载Nginx，保留0015新增表和发布后数据。禁止直接恢复旧数据库覆盖新业务数据、禁止down -v。旧CLI服务不因新API回退而改配置。

## 当前基线

生产预检：主机racknerd-058889d，数据库0014，CLI job_records均终态（15成功、5失败），原生CLI worker active。API/CLI outbox镜像为light-skills-20260921-f02b1e0；磁盘可用67GiB。

## 已发布

- 功能提交 `57ce288e27b3105ca78a0a89455a16ead53f8f97`，发布编号 `api-image-20260922-57ce288`；前端0.2.0。
- 发布增量审查两阶段PASS，批准快照 `89aa8ad6f0fc1986b16967f332561d3ca9e3c9520f78a2998ae63787466ad743`，承接完整业务审查。类型检查通过、正式构建39.77秒。依赖审计critical0，既有high62/moderate39/low5，本轮没有依赖升级。
- 白名单574文件、5,116,502字节，包SHA256 `85b65beb117117c7b89897ca7684134ae95030f504ce738c0884496e0baa2640`。无凭据、环境文件、用户数据、开发路径或Demo样图。
- 发布源 `/opt/hengxin-releases/api-image-20260922-57ce288/src/`；deploy.log记录 `DEPLOY_COMPLETE`，deploy.exit=0。
- 备份 `/opt/hengxin-backups/api-image-20260922-57ce288/`，含数据库dump、旧应用/前端/配置及CLI进程标识；数据库dump已用pg_restore目录读取验证，未做恢复演练。
- 数据库0014→0015。API、api-image-worker、api-image-outbox使用新发布镜像；原生CLI worker进程号与CLI outbox容器ID前后相同，其模型、五并发、认证和运行配置均未修改。
- 三个新服务各143个后端文件哈希全部一致，线上424个前端文件哈希一致，公网首页哈希匹配。PG/Redis/MinIO readiness全部up，匿名auth/me及新模块status/tasks端点均401。
- 独立API worker ping正常，仅消费api_image_edits队列，配置enabled=true。服务器CDN解析为公网地址，中转站models接口200并列出目标模型。未在生产发起收费生成；开发阶段真实双图证据见API实施验证记录。
- 隔离浏览器访问真实HTTPS新模块路由，钉钉登录页正常，无脚本异常或5xx；没有现成真实登录态，因此登录后线上上传/生图尚未验收。未启用开发身份或绕过认证。

## 维护位置

原生CLI继续使用既有 `/opt/hengxin-smart-image/backend` 源码/venv及旧RELEASE.json；新API应用的源码位于上述不可变发布src目录、运行于新镜像，清单为 `/opt/hengxin-smart-image/API_IMAGE_RELEASE.json`。后续重建新API镜像须以该发布src为构建上下文，不能从旧CLI源码目录重建覆盖新镜像。前端清单FRONTEND_RELEASE.json已更新，旧哈希资源保留。

服务端凭据仅写入权限600的infra/.env，临时密钥传输文件已删除。维护新API服务需同时带 `-f compose.yaml -f compose.vps.yaml -f compose.api-image.yaml`，保留显式APP_IMAGE标签；CLI outbox仍使用其原运行镜像。
