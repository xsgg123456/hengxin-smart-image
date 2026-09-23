# 三项整改操作与验证

## 范围

1. CLI 中途 `Reconnecting... N/M (stream disconnected before completion: websocket closed by server before response.completed)` 仅视为待恢复通知；后续完成才消除它。普通错误、完成后的错误、失败终态仍拒绝。最终收图必须是最后回复明确的可读图片，校验路径、数量、格式；恢复收图要求退出凭据为0且无终止原因。
2. needrestart 对专用 `hengxin-vps-codex-worker.service` 设 override_rc=0。系统安全包继续更新；已运行进程使用旧库直到排空重启。配置不保护管理员直接强停、整机重启或硬件故障。
3. API 每站5个任务、每任务10张并发；第6排队。退避与批次间隙保留任务名额，结束释放；旧任务新修改重新排队。无数据库迁移、无前端改动。

## 受控维护

在生产 backend 目录、加载专用服务环境的管理进程中执行：

```sh
.venv/bin/python -m app.worker.maintenance --node hx-vps-codex@racknerd-058889d
.venv/bin/python -m app.worker.maintenance --node hx-vps-codex@racknerd-058889d --restart --wait-seconds 1800
```

默认只查状态。restart 命令先取消目标消费者，再检查 active/reserved/scheduled 与数据库在途记录，忙碌或不确定就等待，超时恢复消费并报错，绝不强停；重启后核验心跳、队列和服务PID。维护期间新任务可以入库排队。自动安全更新排除项安装到 `/etc/needrestart/conf.d/99-hengxin-worker.conf`，下次 needrestart 自动加载，不需重启业务进程。

依据：[Ubuntu 官方说明](https://discourse.ubuntu.com/t/needrestart-changes-in-ubuntu-24-04-service-restarts/44671)。每次需要启用更新后的运行库时，在上述维护流程排空后重启。

## 历史成品补收

仅处理诊断 3835912a-2655-45c7-9a5d-c5a2a565dd02 和 8628af76-8c41-49d8-a865-d249d9aaa3e9。`prepare_recollection` 先验证当前轮次、原进程死亡、exit0、同会话完成及最终图片，再将失败轮转待核实，交已有租约隔离的恢复器上传和发布。保留原错误于 observation.recollection，重复调用拒绝，不调用模型。取消/删除/新轮次或已有版本均拒绝。

## 发布和回退

先备份生产相关源码、needrestart配置和Compose覆盖文件，构建白名单后端镜像并验证安装产物。仅在各自Worker排空后切换。API使用新的专用overlay显式固定api/migrate/api-image-worker/api-image-outbox镜像，池大小5；CLI原生服务单独切换。

回退需再次排空，恢复旧源码和旧API镜像；保留数据库业务数据。五任务版本已经准入的任务必须先完成再退回旧单任务调度。成品补收不靠数据库备份回滚，保留已发布版本及审计。

## 验证证据

- 受控快照 `7cfc8a61e40aa537a55de0bd8b2d69c54f3948b6ffe968b6e003bbe7a0cda08f`，独立两阶段审查 PASS；独立专项126通过、1项Windows文件链接能力跳过。
- Linux完整后端：`docker run --rm --init ... python -m pytest tests -q -p no:cacheprovider`，1026通过、64条件跳过、15条既有警告。首次容器缺少init使测试控制器成为PID1，8个既有子进程监督测试触发父进程失效保护；补充init后全部通过。
- 新生产镜像在无网络隔离容器运行安装产物专项：156通过。compileall成功。
- 白名单包153文件，154030字节，SHA256 `f25179395febf18f480fc7499d3a68197691bed79ec40533460b9fa88be8db11`。凭据/私钥/个人目录扫描零问题。
- API三个服务均已安装 `hengxin-smart-image-backend:three-fixes-20260923`，每个服务150个后端文件哈希匹配。Celery池5，任务容量5、单任务图片容量10。派发暂停后确认API无在途调用再切换，恢复原paused=false；6笔历史API任务仍全部成功。
- 代理重载刷新新容器地址后，公开健康接口200、首页200、匿名auth/me 401。
- needrestart有效配置匹配专用服务且值为0；CLI服务保持运行，未因安装配置重启。
- 两笔补收预检：当前轮次未变、未删除、exit0、最终完成、进程已退出、各4张790×1500图片校验通过。原生Worker安全切换后已补收成功。

发布目录 `/opt/hengxin-releases/three-fixes-20260923`；备份目录 `/opt/hengxin-backups/three-fixes-20260923`。后续Compose维护必须包含本次 `api-override.yaml`。CLI切换与补收最终结果在收尾追加。


## 最终生产结果

- 原CLI最后一个任务于北京时间15:42:25自然完成后才切换，未强停任务。新Worker PID1040843，消费celery队列，心跳ready、容量5、CLI0.156.1；5个原生整改文件与发布包哈希一致。
- 两笔计划内误判补收完成：3835912a…、8628af76…，每轮4版本、succeeded、error=null、stage=completed，保留recollection审计。
- 排空结束的最后一笔“详情图测试2-IT”亦为同类旧代码误报：03f21453-f838-4554-9206-73c8b3e1b1b0，中途Reconnecting 2/2，最终交付4张，exit0，3540.231秒。用户明确批准后补收成功；共三轮12张，未调用模型重新生成。
- 备份backfill-before.json及backfill-third-before.json仅在服务器0700备份目录、文件0600保存；发布目录保存安装验证日志及补收结果。
- 三项整改上线完成。性能优化、恢复轮自动干预扩展继续暂缓。用户随后授权提交本地Git，未要求推送。
