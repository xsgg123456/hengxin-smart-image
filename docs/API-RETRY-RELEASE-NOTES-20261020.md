# 国内 API 重试发布准备 · 2026-10-20

本页记录发布入口与边界，尚不代表已生产部署。需求以 `API-RETRY-PLAN-20261020.md` 为准；实际发布、独立审查、Git 提交由主 Agent 完成。

## 生产只读基线

- 国内 schema `0030`，海外 `overseas_0019`，共用前端 `0.2.43`；国内 API/worker/outbox 使用同一固定镜像 ID `sha256:f0c46d55616ca905a0e7c2711aeb1aad7f5535f681c410192e041b5e53ba666f`。
- 实际 Compose 层数：国内 24、海外 19、身份 3。既有层按运行容器 labels 读取，不用仓库模板覆盖生产配置。
- 现有发布工具 current 指向 `retention-e6b2884be567085697d4048d9b9c82a2d94190d4`；本包包含相同新版镜像保留 helper，入口通过共用发布锁、版本台账及成功后收尾。
- 当前 API 图片项 398 成功、5 失败，75 个任务均终态。97 条历史 uncertain 尝试全部有完成时间，关联图片全部终态、无 lease token/lease deadline，且全部有同图更晚尝试。86 条关联成功图片、11 条关联失败图片。它们保留为历史审计；不删除、不重开、不计为当前发送占用。读证据：`output/api-retry-release/production-baseline.json`（忽略文件）。
- 排空仍阻挡任何非终态图片/任务、活动租约、running 尝试、channel.item_id 和处理中 CLI 修改，并检查 API Celery active/reserved/scheduled、broker 与 unacked。未知活动不会强停。

## 入口与发布范围

`scripts/release/package-api-retry.py` 复用现有已审源码/隐私/静态资源白名单，要求提交与审查快照一致、0031 迁移和前端 0.2.44 齐备。包名 `domestic-api-retry-20261020-<七位提交号>`。不带环境文件、业务图片、数据库和凭据；既有官方 PDF.js 资源白名单保留。

`scripts/release/api-retry-deploy.py` 继承国内发布的代理门禁、正式入口验证，复用现有镜像构建、安装测试、备份隔离恢复和 retention helper。只切换 `api`、`api-image-worker`、`api-image-outbox`，迁移仅运行国内 `migrate`。普通 outbox、缩略图、国内 CLI/删除/保留清理、认证 broker、海外及身份服务不重启。六个原生进程的 PID、工作目录、参数/环境摘要与配置文件摘要均需保持。

精确增量配置：请求 300 秒、下载 60 秒、租约 600 秒；共享发送间隔 5 秒、在途 10、失败阈值 5、冷却 60 秒。三个更新服务停机宽限 660 秒，队列可见性运行时校验至少 900 秒。发布停服务显式使用 `docker stop --timeout=-1`，客户端有总时限；超时只失败关闭入口，不让 Docker 强杀未知请求。[Docker 官方说明](https://docs.docker.com/reference/cli/docker/container/stop/)

## 主 Agent 的执行顺序

1. 完成全部测试、独立两阶段审查、中文提交后，在仓库执行 `hengxin-smart-image/backend/.venv/Scripts/python.exe scripts/release/package-api-retry.py`。检查 `package-audit.json`，传输归档后复核 SHA256、成员路径及清单，不复用历史包。
2. 将已核验发布包解包到 `/opt/hengxin-releases/<release>/src`；只从这份不可变、已审核的版本化包调用入口。它包含最新保留工具，三个阶段均自动持共用锁。
3. 服务器依次执行（`RELEASE` 替换为真实包名）：

```sh
python3 /opt/hengxin-releases/RELEASE/src/scripts/release/api-retry-deploy.py RELEASE build
python3 /opt/hengxin-releases/RELEASE/src/scripts/release/api-retry-deploy.py RELEASE prepare
python3 /opt/hengxin-releases/RELEASE/src/scripts/release/api-retry-deploy.py RELEASE deploy
```

`build` 安装测试和镜像源码哈希验证；`prepare` 固定真实拓扑、环境与新 overlay；`deploy` 关闭两层国内接纳入口→排空→停止三个 API 服务→备份完整国内库并隔离恢复→0031 增量迁移与原字段行指纹核验→安装新服务→原子切换共用 HTML→开放接纳→正式三服务健康与未变更服务验证→登记成功并回收。前端旧静态资源保留。

发布后需主 Agent 从正式浏览器核验重试/停止/等待/未知展示和已有图片/版本读取；本入口不自动提交任何收费模型请求。

## 回退边界

任何阶段失败均写 `RECOVERY_REQUIRED.json` 并关闭国内入口；不会自动恢复旧库、重启旧消费者或强停新在途请求。发布锁台账保留失败候选，主 Agent 必须按实际阶段恢复。

0031 只增加列并为旧策略保守填充计数；迁移后历史原字段必须完整保留。恢复接纳前写 `NEW_POLICY_MAY_BE_ACTIVE`，因为 outbox 即使在 HTTP 关闭时也可能运行。只要曾有 `retry_policy_version='bounded-v2' AND retry_cycle_id IS NOT NULL` 的轮次，旧代码不可直接消费该库，即使这些轮次已结束。脚本不提供自动 downgrade/recover；失败后优先保留新代码修复向前。

若准备考虑迁移前代码恢复，必须先确认实际 schema、当前轮次/lease/请求证据、代理关闭状态、备份完整性及没有接纳新写入；恢复快照不得覆盖新业务数据。主 Agent 需要单独形成可审查的恢复步骤，不能把备份存在当成可直接还原的依据。

## 本地隔离验证

- 14 项新入口/打包测试：故障注入、失败关闭、只更新三服务、配置白名单、历史周期门禁、排空顺序、禁止强杀、迁移必带与隐私白名单。
- 显式启用 `HX_API_RETRY_DOCKER_TEST=1` 的两项真实本地 Docker/PG 测试通过：Compose 时长规范化；忽略 TERM 的测试容器在客户端截止后仍存活；完整 dump 实际隔离恢复；0031 在真实 PostgreSQL 重复应用两次，旧字段指纹不变、旧失败不重开且计数保守迁移；downgrade 拒绝。仅使用唯一命名临时容器并全部收尾。
- 全部发布脚本回归：879 passed、3 skipped、309 subtests passed；两项 Docker 专项在默认回归中跳过，已按上一项显式补跑；Python 编译及 diff 空白检查通过。
- 生产至此只读；未执行部署、迁移、重启、清理、数据库写入或收费模型调用。
