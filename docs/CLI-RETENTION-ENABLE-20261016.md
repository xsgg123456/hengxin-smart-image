# 国内 CLI 自动清理生产启用 · 2026-10-16

状态：已于北京时间2026-10-16 13:43启用，13:44完成验证。仅配置现有清理能力，不修改业务源码或数据结构。

## 计划与验收

1. 核对线上原生执行路径、用户、环境文件、数据库迁移与清理状态；确认首次登记缓冲、活动保护和无待删除回执。保存服务/容器身份及配置基线。
2. 沿用国内原生 Worker 的用户、环境和执行根，安装独立 `hengxin-retention.service`；独立末层环境文件开启 `CLI_RETENTION_ENABLED=true`，批量25，`--loop`每小时扫描，开机自启。验收实际进程环境、服务状态及首轮 completed 日志。
3. 国内 Web API 追加仅该服务的环境覆盖，使管理中心清理状态与执行端一致；沿用全部现行 Compose 链和同一镜像，仅重建 Web API，不重启执行器、队列、海外或身份服务。验收健康、实际配置及其余进程/容器未变。
4. 只读核对初始化时间、下次缓存清理和7天历史期限，确认首轮没有立即清理历史；保存最终证据。不以首次空扫描宣称已验证7天后的生产删除。

## 回退

若启用验证失败，停止并禁用本次新增清理服务；仅在本次修改 Web API 配置后才恢复其原 Compose 链。保留登记/过期/pending状态，不恢复数据库或抹除清理屏障。原生生图服务和主动删除服务不做修改。

## 实际启用与证据

- 生产迁移0029，国内API及原生代码为已安装的domestic-20261015-4c64c1a；未重新构建或升级镜像。
- `/etc/systemd/system/hengxin-retention.service` 已安装，`active/running/enabled`，PID269605，重启次数0。运行用户codex、UMask0077，工作目录 `/opt/hengxin-native-releases/domestic-20261015-4c64c1a/backend`，命令为该环境Python执行 `-m app.retention.worker --loop`。
- 沿用 `/etc/hengxin-smart-image/worker.env` 和 `/opt/hengxin-releases/codex-astra-20261014/runtime.env`，末层新增root所有、0600的 `/etc/hengxin-smart-image/retention.env`：enabled=true、batch_size=25。实际进程确认节点hx-vps-codex、执行根 `/opt/hengxin-smart-image/infra/runtime/execution`。
- 国内API在全部原Compose链末尾追加 `/opt/hengxin-releases/retention-enable-20261016/api-retention.json`。合并配置差异仅为API的 `CLI_RETENTION_ENABLED=true`，同镜像单独重建API成功且healthy。管理中心执行配置函数实际返回 `{"enabled":true,"cacheIdleDays":1,"historyIdleDays":7}`；未绕过身份对外开放该接口。
- 首轮日志为 `{"status":"completed","resources":[],"objectsRemoved":0}`。保留表从4条未初始化变为20条active且全部initialized，cache_cleared/expired/errors均0，对象回执0。这里20为既有会话总数，不是首轮删除数量。
- 首次登记北京时间10月16日13:43:22，最早缓存到期10月17日13:43:22，最早历史到期10月23日13:43:22。后续有效活动会续期；实际处理仍受小时扫描、批量与执行保护约束。
- 前后核对国内CLI、主动删除、海外Worker/Outbox的4个PID和cwd均未变；除国内API外，21个运行容器的ID、启动时间和镜像均未变。
- 公开 `/api/v1/health/ready` 返回ready，PostgreSQL/Redis/MinIO均up。
- 受限证据目录 `/opt/hengxin-releases/retention-enable-20261016/` 保存baseline.json、首轮日志、配置和verification.json；不含在本地文档中公开的凭据。
- `systemd-analyze verify` 通过，输出两条既有1Panel服务StartLimitIntervalSec配置警告，与本次清理单元无关。
- 本轮验证的是安装、真实开关、首次登记与空扫描；未伪造时间、未提前删除真实数据，不声称24小时/7天后的生产回收已经发生。

## 后续发布影响

旧 `scripts/release/domestic-verify.py` 等发布检查仍假定自动清理关闭；后续国内发布需先适配该检查并处理清理服务的版本路径同步，不能直接用旧脚本覆盖本次开关。此次只记录影响，不扩大为发布工具代码改造。
