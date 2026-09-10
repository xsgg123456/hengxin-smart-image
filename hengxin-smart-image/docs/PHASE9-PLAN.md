# Phase 9 执行计划

2026-09-10；技术验证通过，待用户验收。依据 Product-Spec v0.17 第9.1–9.2节、DEV-PLAN Phase9。实际证据见 PHASE9-VALIDATION.md。

1. 真实事件与产物收集：解析当前 CLI 的 JSONL 与会话记录，以明确 session/turn/call 关联原生图片，验证图片解码、数量、slot、目录边界及哈希；无图的文本回复不得成功，历史图片不得冒充本轮输出。
2. Linux 隔离运行：冻结素材与 Skill；每任务持久 home、每轮独立工作区。外层系统隔离只暴露该任务材料和必要运行时，不给执行进程业务数据库、其他任务目录或 Docker socket。用参数数组及 stdin 启动，记录进程身份，超时/取消停止整个执行树并核实退出。
3. 后端持久化：增加 session、attempt、usage、heartbeat；沿用 Phase8 的 PG 认领与发布屏障。失联先进入 uncertain，核实原进程及已有产物后处理，禁止盲目重跑。
4. 集成与交付：迁移、回归、两任务读写隔离、续接、取消、故障恢复及真实图片传输；独立审查通过后登记快照。未实测项不能标通过。

## 已取得的服务器证据

- Ubuntu 24.04 x86_64，CLI 0.153.4，codex 专用用户，ChatGPT 登录；真实文字调用与指定会话续接成功。
- 壁纸编辑成功；图片在 generated_images/<sessionId>/ 下，CLI 最终文字误报失败。必须由执行器校验真实产物，不能相信模型宣称。
- 当前版本二进制的 AppArmor userns 专用规则已安装，全局限制仍开启；这仅修复 CLI 内层沙箱，不能代替跨任务系统隔离。
- 主机约7.8GiB内存，检查时可用约2GiB，已有业务较多；容量不作承诺，集成测试使用独立环境及测试数据。

## 参数及实施约束

用户已确认：沿用专用身份、并发1、单轮60分钟、自动重跑0。Redis visibility timeout 采用4200秒，留10分钟收尾余量；参数冻结到轮次。正式生产发布不在本阶段。

隔离选型：Linux 原生 Worker 通过 Bubblewrap 创建外层文件系统/PID/IPC隔离，仅挂载本任务 home、本轮 work 和只读运行时；CLI 内层仍使用 workspace-write。生产接入不依赖SSH逐条遥控，也不向CLI暴露Docker socket。数据库、Redis、MinIO维持Compose部署；原生Worker以受控环境变量连接仅本机入口。此方案须通过服务器上的跨任务读写与父进程退出验证。

真实执行器已接入；2026-09-10 独立服务器测试完成 HTTP → PG → Celery → CLI → 原生图片校验 → MinIO → API 回传，单轮仅一次执行。详细证据见 PHASE9-VALIDATION.md；正式部署和三类 Skill 效果验收仍在后续阶段。
